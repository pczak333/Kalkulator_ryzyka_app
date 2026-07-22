---
name: project-visual-redesign
description: "16.07.2026 — visual redesign of the Streamlit calculator (design token system, original SVG mark for the calculator — explicitly NOT the law firm's logo, section headers replacing plain st.subheader) plus a PDF/HTML report replacing the inline result block. Faza A/B/C complete and live-verified. Faza D (22.07.2026) replaced the shield+3-bars mark entirely with a hexagon badge + K monogram — read that section before assuming the mark is still the shield."
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

## Faza B: PDF/HTML report — architecture pivot after real local test failures

The plan called for ONE shared HTML+CSS template rendered two ways: a live
in-page preview and a WeasyPrint HTML→PDF conversion. That did not survive
contact with reality — three real technical blockers, found by actually
running each candidate locally and inspecting output, not by reasoning about
library capabilities in the abstract:

1. **WeasyPrint**: `pip install weasyprint` succeeds cleanly, but
   `import weasyprint` raises `OSError` trying to `dlopen` `libgobject-2.0`
   — it needs native Pango/Cairo/GDK-Pixbuf libraries Windows doesn't ship.
   Would work on Streamlit Cloud via `packages.txt` (Linux, apt-installable)
   but is **untestable on this dev machine** without a large GTK3 runtime
   install.
2. **xhtml2pdf** (pure-Python alternative considered next): installs and
   *runs* without error, but its `@font-face`/font-registration handling is
   unreliable for this use case — tried three approaches (`@font-face` with
   a bare Windows path, `@font-face` with a `file:///` URI, direct
   `reportlab.pdfmetrics.registerFont` before calling `pisa.CreatePDF`) and
   **all three** produced PDFs where Polish diacritics (ą/ć/ę/ł/ń/ó/ś/ź/ż)
   rendered as black `.notdef` boxes. Caught by actually **rendering the PDF
   page to a PNG and looking at it** — the first two attempts were checked
   only via `pdfplumber` text extraction (`ąćęłńóśźż` → `nnnnn?nnn`), which
   is a *different* failure mode (ToUnicode CMap issue) and could have been
   misdiagnosed as "just an extraction bug" if I'd stopped there. Rendering
   to an image and looking is the only way to know if glyphs are *actually*
   missing versus just mis-extracted — worth remembering as a general
   verification technique for any future PDF work in this repo.
3. **Raw `reportlab`** with a directly-registered TTF, bypassing xhtml2pdf's
   CSS layer entirely: renders correctly *if and only if* the font has full
   Latin Extended-A coverage. Confirmed this two ways: Windows' system
   Arial worked (not redistributable, Windows-only, unusable for a real
   fix); the `Vera.ttf` bundled inside `reportlab`'s own package did **not**
   work (same black-box failure — Bitstream Vera predates DejaVu's Extended
   Latin coverage). Solution: bundle **DejaVu Sans/Serif** (regular + bold)
   directly in the repo at `app/assets/fonts/*.ttf`, sourced by copying them
   out of the already-installed `matplotlib` package (which ships DejaVu as
   its default font) — not a new runtime dependency, just a one-time asset
   copy, license file included (`LICENSE.txt`, Bitstream-derived, explicitly
   permits redistribution/embedding).

**Resulting architecture** (`app/report_builder.py`): two independent
renderers, not one shared template — `build_report_html()` (plain HTML+CSS
string, used for the in-page preview via `st.components.v1.html`) and
`build_report_pdf()` (reportlab Platypus flowables — Table-based header with
a natively-drawn logo `Drawing`, `Paragraph`s with registered DejaVu fonts).
Both consume the *same* `text_builder.build()` output dict and the *same*
`branding.TOKENS`/`RISK_COLORS`/`RISK_BG`, so they look like one visual
identity despite separate rendering code. `_body_paragraphs()` extracts
paragraphs from the *already-composed* `output["full_text"]` (strips the
`### heading`, the CTA paragraph, and the disclaimer paragraph — those are
rendered separately, highlighted) instead of re-deriving section-assembly
logic from `text_builder.py` — avoids duplicating that logic, and means this
module needed **zero changes to `text_builder.py`** to ship. `markup_bold()`
(public, not `_markup`) converts `**bold**` markdown to `<b>` tags — reused
in `app.py` for the on-page teaser, which needed it after a live-test catch
(see below).

