# Konwersja Record Manager ze Skilla na właściwego subagenta

## Kontekst

`Record Manager` miał być subagentem KRS Guard (wewnętrzny audytor: weryfikuje wybór
dokumentu głównego, segmentację, jakość OCR, spójność formularza K1–K7 i rekomendacji
z panelem technicznym), ale został zapisany w niewłaściwym miejscu i formacie —
`.agents/skills/Record_Manager/SKILL.md`, z frontmatterem stylu Skill (`name`/`description`
bez `tools`). To nie jest ani poprawna ścieżka na skill (`.claude/skills/...`), ani
poprawna ścieżka na subagenta (`.claude/agents/...`), więc plik nie pojawia się na
liście dostępnych skilli ani subagentów.

Subagenty projektowe Claude Code definiuje się jako pliki `.claude/agents/*.md`
z frontmatterem: wymagane `name` + `description` (opis decyduje, kiedy Claude
sam deleguje zadanie do agenta — warto użyć frazy "Use proactively..."), opcjonalnie
`tools` (allowlist; brak = dziedziczy wszystkie), `model` (domyślnie `inherit`).
Treść po frontmatterze staje się dosłownie promptem systemowym subagenta.

Potwierdzone z użytkownikiem:
- Record Manager ma mieć pełny dostęp narzędziowy (Read, Grep, Glob, Edit, Bash) —
  zgodnie z oryginalnym zamysłem "od razu naprawia (lub precyzyjnie wskazuje co i jak
  poprawić)".
- Stary, źle umieszczony plik `.agents/skills/Record_Manager/SKILL.md` zostaje usunięty
  po przeniesieniu treści (plik nie jest jeszcze śledzony przez git — `.agents/` widnieje
  jako `??` w `git status` — więc usunięcie jest bezpieczne, nic nie ginie).

## Zakres zmian

1. **Utworzyć `.claude/agents/record-manager.md`** z frontmatterem:
   ```yaml
   ---
   name: record-manager
   description: >
     Wewnętrzny audytor aplikacji KRS Guard — weryfikuje poprawność wyboru dokumentu
     głównego, segmentację paczki dokumentów, jakość odczytu OCR, spójność formularza
     K1–K7 oraz korelację rekomendacji z panelem technicznym. Use proactively after
     changes to doc_splitter.py, doc_classifier.py, doc_extractor.py, doc_selector.py,
     doc_processor.py, ai_extractor.py, or app.py's document-handling/UI logic, and
     after processing new test documents — to catch regressions against the known
     pitfalls list (P1–P17) before they reach the client.
   tools: Read, Grep, Glob, Edit, Bash
   ---
   ```
   Treść po frontmatterze = obecna zawartość SKILL.md (sekcje 1–7: Rola i zakres,
   Procedura krok po kroku KROK 0–5, Znane pułapki P1–P17, Schemat decyzyjny,
   Komunikacja wyników, Mapa plików, Ograniczenia) przeniesiona bez merytorycznych
   zmian — treść jest już napisana jako dobry prompt systemowy (3-osobowy opis roli,
   konkretne checklisty, format raportowania). Jedyna zmiana: usunięcie zduplikowanego
   bloku frontmatter na górze pliku (obecny `name:`/`description:` Skill-owy), bo te
   pola przenoszą się do nowego YAML frontmatter.

2. **Usunąć** `.agents/skills/Record_Manager/SKILL.md` (i pusty katalog
   `.agents/skills/Record_Manager/`, oraz `.agents/skills/` jeśli po usunięciu
   pozostanie pusty) — treść w całości przeniesiona do kroku 1, nic nie ginie.

3. **Zgodnie z zasadą projektu "ciągłość pracy między komputerami"** (CLAUDE.md) —
   po zaakceptowaniu tego planu skopiować jego finalną treść do `plany/` w repo,
   żeby był dostępny na innych komputerach użytkownika.

## Weryfikacja

- `ls .claude/agents/` pokazuje `record-manager.md`.
- Uruchomić `claude` i sprawdzić, że `record-manager` pojawia się jako dostępny typ
  agenta (np. przez wywołanie Agent tool z `subagent_type: record-manager` na prostym
  pytaniu diagnostycznym, np. "sprawdź czy panel techniczny dla pliku wyrok.pdf pokazuje
  main=WYROK_ZAOCZNY_SPOLKA" — nie wymaga to uruchamiania aplikacji, tylko potwierdza,
  że agent się poprawnie ładuje i ma dostęp do Read/Grep/Glob/Edit/Bash).
- Potwierdzić, że stary plik `.agents/skills/Record_Manager/SKILL.md` już nie istnieje.

## Status

Wykonano 2026-07-08: utworzono `.claude/agents/record-manager.md`, usunięto
`.agents/skills/Record_Manager/SKILL.md` (i puste katalogi nadrzędne). Weryfikacja
w toku (patrz sekcja Weryfikacja) w tej samej sesji.
