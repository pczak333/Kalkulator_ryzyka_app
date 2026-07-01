# -*- coding: utf-8 -*-
"""Ekstrakcja pól dokumentu przez Claude Haiku — główna ścieżka (nie regex).

Polska legalna korespondencja ma dużą liczbę gramatycznych odmian tej samej
formuły ("nakazuje pozwanemu", "strona pozwana", "stronie pozwanej", "stronę
powodową"...) — regex w doc_extractor.py musi znać każdą z góry. AI rozumie
tekst niezależnie od konkretnej odmiany, więc jest odporniejsza na nowe,
nieprzewidziane sformułowania. Koszt jest pomijalny (Haiku, ~$0,001-0,002 na
dokument), więc jest to teraz PIERWSZY wybór, a regex w doc_extractor.py
pozostaje tanim fallbackiem gdy brak klucza API lub AI zawiedzie.
"""
from __future__ import annotations
import json
import re

_MODEL = "claude-haiku-4-5-20251001"
_MAX_CHARS = 4000

_PROMPT_TEMPLATE = (
    "Masz przed sobą tekst polskiego pisma sądowego lub prawnego (po OCR).\n"
    "Wyciągnij następujące informacje w formacie JSON (null jeśli nie znaleziono):\n"
    "{{\n"
    '  "sygnatura": "sygnatura akt np. V GNc 2034/22/S",\n'
    '  "sad_organ": "pełna nazwa sądu lub organu",\n'
    '  "powod": "imię i nazwisko lub nazwa powoda/wierzyciela",\n'
    '  "pozwany": "imię i nazwisko lub nazwa pozwanego/dłużnika/wzywanego",\n'
    '  "termin_dni": liczba_lub_null,\n'
    '  "kwota_zl": liczba_lub_null,\n'
    '  "adresat": "czlonek_zarzadu" lub "spolka" lub "organ" lub null,\n'
    '  "epu": true lub false\n'
    "}}\n\n"
    'Zasady dla pola "adresat" — decyduje WYŁĄCZNIE forma prawna pozwanego/'
    "wzywanego (nie szukaj wprost słów \"art. 299\"/\"członek zarządu\" — ten "
    "kalkulator dotyczy tylko spraw odpowiedzialności członków zarządu, więc "
    "gdy pozwanym jest osoba fizyczna, ZAWSZE zakładaj, że chodzi o członka "
    "zarządu, nawet jeśli podstawa prawna nie jest w tym piśmie wprost "
    "wspomniana — może wynikać z innych dokumentów w sprawie):\n"
    '- "czlonek_zarzadu": pozwany/wzywany to OSOBA FIZYCZNA (imię i nazwisko, '
    'PESEL, "Pan"/"Pani") — niezależnie od tego, czy dokument wprost wspomina '
    "art. 299 KSH czy nie.\n"
    '- "spolka": pozwany/wzywany to SPÓŁKA jako taka (Sp. z o.o., S.A., sp. k. '
    "itp. w NAZWIE POZWANEGO).\n"
    '- "organ": pozwanym/organem wydającym pismo jest ZUS, Urząd Skarbowy lub '
    "inny organ publiczny.\n"
    '- null: nie da się jednoznacznie ustalić.\n'
    '"epu" = true, jeśli pismo pochodzi z elektronicznego postępowania '
    'upominawczego (e-sąd, Sąd Rejonowy Lublin-Zachód, sygnatura "Nc-e").\n\n'
    "Odpowiedź TYLKO w formacie JSON, bez komentarzy.\n\nTekst dokumentu:\n"
)


def extract_fields_ai(text: str, api_key: str) -> dict:
    """Wyciąga pola dokumentu przez Claude Haiku → słownik z polami.

    Zwraca {} przy braku klucza, błędzie API lub niepoprawnym JSON — wołający
    ma wtedy użyć wyniku z doc_extractor.extract_fields() (regex) bez zmian.
    """
    if not api_key or not text:
        return {}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _PROMPT_TEMPLATE + text[:_MAX_CHARS]
        response = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}
