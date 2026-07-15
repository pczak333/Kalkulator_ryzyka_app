---
name: session-2026-07-15-full-regression
description: "15.07.2026 — full parallel-agent regression sweep across all 31 collected test files after the 14.07 session; found and fixed one real bug (postanowienie o umorzeniu continuation page), confirmed one FAIL was AI/OCR flakiness not a code bug."
metadata: 
  node_type: memory
  type: project
  originSessionId: 8db6b830-cf5f-4a60-818d-efade10a7858
---

## What happened

Continuation of the 14.07.2026 session's deferred open item: run the full
regression suite (not just `--only` spot-checks) now that the user copied a
complete set of 31 historically-used test files into
`C:\Users\User\Desktop\testy\`. Of the 31, 20 already had entries in
`tools/regression_expected.json`; 11 were new/uncovered.

Execution approach: split the 20 known files into 4 batches of 5 and the 11
new files into 2 batches, ran via parallel `record-manager` subagents (Agent
tool, multiple calls in one message) — each batch ran
`tools/regression_test.py --only <file>` (or a scratch diagnostic script for
the uncovered files, since the script only iterates files present as JSON
keys) and reported back a compact PASS/FAIL summary instead of raw console
output. This kept the main conversation's context small despite ~31
real OCR+AI pipeline runs.

## Results

**20 known files: 20/20 PASS** (after the fix below; initially 18/20 with 2
FAILs, see below).

**11 new files (no saved ground truth, pure diagnostic — not evaluated
correct/incorrect):** all processed successfully; see the file-by-file
detail preserved in the conversation transcript if needed later.
`Lublin_nakaz_zapłaty_pko.jpeg`/`Lublin_pozew_pko.png` (image variants of
already-known documents) and `art.299_nak_zap.pdf`/`art.299_nakaz_zap2.pdf`/
`nak.zap.3.pdf`/`pozew.pdf` (new documents in the same Kiloutou/Woodhome test
family) all classified plausibly. `ZUS_st.1.jpeg`+`ZUs_str.2.jpeg` processed
together as one 2-page bundle (page 1/page 2 of the same ZUS letter) per
filename inference — correctly detected as one `DECYZJA_ZUS_CZLONEK_ZARZADU`
document with a 2nd related aux doc.

## Two FAILs investigated

**1. `postanowienie.pdf` — NOT a code bug.** First run: `WEZWANIE_SADOWE_SPOLKA`
instead of `POSTANOWIENIE_KRS_Z_URZEDU` (the type added 14.07, see
[[project_out_of_scope_detection]]). Re-ran twice more: **2/2 correct**. This
was AI/OCR run-to-run variance in the `sad_organ`/`powod` extraction feeding
the classifier's structural early-return condition — a well-documented
characteristic of this pipeline (Azure DI + Claude Haiku are not fully
deterministic across runs on the same scan). No code change made; logged as
a known-flaky data point, not a regression.

**2. `art299_pozew_nakaz_umorz._egzek..pdf` — real, reproducible bug, now
fixed.** The postanowienie komornika o umorzeniu (str.12-13) spans two pages:
sentencja (str.12, has its own "POSTANOWIENIE"+"KOMORNIK" header) + koszty
egzekucji rozliczenie (str.13, no header of its own — plain continuation).
Two independent, compounding causes, both now fixed:

- **Splitter** (`doc_splitter.py`, Krok -2 post-processing): the generic
  fallback-kind "komornik" page (str.13) only merges into an immediately
  preceding komornik_* segment if that segment's kind is in
  `_KOMORNIK_MERGE_TARGETS` — `postanowienie_umorzenie_egzekucji` was
  deliberately excluded from that set (same protective reasoning as
  `wniosek_egzekucyjny`, to avoid gluing unrelated pages into art. 299
  bundles). Fixed by adding `postanowienie_umorzenie_egzekucji` to that set
  — `wniosek_egzekucyjny` deliberately left excluded (no evidence of the
  same problem there in this test file; its own multi-page continuation
  already merges fine via the ordinary `None`-continuation path).
- **Classifier** (`doc_classifier.py`): even after the splitter correctly
  merges both pages into one `postanowienie_umorzenie_egzekucji`-kind
  segment, the classifier had no deterministic bonus for that kind (only
  for komornik-letterhead and pismo_procesowe kinds) — so pure keyword
  scoring on the merged 2-page text let `PISMO_KOMORNIK_SPOLKA` win, because
  str.13's cost-breakdown text is dense with "koszty komornicze"/"opłata
  egzekucyjna" keywords. Fixed by adding a +25 deterministic bonus for
  `_splitter_kind == "postanowienie_umorzenie_egzekucji"` →
  `UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC`, following the exact same established
  pattern already used for komornik/pismo_procesowe kinds a few lines above.

Both fixes were necessary — neither alone resolved it (verified by observing
the failure signature *change shape* between runs: sometimes the two pages
split into separate aux docs, sometimes they merged into one but still
misclassified — this is what revealed there were two separate root causes,
not one flaky one).

**Verification:** `art299_pozew_nakaz_umorz._egzek..pdf` alone passed 3/3
consecutive runs after both fixes. Full regression on all 19 other known
files re-run afterward (same parallel-batch approach): 19/19 PASS, no side
effects from touching shared `doc_splitter.py`/`doc_classifier.py` logic.

## Incidental operational finding: a genuinely hung background process

One of the 11 new-file diagnostics (`wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf`,
a large ~20-page komornik bundle) hung for ~1.5 hours with almost no CPU
progress in the last 44 minutes (70.6s → 76.7s CPU time) — a real hang, not
just "slow OCR on a big file" (which is a legitimate, previously-documented
characteristic of this pipeline for large bundles). User approved killing
the process (`taskkill /F`) and retrying; the retry completed normally in a
reasonable time. Worth knowing for future large-bundle test runs: if CPU
time stalls almost completely while wall-clock keeps advancing, that's a
hang signal worth checking, not just "big file, be patient."

## Process note for future sessions

Splitting regression-suite work across parallel subagents (batches of 5,
`record-manager` type) worked well for keeping context small across ~31 real
pipeline runs. One subagent silently stopped partway through its batch after
launching one item's Bash call in the background and ending its turn instead
of waiting — had to be explicitly resumed via SendMessage twice to get full
results. When delegating multi-item sequential work to a subagent, consider
being explicit that "wait for each background command to finish before
moving to the next, and don't end your turn until all items are reported."
