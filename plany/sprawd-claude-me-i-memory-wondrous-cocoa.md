# Plan: Przedsądowe wezwania do zapłaty — scalenie PR #1 + fix bramki

## Context

Problem zgłoszony w "ostatnia konwersacja.txt" (06.07.2026):  
Dwa typy przedsądowych wezwań do zapłaty są obsługiwane niepoprawnie:

**Typ 1** — wezwanie skierowane do spółki (zwykła faktura/należność firmy, bez art. 299 KSH).  
Kalkulator wciągał je w pełną analizę ryzyka osobistego — nieprofesjonalne.  
Fix: ostrzeżenie + zerowanie pól formularza, bez K1/scenariuszy.

**Typ 2** — wezwanie powołujące się na art. 299 KSH, skierowane do członka zarządu.  
Kalkulator wyświetlał: (a) bramkę art. 299 mimo że dokument JUŻ jawnie ją potwierdza, (b) K1 = "inne/nie wiem" zamiast dedykowanej opcji, (c) scenariusz "rodzaj pisma nieustalony".  
Panel techniczny klasyfikował poprawnie — mismatch między klasyfikacją a K1/scenariuszem.

Sesja 06.07 naprawiła Typ 1 + Typ 2 K1/scenariusze, ale zostawiła wynik w PR #1 (draft)  
na gałęzi `worktree-jest-problem-z-w-a-ciw-stateless-teapot` — NIGDY nie scalono z etap2.  
Bramka (Typ 2) nie była naprawiona w PR.

---

## Co robi PR #1 (cherry-pick commit 378a5f0)

Pliki zmienione w PR:

| Plik | Zmiana |
|---|---|
| `app/app.py` | EPU_COMPATIBLE += K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU; `_SPOLKA_OUT_OF_SCOPE_TYPES = {"WEZWANIE_PRZEDSADOWE_SPOLKA"}` + baner ostrzeżenia Typ 1 + zerowanie pól Typ 1 |
| `app/doc_processor.py` | `_DOC_TYPE_TO_K1`: WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU → K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU |
| `app/scenario_selector.py` | `_K1_TO_DOC_TYPE`: (K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU, False) → WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU |
| `dane_wejściowe/csv/08_...csv` | Nowa opcja K1 "Wezwanie przedsądowe (członek zarządu)" |
| `dane_wejściowe/csv/09_...csv` | Punktacja C=2 dla nowej opcji K1 |
| `dane_wejściowe/csv/12_...csv` | 15 nowych scenariuszy BASE_210-224 (5 K2 × 3 poziomy ryzyka) |
| `dane_wejściowe/KRS_Guard_...xlsx` | Excel zsynchronizowany |

## Dodatkowa naprawa (NIE w PR — do zrobienia teraz)

**Bramka art. 299 dla WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU** — plik `app/app.py`.

Obecny warunek:
```python
_person_doc = (prefill.doc_type_code.endswith("_CZLONEK_ZARZADU")
               and not _pozwany_is_company)
```

Po poprawce (ten typ już koduje art. 299 w nazwie — bramka jest redundantna):
```python
_NO_GATE_TYPES = {"WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU"}

_person_doc = (prefill.doc_type_code.endswith("_CZLONEK_ZARZADU")
               and not _pozwany_is_company
               and prefill.doc_type_code not in _NO_GATE_TYPES)
```

---

## Kroki implementacji

1. **Cherry-pick commit 378a5f0** z gałęzi worktree do etap2  
   `git cherry-pick 378a5f0`  
   (Pomijamy 469363b — to tylko notka CLAUDE.md o "PR draft", którą zastąpimy nową dokumentacją)

2. **Fix bramki** w `app/app.py` — dodaj `_NO_GATE_TYPES` i rozszerz warunek `_person_doc`

3. **Test regresji** — uruchom `python tools/regression_test.py --only "przed._wez_do_zap..pdf"`  
   (Typ 1, InterRisk — powinien dalej klasyfikować się jako WEZWANIE_PRZEDSADOWE_SPOLKA + baner ostrzeżenia)

4. **Test przeds._wezw._do_zap2.pdf** — uruchom aplikację, wgraj plik, sprawdź wynik;  
   Jeśli Typ 1 (spółka) → baner + brak analizy; jeśli Typ 2 (art. 299) → brak bramki + poprawny K1

5. **Aktualizuj CLAUDE.md** z decyzjami (Typ 1, Typ 2, bramka, 15 scenariuszy, merge PR)

6. **Commit + push** do etap2

---

## Weryfikacja

- `przed._wez_do_zap..pdf` (InterRisk, Typ 1): baner "dokument dotyczy zobowiązania spółki", formularz K1-K7 pusty, tabela ukryta
- Dokument Typ 2 (art. 299 wezwanie): brak bramki → K1 = "Wezwanie przedsądowe (członek zarządu)" pre-selected → scenariusz BASE_21x zamiast "rodzaj pisma nieustalony"
- Regresja na starszych plikach: 0 nowych FAIL

---

## Pliki krytyczne

- `app/app.py` — cherry-pick + 4-linijkowy fix bramki (wiersze ~587-590)
- `app/doc_processor.py` — cherry-pick (1 wpis w _DOC_TYPE_TO_K1)
- `app/scenario_selector.py` — cherry-pick (1 wpis w _K1_TO_DOC_TYPE)
- `dane_wejściowe/csv/08_...csv`, `09_...csv`, `12_...csv` — cherry-pick (CSV)
- `dane_wejściowe/KRS_Guard_...xlsx` — cherry-pick (Excel)
