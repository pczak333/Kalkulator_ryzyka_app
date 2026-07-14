# Memory Index

- [GitHub repo setup](project_github.md) — repo at github.com/pczak333/Kalkulator_ryzyka_app; commit + push after every meaningful change
- [Git workflow feedback](feedback_git_workflow.md) — commit + push after every meaningful change; clear messages; no bundling unrelated changes
- [Etap2 klasyfikator — stan i todo](project_etap2_classifier.md) — PISMO_PROCESOWE_SADOWE, naprawa cache+sad_organ w doc_classifier.py; do weryfikacji jutro 2026-06-26
- [Wezwania przedsądowe — merged 07.07](project_wezwania_przedsadowe.md) — K1 mapping bug pattern + gate redundancy fix; merged to etap2 (PR #1 needs manual close)
- [Wyrok zaoczny — lekka integracja + fix 14.07](project_wyrok_zaoczny.md) — reuse K1/scenariusza dla nowego typu, ale DAJ MU WŁASNY kod K1 (reuse leciał do UI-label); zweryfikowane live
- [Skille i pluginy w repo — 08.07](project_skills_setup.md) — 6 skilli commitowanych w .agents/.claude/skills (m.in. developing-with-streamlit, regex-vs-llm, agent-browser); pułapki: skills-lock nie czyści się sam, plugin uninstall wymaga --scope project, agent-browser wymaga globalnego CLI per komputer
- [Out-of-scope doc detection — 14.07](project_out_of_scope_detection.md) — użyj już wyciągniętych pól jako sygnału klasyfikacji, nie tylko keyword score; finalnie: AI generuje krótki opis KAŻDEGO nieistotnego dokumentu (opis_dokumentu) do banera zamiast nowego typu/etykiety per dokument — user pushback: generalizuj, nie hardcoduj per przypadek
- [Komornik boilerplate deadlines — 14.07](project_komornik_boilerplate_deadlines.md) — termin ze skargi na czynność komornika (art. 767 KPC, ~7 dni) mylony z realnym terminem; naprawione + 2 dodatkowe błędy odkryte po drodze (list-order matching w _KOMORNIK_TITLES, single-doc pliki nigdy nie przechodziły przez splitter)
- [WPS vs kwota główna — etykieta kwoty — 14.07](project_wps_amount_labeling.md) — NIE pokazuj WPS zamiast należności głównej (WPS to wartość proceduralna, bywa wyższa); zamiast tego podpisz rodzaj kwoty + pokaż WPS jako drugą, opcjonalną pozycję
