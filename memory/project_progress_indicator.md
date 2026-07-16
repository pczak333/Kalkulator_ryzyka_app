---
name: project-progress-indicator
description: "15.07.2026 — replaced the static st.spinner during document analysis with a live-ticking st.status widget (on_progress callback threaded through OCR cascade + doc loop); hit and fixed a real 'expanders may not be nested' bug caught by a live browser test. 16.07.2026 follow-up: switched status.write() (append-only, grew into a long scrolling list) to status.update(label=...) for a single in-place line, and stripped OCR engine names (Azure/Claude/Tesseract) out of user-facing messages."
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

## Follow-up (16.07.2026): one line instead of a growing list, no engine names

User's screenshot from actual use: the widget worked, but `status.write(msg)`
— the call this session's implementation used — **appends a new element on
every call**; it's not an in-place update. On a long scan (Azure poll every
2s) or a multi-page document (Tesseract/Claude per page) that's dozens to
hundreds of stacked lines — unprofessional-looking, not what "progress
indicator" was meant to produce. Second, independent ask in the same
message: several of the progress strings named the OCR engine outright
("(Azure Document Intelligence)", "(Claude)", "(Tesseract)") — an
implementation detail with no reason to be client-facing.

**Fix**: swapped `status.write(msg)` for `status.update(label=msg)` in the
`on_progress` lambda (`app.py`) — `st.status`'s `label` is a single value
that overwrites in place, which is exactly the "one line, updates, doesn't
grow" behavior asked for. Also flipped the container's `expanded=True` to
`expanded=False`, since nothing writes to the body anymore — an expanded
container with an empty body would look broken. The two existing
`status.update(state="error"/"complete", ...)` calls at the start/end were
untouched (already label-based). Separately, edited the 5 message strings in
`doc_ocr.py` to drop engine names (e.g. "OCR: analizuję dokument (Azure
Document Intelligence)..." → "OCR: analizuję dokument...") — pure text
changes, the underlying cascade logic (which engine actually runs, when
escalation happens) is untouched.

**Verified live** (agent-browser, `nakaz_zapłaty+pozew.pdf`, 12 pages):
watched the same single box change label over several screenshots —
"Analizuję dokumenty..." → "OCR: analizuję dokument..." → "OCR: strona
3/10..." → "...10/10..." → results — never more than one line, never an
engine name, no console errors. Final extracted data (sygnatura V GNc
1235/22/S, kwota 34 230,43 zł, termin 14 dni, powód/pozwany) matched the
values already documented for this test file in CLAUDE.md — confirms no
functional regression from the label-vs-write swap.

**Gotcha hit along the way, unrelated to the fix itself**: starting
`streamlit run app/app.py` from the repo root (as CLAUDE.md's own "to run
locally" instructions say) makes Streamlit resolve `secrets.toml` relative
to the *invocation* cwd, not the script's directory — it looked for
`<repo-root>/.streamlit/secrets.toml`, not the real
`app/.streamlit/secrets.toml`, and failed with `StreamlitSecretNotFoundError`
on first upload attempt. Had to restart with cwd = `app/`
(`cd app && streamlit run app.py`). Worth fixing the documented run command
at some point, or noting the cwd requirement explicitly — not done in this
session, flagged here so it isn't rediscovered from scratch.
