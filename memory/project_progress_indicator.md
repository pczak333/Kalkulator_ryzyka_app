---
name: project-progress-indicator
description: "15.07.2026 — replaced the static st.spinner during document analysis with a live-ticking st.status widget (on_progress callback threaded through OCR cascade + doc loop); hit and fixed a real 'expanders may not be nested' bug caught by a live browser test."
metadata: 
  node_type: memory
  type: project
  originSessionId: b843daf9-6aa1-48c6-8080-17f99160f229
---

## What happened

Continuation of the 15.07 session (part 2 of the plan in
`plany/zapoznaj-si-z-dokumentami-nested-cray.md`, after the "Dlaczego pytamy?"
expanders in part 1, see [[project_why_we_ask_expanders]]). User's screenshot
showed `st.spinner("Analizuję dokumenty (OCR + ekstrakcja danych)...")` — one
static sentence with a spinning icon for the *entire* duration of analysis.
For large scanned bundles this can take from tens of seconds to a couple of
minutes (a ~1.5h background hang was even observed once in a prior session,
see [[session_2026-07-15_full_regression]]) — a static spinner gives no
signal whether the app is actually working or has hung.

## Implementation

Added an optional, purely-additive `on_progress: Callable[[str], None] | None
= None` parameter threaded through the whole OCR/processing call chain:

- `doc_ocr.py`: `ocr_with_fallback`, `_ocr_azure`, `_ocr_claude`,
  `_ocr_tesseract`/`_ocr_tesseract_pages`. `_ocr_azure` replaced
  `result = poller.result()` (one opaque blocking call — the single biggest
  suspect for the "hung" impression on large scans) with a manual
  `while not poller.done(): time.sleep(2); ...` loop reporting elapsed
  seconds. `_ocr_claude`/`_ocr_tesseract_pages` report per-page progress
  (they already looped per page).
- `doc_processor.py`: `_process_single_doc`/`process_files` report
  "Analizuję dokument N/M w paczce..." per segment and "Wczytuję plik N/M..."
  per file (only when >1 file).
- `app.py`: `st.spinner(...)` replaced with
  `with st.status(..., expanded=True) as status:` +
  `on_progress=lambda msg: status.write(msg)`, with `status.update(state="error")`
  in the except block before re-raising so the widget doesn't visually stay
  "running" after a failure.

Default `None` everywhere → zero behavior change for existing callers,
notably `tools/regression_test.py` (calls `process_files()` without
`on_progress`).

## Real bug caught by live testing, not by reading the diff

Verified `st.status()`/`.update()` signature directly against the installed
Streamlit 1.45.1 source
(`site-packages/streamlit/elements/lib/mutable_status_container.py`) before
trusting the plan — matched exactly (`label`, `expanded`, `state:
"running"|"complete"|"error"`).

Then ran a **live browser test** (agent-browser) against the actual
Streamlit app — uploaded a real 18-page scanned bailiff bundle
(`egzekucja+zaj._rach.+wyk._majatku.pdf`) and clicked "Analizuj dokumenty".
This surfaced a real, un-caught bug: `st.status` is internally an
expander-type container, and the original code nested
`with st.status(...)` *inside* the pre-existing
`with st.expander("📎 Wgraj dokumenty..."):` block that already wrapped the
whole upload+analyze section. Streamlit raised
`StreamlitAPIException: Expanders may not be nested inside other expanders`
— this would NOT have been caught by reading the diff or by
`tools/regression_test.py` (that suite calls `process_files()` directly,
never renders `app.py`'s UI at all).

**Fix**: restructured so the file uploader and "Analizuj dokumenty" button
stay inside the expander, but the whole processing block (including
`st.status`) moved to render *after* the `with st.expander(...):` block
closes — `_do_analyze` is captured as a plain variable
(`_do_analyze = False` before the `if uploaded_files:` check) so it survives
outside the `with` block.

Re-tested live after the fix: the status widget ticked through real
messages ("OCR: przetwarzam dokument (Azure)... 2s/4s/6s", then "OCR: strona
N/16 (Tesseract)...", then "Analizuję dokument N/7 w paczce...") and
completed correctly into the results view, no error.

## Lesson

**Any Streamlit UI change touching containers (expanders, status, columns,
tabs) needs a live browser test, not just a signature check or
`tools/regression_test.py`** — that suite only exercises the
processing/classification pipeline, never the actual page render, so
container-nesting errors are invisible to it. `developing-with-streamlit`
skill (checking installed-version API) confirms *signatures* are right; it
doesn't catch *structural* incompatibilities like this one. See also
[[project_why_we_ask_expanders]] for the companion lesson about checking
`inspect.signature()` before assuming a widget needs a `key=` param — same
theme of "verify against the actual installed library, don't assume."

## Status at end of session

Code change complete and live-verified in `app/app.py`, `app/doc_ocr.py`,
`app/doc_processor.py`. `tools/regression_test.py` run against whatever
files were present in `C:\Users\User\Desktop\testy` (only 2 real PDFs this
time — the test folder was nearly empty again, same recurring unexplained
issue documented elsewhere in memory/CLAUDE.md) — both PASS, 0 regressions.
CLAUDE.md updated (doc_ocr.py/doc_processor.py/app.py sections). Not yet
committed at the time of writing this memory — see git status before
assuming this is on `origin/etap2`.
