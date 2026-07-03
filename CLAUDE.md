# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**KRS Guard – Kalkulator Ryzyka Prawnego** is a legal risk calculator for cases involving liability of company board members (odpowiedzialność członków zarządu, art. 299 KSH). The calculator takes court/official documents and a user-filled form as input, and produces an oriented risk assessment with a call to action (typically recommending the paid "Audyt 48h" service).

The application is built and running. The stack is **Python + Streamlit**. Source code lives in `app/`.

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Production — Etap 1 (manual form). Deployed on share.streamlit.io for testers. Do NOT push Stage 2 code here until Stage 2 is fully tested. |
| `etap2` | Development — Stage 2 (document upload + OCR). Active development branch. |

Tag `v1.0-etap1` marks the stable Stage 1 checkpoint.

## Application structure

```
app/
├── app.py               # Streamlit entry point — UI, form flow, result display; w "Zestawieniu dokumentów w pliku" badge "WYMAGA REAKCJI" (01.07.2026) pokazuje się TYLKO przy dokumencie głównym (`doc is main`), nie przy dokumentach pomocniczych — wcześniej pojawiał się przy KAŻDYM dokumencie z wykrytym `deadline_days`, więc np. przedsądowe wezwanie do zapłaty (własny termin płatności w piśmie) dostawało badge mimo że w paczce dokumentem głównym i realnie wiążącym był nakaz zapłaty; spójne z resztą UI, gdzie sekcja "Termin na reakcję" już wcześniej pokazywała wyłącznie termin dokumentu głównego. (02.07.2026) `_DOC_TYPE_LABELS` ma nowy wpis `WNIOSEK_EGZEKUCYJNY`; panel techniczny "Segmentacja stron (doc_splitter)" dopisuje teraz do każdej linii finalnie sklasyfikowany typ (`splitter_segments[*]["final_type"]` z doc_processor.py) obok surowej etykiety splittera — cel: widoczna relacja między dwoma niezależnymi przebiegami klasyfikacji zamiast cichej, potencjalnie sprzecznej rozbieżności między panelami. (03.07.2026) Bramka art. 299 używa `is_company_name()` z doc_selector.py zamiast lokalnej listy `_SPOLKA_FORMS` (stara lista znała tylko skróty z kropkami — "Woodraft Home Spółka z ograniczoną odpowiedzialnością" nie była rozpoznawana jako spółka i bramka pytała o osobę fizyczną mimo pozwanej spółki). NOWA GAŁĄŹ dla dokumentów niesądowych: `_NON_LEGAL_MAIN_TYPES` = {DOKUMENT_NIEPRAWNY, DOKUMENT_NIEUSTALONY_PRAWNY, ODPIS_KRS, UMOWA_FAKTURA_KORESPONDENCJA, POTWIERDZENIE_DORECZENIA} — gdy dokument GŁÓWNY jest z tego zbioru (= w paczce nie było żadnego właściwego pisma), `_show_doc_summary()` zamiast tabeli sygnatura/kwota/termin pokazuje ostrzeżenie w duchu arkusza 6S (plik nie wygląda na pismo sądowe; prześlij właściwe pismo albo wypełnij formularz ręcznie — formularz POZOSTAJE dostępny, decyzja użytkownika 03.07.2026: ostrzeżenie, nie twarda blokada), ukrywa expander "Popraw dane odczytu", a po `process_files()` zeruje amount/k7_code/deadline_days/delivery_date/epu (kwota z przelewu/faktury to NIE kwota roszczenia; K1 spada na K1_INNE_NIE_WIEM → istniejąca ścieżka scenariusza 6S); `_DOC_TYPE_LABELS` uzupełnione o ODPIS_KRS/UMOWA_FAKTURA_KORESPONDENCJA/POTWIERDZENIE_DORECZENIA/DOKUMENT_NIEPRAWNY/DOKUMENT_NIEUSTALONY_PRAWNY (wcześniej UI pokazywało surowy tytuł "Odpis Krs" z .title()).
├── data_loader.py       # Reads CSV files from dane_wejściowe/csv/
├── scoring_engine.py    # Computes S = C+P+H+W, maps score to risk level
├── hard_rules.py        # Applies hard safety rules (5B_Twarde_reguly) that override score; HR10 (low OCR quality) + HR11 (pismo procesowe — incomplete docs) active in etap2; requires DOC_TYPE key in state dict
├── scenario_selector.py # Selects base scenario from 6_Biblioteka_scenariuszy
├── context_modules.py   # Collects contextual text snippets (6D–6U sheets)
├── text_builder.py      # Assembles final output text; sanitize_check() verifies no codes leak
│
│   ── Etap 2: document processing modules ──
├── doc_ingestion.py     # Reads uploaded file (PDF/DOCX/JPG/PNG) → list of PageDict per page
├── doc_ocr.py           # OCR kaskada: Azure DI (próg akceptacji 0.75, ten sam co etykieta jakości) → Claude Haiku (eskalacja ZAWSZE gdy Azure poniżej progu, nie tylko gdy tekst pusty — Haiku dokładniejszy dla zaburzonych układów dwukolumnowych/tabelarycznych) → Tesseract (prawdziwa ostatnia deska ratunku, tylko gdy brak klucza ANTHROPIC_API_KEY)
├── doc_extractor.py     # Regex extraction: EPU signals, delivery date, deadline (also word-form: "dwóch tygodni"), amount, addressee (header-only detection + post-correction); powód/pozwany extracted from parties_text only (before UZASADNIENIE/POUCZENIE — prevents grabbing parties from plea body); sygnatura rejects Km/KM prefix (bailiff reference) oraz prefiksy faktur FV/FA/F-VAT/FAKTURA (`_SYGNATURA_EXCLUDE_RE`, myląco pasują do wzorca sygnatury); new Nc-e pattern for long EPU case numbers; _KWOTA_PATTERNS ma dedykowany wzorzec "Wartość przedmiotu sporu" (najwyższy priorytet w pozwie) oraz "kwotę łączną" (nakaz) — oba warianty tolerują "l" zamiast "ł" (częsty artefakt OCR); `_find_deadline_near_keyword()` (01.07.2026) wybiera w oknie ±800 zn. wokół słowa kluczowego NAJBLIŻSZY (najwcześniejszy w oknie) wzorzec terminu z `_TERMIN_WRITTEN`, nie pierwszy wg kolejności listy (lista była posortowana wg długości terminu, 90 dni pierwsze — błędnie wygrywało z bliższym i poprawnym "w terminie dwóch tygodni", gdy okno obejmowało też sąsiedni fragment pouczenia o doręczeniu zagranicznym "w terminie trzech miesięcy"); to samo dla fallbacku "Przebieg 2" na całym tekście; `_POWOD_PATTERNS`/`_POZWANY_PATTERNS` (01.07.2026): dodano `\b` po rdzeniu "Pow[oó]d"/"Pozwan[yąa]" — bez granicy słowa dopasowywały się jako PREFIKS wewnątrz odmienionych form ("powod-**owi**", łapiąc resztę słowa + dalszy tekst zdania jako "nazwę"); `od\s+pozwanego` ma teraz negatywny lookahead na "na rzecz"; nowy wzorzec dla nakazu "zwykłego" (nie EPU): "wniesionego w dniu ... przez powoda [Nazwa]" (data cyfrowa lub słowna); **`_looks_like_party_name()`** (guard ogólny, zastępuje wykluczanie pojedynczych fraz jedna po drugiej) — prawdziwa nazwa strony zawsze zaczyna się wielką literą, formuły procesowe ("od pozwanego na rzecz powoda następujących kwot...", "zapłacić powodowi kwotę...") to fragmenty zdań pisane małą literą; ten guard wykrył i naprawił PRAWDZIWĄ przyczynę niespójności SPOLKA/CZLONEK_ZARZADU: fałszywie wyciągnięta "nazwa" pozwanego (fragment formuły, mała litera) nie zawierała formy spółkowej → post-korekcja adresata błędnie zmieniała "spolka" na "czlonek_zarzadu" — nie bug w doc_classifier.py
├── doc_classifier.py    # Classifies document type using keywords from CSV 07; bonus/penalty logic: +20 for "nakazuję pozwanemu" → NAKAZ, +20 for "wnosimy o"/"P O Z E W" → POZEW (bonus replaces old penalty — OCR-resilient); early return PISMO_PROCESOWE_SADOWE when UZASADNIENIE in head_500; no module-level CSV cache (always reads fresh). (02.07.2026) POZEW-bonus regex ma teraz wykluczenie: nie odpala się, gdy tekst zawiera "WNIOSEK O WSZCZĘCIE POSTĘPOWANIA EGZEKUCYJNEGO" — takie pismo (wierzyciel→komornik) też zawiera "wnoszę o" w petitum i błędnie podbijało EPU_POZEW_*/POZEW_* mimo że to nie jest żaden pozew do sądu. Bonus adresata (+15) ma teraz dodatkową gałąź `elif code in ("WNIOSEK_EGZEKUCYJNY", "UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC") and adresat in (...): base += 15` (ten sam wzorzec co już istniejący dla `PISMO_PROCESOWE_SADOWE`) — bez tego typy BEZ sufiksu `_SPOLKA`/`_CZLONEK_ZARZADU` w nazwie kodu systemowo przegrywały scoring z KAŻDYM konkurentem, który ten sufiks ma (np. `NAKAZ_SPOLKA`), niezależnie od dopasowania słów kluczowych — to była PRAWDZIWA przyczyna (odkryta 02.07.2026), przez którą segment wniosku egzekucyjnego/postanowienia o umorzeniu klasyfikował się jako `NAKAZ_SPOLKA` mimo poprawnej segmentacji stron. (03.07.2026) DOKUMENTY NIESĄDOWE: klasyfikator NIGDY nie mógł zwrócić "to nie jest dokument prawny" — `DOKUMENT_NIEPRAWNY` był (i celowo pozostaje) w `_EXCLUDE_TYPES` dla pętli scoringu, ale NIE było progu minimalnego: jedno słabe trafienie (np. "zarząd" z "Zarząd Cmentarzy Komunalnych" na przelewie bankowym) dawało ODPIS_KRS z pewnością 0.85 jako jedyny kandydat. Naprawione dwiema regułami po scoringu, opartymi o `raw_scores` (wynik czysto tekstowy słów kluczowych/sygnałów PRZED bonusami EPU/adresata — bonusy potrafią wynieść typ do zwycięstwa przy śladowych dowodach tekstowych): (1) `fields["czy_pismo_prawne"] is False` (werdykt AI z ai_extractor) I max raw < 4 → `DOKUMENT_NIEPRAWNY` 0.9 — koniunkcja chroni przed fałszywym alarmem AI na zgarbolonym OCR prawdziwego pisma; (2) backstop bez AI (pole None): max raw ≤ 1 i żadna formuła nakazu/pozwu nie odpaliła → `DOKUMENT_NIEUSTALONY_PRAWNY` 0.3; gdy AI orzekła czy_pismo_prawne=True, backstop NIE działa (segment może być zgarbolonym fragmentem prawdziwego pisma).
├── doc_splitter.py      # Segments multi-page PDF into logical documents via _classify_page_segment(); rule order (CRITICAL): Rule 0 (KOD [hash] — EPU form code, only on EPU header, never in uzasadnienie) → Rule 1 (art.299→pozew) → **Rule 1b (wniosek egzekucyjny) → Rule 1c (postanowienie umorzenie egzekucji) — nowe 02.07.2026, patrz niżej** → Rule 5a (P O Z E W before Rule 2!) → Rule 5a' (P O Z E W anywhere) → Rule 2d (UZASADNIENIE guard→None) → Rule 2/2b (NAKAZ at line-start (?m)^\s* within 200 chars — strict to avoid false-positives from pozew body text) → Rule 3 (wezwanie) → **Rule 4b (klauzula wykonalności→None, nowe 02.07.2026)** → Rule 4 (POUCZENIE→None) → Rule 5b (POZEW, full text) → Rule 6 (fallback); Rule 2c REMOVED; post-processing: Krok 0 upgrades unknown→pozew if [unknown→nakaz_noKOD→nakaz_KOD]; Krok 1 nuclear: scala CAŁY blok przed PIERWSZYM segmentem typu nakaz (niezależnie od tego, czy KOD został wykryty!) w jeden "pozew" — granica oparta na KOD okazała się krucha (różne silniki OCR różnie transkrybują linię "KOD [hash]"; gdy żaden segment nakazu nie ma wykrytego KOD, merge w ogóle się nie uruchamiał i cały pozew ginął w filtrze "unknown"). KEY INSIGHT: Lublin_pozew_nak._zap..pdf jest SKANOWANY — pdfplumber=0 tekstu, Azure DI robi OCR; str.4 (tabela dowodów) ma "Wezwanie do zapłaty" jako tytuł dowodu → Rule 3 odpala → segment wezwanie; nuclear merge to naprawia niezależnie od etykiety. `_is_evidence_citation()` (nowa funkcja, 01.07.2026): sprawdza ~40 znaków PRZED dopasowaniem pod kątem etykiety "Dowód:" lub wypunktowania ("-"/"–"/"—"/"•") — jeśli fraza jest cytowaniem dowodu/załącznika (np. w uzasadnieniu pozwu: "Dowód: wezwanie do zapłaty z dnia..." albo w liście "W załączeniu przedkładam: - wezwanie do zapłaty..." albo "Załączniki: - Tytuł wykonawczy [oryginał]"), NIE klasyfikuje strony jako osobny dokument. (02.07.2026) Guard uogólniony na WSZYSTKIE wzorce fallback Rule 6 (był tylko dla `wezwanie_zaplaty`) — bez tego "Tytuł wykonawczy [oryginał]" w liście załączników wniosku egzekucyjnego (patrz test `art299_pozew_nakaz_umorz._egzek..pdf` niżej) błędnie odcinało stronę jako osobny segment "komornik". PUŁAPKA (znaleziona i naprawiona tego samego dnia): NIE stosować `_is_evidence_citation()` do Rule 1c (postanowienie o umorzeniu) — sentencja postanowienia legalnie wylicza swoje punkty jako "- umorzyć...", "- ustalić..." (wypunktowanie), więc guard fałszywie łapał WŁASNĄ treść postanowienia jako "cytowanie dowodu"; wymóg nagłówka "POSTANOWIENIE"+"KOMORNIK" w oknie pierwszych 500 zn. już wystarczająco chroni przed false-positive (cytat w uzasadnieniu pozwu art.299 nie miałby takiego nagłówka na SWOJEJ stronie).
│   **Rule 1b** (02.07.2026): "WNIOSEK O WSZCZĘCIE POSTĘPOWANIA EGZEKUCYJNEGO" (pismo wierzyciela DO komornika) → kind `wniosek_egzekucyjny`, z guardem `_is_evidence_citation()`. **Rule 1c**: nagłówek "POSTANOWIENIE" WSPÓŁWYSTĘPUJĄCY z "KOMORNIK" w oknie pierwszych 500 zn. ORAZ sentencja "umorzyć [z urzędu] postępowanie egzekucyjne" gdziekolwiek na stronie → kind `postanowienie_umorzenie_egzekucji` (BEZ guardu cytowania — patrz pułapka wyżej). **Rule 4b**: boilerplate klauzuli wykonalności ("uprawnia do egzekucji" / "podlega wykonaniu jako prawomocne") → `None` (kontynuacja poprzedniego nakazu/wyroku) — bez tego fallback Rule 6 ("TYTUŁ WYKONAW...", bo klauzula zawiera "Tytuł wykonawczy wydano...") błędnie zaczynał nowy segment "komornik" od strony klauzuli, odcinając ją od nakazu.
├── doc_selector.py      # Scores candidates (CSV 02) + tie-breaking (CSV 04) → main document; hard rules: (1) NAKAZ wins over POZEW gdy oba typy współistnieją wśród kandydatów, ALE (03.07.2026) reguła jest teraz WARUNKOWA — wyjątek: sekwencja art. 299 KSH (implementacja R10 z CSV 02: "nakaz przeciwko spółce jest głównym TYLKO gdy brak dokumentu przeciwko członkowi zarządu"). Gdy paczka to łańcuch [nakaz przeciw SPÓŁCE → egzekucja → umorzenie → pozew przeciw CZŁONKOM], dokumentem głównym jest POZEW (żywa sprawa), a nakaz jest historyczny (prawomocny, z klauzulą wykonalności — jego "termin 14 dni" NIE biegnie). Sygnały łańcucha (wystarczy jeden; oba wymagają istnienia pozwu typu _CZLONEK_ZARZADU z pozwanym-osobą fizyczną — koniunkcja dwóch niezależnych cech chroni przed błędną klasyfikacją): A) w paczce jest WNIOSEK_EGZEKUCYJNY lub UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC; B) nakaz dotyczy spółki (typ _SPOLKA lub `is_company_name(pozwany)`). Dla bundli tej samej sprawy (nakaz+jego pozew, ten sam pozwany — np. nakaz_zapłaty+pozew.pdf, Lublin_pozew_nak._zap..pdf) nakaz nadal wygrywa jak dotąd; (2) among nakazy, nakaz WITH deadline_days wins over nakaz without (prevents misclassified uzasadnienie pages from beating actual EPU nakaz); R17 scoring fires for deadline_days alone (no delivery_date needed); bundle upgrade: SPOLKA→CZLONEK_ZARZADU when art.299 OR "czlonek zarządu" found in any bundle doc — (03.07.2026) Z GUARDEM: upgrade NIE odpala, gdy `is_company_name(main.pozwany)` — pozwany na samym dokumencie głównym jest spółką, więc wzmianka o art. 299 pochodzi z innego dokumentu paczki; bez guardu powstawał stan niespójny typ *_CZLONEK_ZARZADU + wyświetlany pozwany-spółka → bramka art. 299 pytała o osobę fizyczną wbrew danym na ekranie. NOWY WSPÓŁDZIELONY HELPER `is_company_name()` (+`_COMPANY_FORMS`): rozpoznaje formy spółek WŁĄCZNIE z pełnymi formami pisanymi ("spółka z ograniczoną odpowiedzialnością", "spółka komandytowo-akcyjna" itd.) — używany też przez bramkę art. 299 w app.py i skrypt regresji
├── ai_extractor.py      # (01.07.2026, nowy) `extract_fields_ai(text, api_key)` — ekstrakcja przez Claude Haiku jako GŁÓWNA ścieżka dla sygnatura/sad_organ/powod/pozwany/termin/kwota/adresat/epu; regex (doc_extractor.py) to tani fallback (brak klucza API lub AI zawiedzie → {}). Powód zmiany: polska korespondencja prawna ma za dużo gramatycznych odmian tej samej formuły ("nakazuje pozwanemu"/"strona pozwana"/"stronie pozwanej"/"stronę powodową"...), żeby regex mógł je wszystkie przewidzieć — każdy nowy dokument ujawniał kolejną. Koszt pomijalny (~$0,001-0,002/dokument). WAŻNE dla pola "adresat": prompt NIE wymaga wprost wypisanego "art. 299 KSH"/"członek zarządu" — wystarczy, że pozwany jest osobą fizyczną (ten kalkulator obsługuje wyłącznie sprawy odpowiedzialności członków zarządu, więc podstawa prawna bywa nieobecna w samym piśmie, np. gdy sprawa to formalnie zwykła windykacja pożyczki od osoby fizycznej). Wcześniejsza, węższa wersja promptu (wymagająca jawnego "art. 299") dawała błędny wynik "spolka" dla pozwanego-osoby-fizycznej bez takiej wzmianki — naprawione. (03.07.2026) NOWE POLE `czy_pismo_prawne` (true/false): prompt nie zakłada już z góry, że tekst jest pismem prawnym; false TYLKO gdy tekst JEDNOZNACZNIE nie jest pismem sądowym/komorniczym/urzędowym ani pismem dot. roszczeń (przelew, wyciąg, faktura, paragon, bilet, reklama...), true przy jakiejkolwiek wątpliwości. Konsumowane przez doc_classifier.py (patrz wyżej) do wykrywania dokumentów niezwiązanych ze sprawą.
├── doc_processor.py     # Orchestrator: returns ProcessedDocument dataclass; maps doc_type_code → k1_code via _DOC_TYPE_TO_K1. (01.07.2026) `_build_candidate_dict()` woła `extract_fields()` (regex) i NASTĘPNIE `extract_fields_ai()` — wynik AI nadpisuje pola regexowe tam, gdzie AI coś zwróciła — PRZED `classify_document()`, więc "adresat" od AI zasila bonus klasyfikacyjny dla KAŻDEGO segmentu w paczce (nie tylko głównego, jak w starszej wersji gdzie app.py łatało tylko main_doc post-hoc po `process_files()`). (02.07.2026) `_process_single_doc()`: `splitter_segments` (info dla panelu technicznego "Segmentacja stron") ma teraz dodatkowe pole `"final_type"` = `doc_type_code` finalnie nadany przez `classify_document()` temu samemu segmentowi (sparowane po indeksie `zip(segments, candidates)`) — wcześniej panel pokazywał WYŁĄCZNIE surowy typ ze splittera (sprzed klasyfikacji), co mogło nie zgadzać się z typem pokazanym w "Zestawieniu dokumentów"/"Dokumencie pomocniczym N" (dwa niezależne przebiegi klasyfikacji tej samej strony). (03.07.2026) `_build_candidate_dict()` przekazuje `czy_pismo_prawne` z wyniku AI do `fields` przed `classify_document()` — patrz doc_classifier.py/ai_extractor.py.
│
├── requirements.txt     # All dependencies including pdfplumber, python-docx, Pillow, anthropic, azure-ai-documentintelligence, pytesseract
└── .streamlit/
    ├── config.toml      # Streamlit theme/config
    └── secrets.toml     # LOCAL ONLY (in .gitignore): TEST_PANEL_PASSWORD, ANTHROPIC_API_KEY
```

