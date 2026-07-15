---
name: project-wps-amount-labeling
description: "Product decision + implementation: keep 'należność główna' (principal) as the primary displayed claim amount, never switch to wartość przedmiotu sporu (WPS) — but label which kind of amount is shown, and surface WPS as a secondary line when the document states it separately. 14.07.2026."
metadata:
  node_type: memory
  type: project
  originSessionId: 06278b5e-9e57-459b-a466-9f0d2c654d8d
---

## The question and my recommendation

User, after reviewing a live read-out of a real pozew (PKO Bank vs. Piotr Czak, kwota
roszczenia shown as 81 922,78 zł — the principal), asked whether the calculator should
show wartość przedmiotu sporu (WPS) instead, since Polish pozwy/nakazy often state it
explicitly, and asked for a clearer label so the user has certainty about which figure
they're looking at.

**Recommended against switching to WPS as the primary figure.** WPS is a *procedural*
value (art. 20 k.p.c. — basis for court jurisdiction and filing fees), not a client-
facing "how much do I personally risk" figure. It frequently INCLUDES interest accrued
up to the filing date, so it can be *higher* than the actual principal debt — the
opposite direction of the risk this calculator is trying to communicate. This project
already has a documented incident about exactly this failure mode: `Lublin_pozew_nak._
zap.2.pdf` — WPS 11 286,00 vs. należność główna 10 530,00 — and the underlying rule
("prefer należność główna when the document breaks the claim into principal +
interest/costs") was itself a fix for a real user-reported bug (04.07.2026, wezwanie
InterRisk showing 1 106,44 instead of the real 1 003,00 premium). Switching to WPS now
would be reverting that fix.

**What I did instead**: kept `kwota_zl` (principal-preferring) as the sole figure
feeding K7/scoring — zero change to risk assessment — but added transparency:
- `ai_extractor.py` new field `kwota_zl_rodzaj` (`"glowna"` / `"laczna"`) — tells the UI
  whether the shown figure is an isolated principal or the only/total figure (no
  breakdown in the document).
- New field `wartosc_przedmiotu_sporu_zl` — filled *only* when the document explicitly
  labels a WPS figure that differs numerically from `kwota_zl` (never a duplicate).
- `app.py`: "Kwota roszczenia" row gets a small grey caption underneath explaining what
  kind of amount it is; when WPS is present and different, a second table row
  "Wartość przedmiotu sporu" appears with its own caption ("z odsetkami/kosztami —
  podstawa opłaty sądowej, nie realne zadłużenie"). Both suppressed if the user already
  manually corrected the amount (`corr_kwota`) — a caption on a user-typed number would
  be describing something that's no longer true.

## Why this is the right general shape for "is our number right?" questions

This is the third time this session a user question boiled down to "the calculator
picked ONE number/label/type, but doesn't show its work" ([[project_out_of_scope_
detection]] for document type descriptions is the closest sibling). The fix pattern
that keeps recurring: **don't just pick the best answer — capture and surface the
*alternative* the algorithm considered and rejected, when that alternative is a
real, named legal concept the user might reasonably expect to see** (WPS is not some
internal implementation detail; it is a standard field printed on the pozew itself).
Hiding it silently, even when the *decision* to prefer the principal is correct,
reads as a possible error to a user who can see the WPS in front of them and a
different number on screen.

## Verified

3 synthetic AI-extraction scenarios (explicit principal+interest+WPS breakdown →
correctly split; no breakdown → `rodzaj="laczna"`, WPS null; WPS numerically identical
to the principal → correctly NOT duplicated) + real file `pozew_o_zapłate_pko.pdf`
(`amount=81922.78`, `amount_type="glowna"`, `wps_amount≈85464.00` — matches the
previously documented figures for this same case, `Lublin_pozew_pko.pdf`) +
`tools/regression_test.py` full suite, no regressions. HTML row-rendering logic
sanity-checked in isolation (caption/second-row markup renders correctly).

## Follow-up fix (15.07.2026): caption missing for komornik (bailiff) documents

User re-tested `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf` (PISMO_KOMORNIK_SPOLKA,
805,05 zł) and the "Kwota roszczenia" caption was simply absent — `amount_type` came
back null. Root cause: `ai_extractor.py`'s `kwota_zl_rodzaj` prompt rule was phrased
entirely in the vocabulary of court documents that split a claim into "należność
główna" vs. "odsetki/koszty" (the pozew/nakaz mental model this feature was originally
built for) — it never mentioned bailiff documents, which typically use different
vocabulary (kwota zadłużenia / kwota do zapłaty / suma egzekwowana, or a table breaking
the sum into należność główna / odsetki / koszty egzekucyjne / koszty zastępstwa
procesowego). The model most likely fell through to the rule's own last clause ("null
gdy `kwota_zl` jest null") rather than confidently picking glowna/laczna for unfamiliar
document vocabulary.

Confirmed **not** a code-path gating issue — `doc_processor.py`/`app.py` are fully
type-agnostic on `amount_type` (no `doc_type_code` branching anywhere in that path).
Pure prompt fix: added a new paragraph to the `kwota_zl_rodzaj` prompt rule extending
the same glowna/laczna logic explicitly to komornik documents, with bailiff-specific
example vocabulary, and an explicit instruction not to leave the field null just
because the document is a komornik letter rather than a pozew/nakaz.

**Lesson for future fields extracted per-document-type**: a prompt rule phrased around
the vocabulary of the type it was *first* built for silently under-serves every other
document family unless each new family is explicitly taught to the prompt — the same
"good mechanism, narrow initial vocabulary" gap already seen with `czy_pismo_prawne`
(taught company-vs-individual submitter distinction incrementally) and `termin_dni`
(taught the art. 767 skarga-deadline exclusion incrementally, see
[[project_komornik_boilerplate_deadlines]]). When adding a new AI-extracted field,
consider up front whether its rule wording generalizes across all document families the
calculator already classifies, not just the one that motivated the field.
