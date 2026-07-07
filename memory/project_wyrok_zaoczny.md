---
name: project-wyrok-zaoczny
description: "Wyrok zaoczny misclassified as NAKAZ_SPOLKA (07.07.2026) — new \"light integration\" pattern (recognize + relabel, reuse existing K1/scenario instead of building a full new category)"
metadata: 
  node_type: memory
  type: project
  originSessionId: e96a4de8-2045-4279-8b22-548f4b3b0acf
---

## What happened (07.07.2026)

User uploaded `wyrok.pdf` (a default judgment — "WYROK ZAOCZNY" — against
WOODHOME sp. z o.o., V GC 854/22/S, 51 408 zł, rygor natychmiastowej
wykonalności). The calculator classified it as `NAKAZ_SPOLKA` with only
0.51 confidence. Root cause: the document-type taxonomy
(`dane_wejściowe/csv/07_3_Typy_dokumentow.csv`) never had a "wyrok" type
at all — the classifier can only pick among existing types. The literal
word "nakaz" never appears in the document; `NAKAZ_SPOLKA` won purely
because its keywords ("sprzeciw", "zarzuty", "pozwany") happen to also
describe opposing a default judgment (same vocabulary, different
document). See [[project_etap2_classifier]] for the general classifier
architecture.

User's framing of the bug: "dlaczego nie ma korelacji między dobrze
odczytanym dokumentem a jego analizą" — the raw OCR text clearly showed
"WYROK ZAOCZNY" and "W IMIENIU RZECZYPOSPOLITEJ POLSKIEJ" (a judgment-only
legal formula), but that signal had zero influence on classification
because no candidate type was ever checking for it.

## Business decision: "light integration" pattern (new, distinct from [[project_wezwania_przedsadowe]])

User explicitly rejected building a full new category (new K1 option +
~15 scenario rows per SPOLKA/CZLONEK_ZARZADU variant in CSV 12, the
pattern used for wezwania przedsądowe) — argued a wyrok zaoczny against
the company isn't significant enough to justify that cost. I pushed back
partially (a wyrok with rygor natychmiastowej wykonalności is arguably a
*stronger* art. 299 precursor signal than a nakaz, since it enables
immediate egzekucja) but agreed the real complaint — the wrong label
shown to the client — doesn't require a full scenario library to fix.

**Landed on a lighter pattern**: recognize the type correctly (for
labeling/UI purposes) but reuse an existing K1 code's scoring +
scenario-matching machinery, with a targeted text override for the
handful of scenario fields that name the wrong document type. This works
because `scenario_selector.find_scenario()` matches CSV 12 rows purely on
`(k1_code, epu)` → `resolve_doc_type()`, never on the classifier's raw
`doc_type_code` — so mapping a new type's K1 to an existing K1 code is
enough to get full risk-scoring behavior for free, with zero new CSV
rows.

**How to apply**: when a new document type surfaces, don't default to
the full-buildout pattern from [[project_wezwania_przedsadowe]]. Ask
whether the new type is procedurally close enough to an existing one
(same deadline/remedy shape) to justify reuse. If yes: add the type only
to CSV 07 (classification) + `doc_processor.py _DOC_TYPE_TO_K1` (mapped
to the existing K1) + `doc_selector.py` scoring dicts, then add a text
override in `app.py` (same location/pattern as the existing
`PISMO_PROCESOWE_SADOWE` override block, ~line 856) for only the
scenario fields that literally misname the document. Don't blindly
full-replace every text field — check which fields actually vary
per-scenario first (dumped all unique `user_summary_base` /
`user_risk_explanation_base` / `user_practical_meaning_base` values for
`NAKAZ_SPOLKA`/`NAKAZ_CZLONEK_ZARZADU` from CSV 12 before writing the
override): `user_summary_base` carries a genuinely useful dynamic
risk-level/timeframe sentence worth preserving via a targeted substring
replace, not a full overwrite; `user_practical_meaning_base` was already
identical across all 15 rows for each type, so a full static replacement
loses nothing.

## Implementation (07.07.2026, this session)

- CSV 07 + Excel: new rows `WYROK_ZAOCZNY_SPOLKA` / `_CZLONEK_ZARZADU`.
- `doc_classifier.py`: new early-return keyed on "W IMIENIU
  RZECZYPOSPOLITEJ POLSKIEJ" + "WYROK...ZAOCZNY" in the first 800 chars,
  confidence 0.85.
- `doc_processor.py`: `_DOC_TYPE_TO_K1` maps both new codes onto
  `K1_NAKAZ_SPOLKA` / `K1_NAKAZ_CZLONEK_ZARZADU` — no new CSV 08/09/12
  rows.
- `doc_selector.py`: added to `_TYPE_SCORES` (same tier as NAKAZ),
  `_COURT_TYPES`, `_SPOLKA_TO_CZLONEK`, `_UPGRADED_TYPE_TO_K1`.
- `app.py`: `_DOC_TYPE_LABELS` entries; new `elif` block (next to the
  existing `PISMO_PROCESOWE_SADOWE` override) that patches
  `user_summary_base` (targeted substring replace) and fully replaces
  `user_risk_explanation_base` / `user_practical_meaning_base` for both
  variants.
- `context_modules.py`: added `WYROK_ZAOCZNY_CZLONEK_ZARZADU` to
  `_CZLONEK_ZARZADU_DOC_TYPES` (generic, correct urgency note); left the
  NAKAZ/POZEW-substring-matching helpers (`_k6_procedural_text` etc.)
  alone on purpose — they don't match the new codes and fall back to
  generic text instead of wrongly saying "nakaz zapłaty".
- `tools/regression_expected.json`: added `wyrok.pdf` entry
  (`WYROK_ZAOCZNY_SPOLKA`, 51408.0, deadline_days 14, gate false).

## Status: verified live (08.07.2026)

`C:\Users\User\Desktop\testy\wyrok.pdf` briefly disappeared from the test
folder mid-session (along with `obraz2.png`; an unrelated
`KS_postanowienie.pdf` appeared instead) — cause never established,
possibly related to the same session's finding that `C:` had only
~180 MB free. User confirmed the files were restored the next day.
`python tools/regression_test.py` then gave **1 PASS, 0 FAIL** for
`wyrok.pdf` (main_type `WYROK_ZAOCZNY_SPOLKA`, amount 51408.0,
deadline_days 14, gate false) — matches `regression_expected.json`
exactly. Offline pipeline simulation (done earlier, before the file
reappeared) had already confirmed the same result on the raw OCR text
from the user's screenshot, and confirmed the `user_summary_base` text
override matches 100% of the 15 `NAKAZ_SPOLKA` + 11
`NAKAZ_CZLONEK_ZARZADU` scenario rows in CSV 12 — both checks agree.
