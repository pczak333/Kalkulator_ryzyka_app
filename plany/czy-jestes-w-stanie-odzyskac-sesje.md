# Plan: dokończenie przerwanej sesji (bramka art.299 dla wezwań przedsądowych)

## Context

Poprzednia sesja została przerwana z powodu limitu w trakcie realizacji planu
`plany/przed-kontynuacj-pracy-z-glistening-hanrahan.md`. Odtworzyłem stan
w trybie read-only:

- **Zrobione i zacommitowane**: continuity workflow (`memory/`, `plany/`,
  env var `KRS_GUARD_TESTY_DIR`) w commicie `f1c883b`; cherry-pick fixu
  "K1 dla wezwań przedsądowych członka zarządu" do `etap2` w commicie
  `f6d673f` — potwierdzone `git patch-id` jako identyczny patch co commit
  `378a5f0` z brancha PR #1.
- **W toku, niezacommitowane** (dokładnie punkt B4 planu): `app/app.py` ma
  nowy `_NO_GATE_TYPES = {"WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU"}`, żeby
  bramka art. 299 nie pytała redundantnie o typ dokumentu, który już koduje
  art. 299 w klasyfikacji. Towarzyszące zmiany: `tools/regression_test.py`
  (`_gate_should_fire()` lustrzanie do app.py + porządek `import os`) i
  `tools/regression_expected.json` (`gate: true→false` dla
  `299_przeds._wezw._do_zap..pdf`).
- **Nie zrobione**: regresja z tą poprawką nie uruchomiona; ręczna weryfikacja
  w żywej aplikacji nie zrobiona; `CLAUDE.md` i
  `memory/project_wezwania_przedsadowe.md` nadal piszą "not merged" (stan
  sprzed cherry-picka); PR #1 nadal otwarty jako DRAFT na GitHubie.

Celem tej sesji jest dokończyć dokładnie to, co zostało przerwane — bez
zmiany zakresu czy podejścia, bo poprzedni plan był już zweryfikowany i
zaakceptowany.

## Kroki

1. **Uruchom pełną regresję** (`python tools/regression_test.py`) z bieżącą,
   niezacommitowaną poprawką bramki. Oczekiwany wynik: 0 nowych FAIL
   względem stanu sprzed zmiany, w szczególności `299_przeds._wezw._do_zap..pdf`
   → `gate: false`, a `przeds._wezw._do_zap2.pdf` (Typ 1, spółka) bez zmian.
2. **Ręczna weryfikacja w żywej aplikacji** (`streamlit run app/app.py`) —
   otworzyć `299_przeds._wezw._do_zap..pdf`: sprawdzić brak pytania bramki,
   K1 pre-selected = "Wezwanie przedsądowe (członek zarządu)", scenariusz
   BASE_21x (nie "rodzaj pisma nieustalony"). Jeśli w tym środowisku nie da
   się sterować przeglądarką, jasno to zgłosić i polegać na kroku 1 +
   przeglądzie kodu.
3. **Zaktualizuj `CLAUDE.md`**: sekcja `app.py` (dopisz fix bramki
   `_NO_GATE_TYPES`, data 07.07.2026) oraz status w sekcji dot. wezwań
   przedsądowych — z "PR draft, nie scalony" na stan faktyczny (scalone do
   `etap2` przez cherry-pick, plus fix bramki tej sesji).
4. **Zaktualizuj `memory/project_wezwania_przedsadowe.md`**: sekcja "Status"
   zmienić z "not merged"/"PR #1 DRAFT" na "merged do etap2 (cherry-pick,
   patch-id identyczny z 378a5f0)" + odnotować fix bramki i wynik ręcznej
   weryfikacji z kroku 2.
5. **Commit** wszystkich zmian (app.py, regression_test.py,
   regression_expected.json, CLAUDE.md, memory/project_wezwania_przedsadowe.md)
   jedną, opisową wiadomością (fix bramki + zamknięcie wątku dokumentacyjnego).
6. **Zamknij PR #1 na GitHubie** (`gh pr close 1 --comment "..."`) z
   komentarzem wskazującym, że zmiana trafiła do `etap2` przez cherry-pick
   (commit `f6d673f`), więc GitHub nie wykrył tego automatycznie — **to jest
   akcja widoczna publicznie, potwierdzę z Tobą bezpośrednio przed
   wykonaniem, niezależnie od zatwierdzenia tego planu**.
7. Push do `etap2` (`git push origin etap2`) — również potwierdzę przed
   wykonaniem jako krok z widocznym efektem na zdalnym repo.

## Pliki krytyczne
- `app/app.py` (~linia 583-590, `_NO_GATE_TYPES`)
- `tools/regression_test.py`, `tools/regression_expected.json`
- `CLAUDE.md`
- `memory/project_wezwania_przedsadowe.md`

## Weryfikacja końcowa
- `python tools/regression_test.py` — brak nowych FAIL.
- `git status` — working tree czyste po commicie.
- `gh pr view 1` — status `CLOSED` z komentarzem odsyłającym do `f6d673f`.
- `CLAUDE.md` i `memory/project_wezwania_przedsadowe.md` opisują stan
  zgodny z rzeczywistością (scalone, fix bramki gotowy).

## Wynik realizacji (07.07.2026)

Plan zrealizowany w całości tej samej sesji:
- Regresja: 3/3 PASS (13 plików SKIP — brak lokalnie na tym komputerze).
- Ręczna weryfikacja w przeglądarce: niedostępna w tym środowisku (brak
  `chromium-cli`, Playwright bez pobranej binarki Chromium) — zastąpiona
  przeglądem kodu (`app.py:590-645`, potwierdzone że `_person_doc` oraz
  K1 pre-select działają zgodnie z oczekiwaniem).
- CLAUDE.md i memory/project_wezwania_przedsadowe.md zaktualizowane.
- Commit `3e6cb7f` na `etap2`, wypchnięty do `origin/etap2`.
- PR #1 zamknięty na GitHubie z komentarzem odsyłającym do `f6d673f`.
