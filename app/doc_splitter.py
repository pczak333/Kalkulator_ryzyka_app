# -*- coding: utf-8 -*-
"""Segmentacja PDF na logiczne dokumenty (nakaz / pozew / inne).

Zaadaptowane z kodu archiwalnego (app_archiwalna.py, linie 4209–4468).
"""
from __future__ import annotations
import re
from typing import Optional

# Wzorce per strona — fallback gdy główne wzorce nie rozpoznają typu
_PAGE_DOC_PATTERNS = [
    (r"KOMORNIK\s+S[ĄA]DOW", "komornik", "Pismo komornika sądowego", "evidence", 2000),
    (r"WY[ŻZ][A-Z]+\s+KOMORNICZ", "komornik", "Pismo komornicze", "evidence", 2000),
    (r"TYT[UŁU][LŁ]\s+WYKONAW", "komornik", "Pismo komornicze (tytuł wykonawczy)", "evidence", 2000),
    (r"DECYZJA\s+(?:NR\s+)?\d", "decyzja_zus", "Decyzja organu", "primary", 2000),
    (r"ZAKŁAD\s+UBEZPIECZE[ŃN]", "decyzja_zus", "Decyzja ZUS", "primary", 2000),
    (r"WEZWANIE\s+DO\s+ZAP[LŁ]?AT", "wezwanie_zaplaty", "Wezwanie do zapłaty", "evidence", 2000),
]