Poza `app/` istnieje też `tools/` (03.07.2026):
```
tools/
├── regression_test.py       # Automatyczna regresja pipeline'u: uruchamia process_files() (ta sama ścieżka co aplikacja, z OCR i AI) na plikach z C:\Users\User\Desktop\testy i porównuje z oczekiwaniami; użycie: python tools/regression_test.py [--dir ...] [--only NAZWA.pdf]; brakujące pliki → SKIP z ostrzeżeniem; koszt kilka-kilkanaście centów/przebieg (Azure DI + Haiku). URUCHAMIAĆ PO KAŻDEJ ZMIANIE w doc_*.py/ai_extractor.py — to jest odpowiedź na pytanie "czy poprawka jest ogólna, czy dopasowana do jednego pliku".
└── regression_expected.json # Tabela oczekiwań per plik: main_type (lista akceptowalnych), main_pages, deadline_days, amount (±0,01), aux_types_include (listy alternatyw), gate (czy bramka art. 299 ma się pokazać); klucz nieobecny = nie sprawdzaj
```

**To run locally:**
```bash
streamlit run app/app.py
```

**Secrets required** (`app/.streamlit/secrets.toml`, never commit this file):
```toml
TEST_PANEL_PASSWORD = "krs-test-2024"
ANTHROPIC_API_KEY = "sk-ant-..."
AZURE_DI_KEY = "..."
AZURE_DI_ENDPOINT = "https://krs-guard.cognitiveservices.azure.com/"
```
WAŻNE: każdy klucz i wartość muszą być na tej samej linii (format TOML).

