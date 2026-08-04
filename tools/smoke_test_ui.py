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

Czego ten test NIE łapie
------------------------
Błędu „usunięcie klucza widżetu nie czyści pola" (`pop()` zamiast nadpisania).
W przeglądarce frontend nadal trzyma wartość widżetu i odsyła ją przy kolejnym
przebiegu; AppTest nie ma prawdziwego frontendu, więc przechodzi mimo błędu.
Sprawdzone empirycznie 04.08.2026. **Zmiany w `reset_calculator()` trzeba
przeklikać w przeglądarce.**

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

    # Po wyczyszczeniu formularz ma być z powrotem PUSTY.
    # Świadomie NIE ustawiamy tu ponownie widżetów: AppTest trzyma drzewo
    # z POPRZEDNIEGO przebiegu, a Streamlit zdążył już posprzątać stan widżetów,
    # które zniknęły razem z sekcją wyniku (np. przełącznik `_show_full_report`).
    # Próba zapisu po takim drzewie wywala KeyError w samym AppTest — to
    # ograniczenie narzędzia, nie błąd aplikacji (w przeglądarce widżet po
    # prostu znika).
    if not [b for b in at.button if "Oblicz" in (b.label or "")]:
        print("  BLAD: po wyczyszczeniu zniknął przycisk 'Oblicz ryzyko'")
        return 1

    # (04.08.2026) Sprawdzenie, czy pola FAKTYCZNIE są puste.
    #
    # ⚠️ ZNANE OGRANICZENIE — ten warunek NIE wykrywa błędu „pop() nie czyści
    # widżetu". Sprawdzone empirycznie: test przechodzi także na wersji kodu
    # sprzed naprawy, w której kroki 1, 3 i 7 realnie zostawały zaznaczone
    # w przeglądarce. Powód: w prawdziwej przeglądarce frontend nadal trzyma
    # wartość widżetu i odsyła ją przy kolejnym przebiegu, więc usunięcie klucza
    # z session_state nic nie daje — trzeba go NADPISAĆ. AppTest nie ma
    # prawdziwego frontendu, więc tej sytuacji nie odtwarza.
    # Wniosek: zmiany w `reset_calculator()` wymagają sprawdzenia W PRZEGLĄDARCE.
    # Poniższy warunek zostaje jako tania ochrona przed innymi regresjami.
    niewyczyszczone = [
        (r.label or "?")[:45] for r in at.radio if r.value is not None
    ]
    if niewyczyszczone:
        print(f"  BLAD: {len(niewyczyszczone)} pól nie wyczyściło się:")
        for etykieta in niewyczyszczone:
            print(f"      - {etykieta}")
        return 1
    zaznaczone_checkboxy = [
        (c.label or "?")[:45] for c in at.checkbox if c.value
    ]
    if zaznaczone_checkboxy:
        print(f"  BLAD: checkboxy nadal zaznaczone: {zaznaczone_checkboxy}")
        return 1
    print(f"  OK: wszystkie pola wyczyszczone ({len(at.radio)} radio, "
          f"{len(at.checkbox)} checkbox)")

    print("-" * 60)
    print("WYNIK: wszystkie ścieżki OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
