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

## Third bug (15.07.2026): missing splitter-level rule — no page boundary at all

User re-tested `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf`, a 20-page
komornik bundle that *also* contains a wyrok zaoczny among the bailiff
documents (str.5-6). `doc_classifier.py`'s 07.07.2026 early-return (the
fix above) only runs on an *already-merged page segment* — it has no
effect if the wyrok's own pages never became a distinct segment in the
first place. That's exactly what was happening: `doc_splitter.py` (the
page-boundary layer, upstream of the classifier) had **zero** awareness
of wyrok-zaoczny pages — no rule anywhere in `_classify_page_segment()`
matched "WYROK...ZAOCZNY"/"W IMIENIU RZECZYPOSPOLITEJ POLSKIEJ". The
wyrok's title page fell through every rule to `None` (unrecognized) and
was silently absorbed as a "continuation" of the neighboring bailiff
document — str.5-6 (wyrok) merged into str.1-4's
`komornik_wszczecie_egzekucji` segment into one wrong str.1-6 block.

**Same recurring lesson as the first two bugs on this document type**:
the classifier eventually learns to recognize a type, but a sibling layer
upstream (here, the splitter) doesn't automatically inherit that
knowledge — each layer that makes a type-sensitive decision needs its own
explicit rule, even when the signal (same two phrases) is identical.

**Fix**: added a new splitter rule (Reguła 1a', `doc_splitter.py`, placed
right after Reguła 1a "pismo procesowe" and before Reguła 1 "art. 299 →
pozew" — must precede Reguła 1 because a wyrok's own uzasadnienie could
cite art. 299 KSH) mirroring the classifier's signal exactly: "WYROK" +
"ZAOCZN" + "W IMIENIU RZECZYPOSPOLITEJ POLSKIEJ" in the first ~800 chars
→ kind `wyrok_zaoczny`. Continuation pages of the wyrok (its own
uzasadnienie, no "W IMIENIU..." on their own) risked the same problem
Krok -3 already solves for `pismo_procesowe` (a continuation page that
cites art. 299 could get mis-caught by Reguła 1 as "pozew") — generalized
Krok -3's merge-target set to `{"pismo_procesowe", "wyrok_zaoczny"}`
instead of a single hardcoded string. Added `wyrok_zaoczny` to
`_KOMORNIK_MERGE_TARGETS` (Krok -2, so a stray generic-fallback
continuation page reattaches to the wyrok) but deliberately **not** to
`_komornik_kinds` (Krok -1's art. 299 chain-protection set) — the wyrok
is a separate document being enforced by the surrounding bailiff letters,
the same reasoning that already excludes `wniosek_egzekucyjny` from that
set.

**Second, independent bug found in the same file**: str.11-14 was also
wrongly merged (two genuinely different bailiff documents — zajęcie
rachunku bankowego then zajęcie wierzytelności — collapsed into one
`komornik_zajecie_rachunku` segment). Root cause had nothing to do with
the wyrok: str.13's own letterhead ("Kaemornik Sądowy"/"Kancelaria
Kuojnomicza") was too OCR-garbled to pass Reguła 1d's strict letterhead
gate, so its real title ("ZAWIADOMIENIE O ZAJĘCIU WIE**FR** YTELNOŚCI" —
a genuine character-substitution OCR error, "RZ"→"FR", not just a stray
space) never even got compared against `_KOMORNIK_TITLES`. First attempt
at a fix (drop the letterhead gate entirely, match titles unconditionally)
caused a **real regression**: str.8, a genuine continuation/pouczenie
page with no letterhead of its own, has the near-universal art. 767
skarga-deadline boilerplate paragraph in its body, which then falsely
matched the `komornik_skarga` title pattern — the exact failure mode the
letterhead gate was *already* protecting against
(see [[project_komornik_boilerplate_deadlines]]). Caught by re-running the
diagnostic on the same cached OCR text before moving on, not by regression
suite (this exact page combination isn't in the suite). Final fix:
narrowed instead of removed the gate — added a second, narrower signal
("SYGN" present in the first 700 chars, empirically present on every
document-start page in this file and absent from every continuation page)
that *also* permits attempting the specific-title match, but the generic
`pismo_komornicze` fallback (used when no specific title matches) still
requires the original clean letterhead — so a page with "SYGN" but no
letterhead and no title match correctly falls through to later rules
instead of being force-classified as a bailiff letter. Also tightened the
`komornik_zajecie_wierzytelnosci` pattern itself to match on the
"YTELNOŚCI" suffix (unique to "wierzytelności", no other common legal
word ends that way) within 25 chars of "ZAJĘCI[EU]", instead of requiring
the corrupted "WIE...RZ" prefix to read cleanly.

**Verified**: `doc_splitter.detect_documents_by_pages()` on the real
file's cached OCR text now returns exactly 8 segments matching page
ranges [1-4][5-6][7-8][9-10][11-12][13-14][15-16][17-20] — the exact
boundaries the user confirmed by hand. Full regression suite re-run after
both fixes (see `tools/regression_test.py` output from 15.07.2026 in
CLAUDE.md) — see that log for pass/fail status on all previously-known
files.