The technical panel (scores, raw answers, triggered rules, sanitization check) is hidden behind a password. Default: `krs-test-2024`, overridable via `st.secrets["TEST_PANEL_PASSWORD"]`.

## Data source hierarchy

| Format | Role |
|---|---|
| `dane_wejściowe/KRS_Guard_reguly_i_zasady_funkcjonowania.xlsx` | **Authoritative source** — all rules, scoring, texts, codes |
| `dane_wejściowe/KRS_Guard_specyfikacja_funkcjonalna_logiczna_tekstowa.md` | Functional specification: interprets the Excel data, explains logic and requirements |
| `dane_wejściowe/KRS_Guard_reguly_i_zasady_funkcjonowania.md` | Full Markdown export of all Excel sheets — human/AI readable mirror |
| `dane_wejściowe/csv/*.csv` | Per-sheet CSV exports for programmatic processing (semicolon-delimited) |

**Rule**: never hard-code texts, scores, or rules in application code that can be driven from Excel. The Excel file is the single source of truth.

**Rule — CSV i Excel muszą być zawsze zsynchronizowane**: Każda zmiana w dowolnym pliku CSV (`dane_wejściowe/csv/*.csv`) musi być wprowadzona JEDNOCZEŚNIE do odpowiedniego arkusza Excela (`dane_wejściowe/KRS_Guard_reguly_i_zasady_funkcjonowania.xlsx`) w tej samej operacji. Nigdy nie commituj zmiany tylko w CSV bez zmiany w Excelu. Wyjątek: `PISMO_PROCESOWE_SADOWE` (typ zarządzany wyłącznie w CSV, nie ma go w Excelu — zaznaczone w sekcji Key data sheets).

