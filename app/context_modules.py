"""Zbiera moduły kontekstowe K3–K6 i reguły kontekstowe (6D–6U)."""
from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
from data_loader import (
    load_k3k6_modules,
    load_deadline_rules,
    load_urgency_rules,
    load_krs_rules,
    load_epu_sprzeciw_rules,
    load_epu_block,
    load_zus_rules,
    load_quantity_rules,
    load_unknown_doc_rules,
)

# Typy dokumentów ZUS/organ
_ZUS_DOC_TYPES = {
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
    "DECYZJA_ZUS_CZLONEK_ZARZADU",
    "DECYZJA_US_CZLONEK_ZARZADU",
    "DECYZJA_ZUS_US_SPOLKA",
}

# Typy dokumentów bezpośrednio dotyczące członka zarządu
_CZLONEK_ZARZADU_DOC_TYPES = {
    "POZEW_CZLONEK_ZARZADU",
    "EPU_POZEW_CZLONEK_ZARZADU",
    "NAKAZ_CZLONEK_ZARZADU",
    "EPU_NAKAZ_CZLONEK_ZARZADU",
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU",
    "PISMO_KOMORNIK_CZLONEK_ZARZADU",
    "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU",
    "DECYZJA_ZUS_CZLONEK_ZARZADU",
    "DECYZJA_US_CZLONEK_ZARZADU",
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
}


@dataclass
class ContextOutput:
    k3_text: str = ""
    k4_text: str = ""
    k5_text: str = ""
    k6_text: str = ""
    deadline_text: str = ""
    calendar_note: str = ""
    krs_note: str = ""
    zus_note: str = ""
    urgency_note: str = ""
    epu_text: str = ""
    epu_block_heading: str = ""
    epu_block_text: str = ""
    epu_block_disclaimer: str = ""
    quantity_note: str = ""
    unknown_doc_note: str = ""
    extra_warnings: list[str] = field(default_factory=list)


def _get_module(df: pd.DataFrame, answer_code: str) -> str:
    """Zwraca user_text_fragment dla danego kodu odpowiedzi."""
    mask = (df["answer_code"] == answer_code) & (df["active"] == "TAK")
    hits = df[mask]
    if hits.empty:
        return ""
    val = hits.iloc[0].get("user_text_fragment", "")
    return str(val).strip() if val and str(val) != "nan" else ""


def _deadline_text(k2_code: str, days_exact: int | None) -> tuple[str, str]:
    """Zwraca (tekst terminu, nota o dniach kalendarzowych)."""
    df = load_deadline_rules()
    calendar_note = ""
    # Zawsze dodajemy notę o dniach kalendarzowych
    cal_row = df[df["zakres_terminu"] == "dni kalendarzowe"]
    if not cal_row.empty:
        calendar_note = str(cal_row.iloc[0].get("przykładowe zdanie", "")).strip()
    if calendar_note == "nan":
        calendar_note = "Do tego terminu wliczają się także soboty, niedziele i dni świąteczne."

    if days_exact is not None:
        if days_exact < 0:
            return (
                "Termin na reakcję mógł już upłynąć — konieczne jest pilne "
                "sprawdzenie sytuacji procesowej.",
                calendar_note,
            )
        if days_exact == 0:
            return (
                "Termin na reakcję może upływać dzisiaj — konieczne jest pilne "
                "sprawdzenie sytuacji procesowej.",
                calendar_note,
            )
        if days_exact <= 3:
            return (
                f"Na reakcję pozostaje bardzo ograniczony czas — tylko "
                f"{days_exact} dni kalendarzowe.",
                calendar_note,
            )
        if days_exact <= 5:
            return (
                f"Czas na reakcję jest ograniczony — pozostaje "
                f"{days_exact} dni kalendarzowych.",
                calendar_note,
            )
        if days_exact <= 7:
            return (
                f"Na reakcję pozostaje krótki czas — {days_exact} dni kalendarzowych.",
                calendar_note,
            )
        if days_exact <= 14:
            return (
                f"Na reakcję pozostaje {days_exact} dni kalendarzowych — "
                "warto bez zwłoki uporządkować dokumenty i przygotować dalszą reakcję.",
                calendar_note,
            )
        return (
            f"Na reakcję pozostaje ponad {days_exact} dni — warto spokojnie "
            "uporządkować dokumenty i potwierdzić najważniejsze daty.",
            calendar_note,
        )

    # Brak konkretnej liczby dni – opieramy się na przedziale K2
    bucket_map = {
        "K2_DAYS_LEFT_0_3": "Na reakcję pozostaje bardzo ograniczony czas.",
        "K2_DAYS_LEFT_4_7": "Czas na reakcję jest ograniczony.",
        "K2_DAYS_LEFT_8_14": "Na reakcję jest jeszcze czas, ale nie warto zwlekać.",
        "K2_DAYS_LEFT_ABOVE_14": "Na reakcję pozostaje więcej czasu — warto spokojnie uporządkować dokumenty.",
        "K2_DAYS_LEFT_UNKNOWN": (
            "Termin reakcji nie został jednoznacznie ustalony — "
            "najważniejsze jest szybkie potwierdzenie daty doręczenia i pouczenia."
        ),
    }
    return bucket_map.get(k2_code, ""), calendar_note


