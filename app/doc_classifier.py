# -*- coding: utf-8 -*-
"""Klasyfikuje typ dokumentu na podstawie tekstu i CSV 07."""
from __future__ import annotations
import re
import pandas as pd

_CSV_PATH = "../dane_wejściowe/csv/07_3_Typy_dokumentow.csv"
_EXCLUDE_TYPES = {"DOKUMENT_NIECZYTELNY", "DOKUMENT_NIEPRAWNY", "DOKUMENT_NIEUSTALONY_PRAWNY"}

_DOC_TYPES_CACHE: pd.DataFrame | None = None


def _load_doc_types() -> pd.DataFrame:
    global _DOC_TYPES_CACHE
    if _DOC_TYPES_CACHE is None:
        _DOC_TYPES_CACHE = pd.read_csv(_CSV_PATH, sep=";", encoding="utf-8-sig", header=1)
    return _DOC_TYPES_CACHE


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

        # Bonus za adresata
        adresat = fields.get("adresat")
        if adresat == "czlonek_zarzadu" and "_CZLONEK_ZARZADU" in code:
            base += 4
        elif adresat == "spolka" and ("_SPOLKA" in code or code.endswith("_SPOLKA")):
            base += 4
        elif adresat == "organ" and ("ZUS" in code or "ORGAN" in code or "US_" in code):
            base += 4

        if base > 0:
            scores[code] = base

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
