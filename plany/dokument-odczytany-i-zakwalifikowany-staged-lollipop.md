# Plan: Deep code review — naprawa klasyfikacji EPU, scoringu wyboru dokumentu głównego i reguł

## Context

Przegląd trzema agentami ujawnił dwa klastry bugów:
1. **Klasyfikator** — nakaz zapłaty EPU (Lublin, `VI Nc-e 222431/23`) jest klasyfikowany jako `EPU_POZEW_CZLONEK_ZARZADU` zamiast `EPU_NAKAZ_CZLONEK_ZARZADU`
2. **Wybór dokumentu głównego** (`doc_selector.py`) — brakuje kilku reguł z CSV 02 i score'y nie zgadzają się ze spec

---

## Błąd 1 (KRYTYCZNY): EPU_NAKAZ_* penalizowany przez sprawdzenie formuły nakazu

**Plik:** `app/doc_classifier.py`, linia 76

```python
if not _has_nakaz_formula:
    for _c in list(scores):
        if _c.startswith("NAKAZ_") or _c.startswith("EPU_NAKAZ_"):  # ← BUG
            scores[_c] = max(0, scores[_c] - 20)
```

**Przyczyna:** Kara -20 pkt za brak `nakazuję pozwanemu` dotyczy też `EPU_NAKAZ_*`. Nakazy EPU mają inne sformułowanie formuły (lub OCR je gubi), więc tracą 20 pkt i przegrywają z `EPU_POZEW_*`.

**Naprawa:** Usunąć `EPU_NAKAZ_*` z kary — EPU nakazy mają własne silne sygnały (`Nc-e`, `Sąd Rejonowy Lublin-Zachód`) które wystarczą do odróżnienia od pism procesowych.

```python
# Tylko non-EPU NAKAZ_* penalizuj
if _c.startswith("NAKAZ_"):   # EPU_NAKAZ_* zostają bez kary
    scores[_c] = max(0, scores[_c] - 20)
```

---

## Błąd 2 (WYSOKI): "Nc-e" w keywords EPU_POZEW faworyzuje go przy nakazach

**Plik:** `dane_wejściowe/csv/07_3_Typy_dokumentow.csv`

`EPU_POZEW_CZLONEK_ZARZADU` i `EPU_POZEW_SPOLKA` mają `Nc-e` w `slowa_kluczowe`. "Nc-e" to sygnatury NAKAZÓW (Nc = nakaz cywilny, e = elektroniczny) — nigdy nie powinno być słowem kluczowym pozwu EPU.

**Naprawa:** W obu wierszach EPU_POZEW: usunąć `Nc-e` z `slowa_kluczowe`. Pole `Sąd Rejonowy Lublin-Zachód` i `EPU` wystarczą do identyfikacji, a `Nc-e` pozostaje TYLKO w `EPU_NAKAZ_*`.

---

## Błąd 3 (WAŻNY): Błędne wartości w `_TYPE_SCORES` vs CSV 02

**Plik:** `app/doc_selector.py`, linie 9–33

| Typ | Kod teraz | CSV 02 | Reguła |
|---|---|---|---|
| `PISMO_KOMORNIK_SPOLKA` | 22 | **35** | R11 |
| `UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC` | 35 | **45** | R12 |
| `WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU` | 38 | **35** | R13 |
| `DECYZJA_ZUS_CZLONEK_ZARZADU` | 42 | **45** | R15 |
| `DECYZJA_US_CZLONEK_ZARZADU` | 42 | **45** | R15 |
| `ORGAN_PUBLICZNY_CZLONEK_ZARZADU` | 42 | **45** | R15 |

**Naprawa:** Poprawić wartości w dict `_TYPE_SCORES`.

---

## Błąd 4 (WAŻNY): Brakujące reguły scoring w `score_candidate()`

**Plik:** `app/doc_selector.py`, funkcja `score_candidate()` (linia 57–81)

CSV 02 definiuje reguły R22–R26, R30–R31, które nie są zaimplementowane:

| Reguła | Warunek | Punkty |
|---|---|---|
| R22 | Nie udało się ustalić terminu reakcji (`days_left is None`) | +10 |
| R23 | Dokument pochodzi z sądu | +25 |
| R24 | Dokument pochodzi od komornika | +25 |
| R25 | Dokument pochodzi od ZUS/organu | +25 |
| R26 | Dokument pochodzi od wierzyciela | +15 |
| R30 | Wysokie OCR confidence | +5 |
| R31 | Niskie OCR confidence | −10 |

