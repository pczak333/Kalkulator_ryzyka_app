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
    # max_pos=800 (03.07.2026): tytuł prawdziwego wezwania jest w nagłówku
    # strony; cytowania w Dowód:/Załącznikach leżą głębiej — patrz Reguła 3.
    (r"WEZWANIE\s+DO\s+ZAP[LŁ]?AT", "wezwanie_zaplaty", "Wezwanie do zapłaty", "evidence", 800),
]

# Tytuły pism komorniczych (Reguła 1d) — na poziomie modułu, bo lista jest
# potrzebna też poza _classify_page_segment(). Wzorce tolerują udokumentowane
# artefakty OCR z realnych skanów (05.07.2026, egzekucja+zaj._rach.+wyk._majatku.pdf):
# - "WEZWANIE DO ZLOZENIA WYKAZU MAJ }" (ucięta końcówka) → bez wymogu "MAJĄTKU",
#   sam zwrot "wezwanie do złożenia wykazu" jest wystarczająco charakterystyczny;
# - "ZAJĘCIE WIE RZYTELNOŚCI" / "ZAJECIU W IERZYTELNOŚCI" (spacja wtrącona
#   w środek słowa) → \s* między pierwszymi literami słowa "wierzytelności";
# - (15.07.2026) "ZAJĘCIU WIEFR YTELNOŚCI" (wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf):
#   głębsze zniekształcenie niż sama spacja — "RZ" odczytane jako "FR" (literowa
#   pomyłka OCR, nie tylko wtrącona spacja), więc \s*-tolerancja w środku słowa
#   nie wystarczyła. Wzorzec nie wymaga już poprawnego odczytu prefiksu
#   "WIE...RZ" w ogóle — wystarczy "ZAJĘCI[EU]" w pobliżu (do 25 zn.) końcówki
#   "YTELNOŚCI", unikalnej dla słowa "wierzytelności" (żadne inne powszechne
#   słowo prawne nie kończy się na "ytelności"), więc nie grozi to fałszywymi
#   dopasowaniami mimo luźniejszego okna;
# - mianownik i celownik tytułu ("ZAJĘCIE"/"ZAJĘCIU" rachunku bankowego).
# - (16.07.2026) "WEZWANIE DŁUŻNIKA do złożenia wykazu majątku" (ten sam plik
#   testowy, segment [7-8]) NIE pasowało do wzorca wezwania o wykaz — regex
#   wymagał "WEZWANIE" wprost przed "DO", a prawdziwy tytuł wstawia "DŁUŻNIKA"
#   między nimi; segment dostawał wtedy generyczną etykietę "Pismo komornicze"
#   zamiast konkretnej ("Wezwanie do złożenia wykazu majątku") — sama granica
#   strony/segmentu była poprawna, to była tylko luka jakości etykiety w UI.
#   Naprawione opcjonalnym `(?:D[LŁ]U[ŻZ]NIKA\s+)?` między "WEZWANIE" i "DO".
_KOMORNIK_TITLES = [
    (r"ZAWIADOMIENIE\s+O\s+WSZCZ[EĘ]CIU\s+POST[EĘ]POWANIA\s+EGZEKUCYJ",
     "komornik_wszczecie_egzekucji", "Zawiadomienie o wszczęciu egzekucji"),
    (r"ZAJ[EĘ]CI[EU]\s+RACHUNKU\s+BANKOW",
     "komornik_zajecie_rachunku", "Zajęcie rachunku bankowego"),
    (r"WEZWANIE\s+(?:D[LŁ]U[ŻZ]NIKA\s+)?DO\s+Z[LŁ]O[ŻZ]ENIA\s+WYKAZU",
     "komornik_wezwanie_wykaz", "Wezwanie do złożenia wykazu majątku"),
    (r"(?m)^\s*WYKAZ\s+MAJ[AĄ]TKU",
     "komornik_wykaz_majatku", "Wykaz majątku"),
    (r"ZAJ[EĘ]CI[EU][\s\S]{0,25}?YTELNO[SŚ]CI",
     "komornik_zajecie_wierzytelnosci", "Zajęcie wierzytelności"),
    (r"SKARGA\s+NA\s+CZYNNO[SŚ][CĆ][I]?\s+KOMORNIKA",
     "komornik_skarga", "Skarga na czynności komornika (formularz)"),
    # (14.07.2026) Postanowienie o PODJĘCIU (wznowieniu) wcześniej zawieszonego
    # postępowania egzekucyjnego — notyfikacja o kontynuacji ZNANEJ sprawy, nie
    # nowa czynność egzekucyjna ani nowe żądanie (w odróżnieniu od pozostałych
    # kindów wyżej). Osobny kind, żeby app.py mógł pokazać łagodniejszy baner
    # (patrz app.py, gałąź komornicza) zamiast "najpóźniejszy etap sprawy,
    # wymaga szybkiej reakcji" — ten tekst pasuje do zajęcia majątku, nie do
    # informacyjnego wznowienia. Zgłoszenie użytkownika (KS_postanowienie.pdf):
    # dokument dostawał generyczny kind "pismo_komornicze" i alarmistyczny baner.
    (r"PODJ[AĄ][ĆC]\s+ZAWIESZON\w*\s+POST[EĘ]POWANIE\s+EGZEKUCYJ",
     "komornik_podjecie_zawieszonego", "Podjęcie zawieszonego postępowania"),
]

