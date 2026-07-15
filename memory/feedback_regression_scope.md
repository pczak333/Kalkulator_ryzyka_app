---
name: feedback-regression-scope
description: "When to run the full tools/regression_test.py suite vs. ask/skip, and who should run it (delegate to record-manager subagent, not the main loop)."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b843daf9-6aa1-48c6-8080-17f99160f229
---

## Rule

Don't automatically run the full `tools/regression_test.py` suite after
every change to `doc_*.py`/`ai_extractor.py`/`app.py` without judgment.
For a **purely additive/mechanical change** — a new optional parameter that
defaults to `None`/a no-op, with every call site wrapped so existing
behavior is byte-for-byte unchanged (e.g. the `on_progress` callback added
in [[project_progress_indicator]]) — ask the user first, or skip the full
run, rather than running it as a reflex.

**Why:** CLAUDE.md has a blanket rule ("uruchamiać po KAŻDEJ zmianie w
doc_*.py") written for a real, repeatedly-observed failure mode in this
project: a change that looks local silently breaks a *different* document
type because so much logic is shared across all documents (see the P1–P17
pitfalls list in `.claude/agents/record-manager.md`, and the extensive
CLAUDE.md history of "fix for file X broke file Y"). That risk profile is
real for logic changes (regex patterns, classification thresholds,
scoring). It is much lower for a wrapper-only change with no altered
branches — full regression there has a low signal-to-cost ratio, and the
test folder (`C:\Users\User\Desktop\testy`) is frequently near-empty
anyway (recurring, unexplained issue documented elsewhere in memory), so a
full run often can't even do much. When asked directly ("dlaczego cały
czas chcesz robić regresję na wszystkich plikach"), the user's pushback
was specifically about this reflexive, undifferentiated application of the
rule.

**How to apply:** Before running the full suite, judge the change:
- Touches classification/extraction/scoring/selection *logic* (new regex,
  new threshold, new branch, changed priority) → run full regression,
  no need to ask, per CLAUDE.md's existing rule.
- Purely additive plumbing (new optional param, logging, callback,
  docstring, comment) with zero change to existing code paths → ask the
  user whether to run it, or note explicitly that risk is low and skip,
  rather than running it by default.
- When in doubt, say so explicitly rather than silently picking one.

## Who runs it

Delegate full-suite regression runs (and the broader doc-pipeline audit:
segmentation, main-doc selection, OCR quality, K1–K7 consistency,
recommendation correlation) to the **`record-manager` subagent** rather
than running `tools/regression_test.py` directly in the main loop.
`record-manager` already has `Bash` in its tool list and its whole
procedure (KROK 0–5 + the P1–P17 pitfalls checklist in
`.claude/agents/record-manager.md`) is built exactly for this — "Use
proactively after changes to doc_splitter.py, doc_classifier.py,
doc_extractor.py, doc_selector.py, doc_processor.py, ai_extractor.py, or
app.py's document-handling/UI logic." Confirmed with the user 15.07.2026.
