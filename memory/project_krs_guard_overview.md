---
name: project-krs-guard-overview
description: "NIEAKTUALNE (patrz uwaga niżej) — pierwotny przegląd projektu z 24.06.2026, sprzed konsolidacji gałęzi i Etapu 2. Zachowany jako rekord historyczny; aktualny, wyczerpujący opis projektu jest w CLAUDE.md."
metadata:
  node_type: memory
  type: project
  originSessionId: 3c9b50c6-dfa2-45f2-adc7-31fe9e756245
---

> **NIEAKTUALNE (dopisane 22.07.2026 przy synchronizacji pamięci między
> komputerami):** ten plik opisuje stan projektu z 24.06.2026, sprzed
> konsolidacji gałęzi (patrz [[project_branch_consolidation]] — repo ma dziś
> jedną gałąź `main`, nie ma już `etap2`) i sprzed pełnej implementacji
> Etapu 2. Zachowany wyłącznie jako rekord historyczny pierwszego zarysu
> projektu. **Aktualny, wyczerpująco utrzymywany opis architektury, danych
> wejściowych i logiki kalkulatora jest w `CLAUDE.md` w korzeniu repo — to on
> jest źródłem prawdy, nie ten plik.**

Projekt KRS Guard to kalkulator ryzyka prawnego dla spraw odpowiedzialności członków zarządu (art. 299 KSH). Na dzień 2026-06-24 aplikacja jest w pełni działająca — Etap 1 (formularz ręczny) przetestowany i oznaczony tagiem `v1.0-etap1`. Etap 2 (analiza dokumentów) zaimplementowany na gałęzi `etap2`, wymaga testów z prawdziwymi plikami.

**Why:** Narzędzie wstępnej kwalifikacji spraw klientów kancelarii; konwersja do płatnego Audytu 48h.

**How to apply:** Przy budowie aplikacji zawsze czytać logikę z plików danych (Excel/CSV), nie hardkodować reguł w kodzie. Etap 2 wymaga klucza `ANTHROPIC_API_KEY` w `app/.streamlit/secrets.toml`.

## Strategia gałęzi (HISTORYCZNA — nieaktualna, patrz [[project_branch_consolidation]])

- `main` — produkcja (Etap 1), udostępniona przez share.streamlit.io drugiej osobie testującej. NIE pushować kodu Etapu 2 do `main` przed zakończeniem testów.
- `etap2` — aktywny development (Etap 2). Wszystkie zmiany Etapu 2 idą tutaj.
- Tag `v1.0-etap1` — stabilny checkpoint Etapu 1.

## Dane wejściowe

- Excel: `dane_wejściowe/KRS_Guard_reguly_i_zasady_funkcjonowania.xlsx` — źródło nadrzędne
- Specyfikacja: `dane_wejściowe/KRS_Guard_specyfikacja_funkcjonalna_logiczna_tekstowa.md`
- CSV: `dane_wejściowe/csv/` — 41 plików, jeden per arkusz Excela

## Logika kalkulatora

Przepływ: wybór dokumentu głównego → ocena EPU → formularz K1–K7 → punktacja S = C+P+H+W → twarde reguły → scenariusz bazowy + reguły kontekstowe → wynik dla klienta.

Poziomy ryzyka: RISK_LOW (0-3), RISK_MEDIUM (4-5), RISK_HIGH (6-7), RISK_URGENT (8+).

## Kluczowe arkusze/CSV

| Plik CSV | Rola |
|---|---|
| 08_4_Formularz_6_krokow.csv | Pytania K1–K7, kody odpowiedzi |
| 09_5_Punktacja_formularza.csv | Wartości C/P/H/W per odpowiedź |
| 10_5A_Interpretacja_wyniku.csv | Mapa wynik → poziom ryzyka |
| 11_5B_Twarde_reguly.csv | 10 twardych reguł HR01–HR10 |
| 12_6_Biblioteka_scenariuszy.csv | 173 scenariusze bazowe (LICZBA NIEAKTUALNA — od tego czasu dopisano dziesiątki nowych scenariuszy, patrz CLAUDE.md) |
| 17_10_Testy_kontrolne.csv | 29 przypadków testowych regresyjnych (T01–T43) |
| 07_3_Typy_dokumentow.csv | Typy dokumentów, słowa kluczowe, sygnały silne (używane w Etapie 2) |
| 02_2_Reguly_wyboru_dok_glownego.csv | Reguły punktowe wyboru dokumentu głównego (Etap 2) |
| 04_2B_Reguly_remisu.csv | Reguły remisu przy wyborze dokumentu głównego (Etap 2) |
| 22_6A_Moduly_K3_K6.csv | Moduły tekstowe K3–K6 |
| 24–41 (6D–6V) | Reguły kontekstowe: termin, EPU, KRS, kwota, ZUS, dok. nieustalony |

## Zasady komunikacji (nienaruszalne)

- Nie pokazywać klientowi kodów K1–K7, RISK_*, HRxx, scenario_id
- Nie używać słowa "użytkownik" w wyniku klienta
- Nie generować sprzeciwu/odpowiedzi na pozew dla pism ZUS — tylko "złożenie wyjaśnień"
- Terminy = dni kalendarzowe (soboty, niedziele, święta wliczają się)
- Jeśli znana liczba dni — pokazać dokładną, nie przedział
- Kończyć CTA do Audytu 48h (bez twardej sprzedaży)