def _krs_note(k4_code: str, k5_code: str) -> str:
    """Zwraca wskazówkę dotyczącą KRS na podstawie reguł 6F."""
    df = load_krs_rules()
    mask = (df["k4_status"] == k4_code) & (df["k5_status"] == k5_code)
    hits = df[mask]
    if hits.empty:
        return ""
    val = hits.iloc[0].get("przykład_poprawny", "")
    return str(val).strip() if val and str(val) != "nan" else ""


def _urgency_note_from_csv(doc_type: str, risk_code: str) -> str:
    """Zwraca notę pilności z CSV 25 zależnie od typu dokumentu i poziomu ryzyka."""
    df = load_urgency_rules()
    col = "tekst dla oceny klienta"
    is_czlonek_pozew_nakaz = (
        "CZLONEK_ZARZADU" in doc_type
        and ("POZEW" in doc_type or "NAKAZ" in doc_type)
    )
    if col in df.columns and is_czlonek_pozew_nakaz:
        for _, row in df.iterrows():
            warunek = str(row.get("warunek", "")).strip()
            tekst = str(row.get(col, "")).strip()
            if not tekst or tekst == "nan":
                continue
            if "Sprawa pilna" in warunek and risk_code == "RISK_URGENT":
                return tekst
            if "Wysokie ryzyko" in warunek and risk_code == "RISK_HIGH":
                return tekst
    if doc_type in _CZLONEK_ZARZADU_DOC_TYPES:
        return (
            "Dokument dotyczy bezpośrednio członka zarządu. "
            "Brak właściwej reakcji może mieć znaczenie dla osobistej odpowiedzialności majątkowej."
        )
    return ""


def _epu_sprzeciw_text(k2_code: str) -> str:
    """Zwraca tekst dotyczący sprzeciwu EPU z CSV 28 zależnie od pozostałego czasu."""
    df = load_epu_sprzeciw_rules()
    if df.empty:
        return ""
    col = "tekst_dla_uzytkownika"
    if col not in df.columns:
        return ""
    k2_to_idx = {
        "K2_DAYS_LEFT_0_3":      0,
        "K2_DAYS_LEFT_4_7":      0,
        "K2_DAYS_LEFT_8_14":     1,
        "K2_DAYS_LEFT_ABOVE_14": 2,
        "K2_DAYS_LEFT_UNKNOWN":  None,  # nieznany termin → brak tekstu sprzeciwu EPU
    }
    idx = k2_to_idx.get(k2_code)
    if idx is None:
        return ""
    if idx >= len(df):
        idx = len(df) - 1
    val = df.iloc[idx].get(col, "")
    return str(val).strip() if val and str(val) != "nan" else ""


