# -*- coding: utf-8 -*-
"""Wybiera dokument główny z listy kandydatów według reguł punktowych z CSV 02/04."""
from __future__ import annotations
import re
from datetime import date

_ART299_PAT = re.compile(r"art\.?\s*299\s*[Kk]\.?[Ss]\.?[Hh]", re.IGNORECASE)

# Mapowanie SPOLKA → CZLONEK_ZARZADU dla bundle-level upgrade (Fix B)
_SPOLKA_TO_CZLONEK: dict[str, str] = {
    "EPU_NAKAZ_SPOLKA":         "EPU_NAKAZ_CZLONEK_ZARZADU",
    "EPU_POZEW_SPOLKA":         "EPU_POZEW_CZLONEK_ZARZADU",
    "NAKAZ_SPOLKA":             "NAKAZ_CZLONEK_ZARZADU",
    "POZEW_SPOLKA":             "POZEW_CZLONEK_ZARZADU",
    "WEZWANIE_SADOWE_SPOLKA":   "WEZWANIE_SADOWE_CZLONEK_ZARZADU",
    "PISMO_KOMORNIK_SPOLKA":    "PISMO_KOMORNIK_CZLONEK_ZARZADU",
    "WYROK_ZAOCZNY_SPOLKA":     "WYROK_ZAOCZNY_CZLONEK_ZARZADU",
}

# Wzorzec do wykrywania czlonek zarządu w bundlu — rozszerza art.299 o frazy naturalne.
# Azure DI może fragmentować "art. 299 KSH" w uzasadnieniu, ale "czlonek zarządu"
# zazwyczaj przetrwa jako fragment tekstu (np. "wzywanie członka zarządu dłużnej spółki").
_CZLONEK_UPGRADE_PAT = re.compile(
    r"art\.?\s*299|czło[nk][koa]\s+zarz[aą]du", re.IGNORECASE
)

# Mapowanie CZLONEK doc_type_code → k1_code (lokalnie, unika circular import z doc_processor)
_UPGRADED_TYPE_TO_K1: dict[str, str] = {
    "EPU_NAKAZ_CZLONEK_ZARZADU":       "K1_NAKAZ_CZLONEK_ZARZADU",
    "EPU_POZEW_CZLONEK_ZARZADU":       "K1_POZEW_CZLONEK_ZARZADU",
    "NAKAZ_CZLONEK_ZARZADU":           "K1_NAKAZ_CZLONEK_ZARZADU",
    "POZEW_CZLONEK_ZARZADU":           "K1_POZEW_CZLONEK_ZARZADU",
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU": "K1_WEZWANIE_SADOWE_CZLONEK_ZARZADU",
    "PISMO_KOMORNIK_CZLONEK_ZARZADU":  "K1_PISMO_KOMORNIK_CZLONEK_ZARZADU",
    # (14.07.2026) własny kod K1 zamiast K1_NAKAZ_CZLONEK_ZARZADU — patrz
    # doc_processor.py._DOC_TYPE_TO_K1 (ta sama zmiana, zduplikowana tu, żeby
    # uniknąć circular importu z doc_processor.py).
    "WYROK_ZAOCZNY_CZLONEK_ZARZADU":   "K1_WYROK_ZAOCZNY_CZLONEK_ZARZADU",
}

_REMIS_THRESHOLD = 10  # różnica punktów poniżej której stosujemy reguły remisu

# Formy prawne spółek — do rozpoznawania, czy nazwa strony to spółka (nie osoba
# fizyczna). Zawiera skróty ORAZ pełne formy pisane ("spółka z ograniczoną
# odpowiedzialnością") — AI zwraca często pełną formę z dokumentu, a poprzednia
# lista w app.py znała tylko skróty z kropkami, przez co bramka art. 299
# pojawiała się mimo pozwanej spółki.
_COMPANY_FORMS = (
    "sp. z o.o.", "sp. z o. o.", "sp. z o.o", "sp. z o.o.", "sp.z o.o",
    "spółka z o.", "spółka z ograniczoną odpowiedzialnością",
    "z ograniczoną odpowiedzialnością",
    "s.a.", "spółka akcyjna", "prosta spółka akcyjna", "p.s.a.",
    "sp. k.", "sp.k.", "spółka komandytowa",
    "s.k.a.", "spółka komandytowo-akcyjna",
    "sp. j.", "sp.j.", "spółka jawna",
    "sp. p.", "sp.p.", "spółka partnerska",
)


