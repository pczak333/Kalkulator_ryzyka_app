---
name: project-unrelated-docs-warning
description: "When a user uploads multiple documents that turn out to be unrelated cases (different creditor/powód), the calculator picked a main document correctly but gave no indication the aux document(s) belong to a different matter. Fixed 14.07.2026 by comparing powód across main/aux with fuzzy company-name normalization. Also flags a related, unaddressed risk in doc_selector.py's Fix B."
metadata:
  node_type: memory
  type: project
  originSessionId: 06278b5e-9e57-459b-a466-9f0d2c654d8d
---

## The scenario

User explicitly tested this: uploaded two genuinely unrelated court documents in one
batch — `299_przeds._wezw._do_zap..pdf` (przedsądowe wezwanie, wierzyciel MIPROMET
Sp. z o.o., correctly picked as main — shorter 3-day deadline) and
`art.299_nak_zap.pdf` (nakaz zapłaty, sygn. V GNc 1138/23/S, wierzyciel KILOUTOU
Polska sp. z o.o. — a *different* creditor). Both documents happen to concern the same
individual defendant (Piotr Czak) and, per earlier session history
([[project_etap2_classifier]]-adjacent test files), possibly the same underlying
insolvent company (WOODRAFT HOME) — but from the calculator's structural-data point of
view they are two independent legal claims from two independent creditors.

Main-document selection was correct. The bug: nothing anywhere told the user the aux
document belongs to a *different matter* — the UI silently presents both as if part of
one coherent case, exactly like this app's legitimate multi-document bundles (nakaz+
pozew of the same case, the art. 299 chain pozew→nakaz→wniosek_egzekucyjny→umorzenie).
User's framing: OCR read both documents correctly (verified via the technical panel),
but nothing was *done* with that correct reading — the same "good read, no downstream
use" complaint pattern as [[project_out_of_scope_detection]] and
[[project_komornik_boilerplate_deadlines]], applied to a new axis (cross-document
coherence rather than single-document classification/extraction).

## The fix

Compare `main.powod` (creditor) against every `aux[i].powod`, with fuzzy normalization
(`_normalize_party_name()`/`_parties_differ()` in `app.py`) that strips company-form
suffixes (sp. z o.o., S.A., spółka akcyjna, etc.) so "PKO Bank Polski S.A." and "PKO
BANK POLSKI SPÓŁKA AKCYJNA" are recognized as the same entity. When a clear mismatch is
found, `_show_doc_summary()` shows a non-blocking `st.warning()` naming which aux
document and which creditor differs, inviting the user to either re-upload separately
or continue (risk assessment still uses only the main document).

