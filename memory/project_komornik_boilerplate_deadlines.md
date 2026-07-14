---
name: project-komornik-boilerplate-deadlines
description: "Bailiff document deadline extraction grabs the generic art. 767 KPC skarga-na-czynność-komornika complaint window (usually 7 days) instead of a real substantive deadline — same class of bug as prior boilerplate-pouczenie fixes, not yet generalized to this specific phrase. Diagnosed 14.07.2026, fix in progress same session."
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

## Fix approach (see CLAUDE.md doc_extractor.py/ai_extractor.py/doc_splitter.py/app.py
entries for the final, implemented version — this file captures the diagnosis and
reasoning, not a step-by-step of what changed)

Two layers, matching how every other "boilerplate misread as substance" bug in this
codebase got fixed: (1) a general **guard** in the deadline extractor rejecting any
match preceded by "skarg"/"art. 767" nearby (this helps every bailiff document, not
just this one — a genuinely general fix, not a one-off), and (2) **recognizing this
specific bailiff sub-type** (resumption of a suspended proceeding) so its banner tone
is appropriately lower-key than an active seizure notice — while keeping it inside
the normal `PISMO_KOMORNIK_CZLONEK_ZARZADU` type (still a real, in-scope enforcement
matter against a natural person; the art. 299 KSH gate remains legitimate and should
still show).

## Lesson

Every deadline-extraction bug in this codebase so far has the same shape: a regex
pattern with no awareness of *where* in the document it matched. The keyword-proximity
pass (`_PRIMARY_ACTION_KEYWORDS`) was built for exactly this reason, but the
whole-text fallback pass that runs when the proximity pass finds nothing has no
equivalent protection — it's the weakest link in `doc_extractor.py` and worth
auditing for other boilerplate phrases that could false-positive the same way
(anything from a generic "Pouczenie" section: right to appeal, right to object, right
to request installments, statute-of-limitations notices, etc.).