def is_company_name(name: str | None) -> bool:
    """True, gdy nazwa strony zawiera formę prawną spółki (dowolny wariant zapisu)."""
    n = (name or "").lower()
    return any(f in n for f in _COMPANY_FORMS)


# (16.07.2026) Porównywanie nazw stron (wierzycieli) — przeniesione z app.py, gdzie
# powstało 14-15.07.2026 dla ostrzeżenia "różne sprawy w paczce" (patrz
# memory/project_unrelated_docs_warning.md). Mieszka tu, nie w app.py, bo Fix B
# (bundle-level upgrade SPOLKA→CZLONEK_ZARZADU, niżej) też tego potrzebuje, a
# doc_selector.py nie importuje app.py (uniknięcie circular importu w drugą stronę —
# app.py już importuje z doc_selector.py, więc ten kierunek jest bezpieczny).
_PARTY_SUFFIX_RE = re.compile(
    r"\b(sp[oó]łk[a-ząćęłńóśźż]*\s+z\s+ograniczon[aą]\s+odpowiedzialno[sś]ci[aą]"
    r"|sp\.?\s*z\s*o\.?\s*o\.?"
    r"|s\.?\s*a\.?"
    r"|sp[oó]łk[a-ząćęłńóśźż]*\s+akcyjn[aą]"
    r"|sp\.?\s*k\.?"
    r"|sp[oó]łk[a-ząćęłńóśźż]*\s+komandytow[a-ząćęłńóśźż]*)\b",
    re.IGNORECASE,
)


def normalize_party_name(name: str) -> str:
    n = _PARTY_SUFFIX_RE.sub(" ", name.upper())
    n = re.sub(r"[^\wĄĆĘŁŃÓŚŹŻ]+", " ", n)
    return " ".join(n.split()).strip()


_PERSON_NAME_MAX_TOKENS = 3


def _same_person_reordered(na: str, nb: str) -> bool:
    """True, gdy obie znormalizowane nazwy to ten sam zestaw 2-3 tokenów w
    innej kolejności (np. "FALISZEWSKA BARBARA" vs "BARBARA FALISZEWSKA" —
    ta sama osoba, imię i nazwisko zamienione miejscami między dokumentami
    tej samej paczki — zgłoszenie użytkownika 15.07.2026). Limit 2-3 tokenów
    celowo: tyle ma zwykłe imię+nazwisko (ew. z drugim imieniem). Krótkie
    nazwy firm po usunięciu formy spółkowej (np. "KILOUTOU POLSKA") mogłyby
    teoretycznie też trafić w ten zakres, ale to DODATKOWY warunek obok
    substring-checku w `parties_differ()` (który już poprawnie łapie
    warianty zapisu firm) — nie jego zamiennik."""
    ta, tb = na.split(), nb.split()
    if not (2 <= len(ta) <= _PERSON_NAME_MAX_TOKENS
            and 2 <= len(tb) <= _PERSON_NAME_MAX_TOKENS):
        return False
    return set(ta) == set(tb)