def _classify_page_segment(page_text: str) -> Optional[tuple[str, str, str]]:
    """
    Klasyfikuje jedną stronę wg jej nagłówka (pierwsze 600 zn.).
    Zwraca (internal_doc_type, label, role) lub None jeśli kontynuacja poprzedniego.

    Kolejność reguł jest krytyczna:
    1. art. 299 KSH → zawsze POZEW niezależnie od "nakaz" w tekście
    2. Nagłówek nakazu (≤600 zn.) → NAKAZ (z rozróżnieniem nakazowe/upominawcze)
    3. Wezwanie przedsądowe → WEZWANIE (przed regułą POZEW)
    4. Strony pouczenia → None (kontynuacja nakazu, nie nowy dok.)
    5. Nagłówek pozwu (≤800 zn.) → POZEW
    6. Fallback wzorce per strona
    """
    tu = page_text.upper()

    # Reguła 0: EPU form code — definitywny identyfikator formularza EPU.
    # "KOD [hash]" (np. "KOD a6G1bśdóa6574ac39cd") pojawia się WYŁĄCZNIE na nagłówku
    # nakazu/pozwu EPU — nigdy w treści uzasadnienia ani żadnym innym tekście prawnym.
    # Azure DI wyciąga kod niezawodnie (tekst maszynowy, nie skan).
    if re.search(r"(?m)^\s*KOD\s+\S{5,}", tu[:300]):
        if re.search(r"(?m)P\s+O\s+Z\s+E\s+W|^\s*POZEW\b", tu[:800]):
            return ("pozew", "Pozew", "primary")
        if re.search(r"NAKAZ\s+ZAP", tu[:600]):
            if "UPOMINAWCZ" in tu:
                return ("nakaz_upominawczy", "Nakaz zapłaty (postępowanie upominawcze)", "evidence")
            return ("nakaz_nakazowy", "Nakaz zapłaty (postępowanie nakazowe)", "evidence")

    # Reguła 1: art. 299 KSH — strona zawiera pozew do zarządu
    if re.search(r"ART\.?\s*299.{0,20}K\.?S\.?H", tu):
        return ("pozew", "Pozew (art. 299 KSH)", "primary")

    # Reguła 5a: "P O Z E W" ze spacjami — PRZED Rule 2 (nakaz).
    # EPU pozew zawiera w treści formularza "nakaz zapłaty w postępowaniu upominawczym"
    # (żądanie od sądu). Gdyby Rule 2 była pierwsza, pozew byłby błędnie klasyfikowany
    # jako nakaz. "P O Z E W" ze spacjami to unikalny identyfikator EPU pozwu.
    if re.search(r"(?m)^[^A-Z]{0,10}P\s+O\s+Z\s+E\s+W\b", tu[:800]):
        return ("pozew", "Pozew", "primary")

    # Reguła 2: nagłówek nakazu — NAKAZ na początku linii w pierwszych 200 zn.
    # (?m)^\s* i okno 200 zn. chronią przed false-positives:
    # - pozew EPU: "żądam nakazu zapłaty w postępowaniu" — nakaz w środku zdania ✗
    # - uzasadnienie: "1. Nakaz zapłaty..." — nakaz po numerze listy ✗
    # - faktyczny nakaz EPU: "KOD [hash]\nNAKAZ ZAPŁATY\n..." — NAKAZ na początku linii ✓
    _head200 = tu[:200]
    if re.search(r"(?m)^\s*NAKAZ\s+ZAP[LŁ]?ATY[\s\S]{0,80}W\s+POST[EĘ]POWANIU", _head200):
        if "UPOMINAWCZ" in tu:
            return ("nakaz_upominawczy", "Nakaz zapłaty (postępowanie upominawcze)", "evidence")
        return ("nakaz_nakazowy", "Nakaz zapłaty (postępowanie nakazowe)", "evidence")

    # Reguła 2b: nakaz bez polskich znaków (garbled OCR z Tesseract)
    if re.search(r"(?m)^\s*NAKAZ\s+ZAPLATY[\s\S]{0,80}W\s+POSTEPOWANIU", _head200):
        if "UPOMINAWCZ" in tu:
            return ("nakaz_upominawczy", "Nakaz zapłaty (postępowanie upominawcze)", "evidence")
        return ("nakaz_nakazowy", "Nakaz zapłaty (postępowanie nakazowe)", "evidence")

    # Reguła 2d: strona uzasadnienia → kontynuacja, nie nowy dokument.
    # Obrona drugiej linii gdy Azure DI zwraca "UZASADNIENIE" w rozpoznawalnej formie.
    if re.search(r"[ŁL]?UZASADNIENIE", tu):
        return None

    # Reguła 3: wezwanie przedsądowe (przed POZEW, żeby "WEZWANIE DO ZAPŁATY" nie trafiało jako POZEW)
    _is_nakaz_or_pozew_page = (
        bool(re.search(r"(?m)^[^A-Z]{0,5}POZEW\b", tu)) or
        bool(re.search(r"(?m)^[^A-Z]{0,5}NAKAZ\s+ZAP", tu))
    )
    if not _is_nakaz_or_pozew_page:
        if (
            re.search(r"PRZED[SŚ][AĄ]DOW\w{0,3}\s+WEZWANIE", tu) or
            re.search(r"(?m)^\s*WEZWANIE\s+DO\s+ZAP[LŁ]?AT", tu)
        ):
            return ("wezwanie_zaplaty", "Wezwanie do zapłaty (przedsądowe)", "evidence")

    # Reguła 4: strony pouczenia to kontynuacja nakazu, nie nowy dokument
    # Bez tej ekskluzji "pozew" zawinięty przez OCR na początek linii w pouczeniu
    # tworzyłby false-positive dokument "Pozew"
    _is_pouczenie_page = bool(
        re.search(r"(?m)^\s*POUCZENIE\b", tu[:400]) or
        re.search(r"SPOSOB\s+ZASKARZENIA\s+NAKAZU|SPOSÓB\s+ZASKARŻENIA\s+NAKAZU", tu[:600]) or
        re.search(r"SRODEK\s+ZASKARZENIA.*SPRZECIW|ŚRODEK\s+ZASKARŻENIA.*SPRZECIW", tu[:600])
    )
    if not _is_pouczenie_page:
        # Reguła 5b: POZEW bez spacji na początku linii w nagłówku (≤800 zn.)
        if re.search(r"(?m)^[^A-Z]{0,5}POZEW\b", tu[:800]):
            return ("pozew", "Pozew", "primary")

    # Reguła 6: fallback przez wzorce ogólne
    best_pos = len(page_text) + 1
    best_result = None
    for pat, doc_type, label, role, max_pos in _PAGE_DOC_PATTERNS:
        m = re.search(pat, page_text[:max_pos].upper(), re.IGNORECASE)
        if m and m.start() < best_pos:
            best_pos = m.start()
            best_result = (doc_type, label, role)
    return best_result