def _quantity_note(k7_code: str) -> str:
    """Zwraca tekst kontekstowy dla kwoty roszczenia z CSV 36."""
    df = load_quantity_rules()
    if df.empty:
        return ""
    col = "tekst_dla_klienta"
    if col not in df.columns:
        return ""
    hits = df[df["amount_code"] == k7_code]
    if hits.empty:
        return ""
    val = hits.iloc[0].get(col, "")
    return str(val).strip() if val and str(val) != "nan" else ""


def _load_epu_block() -> tuple[str, str, str]:
    """Zwraca (nagłówek, tekst, zastrzeżenie) z CSV 13 (Blok_EPU)."""
    df = load_epu_block()
    if df.empty:
        return "", "", ""

    def _cell(field_name: str) -> str:
        hits = df[df["pole"] == field_name]
        if hits.empty:
            return ""
        val = hits.iloc[0].get("tresc", "")
        return str(val).strip() if val and str(val) != "nan" else ""

    return _cell("naglowek"), _cell("tekst"), _cell("zastrzezenie")


def _zus_note(doc_type: str) -> str:
    """Dodaje komunikat dla ścieżki ZUS/organ — czyta z CSV 40, kolumna 'tekst / znaczenie'."""
    if doc_type not in _ZUS_DOC_TYPES:
        return ""
    df = load_zus_rules()
    if df.empty or "obszar" not in df.columns:
        return (
            "Pismo organu publicznego dotyczące odpowiedzialności członka zarządu "
            "wymaga złożenia wyjaśnień i przedstawienia dowodów — nie sprzeciwu "
            "ani odpowiedzi na pozew."
        )
    col = "tekst / znaczenie"
    hits = df[df["obszar"] == "Priorytet"]
    if not hits.empty and col in df.columns:
        val = hits.iloc[0].get(col, "")
        if val and str(val) != "nan":
            return str(val).strip()
    # fallback: pierwsze niepuste pole 'tekst / znaczenie' w całym CSV
    if col in df.columns:
        for _, row in df.iterrows():
            val = row.get(col, "")
            if val and str(val) != "nan":
                return str(val).strip()
    return (
        "Pismo organu publicznego dotyczące odpowiedzialności członka zarządu "
        "wymaga złożenia wyjaśnień i przedstawienia dowodów — nie sprzeciwu "
        "ani odpowiedzi na pozew."
    )


def _k6_procedural_text(doc_type: str, generic_text: str) -> str:
    """Zwraca tekst K6_GOAL_PROCEDURAL_LETTER dopasowany do typu dokumentu."""
    if "POZEW" in doc_type:
        return (
            "Zaznaczono, że głównym celem jest przygotowanie właściwego pisma procesowego. "
            "W przypadku pozwu właściwą reakcją jest odpowiedź na pozew — jej zakres "
            "i termin złożenia decydują o możliwości przedstawienia zarzutów i dowodów. "
            "Źle skonstruowane pismo albo spóźniona reakcja mogą ograniczyć możliwość obrony."
        )
    if "NAKAZ" in doc_type:
        return (
            "Zaznaczono, że głównym celem jest przygotowanie właściwego pisma procesowego. "
            "W przypadku nakazu zapłaty właściwą reakcją jest sprzeciw albo zarzuty zależnie "
            "od trybu postępowania — termin jest ściśle określony i nie podlega przedłużeniu. "
            "Źle dobrana forma albo spóźniona reakcja może skutkować uprawomocnieniem nakazu."
        )
    if "WEZWANIE_SADOWE" in doc_type:
        return (
            "Zaznaczono, że głównym celem jest przygotowanie właściwego pisma. "
            "Wezwanie sądowe może wymagać różnych form reakcji zależnie od jego treści "
            "i pouczenia — od pisma przygotowawczego, przez złożenie dokumentów, "
            "po inne działania procesowe. Kluczowe jest dokładne przeczytanie treści "
            "wezwania i wskazanego terminu."
        )
    if doc_type in (
        "DECYZJA_ZUS_CZLONEK_ZARZADU",
        "DECYZJA_US_CZLONEK_ZARZADU",
        "ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
        "DECYZJA_ZUS_US_SPOLKA",
    ):
        return (
            "Zaznaczono, że głównym celem jest przygotowanie właściwego pisma. "
            "W przypadku pisma organu publicznego (ZUS, urząd skarbowy) właściwą reakcją "
            "są wyjaśnienia i dokumenty potwierdzające stanowisko — nie sprzeciw ani "
            "odpowiedź na pozew. Zakres wyjaśnień i termin określa treść pisma i pouczenie."
        )
    if "KOMORNIK" in doc_type:
        return (
            "Zaznaczono, że głównym celem jest przygotowanie właściwego pisma. "
            "W przypadku pisma komorniczego rodzaj reakcji zależy od podstawy egzekucji — "
            "może to być powództwo przeciwegzekucyjne, wniosek o zawieszenie egzekucji "
            "albo inne pismo zależnie od tytułu wykonawczego. Właściwy krok wymaga "
            "wcześniejszego ustalenia treści tytułu."
        )
    if "WEZWANIE_PRZEDSADOWE" in doc_type:
        return (
            "Zaznaczono, że głównym celem jest przygotowanie właściwego pisma. "
            "Wezwanie przedsądowe nie jest pismem procesowym — można na nie odpowiedzieć, "
            "zakwestionować roszczenie lub przygotować się na dalsze kroki wierzyciela. "
            "Decyzja o formie i treści odpowiedzi powinna uwzględniać podstawę roszczenia."
        )
    return generic_text


