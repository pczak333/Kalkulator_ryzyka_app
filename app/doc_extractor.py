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
# Wzorce roli zarządowej — skanowane w PEŁNYM tekście (nie tylko nagłówku).
# Są jednoznaczne: firmy nie pełnią funkcji członka zarządu ani nie są podmiotem art. 299.
# Jeśli choćby jeden z tych wzorców trafi GDZIEKOLWIEK w tekście → czlonek_zarzadu wygrywa.
_CZLONEK_ROLE_PATTERNS = [
    r"cz[łl]onek[a-z\s]*zarz[aą]du",
    r"\bPrezes[a-z\s]*[Zz]arz[aą]du\b",
    r"\bWiceprezes[a-z\s]*[Zz]arz[aą]du\b",
    r"art\.\s*299\s*[Kk][Ss][Hh]",
]

_ADRESAT: dict[str, list[str]] = {
    "czlonek_zarzadu": [
        r"\bPanu\b", r"\bPani\b",
        r"osob[aą]\s+fizyczn",
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

# Wzorzec do sprawdzenia, czy nazwa pozwanego zawiera formę spółkową
_COMPANY_IN_NAME = re.compile(
    r"\bSp\b\.?\s*z|\bS\.A\.\b|[Ss]p[oó][łl]k|sp\.\s*z\s*o\.o",
    re.IGNORECASE,
)

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
# Dwie serie: "w terminie..." i "w ciągu..." (nakaz EPU używa drugiej formy)
_TERMIN_WRITTEN: list[tuple[str, int]] = [
    (r"w\s+terminie\s+trzech\s+miesi[eę]cy",      90),
    (r"w\s+ci[aą]gu\s+trzech\s+miesi[eę]cy",      90),
    (r"w\s+terminie\s+jednego\s+miesi[aą]ca",     30),
    (r"w\s+ci[aą]gu\s+jednego\s+miesi[aą]ca",     30),
    (r"w\s+terminie\s+miesi[aą]ca",               30),
    (r"w\s+ci[aą]gu\s+miesi[aą]ca",               30),
    (r"w\s+terminie\s+czterech\s+tygodni",        28),
    (r"w\s+ci[aą]gu\s+czterech\s+tygodni",        28),
    (r"w\s+terminie\s+dw[oó]ch\s+tygodni",        14),
    (r"w\s+ci[aą]gu\s+dw[oó]ch\s+tygodni",        14),  # forma operatywna nakazu EPU
    (r"w\s+terminie\s+jednego\s+tygodnia",          7),
    (r"w\s+ci[aą]gu\s+jednego\s+tygodnia",          7),
    (r"w\s+terminie\s+tygodnia",                    7),
    (r"w\s+ci[aą]gu\s+tygodnia",                    7),
]

_TERMIN_PATTERNS = [
    r"w\s+terminie\s+(\d+)\s+dni",
    r"(\d+)\s+dni\s+od\s+(?:dnia\s+)?dor[eę]czenia",
    r"sprzeciw.*?w\s+terminie\s+(\d+)",
    r"odpowied[źz].*?w\s+terminie\s+(\d+)",
    r"termin.*?(\d+)\s+dni\s+kalendarzowych",
    r"termin\s+(\d+)\s+dni",
]

# (14.07.2026) Boilerplate "prawo do wniesienia skargi na czynność komornika"
# (art. 767 §1/§4 KPC) to standardowy akapit w niemal KAŻDYM piśmie komorniczym —
# termin (zwykle 7 dni) na zaskarżenie TEJ konkretnej czynności komornika, nie
# termin na odpowiedź/spłatę. Bez tego guardu Przebieg 2 (przeszukuje cały tekst
# bez ograniczenia kontekstowego) regularnie łapał ten termin jako "termin na
# reakcję" dla dokumentów, które w ogóle nie wymagają żadnej odpowiedzi (np.
# postanowienie o podjęciu zawieszonego postępowania egzekucyjnego —
# KS_postanowienie.pdf, zgłoszenie użytkownika: "prawdopodobnie nie wymaga
# reakcji"). Generyczny guard, nie łatka na jeden dokument — dotyczy każdego
# pisma komorniczego z tym standardowym pouczeniem.
_SKARGA_KOMORNIKA_RE = re.compile(r"skarg[aęi]|art\.?\s*767", re.IGNORECASE)


def _is_skarga_komornika_context(text: str, match_start: int, window: int = 150) -> bool:
    start = max(0, match_start - window)
    return bool(_SKARGA_KOMORNIKA_RE.search(text[start:match_start]))


def _first_non_skarga_match(pattern: str, text: str) -> re.Match | None:
    for m in re.finditer(pattern, text, re.IGNORECASE):
        if not _is_skarga_komornika_context(text, m.start()):
            return m
    return None


# Słowa kluczowe akcji — szukamy terminu w ich pobliżu (±400 znaków).
# "nakazuje pozwanemu" MUSI być pierwsze: termin "w ciągu dwóch tygodni" jest bezpośrednio
# po formule operatywnej nakazu (str. 1 nakazu). "sprzeciw" pojawia się też w pouczeniu
# (str. 3-4 nakazu) gdzie w oknie ±400 zn. może być "w terminie tygodnia" (termin zażalenia) = 7 dni.
_PRIMARY_ACTION_KEYWORDS = [
    "nakazuje pozwanemu",
    "sprzeciw",
    "odpowiedź na pozew",
    "zarzuty od nakazu",
    "wniesienia odpowiedzi",
    "wnieść odpowiedź",
]
_CONTEXT_WINDOW = 800

# ── Kwota ─────────────────────────────────────────────────────────────────────
# Wzorzec polskiego formatu liczby: "2.331,59" lub "5000,00" lub "19.142,36"
# Alternatywa: z separatorem tysięcy (2.331) | bez separatora (5000)
_POLISH_NUM = r"(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d{1,2})?"

_WALUTA = r"(?:z[łl](?:otych?|ote)?|PLN)"   # zł, zl, złotych, złote, PLN

_KWOTA_PATTERNS = [
    rf"({_POLISH_NUM})\s*{_WALUTA}\b",
    rf"kwot[ęayo]\s+({_POLISH_NUM})",                         # kwotę/kwota/kwoty/kwoto
    rf"roszczeni[ae].*?({_POLISH_NUM})\s*{_WALUTA}",
    # Nakaz zapłaty: "nakazuję...kwotę X zł" — wieloliniowy ([\s\S] zamiast .)
    rf"nakazuj[eę][\s\S]{{0,600}}?kwot[ęayo]\s+({_POLISH_NUM})\s*{_WALUTA}",
    # Pismo procesowe: "zasądzenie od pozwanego kwoty X złotych" — wysoki priorytet
    rf"zasądzen\w{{0,4}}[^\n]{{0,150}}?kwot\w{{0,3}}\s+({_POLISH_NUM})\s*{_WALUTA}",
    # Nakaz EPU z rozbiciem odsetkowym: "łącznie: 5 267,77 PLN" — wysoki priorytet
    # ("l" zamiast "ł" — częsty artefakt OCR polskich znaków)
    rf"(?:[lł][aą]cznie|[rR]azem|[Ss]uma)[:\s]+({_POLISH_NUM})\s*{_WALUTA}",
    # Pozew: "Wartość przedmiotu sporu 11 286,00 PLN" — oficjalna, jednoznaczna
    # etykieta łącznej wartości sporu; najwyższy priorytet, ma wygrywać z ogólnymi
    # wzorcami "roszczenia kwoty..."/"kwotę..." dopasowującymi kwoty pojedynczych
    # faktur czy rat z listy dowodów.
    rf"[Ww]arto[śs][ćc]\s+przedmiotu\s+sporu\s*[:\s]*({_POLISH_NUM})\s*{_WALUTA}?",
    # Nakaz: "kwotę łączną 11 286,00 PLN (słownie: ...) w tym kwotę 10 530,00 PLN..." —
    # odmiana przymiotnikowa "łączną"/"łączny"/"łączne" (nie "łącznie") nie pasowała
    # do wzorca powyżej; bez tego wzorca ekstraktor łapał podkwotę "w tym kwotę X PLN".
    # "l" zamiast "ł" ([lł]) — częsty artefakt OCR polskich znaków (jak w _WALUTA).
    rf"kwot[ęayo]\s+[lł][aą]czn\w*\s*[:\s]*({_POLISH_NUM})\s*{_WALUTA}",
]

# ── Sygnatura akt ─────────────────────────────────────────────────────────────
_SYGNATURA_PATTERNS = [
    # "Sygnatura akt" lub "Sygn. akt" (z kropką lub bez) — łapie pełną sygnaturę do końca linii
    r"[Ss]ygn(?:atura)?\.?\s*akt[:\s]+([\w\d\.\s/\-]+?\d{4,}(?:/[A-Z\d]+)*)",
    # EPU: "VI Nc-e 222431/23" — wymagana długa liczba (>=4 cyfry), brak limitu
    r"\b([IVX]+\s+Nc-e\s+\d{4,}/\d{2,4})\b",
    r"\b([IVX]+\s+G(?:Nc|C|Co|n)\s+\d+/\d+(?:/[A-Z]+)?)\b",
    r"\b([A-Z]+\s+\d+/\d+(?:/[A-Z\d]+)?)\b",
]

# Prefiksy, które format przypomina sygnaturę sądową ("LITERY liczba/liczba"), ale
# w rzeczywistości oznaczają numer faktury/dokumentu księgowego z listy dowodów
# (np. "FV 135/2021"), nie sygnaturę akt sprawy — odrzucane niezależnie od tego,
# który wzorzec je dopasował.
_SYGNATURA_EXCLUDE_RE = re.compile(r"^(?:Km|FV|FA|F-?VAT|FAKTURA)\b", re.IGNORECASE)

# ── Sąd / organ ───────────────────────────────────────────────────────────────
_SAD_PATTERNS = [
    r"([Ss][aą]d\s+(?:Rejonowy|Okr[eę]gowy|Apelacyjny|Najwy[żz]szy)[^\n\r]{0,120})",
    r"([Ss]ad\s+(?:Rejonowy|Okregowy|Apelacyjny)[^\n\r]{0,120})",   # wariant bez ą (OCR)
    r"([Ss][aą]d\s+dla\s+[^\n\r]{5,100})",
]

# ── Powód / Pozwany ───────────────────────────────────────────────────────────
_POWOD_PATTERNS = [
    # Nakaz "zwykły" (nie EPU): "pozwu wniesionego w dniu ... przez powoda [Nazwa]
    # nakazuje..." Data bywa cyfrowa (9.03.2022) lub słowna (9 marca 2022 roku) —
    # [^\n\r]{0,40}? (nie-zachłanne) zamiast sztywnego wzorca daty obsługuje oba
    # warianty. Nazwa i formuła operatywna bywają w jednym akapicie bez podziału
    # na linie — capture jest nie-zachłanny i zatrzymuje się przed "nakazuje".
    r"wniesion\w*\s+w\s+dniu\s+[^\n\r]{0,40}?przez\s+(?:powoda\s+)?([^\n\r,;]{4,150}?)(?=\s+nakazuj|[\n\r,;]|$)",
    # Nakaz zapłaty: "zapłacił powodowi [Firma] kwotę"
    r"zap[łl]aci[łl]\s+powodowi\s+([^\n\r,;]{4,100}?)\s+kwot",
    # "na rzecz powoda [Firma]"
    r"na\s+rzecz\s+powoda\s+([^\n\r,;]{4,100})",
    # Nagłówek "Powód:" lub "Powód\n" — \b zapobiega dopasowaniu WEWNĄTRZ odmienionej
    # formy "powodowi"/"powoda" (bez granicy słowa "Pow[oó]d" dopasowywał się jako
    # prefiks "powod-" w "powodowi", łapiąc resztę słowa "owi" + dalszy tekst zdania).
    r"[Pp]ow[oó]d(?:em)?\b[:\s]*\n?\s*([^\n\r,;]{4,150})",
    # Linia po słowie "Powód"
    r"[Pp]ow[oó]d\b\s*\n\s*([^\n\r,;]{4,150})",
]

_POZWANY_PATTERNS = [
    # Nakaz zapłaty: "nakazuję pozwanemu [Imię]" lub "nakazuję pozwanej [Firma]"
    r"nakazuj[eę]\s+pozwane(?:mu|j)\s+([^\n\r,;]{4,150})",
    # "od pozwanego [Firma]" — negatywny lookahead na "na rzecz": formuła procesowa
    # "zasądzenie od pozwanego na rzecz powoda kwoty..." NIE wymienia nazwy pozwanego
    # ponownie (już podana wcześniej w nagłówku "Pozwany:") — bez tego guarda regex
    # łapał fragment zdania "na rzecz strony powodowej kwoty..." jako nazwę pozwanego.
    r"od\s+pozwanego\s+(?!na\s+rzecz)([^\n\r,;]{4,100})",
    # Nagłówek "Pozwany:" lub "Pozwany\n" — \b jak wyżej, zapobiega dopasowaniu
    # wewnątrz odmienionych form ("pozwanego", "pozwanej" itp.)
    r"[Pp]ozwan[yąa](?:ch|m|emu)?\b[:\s]*\n?\s*([^\n\r,;]{4,150})",
    # Linia po słowie "Pozwany"
    r"[Pp]ozwan[yąa]\b\s*\n\s*([^\n\r,;]{4,150})",
]

# Wzorzec do odfiltrowania fałszywych wyników (zdania z treści dokumentu)
_FALSZY_WYNIK = re.compile(
    r"\b(jest\s+obowi[aą]zany|powinien|zobowi[aą]zany|mo[zż]e\s+wnie[sś][cć]|"
    r"nale[zż]y|uprawniony|wskaza[cć]|powo[łl]a[cć]|podnie[sś][cć]|"
    r"na\s+rzecz|strony\s+powodowej|strony\s+pozwanej|nast[eę]puj[aą]c\w*)\b",
    re.IGNORECASE,
)

# Prawdziwa nazwa strony (firma lub imię i nazwisko) w tych pismach zawsze zaczyna
# się wielką literą. Formuły procesowe ("od pozwanego na rzecz powoda następujących
# kwot...", "zapłacić powodowi kwotę...") to fragmenty zdań pisane małą literą — ten
# ogólny guard łapie takie fałszywe dopasowania niezależnie od konkretnych słów użytych
# w formule (skuteczniejszy niż wykluczanie pojedynczych fraz jedna po drugiej).
def _looks_like_party_name(val: str) -> bool:
    return bool(val) and val[0].isupper()

# Spójniki na początku wartości = fragment zdania złapany przez regex, nie nazwa własna
_SPOJNIK_START = re.compile(
    r"^(a\s|i\s|oraz\s|dla\s|do\s|od\s|ze\s|ku\s|czy\s|lub\s)",
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
    s = re.sub(r"\s", "", s)
    # Polski format: "2.331,59" → kropka=sep. tysięcy, przecinek=decimal
    if re.match(r"^\d{1,3}(\.\d{3})+,\d{1,2}$", s):
        s = s.replace(".", "").replace(",", ".")
    elif re.match(r"^\d{1,3}(\.\d{3})+$", s):
        s = s.replace(".", "")
    else:
        s = s.replace(",", ".")
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

    W oknie wybierany jest wzorzec NAJBLIŻSZY słowu kluczowemu (najwcześniejsza
    pozycja w oknie), a nie pierwszy wg kolejności listy _TERMIN_WRITTEN.
    Wcześniej lista była sprawdzana w stałej kolejności (90 dni pierwsze), co
    błędnie wygrywało, gdy okno ±800 zn. wokół "sprzeciw" obejmowało zarówno
    właściwą klauzulę nakazu ("w terminie dwóch tygodni od doręczenia nakazu")
    JAK I sąsiadujący fragment pouczenia o doręczeniu zagranicznym ("w terminie
    trzech miesięcy") — 90 dni wygrywało mimo że 14-dniowy termin był bliżej
    i faktycznie dotyczył tego nakazu (nakaz_zaplaty+pozew.pdf, 01.07.2026).
    """
    text_lower = text.lower()
    for keyword in _PRIMARY_ACTION_KEYWORDS:
        idx = text_lower.find(keyword.lower())
        while idx != -1:
            start = max(0, idx - 100)
            end = min(len(text), idx + _CONTEXT_WINDOW)
            window = text[start:end]
            # Wzorce słowne — wybierz najbliższe dopasowanie w oknie
            best_match = None
            best_days = None
            for pattern, days in _TERMIN_WRITTEN:
                m = re.search(pattern, window, re.IGNORECASE)
                if (m and not _is_skarga_komornika_context(text, start + m.start())
                        and (best_match is None or m.start() < best_match.start())):
                    best_match = m
                    best_days = days
            if best_match is not None:
                return best_days
            # Sprawdź wzorce cyfrowe w oknie
            for pattern in _TERMIN_PATTERNS:
                m = re.search(pattern, window, re.IGNORECASE)
                if m and not _is_skarga_komornika_context(text, start + m.start()):
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

    # Adresat — najpierw szukaj sygnałów roli zarządowej w PEŁNYM tekście dokumentu.
    # Wzorce roli (art. 299 KSH, członek zarządu, Prezes Zarządu) są jednoznaczne:
    # firmy ich nie posiadają. Mogą pojawić się w uzasadnieniu (poza nagłówkiem) —
    # dlatego nie ograniczamy do header_text.
    if any(re.search(p, text, re.IGNORECASE) for p in _CZLONEK_ROLE_PATTERNS):
        result["adresat"] = "czlonek_zarzadu"
        result["adresat_confidence"] = 0.85

    # Dalsze głosowanie w nagłówku (przed POUCZENIE/UZASADNIENIE) — może doprecyzować
    # adresat gdy rola nie była wprost wymieniona lub potwierdzić wynik powyżej.
    pouczenie_idx = text.upper().find("POUCZENIE")
    uzasadnienie_idx = text.upper().find("UZASADNIENIE")
    section_delimiters = [i for i in [pouczenie_idx, uzasadnienie_idx] if i > 100]
    header_end = min(section_delimiters) if section_delimiters else _HEADER_MAX_CHARS
    header_text = text[:min(header_end, _HEADER_MAX_CHARS)]

    # parties_text: jeszcze ściślejsza granica dla powód/pozwany — każde wystąpienie
    # UZASADNIENIE/POUCZENIE (nawet na początku segmentu) kończy strefę ekstrakcji.
    # Zapobiega wyciąganiu podmiotów z uzasadnienia pozwu (cytaty Km, Woodraft Home itp.).
    _strict_delims = [i for i in [pouczenie_idx, uzasadnienie_idx] if i >= 0]
    _strict_end = min(_strict_delims) if _strict_delims else _HEADER_MAX_CHARS
    parties_text = text[:min(_strict_end, _HEADER_MAX_CHARS)]
    adresat_scores: dict[str, int] = {}
    for category, patterns in _ADRESAT.items():
        score = sum(1 for p in patterns if re.search(p, header_text, re.IGNORECASE))
        if score:
            adresat_scores[category] = score

    # Głosowanie uzupełnia wynik full-text scan, ale go nie nadpisuje.
    # Wyjątek: głosowanie może zmienić adresat TYLKO gdy scan nie wykrył roli zarządowej
    # (tzn. result["adresat"] nie został jeszcze ustawiony na czlonek_zarzadu przez scan).
    if adresat_scores and result["adresat"] != "czlonek_zarzadu":
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

    # Przebieg 2: fallback — najbliższe (nie pierwsze wg listy) trafienie wzorca
    # w całym tekście; to samo uzasadnienie co w _find_deadline_near_keyword.
    if result["deadline_days"] is None:
        _best_m = None
        _best_days = None
        for pattern, days in _TERMIN_WRITTEN:
            m = _first_non_skarga_match(pattern, text)
            if m and (_best_m is None or m.start() < _best_m.start()):
                _best_m = m
                _best_days = days
        if _best_m is not None:
            result["deadline_days"] = _best_days

    if result["deadline_days"] is None:
        for pattern in _TERMIN_PATTERNS:
            m = _first_non_skarga_match(pattern, text)
            if m:
                try:
                    days = int(m.group(1))
                    if 1 <= days <= 365:
                        result["deadline_days"] = days
                        break
                except (ValueError, IndexError):
                    continue

    # Kwota — najpierw wzorce najbardziej specyficzne (od końca listy).
    # Wzorce bardziej specyficzne (łącznie, nakazuję) szukają sumy dochodzonej; wzorce
    # ogólne (kwotę, liczba+zł) mogą trafić w koszty procesu (zwykle < 1 000 PLN).
    # Jeśli trafienie < 1 000 PLN → zachowaj jako fallback, szukaj dalej.
    found_amount: float | None = None
    found_raw: str | None = None
    _fallback_amount: float | None = None
    _fallback_raw: str | None = None
    for pattern in reversed(_KWOTA_PATTERNS):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1)
            val = _parse_amount(raw)
            if val and val >= 1000:
                found_amount = val
                found_raw = raw
                break
            elif val and val > 0 and _fallback_amount is None:
                _fallback_amount = val
                _fallback_raw = raw
    if found_amount is None and _fallback_amount is not None:
        found_amount = _fallback_amount
        found_raw = _fallback_raw
    if found_amount is not None:
        result["amount"] = found_amount
        result["amount_raw"] = found_raw
        result["k7_code"] = _amount_to_k7(found_amount)

    # Sygnatura akt — odrzuć sygnatury komornicze (Km/KM = referencja w uzasadnieniu,
    # nie własna sygnatura sądu; sądowe sygnatury to np. "VI Nc-e", "I C", "VIII GC")
    # oraz numery faktur/dokumentów księgowych (FV/FA/F-VAT z listy dowodów), które
    # format ("LITERY liczba/liczba") łudząco przypomina sygnaturę.
    for pattern in _SYGNATURA_PATTERNS:
        m = re.search(pattern, text)
        if m:
            syg = _clean_extracted_name(m.group(1))
            if len(syg) >= 4 and not _SYGNATURA_EXCLUDE_RE.match(syg):
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

    # Powód — tylko z nagłówka (parties_text: bezwzględna granica przed UZASADNIENIE/POUCZENIE)
    for pattern in _POWOD_PATTERNS:
        m = re.search(pattern, parties_text, re.IGNORECASE)
        if m:
            val = _clean_extracted_name(m.group(1))
            if (len(val) >= 3
                    and not _FALSZY_WYNIK.search(val)
                    and not _SPOJNIK_START.search(val)
                    and _looks_like_party_name(val)):
                result["powod"] = val
                break

    # Pozwany — tylko z nagłówka (parties_text).
    # Wzorzec nakazu "nakazuję pozwanemu" zawsze jest przed UZASADNIENIE → parties_text go zawiera.
    for pattern in _POZWANY_PATTERNS:
        m = re.search(pattern, parties_text, re.IGNORECASE)
        if m:
            val = _clean_extracted_name(m.group(1))
            if (len(val) >= 3
                    and not _FALSZY_WYNIK.search(val)
                    and not _SPOJNIK_START.search(val)
                    and _looks_like_party_name(val)):
                result["pozwany"] = val
                break

    # Post-korekcja adresata: jeśli pozwany to osoba fizyczna (brak form spółkowych
    # w nazwie), a adresat był wstępnie wykryty jako "spolka" z nazwy powoda → korekta.
    # Opieramy się na już wyciągniętym result["pozwany"], bo w EPU nakazu etykieta
    # "Pozwany:" często nie pojawia się w nagłówku — jest "Dłużnik:" albo fraza
    # "nakazuję pozwanemu [imię]" w treści poza header_text.
    if result.get("adresat") == "spolka":
        pozwany_name = result.get("pozwany") or ""
        if pozwany_name and not _COMPANY_IN_NAME.search(pozwany_name):
            result["adresat"] = "czlonek_zarzadu"
            result["adresat_confidence"] = min(result.get("adresat_confidence", 1.0), 0.65)

    return result