**Weryfikacja synchronizacji CSV ↔ Excel**: Mapowanie CSV → arkusz Excel przez auto-detekcję z nazwy pliku (usuń prefix `NN_` i `.csv`; uwaga: nazwy CSV bez polskich znaków, arkusze z nimi — np. `14_7_Instrukcja_dzialania_AI.csv` → arkusz `7_Instrukcja_działania_AI`). Ostatni audyt: 03.07.2026 (porównanie komórka po komórce) — 41/41 plików zsynchronizowanych. Naprawione wtedy rozjazdy: K6_GOAL_BUY_TIME miało w Excelu H=1 mimo celowej zmiany na H=0 w CSV (commit 5d0f0ba — Excel wtedy nie zsynchronizowany, RÓŻNICA WPŁYWAŁA NA PUNKTACJĘ); R06a w arkuszu 2 miało zdegradowane polskie znaki; R33 miało scalone B36:C36 i pustą kolumnę Warunek; w arkuszu 2B/CSV 04 treści komórek zawierały średnik (separator CSV!) — zamienione na przecinek/pauzę w OBU plikach. ZASADA: nie używać średnika WEWNĄTRZ treści komórek arkuszy eksportowanych do CSV.

## Core business logic (from spec)

**Calculator flow:**
1. Client uploads documents or fills the form manually
2. Calculator identifies the **main document** (dokument główny) — the one requiring the most urgent response
3. EPU / e-Court status is assessed per document type
3a. **Art. 299 KSH gate** (document mode only): if the detected doc type ends with `_CZLONEK_ZARZADU` (individual person as defendant), the app shows a confirmation question before the form: "Czy sprawa dotyczy odpowiedzialności z tytułu pełnienia funkcji członka zarządu?" — "Nie" blocks the form with an info message; "Tak" proceeds. Session state key: `_art299_gate` (None / "yes" / "no"). Gate does NOT appear in manual mode (no document uploaded).
4. Client confirms the claim amount (K7)
5. Client calculates or selects the time remaining to respond (K2)
6. Client answers questions K3–K6
7. Score `S = C + P + H + W` is computed from Excel sheet `5_Punktacja_formularza`
8. Hard safety rules (sheet `5B_Twarde_reguly`) may override the score upward
9. A base scenario (sheet `6_Biblioteka_scenariuszy`) is selected, then contextual rules (sheets `6D`–`6U`) enrich the output text
10. A short, plain-language risk assessment is shown to the client

