---
name: project-wezwania-przedsadowe
description: Two-tier fix (06.07.2026, merged 07.07.2026) for pre-court demand letters (wezwanie przedsądowe) — company-only vs art.299 member liability, plus gate redundancy fix
metadata: 
  node_type: memory
  type: project
  originSessionId: 145f6aeb-2d25-46d7-8efa-6afca27963da
---

## Status as of 07.07.2026

**Merged to `etap2`**: the fix from PR #1 (commit `378a5f0` on branch
`worktree-jest-problem-z-w-a-ciw-stateless-teapot`) landed on `etap2` as
commit `f6d673f` — confirmed via `git patch-id` that both commits produce
the byte-identical patch. It was applied as a fresh commit (not a literal
`git cherry-pick`), so GitHub did not auto-detect the merge; PR #1 needs to
be closed manually with a comment pointing at `f6d673f`.

**Second fix same area (07.07.2026)**: even with K1 correctly wired, the
app still asked the art. 299 gate question ("czy sprawa dotyczy
odpowiedzialności członka zarządu?") for `WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU`
— redundant, since that doc type already encodes art. 299 in its own
classification. Fixed with `_NO_GATE_TYPES = {"WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU"}`
in `app/app.py` (`_person_doc` condition), mirrored in
`tools/regression_test.py::_gate_should_fire()`, `regression_expected.json`
updated (`gate: false` for `299_przeds._wezw._do_zap..pdf`).

**Verified:** `tools/regression_test.py` (3/3 PASS on files present locally,
including the gate fix), a full backend pipeline simulation (scoring →
hard_rules → scenario_selector → text_builder) for both letter types, that
no scenario rows collide after removing BASE_138-140, and a code-level
review of the gate condition + K1 prefill wiring (`app.py:590-645`).

**Still not done:** manual click-through in a live `streamlit run app/app.py`
session with a real browser — no browser automation available in this
session's environment either (no `chromium-cli`, Playwright installed but
its Chromium binary isn't downloaded). If a discrepancy ever shows up in
practice despite the code review, check this first.

## Recurring bug pattern: doc type classified correctly, K1 mapping missing

Discovered again on 06.07.2026 for `WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU`: the
classifier correctly identified the document (confidence 0.52, shown in the
technical panel), but `_DOC_TYPE_TO_K1` (doc_processor.py) had no entry for
it, so it silently fell back to `K1_INNE_NIE_WIEM` and the risk text claimed
"rodzaj pisma nie został jednoznacznie ustalony" — contradicting the panel.

**Why this keeps happening:** adding a new doc type to CSV 07 (classifier)
does NOT automatically wire it into the K1 form → scoring → scenario chain.
That requires four separate additions: CSV 08 (K1 answer code), CSV 09
(scoring row), CSV 12 (scenario rows per K2×risk combo), and two Python dict
entries (`_DOC_TYPE_TO_K1` in doc_processor.py, `_K1_TO_DOC_TYPE` in
scenario_selector.py). The exact same bug was fixed for komornik letters on
05.07.2026 — see [[project_etap2_classifier]].

**How to apply:** when a user reports "the risk text doesn't match what the
technical panel says," check `_DOC_TYPE_TO_K1` first — it's the most common
break point.

## Business decision: two pre-court demand letter types get different treatment

User distinguished two subtypes of "wezwanie przedsądowe" during this fix:

1. **Type 1 — `WEZWANIE_PRZEDSADOWE_SPOLKA`** (plain company invoice, no
   art. 299 mention): user decided the calculator should NOT push this into
   full K1-K7 risk scoring at all — reusing the existing
   `DOKUMENT_NIEPRAWNY`-style soft-warning mechanism (hide table, zero
   fields, form stays reachable manually) but with different wording, since
   unlike a bank transfer this IS a real legal letter, just out of scope for
   personal member-liability risk. New set `_SPOLKA_OUT_OF_SCOPE_TYPES` in
   app.py. No K1/CSV09/CSV12 entries were built for this type — intentional.
2. **Type 2 — `WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU`** (cites art. 299 KSH
   + failed enforcement against the company, addressed to a natural
   person): got the full K1 treatment, weight C=2 (same tier as "Wezwanie
   sądowe (członek zarządu)" — serious, directly targeting the individual,
   but not yet a court document).

**Why:** the user wants the app to feel professional — full risk-scoring
output ("sprawa pilna, wysokie ryzyko") for a routine unpaid invoice to the
company would look wrong/unprofessional. Confirmed via AskUserQuestion; the
recommended options were accepted each time.

**How to apply:** if a new doc type is company-only and doesn't establish
personal member risk, default to the Type-1 pattern (warning only, no K1
buildout) rather than assuming every doc type needs full scoring support.

## Gotcha: `find_scenario()` matches by doc type, not by K1 code

`scenario_selector.find_scenario()` matches CSV 12 rows purely on
`main_document_type_code` + `K2_answer_code` + `risk_level_code` (+
`epu_flag`) — it never looks at the `K1_answer_code` column. This means
stale/orphaned scenario rows (same doc type, wrong/legacy K1_answer_code)
can silently collide with newly-added rows once a K1 mapping is wired up.
Found 3 such orphans (BASE_138-140) when wiring up Type 2 above — they had
`main_document_type_code=WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU` but
`K1_answer_code=K1_INNE_NIE_WIEM` from an earlier authoring pass, so they
were dead until this fix made them reachable and colliding with new rows.

**How to apply:** when adding new scenario rows for a doc type, always grep
CSV 12 for existing rows with that `main_document_type_code` first — don't
assume "no K1 mapping existed" means "no scenario rows exist."
