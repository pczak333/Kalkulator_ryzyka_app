# -*- coding: utf-8 -*-
"""Klasyfikuje typ dokumentu na podstawie tekstu i CSV 07."""
from __future__ import annotations
import re
import pandas as pd

_CSV_PATH = "../dane_wejściowe/csv/07_3_Typy_dokumentow.csv"
_EXCLUDE_TYPES = {"DOKUMENT_NIECZYTELNY", "DOKUMENT_NIEPRAWNY", "DOKUMENT_NIEUSTALONY_PRAWNY"}

def _load_doc_types() -> pd.DataFrame:
    return pd.read_csv(_CSV_PATH, sep=";", encoding="utf-8-sig", header=1)


def _score_text(text: str, keywords_raw: str, signals_raw: str) -> int:
    """Liczy punkty za trafienia słów kluczowych i sygnałów silnych."""
    score = 0
    if isinstance(keywords_raw, str):
        for kw in keywords_raw.split(";"):
            kw = kw.strip()
            if kw and re.search(re.escape(kw), text, re.IGNORECASE):
                score += 1
    if isinstance(signals_raw, str):
        for sig in signals_raw.split(";"):
            sig = sig.strip()
            if sig and re.search(re.escape(sig), text, re.IGNORECASE):
                score += 3  # sygnały silne ważą 3×
    return score


def classify_document(text: str, fields: dict) -> tuple[str, float]:
    """
    Zwraca (doc_type_code, confidence) gdzie confidence ∈ [0.0, 1.0].
    Używa CSV 07: słowa kluczowe + sygnały silne + bonus za EPU i adresata.
    """
    df = _load_doc_types()
    scores: dict[str, int] = {}

    for _, row in df.iterrows():
        code = str(row.get("document_type_code", "")).strip()
        if not code or code in _EXCLUDE_TYPES:
            continue

        base = _score_text(
            text,
            str(row.get("slowa_kluczowe", "")),
            str(row.get("sygnaly_silne", "")),
        )

        # Bonus za EPU
        if fields.get("epu") and code.startswith("EPU_"):
            base += 5

        # Bonus za adresata — główny wyróżnik między _CZLONEK_ZARZADU i _SPOLKA
        adresat = fields.get("adresat")
        if adresat == "czlonek_zarzadu" and "_CZLONEK_ZARZADU" in code:
            base += 15
        elif adresat == "spolka" and ("_SPOLKA" in code or code.endswith("_SPOLKA")):
            base += 15
        elif adresat == "organ" and ("ZUS" in code or "ORGAN" in code or "US_" in code):
            base += 15
        elif code == "PISMO_PROCESOWE_SADOWE" and adresat in ("czlonek_zarzadu", "spolka"):
            base += 15

        if base > 0:
            scores[code] = base

    # Formuła operatywna nakazu ("nakazuję pozwanemu") jako pozytywny sygnał dla NAKAZ_.
    # [\s\S]{0,15} zamiast \s+ — odporna na łamania linii w tabelach EPU (OCR).
    # Bonus zamiast kary: gdy OCR nie wyciągnie frazy, NAKAZ nie jest penalizowany —
    # o wyniku decydują wtedy słowa kluczowe (nakaz zapłaty > pozew).
    _has_nakaz_formula = bool(re.search(
        r"nakazuj[eę][\s\S]{0,15}pozwan",
        text, re.IGNORECASE
    ))
    if _has_nakaz_formula:
        for _c in list(scores):
            if "NAKAZ_" in _c:
                scores[_c] += 20

    # Frazy wnosicielskie lub tytuł "P O Z E W" jako pozytywny sygnał dla POZEW_.
    _has_pozew_signals = bool(re.search(
        r"(wnosimy\s+o|wnosz[eę]\s+o|P\s+O\s+Z\s+E\s+W)",
        text, re.IGNORECASE
    ))
    if _has_pozew_signals:
        for _c in list(scores):
            if "POZEW" in _c:
                scores[_c] += 20

    # Disambiguacja: sąd vs. komornik na podstawie wyciągniętego sad_organ
    _sad_organ = (fields.get("sad_organ") or "").lower()
    if _sad_organ:
        _is_court   = "sąd" in _sad_organ or "sad" in _sad_organ
        _is_bailiff = "komornik" in _sad_organ
        if _is_court and not _is_bailiff:
            for _c in list(scores):
                if "KOMORNIK" in _c:
                    scores[_c] = max(0, scores[_c] - 25)
        elif _is_bailiff and not _is_court:
            for _c in list(scores):
                if "KOMORNIK" not in _c and "UMORZENIE" not in _c:
                    scores[_c] = max(0, scores[_c] - 15)

    if not scores:
        return "DOKUMENT_NIEUSTALONY_PRAWNY", 0.0

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_code, best_score = sorted_scores[0]

    if len(sorted_scores) >= 2:
        second_score = sorted_scores[1][1]
        confidence = best_score / (best_score + second_score) if (best_score + second_score) > 0 else 0.5
    else:
        confidence = 0.85  # jedyny kandydat

    # Jeśli EPU nie jest zaznaczone ale kod wymaga EPU — degraduj
    if not fields.get("epu") and best_code.startswith("EPU_"):
        non_epu = [(c, s) for c, s in sorted_scores if not c.startswith("EPU_")]
        if non_epu:
            best_code, best_score = non_epu[0]
            confidence = min(confidence, 0.7)

    return best_code, round(confidence, 3)
