# -*- coding: utf-8 -*-
"""Automatyczna regresja pipeline'u dokumentów (etap 2).

Uruchamia doc_processor.process_files() — tę samą ścieżkę co aplikacja
(OCR Azure DI → Claude Haiku → ekstrakcja AI → klasyfikacja → wybór
dokumentu głównego) — na plikach testowych i porównuje wynik z tabelą
oczekiwań w regression_expected.json.

Użycie:
    python tools/regression_test.py [--dir C:\\Users\\User\\Desktop\\testy] [--only NAZWA_PLIKU]

Każde uruchomienie kosztuje kilka-kilkanaście centów (Azure DI + Claude
Haiku na każdą stronę) — to akceptowalny koszt pewności, że poprawki mają
zastosowanie ogólne, a nie tylko do wcześniej analizowanych plików.

Format regression_expected.json (na plik; klucz nieobecny = nie sprawdzaj):
    "main_type":         lista akceptowalnych doc_type_code dokumentu głównego
    "main_pages":        [od, do] — zakres stron dokumentu głównego
    "deadline_days":     termin dokumentu głównego (null = ma go nie być)
    "amount":            kwota dokumentu głównego (tolerancja 0,01 zł)
    "aux_types_include": typy, które MUSZĄ wystąpić wśród dok. pomocniczych
    "gate":              czy bramka art. 299 powinna się pokazać
"""
from __future__ import annotations
import argparse
import io
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"
DEFAULT_TEST_DIR = Path(r"C:\Users\User\Desktop\testy")
EXPECTED_PATH = Path(__file__).resolve().parent / "regression_expected.json"

sys.path.insert(0, str(APP_DIR))
import os
os.chdir(APP_DIR)  # doc_classifier czyta CSV 07 ścieżką względną ../dane_wejściowe

from doc_processor import process_files  # noqa: E402
from doc_selector import is_company_name  # noqa: E402


class _FakeUpload(io.BytesIO):
    """Minimalny odpowiednik streamlit UploadedFile (bytes + .name)."""

    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


def _load_secrets() -> dict:
    secrets_path = APP_DIR / ".streamlit" / "secrets.toml"
    secrets: dict = {}
    if not secrets_path.exists():
        return secrets
    for line in secrets_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        secrets[key.strip()] = val.strip().strip('"').strip("'")
    return secrets


def _gate_should_fire(main) -> bool:
    return (main.doc_type_code.endswith("_CZLONEK_ZARZADU")
            and not is_company_name(main.pozwany))


def _check_file(pdf_path: Path, expected: dict, secrets: dict) -> list[str]:
    """Zwraca listę rozbieżności (pusta = PASS)."""
    data = pdf_path.read_bytes()
    upload = _FakeUpload(data, pdf_path.name)
    main, aux = process_files([upload], secrets)
    problems: list[str] = []

    if "main_type" in expected:
        allowed = expected["main_type"]
        if main.doc_type_code not in allowed:
            problems.append(
                f"main_type: jest {main.doc_type_code!r}, oczekiwano jednego z {allowed}")

    if "main_pages" in expected:
        exp_pages = tuple(expected["main_pages"])
        if tuple(main.page_range) != exp_pages:
            problems.append(
                f"main_pages: jest {tuple(main.page_range)}, oczekiwano {exp_pages}")

    if "deadline_days" in expected:
        exp_dl = expected["deadline_days"]
        if main.deadline_days != exp_dl:
            problems.append(
                f"deadline_days: jest {main.deadline_days!r}, oczekiwano {exp_dl!r}")

    if "amount" in expected:
        exp_amount = expected["amount"]
        if exp_amount is None:
            if main.amount is not None:
                problems.append(f"amount: jest {main.amount!r}, oczekiwano None")
        elif main.amount is None or abs(main.amount - exp_amount) > 0.01:
            problems.append(f"amount: jest {main.amount!r}, oczekiwano {exp_amount}")

    if "aux_types_include" in expected:
        aux_types = [d.doc_type_code for d in aux]
        for t in expected["aux_types_include"]:
            # wpis może być listą alternatyw albo pojedynczym typem
            alternatives = t if isinstance(t, list) else [t]
            if not any(a in aux_types for a in alternatives):
                problems.append(
                    f"aux_types: brak {alternatives} wśród {aux_types}")

    if "gate" in expected:
        gate = _gate_should_fire(main)
        if gate != expected["gate"]:
            problems.append(
                f"bramka art.299: jest {gate}, oczekiwano {expected['gate']} "
                f"(typ={main.doc_type_code}, pozwany={main.pozwany!r})")

    # Kontekst diagnostyczny przy niepowodzeniu
    if problems:
        aux_desc = ", ".join(
            f"{d.doc_type_code}[{d.page_range[0]}-{d.page_range[1]}]" for d in aux)
        problems.append(
            f"  (kontekst: main={main.doc_type_code}[{main.page_range[0]}-"
            f"{main.page_range[1]}] termin={main.deadline_days} kwota={main.amount} "
            f"pozwany={main.pozwany!r}; aux: {aux_desc or 'brak'})")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=str(DEFAULT_TEST_DIR),
                        help="folder z plikami testowymi")
    parser.add_argument("--only", default=None,
                        help="uruchom tylko dla pliku o tej nazwie")
    args = parser.parse_args()

    test_dir = Path(args.dir)
    expected_all: dict = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    secrets = _load_secrets()
    if not secrets.get("ANTHROPIC_API_KEY"):
        print("UWAGA: brak ANTHROPIC_API_KEY w secrets.toml — ekstrakcja AI "
              "nie zadziała, wyniki mogą odbiegać od oczekiwań produkcyjnych.")

    passed, failed, skipped = 0, 0, 0
    for fname, expected in expected_all.items():
        if args.only and fname != args.only:
            continue
        pdf_path = test_dir / fname
        if not pdf_path.exists():
            print(f"[SKIP] {fname} — brak pliku w {test_dir}")
            skipped += 1
            continue
        print(f"[....] {fname} — przetwarzam...", flush=True)
        try:
            problems = _check_file(pdf_path, expected, secrets)
        except Exception as e:  # noqa: BLE001 — raportuj i idź dalej
            problems = [f"WYJĄTEK: {type(e).__name__}: {e}"]
        if problems:
            failed += 1
            print(f"[FAIL] {fname}")
            for p in problems:
                print(f"       - {p}")
        else:
            passed += 1
            print(f"[PASS] {fname}")

    print(f"\nWynik: {passed} PASS, {failed} FAIL, {skipped} SKIP")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