**Naprawa:** Dodać do `score_candidate()`:

```python
# R22: nieznany termin
if days_left is None:
    total += 10

# R23-R26: źródło dokumentu (na podstawie doc_type_code)
_COURT_TYPES   = {"POZEW_CZLONEK_ZARZADU","NAKAZ_CZLONEK_ZARZADU","EPU_NAKAZ_CZLONEK_ZARZADU",
                  "EPU_POZEW_CZLONEK_ZARZADU","WEZWANIE_SADOWE_CZLONEK_ZARZADU","POZEW_SPOLKA",
                  "NAKAZ_SPOLKA","EPU_NAKAZ_SPOLKA","EPU_POZEW_SPOLKA","WEZWANIE_SADOWE_SPOLKA",
                  "PISMO_PROCESOWE_SADOWE"}
_BAILIFF_TYPES = {"PISMO_KOMORNIK_CZLONEK_ZARZADU","PISMO_KOMORNIK_SPOLKA",
                  "UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC"}
_ORGAN_TYPES   = {"DECYZJA_ZUS_CZLONEK_ZARZADU","DECYZJA_US_CZLONEK_ZARZADU",
                  "ORGAN_PUBLICZNY_CZLONEK_ZARZADU","DECYZJA_ZUS_US_SPOLKA"}
_CREDITOR_TYPES= {"WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU","WEZWANIE_PRZEDSADOWE_SPOLKA"}

if doc_type in _COURT_TYPES:    total += 25   # R23
elif doc_type in _BAILIFF_TYPES: total += 25  # R24
elif doc_type in _ORGAN_TYPES:   total += 25  # R25
elif doc_type in _CREDITOR_TYPES: total += 15 # R26

# R30-R31: jakość OCR
ocr = doc.get("ocr_quality", "")
if ocr == "HIGH": total += 5    # R30
elif ocr == "LOW": total -= 10  # R31
```

Uwaga: Stałe `_COURT_TYPES`, `_BAILIFF_TYPES` etc. zdefiniować na poziomie modułu (nie w funkcji) żeby nie tworzyć nowych setów przy każdym wywołaniu.

---

## Pliki do modyfikacji

| Plik | Zmiana |
|---|---|
| `app/doc_classifier.py` | Błąd 1: Usuń `EPU_NAKAZ_*` z penalizacji |
| `dane_wejściowe/csv/07_3_Typy_dokumentow.csv` | Błąd 2: Usuń `Nc-e` z keywords EPU_POZEW |
| `app/doc_selector.py` | Błąd 3: Popraw _TYPE_SCORES; Błąd 4: Dodaj R22–R26, R30–R31 |

---

## Co NIE jest zmieniane

- HR10 (OCR quality warning) — obecna implementacja jest konserwatywna ale akceptowalna; zmiana wymagałaby dodatkowych pól w `state` dict
- HR11 w CSV 11 — spec gap (HR11 nie ma w arkuszu), ale kod działa poprawnie; do uzupełnienia w Excelu przez autora
- Reguły remisu R5/R6 w `_tiebreak()` — brak krytyczny dla użytkownika, bo `_TYPE_SCORES` i tak faworyzuje dokumenty sądowe nad wierzycielskimi z dużą różnicą punktów
- Pojedynczy dokument pomocniczy jako "główny" (`if len(candidates) == 1`) — akceptowalny edge case

---

## Weryfikacja

1. **Test 1** (fix Błąd 1+2): Uruchomić app, wgrać `Lublin_pozew_nak._zap..pdf` → powinien wyświetlić "Nakaz zapłaty (e-Sąd / EPU)" NIE "Pozew (e-Sąd / EPU)"
2. **Test 2** (fix Błąd 3+4): Wgrać kilka dokumentów jednocześnie → sprawdzić w Panelu technicznym czy dokument z sądu wygrywa z wezwaniem przedsądowym o oczekiwaną różnicę punktów
3. **Test regresji**: Ponownie wgrać `art.299_pismow_przygot._powoda.pdf` → nadal powinien klasyfikować jako `PISMO_PROCESOWE_SADOWE` (nie `NAKAZ_*`)
