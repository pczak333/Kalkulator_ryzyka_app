---
name: project-claude-md-compression
description: "CLAUDE.md skrocony 22.07.2026 ze 164 847 do 41 141 znakow (limit 150 000); co zostalo, co usuniete, gdzie szukac pelnej historii."
metadata: 
  node_type: memory
  type: project
  originSessionId: 843a77a7-45c6-440a-8cbb-09ba5fcc56e9
  modified: 2026-07-22T12:41:04.089Z
---

22.07.2026 użytkownik poprosił o skrócenie `CLAUDE.md` do limitu 150 000
znaków (plik miał 164 847). Wykonana kompresja: 164 847 → 41 141 znaków —
commit `89a9d0b` na `main`, wypchnięty na `origin`.

## Co zostało zrobione

Zidentyfikowano, że 72% objętości pliku (20 linii z ~330) to pojedyncze,
bardzo długie akapity — opis `app.py` w drzewie katalogów (27 041 znaków w
jednej linii), opisy modułów `doc_*.py`/`ai_extractor.py` (~59 000 znaków
łącznie) i sekcja "Test documents" (~36 000 znaków) — każdy zbudowany z
kolejno dopisywanych wpisów "(DD.MM.RRRR, TEMAT) zgłoszenie użytkownika,
diagnoza, naprawa, weryfikacja...".

Każdy taki blok przepisano na 1-6 zdań opisujących **bieżące zachowanie**
(aktywne guardy, kolejność reguł, kluczowe niezmienniki), z odesłaniem do
właściwego pliku `memory/*.md`, gdy pełna historia/uzasadnienie już tam
istniała (a istniała dla niemal wszystkiego — poprzednie sesje już prowadziły
memory/ per-temat równolegle do CLAUDE.md). Struktura pliku (wszystkie
nagłówki `##`/`###`, kolejność sekcji, tabele danych) bez zmian — usunięta
została wyłącznie narracja, nie unikalna wiedza.

## Gdzie szukać, czego w CLAUDE.md już nie ma

Pełna chronologiczna historia napraw (kto zgłosił, jaki zrzut ekranu, ile
razy zweryfikowano, jakie było pierwsze błędne podejście) dla poszczególnych
tematów jest w:
- [[project_visual_redesign]] — redesign wizualny (Fazy A-D), raport PDF/HTML
- [[project_komornik_boilerplate_deadlines]] / [[project_wyrok_zaoczny]] —
  najbardziej złożone sesje debugowania `doc_splitter.py`
- [[project_unrelated_docs_warning]] — ostrzeżenie o różnych sprawach w paczce
- [[project_out_of_scope_detection]] — dokumenty niesądowe/poza zakresem
- [[project_wps_amount_labeling]] — etykieta rodzaju kwoty + WPS
- [[project_ai_key_silent_fallback]] — cichy fallback AI→regex
- [[project_form_content_audit]] — audyt treści formularza K1-K7
- [[project_progress_indicator]] — wskaźnik postępu OCR
- [[project_deployment_cwd_bug]] — bug ścieżki cwd na Streamlit Cloud
- `tools/regression_expected.json` — surowe wartości oczekiwane per plik
  testowy (CLAUDE.md teraz opisuje tylko PO CO dany plik istnieje, nie
  szczegóły każdej weryfikacji)

## Zasada na przyszłość

Zapisana jako osobna pamięć: [[feedback_claude_md_conciseness]] — nowe zmiany
dokumentować w CLAUDE.md zwięźle (bieżący stan), pełną narrację od razu do
memory/*.md, żeby plik nie urósł ponownie do limitu.
