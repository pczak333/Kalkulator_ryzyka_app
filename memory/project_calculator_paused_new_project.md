---
name: project-calculator-paused-new-project
description: "22.07.2026 — użytkownik zamknął aktywną pracę nad Kalkulatorem Ryzyka (uznany za gotowy/stabilny) i przechodzi do nowego, osobnego projektu: strony internetowej, której częścią ma być ten kalkulator."
metadata: 
  node_type: memory
  type: project
  originSessionId: 81133bfc-4d56-4983-9b14-4f3f334bc3cb
  modified: 2026-07-22T14:57:40.619Z
---

Praca nad KRS Guard – Kalkulator Ryzyka Prawnego została zamknięta 22.07.2026
na życzenie użytkownika ("zamykamy pracę nad kalkulatorem ryzyka i przechodzimy
do nowego projektu"). Repo zostaje w stanie stabilnym: `main` clean, w pełni
zsynchronizowany z `origin/main` (patrz [[session_2026-07-22_summary]] dla
pełnego stanu na koniec ostatniej sesji — nowy znak graficzny, audyt formularza,
naprawiony krytyczny bug cwd na Streamlit Cloud, CLAUDE.md skompresowany).

**Why:** użytkownik przechodzi do nowego, osobnego projektu — strony
internetowej, której częścią ma być ten kalkulator. Temat był już
zasygnalizowany pod koniec poprzedniej sesji jako "wątek otwarty, ale
niezaczęty" — teraz jest to aktywny kierunek, nie tylko koncepcja.

**How to apply:** Jeśli przyszła sesja w TYM repo (Kalkulator_ryzyka_app)
zaczyna się od razu od nowych zadań — nie zakładaj kontynuacji rozwoju
kalkulatora jako priorytetu, tylko dopytaj, czy to konserwacja/bugfix istniejącej
appki, czy praca ma się przenieść do nowego, osobnego repo/projektu strony.
Rekomendacja doradcza z poprzedniej sesji (niewdrożona, czysto koncepcyjna):
nie kopiować kodu Streamlit do `dane_wejściowe` nowego projektu — albo (a)
osadzić istniejącą appkę przez iframe/link, albo (b) skopiować tylko
`dane_wejściowe/` (Excel+CSV reguł) jako input do nowego projektu i napisać
nową warstwę UI w stacku nowej strony.