def parties_differ(a: str | None, b: str | None) -> bool:
    """True gdy dwie nazwy stron (np. wierzycieli) wyglądają na WYRAŹNIE różne
    podmioty — nie tylko inny zapis tej samej firmy albo tej samej osoby z
    imieniem/nazwiskiem zapisanym w innej kolejności. Puste/brakujące
    wartości nigdy nie liczą się jako "różne" (brak fałszywego alarmu przy
    braku danych)."""
    if not a or not b:
        return False
    na, nb = normalize_party_name(a), normalize_party_name(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return False
    if _same_person_reordered(na, nb):
        return False
    return True


# Źródło dokumentu — używane przez R23–R26 w score_candidate()
_COURT_TYPES = {
    "POZEW_CZLONEK_ZARZADU", "NAKAZ_CZLONEK_ZARZADU",
    "EPU_NAKAZ_CZLONEK_ZARZADU", "EPU_POZEW_CZLONEK_ZARZADU",
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU",
    "POZEW_SPOLKA", "NAKAZ_SPOLKA",
    "EPU_NAKAZ_SPOLKA", "EPU_POZEW_SPOLKA",
    "WEZWANIE_SADOWE_SPOLKA", "PISMO_PROCESOWE_SADOWE",
    "WYROK_ZAOCZNY_SPOLKA", "WYROK_ZAOCZNY_CZLONEK_ZARZADU",
}
_BAILIFF_TYPES = {
    "PISMO_KOMORNIK_CZLONEK_ZARZADU", "PISMO_KOMORNIK_SPOLKA",
    "UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC",
}
_ORGAN_TYPES = {
    "DECYZJA_ZUS_CZLONEK_ZARZADU", "DECYZJA_US_CZLONEK_ZARZADU",
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU", "DECYZJA_ZUS_US_SPOLKA",
}
_CREDITOR_TYPES = {
    "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU", "WEZWANIE_PRZEDSADOWE_SPOLKA",
}

# Punktacja typów dokumentów (z CSV 02 reguły R04–R16)
_TYPE_SCORES: dict[str, int] = {
    "EPU_NAKAZ_CZLONEK_ZARZADU":     60,
    "NAKAZ_CZLONEK_ZARZADU":         55,
    "EPU_POZEW_CZLONEK_ZARZADU":     52,
    "POZEW_CZLONEK_ZARZADU":         50,
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU": 45,
    "PISMO_KOMORNIK_CZLONEK_ZARZADU": 45,
    "DECYZJA_ZUS_CZLONEK_ZARZADU":   45,   # R15
    "DECYZJA_US_CZLONEK_ZARZADU":    45,   # R15
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU": 45, # R15
    "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU": 35,   # R13
    "UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC": 45,   # R12
    "EPU_NAKAZ_SPOLKA":              32,
    "NAKAZ_SPOLKA":                  30,
    "WYROK_ZAOCZNY_CZLONEK_ZARZADU": 55,  # ten sam poziom co NAKAZ_CZLONEK_ZARZADU (reużycie K1)
    "WYROK_ZAOCZNY_SPOLKA":          30,  # ten sam poziom co NAKAZ_SPOLKA (reużycie K1)
    "EPU_POZEW_SPOLKA":              27,
    "POZEW_SPOLKA":                  25,
    "WEZWANIE_SADOWE_SPOLKA":        22,
    "PISMO_KOMORNIK_SPOLKA":         35,        # R11
    "DECYZJA_ZUS_US_SPOLKA":         20,
    "WEZWANIE_PRZEDSADOWE_SPOLKA":   15,
    "POTWIERDZENIE_DORECZENIA":      -20,
    "ODPIS_KRS":                     -20,
    "UMOWA_FAKTURA_KORESPONDENCJA":  -20,
    "DOKUMENT_NIEPRAWNY":           -100,
}

# Punkty za adresata (R01-R03)
_ADRESAT_SCORES: dict[str, int] = {
    "czlonek_zarzadu": 40,
    "spolka":          15,
    None:               5,
}

# Punkty za termin (R18–R21, wg CSV 02)
def _deadline_score(days_left: int | None) -> int:
    if days_left is None:
        return 0
    if days_left <= 0:
        return 45   # przeterminowany — krytyczny
    if days_left <= 3:
        return 40   # R18: 0-3 dni
    if days_left <= 7:
        return 30   # R19: 4-7 dni (poprawka: było 35)
    if days_left <= 14:
        return 20   # R20: 8-14 dni (poprawka: było 30)
    return 10       # R21: > 14 dni (poprawka: było 20)


def score_candidate(doc: dict) -> int:
    """Oblicza łączną punktację kandydata na dokument główny."""
    total = 0

    # Adresat (R01-R03)
    adresat = doc.get("addressee")
    total += _ADRESAT_SCORES.get(adresat, 5)

    # Typ dokumentu (R04-R16)
    doc_type = doc.get("doc_type_code", "")
    total += _TYPE_SCORES.get(doc_type, 0)

    # R17: dokument zawiera wyraźny termin reakcji → +35
    # Pełna wersja: days_left znane (delivery_date + deadline_days dostępne).
    # Częściowa: deadline_days znane, ale brak daty doręczenia (np. nakaz EPU bez zwrotki).
    # Nakaz ze sformułowaniem "w ciągu dwóch tygodni" jest tak samo pilny — nie karać go
    # za brak zwrotki, bo uzasadnienie (strona bez terminu) nie powinno go wyprzedzać.
    days_left = doc.get("days_left")
    deadline_days = doc.get("deadline_days")
    if days_left is not None:
        total += 35   # potwierdzony termin — pełny bonus R17
        total += _deadline_score(days_left)  # R18-R21: pilność względem dziś
    elif deadline_days is not None:
        total += 35   # instrukcja terminu obecna — pełny bonus R17
        total += _deadline_score(deadline_days)  # przybliżona pilność (zakładamy od dziś)
    else:
        total += 10   # R22: termin nieznany

    # R23-R26: źródło dokumentu
    if doc_type in _COURT_TYPES:
        total += 25    # R23
    elif doc_type in _BAILIFF_TYPES:
        total += 25    # R24
    elif doc_type in _ORGAN_TYPES:
        total += 25    # R25
    elif doc_type in _CREDITOR_TYPES:
        total += 15    # R26

    # art. 299 KSH w tekście (R27)
    if "art. 299" in doc.get("raw_text", "") or "art.299" in doc.get("raw_text", ""):
        total += 35

    # Sygnatura Nc-e / Lublin-Zachód (R28) — +25 pkt per CSV 02
    if doc.get("epu"):
        total += 25

    # R30-R31: jakość odczytu OCR
    ocr = doc.get("ocr_quality", "")
    if ocr == "HIGH":
        total += 5     # R30
    elif ocr == "LOW":
        total -= 10    # R31

    return total


def _tiebreak(a: dict, b: dict) -> dict:
    """Stosuje reguły remisu (CSV 04) i zwraca preferowany dokument."""
    # R1: czlonek_zarzadu > spolka
    if a.get("addressee") == "czlonek_zarzadu" and b.get("addressee") != "czlonek_zarzadu":
        return a
    if b.get("addressee") == "czlonek_zarzadu" and a.get("addressee") != "czlonek_zarzadu":
        return b

    # R2: bieżący termin > brak terminu (days_left lub choćby deadline_days)
    a_has_deadline = (a.get("days_left") is not None or a.get("deadline_days") is not None)
    b_has_deadline = (b.get("days_left") is not None or b.get("deadline_days") is not None)
    if a_has_deadline and not b_has_deadline:
        return a
    if b_has_deadline and not a_has_deadline:
        return b

    # R3: nakaz > pozew (jeśli termin biegnie)
    nakaz_types = {"NAKAZ_CZLONEK_ZARZADU", "EPU_NAKAZ_CZLONEK_ZARZADU", "NAKAZ_SPOLKA", "EPU_NAKAZ_SPOLKA"}
    a_is_nakaz = a.get("doc_type_code") in nakaz_types
    b_is_nakaz = b.get("doc_type_code") in nakaz_types
    if a_is_nakaz and not b_is_nakaz:
        return a
    if b_is_nakaz and not a_is_nakaz:
        return b

    # R4: EPU > inne
    if a.get("epu") and not b.get("epu"):
        return a
    if b.get("epu") and not a.get("epu"):
        return b

    # R5: sąd > wierzyciel
    a_court = a.get("doc_type_code") in _COURT_TYPES
    b_court = b.get("doc_type_code") in _COURT_TYPES
    a_cred  = a.get("doc_type_code") in _CREDITOR_TYPES
    b_cred  = b.get("doc_type_code") in _CREDITOR_TYPES
    if a_court and b_cred:
        return a
    if b_court and a_cred:
        return b

    # R6: komornik > wierzyciel
    a_bail = a.get("doc_type_code") in _BAILIFF_TYPES
    b_bail = b.get("doc_type_code") in _BAILIFF_TYPES
    if a_bail and b_cred:
        return a
    if b_bail and a_cred:
        return b

    # R7: nowszy dokument
    a_date = a.get("delivery_date") or date.min
    b_date = b.get("delivery_date") or date.min
    return a if a_date >= b_date else b


def select_main_document(candidates: list[dict]) -> tuple[dict, list[dict]]:
    """
    Przyjmuje listę słowników z polami: doc_type_code, epu, addressee,
    days_left, delivery_date, raw_text.
    Zwraca (dokument_główny, [dokumenty_pomocnicze]).
    """
    if not candidates:
        return {}, []

    if len(candidates) == 1:
        main = dict(candidates[0])
        main["status"] = "GLOWNY"
        return main, []

    # Oblicz punktację
    scored = [(doc, score_candidate(doc)) for doc in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_doc, best_score = scored[0]
    second_doc, second_score = scored[1]

    # Twarda reguła: nakaz pilniejszy od pozwu TEJ SAMEJ sprawy (EPU lub zwykły),
    # NIEZALEŻNIE OD PUNKTÓW — w tym przy remisie punktowym. Scoring (art. 299 bonus +35)
    # może podnieść pozew do remisu z nakazem, a wtedy _tiebreak() sprawdzałby adresata (R1)
    # PRZED regułą nakaz>pozew (R3) — co błędnie wybierałoby pozew, gdyby jego adresat był
    # źle sklasyfikowany. Dlatego reguła działa gdy oba typy współistnieją — nie tylko gdy
    # best_doc akurat jest pozwem.
    #
    # WYJĄTEK (03.07.2026, sekwencja art. 299 KSH — implementuje R10 z CSV 02):
    # gdy paczka to łańcuch "nakaz przeciwko SPÓŁCE → egzekucja → umorzenie →
    # pozew przeciwko CZŁONKOWI ZARZĄDU", dokumentem wymagającym reakcji jest
    # POZEW (żywa, nowa sprawa przeciwko osobie fizycznej), a nakaz jest
    # historyczny (prawomocny, z klauzulą wykonalności — żaden termin z niego
    # już nie biegnie). Sygnały łańcucha (wystarczy jeden, oba wymagają pozwu
    # typu _CZLONEK_ZARZADU z pozwanym-osobą fizyczną):
    #   A) w paczce jest dokument egzekucyjny (WNIOSEK_EGZEKUCYJNY lub
    #      UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC) — egzekucja przeciwko spółce
    #      już była, więc nakaz na pewno jest zamkniętym etapem;
    #   B) nakaz dotyczy spółki (typ _SPOLKA lub pozwany z formą spółkową),
    #      a pozew członka zarządu — różni pozwani = różne sprawy (R10:
    #      "nakaz przeciwko spółce jest głównym TYLKO gdy brak dokumentu
    #      przeciwko członkowi zarządu").
    _nakaz_codes = {"EPU_NAKAZ_CZLONEK_ZARZADU", "EPU_NAKAZ_SPOLKA",
                    "NAKAZ_CZLONEK_ZARZADU", "NAKAZ_SPOLKA"}
    _pozew_codes = {"EPU_POZEW_CZLONEK_ZARZADU", "EPU_POZEW_SPOLKA",
                    "POZEW_CZLONEK_ZARZADU", "POZEW_SPOLKA"}
    _egzekucja_codes = {"WNIOSEK_EGZEKUCYJNY", "UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC"}
    _nakazes = [d for d, _ in scored if d.get("doc_type_code") in _nakaz_codes]
    _pozwy   = [d for d, _ in scored if d.get("doc_type_code") in _pozew_codes]
    if _nakazes and _pozwy:
        # Wśród nakazów preferuj ten, który MA instrukcję terminu — strony
        # uzasadnienia błędnie sklasyfikowane jako nakaz nie mają "w ciągu dwóch
        # tygodni" → deadline_days=None. Faktyczny nakaz EPU zawsze ma deadline_days.
        _nakazes_with_dl = [d for d in _nakazes if d.get("deadline_days") is not None]
        _nakaz = _nakazes_with_dl[0] if _nakazes_with_dl else _nakazes[0]

        # Pozwy przeciwko członkowi zarządu (typ CZLONEK i pozwany bez formy
        # spółkowej — koniunkcja dwóch niezależnych cech chroni przed znaną
        # niespójnością klasyfikacji SPOLKA/CZLONEK_ZARZADU).
        _pozwy_cz = [d for d in _pozwy
                     if d.get("doc_type_code", "").endswith("_CZLONEK_ZARZADU")
                     and not is_company_name(d.get("pozwany"))]
        _egzekucja_docs = [d for d, _ in scored
                           if d.get("doc_type_code") in _egzekucja_codes]
        _nakaz_dot_spolki = ("_SPOLKA" in _nakaz.get("doc_type_code", "")
                             or is_company_name(_nakaz.get("pozwany")))
        _art299_chain = bool(_pozwy_cz) and bool(_egzekucja_docs or _nakaz_dot_spolki)

        best_doc = _pozwy_cz[0] if _art299_chain else _nakaz

    # Remis (gdy twarda reguła nakaz>pozew nie zadecydowała)?
    elif best_score - second_score < _REMIS_THRESHOLD:
        best_doc = _tiebreak(best_doc, second_doc)

    # Twarda reguła (05.07.2026): w paczce pism komorniczych dokumentem głównym
    # jest ZAWIADOMIENIE O WSZCZĘCIU POSTĘPOWANIA EGZEKUCYJNEGO — to ono
    # inicjuje egzekucję i na nie się reaguje; zajęcia rachunku/wierzytelności,
    # wezwania o wykaz majątku itd. to SKUTKI wszczęcia (ta sama sygnatura,
    # ta sama egzekucja). Bez tej reguły scoring wybierał zajęcie rachunku,
    # bo miało wyekstrahowany termin z pouczenia (+35 R17 +30 R19), a kwota
    # w ogóle nie jest punktowana — wszczęcie z pełną kwotą przegrywało o ~55
    # pkt. Sygnał wszczęcia: kind segmentu ze splittera (deterministyczny)
    # LUB tytuł w nagłówku tekstu (fallback na wariancję OCR kindów).
    _KOMORNIK_MAIN_CODES = {"PISMO_KOMORNIK_SPOLKA", "PISMO_KOMORNIK_CZLONEK_ZARZADU"}
    _WSZCZECIE_RE = re.compile(
        r"ZAWIADOMIENIE\s+O\s+WSZCZ[EĘ]CIU\s+POST[EĘ]POWANIA\s+EGZEKUCYJ",
        re.IGNORECASE,
    )

    def _is_wszczecie_egzekucji(d: dict) -> bool:
        if d.get("splitter_doc_type") == "komornik_wszczecie_egzekucji":
            return True
        return bool(_WSZCZECIE_RE.search(d.get("raw_text", "")[:2500]))

    if best_doc.get("doc_type_code") in _KOMORNIK_MAIN_CODES and not _is_wszczecie_egzekucji(best_doc):
        _wszczecia = [d for d, _ in scored
                      if d.get("doc_type_code") in _KOMORNIK_MAIN_CODES
                      and _is_wszczecie_egzekucji(d)]
        if _wszczecia:
            best_doc = _wszczecia[0]

    main = dict(best_doc)
    main["status"] = "GLOWNY"

    # Kwota dokumentu głównego z paczki komorniczej (05.07.2026): jeśli główny
    # nie ma kwoty, a inne pismo komornicze TEJ SAMEJ egzekucji (ta sama
    # sygnatura, np. GKm 62/22) ma — przepisz ją. Wąski zakres (tylko typy
    # komornicze, tylko zgodna sygnatura) — zabezpieczenie na wypadek, gdy
    # wariancja OCR pozbawi segment główny kwoty, którą widać w innym piśmie.
    if main.get("doc_type_code") in _KOMORNIK_MAIN_CODES and not main.get("amount"):
        _sig = (main.get("sygnatura") or "").strip().upper()
        _donors = [d for d in candidates
                   if d is not best_doc
                   and d.get("amount")
                   and d.get("doc_type_code") in _KOMORNIK_MAIN_CODES
                   and _sig
                   and (d.get("sygnatura") or "").strip().upper() == _sig]
        if _donors:
            # Preferuj kwotę z zawiadomienia o wszczęciu; w razie braku —
            # najwyższą (pouczenia cytują drobne kwoty ustawowe, np. grzywnę).
            _wszcz_donors = [d for d in _donors if _is_wszczecie_egzekucji(d)]
            _src = _wszcz_donors[0] if _wszcz_donors else max(_donors, key=lambda d: d["amount"])
            main["amount"] = _src["amount"]

    # Fix B: bundle-level upgrade SPOLKA → CZLONEK_ZARZADU.
    # Szuka art. 299 KSH LUB "czlonek zarządu" w dowolnym dokumencie bundla.
    # Azure DI może fragmentować "art. 299 KSH" w uzasadnieniu, ale frazy naturalne
    # (np. "wzywanie członka zarządu dłużnej spółki") zazwyczaj przetrwają OCR.
    # GUARD (03.07.2026): NIE upgraduj, gdy pozwany na SAMYM dokumencie głównym
    # jest spółką — wtedy dokument naprawdę jest skierowany przeciwko spółce,
    # a wzmianka o art. 299/członku zarządu pochodzi z INNEGO dokumentu paczki
    # (np. pozwu art. 299 towarzyszącego staremu nakazowi przeciwko spółce).
    # Bez guardu powstawał stan niespójny: typ *_CZLONEK_ZARZADU + wyświetlany
    # pozwany-spółka → bramka art. 299 pytała o osobę fizyczną wbrew danym.
    # GUARD (16.07.2026): wzmianka o art. 299/członku zarządu liczy się TYLKO,
    # gdy pochodzi z dokumentu tego SAMEGO wierzyciela (powód) co dokument
    # główny — inaczej dwa niepowiązane dokumenty w jednej paczce (różni
    # wierzyciele, różne sprawy) mogłyby skrośnie zanieczyścić klasyfikację
    # (zgłoszony, ale dotąd niezaobserwowany w praktyce błąd, patrz
    # memory/project_unrelated_docs_warning.md — "Related, unaddressed risk").
    # Ten sam `parties_differ()` co ostrzeżenie "różne sprawy w paczce" w
    # app.py: brak powoda po którejkolwiek stronie NIE blokuje upgrade (zero
    # danych = brak dowodu na różnicę, nie fałszywy alarm).
    _main_powod = main.get("powod")
    _bundle_has_czlonek = any(
        _CZLONEK_UPGRADE_PAT.search(d.get("raw_text", ""))
        and not parties_differ(_main_powod, d.get("powod"))
        for d in candidates
    )
    _upgraded_type = _SPOLKA_TO_CZLONEK.get(main.get("doc_type_code", ""))
    if _bundle_has_czlonek and _upgraded_type and not is_company_name(main.get("pozwany")):
        main["doc_type_code"] = _upgraded_type
        main["k1_code"] = _UPGRADED_TYPE_TO_K1.get(_upgraded_type, "K1_INNE_NIE_WIEM")
        main["addressee"] = "czlonek_zarzadu"

    others = []
    for doc, _ in scored:
        if doc is not best_doc:
            other = dict(doc)
            other["status"] = _aux_status(doc)
            others.append(other)

    return main, others


def _aux_status(doc: dict) -> str:
    code = doc.get("doc_type_code", "")
    if code in ("POTWIERDZENIE_DORECZENIA",):
        return "POMOCNICZY_DORECZENIE"
    if code in ("ODPIS_KRS",):
        return "POMOCNICZY_KRS"
    if code in ("UMOWA_FAKTURA_KORESPONDENCJA", "DOKUMENT_NIEPRAWNY"):
        return "NIEISTOTNY"
    return "POMOCNICZY"
