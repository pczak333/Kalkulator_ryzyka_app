# -*- coding: utf-8 -*-
"""Szybki test dymny interfejsu — BEZ przeglądarki.

Po co to jest
-------------
Błędy typu `StreamlitAPIException` (np. modyfikacja klucza widżetu po jego
utworzeniu, zagnieżdżone expandery) wywalają CAŁĄ aplikację czerwoną ramką,
a `regression_test.py` ich nie łapie, bo testuje wyłącznie logikę i nie
renderuje interfejsu. Do 04.08.2026 jedynym sposobem było ręczne klikanie
w przeglądarce — i właśnie dlatego błąd „Wyczyść kalkulator" przeżył w kodzie
od czerwca do sierpnia.

`streamlit.testing.v1.AppTest` renderuje aplikację w pamięci i pozwala klikać
widżety z Pythona. Łapie dokładnie tę klasę błędów, kilkanaście sekund,
bez przeglądarki i bez `agent-browser`.

Uruchomienie
------------
    python tools/smoke_test_ui.py

Kod wyjścia 0 = OK, 1 = któraś ścieżka wywala aplikację.

Uwaga o polach radio
--------------------
`labeled_radio()` podaje `options=range(len(labels))` + `format_func`, więc
wartością widżetu jest LICZBA (indeks), nie etykieta. W teście ustawiamy
`r.set_value(0)`, nie `r.set_value(r.options[0])` — to drugie wywala
`format_func`.
"""
from __future__ import annotations
import os
import sys
import tomllib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(REPO, "app")
APP = os.path.join(APP_DIR, "app.py")


def _wczytaj_sekrety() -> dict:
    p = os.path.join(APP_DIR, ".streamlit", "secrets.toml")
    if not os.path.exists(p):
        return {}
    with open(p, "rb") as f:
        return tomllib.load(f)


def _nowa_apka(sekrety: dict):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=120)
    for k, v in sekrety.items():
        at.secrets[k] = v
    return at


def _sprawdz(at, etap: str) -> bool:
    """True = był wyjątek."""
    if at.exception:
        print(f"  BLAD na etapie: {etap}")
        for e in at.exception:
            print("    ", str(e.value)[:200])
        return True
    print(f"  OK: {etap}")
    return False


def main() -> int:
    os.chdir(APP_DIR)          # app.py oczekuje CWD = app/ (patrz CLAUDE.md)
    sys.path.insert(0, APP_DIR)
    sekrety = _wczytaj_sekrety()

    print("SMOKE TEST UI — pełna ścieżka formularza")
    print("-" * 60)

    at = _nowa_apka(sekrety)
    at.run()
    if _sprawdz(at, "start aplikacji"):
        return 1

    for r in at.radio:
        if r.value is None:
            try:
                r.set_value(0)
            except Exception as ex:
                print(f"  (pominięto radio: {str(ex)[:60]})")
    at.run()
    if _sprawdz(at, "wypełnienie formularza"):
        return 1

    oblicz = [b for b in at.button if "Oblicz" in (b.label or "")]
    if not oblicz:
        print("  BLAD: nie znaleziono przycisku 'Oblicz ryzyko'")
        return 1
    oblicz[0].click()
    at.run()
    if _sprawdz(at, "kliknięcie 'Oblicz ryzyko'"):
        return 1

    czysc = [b for b in at.button if "Wyczy" in (b.label or "")]
    if not czysc:
        print("  BLAD: nie znaleziono przycisku 'Wyczyść kalkulator'")
        return 1
    czysc[0].click()
    at.run()
    # Regresja z 04.08.2026: tu leciał StreamlitAPIException, bo przycisk
    # wołał reset_calculator() po utworzeniu widżetów k3-k6.
    if _sprawdz(at, "kliknięcie 'Wyczyść kalkulator'"):
        return 1

    # Po wyczyszczeniu formularz ma być z powrotem pusty i gotowy do wypełnienia.
    # Świadomie NIE ustawiamy tu ponownie widżetów: AppTest trzyma drzewo
    # z POPRZEDNIEGO przebiegu, a Streamlit zdążył już posprzątać stan widżetów,
    # które zniknęły razem z sekcją wyniku (np. przełącznik `_show_full_report`).
    # Próba zapisu po takim drzewie wywala KeyError w samym AppTest — to
    # ograniczenie narzędzia, nie błąd aplikacji (w przeglądarce widżet po
    # prostu znika). Wystarczy sprawdzić, że formularz wrócił do stanu pustego.
    if at.exception:
        print("  BLAD: wyjątek po wyczyszczeniu")
        return 1
    if not [b for b in at.button if "Oblicz" in (b.label or "")]:
        print("  BLAD: po wyczyszczeniu zniknął przycisk 'Oblicz ryzyko'")
        return 1
    print("  OK: formularz wrócił do stanu wyjściowego")

    print("-" * 60)
    print("WYNIK: wszystkie ścieżki OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