**Risk levels (S = C+P+H+W):**
- 0–3 → RISK_LOW (Niższe ryzyko / prewencja)
- 4–5 → RISK_MEDIUM (Średnie ryzyko / braki danych)
- 6–7 → RISK_HIGH (Wysokie ryzyko)
- 8+ → RISK_URGENT (Sprawa pilna)

Risk level codes must never be shown to the client — only the user-facing label.

## Form structure (K1–K7)

| Code | Field |
|---|---|
| K1 | Type of main document (ciężar i charakter dokumentu) |
| K2 | Time remaining to respond |
| K3 | Scope of support needed |
| K4 | Board member status (aktualny / rezygnacja / odwołanie) |
| K5 | KRS registration status |
| K6 | Client's primary goal |
| K7 | Claim amount |

## Key data sheets and their roles

| Sheet | CSV file | Purpose |
|---|---|---|
| `1_Slownik_pojec_KRS_Guard` | `01_…csv` | Term definitions — what the AI must not confuse |
| `2_Reguly_wyboru_dok_glownego` + `2A/2B/2C/2D` | `02–06_…csv` | Main document selection rules and tie-breaking |
| `3_Typy_dokumentow` | `07_…csv` | Document type codes, EPU compatibility, scoring. Custom type `PISMO_PROCESOWE_SADOWE` added (not in Excel — managed directly in CSV) |
| `4_Formularz_6_krokow` | `08_…csv` | Form questions, answer codes, labels |
| `5_Punktacja_formularza` | `09_…csv` | C/P/H/W point values per answer |
| `5A_Interpretacja_wyniku` | `10_…csv` | Score-to-risk-level mapping |
| `5B_Twarde_reguly` | `11_…csv` | Hard safety rules that override the score |
| `6_Biblioteka_scenariuszy` | `12_…csv` | Base scenario texts (173 scenarios) |
| `6A_Moduly_K3_K6` | `22_…csv` | Contextual text modules for K3–K6 answers |
| `6D`–`6U` | `24–41_…csv` | Contextual rules: deadline, EPU, KRS, claim amount, ZUS, unknown doc |
| `10_Testy_kontrolne` | `17_…csv` | Regression test cases |
| `14_Kontrola_jakosci` | `21_…csv` | Quality control checklist |

## Git workflow

