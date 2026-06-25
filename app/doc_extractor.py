# -*- coding: utf-8 -*-
"""Wyciąga pola z tekstu dokumentu: EPU, adresat, daty, termin, kwota, sygnatura."""
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
]

# Adresat wykrywany tylko w nagłówku dokumentu — pouczenie (str. 3+) zaburza wynik
_HEADER_MAX_CHARS = 2000

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
        r"[Ss]p[oó][łl][ck][a-z]*\b",
        r"[Ss]p\.\s*z\s*o\.o",
        r"\bS\.A\.\b",
        r"[Ss]p[oó][łl][ck][a-z]*\s+z\s+ograniczon",
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

# Terminy słowne → liczba dni (sprawdzane PRZED wzorcami cyfrowymi)
_TERMIN_WRITTEN: list[tuple[str, int]] = [
    (r"w\s+terminie\s+trzech\s+miesi[eę]cy",      90),
    (r"w\s+terminie\s+jednego\s+miesi[aą]ca",     30),
    (r"w\s+terminie\s+miesi[aą]ca",               30),
    (r"w\s+terminie\s+czterech\s+tygodni",        28),
    (r"w\s+terminie\s+dw[oó]ch\s+tygodni",       14),
    (r"w\s+terminie\s+jednego\s+tygodnia",         7),
    (r"w\s+terminie\s+tygodnia",                   7),
]

_TERMIN_PATTERNS = [
    r"w\s+terminie\s+(\d+)\s+dni",
    r"(\d+)\s+dni\s+od\s+(?:dnia\s+)?dor[eę]czenia",
    r"sprzeciw.*?w\s+terminie\s+(\d+)",
    r"odpowied[źz].*?w\s+terminie\s+(\d+)",
    r"termin.*?(\d+)\s+dni\s+kalendarzowych",
    r"termin\s+(\d+)\s+dni",
]

# Słowa kluczowe akcji — szukamy terminu w ich pobliżu (±400 znaków)
_PRIMARY_ACTION_KEYWORDS = [
    "sprzeciw",
    "odpowiedź na pozew",
    "zarzuty od nakazu",
    "wniesienia odpowiedzi",
    "wnieść odpowiedź",
]
_CONTEXT_WINDOW = 400

# ── Kwota ─────────────────────────────────────────────────────────────────────
_KWOTA_PATTERNS = [
    r"(\d[\d\s]{0,12}[\d,]+)\s*(?:z[łl]|PLN)\b",
    r"kwot[ęa]\s+(\d[\d\s]{0,12}[\d,]+)",
    r"roszczeni[ae].*?(\d[\d\s]{0,12}[\d,]+)\s*(?:z[łl]|PLN)",
]

# ── Sygnatura akt ─────────────────────────────────────────────────────────────
_SYGNATURA_PATTERNS = [
    r"[Ss]ygn(?:atura)?\.\s*akt\s+([\w\d\.\s/]+?\d{2,4}(?:/[A-Z\d]+)*)",
    r"\b([IVX]+\s+G(?:Nc|C|Co|n)\s+\d+/\d+(?:/[A-Z]+)?)\b",
    r"\b([A-Z]+\s+\d+/\d+(?:/[A-Z\d]+)?)\b",
]

# ── Sąd / organ ───────────────────────────────────────────────────────────────
_SAD_PATTERNS = [
    r"([Ss][aą]d\s+(?:Rejonowy|Okr[eę]gowy|Apelacyjny|Najwy[żz]szy)[^\n\r]{0,120})",
    r"([Ss]ad\s+(?:Rejonowy|Okregowy|Apelacyjny)[^\n\r]{0,120})",   # wariant bez ą (OCR)
    r"([Ss][aą]d\s+dla\s+[^\n\r]{5,100})",
]

# ── Powód / Pozwany ───────────────────────────────────────────────────────────
_POWOD_PATTERNS = [
    # Nakaz zapłaty: "zapłacił powodowi [Firma] kwotę"
    r"zap[łl]aci[łl]\s+powodowi\s+([^\n\r,;]{4,100}?)\s+kwot",
    # "na rzecz powoda [Firma]"
    r"na\s+rzecz\s+powoda\s+([^\n\r,;]{4,100})",
    # Nagłówek "Powód:" lub "Powód\n"
    r"[Pp]ow[oó]d(?:em)?[:\s]*\n?\s*([^\n\r,;]{4,150})",
    # Linia po słowie "Powód"
    r"[Pp]ow[oó]d\s*\n\s*([^\n\r,;]{4,150})",
]

_POZWANY_PATTERNS = [
    # Nakaz zapłaty: "nakazuję pozwanemu [Imię]" lub "nakazuję pozwanej [Firma]"
    r"nakazuj[eę]\s+pozwane(?:mu|j)\s+([^\n\r,;]{4,150})",
    # "od pozwanego [Firma]"
    r"od\s+pozwanego\s+([^\n\r,;]{4,100})",
    # Nagłówek "Pozwany:" lub "Pozwany\n"
    r"[Pp]ozwan[yąa](?:ch|m|emu)?[:\s]*\n?\s*([^\n\r,;]{4,150})",
    # Linia po słowie "Pozwany"
    r"[Pp]ozwan[yąa]\s*\n\s*([^\n\r,;]{4,150})",
]

