# -*- coding: utf-8 -*-
"""Wybiera dokument główny z listy kandydatów według reguł punktowych z CSV 02/04."""
from __future__ import annotations
from datetime import date

_REMIS_THRESHOLD = 10  # różnica punktów poniżej której stosujemy reguły remisu

# Punktacja typów dokumentów (z CSV 02 reguły R04–R16)
_TYPE_SCORES: dict[str, int] = {
    "EPU_NAKAZ_CZLONEK_ZARZADU":     60,
    "NAKAZ_CZLONEK_ZARZADU":         55,
    "EPU_POZEW_CZLONEK_ZARZADU":     52,
    "POZEW_CZLONEK_ZARZADU":         50,
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU": 45,
    "PISMO_KOMORNIK_CZLONEK_ZARZADU": 45,
    "DECYZJA_ZUS_CZLONEK_ZARZADU":   42,
    "DECYZJA_US_CZLONEK_ZARZADU":    42,
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU": 42,
    "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU": 38,
    "UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC": 35,
    "EPU_NAKAZ_SPOLKA":              32,
    "NAKAZ_SPOLKA":                  30,
    "EPU_POZEW_SPOLKA":              27,
    "POZEW_SPOLKA":                  25,
    "WEZWANIE_SADOWE_SPOLKA":        22,
    "PISMO_KOMORNIK_SPOLKA":         22,
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

# Punkty za termin (R17–R20)
def _deadline_score(days_left: int | None) -> int:
    if days_left is None:
        return 0
    if days_left <= 0:
        return 45   # przeterminowany — krytyczny
    if days_left <= 3:
        return 40
    if days_left <= 7:
        return 35
    if days_left <= 14:
        return 30
    return 20       # > 14 dni


def score_candidate(doc: dict) -> int:
    """Oblicza łączną punktację kandydata na dokument główny."""
    total = 0

    # Adresat (R01-R03)
    adresat = doc.get("addressee")
    total += _ADRESAT_SCORES.get(adresat, 5)

    # Typ dokumentu (R04-R16)
    doc_type = doc.get("doc_type_code", "")
    total += _TYPE_SCORES.get(doc_type, 0)

    # Termin (R17-R20)
    days_left = doc.get("days_left")
    total += _deadline_score(days_left)

    # art. 299 KSH w tekście (R27)
    if "art. 299" in doc.get("raw_text", "") or "art.299" in doc.get("raw_text", ""):
        total += 35

    # Sygnatura Nc-e / Lublin-Zachód (R28) — +25 pkt per CSV 02
    if doc.get("epu"):
        total += 25

    return total


def _tiebreak(a: dict, b: dict) -> dict:
    """Stosuje reguły remisu (CSV 04) i zwraca preferowany dokument."""
    # R1: czlonek_zarzadu > spolka
    if a.get("addressee") == "czlonek_zarzadu" and b.get("addressee") != "czlonek_zarzadu":
        return a
    if b.get("addressee") == "czlonek_zarzadu" and a.get("addressee") != "czlonek_zarzadu":
        return b

    # R2: bieżący termin > brak terminu
    a_has_deadline = (a.get("days_left") is not None)
    b_has_deadline = (b.get("days_left") is not None)
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

    # Remis?
    if best_score - second_score < _REMIS_THRESHOLD:
        best_doc = _tiebreak(best_doc, second_doc)

    main = dict(best_doc)
    main["status"] = "GLOWNY"

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
