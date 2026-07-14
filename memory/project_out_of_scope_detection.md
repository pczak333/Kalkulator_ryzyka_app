---
name: project-out-of-scope-detection
description: "General pattern for detecting documents the calculator shouldn't analyze — use already-extracted structured fields (sad_organ, powod) as gating signals, not just keyword score. First applied 14.07.2026 to KRS ex-officio dissolution orders."
metadata:
  node_type: memory
  type: project
  originSessionId: 06278b5e-9e57-459b-a466-9f0d2c654d8d
---

## The recurring problem

This is the third distinct "this document shouldn't be analyzed as a claim" case in
this codebase, and each one so far got solved ad hoc:
1. `DOKUMENT_NIEPRAWNY` (03.07.2026) — bank transfer/invoice, not a legal document at
   all. Gated on AI field `czy_pismo_prawne is False`.
2. `WEZWANIE_PRZEDSADOWE_SPOLKA` out-of-scope handling (06.07.2026) — real legal
   document but no art. 299 KSH angle. Gated on the classified *type*, not on raw
   extracted fields.
3. **`POSTANOWIENIE_KRS_Z_URZEDU` (14.07.2026, this session)** — a real court order
   (KRS registry division dissolving an inactive/assetless company without
   liquidation, art. 25a/25b ustawy o KRS) got classified as `WEZWANIE_SADOWE_SPOLKA`
   at only 0.52 confidence and ran through the full risk-assessment UI (badge,
   deadline table) as if it were a creditor claim. It has no plaintiff and no claim
   amount — `doc_classifier.py` correctly extracted `sad_organ` (contains "Wydział
   Gospodarczy Krajowego Rejestru Sądowego") and `powod: null`, but neither field was
   used anywhere as a classification signal. User's framing, worth remembering
   verbatim: *"odczyt dokumentu w ogóle nie ma znaczenia w kolejnych analizach, a
   przecież po to tak się męczyliśmy nad prawidłowym odczytem dokumentu aby ten
   prawidłowy odczyt wykorzystać w dalszej analizie lub decyzji"* — the correct OCR
   extraction wasn't feeding back into the "should this even be analyzed" decision.

## The fix, and the reusable lesson

Grepped `doc_selector.py`/`doc_processor.py` for any existing use of `powod` as a
signal: zero hits. The classifier (`doc_classifier.py`) had exactly two escape
hatches from keyword scoring — `czy_pismo_prawne is False` (not a legal document) and
a low-raw-score backstop — and neither covers "genuinely a court/official document,
but not an adversarial money claim."

**Added a third, general escape hatch**: a new early-return keyed on a *structural
conjunction* of already-extracted fields rather than a one-off phrase match —
`sad_organ` mentions "rejestrowy"/"rejestru sądowego" (a KRS registry division, which
never hears adversarial disputes — litigation always goes through a different
division) **AND** `powod` is empty (no plaintiff — ex-officio proceedings are never
adversarial) **AND** the text has a "POSTANOWIENIE" title or "z urzędu" phrase. New
type `POSTANOWIENIE_KRS_Z_URZEDU`, confidence 0.85, plus a CSV 07 row as a keyword
fallback for when field extraction itself fails.

**Why this is different from every prior "add a new document type" fix in this
codebase**: every earlier early-return (wyrok zaoczny, doręczenie nakazu, pismo
procesowe) is keyed on a specific phrase/title for *that* document. This one is keyed
on a *combination of fields that generalizes* — any future ex-officio KRS registry
proceeding (not just dissolution-without-liquidation specifically, e.g. a future
"wezwanie do uzupełnienia wpisu") will hit the same conjunction without needing a new
rule. This is the direct, generalized answer to the user's complaint: extracted
fields (`sad_organ`, `powod`) now actually gate classification, the same way
`czy_pismo_prawne` already gates the "not a legal document at all" case.

**How to apply next time a similar complaint surfaces** ("the OCR/extraction was
right, but the classification/analysis ignored it"): before reaching for a new
CSV-07 keyword row, check whether the misclassified document has a *structural*
signature in already-extracted fields (missing plaintiff, registry-division court,
missing claim amount, `czy_pismo_prawne` boundary cases, `rodzaj_pisma` mismatches —
see `_RODZAJ_PISMA_FAMILIES` in doc_classifier.py, which has no bucket for
"decyzja/postanowienie rejestrowe z urzędu" and might need one if this pattern
recurs for ZUS/US ex-officio decisions too). A conjunction of 2-3 structural fields
generalizes much better than a phrase-match early-return.

**UI mechanism reused**: [[project_wyrok_zaoczny]] and the existing
`_NON_LEGAL_MAIN_TYPES`/`_SPOLKA_OUT_OF_SCOPE_TYPES` sets in `app.py` already had the
"hide the claim table, zero K7/deadline/amount, show a warning banner instead"
mechanism — added a *third* set (`_KRS_REJESTROWE_OUT_OF_SCOPE_TYPES`) rather than
reusing `_NON_LEGAL_MAIN_TYPES`, because that generic banner says "doesn't look like
a court document" — which would be false and confusing here (it very much IS a real
court order, just not a money claim). Lesson: when adding a new out-of-scope
category, check whether the existing banner wording is still true for the new case
before reusing it — if it would say something factually wrong, it needs its own set
+ banner text, not a shoehorn into the nearest existing one.

## Verification caveat (14.07.2026)

No PDF file was available for this test case — only a `.docx` OCR-text dump and two
screenshots (the actual PDF had vanished from `C:\Users\User\Desktop\testy\` again,
the same recurring cross-session file-loss issue noted in
[[project_wyrok_zaoczny]]). Verified `doc_classifier.classify_document()` directly
against the real extracted text/fields (0.85, correct) plus synthetic sanity checks
(a real lawsuit with a plaintiff, and a bailiff document with no plaintiff, both
correctly do NOT trigger the new rule) — but never exercised the actual Streamlit
upload → banner → zeroed-fields path end-to-end. Do that live pass once the PDF
resurfaces, and add it to `regression_expected.json`
(`main_type: ["POSTANOWIENIE_KRS_Z_URZEDU"], gate: false`).
