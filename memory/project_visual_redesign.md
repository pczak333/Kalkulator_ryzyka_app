---
name: project-visual-redesign
description: "16.07.2026 — visual redesign of the Streamlit calculator (design token system, original SVG mark for the calculator — explicitly NOT the law firm's logo, section headers replacing plain st.subheader) plus (planned) a PDF/HTML report replacing the inline result block. Faza A (visual redesign) complete and live-verified; Faza B (report) not yet started."
metadata:
  node_type: memory
  type: project
  originSessionId: 935a6952-4b75-47de-a4be-ad7f1b62d18b
---

## What prompted this

User: the calculator works but looks like a generic Streamlit form — steps
separated only by `st.divider()`, colors picked ad hoc per element, and the
final risk assessment renders as one long markdown block directly under the
form. Ask: professional, trustworthy visual design with clearly separated
blocks, and the final result should NOT display inline — instead downloadable/
viewable as a polished PDF/HTML document. Full plan:
`plany/redesign-graficzny-i-raport-pdf-snug-goose.md`.

## Two explicit user corrections mid-planning (important, don't repeat)

1. Asked to pick technical decisions myself ("nie jestem techniczny, sam
   wybierz") after I tried to ask clarifying questions via AskUserQuestion —
   **don't ask this user technical implementation-detail questions**, make
   the call and explain the reasoning. Decided: WeasyPrint for PDF (single
   HTML/CSS template for both preview and PDF), teaser+buttons instead of
   full inline text.
2. Rejected my first attempt to reuse the *law firm's* existing "KRS Guard"
   logo files (found outside the repo at
   `...\KALKULATOR GUARD\KANCELARIA_PRS\Ogólne\loga\`) — explicit correction:
   **the calculator needs its OWN, separate logo, distinct from the law
   firm's business branding, and it must not be an emoji standing in for a
   logo** (previously `page_icon="⚖️"`). This is the one to remember for any
   future branding work on this project — KRS Guard the law firm and "the
   calculator" are two distinct visual identities in this user's mind, even
   though the calculator's *text* branding ("KRS Guard — Kalkulator Ryzyka
   Prawnego") stays as-is; only the *mark/logo* had to be original.

## Design decisions (Faza A)

New `app/branding.py` — single source of truth for both `app.py` and the
future `report_builder.py` (Faza B): `TOKENS` dict (colors, radii, shadow,
3-role font stack: serif display / system-sans body / mono for data),
`css_variables()` (renders `:root{--x:y}` block), and the logo itself as
inline SVG functions (`logo_svg`, `logo_svg_light_on_dark`,
`logo_svg_dark_on_light`) — not an external image file, so it's crisp at any
size and has zero dependency on files outside the repo.

**The mark**: an abstracted shield silhouette with three ascending bars
inside (like a small rising bar chart) — deliberately ties to the
calculator's own 4-tier risk scale (low→medium→high→urgent) rather than
being generic clipart (explicitly avoided literal scales-of-justice
iconography — too on-the-nose/generic). Visually verified via a standalone
HTML screenshot before committing to the shape (both large size and 32px
favicon scale) — reads cleanly as "shield + graph" at both sizes.

**Risk color scale**: replaced the old, semantically-arbitrary
green/orange/red/**purple** (`RISK_LOW`..`RISK_URGENT`) with a genuine
severity *gradient*: green → amber → red → dark crimson (`#1f7a4d` /
`#b5750a` / `#a83232` / `#6b1220`). The old purple for URGENT didn't
intuitively read as "worse than red" to a viewer — the new scale does, by
construction. `RISK_ICONS` (the old 🟢🟡🔴🚨 emoji dict) was deleted entirely
— `colored_risk_box()` is now a pill badge (light tinted background + bold
colored text, `compact` param added for reuse in Faza B's teaser) with no
emoji at all.

**Step headers**: `section_header(number, title)` replaces
`st.subheader("Krok N — ...")` — renders a "KROK N" eyebrow pill + a title
with a colored left accent bar. Numbering is legitimate here per the
`frontend-design` skill's own caveat (only use numbered markers when the
content is a real sequence) — these genuinely are ordered form steps the
client must complete top to bottom.

**Deliberate scope-narrowing, not in the original plan**: the plan called
for wrapping each Krok step in `st.container(border=True)` for real bordered
cards. Decided against it during implementation — this file has deep,
multi-level conditional logic (the art. 299 gate, K1-K7 branching, EPU
handling), and wrapping each step would mean re-indenting large blocks of
that logic purely for a cosmetic change, a real risk of introducing a bug
for zero functional benefit. `section_header()` achieves the same "clearly
separated blocks" goal (eyebrow tag + accent + spacing) with a **purely
additive** change — zero lines of existing logic touched, zero
re-indentation. Worth remembering as the general principle for any future
touch-up to this file: prefer additive CSS/helper-function changes over
restructuring control flow, even when the "more correct" Streamlit-native
widget would be a container wrap.

## Tooling gotcha discovered during verification (not an app bug)

`agent-browser click @ref` / `find text ... click` does **not** register a
selection on this app's native `st.radio` options (BaseWeb-based Streamlit
component). Diagnosed via `git stash` (confirmed identical failure on the
unmodified `app.py` — pre-existing, not caused by this session's CSS).
Root cause: the snapshot's `radio` role ref points at the actual `<input
type="radio">`, which BaseWeb renders as a zero-size, invisible element
(`is visible: false`, `0×0` box) — the *visible* clickable surface is the
wrapping `<label>` containing a custom-styled circle div + the option text
in a nested `stMarkdownContainer > p`. Real mouse clicks in a real browser
land on the label and work fine (label wraps its input, so any click inside
it fires natively) — it's specifically CDP-driven ref/selector clicks that
target the wrong (invisible) descendant.

**Working fix**: dispatch synthetic `mousedown`/`mouseup`/`click`
`MouseEvent`s directly on the matched `<label>` via `agent-browser eval`,
matched by `label.innerText.trim() === exact option text`. Reusable snippet
now documented in CLAUDE.md's `app.py` entry (16.07.2026 note) — grep there
before re-deriving this next time a live test needs to fill radio buttons.
`st.button`/`st.download_button` clicks work fine with plain
`agent-browser click @ref` — this issue is specific to `st.radio`.

## Verified (Faza A)

Live browser test (agent-browser): header banner + logo render correctly on
the navy background, "KROK N" pills + accented titles render on every step,
primary button picks up the navy token color automatically (already matched
`config.toml`'s `primaryColor`), full form fill-through (using the
JS-dispatch workaround above) → submit → risk pill renders in the new
severity-gradient color (`RISK_URGENT` tested, showed dark crimson
correctly) with zero console errors. The underlying result *text* block is
still the old inline markdown at this point — untouched, confirms Faza A's
CSS/header/RISK_COLORS changes didn't regress the existing calculation
pipeline.

## Status / what's left

Faza A (visual redesign of the form) is complete, live-verified, not yet
committed at the time of writing this memory — check git status before
assuming this landed. Faza B (PDF/HTML report replacing the inline result
block, new `report_builder.py`, WeasyPrint dependency) has **not started
yet** — see the plan file for its scope. Update this memory (or add a
follow-up section) once Faza B lands; don't let this description go stale
claiming Faza B is done when it isn't.
