---
name: feedback-claude-md-conciseness
description: "CLAUDE.md musi opisywać biezacy stan zwiezle; pelna historia (daty, zrzuty ekranu, przebiegi weryfikacji) nalezy do memory/*.md, nie do CLAUDE.md."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 843a77a7-45c6-440a-8cbb-09ba5fcc56e9
  modified: 2026-07-22T12:40:43.224Z
---

Gdy dokumentujesz zmianę w CLAUDE.md (sekcja "Application structure" per moduł,
"Test documents" per plik), pisz 1-3 zdania opisujące **bieżące zachowanie** —
nie chronologiczną narrację "(DD.MM.RRRR) zgłoszenie użytkownika, zrzut ekranu
obrazX, zweryfikowano Y/Y razy...". Pełną historię/uzasadnienie zapisuj w
osobnym pliku `memory/*.md` (per temat, patrz [[MEMORY.md]] index) i odsyłaj
do niego z CLAUDE.md jednym zdaniem ("patrz memory/project_X.md").

**Why:** 22.07.2026 plik CLAUDE.md urósł do 164 847 znaków (limit narzędzia:
150 000) — niemal cała objętość (72%, 20 linii) to pojedyncze bardzo długie
akapity per moduł/plik testowy, każdy dopisujący kolejny wpis "(data,
zgłoszenie, naprawa, weryfikacja)" bez usuwania starszych. Poproszony o
skrócenie do limitu, skompresowano plik do 41 141 znaków usuwając wyłącznie tę
narrację (nie żadną unikalną wiedzę biznesową) — cała treść historyczna była
już równolegle zapisana per-temat w `memory/*.md` z poprzednich sesji, więc
kompresja nie utraciła informacji, tylko usunęła duplikację.

**How to apply:** Zanim dopiszesz kolejny akapit "(DD.MM.RRRR, TEMAT) ..." do
opisu modułu w CLAUDE.md — zapytaj się, czy to fakt o BIEŻĄCYM zachowaniu (np.
"guard X wymaga Y, bo inaczej Z" — zostaje, zwięźle) czy o PRZEBIEGU pracy nad
tym ("zgłoszenie użytkownika, zrzut ekranu, ile razy zweryfikowano" — to
memory/, nie CLAUDE.md). Jeśli dany temat nie ma jeszcze pliku w memory/,
utwórz go zamiast wydłużać CLAUDE.md. Ta sama zasada jest teraz też zapisana
wprost w CLAUDE.md (sekcja "Zasady pracy" → "Synchronizacja dokumentacji").
Zobacz [[project_claude_md_compression]] po szczegóły samej kompresji z
22.07.2026.
