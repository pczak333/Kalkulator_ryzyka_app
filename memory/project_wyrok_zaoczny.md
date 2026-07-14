---
name: project-wyrok-zaoczny
description: "Wyrok zaoczny misclassified as NAKAZ_SPOLKA (07.07.2026) — new \"light integration\" pattern (recognize + relabel, reuse existing K1/scenario instead of building a full new category); 14.07.2026 follow-up fix: light integration leaked into K1 UI label, gave wyrok its own K1 code"
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

## Follow-up bug + fix (14.07.2026): light integration leaked into the UI

First live test in Streamlit (not caught by `regression_test.py`, which
only checks `main_type`/`amount`/`deadline_days`/`gate`, never K1)
surfaced a real bug: Krok 1 of the form pre-selected **"Nakaz zapłaty
(spółka)"** and the technical panel showed `Kod K1: K1_NAKAZ_SPOLKA` for
a document whose title/summary/panel "Typ dokumentu" all correctly said
`WYROK_ZAOCZNY_SPOLKA`. Root cause: `_DOC_TYPE_TO_K1` mapped the new
doc types onto the *existing* `K1_NAKAZ_SPOLKA`/`K1_NAKAZ_CZLONEK_ZARZADU`
codes, and that same K1 code drives both (a) scoring/scenario-text reuse
(intentional) and (b) the label shown in Krok 1 + the raw code in the
technical panel (not intentional — nobody had traced that far). The
07.07 `app.py` text-override block runs only *after* form submit and
never touches Krok 1's pre-selection or the technical panel, both of
which read `prefill.k1_code` baked in at `doc_processor.py` time.

**Lesson for future "light integration" cases**: reusing an existing K1
code gets you scoring + scenario-text reuse "for free", but it also
silently reuses that K1 code's **CSV 08 label** — visible confirmation
bias risk (client sees two contradictory document names on the same
screen). The fix is not to abandon the light-integration pattern, but to
split the two concerns: give the new type **its own K1 code** (own CSV
08 label, own CSV 09 scoring row — copied 1:1 from the reused type) while
keeping `scenario_selector.py`'s `_K1_TO_DOC_TYPE` reverse-mapping
pointed at the *original* type, so `find_scenario()` still resolves to
the reused scenario text and the existing `app.py` override block (which
matches on `state["DOC_TYPE"]`, independent of K1) keeps working
unchanged.

Also caught in the same fix: `hard_rules.py`'s HR02/HR04 (urgent-deadline
safety overrides) checked `K1 == "K1_NAKAZ_CZLONEK_ZARZADU"` by exact
string — splitting the K1 code would have silently *removed* that safety
net for wyrok-zaoczny-członek-zarządu with a short deadline. Extended
both to match a small tuple of "nakaz-like" K1 codes instead of a single
literal. **Checklist for next light-integration case**: grep the whole
`app/` tree for every literal usage of the reused K1 code before deciding
the new code is a safe drop-in — it showed up in 4 places beyond
`doc_processor.py`: `scenario_selector.py` (`_K1_TO_DOC_TYPE`),
`doc_selector.py` (`_UPGRADED_TYPE_TO_K1`, a duplicate mapping kept
separate to avoid a circular import), `app.py` (`EPU_COMPATIBLE`), and
`hard_rules.py` (HR02/HR04 conditions).

Files touched: CSV 08/09/11 + Excel sheets `4_Formularz_6_krokow`/
`5_Punktacja_formularza`/`5B_Twarde_reguly` (synced via a one-off
openpyxl script, not by hand — direct cell edits by row-index lookup on
`answer_code_AI`); `doc_processor.py`, `scenario_selector.py`,
`doc_selector.py`, `hard_rules.py`, `app.py`. Verified: `k1_code` for
`wyrok.pdf` is now `K1_WYROK_ZAOCZNY_SPOLKA`, CSV 08 label resolves to
"Wyrok zaoczny (spółka)", `resolve_doc_type()` still resolves to
`NAKAZ_SPOLKA` (scenario text unchanged), HR02 fires correctly for
`K1_WYROK_ZAOCZNY_CZLONEK_ZARZADU` + `K2_DAYS_LEFT_0_3`, full regression
suite still green.
