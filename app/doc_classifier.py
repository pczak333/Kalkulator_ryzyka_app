# -*- coding: utf-8 -*-
"""Klasyfikuje typ dokumentu na podstawie tekstu i CSV 07."""
from __future__ import annotations
import re
import pandas as pd

_CSV_PATH = "../dane_wejściowe/csv/07_3_Typy_dokumentow.csv"
_EXCLUDE_TYPES = {"DOKUMENT_NIECZYTELNY", "DOKUMENT_NIEPRAWNY", "DOKUMENT_NIEUSTALONY_PRAWNY"}

def _load_doc_types() -> pd.DataFrame:
    return pd.read_csv(_CSV_PATH, sep=";", encoding="utf-8-sig", header=1)


def _score_text(text: str, keywords_raw: str, signals_raw: str) -> int:
    """Liczy punkty za trafienia słów kluczowych i sygnałów silnych."""
    score = 0
    if isinstance(keywords_raw, str):
        for kw in keywords_raw.split(";"):
            kw = kw.strip()
            if kw and re.search(re.escape(kw), text, re.IGNORECASE):
                score += 1
    if isinstance(signals_raw, str):
        for sig in signals_raw.split(";"):
            sig = sig.strip()
            if sig and re.search(re.escape(sig), text, re.IGNORECASE):
                score += 3  # sygnały silne ważą 3×
    return score


