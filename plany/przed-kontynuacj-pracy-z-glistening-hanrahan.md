# Plan: workflow ciągłości planów (repo) + wdrożenie PR #1 (przedsądowe wezwania)

## Context

Użytkownik pracuje na trzech komputerach. Pliki planów trybu planowania Claude
Code zapisują się lokalnie (`C:\Users\User\.claude\plans\...` / na innym
komputerze `C:\Users\Piotr Czak\.claude\plans\...`) — przy zmianie komputera
plan i kontekst pracy się gubiły. Użytkownik ręcznie skopiował dotychczasowe
pliki planów z dwóch komputerów do nowego folderu `plany/` w repozytorium i
poprosił, aby **od teraz każdy finalny plan był też zapisywany w repo**, żeby
kontynuacja pracy nie zależała od tego, na którym komputerze się pracuje.

Drugi wątek: ostatni plan (`plany/sprawd-claude-me-i-memory-wondrous-cocoa.md`)
opisuje dokończenie sesji z 06.07.2026 — naprawę obsługi przedsądowych wezwań
do zapłaty. Fix jest gotowy i zweryfikowany (regresja + symulacja pipeline'u),
siedzi na gałęzi `worktree-jest-problem-z-w-a-ciw-stateless-teapot` jako
**PR #1 (DRAFT, niescalony)**, plus jedna dodatkowa poprawka (bramka art. 299)
nigdy nie trafiła do PR. Użytkownik poprosił o sprawdzenie tego planu przed
kontynuacją — zweryfikowałem go w trybie read-only i jest w pełni aktualny.

## Część A — weryfikacja stanu (już wykonana, wynik pozytywny)

Sprawdzone w trybie read-only, bez żadnych zmian w repo:
- Commit `378a5f0` istnieje na gałęzi `worktree-jest-problem-z-w-a-ciw-stateless-teapot`, zawiera dokładnie opisane w planie zmiany (app.py, doc_processor.py, scenario_selector.py, CSV 08/09/12, Excel, regression_expected.json).
- PR #1 (`gh pr list`) faktycznie istnieje, status **DRAFT**, base = `etap2` — niescalony.
- Commit `378a5f0` **nie jest** jeszcze w historii `etap2` (potwierdzone `git log etap2`).
- Gałąź `etap2` odjechała od `worktree-...` (dalsze commity: paczka komornicza, pismo przygotowawcze) — sprawdziłem **dry-run cherry-pick** (`--no-commit -n`), **zero konfliktów**, następnie w pełni cofnąłem próbne zmiany (`git reset` + `git checkout --`) tak, że working tree wrócił do stanu sprzed testu.
- Bieżący `app/app.py:545-546` nadal ma stary warunek bramki (`_person_doc` bez `_NO_GATE_TYPES`) — poprawka opisana w planie jest nadal potrzebna i nieaplikowana.
- Pamięć projektu (`project_wezwania_przedsadowe.md`) potwierdza tę samą historię i status "not merged", "not manually verified in browser".
- Przy okazji zauważyłem konkretny przykład problemu wielokomputerowego: `tools/regression_test.py` ma niezacommitowaną zmianę `DEFAULT_TEST_DIR` (`C:\Users\User\Desktop\testy` → `C:\Users\Piotr Czak\Desktop\testy`) — inny komputer, inna ścieżka domowa.

**Wniosek: plan w `sprawd-claude-me-i-memory-wondrous-cocoa.md` jest aktualny i można go realizować bez zmian.**

## Część B — implementacja

### B0. Odkrycie w trakcie sesji: ten sam problem dotyczy pamięci (memory)
Użytkownik skopiował do repo (poza `plany/`) surowy folder
`C:\Users\User\.claude\projects\C--Users-User-Desktop-Kalkulator-ryzyka-app\`
jako `./projects/` (32 MB, nieśledzony przez git). Sprawdziłem zawartość:
- To głównie surowe logi całych rozmów (pliki `.jsonl`, transkrypty
  podagentów) — **nie nadają się do repozytorium** (rozmiar, potencjalnie
  wrażliwa treść, brak wartości jako "pamięć" w ustrukturyzowanym sensie).
- W środku jest jednak podfolder `memory/` z 5 plikami `.md`
  (`MEMORY.md`, `feedback_git_workflow.md`, `project_etap2_classifier.md`,
  `project_github.md`, `project_wezwania_przedsadowe.md`) — to właściwa,
  ustrukturyzowana pamięć projektowa. Porównałem każdy z 5 plików z lokalną
  pamięcią na tym komputerze — **wszystkie identyczne** (folder pochodzi z
  TEGO SAMEGO komputera, nie z trzeciego — do trzeciego użytkownik nie ma
  teraz dostępu, więc jego pamięć zostaje do zsynchronizowania później, gdy
  będzie dostępny).

Decyzja użytkownika: (1) surowy `./projects/` — usunąć z repo, zostawić tylko
wyciągnięte pliki `.md`; (2) nowy folder w repo na pamięć: **`memory/`**
(nazwa PO ANGIELSKU, celowo — dokładnie zgodna z nazwą lokalnego folderu
`~/.claude/projects/.../memory/`, żeby synchronizacja nie wymagała
tłumaczenia nazw w każdej instrukcji/skrypcie i nie było ryzyka pomyłki,
do którego folderu coś wgrać. `plany/` zostaje po polsku — to inny
przypadek, bez stałej nazwy 1:1 po stronie lokalnej).

### B1. Proces: plany i pamięć zawsze też w repo (na przyszłość)
Dopisz do `CLAUDE.md`, sekcja "Zasady pracy Claude Code w tym projekcie", nową
podsekcję (np. "Ciągłość pracy między komputerami"):
- Po zaakceptowaniu planu (koniec trybu plan mode) **skopiuj finalną treść
  planu do `plany/<opisowa-nazwa>.md`** w repo i zacommituj razem z resztą
  zmian tej sesji (albo od razu, jeśli implementacja jeszcze się nie zaczyna).
- Po każdej aktualizacji pamięci projektu (nowy/zmieniony plik w
  `~/.claude/projects/.../memory/`) **skopiuj ten plik też do `memory/`** w
  repo i zacommituj. `memory/MEMORY.md` w repo ma być zawsze aktualną kopią
  lokalnego indeksu pamięci.
- Na początku każdej sesji, jeśli lokalna pamięć (`~/.claude/projects/.../memory/`)
  różni się od tego, co jest w `memory/` w repo (np. bo sesja toczyła się na
  innym komputerze) — **synchronizuj z repo do lokalnego magazynu pamięci**
  (repo jest źródłem prawdy dla ciągłości między komputerami; nowsza treść
  w repo wygrywa).
- Lokalne pliki trybu planowania/pamięci (`~/.claude/plans/...`,
  `~/.claude/projects/.../memory/`) zostają jak są — to mechanizm harnessu,
  nie da się go przekierować — ale **kopie w repo (`plany/`, `memory/`) są
  źródłem prawdy dla kontynuacji między komputerami**.
- Na początku każdej sesji, jeśli użytkownik odwołuje się do "ostatniego
  planu"/kontynuacji, sprawdź najpierw `plany/` i `memory/` w repo
  (posortowane po dacie modyfikacji), nie tylko lokalne katalogi.

### B1a. Sprzątanie tej sesji
1. Skopiuj 5 plików z `./projects/C--Users-User-Desktop-Kalkulator-ryzyka-app/memory/`
   do nowego `memory/` w repo (zawartość już zweryfikowana jako identyczna z
   lokalną pamięcią — to tylko przeniesienie, bez zmian treści).
2. Usuń folder `./projects/` z katalogu repo (pozostaje tylko lokalnie w
   `~/.claude/projects/...`, poza gitem — to normalne miejsce przechowywania
   harnessu, nie trzeba go duplikować).
3. Dodaj `memory/` do struktury opisanej w CLAUDE.md (analogicznie do `plany/`).

### B2. Napraw hardkodowaną ścieżkę per-komputer w `tools/regression_test.py`
Zamiast twardego `DEFAULT_TEST_DIR`, odczytuj z zmiennej środowiskowej z
fallbackiem, np.:
```python
DEFAULT_TEST_DIR = Path(os.environ.get("KRS_GUARD_TESTY_DIR", r"C:\Users\User\Desktop\testy"))
```
To usuwa źródło konfliktów przy przełączaniu komputerów (obecna niezacommitowana
zmiana w working tree to właśnie to zderzenie). Odrzuć/zastąp obecną
niezacommitowaną edycję tą wersją.

### B3. Cherry-pick commit 378a5f0 do `etap2`
```
git cherry-pick 378a5f0
```
(Bez `469363b` — to tylko notka CLAUDE.md o "PR draft", zastąpimy ją nową
dokumentacją w B5.) Dry-run już potwierdził brak konfliktów.

### B4. Fix bramki art. 299 w `app/app.py` (NIE był w PR)
W okolicy linii 545-546, rozszerz warunek:
```python
_NO_GATE_TYPES = {"WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU"}

_person_doc = (prefill.doc_type_code.endswith("_CZLONEK_ZARZADU")
               and not _pozwany_is_company
               and prefill.doc_type_code not in _NO_GATE_TYPES)
```
Uzasadnienie: ten typ dokumentu już koduje art. 299 w samej nazwie/klasyfikacji
— pytanie bramki byłoby redundantne wobec tego, co dokument już potwierdza.

### B5. Testy
1. `python tools/regression_test.py --only "przed._wez_do_zap..pdf"` — Typ 1
   (InterRisk, spółka) — musi dalej dawać `WEZWANIE_PRZEDSADOWE_SPOLKA` +
   baner ostrzeżenia, bez regresji.
2. Pełna regresja (`python tools/regression_test.py`) — 0 nowych FAIL.
3. Ręczny test w żywej aplikacji (`streamlit run app/app.py`) na pliku Typu 2
   (wezwanie art. 299, członek zarządu) — sprawdź: brak bramki, K1
   pre-selected = "Wezwanie przedsądowe (członek zarządu)", scenariusz
   BASE_21x zamiast "rodzaj pisma nieustalony".

### B6. Dokumentacja i commit
- Zaktualizuj `CLAUDE.md`: sekcja doc_processor.py/app.py (mapowanie K1,
  fix bramki), sekcja "Test documents" (dopisz plik(i) Typu 2 jeśli jeszcze
  nie są opisane), status PR #1 → scalony.
- Zaktualizuj memory `project_wezwania_przedsadowe.md` (status: merged,
  manual verification done).
- Commit + push do `etap2`.
- Zamknij PR #1 na GitHubie (`gh pr close 1 --comment "..."`) z komentarzem
  wskazującym commit w `etap2`, do którego trafiła ta poprawka (cherry-pick,
  nie merge — stąd PR trzeba zamknąć ręcznie, GitHub sam tego nie wykryje).

## Weryfikacja końcowa
- `git log etap2` zawiera cherry-pickowany commit.
- `app/app.py` ma `_NO_GATE_TYPES`.
- Regresja: brak nowych FAIL względem stanu przed zmianą.
- Żywa aplikacja: oba typy wezwań (spółka / członek zarządu) zachowują się
  zgodnie z opisem w B5.3.
- `plany/` zawiera ten plan jako plik (kopiowany po zakończeniu sesji zgodnie
  z B1).
- `memory/` istnieje w repo z 5 plikami pamięci, zsynchronizowane z lokalną
  pamięcią; `./projects/` (surowe logi) usunięte z katalogu repo.

## Pliki krytyczne
- `app/app.py` — cherry-pick + fix bramki (~linie 545-590)
- `app/doc_processor.py`, `app/scenario_selector.py` — cherry-pick (mapowania K1)
- `dane_wejściowe/csv/08_...csv`, `09_...csv`, `12_...csv`, Excel — cherry-pick
- `tools/regression_test.py` — env var fix dla `DEFAULT_TEST_DIR`
- `CLAUDE.md` — nowa podsekcja o ciągłości planów i pamięci + aktualizacja stanu wezwań
- `memory/` (nowy folder) — kopia plików pamięci projektu z `~/.claude/projects/.../memory/`
- `./projects/` — do usunięcia z katalogu repo (pozostaje tylko lokalnie, poza gitem)