# Reguła 1d': formularze komornicze BEZ nagłówka kancelarii na stronie —
# urzędowy formularz skargi i wzór wykazu majątku to załączniki drukowane z
# własnym tytułem na samej górze, bez papieru firmowego komornika, więc
# Reguła 1d (wymagająca nagłówka kancelarii w pierwszych 600 zn.) ich nie
# widzi i strony spadały do generycznego fallbacku Reguły 6 ("komornik").
# Okna pozycji celowo ciasne (tytuł formularza jest na górze strony) —
# wzmianki o skardze/wykazie w pouczeniach innych pism leżą głębiej.
_KOMORNIK_FORM_TITLES = [
    (r"URZ[EĘ]DOWY\s+FORMULARZ\s+SKARGI|SKARGA\s+NA\s+CZYNNO[SŚ][CĆ][I]?\s+KOMORNIKA",
     "komornik_skarga", "Skarga na czynności komornika (formularz)", 600),
    (r"(?m)^[^\n]{0,60}?WYKAZ\s+MAJ[AĄ]TKU",
     "komornik_wykaz_majatku", "Wykaz majątku", 400),
]

# Tytuł pisma procesowego w toku postępowania (05.07.2026): pismo
# przygotowawcze, odpowiedź na sprzeciw/pozew, replika. Kotwica początku
# linii + negative lookahead na "Z DNIA" odróżniają WŁASNY tytuł strony od
# cytowań w treści innych pism ("...w piśmie przygotowawczym z dnia 30
# stycznia...", "doręcza odpis pisma przygotowawczego z dnia..."). Ten sam
# wzorzec ma doc_classifier.py (early-return PISMO_PROCESOWE_SADOWE).
_PISMO_PROC_TITLE_RE = re.compile(
    r"(?m)^\s{0,5}(?:PISM[OA]\s+PRZYGOTOWAWCZ\w*"
    r"|ODPOWIED[ZŹŻ]\s+NA\s+(?:SPRZECIW|POZEW)\w*"
    r"|REPLIKA\b)"
    r"(?!\s+Z\s+DNIA)"
)


