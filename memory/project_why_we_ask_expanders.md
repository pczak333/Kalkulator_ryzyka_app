---
name: project-why-we-ask-expanders
description: "15.07.2026 — added a collapsible 'Dlaczego pytamy?' explanation under each K1-K7 form step, sourced from an existing-but-unused CSV column (why_we_ask) rather than hardcoded text; fixed a data inconsistency in the same CSV row while there."
metadata:
  node_type: memory
  type: project
  originSessionId: 8db6b830-cf5f-4a60-818d-efade10a7858
---

## What happened

User wanted a "Dlaczego pytamy?" (why do we ask?) explanation at the end of
each K1-K7 form step, shown as a collapsible element after clicking an icon —
pattern taken from their own HTML prototype
(`C:\Users\User\Desktop\testy\krs_guard_kalkulator_ryzyka_v5.html`, a
`<details class="why"><summary>ℹ️ Dlaczego pytamy?</summary>...` element).

## Key finding: the content already existed, unused

Before writing any new copy, checked `dane_wejściowe/csv/08_4_Formularz_6_krokow.csv`
(the CSV backing the K1-K7 form questions/options) and found it already had a
`why_we_ask` column with well-written, client-appropriate Polish text per
step — populated when the form was originally designed, but never read by
`app.py` anywhere. Per this project's core rule ("never hardcode text that
can be CSV-driven"), the right move was to surface this existing column, not
write fresh copy. Confirmed with the user before implementing (`AskUserQuestion`)
that the existing texts were acceptable as-is — they were.

## Implementation

- `get_why_we_ask(step_id)` (app.py, next to `get_answers_for_step`) reads
  the already-cached `get_form_data()` DataFrame, filters by `step_id`, and
  returns the **most common** non-empty `why_we_ask` value
  (`collections.Counter(...).most_common(1)`) rather than just the first
  row's value — see the data-inconsistency note below for why this matters.
- `render_why_expander(step_id)` wraps it in
  `st.expander("ℹ️ Dlaczego pytamy?", expanded=False)` + `st.markdown(why)`,
  called once at the end of each of the 7 step blocks (K5's call sits
  *inside* the existing `if k4 == "K4_BOARD_RESIGNED":` conditional, since
  that's the only case K5 is shown at all — reusing the pre-existing gate,
  not inventing a new one).

## Data inconsistency found and fixed

One CSV row for K1 (`K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU`, added 05.07.2026
when that document category was introduced) had a *different* `why_we_ask`
text than the other 13 K1 rows — almost certainly a copy-paste oversight
from that addition, not an intentional per-answer variant (the expander
explains the *step*, read before any answer is chosen, so a per-answer
variant wouldn't make sense here anyway). The `Counter`-based "most common"
logic in `get_why_we_ask()` already made this harmless for display (13-vs-1
resolves correctly either way), but fixed the source data too, per the
project's "CSV and Excel must always be synchronized" rule — edited both
`08_4_Formularz_6_krokow.csv` and cell H40 of the `4_Formularz_6_krokow`
Excel sheet via a one-off openpyxl script (direct cell write by row index,
not by hand), verified `H40 == H3` (the reference generic-text row) after
saving.

## Streamlit API detail worth remembering

Checked the installed Streamlit version (1.45.1) directly via
`inspect.signature(st.expander)` before assuming a `key=` parameter was
needed for 7 identically-labeled expanders on one page (the original plan
assumed one was required and necessary to avoid a duplicate-ID collision).
**It isn't** — `st.expander`'s signature in this version is
`(label, expanded=False, *, icon=None)`, no `key` param exists at all.
Read Streamlit's `layouts.py` source to confirm why: `st.expander` is a
*container* (like `st.columns`/`st.container`), not a stateful input widget
— containers are positionally identified in the script's render tree, not
by label text, so identical labels at different call sites never collide.
This is a useful general lesson: don't assume a widget needs explicit
key-based disambiguation without checking whether it's actually a
value-holding widget (`st.button`, `st.text_input`, ...) or a layout
primitive — only the former needs it.

## Verified

Live browser test via `agent-browser` (Streamlit app run locally): all 7
expanders present with correct text on load (K5's — the 8th — correctly
absent until K4 is answered "Była rezygnacja / odwołanie", confirmed by
watching the expander count go 7→8 after toggling that radio via keyboard
focus+space, since a plain synthetic mouse click didn't register on the
custom BaseWeb radio component — a tooling quirk, not an app bug). No
console errors/exceptions from repeated identical expander labels, matching
the API-signature finding above.

**Not yet verified**: full `tools/regression_test.py` suite — the test
files were missing from `C:\Users\User\Desktop\testy` again at the time
this was implemented (same recurring, never-fully-explained issue as
documented elsewhere in memory/CLAUDE.md). Low risk since this change
touches only `app.py`'s form-rendering layer and CSV/Excel text — zero
changes to `doc_*.py`/`ai_extractor.py` (the OCR/classification pipeline
those regression tests actually exercise) — but still flagged, per project
convention, to run once the test folder is available again.
