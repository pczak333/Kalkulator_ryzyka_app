---
name: project-komornik-boilerplate-deadlines
description: "Bailiff document deadline extraction grabs the generic art. 767 KPC skarga-na-czynność-komornika complaint window (usually 7 days) instead of a real substantive deadline — same class of bug as prior boilerplate-pouczenie fixes. Fixed 14.07.2026 (extraction guard + new splitter kind + softer banner); also surfaced and fixed a list-order-vs-position bug in _KOMORNIK_TITLES matching, and a gap where single-document uploads never ran through the splitter at all."
metadata:
  node_type: memory
  type: project
  originSessionId: 06278b5e-9e57-459b-a466-9f0d2c654d8d
---

## The document and the complaint

`KS_postanowienie.pdf` — a bailiff's order (Komornik Sądowy przy SR dla
Krakowa-Krowodrzy, sygn. Km 449/24) to **resume a previously suspended** enforcement
proceeding (wierzyciel LYSON PAWEL, dłużnik CZAK PIOTR — a natural person), citing
art. 820 kpc. The entire operative sentencja is one line: "Podjąć zawieszone
postępowanie egzekucyjne w związku z wnioskiem wierzyciela zgodnie z art 820 kpc." —
a status notification that a case the debtor already knows about is continuing, not a
new demand or a new seizure action.

The calculator classified it as `PISMO_KOMORNIK_CZLONEK_ZARZADU`, extracted
`deadline_days=7`, and showed the same urgent banner ("najpóźniejszy etap sprawy,
wymaga szybkiej, profesjonalnej reakcji") used for actual asset-seizure notices. User
questioned whether this reading is right — correctly, per the diagnosis below.

## Root cause

The "7 dni" comes from the document's standard "Pouczenie" boilerplate about the
right to file a **skarga na czynność komornika** (art. 767 §1/§4 KPC) — a complaint
against *this specific bailiff action*, filed within 7 days, entirely optional and
conditional on the debtor wanting to challenge it. It is not a payment or response
deadline. This paragraph appears near-verbatim in essentially every bailiff document
in Poland, so this is a systemic extraction gap, not a one-off phrase to special-case.

Confirmed in code: `doc_extractor.py`'s keyword-proximity pass
(`_PRIMARY_ACTION_KEYWORDS`) doesn't include "skarg"-related terms, so this document
falls through to the unguarded whole-text fallback pass, which matches
`r"w\s+terminie\s+(\d+)\s+dni"` against the skarga clause with zero context check.
`ai_extractor.py`'s `termin_dni` field has no disambiguation rule at all (unlike
`kwota_zl`/`sad_organ`, which do). This is the same *class* of bug as prior fixes in
this codebase (see [[project_etap2_classifier]] and CLAUDE.md's
`_find_deadline_near_keyword()` history — "termin trzech miesięcy" from a
foreign-service clause, "14 dni" from a cytowany pouczenie in a bailiff continuation
page) — boilerplate pouczenie text mistaken for the substantive deadline — but this
specific phrase (art. 767 skarga window) had never been guarded against before,
because no prior test document surfaced it.

## Fix implemented (14.07.2026, same session)

Two layers, matching how every other "boilerplate misread as substance" bug in this
codebase got fixed — see CLAUDE.md's `doc_extractor.py`/`ai_extractor.py`/
`doc_splitter.py`/`doc_processor.py`/`app.py` entries for full detail:

1. **General guard** in `doc_extractor.py` (`_is_skarga_komornika_context()`/
   `_first_non_skarga_match()`): rejects any deadline match preceded within ~150
   chars by "skarg"/"art. 767" — applied to both extraction passes (keyword-proximity
   and whole-text fallback). This helps every bailiff document, not just this one.
   Mirrored in `ai_extractor.py`'s prompt with a new `termin_dni` rule block (it had
   none before, unlike `kwota_zl`/`sad_organ`).