def classify_document(text: str, fields: dict) -> tuple[str, float]:
    """
    Zwraca (doc_type_code, confidence) gdzie confidence ∈ [0.0, 1.0].
    Używa CSV 07: słowa kluczowe + sygnały silne + bonus za EPU i adresata.
    """
    # Obrona drugiej linii: jeśli segment zaczyna się od nagłówka UZASADNIENIE,
    # to nie jest nakaz ani pozew — to kontynuacja pozwu (tabela dowodów, uzasadnienie).
    # Azure DI może garblować "UZASADNIENIE" jako "ŁUZASADNIENIE" (garbled first char).
    # 500 zn.: str.3 ma ~50 zn. garblowanej tabeli, potem "ŁUZASADNIENIE" at ~90 zn.
    _head_500 = text[:500].upper()
    if re.search(r"[ŁL]?UZASADNIENIE", _head_500):
        return "PISMO_PROCESOWE_SADOWE", 0.55

    # (03.07.2026) Sądowe doręczenie nakazu z pouczeniem — pismo przewodnie
    # sądu, nie sam nakaz. Bez tego shortcutu segment doręczenia (który
    # wielokrotnie wymienia "nakaz zapłaty" i zawiera "w terminie dwóch
    # tygodni" w pouczeniu) klasyfikował się jako NAKAZ i WYGRYWAŁ wybór
    # dokumentu głównego z właściwym nakazem (dłuższy tekst = więcej trafień).
    # POTWIERDZENIE_DORECZENIA: czy_moze_byc_glowny=NIE (CSV 07), -20 pkt w
    # selektorze, status POMOCNICZY_DORECZENIE — dokładnie właściwa rola.
    # (04.07.2026) Zawężone jak Reguła 1e splittera: tytuł na początku linii
    # + strona bez nagłówka POUCZENIE (klauzula o doręczeniu zagranicznym w
    # pouczeniu nakazu zawiera "gdy doręczenie nakazu zapłaty ma mieć
    # miejsce..." i bez kotwicy strony pouczenia łapały ten shortcut).
    if (re.search(r"(?m)^[^A-ZĄĆĘŁŃÓŚŹŻ]{0,5}DOR[EĘ]CZENIE[\s\S]{0,40}NAKAZU", _head_500)
            and not re.search(r"(?m)^\s*POUCZENIE\b", text[:400].upper())):
        return "POTWIERDZENIE_DORECZENIA", 0.85

    df = _load_doc_types()
    scores: dict[str, int] = {}
    # Surowe wyniki czysto tekstowe (słowa kluczowe + sygnały silne, PRZED
    # bonusami EPU/adresata) — miara faktycznych dowodów w treści dokumentu.
    # Bonusy potrafią wynieść typ do zwycięstwa przy zerowych/śladowych
    # trafieniach tekstowych, więc do oceny "czy to w ogóle pismo prawne"
    # służą wyłącznie wyniki surowe.
    raw_scores: dict[str, int] = {}

    for _, row in df.iterrows():
        code = str(row.get("document_type_code", "")).strip()
        if not code or code in _EXCLUDE_TYPES:
            continue

        base = _score_text(
            text,
            str(row.get("slowa_kluczowe", "")),
            str(row.get("sygnaly_silne", "")),
        )
        raw_scores[code] = base

        # Bonus za EPU
        if fields.get("epu") and code.startswith("EPU_"):
            base += 5

        # Bonus za adresata — główny wyróżnik między _CZLONEK_ZARZADU i _SPOLKA
        adresat = fields.get("adresat")
        if adresat == "czlonek_zarzadu" and "_CZLONEK_ZARZADU" in code:
            base += 15
        elif adresat == "spolka" and ("_SPOLKA" in code or code.endswith("_SPOLKA")):
            base += 15
        elif adresat == "organ" and ("ZUS" in code or "ORGAN" in code or "US_" in code):
            base += 15
        elif code == "PISMO_PROCESOWE_SADOWE" and adresat in ("czlonek_zarzadu", "spolka"):
            base += 15
        # Typy bez sufiksu _SPOLKA/_CZLONEK_ZARZADU w nazwie (dokument ma tę
        # samą treść niezależnie od tego, czy dłużnikiem jest spółka, czy
        # osoba fizyczna — np. wniosek do komornika czy postanowienie o
        # umorzeniu nie różnią się brzmieniem) muszą dostać ten sam bonus, co
        # sufiksowane typy — inaczej systematycznie przegrywają scoring z
        # KAŻDYM konkurentem typu "_SPOLKA"/"_CZLONEK_ZARZADU" niezależnie od
        # dopasowania słów kluczowych (odkryte 02.07.2026: scalony segment
        # wniosku egzekucyjnego/postanowienia o umorzeniu klasyfikował się
        # jako NAKAZ_SPOLKA tylko dlatego, że NAKAZ_SPOLKA ma "_SPOLKA" w
        # nazwie, a WNIOSEK_EGZEKUCYJNY/UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC —
        # nie).
        elif code in ("WNIOSEK_EGZEKUCYJNY", "UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC") and adresat in ("czlonek_zarzadu", "spolka"):
            base += 15

        if base > 0:
            scores[code] = base

    # Formuła operatywna nakazu ("nakazuję pozwanemu") jako pozytywny sygnał dla NAKAZ_.
    # [\s\S]{0,15} zamiast \s+ — odporna na łamania linii w tabelach EPU (OCR).
    # Bonus zamiast kary: gdy OCR nie wyciągnie frazy, NAKAZ nie jest penalizowany —
    # o wyniku decydują wtedy słowa kluczowe (nakaz zapłaty > pozew).
    _has_nakaz_formula = bool(re.search(
        r"nakazuj[eę][\s\S]{0,15}pozwan",
        text, re.IGNORECASE
    ))
    if _has_nakaz_formula:
        for _c in list(scores):
            if "NAKAZ_" in _c:
                scores[_c] += 20

    # Frazy wnosicielskie lub tytuł "P O Z E W" jako pozytywny sygnał dla POZEW_.
    # Wykluczenie: wniosek wierzyciela o wszczęcie postępowania egzekucyjnego
    # (pismo DO komornika) też zawiera "wnoszę o" w petitum ("niniejszym
    # wnoszę o: 1. Wszczęcie i przeprowadzenie egzekucji...") — bez tego
    # wykluczenia bonus POZEW błędnie podbijał EPU_POZEW_*/POZEW_* dla takiego
    # pisma, mimo że to nie jest żaden pozew do sądu.
    _is_wniosek_egzekucyjny = bool(re.search(
        r"WNIOSEK\s+O\s+WSZCZ[EĘ]CIE\s+POST[EĘ]POWANIA\s+EGZEKUCYJ",
        text, re.IGNORECASE
    ))
    # (03.07.2026) Pismo komornicze (nagłówek kancelarii komorniczej w
    # pierwszych ~600 zn.) też nie jest pozwem — urzędowy formularz skargi
    # na czynności komornika zawiera "wnoszę o" w petitum i bez tego
    # wykluczenia bonus POZEW błędnie podbijał POZEW_* dla pism komornika.
    # (04.07.2026) Drugi, DETERMINISTYCZNY sygnał: kind segmentu ze splittera
    # (fields["splitter_kind"], nadawany po nagłówku kancelarii komorniczej
    # na PIERWSZEJ stronie segmentu) — strony kontynuacji (boilerplate
    # pouczeń k.p.c., formularze) nie mają nagłówka w swoich pierwszych
    # 600 zn., więc sam test tekstowy ich nie łapał.
    _splitter_kind = str(fields.get("splitter_kind") or "")
    _is_komornik_segment = (_splitter_kind.startswith("komornik")
                            or _splitter_kind == "pismo_komornicze")
    _is_komornik_letter = _is_komornik_segment or bool(re.search(
        r"KOMORNIK\s+S[ĄA]DOW|KANCELARIA\s+KOMORNICZ",
        text[:600], re.IGNORECASE
    ))
    _has_pozew_signals = bool(re.search(
        r"(wnosimy\s+o|wnosz[eę]\s+o|P\s+O\s+Z\s+E\s+W)",
        text, re.IGNORECASE
    )) and not _is_wniosek_egzekucyjny and not _is_komornik_letter
    if _has_pozew_signals:
        for _c in list(scores):
            if "POZEW" in _c:
                scores[_c] += 20

    # (04.07.2026) Segment rozpoznany przez splitter jako pismo komornicze
    # (kind z nagłówka kancelarii) dostaje deterministyczny bonus dla
    # PISMO_KOMORNIK_* — boilerplate pouczeń k.p.c. w takich pismach CYTUJE
    # "nakaz zapłaty" (klauzule o tytułach wykonawczych) i przy niekorzystnej
    # wariancji OCR segment potrafił sklasyfikować się jako NAKAZ_* (raz
    # wygrywając nawet wybór dokumentu głównego z kwotą "2000 zł" z przepisu
    # o grzywnie). Bonus omija typy egzekucyjne, które już są komornicze.
    if _is_komornik_segment:
        _kom_code = ("PISMO_KOMORNIK_CZLONEK_ZARZADU"
                     if fields.get("adresat") == "czlonek_zarzadu"
                     else "PISMO_KOMORNIK_SPOLKA")
        scores[_kom_code] = scores.get(_kom_code, 0) + 25

    # Disambiguacja: sąd vs. komornik na podstawie wyciągniętego sad_organ.
    # (03.07.2026) KOMORNIK ma pierwszeństwo: kancelaria komornicza zawsze
    # urzęduje "przy Sądzie Rejonowym X", więc nazwa organu zawiera OBA słowa
    # ("komornik" i "sąd") — poprzedni warunek `_is_bailiff and not _is_court`
    # nigdy nie działał dla prawdziwych pism komorniczych (kary się nie
    # naliczały i np. POZEW_SPOLKA wygrywał z PISMO_KOMORNIK_SPOLKA).
    _sad_organ = (fields.get("sad_organ") or "").lower()
    if _sad_organ:
        _is_court   = "sąd" in _sad_organ or "sad" in _sad_organ
        _is_bailiff = "komornik" in _sad_organ
        if _is_bailiff:
            for _c in list(scores):
                if "KOMORNIK" not in _c and "UMORZENIE" not in _c and "EGZEKUCYJNY" not in _c:
                    scores[_c] = max(0, scores[_c] - 15)
        elif _is_court:
            for _c in list(scores):
                if "KOMORNIK" in _c:
                    scores[_c] = max(0, scores[_c] - 25)

    if not scores:
        return "DOKUMENT_NIEUSTALONY_PRAWNY", 0.0

    # Najmocniejszy dowód TEKSTOWY w całym dokumencie (bez bonusów).
    _max_raw = max(raw_scores.values()) if raw_scores else 0

    # Dokument niezwiązany ze sprawą (03.07.2026): AI (ai_extractor) czytała
    # pełny tekst i orzekła, że to NIE jest pismo prawne (czy_pismo_prawne=False
    # — np. potwierdzenie przelewu, faktura, wyciąg), a trafienia słów
    # kluczowych są śladowe (< 4 = brak sygnału silnego i najwyżej 3 słabe
    # słowa). Koniunkcja chroni przed fałszywym alarmem AI na zgarbolonym OCR
    # prawdziwego pisma — takie pismo i tak trafia mocno w słowa kluczowe.
    # Bez tej reguły przelew bankowy z frazą "Zarząd Cmentarzy Komunalnych"
    # dostawał ODPIS_KRS z pewnością 0.85 (jedno słabe słowo "zarząd").
    if fields.get("czy_pismo_prawne") is False and _max_raw < 4:
        return "DOKUMENT_NIEPRAWNY", 0.9

    # Backstop bez AI (brak klucza API / błąd AI → brak pola czy_pismo_prawne):
    # jeśli najmocniejszy dowód tekstowy to pojedyncze słabe słowo (≤ 1)
    # i nie odpaliła żadna formuła operatywna nakazu/pozwu — nie ma podstaw
    # do klasyfikacji; wcześniej jedyny kandydat dostawał pewność 0.85
    # z jednego przypadkowego trafienia. Gdy AI orzekła czy_pismo_prawne=True,
    # backstop NIE działa (ufamy AI — segment może być zgarbolonym fragmentem
    # prawdziwego pisma). Kind komorniczy ze splittera to również dowód
    # (nagłówek kancelarii) — taki segment nie jest "nieustalony".
    if (fields.get("czy_pismo_prawne") is None and _max_raw <= 1
            and not _has_nakaz_formula and not _has_pozew_signals
            and not _is_komornik_segment):
        return "DOKUMENT_NIEUSTALONY_PRAWNY", 0.3

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_code, best_score = sorted_scores[0]

    if len(sorted_scores) >= 2:
        second_score = sorted_scores[1][1]
        confidence = best_score / (best_score + second_score) if (best_score + second_score) > 0 else 0.5
    else:
        confidence = 0.85  # jedyny kandydat

    # Jeśli EPU nie jest zaznaczone ale kod wymaga EPU — degraduj
    if not fields.get("epu") and best_code.startswith("EPU_"):
        non_epu = [(c, s) for c, s in sorted_scores if not c.startswith("EPU_")]
        if non_epu:
            best_code, best_score = non_epu[0]
            confidence = min(confidence, 0.7)

    return best_code, round(confidence, 3)