**Why `powod` and not `sygnatura`, deliberately**: this codebase has extensive,
carefully-built logic for legitimate bundles where the *sygnatura legitimately differs*
across documents belonging to the *same* matter — most notably the bailiff case number
(Km NN/YY) vs. the court case number in the nakaz→egzekucja→umorzenie chain
(`doc_selector.py`'s whole "Fix B"/art. 299 chain detection exists because of this). Had
I compared sygnatura, it would have false-positived on every one of those real,
already-tested bundles. The creditor identity, by contrast, is invariant within a
single matter in every bundle pattern this app currently supports — a different
creditor name is a reliable, general signal of "different case," full stop.

**Zero new AI calls** — `powod` is already extracted for every candidate document in
the pool (`doc_processor.py`'s `_build_candidate_dict()` runs AI extraction per
candidate, not just the eventual main), so this is pure app.py-side comparison logic.

## Related, unaddressed risk (flagged for future investigation, not fixed here)

`doc_selector.py`'s "Fix B" bundle upgrade (SPOLKA→CZLONEK_ZARZADU) scans the *entire
pooled text* of all candidates for "art. 299"/"członek zarządu" mentions to decide
whether to upgrade a SPOLKA-typed main document. If a user uploads two genuinely
unrelated documents where one mentions art. 299 and the other doesn't, this could in
principle cross-contaminate classification of a document that has nothing to do with
board-member liability. Not exercised by this session's test case (the main document
here was already correctly `_CZLONEK_ZARZADU` from its own content, so Fix B never
needed to fire) — but worth checking if a future bug report shows a SPOLKA document
getting upgraded due to an unrelated aux document's content. If it recurs, the same
`_parties_differ()` helper could gate Fix B too (only trust art.299 mentions from
documents sharing the main document's creditor).

## Verified

7 unit cases for `_parties_differ()` (different companies, same company different
spelling, PKO Bank Polski S.A. vs. full "spółka akcyjna" form, missing data on either
side, person names) all correct. Simulated the full `_show_doc_summary()` banner
construction with real extracted data (MIPROMET vs. KILOUTOU) — renders the intended
message. `tools/regression_test.py` does not exercise this (it calls `process_files()`
directly, never renders the Streamlit banner layer) — no regression risk from that
angle since nothing in `doc_processor.py`/`doc_selector.py` changed.

## Follow-up fix (15.07.2026): swapped name-token order false positive

User re-tested `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf` and got a false "different
case" warning: `main.powod = "Faliszewska Barbara"`, one aux doc's `powod =
"Barbara Faliszewska"` — the same real person, just first-name/last-name written in
reversed order between two documents of the same bailiff case (the wszczęcie egzekucji
letter vs. a later zajęcie letter apparently transcribed the name differently). The
original `_parties_differ()` only does a substring check after normalization — a
reversed 2-token name fails both directions of that check, so it was flagged as a
different creditor.

Fix: added `_same_person_reordered(na, nb)` — when **both** normalized names have 2-3
tokens (typical imię+nazwisko, optionally with a second given name), compare them as
token **sets** regardless of order; if equal, treat as the same party. This is an
*additional* check alongside the existing substring check, not a replacement for it —
substring matching still handles company-name variants (PKO Bank Polski S.A. vs. full
form) exactly as before.

Manual trace-throughs (re-verifying the original 7 cases still hold, plus the new bug
case and one new adversarial case):
- `"Faliszewska Barbara"` vs `"Barbara Faliszewska"` → token sets equal → **not
  flagged** (bug fixed).
- `"Jan Kowalski"` vs `"Piotr Kowalski"` (same surname, different actual person) → token
  sets `{JAN,KOWALSKI}` vs `{PIOTR,KOWALSKI}` differ → **still flagged** as different
  (the fix doesn't get fooled by a shared surname alone).
- `"MIPROMET Sp. z o.o."` vs `"KILOUTOU Polska sp. z o.o."` (original verified case) →
  MIPROMET normalizes to 1 token, below the 2-3 token gate → reordering check never
  fires → substring check alone still flags it as different. No regression.
- `"PKO Bank Polski S.A."` vs full "spółka akcyjna" form → identical after
  normalization, substring check already resolves this before the reordering check is
  reached. No regression.

**Documented residual risk, accepted deliberately**: two genuinely *different* short
entities (companies, after suffix-stripping) whose names happen to be an exact 2-3
token permutation of each other (e.g. hypothetical "Auto Serwis" vs "Serwis Auto")
would now be wrongly treated as the same party. No test file in the current suite
exhibits this pattern; assessed as low real-world risk because AI-extracted company
names preserve canonical word order in practice, unlike personal names, which
legitimately vary Imię-Nazwisko vs Nazwisko-Imię between different documents/forms of
the same case. Revisit if a future bundle surfaces this collision.

No automated regression coverage exists for this path today (`tools/regression_test.py`
never renders the Streamlit banner) — verification was a standalone script importing
`_parties_differ()`/`_same_person_reordered()` from `app.py` directly, same approach as
the original 7 cases.

## Related, discovered-but-deferred issue (15.07.2026): OCR letter-substitution typos

Running the real fix end-to-end on `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf` surfaced
a *different* false positive on the same file: one aux document's `powod` came back as
`"Barbara Baliszewska"` (OCR misread F→B) against the main document's `"Faliszewska
Barbara"` — still flagged as a different creditor. This is NOT the word-order bug fixed
above; it's a single-character OCR substitution within a token.

Investigated a token-level fuzzy match (per-token `difflib.SequenceMatcher` ratio,
requiring all-but-one token to match exactly and the remaining token to score above a
threshold) and it does discriminate the real typo correctly (`"FALISZEWSKA"` vs
`"BALISZEWSKA"` → 0.909 ratio). **Deliberately not implemented**: the same technique
scores a genuinely *different*-person case dangerously close — Polish gendered surname
variants like `"WISNIEWSKA"` vs `"WISNIEWSKI"` (a very plausible spouse/family-member
pairing sharing a surname, i.e. two different real people) score 0.900, higher than the
real typo. A single similarity threshold cannot safely separate "OCR typo, same person"
from "gendered surname variant, different person" — and the failure mode of getting it
wrong (silently suppressing a genuine cross-case warning) is worse than the failure mode
of leaving it alone (an occasional unnecessary but non-blocking `st.warning()`, since
this feature never blocks the calculation, only informs). Left as a known, documented
residual false-positive rate for OCR-degraded names — revisit only if a future report
shows this recurring with a clearer discriminating signal than plain edit-distance.