**Real bug caught by live testing** (not the architecture pivot — this one
was in my own `app.py` wiring): the teaser paragraph is injected via
`st.markdown(f"<p>...</p>", unsafe_allow_html=True)`. `output["lead"]`
contains markdown `**bold**` spans, but raw-HTML injection doesn't run
Streamlit's markdown parser — the literal asterisks showed up on screen
(`Dokument: **Nakaz zapłaty (członek zarządu)**.`). Fixed by piping the
teaser through `report_builder.markup_bold()` before injection. Only found
by looking at an actual screenshot after a real form submission — this is
exactly the kind of thing that "the code compiles and the function returns
without error" would never catch.

**Verified end-to-end**, twice — once with synthetic data (standalone script
calling `report_builder` functions directly, checked by rendering the PDF to
a PNG and eyeballing it), and once through the **actual live app** with a
real submitted form (agent-browser, JS-dispatch workaround for `st.radio`,
see above): risk pill/teaser render correctly with bold applied, the
"Zobacz pełny raport" toggle embeds the HTML report inline with matching
styling, and the "Pobierz jako PDF" button correctly serves bytes through
Streamlit's own `/media/*.pdf` endpoint (confirmed by fetching that URL
directly and rendering the result — correct real scenario text, correct
Polish characters, correct CTA box). One tooling-only hiccup: `agent-browser
download` returned "Download was canceled" — Streamlit's download button
uses a fetch/blob mechanism to its media endpoint rather than a plain
`<a href download>`, which that specific CDP command doesn't handle;
fetching the URL directly (visible in
`performance.getEntriesByType('resource')` after the click) sidesteps it.
Not an application bug.

## Status: both phases complete

Faza A and Faza B are both implemented and live-verified. `reportlab` added
to `app/requirements.txt` — pure-Python, no system dependencies, so (unlike
the originally-planned WeasyPrint) **no `packages.txt` is needed** for
Streamlit Cloud deployment; this is a simplification versus the original
plan, not a follow-up task. Check git status/CLAUDE.md before assuming
this is pushed to `origin/etap2` — write this memory before the commit step.

## Faza C — poprawki graficzne + teksty CTA/disclaimer (21.07.2026)

Cztery zgłoszenia użytkownika (obraz1-4) po redesignie:
1. **Emoji nieprofesjonalne** → zastąpione monochromatycznymi: Material Symbols
   `icon=":material/..."` w widgetach natywnych (expander/button/download_button/
   info/warning), `branding.icon_svg()` (nowy zestaw SVG + `_ICON_PATHS`) w
   banerach HTML `st.markdown` (te NIE przyjmują Material). `st.toggle` nie ma
   `icon=` → `:material/description:` inline w labelu.
2. **Ostrzeżenia pomarańczowe → niebieskie**: banery ręczne (divy `#fff8e1`/
   `#fffbeb`) na nowe tokeny `notice_bg`/`notice_border` (branding.py) + lewy
   granatowy akcent. Natywne `st.warning` NIE przemalowywane globalnie —
   Streamlit 1.45.1 nie ma markera rodzaju alertu w DOM (kind→BaseWeb emotion,
   brak data-kind), więc czysty selektor „tylko warning" nie istnieje; a
   pomarańczowe ze zrzutów to i tak divy ręczne (pełna kontrola).
3. **Nagłówki kroków większe**: `.kg-step-title` 1.28→1.65rem, eyebrow
   0.72→0.8rem; ukryta auto-kotwica 🔗 Streamlita (`[data-testid=
   stHeaderActionElements]{display:none}`).
