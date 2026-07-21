# Plan: poprawki graficzne i teksty CTA/disclaimer (KRS Guard)

## Context
Po redesignie z 16.07 użytkownik zgłosił (zrzuty obraz1–4) cztery mankamenty
wizualne/tekstowe kalkulatora:
1. **Ikony** to emoji (🖨 📄 🔒 📌 ✏️ ℹ️ ⚠️ …) — wyglądają nieprofesjonalnie,
   nie pasują do prawnego charakteru. Dodatkowo **tło pomarańczowych ostrzeżeń**
   ma być zmienione na odpowiedni odcień niebieskiego, spójny z całością.
2. **Nazwy kroków** (nagłówki „KROK N" + tytuł) są zbyt małe (obraz3).
3. **Box CTA** na końcu raportu jest niemal czarny — wygląda jak „żałobna
   klepsydra" (obraz4). Ponadto treść CTA: pierwsze zdanie mówi o ryzyku, drugie
   o Audycie 48h, ale **brak sensownego przejścia** między nimi (użytkownik może
   być zdezorientowany). Ostatnie zdanie — disclaimer „Ocena orientacyjna, nie
   stanowi porady prawnej" — **brzmi słabo i jest za małe**, łatwo je przeoczyć.

Cel: spójna, profesjonalna, „prawnicza" szata; czytelne kroki; box CTA jako
wyróżniona rekomendacja (nie nagrobek) z logicznym przejściem do Audytu 48h;
mocniejszy, wyraźniejszy disclaimer.

**Decyzje użytkownika (AskUserQuestion):**
- Box CTA → **jasny niebieski panel** (jasne tło, granatowy tekst, granatowy
  akcent z lewej).
- Ikony → **profesjonalne, monochromatyczne**: Material Symbols w widgetach
  Streamlit + dopasowane inline-SVG w banerach HTML (granat/grafit).

⚠️ Zadanie dotyka **4 plików** i **>80 linii** (m.in. ~30 miejsc z ikonami) —
jeśli rozmowa zostanie przerwana limitem, zrobię checkpoint (co zrobione / co
zostaje).

## Ustalenia z eksploracji (fakty, file:line)
- **Ikony**: cała ~30-pozycyjna inwentaryzacja emoji w `app.py` (m.in. 207 ℹ️
  expander „Dlaczego pytamy?", 274/280 🖨 OCR, 289 ⚠️, 293/542 ✏️, 300 📄,
  531 📄 nagłówek tabeli, 593 🔒, 603 📋, 763 📌, 776 📎, 1390 📄 toggle,
  1393 ⬇, 1404 🔄, 1410 🔧, 908/916/1356 ⚠️ w `st.warning`). Streamlit 1.45.1
  **wspiera Material Symbols** (`icon=` w `st.info/warning/success/error/button/
  expander`; `validate_material_icon` obecne). `st.toggle` NIE ma `icon=` →
  `:material/...:` inline w labelu. Banery „ręcznie" rysowane przez
  `st.markdown` (HTML div) NIE przyjmą Material w tekście → tam inline-SVG.
- **Kolory ostrzeżeń**: część to natywne `st.info/st.warning` (domyślny motyw,
  zero CSS override — `app.py:666-736` nie stylizuje `stAlert`); część to
  ręczne divy z hardkodowanym hex: OCR żółty `#fff8e1/#f9a825` (286-295),
  ochrona danych żółty `#fffbeb/#fbbf24` (591-598), „Zanim wgrasz" już niebieski
  `#eff6ff/#93c5fd` (760-773), cyfrowy zielony `#e8f5e9/#43a047` (297-303).
- **Nagłówki kroków** — `section_header()` `app.py:739-751`; CSS w bloku
  centralnym: `.kg-step-eyebrow` `0.72rem` (701-713), `.kg-step-title`
  **`1.28rem`** (714-721) = „za małe". Auto-anchor 🔗 przy tytule to dodatek
  Streamlита do nagłówków.
- **Box CTA + disclaimer** — `report_builder.py`: HTML `.kg-report-cta` bg
  `var(--ink)` `#0f1b2d` (155-156), `.kg-report-footer` `0.76rem` `ink_muted`
  (157-158); PDF ten sam box `ink` (233/295) i footer `7.6pt` (235-236/307).
  Renderowane z pól `output["cta"]` / `output["disclaimer"]`.
- **Teksty CTA/disclaimer są HARDKODOWANE** (nie CSV) → edycja tylko w Pythonie,
  bez synchronizacji CSV↔Excel: disclaimer `text_builder.py:67`
  (`_LEGAL_DISCLAIMER`); 5 wariantów CTA `text_builder.py:70-97`
  (`_CTA_PERSONAL/_COMPANY/_UNKNOWN/_PISMO_PROCESOWE/_ZUS`, wybór
  `_cta_for_doc_type` 105-120). (Body „Co teraz warto zrobić" JEST z CSV
  — nie ruszamy.)

## Zmiany

### A. Tokeny (`branding.py`) — jedno źródło kolorów/ikon
- Dodać tokeny niebieskiego „notice/info" (jasne tło + obwódka + akcent) i
  parę na box CTA (jasnoniebieskie tło `~#eaf1f8`, granatowy tekst=`ink`,
  akcent=`navy`). Reużyć w `app.py` i `report_builder.py` (spójność UI↔raport).
- Dodać mały zestaw inline-SVG ikon monochromatycznych (helper `icon_svg(name,
  color, size)` z kilkoma `path` — np. document, scan, shield/lock, info,
  push_pin/marker) tą samą techniką co logo (`str.format` + `unsafe_allow_html`).
  Do banerów HTML w `app.py`.

### B. `app.py` — CSS + ikony
1. **Nagłówki kroków większe**: `.kg-step-title` `1.28rem → ~1.6rem`;
   `.kg-step-eyebrow` `0.72rem → ~0.78rem` (+ nieco paddingu). Ukryć auto-anchor
   nagłówka (CSS `.kg-step-title a{display:none}` / selektor anchora Streamlit).
2. **Ostrzeżenia pomarańczowe → niebieskie**: ręczne divy (286-295, 591-598)
   przemalować na tokeny niebieskie z `branding.py`; zielony baner cyfrowy (300)
   zostaje (pozytywny sygnał „dane wiarygodne", semantycznie ok). Natywne
   `st.warning` — dodać w bloku centralnym CSS override na spokojny niebieski
   tint (weryfikacja selektora `stAlertContainer`/`:has()` w Streamlit 1.45 —
   skill developing-with-streamlit); `st.error`/pigułki ryzyka bez zmian
   (zachować sygnał wagi).
3. **Ikony emoji → profesjonalne**: w widgetach natywnych `icon=":material/…"`
   (np. expander „Dlaczego pytamy?" `:material/help`, „Popraw dane odczytu"
   `:material/edit`, „Zestawienie" `:material/description`, „Wgraj" `:material/
   upload_file`, „Wyczyść" `:material/refresh`, „Panel techniczny"
   `:material/build`, `st.warning` AI-status `:material/warning`); toggle
   „Zobacz pełny raport" — `:material/description` inline w labelu;
   `download_button` PDF — `icon=":material/download"`. Banery HTML — `icon_svg`
   z `branding.py`. Dobór ikon pod prawny charakter (dokument/tarcza/pieczęć).

### C. `report_builder.py` — box CTA + disclaimer (HTML **i** PDF)
1. **Box CTA**: `.kg-report-cta` bg `#0f1b2d → jasnoniebieski token` +
   `border-left: 4px solid var(--navy)` + tekst `color: var(--ink)` (granat)
   zamiast białego (HTML 155-156). PDF analogicznie (233-234 styl tekstu na
   `ink`; 295 `BACKGROUND` na jasnoniebieski + lewy akcent przez komórkę/
   `LINEBEFORE`). Ten sam token co UI.
2. **Disclaimer wyraźniejszy**: `.kg-report-footer` `0.76rem → ~0.9rem`, kolor
   z `ink_muted` na ciemniejszy/`ink`, mocniejszy lead („**Zastrzeżenie:** …").
   PDF: `7.6pt → ~9pt`, ciemniejszy (235-236/307).

### D. `text_builder.py` — treść CTA + disclaimer
1. **Przejście w CTA** (wszystkie 5 wariantów, 70-97): dodać zdanie-most między
   ryzykiem a Audytem 48h. Wzorzec dla `_CTA_COMPANY` (obraz4):
   „…skieruje roszczenie bezpośrednio do Ciebie z art. 299 KSH. **Zanim to
   nastąpi, warto rzetelnie sprawdzić, czy i jak można się obronić — i temu
   właśnie służy Audyt 48h:** pisemna opinia prawna sporządzona przez radcę
   prawnego (nie automatyczna ocena), na której możesz oprzeć swoją decyzję."
   Analogiczne mostki dla pozostałych wariantów (finalne brzmienie do akceptacji
   przy wdrożeniu).
2. **Disclaimer mocniejszy** (67): np. „**Zastrzeżenie:** Powyższa ocena ma
   charakter orientacyjny i nie stanowi porady prawnej. Wiążącą opinię może
   wydać wyłącznie radca prawny lub adwokat po analizie pełnej dokumentacji."
   (Uwaga: `sanitize_check()` w text_builder — pilnować, by nowy tekst nie
   zawierał kodów technicznych; zwykły tekst prawny jest bezpieczny.)

## Wybór agentów do wdrożenia (zgodnie z prośbą użytkownika)
- **skill `developing-with-streamlit`** — potwierdzić składnię `icon=`/`:material/`
  per widget i selektor CSS do przemalowania `st.warning` w 1.45.1.
- **skill `frontend-design`** — kalibracja doboru ikon i odcieni (spójność,
  prawny charakter) przy edycji.
- Rdzeń edycji (spójne tokeny cross-file: `branding.py`↔`app.py`↔
  `report_builder.py`) robię sam, żeby nie rozjechać współdzielonych kolorów.
- **`agent-browser`** — żywa weryfikacja wizualna w przeglądarce (patrz niżej).

## Verification
1. `cd app && streamlit run app.py`; **agent-browser** — wgrać dokument (np.
   `nak.zap.3.pdf`), zrzuty: (a) nagłówki kroków wyraźnie większe; (b) banery
   dawniej pomarańczowe teraz niebieskie; (c) ikony renderują się jako
   monochromatyczne (Material + SVG), zero emoji; (d) toggle „Zobacz pełny
   raport" → box CTA jasnoniebieski z granatowym tekstem i lewym akcentem,
   disclaimer większy i z mocniejszym brzmieniem, przejście do Audytu 48h czyta
   się płynnie; brak błędów w konsoli.
2. **PDF**: pobrać przez `download_button`, wyrenderować stronę jako obraz —
   box CTA jasnoniebieski, disclaimer większy, polskie znaki poprawne (reportlab
   + DejaVu bez zmian).
3. **Regresja**: `tools/regression_test.py` NIE jest wymagana — zmiany są czysto
   wizualne/tekstowe, nie dotykają `doc_*.py`/`ai_extractor.py` ani logiki
   ekstrakcji/wyboru dokumentu (sprawdza main_type/kwotę/termin/bramkę, nie
   teksty CTA/disclaimer). Uruchomić tylko, jeśli coś w text_builder wpłynie na
   `full_text` w sposób łapany przez `sanitize_check` (szybki self-check).
4. Commit + push (`main`), aktualizacja CLAUDE.md + `memory/` (redesign) w tej
   samej sesji.