# Wzorzec do odfiltrowania fałszywych wyników (zdania z treści dokumentu)
_FALSZY_WYNIK = re.compile(
    r"\b(jest\s+obowi[aą]zany|powinien|zobowi[aą]zany|mo[zż]e\s+wnie[sś][cć]|"
    r"nale[zż]y|uprawniony|wskaza[cć]|powo[łl]a[cć]|podnie[sś][cć])\b",
    re.IGNORECASE,
)

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


def _find_deadline_near_keyword(text: str) -> int | None:
    """
    Przebieg 1: szuka terminu w oknie ±400 znaków wokół słów kluczowych akcji
    (sprzeciw, odpowiedź na pozew itp.). Priorytetyzuje termin przy "sprzeciw"
    nad ogólnymi wzmiankami w pouczeniu (np. termin zażalenia = 3 miesiące).
    """
    text_lower = text.lower()
    for keyword in _PRIMARY_ACTION_KEYWORDS:
        idx = text_lower.find(keyword.lower())
        while idx != -1:
            start = max(0, idx - 100)
            end = min(len(text), idx + _CONTEXT_WINDOW)
            window = text[start:end]
            # Sprawdź wzorce słowne w oknie
            for pattern, days in _TERMIN_WRITTEN:
                if re.search(pattern, window, re.IGNORECASE):
                    return days
            # Sprawdź wzorce cyfrowe w oknie
            for pattern in _TERMIN_PATTERNS:
                m = re.search(pattern, window, re.IGNORECASE)
                if m:
                    try:
                        days = int(m.group(1))
                        if 1 <= days <= 365:
                            return days
                    except (ValueError, IndexError):
                        pass
            idx = text_lower.find(keyword.lower(), idx + 1)
    return None


def _clean_extracted_name(s: str) -> str:
    """Czyści wyciągnięty ciąg (powód/pozwany/sąd) z artefaktów OCR."""
    s = s.strip().rstrip(".,;:")
    # Usuń wielokrotne spacje
    s = re.sub(r"\s{2,}", " ", s)
    return s


def extract_fields(text: str) -> dict:
    """
    Wyciąga pola z tekstu dokumentu.
    Zwraca słownik z kluczami:
      epu, epu_confidence, adresat, adresat_confidence,
      delivery_date, deadline_days, amount, amount_raw, k7_code,
      sygnatura, sad_organ, powod, pozwany
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
        "sygnatura": None,
        "sad_organ": None,
        "powod": None,
        "pozwany": None,
    }

    # EPU
    epu_hits = sum(1 for p in _EPU_PATTERNS if re.search(p, text))
    if epu_hits >= 1:
        result["epu"] = True
        result["epu_confidence"] = min(0.6 + epu_hits * 0.15, 1.0)

    # Adresat — tylko nagłówek dokumentu (przed sekcją POUCZENIE lub max 2000 znaków)
    pouczenie_idx = text.upper().find("POUCZENIE")
    header_end = pouczenie_idx if pouczenie_idx > 0 else _HEADER_MAX_CHARS
    header_text = text[:min(header_end, _HEADER_MAX_CHARS)]
    adresat_scores: dict[str, int] = {}
    for category, patterns in _ADRESAT.items():
        score = sum(1 for p in patterns if re.search(p, header_text, re.IGNORECASE))
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

    # Termin z pouczenia — dwuprzebiegowy:
    # Przebieg 1: termin w pobliżu słów kluczowych akcji (np. "sprzeciw")
    result["deadline_days"] = _find_deadline_near_keyword(text)

    # Przebieg 2: fallback — pierwsze trafienie wzorca w całym tekście
    if result["deadline_days"] is None:
        for pattern, days in _TERMIN_WRITTEN:
            if re.search(pattern, text, re.IGNORECASE):
                result["deadline_days"] = days
                break

    if result["deadline_days"] is None:
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

    # Kwota — najpierw wzorce najbardziej specyficzne (od końca listy)
    found_amount: float | None = None
    found_raw: str | None = None
    for pattern in reversed(_KWOTA_PATTERNS):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1)
            val = _parse_amount(raw)
            if val and val > 0:
                found_amount = val
                found_raw = raw
                break
    if found_amount is not None:
        result["amount"] = found_amount
        result["amount_raw"] = found_raw
        result["k7_code"] = _amount_to_k7(found_amount)

    # Sygnatura akt
    for pattern in _SYGNATURA_PATTERNS:
        m = re.search(pattern, text)
        if m:
            syg = _clean_extracted_name(m.group(1))
            if len(syg) >= 4:
                result["sygnatura"] = syg
                break

    # Sąd / organ — pierwsze trafienie
    for pattern in _SAD_PATTERNS:
        m = re.search(pattern, text)
        if m:
            sad = _clean_extracted_name(m.group(1))
            if len(sad) >= 10:
                result["sad_organ"] = sad
                break

    # Powód — z filtrem fałszywych wyników (zdania z treści dokumentu)
    for pattern in _POWOD_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = _clean_extracted_name(m.group(1))
            if len(val) >= 3 and not _FALSZY_WYNIK.search(val):
                result["powod"] = val
                break

    # Pozwany — z filtrem fałszywych wyników
    for pattern in _POZWANY_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = _clean_extracted_name(m.group(1))
            if len(val) >= 3 and not _FALSZY_WYNIK.search(val):
                result["pozwany"] = val
                break

    return result
