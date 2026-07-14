---
name: project-out-of-scope-detection
description: "General pattern for detecting documents the calculator shouldn't analyze — use already-extracted structured fields (sad_organ, powod) as gating signals, not just keyword score. Applied 14.07.2026 to KRS ex-officio dissolution orders, then a personal PIT tax return — the latter also exposed that a fixed keyword-count threshold is unreliable for long (multi-page) documents."
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

## Verified live (14.07.2026, follow-up session)

The PDF (`postanowienie.pdf`) resurfaced in `C:\Users\User\Desktop\testy\` — same
recurring cross-session file-loss/reappearance issue as [[project_wyrok_zaoczny]], no
root cause ever established, just plan around it. User uploaded it live in Streamlit
and confirmed the banner ("To postanowienie sądu rejestrowego KRS, nie spór o
zapłatę") and the "Zestawienie dokumentów" label both render correctly. Added to
`regression_expected.json` (`main_type: ["POSTANOWIENIE_KRS_Z_URZEDU"], amount: null,
gate: false`) — `tools/regression_test.py --only postanowienie.pdf` passes.

## Follow-on issue found during this live test: form stays active under the banner

The out-of-scope banner mechanism (this file, `_NON_LEGAL_MAIN_TYPES`/
`_SPOLKA_OUT_OF_SCOPE_TYPES`/`_KRS_REJESTROWE_OUT_OF_SCOPE_TYPES` in `app.py`) hides
the claim-data table and zeroes K7/deadline/amount, but never gated the Krok 1-7 form
itself — it renders unconditionally as a top-level script block in `app.py`
(`~line 686` onward, no `if`/gate wrapping it at all), so it appeared fully active and
clickable right under a banner that says "there's nothing here to evaluate." Fixed
(same session) by reusing the existing art.299-gate `st.stop()` pattern
(`app.py:644-678`, the only prior precedent for conditionally blocking form
rendering) — the form is now hidden behind an explicit opt-in button ("Mimo to chcę
wypełnić formularz ręcznie") rather than rendering by default. Lesson for next
out-of-scope category: the banner-and-zero-fields mechanism was never actually
"deactivating" anything downstream — it just changed what's displayed *above* an
otherwise-unaffected form. Check this every time a new out-of-scope type is added.

## Related: same underlying lesson applied to a different signal (14.07.2026)

Same session, different document (`KS_postanowienie.pdf` — a bailiff's order
*resuming* a suspended enforcement, not dissolving/out-of-scope at all): the
classifier and extractor correctly read the document but wrongly treated it as
urgent. Not a duplicate of this out-of-scope pattern (the document IS in scope — it's
an active enforcement against a natural person, art. 299 KSH gate is legitimately
relevant) — see [[project_komornik_boilerplate_deadlines]] for that fix. Mentioned
here because it was reported in the same user message and diagnosed with the same
underlying discipline: distrust a single regex/keyword match without checking whether
it's inside boilerplate (pouczenie) text rather than the operative part of the
document.

## Third out-of-scope instance: PIT tax return, next session — and the threshold trap

User (visibly frustrated — "znowu mamy ten sam błąd, który miał być rozwiązany",
"poważny błąd... co może zniechęcić potencjalnych użytkowników") uploaded their own
15-page PIT-36 (personal annual tax return, native digital PDF). Classified as
`DECYZJA_ZUS_US_SPOLKA` ("Decyzja ZUS/urzędu skarbowego (spółka)") at 0.667 confidence
— again with every identifying field (`sad_organ`, `sygnatura`, `powod`, `pozwany`,
`addressee`) correctly extracted as `null`, again ignored by classification.

Root cause was subtly different from the KRS case and taught a **new, important
lesson**: I added the obvious general fix first — a backstop keyed on "no identifying
fields at all" conjuncted with the existing weak-raw-score threshold (`< 4`, copied
from the `DOKUMENT_NIEPRAWNY` rule). It worked on a synthetic 3000-char excerpt of the
document but **failed on the real, full 15-page file** — raw score for
`DECYZJA_ZUS_US_SPOLKA` was exactly 4 (not `< 4`), purely from volume: a long,
repetitive tax form re-triggers generic single-point keywords ("podatnik", "urząd
skarbowy", "spółka" in a business-income section, "płatnik") many times across 15
pages, accumulating a score with zero real correlation to document length. **A fixed
keyword-count threshold that was calibrated on a one-page bank-transfer receipt does
not transfer to a fifteen-page government form.** This is a distinct, generalizable
risk: any future keyword-count-based backstop in this codebase should be treated with
suspicion for long documents.

Fixed with two layers, not one:
1. Kept the general "no identifying fields + weak raw score" backstop (still useful
   for short unknown documents, the original bank-transfer case) — see
   `doc_classifier.py`.
2. **Added a deterministic, non-threshold early-return** for the specific, unique,
   unambiguous marker this document family has: "POLTAX" (the e-Deklaracje system
   header, present on literally every Polish PIT form) or a `PIT` + 2-digit form code
   pattern (PIT-36/37/28/38/39...) in the first 1500 chars → `DOKUMENT_NIEPRAWNY` 0.9,
   completely bypassing the scoring loop and its threshold fragility. This mirrors how
   `WYROK_ZAOCZNY_SPOLKA` was solved (unique phrase match, not scoring) rather than
   the KRS case's structural-conjunction approach — picked because PIT forms have an
   unmistakable, unique textual fingerprint that a scoring threshold shouldn't be
   trusted to reliably outweigh at any document length.
3. Also tightened `ai_extractor.py`'s `czy_pismo_prawne` prompt: documents the client
   **submits to** an authority (own tax return, declaration, application) should be
   `False`, not just documents received **from** one. The AI's literal instruction to
   return `True` for "anything urzędowe" is what let a legitimately-official-but-
   irrelevant document through in the first place.

**Lesson for the next occurrence of this bug class**: when a fix relies on "raw
keyword score below N", verify it against the *actual, full-length* real document, not
a truncated excerpt — length-insensitive thresholds silently degrade as document size
grows. When a document type has a unique, deterministic textual fingerprint (a form
code, a fixed header phrase), prefer a phrase-match early-return over a scoring
threshold — it can't be out-argued by volume.

Verified: `process_files()` on the real file (`DECYZJA_ZUS_US_SPOLKA` 0.667 →
`DOKUMENT_NIEPRAWNY` 0.9), synthetic sanity check on a real nakaz (unaffected), added
to `regression_expected.json` (`main_type: ["DOKUMENT_NIEPRAWNY"], gate: false`),
`tools/regression_test.py --only pit_2025.pdf` passes.