4. **Box CTA „żałobna klepsydra" (czarny) → jasnoniebieski panel** (decyzja
   użytkownika: AskUserQuestion, opcja „jasny niebieski"): `report_builder.py`
   HTML+PDF, tło `var(--ink)`→`notice_bg`, tekst biały→granat, lewy akcent.
   **Disclaimer** większy (0.76→0.9rem / 7.6→9pt), ciemniejszy, pogrubiony lead
   „**Zastrzeżenie:**", mocniejsza treść (`text_builder._LEGAL_DISCLAIMER`).
   **5 wariantów CTA** dostało zdanie-most ryzyko→Audyt 48h (dawniej brak
   przejścia). Teksty CTA/disclaimer HARDKODOWANE w text_builder.py (NIE CSV).

**Weryfikacja**: żywy test agent-browser — wejście (nagłówki większe bez
kotwicy, banery niebieskie z SVG, Material jako glify, DOM bez dosłownego
`:material/`) + raport otwarty jako wyrenderowany plik HTML/PDF (box CTA
niebieski, disclaimer większy, polskie znaki OK). PUŁAPKI NARZĘDZIOWE (nie app):
`agent-browser upload` na `st.file_uploader` → „AxiosError: Network Error" (CDP
omija XHR-upload Streamlita, obejście: render raportu do pliku); Chrome dla
agent-browser wymaga `agent-browser install` per komputer (świeży `open`
hangował, aż doinstalowano). Regresja pipeline NIE wymagana — zero zmian w
doc_*.py/ai_extractor/logice ekstrakcji.

## Faza D — nowy znak: plakietka z monogramem K (22.07.2026)

Użytkownik poprosił o propozycje ZNAKU GRAFICZNEGO na nowo — nie kosmetykę
istniejącego, tylko przegląd alternatyw. Proces w dwóch turach, obie jako
galerie Artifact (SVG budowany ręcznie tymi samymi technikami co
`branding.py` — `<symbol>`/`<use>` + CSS custom properties do przebarwiania —
żeby wybrany kierunek dało się bez tarcia przenieść do kodu produkcyjnego):

**Tura 1** — 6 koncepcji szeroko: 2 rozwijające tarczę+słupki (tarcza
geometryczna faceted; tarcza ze wstęgą wznoszącą zamiast osobnych słupków) +
4 nowe kierunki (wskaźnik/miernik ryzyka — kolorowy pierścień + wskazówka;
wznoszący chevron — najbardziej minimalistyczny; **plakietka-monogram K**;
tarcza z dziurką od klucza). Użytkownik wybrał plakietkę-monogram, ale z
istotnym zastrzeżeniem: pierwsza wersja budowała literę K z 3 kresek
nawiązujących do 4-stopniowej skali ryzyka (ten sam motyw co tarcza+słupki) —
**to znaczenie jest niewidoczne dla klienta końcowego**, widzi po prostu
białą literę. **Lekcja ogólna (zapamiętać na przyszłość dla każdego przyszłego
projektowania znaku/ikony w tym repo): nie zaszywać w znaku narracji, która
wymaga wyjaśnienia, żeby ktokolwiek ją odczytał — oceniać kształt wyłącznie
na tym, co faktycznie widać, nigdy na zamierzonym-ale-niewidocznym sensie.**

**Tura 2** — 6 wariantów samego monogramu, tym razem BEZ próby zaszycia
skali ryzyka, dwie niezależne osie: krój litery (monoline / blokowe-solidne /
negatywowe-wycięte / serifowe nawiązujące do Georgia) × kształt plakietki
(sześciokąt / koło / zaokrąglony kwadrat), z kartami skonstruowanymi tak, by
każda para kart izolowała jedną zmienną naraz (kontrolowane porównanie, nie
przypadkowa siatka). Wariant negatywowy w mockupie użył PRAWDZIWEJ maski SVG
(`<mask>`) — dopiero przy wdrożeniu do produkcji okazało się to zbędne (patrz
niżej).

**Wybrany finalnie**: wariant negatywowy (K jako wycięcie w w pełni
wypełnionej sześciokątnej plakietce, czyta się jak pieczęć/stempel).