def detect_documents_by_pages(full_text: str) -> list[dict]:
    """
    Dzieli tekst (z separatorami '--- STRONA X ---') na logiczne dokumenty.
    Zwraca [] jeśli plik zawiera tylko 1 logiczny dokument lub brak separatorów.

    Struktura każdego słownika:
      text:     str        — tekst segmentu (bez separatorów)
      pages:    list[int]  — numery stron wchodzących w skład segmentu
      doc_type: str        — wewnętrzny typ (nakaz_nakazowy, pozew, ...)
      role:     str        — "primary" | "evidence"
      label:    str        — etykieta do wyświetlania
    """
    if not full_text:
        return []

    page_pattern = re.compile(r"---\s*STRONA\s+(\d+)\s*---", re.IGNORECASE)
    parts = page_pattern.split(full_text)

    # parts = [tekst_przed_str1, "1", tekst_str1, "2", tekst_str2, ...]
    pages: list[tuple[int, str]] = []
    if parts[0].strip():
        pages.append((0, parts[0]))  # tekst przed pierwszym separatorem
    for i in range(1, len(parts), 2):
        page_num = int(parts[i]) if parts[i].strip().isdigit() else 0
        page_text = parts[i + 1] if i + 1 < len(parts) else ""
        pages.append((page_num, page_text))

    if not pages:
        return []

    # Grupuj strony w dokumenty wg klasyfikacji per strona
    documents: list[dict] = []
    current_doc: dict | None = None

    for page_num, page_text in pages:
        classification = _classify_page_segment(page_text)

        if classification:
            doc_type, label, role = classification
            if current_doc is not None and current_doc["doc_type"] == doc_type:
                # Kontynuacja tego samego dokumentu (np. nakaz rozciąga się na 3 strony)
                current_doc["pages"].append(page_num)
                current_doc["text"] += "\n" + page_text
            else:
                if current_doc is not None:
                    documents.append(current_doc)
                current_doc = {
                    "doc_type": doc_type,
                    "label": label,
                    "role": role,
                    "pages": [page_num],
                    "text": page_text,
                }
        elif current_doc is not None:
            # Kontynuacja — strona pouczenia, uzasadnienia, itp.
            current_doc["pages"].append(page_num)
            current_doc["text"] += "\n" + page_text
        else:
            # Strony przed pierwszym rozpoznanym nagłówkiem
            current_doc = {
                "doc_type": "unknown",
                "label": "Dokument",
                "role": "primary",
                "pages": [page_num],
                "text": page_text,
            }

    if current_doc is not None:
        documents.append(current_doc)

    # Usuń "unknown" tylko gdy są inne dokumenty
    documents = [d for d in documents if d["doc_type"] != "unknown" or len(documents) == 1]

    # Przypisz role wg kontekstu bundla
    _nakaz_types = {"nakaz_upominawczy", "nakaz_nakazowy"}
    _pozew_types = {"pozew"}
    _has_nakaz = any(d["doc_type"] in _nakaz_types for d in documents)
    _has_pozew = any(d["doc_type"] in _pozew_types for d in documents)

    _is_art299_bundle = bool(
        re.search(r"art\.?\s*299.{0,20}k\.?s\.?h", full_text, re.IGNORECASE)
    )

    if _has_nakaz and _has_pozew:
        # Nakaz EPU = wymaga sprzeciwu w krótkim terminie → zawsze primary.
        # Art. 299 override stosujemy TYLKO gdy nakaz jest starym nakazem wobec spółki
        # (nie EPU), a pozew art. 299 to nowe, osobne postępowanie — wtedy pozew pilniejszy.
        _has_epu_nakaz = any(
            d["doc_type"] in _nakaz_types and
            re.search(r"Nc-e|e-[Ss][aą]d|\bEPU\b", d["text"], re.IGNORECASE)
            for d in documents
        )
        if _is_art299_bundle and not _has_epu_nakaz:
            # Stary nakaz wobec spółki + nowy pozew art. 299 → pozew pilniejszy
            for d in documents:
                if d["doc_type"] in _pozew_types:
                    d["role"] = "primary"
                elif d["doc_type"] in _nakaz_types:
                    d["role"] = "evidence"
        else:
            # EPU nakaz lub zwykły nakaz+pozew → nakaz pilniejszy (sprzeciw 14 dni)
            for d in documents:
                if d["doc_type"] in _nakaz_types:
                    d["role"] = "primary"
                elif d["doc_type"] in _pozew_types:
                    d["role"] = "evidence"

    if len(documents) <= 1:
        return []  # Zestawienie bez sensu dla jednego dokumentu

    return documents
