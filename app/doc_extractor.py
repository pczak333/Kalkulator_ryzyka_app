# -*- coding: utf-8 -*-
"""Wyciąga pola z tekstu dokumentu: EPU, adresat, daty, termin, kwota."""
from __future__ import annotations
import re
from datetime import date, datetime

# ── EPU / e-Sąd ──────────────────────────────────────────────────────────────
_EPU_PATTERNS = [
    r"Nc-e\s*\d",
    r"e-[Ss]ąd",
    r"\bEPU\b",
    r"Elektroniczne\s+Post[eę]powanie\s+Upominawcze",
    r"S[aą]d\s+Rejonowy\s+Lublin.Zach[oó]d",
    r"VI\s+Wydzia[łl]\s+Cywilny",
]

# ── Adresat ───────────────────────────────────────────────────────────────────
_ADRESAT: dict[str, list[str]] = {
    "czlonek_zarzadu": [
        r"\bPanu\b", r"\bPani\b",
        r"cz[łl]onek[a-z\s]*zarz[aą]du",
        r"\bPrezes[a-z\s]*[Zz]arz[aą]du\b",
        r"\bWiceprezes[a-z\s]*[Zz]arz[aą]du\b",
        r"osob[aą]\s+fizyczn",
        r"art\.\s*299\s*[Kk][Ss][Hh]",
    ],
    "spolka": [
        r"[Ss]p[oó][łl]k[aą]\b",
        r"[Ss]p\.\s*z\s*o\.o",
        r"\bS\.A\.\b",
        r"sp[oó][łl]k[aą]\s+z\s+ograniczon",
    ],
    "organ": [
        r"\bZUS\b",
        r"Zak[łl]ad\s+Ubezpiecze[nń]\s+Spo[łl]ecznych",
        r"[Uu]rz[aą]d\s+[Ss]karbowy",
        r"Naczelnik\s+[Uu]rz[eę]du\s+[Ss]karbowego",
        r"[Oo]dpowiedzialno[śs][śs][ćc]\s+osoby\s+trzeciej",
    ],
}

# ── Daty i terminy ────────────────────────────────────────────────────────────
_DATE_FORMATS = ["%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"]

_DORECZENIE_PATTERNS = [
    r"[Dd]at[aą]\s+dor[eę]czenia[:\s]+(\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{4})",
    r"dor[eę]czono[:\s]+(\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{4})",
    r"odebra[łl]em[:\s]+dnia\s+(\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{4})",
    r"data\s+odbioru[:\s]+(\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{4})",
    r"(\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{4})\s*–?\s*data\s+dor[eę]czenia",
]

_TERMIN_PATTERNS = [
    r"w\s+terminie\s+(\d+)\s+dni",
    r"(\d+)\s+dni\s+od\s+(?:dnia\s+)?dor[eę]czenia",
    r"sprzeciw.*?w\s+terminie\s+(\d+)",
    r"odpowied[źz].*?w\s+terminie\s+(\d+)",
    r"termin.*?(\d+)\s+dni\s+kalendarzowych",
    r"termin\s+(\d+)\s+dni",
]

# ── Kwota ─────────────────────────────────────────────────────────────────────
_KWOTA_PATTERNS = [
    r"(\d[\d\s]{0,12}[\d,]+)\s*(?:z[łl]|PLN)\b",
    r"kwot[ęa]\s+(\d[\d\s]{0,12}[\d,]+)",
    r"roszczeni[ae].*?(\d[\d\s]{0,12}[\d,]+)\s*(?:z[łl]|PLN)",
]

# Progi bucket K7
_K7_BUCKETS = [
    (10_000, "K7_AMOUNT_UP_TO_10K"),
    (50_000, "K7_AMOUNT_10K_50K"),
    (150_000, "K7_AMOUNT_50K_150K"),
    (500_000, "K7_AMOUNT_150K_500K"),
]
_K7_ABOVE = "K7_AMOUNT_ABOVE_500K"
_K7_UNKNOWN = "K7_AMOUNT_UNKNOWN"


def _parse_date(s: str) -> date | None:
    s = s.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_amount(s: str) -> float | None:
    s = re.sub(r"\s", "", s).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _amount_to_k7(amount: float) -> str:
    for threshold, code in _K7_BUCKETS:
        if amount <= threshold:
            return code
    return _K7_ABOVE


def extract_fields(text: str) -> dict:
    """
    Wyciąga pola z tekstu dokumentu.
    Zwraca słownik z kluczami:
      epu, epu_confidence, adresat, adresat_confidence,
      delivery_date, deadline_days, amount, amount_raw, k7_code
    """
    result: dict = {
        "epu": False,
        "epu_confidence": 0.0,
        "adresat": None,
        "adresat_confidence": 0.0,
        "delivery_date": None,
        "deadline_days": None,
        "amount": None,
        "amount_raw": None,
        "k7_code": _K7_UNKNOWN,
    }

    # EPU
    epu_hits = sum(1 for p in _EPU_PATTERNS if re.search(p, text))
    if epu_hits >= 1:
        result["epu"] = True
        result["epu_confidence"] = min(0.6 + epu_hits * 0.15, 1.0)

    # Adresat — liczymy trafienia dla każdej kategorii
    adresat_scores: dict[str, int] = {}
    for category, patterns in _ADRESAT.items():
        score = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
        if score:
            adresat_scores[category] = score

    if adresat_scores:
        best = max(adresat_scores, key=lambda k: adresat_scores[k])
        total = sum(adresat_scores.values())
        result["adresat"] = best
        result["adresat_confidence"] = adresat_scores[best] / max(total, 1)

    # Data doręczenia
    for pattern in _DORECZENIE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            parsed = _parse_date(m.group(1))
            if parsed:
                result["delivery_date"] = parsed
                break

    # Termin z pouczenia (liczba dni)
    for pattern in _TERMIN_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                days = int(m.group(1))
                if 1 <= days <= 365:
                    result["deadline_days"] = days
                    break
            except (ValueError, IndexError):
                continue

    # Kwota
    best_amount: float | None = None
    best_raw: str | None = None
    for pattern in _KWOTA_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            raw = m.group(1)
            val = _parse_amount(raw)
            if val and val > 0:
                if best_amount is None or val > best_amount:
                    best_amount = val
                    best_raw = raw
    if best_amount is not None:
        result["amount"] = best_amount
        result["amount_raw"] = best_raw
        result["k7_code"] = _amount_to_k7(best_amount)

    return result