**Wdrożenie do kodu** (`app/branding.py`, `tools/generate_favicon.py`,
`app/report_builder.py`): kluczowe uproszczenie odkryte przy przejściu z
mockupu do produkcji — istniejąca architektura kolorów (`logo_svg(shield,
bars)`, dwa parametry: kolor konturu i kolor "akcentu") generalizuje się
idealnie na nowy znak BEZ potrzeby prawdziwej maski. Skoro plakietka jest
zawsze pokazywana na jednolitym tle (granatowy nagłówek appki / biały raport
PDF-HTML — jedyne dwa konteksty użycia), pomalowanie litery K kolorem
identycznym z tłem daje efekt wizualnie nieodróżnialny od prawdziwego
wycięcia, przy zerowej dodatkowej złożoności w PIL (`generate_favicon.py`)
i reportlab (`_logo_drawing()`) — obie te technologie NIE mają wygodnego
odpowiednika SVG `<mask>`, więc unikanie go tu było realną oszczędnością, nie
tylko uproszczeniem kosmetycznym. Litera K = trzon (`rect` zaokrąglony) +
2 ramiona (`polygon`), wypełnione parametrem `bars` — dokładnie tym samym
parametrem, który wcześniej malował 3 słupki. Sześciokątny kontur (proste
odcinki) zastąpił krzywą Beziera tarczy — DODATKOWA korzyść uboczna: `PIL`/
`reportlab` nie muszą już APROKSYMOWAĆ konturu wielokątem (jak wcześniej dla
tarczy), bo sześciokąt już jest wielokątem — te same współrzędne dosłownie w
SVG, PNG i PDF.

**Zweryfikowane**: `python tools/generate_favicon.py` (favicon.png otwarty i
obejrzany — czytelne, dobrze wykadrowane K); `build_report_pdf()`/
`build_report_html()` na syntetycznych danych — bez błędów (PDF ~65KB);
`renderPM` do PNG NIE zadziałał na tym komputerze (brak `rlPyCairo`, ten sam
znany brak jak przy WeasyPrint — patrz Faza B) więc PDF nie został
wyrenderowany do obrazu bezpośrednio, ale współrzędne są dosłownie te same co
w już-zweryfikowanym PNG faviconu; żywy test w przeglądarce
(`streamlit run app.py`, zrzut ekranu przez `mcp__claude-in-chrome`) —
nagłówek renderuje białą plakietkę z granatowym K na granatowym tle
poprawnie, bez błędów.

**Poprawka proporcji (22.07.2026, ta sama sesja co wdrożenie)**: użytkownik
zgłosił (zrzuty `obraz1.png`/`obraz2.png` z folderu testy), że plakietka w
nagłówku APPKI wygląda na małą/nieproporcjonalną, podczas gdy w nagłówku
RAPORTU proporcje są dobre. Diagnoza: to nie błąd samego stosunku rozmiar
znaku:font tytułu (appka miała nawet nieco WYŻSZY stosunek niż raport,
50/24.8≈2.0 vs 38/20≈1.9) — przyczyna to długi, dwuliniowy podtytuł appki
("Bezpłatna, orientacyjna ocena ryzyka w sprawach...") vs krótki, jednoliniowy
podtytuł raportu ("Raport oceny ryzyka · wygenerowano..."), przez co cały
blok tekstu w appce jest znacznie wyższy, a znak dobrany do wysokości samego
tytułu wygląda na mały obok niego. Naprawione podniesieniem rozmiaru znaku w
`app.py`'s `.kg-header` z 50px na 66px (wyliczone tak, by znak zajmował
podobny % wysokości całego bloku tytuł+podtytuł co w raporcie, ~88%) +
drobna korekta paddingu/gap. Lekcja: przy porównywaniu proporcji znak:tekst
między dwoma layoutami liczy się wysokość CAŁEGO bloku tekstowego (wszystkie
linie po zawinięciu), nie tylko font-size pojedynczej linii tytułu.