def _unknown_doc_note(doc_type: str) -> str:
    """Zwraca wskazówkę priorytetu dla dokumentu nieustalonego (CSV 38)."""
    if doc_type != "DOKUMENT_NIEUSTALONY_PRAWNY":
        return ""
    df = load_unknown_doc_rules()
    if df.empty or "obszar" not in df.columns:
        return ""
    col = "zasada / treść"
    hits = df[df["obszar"] == "Priorytet"]
    if not hits.empty and col in df.columns:
        val = hits.iloc[0].get(col, "")
        if val and str(val) != "nan":
            return str(val).strip()
    return ""


def collect(
    state: dict,
    doc_type: str,
    days_exact: int | None = None,
    risk_code: str = "",
) -> ContextOutput:
    """
    Zbiera wszystkie moduły kontekstowe dla danego stanu formularza.

    Parameters
    ----------
    state : dict
        Słownik z kluczami K3, K4, K5, K6.
    doc_type : str
        main_document_type_code (np. EPU_NAKAZ_CZLONEK_ZARZADU).
    days_exact : int | None
        Dokładna liczba dni pozostałych na reakcję (jeśli wyliczona z dat).
    risk_code : str
        Końcowy kod ryzyka (po twardych regułach) – potrzebny dla CSV 25.
    """
    modules_df = load_k3k6_modules()
    out = ContextOutput()

    out.k3_text = _get_module(modules_df, state.get("K3", ""))
    out.k4_text = _get_module(modules_df, state.get("K4", ""))
    out.k5_text = _get_module(modules_df, state.get("K5", ""))
    k6_code = state.get("K6", "")
    out.k6_text = _get_module(modules_df, k6_code)
    if k6_code == "K6_GOAL_PROCEDURAL_LETTER":
        out.k6_text = _k6_procedural_text(doc_type, out.k6_text)

    k2_code = state.get("K2", "")
    out.deadline_text, out.calendar_note = _deadline_text(k2_code, days_exact)

    k4 = state.get("K4", "")
    k5 = state.get("K5", "")
    if k4 and k5:
        out.krs_note = _krs_note(k4, k5)

    out.zus_note = _zus_note(doc_type)
    out.urgency_note = _urgency_note_from_csv(doc_type, risk_code)

    if state.get("EPU"):
        out.epu_block_heading, out.epu_block_text, out.epu_block_disclaimer = _load_epu_block()
        if "NAKAZ" in doc_type:
            out.epu_text = _epu_sprzeciw_text(k2_code)

    k7_code = state.get("K7", "")
    if k7_code:
        out.quantity_note = _quantity_note(k7_code)

    out.unknown_doc_note = _unknown_doc_note(doc_type)

    return out