2. **New splitter kind** `komornik_podjecie_zawieszonego` in `doc_splitter.py`
   (`_KOMORNIK_TITLES`), plus a new `app.py` banner branch keyed on
   `main.splitter_label` — softer tone ("to nie jest nowe żądanie...") instead of
   "najpóźniejszy etap sprawy, wymaga szybkiej reakcji". Stays inside
   `PISMO_KOMORNIK_CZLONEK_ZARZADU` (still real, in-scope enforcement against a
   natural person — art. 299 KSH gate and the full K1-K7 form remain active, in
   contrast to [[project_out_of_scope_detection]]'s pattern).

**Two additional bugs surfaced and fixed while implementing #2, worth remembering
independently:**

- `doc_processor.py`'s single-document code path (`detect_documents_by_pages()`
  returns `[]` when a file is just one logical document — true for this 1-2 page
  PDF) never called the splitter's per-page classifier at all, so
  `ProcessedDocument.splitter_label` was silently always `""` for any singly-uploaded
  file. Only multi-document bundles got splitter-kind metadata. Fixed by calling
  `_classify_page_segment()` on the whole text in that branch too — same fix
  incidentally improves classification confidence for single-file komornik uploads in
  general (they now get the same `splitter_kind` bonus signal in `doc_classifier.py`
  that bundle members already got).
- `doc_splitter.py`'s `_KOMORNIK_TITLES` matching picked the first pattern that
  matched **anywhere** in the header window, in **list order** — not by position in
  the text. The `komornik_skarga` pattern (`SKARGA NA CZYNNOŚĆ KOMORNIKA`) also
  matches the standard art. 767 boilerplate in the Pouczenie section of nearly every
  bailiff letter, so it silently shadowed any new kind added *after* it in the list —
  exactly what happened to the new `komornik_podjecie_zawieszonego` entry (its true
  title appears early in the text, but list-order matching ignored that and picked
  `komornik_skarga`'s later, boilerplate match instead, because that pattern came
  first in the list). This had been silently "working" for the 5 pre-existing kinds
  only because they all happened to be listed *before* `komornik_skarga`. Fixed by
  switching to earliest-*position*-wins matching (mirroring the existing Reguła 6
  fallback's `best_pos` pattern) — a general fix that removes a latent trap for any
  future kind appended to the list.

## Lesson

Every deadline-extraction bug in this codebase so far has the same shape: a regex
pattern with no awareness of *where* in the document it matched. The keyword-proximity
pass (`_PRIMARY_ACTION_KEYWORDS`) was built for exactly this reason, but the
whole-text fallback pass that runs when the proximity pass finds nothing has no
equivalent protection — it's the weakest link in `doc_extractor.py` and worth
auditing for other boilerplate phrases that could false-positive the same way
(anything from a generic "Pouczenie" section: right to appeal, right to object, right
to request installments, statute-of-limitations notices, etc.).

Broader lesson from the two bugs found *while implementing* the fix (see above): both
were latent, previously-masked-by-luck problems in shared infrastructure
(`doc_splitter.py`'s title matching, `doc_processor.py`'s single-doc path) that only
became visible because a new case exercised a code path nothing had exercised before.
When adding a new recognized document sub-type to an existing dispatch list/matching
loop, don't just add the entry — verify empirically end-to-end (`process_files()` on
the real file, not just the specific function you touched) that it actually reaches
the UI, rather than assuming the wiring documented for *other* similar types
generalizes automatically.

## Verified (14.07.2026)

`process_files()` on the real `KS_postanowienie.pdf`: `deadline_days=None` (was `7`),
`splitter_label="Podjęcie zawieszonego postępowania"` (was `""`), doc_type/K1 code
unchanged (`PISMO_KOMORNIK_CZLONEK_ZARZADU`/`K1_PISMO_KOMORNIK_CZLONEK_ZARZADU`).
Synthetic regression checks: a real 14-day wezwanie-do-wykazu-majątku deadline still
extracts correctly even with the same art. 767 boilerplate present elsewhere in the
document; a genuine "SKARGA NA CZYNNOŚCI KOMORNIKA" complaint form (title at the very
top) still classifies as `komornik_skarga`. Added to `regression_expected.json`
(`main_type: ["PISMO_KOMORNIK_CZLONEK_ZARZADU"], deadline_days: null, gate: true`),
`tools/regression_test.py --only KS_postanowienie.pdf` passes.
