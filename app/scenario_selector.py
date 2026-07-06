"""Dobiera scenariusz bazowy z biblioteki 173 scenariuszy (CSV 12)."""
from __future__ import annotations
import pandas as pd
from data_loader import load_scenarios

# Mapowanie kodu K1 + EPU → main_document_type_code
_K1_TO_DOC_TYPE: dict[tuple, str] = {
    ("K1_POZEW_SPOLKA", False):                      "POZEW_SPOLKA",
    ("K1_POZEW_SPOLKA", True):                       "POZEW_SPOLKA",  # brak scenariuszy EPU dla tej ścieżki
    ("K1_POZEW_CZLONEK_ZARZADU", False):            "POZEW_CZLONEK_ZARZADU",
    ("K1_POZEW_CZLONEK_ZARZADU", True):             "EPU_POZEW_CZLONEK_ZARZADU",
    ("K1_NAKAZ_SPOLKA", False):                     "NAKAZ_SPOLKA",
    ("K1_NAKAZ_SPOLKA", True):                      "EPU_NAKAZ_SPOLKA",
    ("K1_NAKAZ_CZLONEK_ZARZADU", False):            "NAKAZ_CZLONEK_ZARZADU",
    ("K1_NAKAZ_CZLONEK_ZARZADU", True):             "EPU_NAKAZ_CZLONEK_ZARZADU",
    ("K1_WEZWANIE_SADOWE_SPOLKA", False):           "WEZWANIE_SADOWE_SPOLKA",
    ("K1_WEZWANIE_SADOWE_CZLONEK_ZARZADU", False):  "WEZWANIE_SADOWE_CZLONEK_ZARZADU",
    ("K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU", False):  "ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
    # Pisma komornicze (05.07.2026): wariant epu=True celowo mapowany tak samo —
    # pisma komornicze nie pochodzą z EPU, ale ekstrakcja AI potrafi błędnie
    # zwrócić epu=true (np. gdy tytułem wykonawczym w piśmie jest nakaz EPU);
    # scenariusze komornicze mają epu_flag=NIE, a kaskada w find_scenario()
    # znajdzie je drugą próbą (dopasowanie bez warunku EPU).
    ("K1_PISMO_KOMORNIK_SPOLKA", False):            "PISMO_KOMORNIK_SPOLKA",
    ("K1_PISMO_KOMORNIK_SPOLKA", True):             "PISMO_KOMORNIK_SPOLKA",
    ("K1_PISMO_KOMORNIK_CZLONEK_ZARZADU", False):   "PISMO_KOMORNIK_CZLONEK_ZARZADU",
    ("K1_PISMO_KOMORNIK_CZLONEK_ZARZADU", True):    "PISMO_KOMORNIK_CZLONEK_ZARZADU",
    # (06.07.2026) Przedsądowe wezwanie do zapłaty do członka zarządu — nie
    # pochodzi z EPU, więc tylko wariant epu=False (w odróżnieniu od pism
    # komorniczych, tu nie ma tytułu wykonawczego, który AI mogłaby pomylić
    # z nakazem EPU).
    ("K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU", False): "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU",
    ("K1_INNE_NIE_WIEM", False):                    "DOKUMENT_NIEUSTALONY_PRAWNY",
}

_FALLBACK_DOC_TYPE = "DOKUMENT_NIEUSTALONY_PRAWNY"


def resolve_doc_type(k1_code: str, epu: bool) -> str:
    """Zamienia kod K1 + EPU na main_document_type_code."""
    return _K1_TO_DOC_TYPE.get((k1_code, epu), _FALLBACK_DOC_TYPE)


def find_scenario(
    k1_code: str,
    k2_code: str,
    risk_level_code: str,
    epu: bool,
    scenarios_df: pd.DataFrame | None = None,
) -> dict:
    """
    Wyszukuje pasujący scenariusz bazowy.

    Kolejność prób:
    1. Dokładny match: doc_type + K2 + risk_level + epu_flag
    2. Bez warunku EPU: doc_type + K2 + risk_level
    3. Fallback na DOKUMENT_NIEUSTALONY_PRAWNY + K2 + risk_level
    4. Fallback na DOKUMENT_NIEUSTALONY_PRAWNY + RISK_MEDIUM
    """
    if scenarios_df is None:
        scenarios_df = load_scenarios()

    df = scenarios_df[scenarios_df["scenario_status"] == "AKTYWNY"].copy()

    doc_type = resolve_doc_type(k1_code, epu)
    epu_val = "TAK" if epu else "NIE"

    def _match(doc: str, k2: str, risk: str, epu_col: str | None) -> dict | None:
        mask = (
            (df["main_document_type_code"] == doc)
            & (df["K2_answer_code"] == k2)
            & (df["risk_level_code"] == risk)
        )
        if epu_col is not None:
            mask &= df["epu_flag"] == epu_col
        hits = df[mask]
        if not hits.empty:
            return hits.iloc[0].to_dict()
        return None

    row = (
        _match(doc_type, k2_code, risk_level_code, epu_val)
        or _match(doc_type, k2_code, risk_level_code, None)
        or _match(_FALLBACK_DOC_TYPE, k2_code, risk_level_code, "NIE")
    )

    if row is None:
        # absolutny fallback – pierwszy aktywny scenariusz DOKUMENT_NIEUSTALONY
        hits = df[df["main_document_type_code"] == _FALLBACK_DOC_TYPE]
        row = hits.iloc[0].to_dict() if not hits.empty else {}

    return row or {}
