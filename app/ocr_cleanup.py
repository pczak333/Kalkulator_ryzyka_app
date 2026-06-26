# -*- coding: utf-8 -*-
"""Czyszczenie tekstu po OCR — polskie pisma sądowe.
Źródło: adaptacja kodu archiwalnego (app_archiwalna.py, linie 990–1095).
"""
from __future__ import annotations
import re
from typing import List


# Typowe pomyłki Tesseract w polskich pismach sądowych
_REPLACEMENTS = [
    ("Sadu", "Sądu"), ("sadzie", "sądzie"), ("Sadzie", "Sądzie"),
    ("Wydzial", "Wydział"), ("wydzial", "wydział"),
    ("Cywiynym", "Cywilnym"), ("CywiInym", "Cywilnym"), ("Cywiiynym", "Cywilnym"),
    ("zaplaty", "zapłaty"), ("Zaplaty", "Zapłaty"), ("zapiały", "zapłaty"),
    ("zapłały", "zapłaty"), ("Zapiały", "Zapłaty"), ("Zapłały", "Zapłaty"),
    ("postepowaniu", "postępowaniu"), ("Postepowaniu", "Postępowaniu"),
    ("doreczenia", "doręczenia"), ("Doreczenia", "Doręczenia"),
    ("elekironicznym", "elektronicznym"), ("elektroniczaych", "elektronicznych"),
    ("plaćówce", "placówce"), ("placéwce", "placówce"),
    ("operalora", "operatora"), ("operałora", "operatora"),
    ("Rzeczypospolilej", "Rzeczypospolitej"),
    ("Referendatz", "Referendarz"), ("referendatz", "referendarz"),
    ("Dała wydania", "Data wydania"), ("Wydziałe", "Wydziale"),
    ("poiłe", "poczcie"), ("lułego", "lutego"),
]


def clean_ocr_text(text: str) -> str:
    """
    Czyści surowy tekst OCR z typowych błędów Tesseract dla polskich pism sądowych.
    Stosować po OCR, przed ekstrakcją pól i analizą AI.
    """
    if not text:
        return text

    t = text

    # Ujednolicenie myślników / separatorów stron
    t = t.replace("—", "-").replace("–", "-")

    # Typowe zamiany znaków w liczbach (OCR): ] / | / I / l między cyframi → 1, O → 0
    t = re.sub(r"(?<=\d)[\]\[|Il](?=\d)", "1", t)
    t = re.sub(r"(?<=\d)[oO](?=\d)", "0", t)
    t = re.sub(r"(?<=\d)\]\s(?=\d{3}[,\.])", "1 ", t)

    # Słownikowe zamiany polskich błędów OCR
    for wrong, correct in _REPLACEMENTS:
        t = t.replace(wrong, correct)

    # Czyszczenie linii-śmieci
    cleaned_lines: list[str] = []
    for raw_ln in t.split("\n"):
        ln = raw_ln.strip()
        if not ln:
            cleaned_lines.append("")
            continue
        # Separatory stron "--- STRONA X ---" — ZACHOWAJ (potrzebne do segmentacji)
        if re.fullmatch(r"---\s*STRONA\s+\d+\s*---", ln, flags=re.I):
            cleaned_lines.append(ln)
            continue
        # Inne linie z "STRONA N" (artefakty OCR) — usuń
        if re.fullmatch(r"[-=]{2,}\s*STRONA\s*\d+\s*[-=]{2,}", ln, flags=re.I):
            continue
        # 1–2 losowe litery
        if re.fullmatch(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{1,2}", ln):
            continue
        # same znaki niealfanumeryczne
        if re.fullmatch(r"[\W_]{1,4}", ln):
            continue
        # typowe artefakty OCR
        if re.fullmatch(r"(io|lo|ii|lll|HH|==+)", ln, flags=re.I):
            continue
        ln = re.sub(r"^[\s\|:;,_'`~•·]+", "", ln)
        ln = re.sub(r"[ \t]+", " ", ln)
        cleaned_lines.append(ln)

    t = "\n".join(cleaned_lines)

    # Porządki w białych znakach i interpunkcji
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    t = re.sub(r"([([])\s+", r"\1", t)
    t = re.sub(r"\s+([)])", r"\1", t)
    t = re.sub(r" +\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    # Normalizacja PESEL — Tesseract czasem gubi "L" lub zastępuje je artefaktem
    t = re.sub(r"\bPESE[^\w\s]", "PESEL", t)

    # OCR artifacts przy polskich samogłoskach ą/ó → spacja (typowe dla skanów B&W)
    # Np. "ciągu" → "ci gu",  "dwóch" → "dw ch"
    t = re.sub(r"\bci\s+gu\b", "ciągu", t)
    t = re.sub(r"\bdw\s+ch\b", "dwóch", t)

    # Normalizacja sygnatur
    t = re.sub(r"(?i)sygnatura\s+akt", "Sygnatura akt", t)
    t = re.sub(r"(?i)\bN[eę]-e\b", "Nc-e", t)
    t = re.sub(r"(?i)\bNc\s*e\b", "Nc-e", t)
    t = re.sub(r"(?i)\bV\]\b", "VI", t)
    t = re.sub(r"(?i)\bGNe\b", "GNc", t)

    # Scalanie sztucznie połamanych linii (bezpieczne heurystyki)
    lines_local = t.split("\n")
    merged: List[str] = []
    i = 0
    while i < len(lines_local):
        cur = lines_local[i].strip()
        if not cur:
            merged.append("")
            i += 1
            continue
        # zachowaj nagłówki CAPS
        if cur.isupper() and len(cur) > 5:
            merged.append(cur)
            i += 1
            continue
        while i + 1 < len(lines_local):
            nxt = lines_local[i + 1].strip()
            if not nxt:
                break
            if re.search(r"[.!?:;)]$", cur):
                break
            if nxt.isupper() and len(nxt) > 6:
                break
            if re.match(
                r"^(ul\.|al\.|sygnatura|data wydania|sąd|referendarz|kod )", nxt, flags=re.I
            ):
                break
            if re.match(r"^[a-ząćęłńóśźż0-9,(]", nxt):
                cur = f"{cur} {nxt}"
                i += 1
                continue
            break
        merged.append(cur)
        i += 1

    t = "\n".join(merged)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
