---
name: session-2026-07-15-progress-indicator-and-regression-policy
description: "15.07.2026, session tail — finished the st.spinner→st.status progress indicator (part 2 of the why-we-ask plan), caught+fixed a real nested-expander bug via live browser test, then recorded a feedback memory on when to run full regression and who should run it. All work committed and pushed to etap2."
metadata:
  type: project
  originSessionId: 8db6b830-cf5f-4a60-818d-efade10a7858
---

## What happened, in order

This was the continuation/close of the 15.07.2026 session (4th distinct
piece of work that day, after the "Dlaczego pytamy?" expanders and the
`wyrok_egzekucja` bundle fixes — see [[project_why_we_ask_expanders]] and
[[project_wyrok_zaoczny]]).

1. **Picked up mid-implementation**: found uncommitted changes in
   `app/app.py`, `app/doc_ocr.py`, `app/doc_processor.py` implementing part
   2 of `plany/zapoznaj-si-z-dokumentami-nested-cray.md` — replacing the
   static `st.spinner` during document analysis with a live-progress
   `st.status` widget, via an optional `on_progress` callback threaded
   through the OCR cascade and the per-document processing loop.

2. **Verified before trusting the plan**: read the actual installed
   Streamlit 1.45.1 source
   (`mutable_status_container.py`) to confirm `st.status()`/`.update()`
   signatures matched what the plan assumed. They did.

3. **Live browser test caught a real bug the diff review missed**: using
   `agent-browser`, uploaded a real 18-page scanned bailiff bundle
   (`egzekucja+zaj._rach.+wyk._majatku.pdf`) and triggered analysis.
   Streamlit raised `StreamlitAPIException: Expanders may not be nested
   inside other expanders` — `st.status` is internally an expander-type
   container, and the code had it nested inside the pre-existing
   `st.expander("📎 Wgraj dokumenty...")`. Fixed by moving the whole
   processing block (including `st.status`) to render *after* the
   `with st.expander(...):` block closes, keeping only the file uploader
   and "Analizuj dokumenty" button inside it. Re-tested live — confirmed
   ticking progress messages (Azure poll seconds, per-page OCR, per-doc
   analysis) and correct completion. Full details in
   [[project_progress_indicator]].

4. **Ran regression**: `tools/regression_test.py` — 2 PASS, 0 FAIL (test
   folder `C:\Users\User\Desktop\testy` was down to only 2 real PDFs again,
   the same recurring never-explained emptying issue from prior sessions).

5. **Updated CLAUDE.md** (doc_ocr.py/doc_processor.py/app.py sections) and
   committed+pushed (`ace90b6`).

6. **User asked a clarifying/pushback question**: "why do you keep wanting
   to run regression on all files, explain this to me" — prompted by
   having run the full suite reflexively even though this particular
   change was purely additive (`on_progress=None` default, every call site
   a no-op without it). Answered honestly: full-suite regression matters
   most for *logic* changes (this project has extensive history of "fix
   for file X broke file Y" because so much is shared across document
   types), less so for a wrapper-only change — and importantly, the actual
   bug found this session (nested expanders) would NOT have been caught by
   `regression_test.py` anyway, since that script calls `process_files()`
   directly and never renders `app.py`'s UI. Live browser testing is the
   only thing that catches Streamlit-container-structure bugs.

7. **User asked**: should this recurring regression running be delegated
   to the `record-manager` subagent? Confirmed yes —
   `.claude/agents/record-manager.md` already has `Bash` in its tool list
   and its whole procedure (KROK 0–5 + P1–P17 pitfalls checklist) is built
   for exactly this "audit after doc_*.py/app.py changes" use case.

8. **Saved as feedback memory** ([[feedback_regression_scope]]): run full
   regression without asking only for logic changes (regex/threshold/
   branch/priority); for purely additive/mechanical changes, ask first or
   skip; delegate regression/pipeline-audit runs to `record-manager` rather
   than running `tools/regression_test.py` directly in the main loop going
   forward.

## Commits this session tail

- `ace90b6` — Zamień statyczny spinner na st.status z realnym postępem OCR/AI
- `d713655` — Zapisz preferencję: pełna regresja tylko dla zmian logiki, nie wrapperów

Both pushed to `origin/etap2`. Working tree clean at end of session.

## State to pick up next time

- Progress-indicator feature is complete and live-verified, but only
  spot-checked against 2 real test files (the rest of the ~29-file known
  test set were missing from `C:\Users\User\Desktop\testy` again this
  session — recurring issue, never root-caused, see notes in
  [[project_progress_indicator]] and CLAUDE.md's Test documents section).
  Worth a full `record-manager`-driven regression pass once the folder is
  repopulated, specifically checking that the `on_progress`/`st.status`
  change didn't affect any of the previously-fixed edge cases (it
  shouldn't, being purely additive, but per the newly-recorded policy this
  is exactly the kind of change where a lower-cost spot-check was
  appropriate rather than a blanket full run).
- Local Streamlit dev server (started from `app/` directory this session
  so `st.secrets` resolves correctly — running from repo root fails with
  `StreamlitSecretNotFoundError`) was stopped at end of session.
- No open plan, no pending task-list items — this piece of work is closed.
