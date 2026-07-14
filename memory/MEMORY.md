# Memory Index

- [GitHub repo setup](project_github.md) — repo at github.com/pczak333/Kalkulator_ryzyka_app; commit + push after every meaningful change
- [Git workflow feedback](feedback_git_workflow.md) — commit + push after every meaningful change; clear messages; no bundling unrelated changes
- [Etap2 klasyfikator — stan i todo](project_etap2_classifier.md) — PISMO_PROCESOWE_SADOWE, naprawa cache+sad_organ w doc_classifier.py; do weryfikacji jutro 2026-06-26
- [Wezwania przedsądowe — merged 07.07](project_wezwania_przedsadowe.md) — K1 mapping bug pattern + gate redundancy fix; merged to etap2 (PR #1 needs manual close)
- [Wyrok zaoczny — lekka integracja + fix 14.07](project_wyrok_zaoczny.md) — reuse K1/scenariusza dla nowego typu, ale DAJ MU WŁASNY kod K1 (reuse leciał do UI-label); zweryfikowane live
- [Skille i pluginy w repo — 08.07](project_skills_setup.md) — 6 skilli commitowanych w .agents/.claude/skills (m.in. developing-with-streamlit, regex-vs-llm, agent-browser); pułapki: skills-lock nie czyści się sam, plugin uninstall wymaga --scope project, agent-browser wymaga globalnego CLI per komputer
- [Out-of-scope doc detection — 14.07](project_out_of_scope_detection.md) — użyj już wyciągniętych pól (sad_organ, powod) jako strukturalnego sygnału klasyfikacji, nie tylko keyword score; zweryfikowane live; formularz K1-K7 dalej renderował się aktywnie mimo banera — fix w toku
- [Komornik boilerplate deadlines — 14.07](project_komornik_boilerplate_deadlines.md) — termin ze skargi na czynność komornika (art. 767 KPC, ~7 dni, w niemal każdym piśmie) mylony z realnym terminem reakcji; diagnoza gotowa, fix w toku
