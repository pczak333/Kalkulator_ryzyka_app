---
name: session-2026-07-14-summary
description: "Single entry point for what happened in the 14.07.2026 session — 6 fixes/features on etap2, all committed and pushed. Read this first when resuming work; it links to the detailed per-topic memory files."
metadata:
  node_type: memory
  type: project
  originSessionId: 06278b5e-9e57-459b-a466-9f0d2c654d8d
---

## State at end of session

Branch `etap2`, fully committed and pushed to `origin/etap2`. Latest commit:
`cce132b`. Working tree clean. No uncommitted work anywhere. Eight commits landed
this session, oldest to newest:

1. `c5b38a1` — Krok 1 wyrok zaoczny K1-label fix
2. `3fb7339` — POSTANOWIENIE_KRS_Z_URZEDU out-of-scope detection
3. `40416e0` — docs-only: live verification confirmation + new-topics writeup
4. `2d09b84` — form opt-in gate for out-of-scope docs + komornik boilerplate deadline fix
5. `5d05653` — PIT tax return misclassification fix
6. `8c21d3d` — AI-generated `opis_dokumentu` for out-of-scope banner (generalized PIT fix)
7. `e595053` — WPS vs. kwota główna labeling
8. `cce132b` — cross-document creditor-mismatch warning

Detailed memory per topic (all also copied to repo `memory/` — read these for full
technical detail, this file is just the map):
- [[project_wyrok_zaoczny]] — K1 code split, live-verified
- [[project_out_of_scope_detection]] — the throughline for 4 of today's fixes: KRS
  registry orders, PIT tax returns, the form-opt-in-gate UX fix, and the final
  generalization to AI-generated `opis_dokumentu`
- [[project_komornik_boilerplate_deadlines]] — art. 767 skarga-window false deadline +
  two incidentally-discovered bugs (splitter list-order matching, single-doc uploads
  never hitting the splitter)
- [[project_wps_amount_labeling]] — kept należność główna as primary, added WPS as a
  labeled secondary line
- [[project_unrelated_docs_warning]] — powód-mismatch warning; flags an unaddressed
  risk in `doc_selector.py`'s Fix B for future attention

The plan file used throughout the session (`~/.claude/plans/breezy-munching-harp.md`,
reused/overwritten for each of the ~6 planning rounds) has its final state (topic 8)
copied to the repo at `plany/ostrzezenie-o-niezwiazanych-dokumentach-breezy-munching-harp.md`
per the project's cross-computer continuity rule. The five earlier plan versions from
this session were not individually saved before being overwritten — their substance is
fully captured in the per-topic memory files above (which include more detail than the
original plans: verification results, actual code locations, discovered side-bugs).

## The throughline across the whole session

Every fix today was a variation on one theme, stated explicitly by the user multiple
times and worth carrying into future sessions as a standing principle for this
codebase: **the OCR/AI extraction is already correct — the bug is always that a
downstream decision (classification, banner text, amount shown, bundle coherence)
ignores what was correctly extracted.** Concretely this showed up as:
- structural fields (`sad_organ`, `powod`, `sygnatura`) not gating classification
  (KRS, PIT)
- a static banner/label where a specific, already-known answer existed (PIT →
  generalized to AI-generated `opis_dokumentu` for *any* irrelevant document)
- a boilerplate regex match with no awareness of *where* in the document it fired
  (komornik art. 767 skarga clause)
- one correct number (kwota główna) chosen over another correct-but-different number
  (WPS) with no way for the user to see that a choice was even made
- two documents pooled together with no signal that they might not belong together

When the next bug report has this shape, check whether the "wrong" answer is actually
a *downstream* problem (ignoring already-correct data) before reaching for a new
regex/keyword/type. That's been true in 6/6 cases this session.

## Known open items (not fixed, intentionally deferred)

- `doc_selector.py`'s "Fix B" (SPOLKA→CZLONEK_ZARZADU upgrade) scans the *entire*
  pooled bundle text for art. 299 mentions — could in principle misfire across two
  genuinely unrelated uploaded documents. Not exercised by any real bug report yet;
  watch for it. See [[project_unrelated_docs_warning]].
- Test PDF files in `C:\Users\User\Desktop\testy\` keep disappearing/reappearing
  between sessions (same unexplained issue noted repeatedly across
  [[project_wyrok_zaoczny]] and others) — always check that folder fresh at the start
  of a session rather than assuming a previously-used file is still there.
- Several `regression_expected.json` entries were added this session
  (`postanowienie.pdf`, `KS_postanowienie.pdf`, `pit_2025.pdf`,
  `pozew_o_zapłate_pko.pdf`) but could only be spot-verified with `--only` since most
  of the *other* historical test files were absent from the testy folder during this
  session (see point above) — worth a full `tools/regression_test.py` run (no
  `--only`) next time all files happen to be present together, to catch any
  cross-fix interaction the session's individual verifications might have missed.