def _is_evidence_citation(tu: str, pos: int) -> bool:
    """Czy dopasowanie w pozycji `pos` (w tekście już zuppercase'owanym `tu`) to
    cytowanie dowodu/załącznika ("Dowód: wezwanie do zapłaty...", "- wezwanie
    do zapłaty...") a nie własny nagłówek/tytuł strony. Bez tego sprawdzenia
    fraza "wezwanie do zapłaty" wymieniona jako pozycja dowodowa w uzasadnieniu
    pozwu (lub w liście załączników) fałszywie klasyfikuje całą stronę jako
    osobny dokument "Wezwanie do zapłaty".

    (03.07.2026) Kontekst rozszerzony z 40 do 200 zn. wstecz + dodatkowy test
    na słowa DOWÓD/ZAŁĄCZNIK/W ZAŁĄCZENIU gdziekolwiek w tym oknie: OCR potrafi
    zawinąć długi wiersz listy załączników tak, że "wezwanie do zapłaty..."
    zaczyna nową linię BEZ wypunktowania bezpośrednio przed dopasowaniem
    (np. "- wezwanie do zapłaty do pozwanego z dnia 24 października 2022 roku
    wraz z dowodem nadania," łamane po "roku") — wtedy stary guard przepuszczał
    i ostatnia strona pozwu stawała się osobnym "dokumentem"."""
    ctx = tu[max(0, pos - 200):pos]
    ctx_tail = ctx[-40:]
    if re.search(r"DOW[OÓ]D\s*:?\s*$", ctx_tail) or re.search(r"[-–—•]\s*$", ctx_tail):
        return True
    return bool(re.search(r"DOW[OÓ]D|ZA[LŁ][AĄ]CZNIK|W\s+ZA[LŁ][AĄ]CZENIU", ctx))


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
    # Okno KOD: pełny tekst strony — pdfplumber może wyciągać pola formularza w dowolnej kolejności.
    if re.search(r"(?m)^\s*KOD\s+\S{5,}", tu):
        # Szukaj "P O Z E W" w PEŁNYM tekście — może pojawić się po 800 znaku
        if re.search(r"(?m)P\s+O\s+Z\s+E\s+W|^\s*POZEW\b", tu):
            return ("pozew", "Pozew", "primary")
        if re.search(r"NAKAZ\s+ZAP", tu[:600]):
            if "UPOMINAWCZ" in tu:
                return ("nakaz_upominawczy", "Nakaz zapłaty (postępowanie upominawcze)", "evidence")
            return ("nakaz_nakazowy", "Nakaz zapłaty (postępowanie nakazowe)", "evidence")

    # Reguła 1a (05.07.2026): pismo procesowe w toku postępowania — tytuł
    # "PISMO PRZYGOTOWAWCZE"/"ODPOWIEDŹ NA SPRZECIW/POZEW"/"REPLIKA" na
    # początku linii w nagłówku strony (pierwsze ~2500 zn. — tytuł leży po
    # bloku adresowym, w pismo_przygotowawcze_kontynuacja.pdf ~390 zn. od
    # góry). MUSI być PRZED Regułą 1: pismo przygotowawcze w sprawie z
    # art. 299 KSH cytuje ten przepis wielokrotnie i bez tej reguły strona
    # tytułowa pisma dostawała kind "pozew".
    _pp_m = _PISMO_PROC_TITLE_RE.search(tu[:2500])
    if _pp_m and not _is_evidence_citation(tu, _pp_m.start()):
        return ("pismo_procesowe", "Pismo procesowe (kontynuacja postępowania)", "evidence")

    # Reguła 1a' (15.07.2026): wyrok zaoczny — ten sam sygnał co early-return
    # w doc_classifier.py (formuła "W IMIENIU RZECZYPOSPOLITEJ POLSKIEJ" +
    # "WYROK...ZAOCZNY" występuje WYŁĄCZNIE w wyrokach, nigdy w nakazach
    # zapłaty), ale tu na poziomie STRONY — bez tej reguły strona wyroku nie
    # pasowała do ŻADNEJ reguły splittera (klasyfikator ma swój wyrokowy
    # early-return od 07.07.2026, ale działa dopiero na już sklejonym
    # segmencie — za późno, by wytyczyć granicę strony), wpadała w
    # None/kontynuację i cicho doklejała się do sąsiedniego pisma
    # komorniczego (zgłoszenie użytkownika 15.07.2026,
    # wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf: str.1-4 wyroku sklejone ze
    # str.5-6 zawiadomienia o wszczęciu egzekucji w jeden fałszywy segment
    # str.1-6). MUSI być PRZED Regułą 1 (art. 299 → pozew): uzasadnienie
    # wyroku przeciw spółce mogłoby cytować art. 299 KSH na stronie
    # tytułowej. Strony kontynuacji (uzasadnienie, str. 2-4) nie mają
    # własnego "W IMIENIU..." i nie złapią tej reguły — jeśli cytują
    # art. 299, Reguła 1 może je błędnie odciąć jako "pozew"; naprawia to
    # Krok -3 niżej (rozszerzony o kind "wyrok_zaoczny", tym samym wzorcem
    # co już istniejący dla "pismo_procesowe").
    if (re.search(r"(?m)^\s{0,5}WYROK\b[\s\S]{0,20}?ZAOCZN\w*", tu[:800])
            and re.search(r"W\s+IMIENIU\s+RZECZYPOSPOLITEJ\s+POLSKIEJ", tu[:800])):
        return ("wyrok_zaoczny", "Wyrok zaoczny", "primary")

    # Reguła 1: art. 299 KSH — strona zawiera pozew do zarządu
    if re.search(r"ART\.?\s*299.{0,20}K\.?S\.?H", tu):
        return ("pozew", "Pozew (art. 299 KSH)", "primary")

    # Reguła 1b: wniosek wierzyciela o wszczęcie postępowania egzekucyjnego —
    # pismo DO komornika, nie pozew ani nakaz. Musi być wykryte PRZED Regułą 2d
    # (UZASADNIENIE→None), bo takie pismo bywa wielostronicowe i nie ma
    # własnej sekcji uzasadnienia, ale sąsiaduje z dokumentami, które ją mają.
    # Okno nagłówka (2000 zn.) + guard cytowania chroni przed złapaniem
    # wzmianki o takim wniosku w liście dowodów/załączników innego pisma.
    _wniosek_egz_m = re.search(r"WNIOSEK\s+O\s+WSZCZ[EĘ]CIE\s+POST[EĘ]POWANIA\s+EGZEKUCYJ", tu[:2000])
    if _wniosek_egz_m and not _is_evidence_citation(tu, _wniosek_egz_m.start()):
        return ("wniosek_egzekucyjny", "Wniosek o wszczęcie postępowania egzekucyjnego", "evidence")

    # Reguła 1c: postanowienie komornika o umorzeniu postępowania egzekucyjnego.
    # Wymaga nagłówka "POSTANOWIENIE" WSPÓŁWYSTĘPUJĄCEGO z "KOMORNIK" w oknie
    # pierwszych ~500 zn. (analogicznie do Reguły 2 dla nakazu — nagłówek, nie
    # gdziekolwiek w tekście) ORAZ sentencji umorzenia gdziekolwiek na stronie.
    # Sam nagłówek "POSTANOWIENIE" jest zbyt ogólny (każde orzeczenie sądu), a
    # samo "umorzyć postępowanie egzekucyjne" bywa CYTOWANE w uzasadnieniu
    # pozwu art. 299 jako dowód bezskuteczności egzekucji — nie chcemy urwać
    # takiej strony od pozwu. Wymóg obu naraz + nagłówek w oknie ogranicza to
    # do stron będących WŁASNYM postanowieniem komornika. Bez guardu
    # _is_evidence_citation() — sentencja postanowienia legalnie wylicza swoje
    # punkty jako "- umorzyć...", "- ustalić..." itd.; ten sam wzorzec
    # wypunktowania, który dla INNYCH reguł odróżnia cytat dowodu od nagłówka,
    # tu fałszywie łapałby WŁASNĄ treść postanowienia jako "cytowanie".
    _head500 = tu[:500]
    if "POSTANOWIENIE" in _head500 and "KOMORNIK" in _head500:
        _umorzenie_m = re.search(
            r"UMORZY[ĆC]\s+(?:Z\s+URZ[EĘ]DU\s+)?POST[EĘ]POWANIE\s+EGZEKUCYJ"
            r"|POST[EĘ]POWANIE\s+EGZEKUCYJNE[\s\S]{0,60}UMORZ",
            tu
        )
        if _umorzenie_m:
            return ("postanowienie_umorzenie_egzekucji", "Postanowienie o umorzeniu postępowania egzekucyjnego", "evidence")

    # Reguła 1d (03.07.2026): pisma komornicze — strona zaczynająca się od
    # nagłówka kancelarii komorniczej ("Komornik Sądowy przy Sądzie Rejonowym
    # ...", "Kancelaria Komornicza nr ...") to POCZĄTEK nowego pisma
    # komorniczego; strony kontynuacji (boilerplate k.p.c., pouczenia) nie
    # mają tego nagłówka → None → doklejane do bieżącego segmentu. Tytuł
    # pisma (w pierwszych ~2500 zn., bo nagłówek+adresat+tabela tytułu
    # wykonawczego potrafią zająć górną połowę strony) daje ODRĘBNY kind per
    # rodzaj pisma — różne kindy tworzą osobne segmenty mimo scalania
    # segmentów tego samego typu w detect_documents_by_pages(); bez tego
    # 18-stronicowa paczka 7 pism komorniczych sklejała się w jeden segment
    # (a jeden segment → detect_documents zwraca [] → cały plik szedł do
    # klasyfikatora jako jeden dokument). MUSI być PO Regule 1c —
    # postanowienie o umorzeniu też ma nagłówek komorniczy.
    # (15.07.2026) Bramka rozszerzona: nagłówek kancelarii bywa na tyle
    # silnie zniekształcony przez OCR (np. "Kaemornik Sądowy"/"Kancelaria
    # Kuojnomicza"), że nie pasuje do żadnego wariantu regexu, mimo że tytuł
    # WŁAŚCIWEGO pisma na tej samej stronie ("ZAWIADOMIENIE O ZAJĘCIU
    # WIEFR YTELNOŚCI..." — wstawiona losowa litera w środek słowa, inny typ
    # zniekształcenia niż dotąd tolerowany) jest odczytany na tyle dobrze, że
    # pasuje. Dodatkowy sygnał "SYGN" w pierwszych 700 zn. (skrócone "Sygn."/
    # "Sygn. akt" przed numerem sprawy komorniczej — obecne na KAŻDEJ
    # stronie rozpoczynającej nowe pismo komornicze w tym pliku testowym,
    # nieobecne na ŻADNEJ stronie kontynuacji) otwiera próbę dopasowania
    # tytułu z `_KOMORNIK_TITLES` NAWET gdy nagłówek kancelarii zawiódł.
    # Bez tej zmiany strona spadała do generycznego fallbacku Reguły 6
    # (kind "komornik") i doklejała się do POPRZEDNIEGO pisma komorniczego w
    # Kroku -2 — mimo że była NOWYM, odrębnym pismem (zgłoszenie użytkownika
    # 15.07.2026, wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf: str.13-14
    # "Zawiadomienie o zajęciu wierzytelności" sklejone ze str.11-12 "Zajęcie
    # rachunku bankowego" w jeden fałszywy segment str.11-14).
    # WAŻNE: fallback "pismo_komornicze" (gdy ŻADEN konkretny tytuł nie
    # pasuje) pozostaje warunkowany WYŁĄCZNIE czystym nagłówkiem, nie samym
    # "SYGN" — inne typy pism (nakaz, pozew) też zwykle mają "Sygn. akt" w
    # nagłówku, więc sam ten sygnał, bez pasującego tytułu komorniczego, nie
    # jest wystarczającym dowodem, że to pismo komornicze (musi przejść do
    # dalszych reguł: 1e/2/2b/3/5a/5a'/6). Guard `_is_evidence_citation()` w
    # pętli dopasowania chroni przed złapaniem tytułu WYMIENIONEGO w liście
    # dowodów/załączników innego pisma — ten sam mechanizm, co Reguła 1b/1a.
    _kom_letterhead = bool(re.search(r"KOMORNIK\s+S[ĄA]DOW|KANCELARIA\s+KOMORNICZ", tu[:600]))
    _kom_sygn = bool(re.search(r"SYGN", tu[:700]))
    if _kom_letterhead or _kom_sygn:
        _kom_head = tu[:2500]
        # (14.07.2026) Dopasowanie wg NAJWCZEŚNIEJSZEJ pozycji w tekście, nie
        # wg kolejności na liście _KOMORNIK_TITLES (wzorem Reguły 6 niżej) —
        # boilerplate pouczenia "Skarga na czynność komornika... w terminie
        # 7 dni" (art. 767 KPC) występuje w niemal KAŻDYM piśmie komorniczym,
        # więc wzorzec `komornik_skarga` fałszywie dopasowywał się do tego
        # akapitu, a przy dopasowaniu wg kolejności listy wygrywał z
        # prawdziwym tytułem dokumentu, jeśli `komornik_skarga` był bliżej
        # początku listy niż faktyczny typ. Ujawnione przy dodaniu
        # `komornik_podjecie_zawieszonego` (postanowienie ma własny tytuł
        # wcześnie w tekście, ale boilerplate skargowy w Pouczeniu dalej też
        # pasuje do wzorca `komornik_skarga` i był sprawdzany pierwszy).
        _best_pos = len(_kom_head) + 1
        _best_result = None
        for _pat, _kind, _label in _KOMORNIK_TITLES:
            _m = re.search(_pat, _kom_head)
            if _m and _m.start() < _best_pos and not _is_evidence_citation(tu, _m.start()):
                _best_pos = _m.start()
                _best_result = (_kind, _label, "evidence")
        if _best_result:
            return _best_result
        if _kom_letterhead:
            return ("pismo_komornicze", "Pismo komornicze", "evidence")

    # Reguła 1d' (05.07.2026): formularze komornicze bez nagłówka kancelarii
    # (urzędowy formularz skargi, wzór wykazu majątku) — rozpoznawane po
    # własnym tytule na górze strony; patrz komentarz przy _KOMORNIK_FORM_TITLES.
    for _pat, _kind, _label, _win in _KOMORNIK_FORM_TITLES:
        if re.search(_pat, tu[:_win]):
            return (_kind, _label, "evidence")

    # Reguła 1e (03.07.2026): sądowe doręczenie nakazu zapłaty z pouczeniem —
    # pismo przewodnie sądu ("DORĘCZENIE NAKAZU ZAPŁATY W POSTĘPOWANIU
    # UPOMINAWCZYM Z POUCZENIEM"), po którym następują strony pouczenia.
    # Bez tej reguły strony doręczenia+pouczenia były "unknown", a nuklearne
    # scalanie (Krok 1 niżej) przemianowywało je na "pozew" — w efekcie UI
    # pokazywało DWA nakazy, a dokumentem głównym zostawało doręczenie
    # (bez kwoty) zamiast właściwego nakazu. Okno 600 zn.: tytuł leży po
    # nagłówku sądu i polu adresata (~250-400 zn.).
    # ZAWĘŻENIE (04.07.2026): (1) tytuł musi być na POCZĄTKU linii — strony
    # POUCZENIA nakazu zawierają w treści frazę "gdy doręczenie nakazu
    # zapłaty ma mieć miejsce poza granicami..." (klauzula o doręczeniu
    # zagranicznym) i bez kotwicy linia środkowa uruchamiała regułę
    # (nakaz_zapłaty+pozew.pdf str.3-8 odcinały się jako fałszywe
    # "doręczenie"); (2) strona z nagłówkiem POUCZENIE na górze to strona
    # pouczenia, nie pismo przewodnie.
    if (re.search(r"(?m)^[^A-ZĄĆĘŁŃÓŚŹŻ]{0,5}DOR[EĘ]CZENIE[\s\S]{0,40}NAKAZU", tu[:600])
            and not re.search(r"(?m)^\s*POUCZENIE\b", tu[:400])):
        return ("doreczenie_sadowe", "Doręczenie nakazu z pouczeniem", "evidence")

    # Reguła 5a: "P O Z E W" ze spacjami — PRZED Rule 2 (nakaz).
    # EPU pozew zawiera w treści formularza "nakaz zapłaty w postępowaniu upominawczym"
    # (żądanie od sądu). Gdyby Rule 2 była pierwsza, pozew byłby błędnie klasyfikowany
    # jako nakaz. "P O Z E W" ze spacjami to unikalny identyfikator EPU pozwu.
    # Okno: pełny tekst (tytuł może być poza pierwszymi 800 znakami).
    if re.search(r"(?m)^[^A-Z]{0,10}P\s+O\s+Z\s+E\s+W\b", tu):
        return ("pozew", "Pozew", "primary")

    # Reguła 5a': "P O Z E W" gdziekolwiek w tekście — fallback gdy Rule 5a nie odpala.
    # Rule 5a wymaga początku linii z max 10 nieduże znaki przed P, co może nie zadziałać
    # gdy pdfplumber wyciąga "FORMULARZ: P O Z E W" jako jedną linię z wielką literą F.
    # Bez anchora: wystarczy że "P O Z E W" (ze spacjami) pojawi się gdziekolwiek.
    if re.search(r"P\s+O\s+Z\s+E\s+W", tu):
        return ("pozew", "Pozew", "primary")

    # Reguła 2d: strona uzasadnienia → kontynuacja, nie nowy dokument.
    # Przeniesiona PRZED Rule 2 — gdy Azure DI zwraca UZASADNIENIE w rozpoznawalnej formie,
    # daje szansę na prawidłowy None zanim "NAKAZ ZAPŁATY" z nagłówka EPU wywoła Rule 2.
    if re.search(r"[ŁL]?UZASADNIENIE", tu):
        return None

    # Reguła 2: nagłówek nakazu — NAKAZ na początku linii w pierwszych 200 zn.
    # Guard "P O Z E W": formularze EPU powtarzają nagłówek "NAKAZ ZAPŁATY W POSTĘPOWANIU"
    # na KAŻDEJ stronie — w tym na stronach uzasadnienia pozwu (str.3–4). Jeśli strona
    # zawiera "P O Z E W" gdziekolwiek → to formularz pozwu EPU, nie samodzielny nakaz.
    _head200 = tu[:200]
    if re.search(r"(?m)^\s*NAKAZ\s+ZAP[LŁ]?ATY[\s\S]{0,80}W\s+POST[EĘ]POWANIU", _head200):
        if re.search(r"P\s+O\s+Z\s+E\s+W", tu):
            return None
        if "UPOMINAWCZ" in tu:
            return ("nakaz_upominawczy", "Nakaz zapłaty (postępowanie upominawcze)", "evidence")
        return ("nakaz_nakazowy", "Nakaz zapłaty (postępowanie nakazowe)", "evidence")

    # Reguła 2b: nakaz bez polskich znaków (garbled OCR z Tesseract)
    if re.search(r"(?m)^\s*NAKAZ\s+ZAPLATY[\s\S]{0,80}W\s+POSTEPOWANIU", _head200):
        if re.search(r"P\s+O\s+Z\s+E\s+W", tu):
            return None
        if "UPOMINAWCZ" in tu:
            return ("nakaz_upominawczy", "Nakaz zapłaty (postępowanie upominawcze)", "evidence")
        return ("nakaz_nakazowy", "Nakaz zapłaty (postępowanie nakazowe)", "evidence")

    # Reguła 3: wezwanie przedsądowe (przed POZEW, żeby "WEZWANIE DO ZAPŁATY" nie trafiało jako POZEW)
    _is_nakaz_or_pozew_page = (
        bool(re.search(r"(?m)^[^A-Z]{0,5}POZEW\b", tu)) or
        bool(re.search(r"(?m)^[^A-Z]{0,5}NAKAZ\s+ZAP", tu))
    )
    if not _is_nakaz_or_pozew_page:
        # (03.07.2026) Okno ograniczone do pierwszych 800 zn.: PRAWDZIWE
        # wezwanie ma tytuł w nagłówku strony (także po papierze firmowym —
        # np. "OSTATECZNE PRZEDSĄDOWE WEZWANIE DO ZAPŁATY" InterRisk zaczyna
        # się ~400-600 zn. od góry). Cytowania w "Dowód:"/liście załączników
        # leżą głęboko na stronie (w art.299_pozew str.6 w ~2/3 strony) —
        # limit pozycji odcina je nawet, gdy guard cytowań by nie zadziałał.
        _wez_m = (
            re.search(r"PRZED[SŚ][AĄ]DOW\w{0,3}\s+WEZWANIE", tu[:800]) or
            re.search(r"(?m)^\s*WEZWANIE\s+DO\s+ZAP[LŁ]?AT", tu[:800])
        )
        # Guard: jeśli dopasowanie jest poprzedzone etykietą "Dowód:" lub
        # wypunktowaniem (lista załączników), to cytowanie dowodu w innym
        # piśmie, nie własny nagłówek strony — nie klasyfikuj jako wezwanie.
        if _wez_m and not _is_evidence_citation(tu, _wez_m.start()):
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
        if re.search(r"(?m)^[^A-Z]{0,5}POZEW\b", tu):
            return ("pozew", "Pozew", "primary")

    # Reguła 4b: klauzula wykonalności → kontynuacja poprzedniego nakazu/wyroku,
    # nie nowy dokument. Boilerplate klauzuli (art. 776 k.p.c.) bywa na osobnej
    # stronie zaraz po treści nakazu — bez tej reguły fallback Reguła 6
    # ("TYTUŁ WYKONAW...", bo klauzula zawiera "Tytuł wykonawczy wydano...")
    # błędnie zaczynał od niej nowy segment "komornik", odcinając stronę
    # klauzuli od nakazu, którego dotyczy.
    if re.search(r"UPRAWNIA\s+DO\s+EGZEKUCJI|PODLEGA\s+WYKONANIU\s+JAKO\s+PRAWOMOCNE", tu):
        return None

    # Reguła 6: fallback przez wzorce ogólne
    best_pos = len(page_text) + 1
    best_result = None
    for pat, doc_type, label, role, max_pos in _PAGE_DOC_PATTERNS:
        window = page_text[:max_pos].upper()
        m = re.search(pat, window, re.IGNORECASE)
        if m and m.start() < best_pos:
            # To samo zabezpieczenie co w Regule 3: fraza cytowana jako dowód/
            # załącznik ("Dowód: wezwanie...", "- wezwanie...", "- Tytuł
            # wykonawczy [oryginał]" w liście załączników wniosku do komornika)
            # nie jest nagłówkiem strony. Dotyczy KAŻDEGO wzorca fallback, nie
            # tylko wezwania — lista załączników potrafi wymienić dowolny typ
            # pisma po nazwie.
            if _is_evidence_citation(window, m.start()):
                continue
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

    # Post-processing: scal fragmenty formularza EPU przed nakazem w jeden segment pozwu.
    #
    # Problem: wielostronicowy EPU PDF ma: [pozew str.1-3] [tabela dowodów str.4→wezwanie_zaplaty]
    # [nakaz str.5-7 z KOD]. Strona 4 (tabela dowodów) zawiera w liście dowodów tytuł
    # "Wezwanie do zapłaty" → Rule 3 błędnie klasyfikuje ją jako wezwanie.
    # Powinna być scalona z pozwem.
    #
    # Zasada: wszystkie segmenty PRZED pierwszym nakazem z KOD = strony formularza EPU
    # (pozew + załączniki) — scalane w jeden "pozew" w Kroku 1, chyba że wśród nich
    # jest własny segment typu nakaz (wtedy działa węższy Krok 0 poniżej).
    _KOD_RE = re.compile(r"(?m)^\s*KOD\s+\S{5,}")
    _nakaz_set = {"nakaz_upominawczy", "nakaz_nakazowy"}

    # Krok -3 (05.07.2026): strony kontynuacji pisma procesowego złapane przez
    # Regułę 1 (art. 299 → "pozew") → scal z poprzedzającym segmentem
    # pismo_procesowe. Pismo przygotowawcze w sprawie z art. 299 KSH cytuje
    # ten przepis na WIELU stronach (nie tylko tytułowej), a Reguła 1 działa
    # per strona — nie można jej zawęzić bez psucia bundli EPU (tam strona
    # uzasadnienia z art. 299 MUSI dostawać "pozew", żeby scalać się z
    # formularzem pozwu). Scalamy więc po fakcie, ale TYLKO segmenty bez
    # własnego tytułu pozwu (line-start "POZEW"/"P O Z E W") i bez kodu
    # formularza EPU ("KOD [hash]") — prawdziwy pozew zawsze ma jedno z dwóch.
    # (15.07.2026) Zbiór celów scalania rozszerzony o "wyrok_zaoczny" — ten
    # sam problem: strona uzasadnienia wyroku cytująca art. 299 KSH nie ma
    # własnego "W IMIENIU..." (Reguła 1a' wymaga tego w oknie 800 zn.), więc
    # Reguła 1 mogłaby ją błędnie odciąć jako "pozew"; te same guardy
    # (brak własnego tytułu pozwu, brak KOD) chronią prawdziwy, samodzielny
    # pozew przed połknięciem.
    _POZEW_TITLE_RE = re.compile(r"(?m)^[^A-ZĄĆĘŁŃÓŚŹŻ]{0,10}POZEW\b|P\s+O\s+Z\s+E\s+W")
    _PISMO_PROC_MERGE_TARGETS = {"pismo_procesowe", "wyrok_zaoczny"}
    _merged_pp: list[dict] = []
    for _d in documents:
        _du = _d["text"].upper()
        if (_d["doc_type"] == "pozew" and _merged_pp
                and _merged_pp[-1]["doc_type"] in _PISMO_PROC_MERGE_TARGETS
                and not _POZEW_TITLE_RE.search(_du)
                and not _KOD_RE.search(_du)):
            _merged_pp[-1]["pages"].extend(_d["pages"])
            _merged_pp[-1]["text"] += "\n" + _d["text"]
        else:
            _merged_pp.append(_d)
    documents = _merged_pp

    # Krok -2 (05.07.2026): strony kontynuacji pism komorniczych złapane przez
    # fallback Reguły 6 (kind "komornik": strona BEZ nagłówka kancelarii w
    # pierwszych 600 zn., ale z "TYTUŁ WYKONAW..."/"KOMORNIK SĄDOW..." głębiej
    # — tabela tytułu wykonawczego, pouczenia k.p.c., podpis komornika na
    # ostatniej stronie) → scal z poprzedzającym pismem komorniczym. Nowe
    # pismo komornicze ZAWSZE zaczyna się nagłówkiem kancelarii (Reguła 1d)
    # albo tytułem formularza (Reguła 1d'), więc segment "komornik" tuż po
    # segmencie komorniczym to kontynuacja, nie osobny dokument. Bez tego
    # kroku str.2-4 (pouczenia zawiadomienia o wszczęciu egzekucji) odcinały
    # się jako "Pismo komornicze (tytuł wykonawczy)", a segment wszczęcia
    # (sama str.1) tracił kwotę i pouczenia — i przegrywał wybór dokumentu
    # głównego. wniosek_egzekucyjny celowo POZA zbiorem celów scalania (jak
    # w Kroku -1) — nie ruszać bundli art. 299.
    # (15.07.2026) postanowienie_umorzenie_egzekucji DOŁĄCZONE do celów
    # scalania — prawdziwe postanowienia komornika o umorzeniu bywają
    # dwustronicowe (sentencja + rozliczenie kosztów egzekucji na str. 2, bez
    # własnego nagłówka kancelarii/POSTANOWIENIE). Bez tego wpisu strona
    # kosztów spadała do generycznego fallbacku "komornik" i — nie mogąc się
    # skleić z poprzedzającym postanowieniem — szła do klasyfikatora jako
    # OSOBNY dokument, gdzie słowa kluczowe kosztów egzekucyjnych dawały jej
    # PISMO_KOMORNIK_SPOLKA zamiast UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC
    # (zgłoszenie: art299_pozew_nakaz_umorz._egzek..pdf, str.12-13 rozjechane
    # na dwa aux zamiast jednego). Bezpieczne dla ochrony bundli art. 299 z
    # Kroku -1 opisanej wyżej — ten krok tylko DOKLEJA generyczną kontynuację
    # BEZPOŚREDNIO PO postanowieniu, nie przesuwa granic segmentów wstecz.
    # (15.07.2026) wyrok_zaoczny DOŁĄCZONY do celów scalania — strona
    # kontynuacji wyroku (np. z podpisem/pieczęcią komornika egzekwującego
    # wyrok gdzieś na dole strony) złapana przez generyczny fallback Reguły 6
    # (kind "komornik") powinna doklejać się z powrotem do wyroku, nie
    # stawać się osobnym segmentem. Bezpieczne: ten krok reaguje TYLKO na
    # generyczny kind "komornik" (nigdy na konkretnie nazwany
    # komornik_wszczecie_egzekucji itp.), więc nie skleja wyroku z sąsiednim,
    # odrębnie tytułowanym pismem komorniczym. Celowo NIE dołączony do
    # _komornik_kinds w Kroku -1 niżej — wyrok to odrębny dokument
    # egzekwowany przez otaczające pisma komornicze, nie fragment paczki
    # egzekucyjnej (analogicznie do celowo wykluczonego wniosek_egzekucyjny).
    _KOMORNIK_MERGE_TARGETS = {
        "komornik_wszczecie_egzekucji", "komornik_zajecie_rachunku",
        "komornik_wezwanie_wykaz", "komornik_wykaz_majatku",
        "komornik_zajecie_wierzytelnosci", "komornik_skarga",
        "pismo_komornicze", "komornik", "postanowienie_umorzenie_egzekucji",
        "wyrok_zaoczny",
    }
    _merged_kom: list[dict] = []
    for _d in documents:
        if (_d["doc_type"] == "komornik" and _merged_kom
                and _merged_kom[-1]["doc_type"] in _KOMORNIK_MERGE_TARGETS):
            _merged_kom[-1]["pages"].extend(_d["pages"])
            _merged_kom[-1]["text"] += "\n" + _d["text"]
        else:
            _merged_kom.append(_d)
    documents = _merged_kom

    # Krok -1 (04.07.2026): spójność paczki komorniczej. Segment typu nakaz/
    # pozew WCIŚNIĘTY między segmenty komornicze to prawie na pewno źle
    # odcięty fragment pisma komorniczego, nie samodzielny dokument: tabela
    # "Tytuł wykonawczy" cytuje pełny tytuł nakazu ("Nakaz zapłaty w
    # postępowaniu upominawczym Sądu..."), a wielostronicowy boilerplate
    # pouczeń k.p.c. bywa RÓŻNIE transkrybowany przez OCR między
    # uruchomieniami (udokumentowana wariancja Azure DI) — raz strona wraca
    # jako kontynuacja (None), raz łapie regułę nakazu/pozwu. Scal taki
    # segment z poprzedzającym segmentem komorniczym. Warunek "przed i po
    # jest segment komorniczy" chroni prawdziwe bundle (np. art299: nakaz
    # leży między POZWEM a wnioskiem egzekucyjnym — wniosek_egzekucyjny i
    # postanowienie_umorzenie NIE są w _komornik_kinds, więc reguła śpi).
    _komornik_kinds = {
        "komornik_wszczecie_egzekucji", "komornik_zajecie_rachunku",
        "komornik_wezwanie_wykaz", "komornik_wykaz_majatku",
        "komornik_zajecie_wierzytelnosci", "komornik_skarga",
        "pismo_komornicze", "komornik",
    }
    if sum(1 for d in documents if d["doc_type"] in _komornik_kinds) >= 2:
        _coherent: list[dict] = []
        for _i, _d in enumerate(documents):
            _prev_is_kom = bool(_coherent) and _coherent[-1]["doc_type"] in _komornik_kinds
            _next_is_kom = any(
                documents[_j]["doc_type"] in _komornik_kinds
                for _j in range(_i + 1, len(documents))
            )
            if (_d["doc_type"] in (_nakaz_set | {"pozew"})
                    and _prev_is_kom and _next_is_kom):
                _coherent[-1]["pages"].extend(_d["pages"])
                _coherent[-1]["text"] += "\n" + _d["text"]
            else:
                _coherent.append(_d)
        documents = _coherent

    # Krok 0: jeśli brak "pozew" ale jest wzorzec [unknown → nakaz_bez_KOD → nakaz_z_KOD],
    # segment "unknown" to strona pozwu EPU → upgrade do "pozew".
    if not any(d["doc_type"] == "pozew" for d in documents):
        _has_no_kod = any(
            d["doc_type"] in _nakaz_set and not _KOD_RE.search(d["text"])
            for d in documents
        )
        _has_kod = any(
            d["doc_type"] in _nakaz_set and _KOD_RE.search(d["text"])
            for d in documents
        )
        if _has_no_kod and _has_kod:
            _first_no_kod_i = next(
                i for i, d in enumerate(documents)
                if d["doc_type"] in _nakaz_set and not _KOD_RE.search(d["text"])
            )
            if _first_no_kod_i > 0 and documents[_first_no_kod_i - 1]["doc_type"] == "unknown":
                _unk = documents[_first_no_kod_i - 1]
                _unk["doc_type"] = "pozew"
                _unk["label"] = "Pozew"
                _unk["role"] = "primary"

    # Krok 1 (nuclear): blok przed PIERWSZYM segmentem typu nakaz (niezależnie od
    # KOD!) = zawsze formularz pozwu + załączniki (tabele dowodów, wezwania
    # przywołane jako dowód, strony niesklasyfikowane przez OCR). Scal cały ten
    # blok w jeden "pozew". Granica NIE wymaga wykrycia "KOD [hash]" (Rule 0) —
    # zależność od KOD okazała się krucha: różne silniki OCR (Azure/Tesseract/
    # Claude) różnie transkrybują tę linię, a gdy żaden segment nakazu nie ma
    # wykrytego KOD, poprzednia wersja tego kroku w ogóle się nie uruchamiała i
    # cały pre-blok (pozew) ginął bezpowrotnie w filtrze "unknown" niżej. Granica
    # oparta na samym typie "nakaz" jest odporna na to, jak dokładnie OCR
    # odczytał KOD. Ponieważ to PIERWSZY indeks nakazu, blok przed nim z
    # definicji nie zawiera segmentu typu nakaz — inny przypadek (nakaz bez KOD
    # bezpośrednio przed nakazem z KOD w obrębie tego samego pisma) obsługuje
    # osobny, węższy Krok 0 powyżej.
    _first_nakaz_idx = next(
        (i for i, d in enumerate(documents) if d["doc_type"] in _nakaz_set),
        None
    )
    # (03.07.2026) Warunek na scalanie: pre-blok musi zawierać segment typu
    # pozew/unknown/wezwanie_zaplaty — to są rodzaje, które w bundlu EPU
    # faktycznie SĄ stronami formularza pozwu i jego załączników (pierwotny
    # cel tego kroku). Jeśli pre-blok składa się WYŁĄCZNIE z segmentów
    # rozpoznanych jako inne, samodzielne pisma (doreczenie_sadowe,
    # komornik_*, wniosek_egzekucyjny, postanowienie_umorzenie...), NIE wolno
    # ich przemianowywać na "pozew" — np. sądowe doręczenie nakazu z
    # pouczeniem (str.1-4 przed nakazem) stawało się fałszywym "pozwem".
    _MERGEABLE_PRE_TYPES = {"pozew", "unknown", "wezwanie_zaplaty"}
    if _first_nakaz_idx is not None and _first_nakaz_idx > 0:
        _pre = documents[:_first_nakaz_idx]
        if any(d["doc_type"] in _MERGEABLE_PRE_TYPES for d in _pre):
            _merged_pages = [p for d in _pre for p in d["pages"]]
            _merged_text = "\n".join(d["text"] for d in _pre)
            documents = [{
                "doc_type": "pozew",
                "label": "Pozew",
                "role": "primary",
                "pages": _merged_pages,
                "text": _merged_text,
            }] + documents[_first_nakaz_idx:]

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
