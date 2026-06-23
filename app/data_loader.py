"""Wczytuje pliki CSV z dane_wejściowe/csv/ do pandas DataFrames."""
import os
import pandas as pd

_BASE = os.path.join(os.path.dirname(__file__), "..", "dane_wejściowe", "csv")


def _read(filename: str) -> pd.DataFrame:
    path = os.path.join(_BASE, filename)
    with open(path, encoding="utf-8") as f:
        first = f.readline().strip()
    # Wiersz tytułowy ma tylko jedną niepustą komórkę (reszta to ;; po sobie)
    cells = first.split(";")
    non_empty = [c for c in cells if c.strip()]
    skip = 1 if len(non_empty) <= 1 else 0
    df = pd.read_csv(path, sep=";", skiprows=skip, encoding="utf-8", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df.dropna(how="all")


def load_scoring() -> pd.DataFrame:
    """CSV 09: punktacja C/P/H/W per kod odpowiedzi."""
    return _read("09_5_Punktacja_formularza.csv")


def load_risk_interpretation() -> pd.DataFrame:
    """CSV 10: zakres punktów → poziom ryzyka."""
    return _read("10_5A_Interpretacja_wyniku.csv")


def load_hard_rules() -> pd.DataFrame:
    """CSV 11: twarde reguły HR01–HR10."""
    return _read("11_5B_Twarde_reguly.csv")


def load_scenarios() -> pd.DataFrame:
    """CSV 12: biblioteka 173 scenariuszy bazowych."""
    return _read("12_6_Biblioteka_scenariuszy.csv")


def load_form_questions() -> pd.DataFrame:
    """CSV 08: pytania formularza K1–K7."""
    return _read("08_4_Formularz_6_krokow.csv")


def load_doc_types() -> pd.DataFrame:
    """CSV 07: typy dokumentów z kompatybilnością EPU."""
    return _read("07_3_Typy_dokumentow.csv")


def load_k3k6_modules() -> pd.DataFrame:
    """CSV 22: moduły tekstowe K3–K6."""
    return _read("22_6A_Moduly_K3_K6.csv")


def load_deadline_rules() -> pd.DataFrame:
    """CSV 24: reguły języka terminu."""
    return _read("24_6D_Reguly_tekstu_terminu.csv")


def load_urgency_rules() -> pd.DataFrame:
    """CSV 25: reguły pilności członka zarządu."""
    return _read("25_6E_Reguly_pilnosci_czlonka_zarz.csv")


def load_krs_rules() -> pd.DataFrame:
    """CSV 26: reguły KRS i next step."""
    return _read("26_6F_Reguly_KRS_next_step.csv")


def load_epu_sprzeciw_rules() -> pd.DataFrame:
    """CSV 28: reguły EPU sprzeciw."""
    return _read("28_6H_Reguly_EPU_sprzeciw.csv")


def load_zus_rules() -> pd.DataFrame:
    """CSV 40: reguły ZUS/urząd."""
    return _read("40_6U_ZUS_urzad_v35.csv")


def load_quantity_rules() -> pd.DataFrame:
    """CSV 36: reguły kwoty roszczenia."""
    return _read("36_6Q_Reguly_kwoty_roszczenia.csv")


def load_unknown_doc_rules() -> pd.DataFrame:
    """CSV 38: reguły dokumentu nieustalonego."""
    return _read("38_6S_Dokument_nieustalony_v34.csv")


def load_epu_block() -> pd.DataFrame:
    """CSV 13: blok edukacyjny EPU/e-Sąd (nagłówek + tekst + zastrzeżenie)."""
    return _read("13_Blok_EPU.csv")


def load_tests() -> pd.DataFrame:
    """CSV 17: testy kontrolne."""
    return _read("17_10_Testy_kontrolne.csv")
