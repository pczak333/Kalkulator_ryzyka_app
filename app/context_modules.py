"""Zbiera moduły kontekstowe K3–K6 i reguły kontekstowe (6D–6U)."""
from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
from data_loader import (
    load_k3k6_modules,
    load_deadline_rules,
    load_krs_rules,
    load_zus_rules,
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


def _zus_note(doc_type: str) -> str:
    """Dodaje komunikat dla ścieżki ZUS/organ."""
    if doc_type not in _ZUS_DOC_TYPES:
        return ""
    df = load_zus_rules()
    if df.empty:
        return ""
    # Pierwsza reguła jako generyczny komunikat
    for col in ["tekst_dla_klienta", "komunikat_dla_uzytkownika", "zasada_tekstu"]:
        if col in df.columns:
            val = df.iloc[0].get(col, "")
            if val and str(val) != "nan":
                return str(val).strip()
    return (
        "Pismo organu publicznego dotyczące odpowiedzialności członka zarządu "
        "wymaga złożenia wyjaśnień i przedstawienia dowodów — nie sprzeciwu "
        "ani odpowiedzi na pozew."
    )


def collect(
    state: dict,
    doc_type: str,
    days_exact: int | None = None,
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
    """
    modules_df = load_k3k6_modules()
    out = ContextOutput()

    out.k3_text = _get_module(modules_df, state.get("K3", ""))
    out.k4_text = _get_module(modules_df, state.get("K4", ""))
    out.k5_text = _get_module(modules_df, state.get("K5", ""))
    out.k6_text = _get_module(modules_df, state.get("K6", ""))

    k2_code = state.get("K2", "")
    out.deadline_text, out.calendar_note = _deadline_text(k2_code, days_exact)

    k4 = state.get("K4", "")
    k5 = state.get("K5", "")
    if k4 and k5:
        out.krs_note = _krs_note(k4, k5)

    out.zus_note = _zus_note(doc_type)

    if doc_type in _CZLONEK_ZARZADU_DOC_TYPES:
        out.urgency_note = (
            "Dokument dotyczy bezpośrednio członka zarządu. "
            "Brak właściwej reakcji może mieć znaczenie dla osobistej odpowiedzialności majątkowej."
        )

    return out