After every meaningful change — new file, updated spec, working feature, config change — commit and push to GitHub:

```bash
git add <specific files>
git commit -m "short description of what changed and why"
git push origin etap2   # use etap2 during Stage 2 development; main is for production only
```

Use clear, descriptive commit messages in English or Polish (match the language of the changed content). Never bundle unrelated changes into one commit.

**Important:** All Stage 2 development goes to `etap2` branch. Merge to `main` only when Stage 2 is fully tested.

## Test documents

Test files used during Stage 2 development are stored in `C:\Users\User\Desktop\testy\` (outside the repo). **Always check this folder for current test files and screenshots before diagnosing any bug.**
- `Lublin_nakaz_zapłaty_pko.pdf` — EPU nakaz zapłaty (Sąd Rejonowy Lublin-Zachód); powód: PKO Bank Polski S.A.; pozwany: PIOTR CZAK; **aktualna treść pliku** (stan 01.07.2026, archiwum `KANCELARIA_PRS\do testów\analizy ok\`): sygnatura VI Nc-e 1245792/25, kwota łączna 85 463,92 zł — ta sama sygnatura/kwota co `Lublin_pozew_pko.pdf` (logicznie poprawne: to nakaz DLA TEJ SAMEJ sprawy); termin: 14 dni; should classify as `EPU_NAKAZ_CZLONEK_ZARZADU`. (Starsza notatka w tym pliku wspominała inne dane "236/25"/"80 460,82 zł" — plik testowy został od tego czasu zregenerowany przez użytkownika.)
- `Lublin_pozew_pko.pdf` — EPU pozew o zapłatę (VI Nc-e 1245792/25, Sąd Rejonowy Lublin-Zachód); powód: PKO Bank Polski S.A.; pozwany: PIOTR CZAK; kwota: 85 463,92 zł; tytuł dokumentu: "P O Z E W" (ze spacjami); should classify as `EPU_POZEW_CZLONEK_ZARZADU`; triggered fix: bonus/kara zamienione na bonus/bonus (OCR-resilient)
- `Lublin_pozew_nak._zap..pdf` — SKANOWANY wielostronicowy PDF; wersja oryginalna miała 8 stron (str.1: pozew, str.2: pismo przewodnie sądu, str.3: uzasadnienie art.299, str.4: tabela dowodów, str.5-7: nakaz EPU, str.8: pusta); użytkownik usunął str.2 i str.8 → analiza prawidłowa ✓ (commit a67f6e3); powód: Krzysztof Knop; pozwany: Piotr Czak; sygnatura: VI Nc-e 222431/23; kwota: 5 267,77 zł; wynik: [1/2] nakaz GŁÓWNY + [2/2] pozew POMOCNICZY, K1=Nakaz (członek zarządu), termin 14 dni, bramka art.299 TAK; UWAGA: Azure DI nie wykrywa KOD na str.1 (pozew EPU) — tylko na str.5 (nakaz); nuclear merge (Krok 1, wersja niezależna od KOD) scala pre-blok
- `Lublin_pozew_nak._zap.2.pdf` — nowszy wariant tego samego typu bundla (4 str.: pozew str.1-2, nakaz str.3-4); VI Nc-e 1707736/22, Marcin Pycek vs WOODHOME sp. z o.o. (SPÓŁKA, nie członek zarządu — pozwanym jest sama spółka); "Wartość przedmiotu sporu 11 286,00 PLN" na str.1 pozwu. Ujawnił 01.07.2026: (1) segmentacja gubiła str.1 pozwu gdy Rule 0 (KOD) nie wykryła nakazu — naprawione uogólnieniem Kroku 1 (patrz doc_splitter.py wyżej); (2) ekstraktor kwoty łapał wartość faktury z listy dowodów zamiast "Wartość przedmiotu sporu"/"kwotę łączną" — naprawione nowymi wzorcami w `_KWOTA_PATTERNS`; (3) ekstraktor sygnatury łapał numer faktury "FV 135/2021" — naprawione `_SYGNATURA_EXCLUDE_RE`; (4) kaskada OCR nie eskalowała do Claude Haiku przy niskiej jakości Azure — naprawione (patrz doc_ocr.py wyżej). Oba pozostałe problemy NAPRAWIONE (01.07.2026, ta sama sesja, patrz doc_extractor.py wyżej): powód/pozwany garbled dla NAKAZ (`\b` po "Pow[oó]d"/"Pozwan[yąa]") oraz niespójność SPOLKA/CZLONEK_ZARZADU (prawdziwa przyczyna: `_POZWANY_PATTERNS[1]` łapał "następujących kwot" z formuły "Wnoszę o zasądzenie na rzecz Powoda od Pozwanego następujących kwot:" jako nazwę pozwanego — naprawione ogólnym guardem `_looks_like_party_name()`). Po naprawie: aux poprawnie `EPU_POZEW_SPOLKA` (nie CZLONEK_ZARZADU), zgodnie z dokumentem głównym; pozwany poprawnie "WOODHOME SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ...". Zweryfikowane end-to-end, 5/5 testów regresji bez zmian.
- `nakaz_zapłaty+pozew.pdf` — 12 stron: nakaz str.1-7 (str.2/8 puste — plik drukowany dwustronnie i zeskanowany), pozew str.9-11 (str.10 pusta); Sąd Rejonowy dla Krakowa-Śródmieścia V Wydział Gospodarczy (NIE EPU/e-sąd — postępowanie "zwykłe"); Sygn. V GNc 1235/22/S; powód: Mariusz Szewłoga; pozwany: Woodhome sp. z o.o.; kwota: 34 230,43 zł (nakaz) / 34 231,00 zł (wartość przedmiotu sporu pozwu). Ujawnił 01.07.2026: str.11 (uzasadnienie pozwu + lista załączników) błędnie klasyfikowana jako osobny dokument "Wezwanie sądowe", bo str.11 wymienia "Dowód: wezwanie do zapłaty z dnia..." oraz w liście załączników "- wezwanie do zapłaty z dnia..." — to CYTOWANIA dowodu/załącznika, nie nagłówek strony. Prawdziwa przyczyna: Rule 6 (fallback `_PAGE_DOC_PATTERNS`, wzorzec bez kotwicy początku linii, przeszukiwany w pierwszych 2000 zn.) dopasowywał frazę gdziekolwiek — nie Rule 3 (ta poprawnie odrzucała dzięki kotwicy `^\s*`, ale mogłaby zawieść przy innym łamaniu linii przez inny silnik OCR). Naprawione `_is_evidence_citation()` — patrz doc_splitter.py wyżej. Dodatkowo naprawiono (01.07.2026, ta sama sesja): `deadline_days` dla nakazu pokazywał 90 zamiast 14 — ekstraktor terminu łapał "w terminie trzech miesięcy" (klauzula o doręczeniu zagranicznym w pouczeniu) zamiast bliższego, poprawnego "w terminie dwóch tygodni od doręczenia nakazu"; naprawione w `_find_deadline_near_keyword()` (wybór najbliższego, nie pierwszego wg listy, dopasowania — patrz doc_extractor.py wyżej). Naprawa terminu podniosła punktację nakazu do remisu z pozwem, co ujawniło DRUGI błąd: `doc_selector.py`'s hard rule "nakaz>pozew" nie obejmowała remisu punktowego, więc `_tiebreak()` (R1: adresat) błędnie wybierał pozew (jego adresat błędnie "czlonek_zarzadu" — ta sama niespójność SPOLKA/CZLONEK_ZARZADU) — naprawione uczynieniem reguły nakaz>pozew bezwarunkową (patrz doc_selector.py wyżej). Po obu poprawkach: main=NAKAZ_SPOLKA str.1-7 deadline_days=14. Dodatkowo naprawiono (patrz `Lublin_pozew_nak._zap.2.pdf` wyżej i doc_extractor.py na górze pliku): powód/pozwany garbled + niespójność SPOLKA/CZLONEK_ZARZADU — po tej naprawie aux poprawnie `POZEW_SPOLKA` (nie CZLONEK_ZARZADU), zgodnie z dokumentem głównym. Zweryfikowane, 5/5 testów regresji bez zmian.
- `Nakaz_zapłaty+pozew+przes_wez._do_zap..pdf` — ten sam case co wyżej + dodana 3. strona: przedsądowe wezwanie do zapłaty (str.7-8, pismo pełnomocnika wierzyciela — NIE dokument sądowy). Ujawnił 01.07.2026: klasyfikator dawał `WEZWANIE_SADOWE_SPOLKA` (sądowe) zamiast `WEZWANIE_PRZEDSADOWE_SPOLKA` — zweryfikowałem realnym uruchomieniem `doc_classifier._score_text()`: oba typy dostawały DOKŁADNIE ten sam wynik (2 pkt), o zwycięstwie "sądowe" decydowała czysto kolejność wierszy w CSV 07 (Python stable sort), nie treść dokumentu. Naprawione: dodano słowo kluczowe "przedsądowe" do `WEZWANIE_PRZEDSADOWE_SPOLKA`/`_CZLONEK_ZARZADU` w CSV 07 i Excel (arkusz `3_Typy_dokumentow`) — daje +1 pkt przewagi niezależnie od kolejności wierszy. Ten sam test posłużył do weryfikacji wariantu 4 (patrz niżej) — po zmianie wszystkie 3 dokumenty poprawnie spójnie SPOLKA, czyste nazwy powód/pozwany bez artefaktów. Ten sam plik ujawnił też (kolejna sesja, 01.07.2026) błąd UI: w "Zestawieniu dokumentów w pliku" badge "WYMAGA REAKCJI" pojawiał się zarówno przy nakazie (główny), jak i przy przedsądowym wezwaniu (pomocniczy, ma własny termin płatności "w terminie 7 dni..."), sugerując klientowi dwa niezależne terminy do pilnowania — naprawione w `app.py` (patrz wyżej), badge teraz tylko przy dokumencie głównym. Potwierdzone przez użytkownika na żywej sesji.

- `art299_pozew_nakaz_umorz._egzek..pdf` — nowy plik testowy (02.07.2026), 13 str. skan; Sygn. XIII I GNc 6937/20, Sąd Rejonowy dla Łodzi-Śródmieścia; powód: Kiloutou Polska sp. z o.o.; pozwany/dłużnik nakazu: Woodraft Home sp. z o.o.; pozwani pozwu (27.02.2023, postępowanie nakazowe): Krzysztof Duda, Piotr Czak, Przemysław Duda (członkowie zarządu, art. 299 KSH); kwota nakazu 4 547,81 zł. Struktura: str.1-6 pozew, str.7-8 nakaz zapłaty (03.12.2020) + klauzula wykonalności (12.04.2021), str.9-11 wniosek wierzyciela o wszczęcie postępowania egzekucyjnego do komornika (19.04.2021), str.12-13 formalne POSTANOWIENIE komornika (sygn. GKm 46/21, Jakub Niedopytalski) o umorzeniu postępowania egzekucyjnego z urzędu (25.10.2021, art. 824 §1 pkt 3 k.p.c. — brak majątku dłużnika = bezskuteczność egzekucji, przesłanka art. 299 KSH). Segmentacja i klasyfikacja segmentów rozwiązane 02.07.2026 (reguły 1b/1c/4b w doc_splitter.py + bonus adresata w doc_classifier.py + słowa kluczowe CSV 07). **STATUS 03.07.2026: WYBÓR DOKUMENTU GŁÓWNEGO NAPRAWIONY I ZWERYFIKOWANY.** Użytkownik zgłosił (słusznie), że wynik z 02.07 był merytorycznie błędny: dokumentem wymagającym reakcji NIE jest nakaz z 2020 (prawomocny, historyczny — egzekucja z niego już przeprowadzona i umorzona), tylko POZEW z 2023 przeciwko członkom zarządu (żywa sprawa). Przyczyna: bezwarunkowa twarda reguła nakaz>pozew w doc_selector.py, sprzeczna z R10 z CSV 02 — naprawiona regułą warunkową (wyjątek dla sekwencji art. 299, patrz doc_selector.py wyżej). Dodatkowo bramka art. 299 pojawiała się z tekstem "pozwanym jest osoba fizyczna" przy wyświetlanym pozwanym-spółce (dwie przyczyny: brak pełnych form spółkowych w _SPOLKA_FORMS + Fix B upgrade bez guardu — obie naprawione). Wynik po naprawie: main=`POZEW_CZLONEK_ZARZADU` str.1-6, aux=`NAKAZ_SPOLKA` str.7-8 (bez badge WYMAGA REAKCJI), `WNIOSEK_EGZEKUCYJNY` str.9-11, `UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC` str.12-13; bramka art. 299 pokazuje się ZASADNIE (pozwani pozwu to osoby fizyczne). Regresja: 8/8 przez tools/regression_test.py. Potwierdzone przez użytkownika na żywej sesji Streamlit (03.07.2026).
- `potwierdzenie opłaty prolongacyjnej za grób.PDF` — nowy plik testowy (03.07.2026); potwierdzenie przelewu bankowego (Raiffeisen, 2017, 680 zł, beneficjent "Zarząd Cmentarzy Komunalnych w Krakowie") — dokument CELOWO niezwiązany z żadną sprawą sądową. Ujawnił: klasyfikator wciskał dokumenty niesądowe w typy prawne — przelew dostawał `ODPIS_KRS` z pewnością 0.85 (jedno słabe trafienie "zarząd" z nazwy beneficjenta; ODPIS_KRS był jedynym kandydatem → sztywna pewność 0.85), a UI pokazywało tabelę "Odpis Krs / Kwota roszczenia 680,00 zł" jak dla pisma sądowego. Naprawione (03.07.2026): pole `czy_pismo_prawne` w ai_extractor.py + reguły progowe w doc_classifier.py + gałąź ostrzeżenia w app.py (patrz wpisy modułów wyżej). Wynik po naprawie: `DOKUMENT_NIEPRAWNY`, ostrzeżenie "plik nie wygląda na pismo sądowe" zamiast tabeli, formularz dostępny ręcznie, kwota z przelewu NIE zasila K7. Potwierdzone przez użytkownika na żywej sesji Streamlit (03.07.2026).

### Wariant 4 (01.07.2026): ekstrakcja AI jako główna ścieżka
Po CZWARTYM z rzędu przypadku "nowy dokument = nowa gramatyczna odmiana formuły,
której regex nie przewidział" (`_POWOD_PATTERNS`/`_POZWANY_PATTERNS` łatane
wielokrotnie tego dnia), zmieniono architekturę: `doc_processor.py` woła teraz
`ai_extractor.extract_fields_ai()` (Claude Haiku) jako GŁÓWNĄ ścieżkę dla
sygnatura/sad_organ/powod/pozwany/termin/kwota/adresat/epu dla KAŻDEGO
dokumentu w paczce (nie tylko głównego, jak w starszej wersji w app.py) —
regex w doc_extractor.py to tani fallback (brak klucza API/błąd AI → {}).
Koszt: ~$0,001-0,002/dokument (Claude Haiku), pomijalny.

**Pułapka wykryta podczas weryfikacji:** pierwsza wersja promptu AI wymagała
JAWNEGO "art. 299 KSH"/"członek zarządu" w tekście, żeby zwrócić adresat=
"czlonek_zarzadu" — to spowodowało REGRESJĘ dla `Lublin_pozew_pko.pdf`
(pozwany Piotr Czak, osoba fizyczna, ale tekst pozwu nie wspomina art. 299
wprost — sprawa wygląda jak zwykła windykacja pożyczki), AI zwróciło
błędnie "spolka". Naprawione: prompt mówi teraz wprost, że ten kalkulator
obsługuje WYŁĄCZNIE sprawy odpowiedzialności członków zarządu, więc pozwany
będący osobą fizyczną ZAWSZE oznacza "czlonek_zarzadu", niezależnie od tego,
czy podstawa prawna jest w piśmie wprost wymieniona (może wynikać z innych
dokumentów w sprawie). Zweryfikowano end-to-end na 6 plikach testowych po tej
poprawce — wszystkie poprawne, brak regresji.

## Zasady pracy Claude Code w tym projekcie

### Synchronizacja dokumentacji (obowiązkowe)
- **Po każdej zmianie kodu lub danych**: zaktualizuj CLAUDE.md (sekcja doc_*.py, test documents) oraz plik memory projektu (`project-etap2-state.md`) — jeszcze w tej samej sesji, przed commitem.
- **Nie czekaj do końca rozmowy** z aktualizacją dokumentacji — rób to na bieżąco po każdym zakończonym kroku.

### Ostrzeżenie o limicie tokenów
Przed przystąpieniem do zadania, które może wymagać dużej liczby tokenów (wiele plików, skomplikowane refaktoryzacje, analizy wielu arkuszy), pokaż użytkownikowi ostrzeżenie:

```
⚠️ OSTRZEŻENIE: To zadanie może być długie (szacuję: [liczba] plików / [zakres] zmian).
Jeśli rozmowa zostanie przerwana z powodu limitu, zrób checkpoint — zatrzymaj się i powiedz
co zostało zrobione, a co jeszcze pozostaje. Kontynuować?
```

Próg ostrzeżenia: zadanie dotyka >4 plików LUB >80 linii kodu do zmiany LUB >3 arkuszy CSV/Excel jednocześnie.

## Communication rules (non-negotiable)

- Never show technical codes (K1–K7, RISK_*, HRxx, scenario_id) to the client
- Never use the word "użytkownik" in client-facing output; use "W formularzu wskazano…", "Zaznaczono…", "Na tym etapie…"
- Never generate "sprzeciw od nakazu" or "odpowiedź na pozew" for ZUS/agency letters — only "złożenie wyjaśnień"
- Always state that deadlines include weekends and holidays ("wliczają się soboty, niedziele i dni świąteczne")
- If a specific day count is available, show the exact number — never a range
- End every result with a CTA toward Audyt 48h without using hard-sell language
