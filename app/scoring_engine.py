"""Oblicza wynik S = C + P + H + W na podstawie kodów odpowiedzi K1–K7."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from data_loader import load_scoring, load_risk_interpretation

# Poziomy ryzyka w kolejności rosnącej
RISK_ORDER = ["RISK_LOW", "RISK_MEDIUM", "RISK_HIGH", "RISK_URGENT"]


@dataclass
class ScoreResult:
    C: int
    P: int
    H: int
    W: int
    S: int
    risk_level_code: str
    risk_level_label: str


def _build_score_map(df: pd.DataFrame) -> dict[str, dict]:
    """Buduje słownik {answer_code: {C, P, H, W}} z CSV 09."""
    result: dict[str, dict] = {}
    for _, row in df.iterrows():
        code = str(row.get("answer_code_AI", "")).strip()
        if not code or code == "nan":
            continue
        try:
            result[code] = {
                "C": int(float(str(row.get("points_C", 0) or 0))),
                "P": int(float(str(row.get("points_P", 0) or 0))),
                "H": int(float(str(row.get("points_H", 0) or 0))),
                "W": int(float(str(row.get("points_W", 0) or 0))),
            }
        except (ValueError, TypeError):
            continue
    return result


def _interpret_risk(score: int, df: pd.DataFrame) -> tuple[str, str]:
    """Zwraca (risk_level_code, risk_level_label) na podstawie sumy punktów."""
    for _, row in df.iterrows():
        code = str(row.get("risk_level_code", "")).strip()
        label = str(row.get("nazwa_poziomu", "")).strip()
        score_range = str(row.get("score_range", "")).strip()
        if not code or code == "nan":
            continue
        if ">=" in score_range:
            threshold = int(score_range.replace("S >=", "").strip())
            if score >= threshold:
                return code, label
        elif "=" in score_range and "–" in score_range:
            parts = score_range.replace("S =", "").strip().split("–")
            lo, hi = int(parts[0].strip()), int(parts[1].strip())
            if lo <= score <= hi:
                return code, label
        elif "<=" in score_range:
            threshold = int(score_range.replace("S <=", "").strip())
            if score <= threshold:
                return code, label
    # domyślnie
    if score >= 8:
        return "RISK_URGENT", "Sprawa pilna"
    if score >= 6:
        return "RISK_HIGH", "Wysokie ryzyko"
    if score >= 4:
        return "RISK_MEDIUM", "Średnie ryzyko / braki danych"
    return "RISK_LOW", "Niższe ryzyko / prewencja"


def calculate(answers: dict[str, str]) -> ScoreResult:
    """
    Oblicza wynik dla podanego zestawu odpowiedzi.

    Parameters
    ----------
    answers : dict
        Klucze to kody kroków (K1, K2, K3, K4, K5, K6, K7, K2A).
        Wartości to kody odpowiedzi, np. {"K1": "K1_NAKAZ_CZLONEK_ZARZADU"}.
    """
    score_df = load_scoring()
    risk_df = load_risk_interpretation()
    score_map = _build_score_map(score_df)

    C = P = H = W = 0
    for _step, code in answers.items():
        if code and code in score_map:
            pts = score_map[code]
            C += pts["C"]
            P += pts["P"]
            H += pts["H"]
            W += pts["W"]

    S = C + P + H + W
    risk_code, risk_label = _interpret_risk(S, risk_df)
    return ScoreResult(C=C, P=P, H=H, W=W, S=S,
                       risk_level_code=risk_code, risk_level_label=risk_label)


def elevate_risk(current_code: str, minimum_code: str) -> str:
    """Podnosi poziom ryzyka do minimum jeśli aktualny jest niższy."""
    curr_idx = RISK_ORDER.index(current_code) if current_code in RISK_ORDER else 0
    min_idx = RISK_ORDER.index(minimum_code) if minimum_code in RISK_ORDER else 0
    return RISK_ORDER[max(curr_idx, min_idx)]


def risk_label_for_code(code: str) -> str:
    labels = {
        "RISK_LOW": "Niższe ryzyko / prewencja",
        "RISK_MEDIUM": "Średnie ryzyko / braki danych",
        "RISK_HIGH": "Wysokie ryzyko",
        "RISK_URGENT": "Sprawa pilna",
    }
    return labels.get(code, code)
