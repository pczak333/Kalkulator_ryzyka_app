# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**KRS Guard – Kalkulator Ryzyka Prawnego** is a legal risk calculator for cases involving liability of company board members (odpowiedzialność członków zarządu, art. 299 KSH). The calculator takes court/official documents and a user-filled form as input, and produces an oriented risk assessment with a call to action (typically recommending the paid "Audyt 48h" service).

The application is built and running. The stack is **Python + Streamlit**. Source code lives in `app/`.

## Branch strategy

**Jedna gałąź: `main`.** (16.07.2026) Etap 2 (upload dokumentów + OCR + AI +
redesign wizualny) uznany za wystarczająco przetestowany i scalony do `main`
przez fast-forward merge — na wyraźną decyzję użytkownika: jedna wersja, jedna
gałąź, zamiast dotychczasowego podziału main (produkcja)/etap2 (rozwój). Gałąź
`etap2` i dwie zbędne gałęzie robocze usunięte lokalnie i na `origin` (były w
100% zawarte w historii `etap2`, zweryfikowane przed usunięciem). Deployment
na share.streamlit.io śledzi `main` bezpośrednio.

Wszystkie przyszłe zmiany: commit + push bezpośrednio na `main` (patrz "Git
workflow" niżej) — bez osobnej gałęzi deweloperskiej. Tag `v1.0-etap1` zostaje
jako historyczny checkpoint stabilnej wersji Etapu 1.

## Application structure

Poniżej opis **aktualnego zachowania** każdego modułu. Szczegółowa historia
napraw (daty, zgłoszenia, zrzuty ekranu, weryfikacje) żyje w `memory/*.md`
(indeks: `memory/MEMORY.md`) i w historii gita — CLAUDE.md celowo nie
powtarza tej narracji, żeby nie rosnąć bez końca.

```
app/
├── app.py               # Streamlit entry point — UI, form flow, result display.
│   Kluczowe bieżące zachowania:
│   - Badge "WYMAGA REAKCJI" w "Zestawieniu dokumentów" pokazuje się TYLKO przy dokumencie głównym, nigdy przy pomocniczych.
│   - `_DOC_TYPE_LABELS` pokrywa wszystkie kody typów (w tym WNIOSEK_EGZEKUCYJNY, ODPIS_KRS, UMOWA_FAKTURA_KORESPONDENCJA, POTWIERDZENIE_DORECZENIA, DOKUMENT_NIEPRAWNY/_NIEUSTALONY_PRAWNY, PISMO_KOMORNIK_*, WEZWANIE_PRZEDSADOWE_*, WYROK_ZAOCZNY_*, POSTANOWIENIE_KRS_Z_URZEDU); panel "Segmentacja stron" pokazuje obok siebie surową etykietę splittera i finalny typ z klasyfikatora.
│   - Bramka art. 299 używa `is_company_name()` z doc_selector.py (nie lokalnej listy skrótów); `_NO_GATE_TYPES = {"WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU"}` pomija bramkę dla typów, które już same kodują art. 299 w klasyfikacji.
│   - Trzy rodziny banerów "poza zakresem", każda z własną gałęzią w `_show_doc_summary()` i własnym mechanizmem ukryj-tabelę/zeruj-pola: `_NON_LEGAL_MAIN_TYPES` (dokument niesądowy, używa AI `doc_description` gdy dostępne), `_SPOLKA_OUT_OF_SCOPE_TYPES` (zwykła faktura do spółki, bez art. 299), `_KRS_REJESTROWE_OUT_OF_SCOPE_TYPES` (postępowanie rejestrowe KRS, nie spór o zapłatę). Formularz K1-K7 chowa się za jawnym opt-in (`_manual_form_opt_in`, ten sam wzorzec `st.stop()` co bramka art. 299), gdy dokument główny należy do którejkolwiek z tych trzech grup.
│   - Pisma komornicze (`_KOMORNIK_MAIN_TYPES`) dostają kontekstowy baner (łagodniejszy dla "wznowienia zawieszonego postępowania" niż dla aktywnego zajęcia); dokumenty spółkowe dostają osobny baner "ryzyko pośrednie" (tekst z CSV 35 przez `data_loader.load_spolka_indirect_risk_text()`).
│   - `_komornik_display_label()` dopisuje do etykiety pisma komorniczego rodzaj czynności ze splittera, żeby wieloliterowa paczka jednej egzekucji nie pokazywała identycznych pozycji.
│   - `EPU_COMPATIBLE` zna wszystkie kody K1 dodane od 01.07 (komornicze, przedsądowe-członek, wyrok zaoczny) z poprawną zgodnością EPU.
│   - Tabela kwoty roszczenia pokazuje podpis czy to należność główna czy kwota łączna, plus opcjonalny drugi wiersz "Wartość przedmiotu sporu" gdy dokument podaje WPS różny od kwoty głównej — oba pomijane po ręcznej korekcie kwoty.
│   - `st.warning()` odpala się, gdy wierzyciel (`powod`) dokumentu pomocniczego wyraźnie różni się od wierzyciela dokumentu głównego (`parties_differ()` z doc_selector.py) — sygnał "to może być inna sprawa w tej samej paczce".
│   - Wskaźnik postępu analizy: `st.status(..., expanded=False)` z jednym aktualizującym się `label` (nie `.write()`, które by dopisywało wiersze), karmiony callbackami `on_progress` z pipeline'u OCR/przetwarzania; nazwy silników (Azure/Claude/Tesseract) nigdzie nie trafiają do tekstu dla klienta. Blok przetwarzania renderuje się POZA `st.expander("Wgraj dokumenty")` (Streamlit zabrania zagnieżdżonych expanderów, a `st.status` jest expanderem wewnętrznie).
│   - Wynik to kompaktowa zajawka (pigułka ryzyka + pierwsze zdanie przez `_first_sentence()`, pogrubienie markdown konwertowane `report_builder.markup_bold()`) + toggle "Zobacz pełny raport" (osadza `report_builder.build_report_html()`) + przycisk "Pobierz PDF" (`report_builder.build_report_pdf()`).
│   - Gdy `prefill.ai_extraction_status != "ok"` pokazuje się ostrzeżenie o wyłączonej/nieudanej ekstrakcji AI (brak klucza vs. błąd wywołania) + wiersz w panelu technicznym "Ekstrakcja AI: OK / fallback regex". Patrz `memory/project_ai_key_silent_fallback.md`.
│   - Ikony: emoji zastąpione Material Symbols (`icon=":material/...":` w widgetach natywnych) i `branding.icon_svg()` w banerach HTML (Material Symbols nie renderują się w surowym `st.markdown` HTML). Pomarańczowe banery przemalowane na niebieskie (`notice_bg`/`notice_border`); natywny `st.warning` zostawiony bez zmian (brak per-kind hooka w DOM Streamlit 1.45.1).
│   - Rozmiar znaku w nagłówku (`logo_svg_light_on_dark`) dobrany tak, by proporcja względem bloku tytuł+podtytuł zgadzała się z nagłówkiem raportu (podtytuł appki zawija się do 2 linii, podtytuł raportu nie).
│   - Bramka art. 299 i checkbox EPU mają uproszczony język + expander "Dlaczego pytamy?" (jak wszystkie kroki K1-K7); kolumna `question_text` w CSV 08 jest martwa — etykiety są zahardkodowane per-krok w wywołaniach `labeled_radio()`, zsynchronizowane z CSV/Excel (patrz `memory/project_form_content_audit.md` po niuans odwrócenia kierunku dla K3/K6).
│   - Helpery porównania nazw stron (`normalize_party_name`/`parties_differ`) mieszkają w `doc_selector.py` — app.py je importuje.
│   - Pełna historia/uzasadnienie powyższego: `memory/project_visual_redesign.md`, `memory/project_progress_indicator.md`, `memory/project_out_of_scope_detection.md`, `memory/project_unrelated_docs_warning.md`, `memory/project_wps_amount_labeling.md`, `memory/project_komornik_boilerplate_deadlines.md`.
├── branding.py          # System tokenów wizualnych (kolory, typografia, promienie, cienie — `TOKENS` + `css_variables()`) i znak graficzny kalkulatora: `logo_svg()`/`logo_svg_light_on_dark()`/`logo_svg_dark_on_light()` — inline SVG, sześciokątna plakietka z monogramem "K" (negatywowy styl — litera wypełniona kolorem tła), świadomie NIE logo kancelarii KRS Guard. Favicon (`app/assets/favicon.png`) generowany osobno przez `tools/generate_favicon.py` (PIL) z tych samych tokenów. `RISK_COLORS`/`RISK_BG` (kolor/tło pigułki per poziom ryzyka) i `icon_svg()`/`_ICON_PATHS` (monochromatyczne ikony Material-Symbols-style do banerów HTML) też tu mieszkają, współdzielone przez app.py i report_builder.py.
├── report_builder.py    # Buduje raport wyniku z `text_builder.build()`: `build_report_html()` (podgląd embedded przez `st.components.v1.html`) i `build_report_pdf()` (do pobrania, `reportlab`). WeasyPrint/xhtml2pdf ODRZUCONE po realnych testach (WeasyPrint wymaga natywnych DLL niedostępnych na Windows; xhtml2pdf gubił polskie znaki diakrytyczne w każdej wypróbowanej konfiguracji `@font-face`). Dołączone fonty DejaVu Sans/Serif (z matplotlib — pełne pokrycie Latin Extended-A, w odróżnieniu od fontu bundlowanego z reportlab). Znak graficzny narysowany natywnie w reportlab (`_logo_drawing()`, te same współrzędne co SVG w branding.py). `markup_bold()` (publiczna) konwertuje markdown `**pogrubienia**` na `<b>`, reużywana przez zajawkę wyniku w app.py.
├── data_loader.py       # Reads CSV files from dane_wejściowe/csv/; `load_spolka_indirect_risk_text()` — komunikat o ryzyku pośrednim dla dokumentów spółki z CSV 35 (arkusz 6P), używany przez baner w app.py
├── scoring_engine.py    # Computes S = C+P+H+W, maps score to risk level
├── hard_rules.py        # Applies hard safety rules (5B_Twarde_reguly) that override score; HR10 (low OCR quality) + HR11 (pismo procesowe — incomplete docs) active. HR02/HR04 (pilność 0-3/4-7 dni dla nakazu-członka-zarządu) sprawdzają `K1 in _NAKAZ_LIKE_CZLONEK_CODES` (tuple, nie pojedynczy literał) — obejmuje też `K1_WYROK_ZAOCZNY_CZLONEK_ZARZADU`, bo rozdzielenie kodów K1 wyroku/nakazu inaczej po cichu wyłączyłoby te reguły bezpieczeństwa.
├── scenario_selector.py # Selects base scenario from 6_Biblioteka_scenariuszy by (k1_code, epu). `_K1_TO_DOC_TYPE` mapuje kody K1, które są reużyciem-z-własną-etykietą (komornicze, przedsądowe-członek, wyrok zaoczny) z powrotem na typ dokumentu, którego wiersze/tekst scenariusza w CSV 12 faktycznie obowiązują — bez tego mapowania `find_scenario()` spadałby na DOKUMENT_NIEUSTALONY_PRAWNY.
├── context_modules.py   # Collects contextual text snippets (6D–6U sheets); `_CZLONEK_ZARZADU_DOC_TYPES` zna WYROK_ZAOCZNY_CZLONEK_ZARZADU (generyczna nota pilności — moduły bez wpisu celowo zwracają pusty/generyczny tekst zamiast błędnie wspominać "nakaz zapłaty").
├── text_builder.py      # Assembles final output text; sanitize_check() verifies no codes leak. `_LEGAL_DISCLAIMER` i 5 wariantów CTA (`_CTA_PERSONAL/_COMPANY/_UNKNOWN/_PISMO_PROCESOWE/_ZUS`) są HARDKODOWANE tutaj (nie w CSV) — jedyne miejsce do edycji tych tekstów. Disclaimer/CTA renderowane przez `report_builder.py` z `output["disclaimer"]`/`output["cta"]` przez `markup_bold`.
│
│   ── Etap 2: document processing modules ──
├── doc_ingestion.py     # Reads uploaded file (PDF/DOCX/JPG/PNG) → list of PageDict per page
├── doc_ocr.py           # Kaskada OCR: Azure DI (próg akceptacji 0.75) → Claude Haiku (eskalacja ZAWSZE gdy Azure poniżej progu, nie tylko przy pustym tekście — dokładniejszy dla zaburzonych układów dwukolumnowych/tabelarycznych) → Tesseract (prawdziwa ostatnia deska ratunku, tylko przy braku klucza ANTHROPIC_API_KEY). Wszystkie funkcje OCR mają opcjonalny `on_progress: Callable[[str], None] | None = None` (domyślnie None = zero zmian zachowania) używany przez wskaźnik postępu app.py; komunikaty per-strona/per-poll są neutralne co do silnika (bez "Azure"/"Claude"/"Tesseract" w tekście dla klienta).
├── doc_extractor.py     # Regex extraction — tani fallback, gdy AI-ekstrakcja niedostępna: sygnały EPU, data doręczenia, termin (też słownie: "dwóch tygodni"), kwota, adresat; sygnatura odrzuca prefiksy komornicze (Km/KM) i fakturowe (FV/FA/F-VAT/FAKTURA). `_looks_like_party_name()` — ogólny guard przeciw łapaniu fragmentów formuł procesowych jako nazwy strony (zastąpił szereg pojedynczych wykluczeń). `_is_skarga_komornika_context()` odrzuca dopasowania terminu w kontekście "skarg"/"art. 767" (termin na skargę na czynność komornika, nie realny termin odpowiedzi) w obu przebiegach ekstrakcji. `_KWOTA_PATTERNS` rozróżnia "Wartość przedmiotu sporu"/kwotę łączną od należności głównej. Powód/pozwany wyciągane tylko z parties_text (przed UZASADNIENIE/POUCZENIE).
├── doc_classifier.py    # Classifies document type from CSV 07 keywords + scoring bonuses/penalties (no module-level CSV cache — always reads fresh). Deterministyczne early-returny dla: PISMO_PROCESOWE_SADOWE (UZASADNIENIE w nagłówku / tytuł pisma przygotowawczego), POTWIERDZENIE_DORECZENIA (nagłówek "DORĘCZENIE...NAKAZU"), WYROK_ZAOCZNY_* ("W IMIENIU RZECZYPOSPOLITEJ POLSKIEJ" + "WYROK...ZAOCZNY"), POSTANOWIENIE_KRS_Z_URZEDU (sąd rejestrowy + pusty powód + "postanowienie"/"z urzędu"), DOKUMENT_NIEPRAWNY dla formularzy PIT. Dwa backstopy łapią dokumenty niesądowe nawet gdy AI-owe `czy_pismo_prawne` jest niejednoznaczne/puste: (1) `czy_pismo_prawne is False` + niski raw score → DOKUMENT_NIEPRAWNY; (2) WSZYSTKIE z sad_organ/sygnatura/powod/pozwany puste + niski raw score + brak formuły nakazu/pozwu/komorniczej → DOKUMENT_NIEUSTALONY_PRAWNY (potrzebne, bo długie wielostronicowe formularze jak 15-stronicowy PIT-36 mogą nabić raw score samą objętością/generycznymi słowami). `splitter_kind` (z doc_processor, przekazany z klasyfikacji per-segment w doc_splitter) daje deterministyczne bonusy dla segmentów komorniczych/pismo-procesowe/umorzenie-egzekucji — bez nich poprawnie zsegmentowany fragment nadal przegrywałby scoringiem słów kluczowych z innym typem. **KRYTYCZNY BUG WDROŻENIOWY naprawiony 22.07.2026**: `_CSV_PATH` był gołym względnym stringiem, który działał TYLKO dlatego, że lokalny dev zawsze uruchamia z `cd app`; Streamlit Community Cloud uruchamia z cwd=korzeń repo, co dawało `FileNotFoundError` przy KAŻDYM uploadzie dokumentu na produkcji. Naprawione budową ścieżki przez `os.path.dirname(__file__)` (ten sam wzorzec co `data_loader.py`). Patrz `memory/project_deployment_cwd_bug.md` — **sprawdź ten plik, gdy wdrożenie Cloud zachowuje się inaczej niż lokalny dev.**
├── doc_splitter.py      # Segments multi-page PDF into logical documents via `_classify_page_segment()`. Kolejność reguł jest krytyczna i opisana inline w kodzie (obecnie: KOD/nagłówek EPU → art.299→pozew → wniosek egzekucyjny → postanowienie umorzenie egzekucji → pismo procesowe → wyrok zaoczny → warianty tytułu P O Z E W → guard UZASADNIENIE → NAKAZ na początku linii → wezwanie → guard klauzuli wykonalności → guard POUCZENIE → tytuły pism komorniczych z nagłówkiem kancelarii, `_KOMORNIK_TITLES` dopasowywane wg najwcześniejszej pozycji w tekście, NIE kolejności listy → fallback). Kilka kroków post-processingu scala/przemianowuje segmenty: "nuklearne scalanie" zwija cały blok przed pierwszym nakazem w "pozew" (wykrycie KOD jest niestabilne między przebiegami OCR, więc scalanie od tego nie zależy); strony kontynuacji pism komorniczych (bez własnego nagłówka) doklejają się do poprzedniego segmentu komorniczego (`_KOMORNIK_MERGE_TARGETS`, dziś też `postanowienie_umorzenie_egzekucji` i `wyrok_zaoczny`); segment nakaz/pozew wciśnięty między dwa segmenty komornicze scala się w łańcuch komorniczy (OCR transkrybuje boilerplate niespójnie między przebiegami). `_is_evidence_citation()` chroni przed tytułami, które są tylko CYTOWANE w liście dowodów/załączników ("Dowód: wezwanie do zapłaty z dnia...") — okno kontekstu 200 zn. Najbardziej złożone sesje debugowania tego pliku: `memory/project_komornik_boilerplate_deadlines.md`, `memory/project_wyrok_zaoczny.md`.
├── doc_selector.py      # Scores candidates (CSV 02) + tie-breaking (CSV 04) → main document. Kluczowe reguły: NAKAZ wygrywa z POZEW wśród kandydatów, Z WYJĄTKIEM łańcucha art. 299 (nakaz przeciw spółce + wniosek egzekucyjny/umorzenie w paczce + obecny pozew typu _CZLONEK_ZARZADU → pozew jest głównym, nakaz jest historyczny); wśród nakazów wygrywa ten z `deadline_days`. Bundle-level upgrade SPOLKA→CZLONEK_ZARZADU odpala, gdy jakikolwiek dokument paczki wspomina art. 299/członka zarządu, chronione przez `is_company_name(main.pozwany)` (nie podnoś, gdy pozwany dokumentu głównego jest już wyraźnie spółką) I `parties_differ()` (nie pozwól wzmiance z niepowiązanej sprawy w tej samej paczce wywołać upgrade'u). `is_company_name()`/`_COMPANY_FORMS` (współdzielone z bramką art. 299 w app.py i skryptem regresji) rozpoznaje pełne formy spółkowe, nie tylko skróty. Reguły komornicze: pismo "wszczęcie" zawsze wygrywa wybór głównego nad innymi pismami tej samej egzekucji; brakująca kwota głównego dokumentu spada na kwotę innego pisma komorniczego tej samej sygnatury. `normalize_party_name()`/`parties_differ()` (publiczne, przeniesione tu z app.py) porównują nazwy wierzycieli tolerując odwróconą kolejność (`_same_person_reordered`) i pojedynczą literówkę OCR (`_same_person_ocr_typo`, celowo wąska — pomija dwa ostatnie znaki, gdzie polskie końcówki rodzajowe nazwisk typu -ski/-ska legalnie różnią różne osoby). Patrz `memory/project_unrelated_docs_warning.md`.
├── ai_extractor.py      # `extract_fields_ai_with_status(text, api_key) -> (dict, status)` gdzie status to "ok"/"no_key"/"failed" — ekstrakcja AI (Claude Haiku) jest GŁÓWNĄ ścieżką dla sygnatura/sad_organ/powod/pozwany/termin/kwota/adresat/epu/rodzaj_pisma/doc_description/amount_type/wps_amount; regex w doc_extractor.py to tani fallback. `extract_fields_ai()` zostaje jako cienki wrapper (zgodność wsteczna). Kluczowe zasady promptu: pozwany-osoba-fizyczna ZAWSZE implikuje "czlonek_zarzadu" (kalkulator obsługuje wyłącznie sprawy odpowiedzialności członków zarządu, więc podstawa prawna może nie być wprost w piśmie); `kwota_zl` preferuje należność główną nad kwotą łączną, gdy dokument je rozbija (też dla słownictwa egzekucyjnego: "koszty egzekucyjne"/"koszty zastępstwa" → "glowna"); `sad_organ` to WYŁĄCZNIE organ wydający, nigdy sąd rejestrowy ze stopki firmowej nadawcy; `termin_dni` wprost wyklucza termin na skargę na czynność komornika (art. 767 KPC, zwykle 7 dni); `czy_pismo_prawne` jest `False` zarówno dla dokumentów niesądowych (faktury, paragony, przelewy), jak i dla dokumentów SKŁADANYCH przez klienta DO urzędu (własny PIT, wnioski) — nie tylko dla pism OD sądu/komornika/urzędu. `opis_dokumentu` to krótki, zawsze wypełniany opis PO POLSKU tego, czym dokument faktycznie jest — używany generycznie przez baner niesądowy w app.py zamiast hardkodowania etykiety per typ. `wartosc_przedmiotu_sporu_zl`/`kwota_zl_rodzaj` rozróżniają proceduralną wartość WPS od należności głównej. Status ("no_key"/"failed") jest pokazywany przez app.py, żeby placeholder/wygasły klucz API nie udawał po cichu regresji kodu — patrz `memory/project_ai_key_silent_fallback.md`.
├── doc_processor.py     # Orchestrator: returns `ProcessedDocument` dataclass; maps doc_type_code → k1_code via `_DOC_TYPE_TO_K1` (każdy typ dokumentu potrzebujący własnego prefill/etykiety formularza ma własny kod K1 — reużyte-ale-relabelowane typy jak WYROK_ZAOCZNY_* mają WŁASNY kod K1, mimo że `scenario_selector._K1_TO_DOC_TYPE` kieruje je z powrotem na tekst scenariusza NAKAZ_*, żeby widoczna etykieta Kroku 1 i kod w panelu technicznym zgadzały się z rzeczywistym typem dokumentu). `_build_candidate_dict()` woła `extract_fields()` (regex), potem `extract_fields_ai_with_status()` — AI nadpisuje pola regexowe tam, gdzie coś zwróciła, dla KAŻDEGO dokumentu w paczce (nie tylko głównego), PRZED `classify_document()` (więc sygnały AI jak `adresat`/`czy_pismo_prawne`/`splitter_kind`/`rodzaj_pisma` zasilają klasyfikację każdego segmentu). Pliki wgrane pojedynczo (bez podziału wielostronicowego) też wołają `doc_splitter._classify_page_segment()` na całym tekście, żeby `splitter_label`/`splitter_kind` były wypełnione. `on_progress` przekazywany do `ocr_with_fallback()`, zgłasza "Analizuję dokument N/M..."/"Wczytuję plik N/M...". Pola `ProcessedDocument` dodane z czasem: `splitter_label`, `doc_description`, `amount_type`/`wps_amount`, `ai_extraction_status` (domyślnie "ok" — stare/ręczne/testowe konstruowanie bez tego pola działa bez zmian).
│
├── requirements.txt     # All dependencies including pdfplumber, python-docx, Pillow, anthropic, azure-ai-documentintelligence, pytesseract, reportlab (raport PDF, patrz report_builder.py — pure-Python, brak zależności systemowych, działa bez zmian na Streamlit Cloud)
├── assets/              # `favicon.png` (generowany przez tools/generate_favicon.py) i `fonts/` (DejaVu Sans/Serif — regular+bold, dla report_builder.py; LICENSE.txt dołączona). Wyjątek w .gitignore (`!app/assets/*.png`) — to prawdziwe assety aplikacji, nie zrzuty ekranu ze scratchpada.
└── .streamlit/
    ├── config.toml      # Streamlit theme/config
    └── secrets.toml     # LOCAL ONLY (in .gitignore): TEST_PANEL_PASSWORD, ANTHROPIC_API_KEY
```

Poza `app/` istnieje też `tools/`:
```
tools/
├── regression_test.py       # Uruchamia `process_files()` (ta sama ścieżka co aplikacja, z prawdziwym OCR+AI) na plikach testowych i porównuje z `regression_expected.json`; użycie: `python tools/regression_test.py [--dir ...] [--only NAZWA.pdf]`; brakujące pliki → SKIP z ostrzeżeniem. **URUCHAMIAĆ PO KAŻDEJ ZMIANIE w doc_*.py/ai_extractor.py** — to odpowiedź na pytanie "czy poprawka jest ogólna, czy dopasowana do jednego pliku". `DEFAULT_TEST_DIR` czyta zmienną środowiskową `KRS_GUARD_TESTY_DIR` (fallback `C:\Users\User\Desktop\testy`), więc nie trzeba jej ręcznie edytować na innym komputerze. Obsługuje opcjonalne pole `"files"` per wpis JSON — lista plików wgrywanych razem jako jedna paczka; brak pola = domyślnie `[klucz_slownika]`.
└── regression_expected.json # Tabela oczekiwań per plik: main_type (lista akceptowalnych), main_pages, deadline_days, amount (±0,01), aux_types_include, gate, opcjonalnie files; klucz nieobecny = nie sprawdzaj. Znany flaky wpis: `nak.zap.3.pdf` sporadycznie odczytuje kwotę `pozew.pdf` (1380,00 zamiast 1567,33, ta sama sygnatura V GNc 2034/22) — potwierdzona przedistniejąca niestabilność OCR/AI, nie regresja kodu (powtórny test 2/2 PASS).
```

Poza `app/` i `tools/` w repo są też (praca na kilku komputerach):
```
plany/    # Kopie finalnych planów z trybu planowania Claude Code (po polsku) — lokalny plik planu
          # (~/.claude/plans/...) jest per-komputer, więc kontynuacja pracy między komputerami
          # opiera się na kopii w repo, nie na pliku lokalnym.
memory/   # Kopia plików pamięci projektu Claude Code (~/.claude/projects/.../memory/) — ta sama
          # przyczyna: pamięć jest per-komputer, repo jest źródłem prawdy dla ciągłości.
```

### Skille i pluginy Claude Code (08.07.2026)

Skille projektowe instalowane przez `npx skills add <github-repo> --skill <nazwa>` żyją W REPO
(commitowane — dostępne na obu komputerach bez rekonfiguracji):
```
.agents/skills/    # Źródło zarządzane przez npx skills (uniwersalne dla wielu agentów)
.claude/skills/    # Miejsce, z którego czyta Claude Code; npx tworzy tu symlink do .agents/,
                   # ale git na Windows (core.symlinks=false) rozwija go do zwykłych plików —
                   # celowo tak zostawione, bo kopia działa po checkout na drugim komputerze,
                   # a symlink z absolutną ścieżką by się tam zepsuł.
skills-lock.json   # Rejestr zainstalowanych skilli (źródło + hash). UWAGA: `npx skills remove`
                   # usuwa pliki skilla, ale NIE czyści jego wpisu tutaj — trzeba ręcznie.
.claude/settings.json  # `enabledPlugins` — pluginy włączone dla projektu (współdzielone przez repo).
```
Zainstalowane skille: `frontend-design` (anthropics/skills — wskazówki projektowania UI),
`find-skills` (vercel-labs/skills — meta-skill: wyszukiwanie/instalacja kolejnych skilli;
proponowane przez niego instalacje weryfikować przed uruchomieniem),
`developing-with-streamlit` (streamlit/agent-skills, oficjalny — wszystkie zadania Streamlit
w app.py; ma skrypt discover.py ładujący docsy zgodne z zainstalowaną wersją Streamlita),
`regex-vs-llm-structured-text` (affaan-m/everything-claude-code — framework decyzyjny
regex vs LLM przy parsowaniu tekstu; dokładnie oś architektury doc_extractor.py/ai_extractor.py),
`prompt-engineering-patterns` (wshobson/agents — wzorce promptów; do rozwoju promptu
ekstrakcyjnego w ai_extractor.py),
`agent-browser` (vercel-labs/agent-browser — automatyzacja przeglądarki CLI:
klikanie/formularze/zrzuty ekranu, przydatne do testowania aplikacji Streamlit na żywo;
UWAGA: SKILL.md to tylko stub — wymaga globalnego CLI `npm i -g agent-browser &&
agent-browser install`, a właściwe instrukcje ładuje się przez `agent-browser skills get core`).
Włączone pluginy: `document-skills@anthropic-agent-skills` (xlsx/docx/pptx/pdf),
`claude-api@anthropic-agent-skills`.
Historia: `vercel-react-best-practices` zainstalowany i usunięty (dotyczy React/Next.js,
projekt jest Python+Streamlit); plugin `frontend-design@claude-plugins-official` odinstalowany
jako duplikat wersji skillowej (pluginy projektowe odinstalowuje się
`claude plugin uninstall <nazwa> --scope project` — domyślny scope to user i wtedy komenda zawodzi).

**To run locally:**
```bash
cd app
streamlit run app.py
```
IMPORTANT: run from inside `app/`, not the repo root. Streamlit resolves
`secrets.toml` relative to the **invocation cwd**, not the script's directory —
`streamlit run app/app.py` from the repo root fails with
`StreamlitSecretNotFoundError` because it looks for `<repo-root>/.streamlit/secrets.toml`
instead of the real `app/.streamlit/secrets.toml` (see `memory/project_progress_indicator.md`).

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

**Weryfikacja synchronizacji CSV ↔ Excel**: Mapowanie CSV → arkusz Excel przez auto-detekcję z nazwy pliku (usuń prefix `NN_` i `.csv`; uwaga: nazwy CSV bez polskich znaków, arkusze z nimi — np. `14_7_Instrukcja_dzialania_AI.csv` → arkusz `7_Instrukcja_działania_AI`). Ostatni pełny audyt: 03.07.2026 (porównanie komórka po komórce) — 41/41 plików zsynchronizowanych. ZASADA: nie używać średnika WEWNĄTRZ treści komórek arkuszy eksportowanych do CSV (średnik to separator CSV).

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
| `4_Formularz_6_krokow` | `08_…csv` | Form questions, answer codes, labels. K1 zawiera opcje komornicze (`K1_PISMO_KOMORNIK_SPOLKA`/`_CZLONEK_ZARZADU`, C=2/C=3 w CSV 09) i `K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU` (C=2, celowo bez odpowiednika dla spółki — Typ 1 obsługiwany w app.py przez ostrzeżenie, nie przez K1) |
| `5_Punktacja_formularza` | `09_…csv` | C/P/H/W point values per answer |
| `5A_Interpretacja_wyniku` | `10_…csv` | Score-to-risk-level mapping |
| `5B_Twarde_reguly` | `11_…csv` | Hard safety rules that override the score |
| `6_Biblioteka_scenariuszy` | `12_…csv` | Base scenario texts (221 scenarios, w tym pełne pokrycie K2×ryzyko dla PISMO_KOMORNIK_SPOLKA/_CZLONEK_ZARZADU i WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU) |
| `6A_Moduly_K3_K6` | `22_…csv` | Contextual text modules for K3–K6 answers |
| `6D`–`6U` | `24–41_…csv` | Contextual rules: deadline, EPU, KRS, claim amount, ZUS, unknown doc |
| `10_Testy_kontrolne` | `17_…csv` | Regression test cases |
| `14_Kontrola_jakosci` | `21_…csv` | Quality control checklist |

## Git workflow

After every meaningful change — new file, updated spec, working feature, config change — commit and push to GitHub:

```bash
git add <specific files>
git commit -m "short description of what changed and why"
git push origin main
```

Use clear, descriptive commit messages in English or Polish (match the language of the changed content). Never bundle unrelated changes into one commit.

Jedna gałąź (`main`) — patrz "Branch strategy" wyżej. Nie ma już osobnej gałęzi `etap2`.

## Test documents

Test files live in `C:\Users\User\Desktop\testy\` (outside the repo — **always
check this folder for current test files before diagnosing a bug**; files
have occasionally gone missing/reappeared between sessions for an unexplained
reason, not a disk-space issue). Expected values per file are tracked in
`tools/regression_expected.json`; below is what each file is *for*, not its
debugging history (that lives in `memory/*.md`, see `MEMORY.md` index, and in
`memory/session_2026-07-15_full_regression.md` specifically).

- `Lublin_nakaz_zapłaty_pko.pdf`/`.jpeg`, `Lublin_pozew_pko.pdf` — one EPU case (PKO Bank Polski S.A. vs Piotr Czak, VI Nc-e 1245792/25), nakaz + pozew. Expected: `EPU_NAKAZ_CZLONEK_ZARZADU`/`EPU_POZEW_CZLONEK_ZARZADU`, 81 922,78 zł (należność główna; 85 463,92 = łączna), 14 dni, gate yes.
- `Lublin_pozew_nak._zap..pdf` — 8-str. skan, pozew (Krzysztof Knop vs Piotr Czak) + nakaz EPU; main=nakaz str.5-7 (14 dni, VI Nc-e 222431/23, 5 267,77 zł), aux=pozew, gate yes.
- `Lublin_pozew_nak._zap.2.pdf` — pozew+nakaz przeciw spółce (WOODHOME sp. z o.o., nie członek zarządu); aux poprawnie `EPU_POZEW_SPOLKA`; kwota 10 530,00 zł (główna; 11 286 = WPS).
- `nakaz_zapłaty+pozew.pdf` — nakaz "zwykły", nie EPU (V GNc 1235/22/S, Woodhome sp. z o.o., 34 230,43 zł) + jego pozew; main=nakaz str.1-7, 14 dni.
- `Nakaz_zapłaty+pozew+przes_wez._do_zap..pdf` — ta sama sprawa + przedsądowe wezwanie do zapłaty (własny termin) jako trzeci, pomocniczy dokument; weryfikuje poprawną sub-klasyfikację (`WEZWANIE_PRZEDSADOWE_SPOLKA`, nie sądowe) i że badge "WYMAGA REAKCJI" pokazuje się tylko przy głównym.
- `art299_pozew_nakaz_umorz._egzek..pdf` — 13-str. łańcuch art. 299: pozew (2023, żywa sprawa, członkowie Duda/Czak/Duda) jest główny; historyczny nakaz (2020) + wniosek egzekucyjny + postanowienie o umorzeniu są pomocnicze. Weryfikuje regułę "nakaz zwykle wygrywa, poza łańcuchem art. 299".
- `potwierdzenie opłaty prolongacyjnej za grób.PDF` — przelew bankowy, bez związku z żadną sprawą. Weryfikuje wykrycie `DOKUMENT_NIEPRAWNY` (nie `ODPIS_KRS` z przypadkowego słowa "zarząd") i baner/opt-in formularza.
- `art.299_pozew.pdf` — pojedynczy 6-str. pozew art. 299 (ATTIC sp. z o.o. vs Piotr Czak, 19 142,36 zł); kanarek regresji dla guardu cytowań dowodowych (linia listy załączników zaczynająca się od "wezwanie do zapłaty" nie może odciąć się jako osobny dokument).
- `egzekucja+zaj._rach.+wyk._majatku.pdf` — 18-str., 7 pism jednej egzekucji (GKm 62/22, WOODHOME sp. z o.o., 111 169,63 zł główna). Kanarek dla segmentacji/etykietowania pism komorniczych i ścieżki K1 "Pismo komornicze"; main = pismo o wszczęciu (str.1-4), nie pismo z najbliżej wyglądającym terminem.
- `nakaz_zapłaty.pdf` — sądowe pismo przewodnie doręczające nakaz (str.1-4) + sam nakaz (str.5, 2 331,59 zł, 14 dni). Kanarek dla segmentacji `doreczenie_sadowe` (pismo przewodnie nie może wygrać wyboru głównego z prawdziwym nakazem).
- `przed._wez_do_zap..pdf` — przedsądowe wezwanie ubezpieczyciela InterRisk do spółki (1 003,00 zł główna; 1 106,44 łączna), bez wątku członka zarządu. Kanarek dla ekstrakcji kwoty głównej vs łącznej i banera "ryzyko pośrednie" spółki.
- `pismo_przygotowawcze_kontynuacja.pdf` / `art.299_pismow_przygot._powoda.pdf` — pisma przygotowawcze cytujące art. 299 w toczącej się sprawie; kanarki dla klasyfikacji `PISMO_PROCESOWE_SADOWE` (nie może wyjść jako świeży pozew tylko dlatego, że cytuje żądanie).
- `299_przeds._wezw._do_zap..pdf` — przedsądowe wezwanie powołujące się wprost na art. 299 KSH przeciw członkowi zarządu (MIPROMET sp. z o.o. vs Piotr Czak, 1 067,03 zł, 3 dni). Kanarek dla `K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU` i `_NO_GATE_TYPES` (bramka NIE może ponownie pytać o to, co dokument już rozstrzygnął).
- `przeds._wezw._do_zap2.pdf` — przedsądowe wezwanie do spółki bez wątku art. 299 (Instal Lux vs Woodhome, 10 296,00 zł); kanarek dla `_SPOLKA_OUT_OF_SCOPE_TYPES` (K1 celowo zostaje `K1_INNE_NIE_WIEM`).
- `wyrok.pdf` — wyrok zaoczny, nie nakaz (WOODHOME sp. z o.o., 51 408,00 zł, 14 dni, rygor natychmiastowej wykonalności). Kanarek dla `WYROK_ZAOCZNY_SPOLKA`/jego własnego kodu K1 (reużywa tekst scenariusza NAKAZ_SPOLKA z podmianą nazwy dokumentu, ale nie może wyciekać `K1_NAKAZ_SPOLKA` do UI).
- `postanowienie.pdf` — postanowienie sądu rejestrowego KRS o rozwiązaniu nieaktywnej spółki bez likwidacji (brak powoda, brak kwoty). Kanarek dla `POSTANOWIENIE_KRS_Z_URZEDU` i opt-in formularza (formularz nie może wyglądać jak oczekiwany kolejny krok, gdy kalkulator nie ma czego ocenić).
- `KS_postanowienie.pdf` — postanowienie komornika o podjęciu zawieszonego postępowania (Km 449/24, osoba fizyczna); sentencja mówi wyłącznie "podjąć zawieszone postępowanie". Kanarek dla guardu terminu boilerplate'owego (termin ze skargi na czynność komornika, art. 767 KPC, nie może wyjść jako `deadline_days`) i łagodniejszego banera "wznowienie, nie nowe żądanie".
- `pit_2025.pdf` — własne 15-str. zeznanie PIT-36 (natywny PDF, brak danych sprawy). Kanarek dla backstopu "wszystkie pola identyfikujące puste" + deterministycznego early-return dla formularzy PIT (sam backstop jest niemiarodajny na długich dokumentach — raw score potrafi trafić dokładnie na granicę progu z samej objętości).
- `pozew_o_zapłate_pko.pdf` — ta sama sprawa PKO co `Lublin_pozew_pko.pdf`; kanarek dla etykiety rodzaju kwoty (`amount_type="glowna"`, `wps_amount≈85464.00`).
- `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf` — najbardziej złożony plik w zestawie: 20-str. paczka łącząca wyrok zaoczny z 7-pisemnym łańcuchem komorniczym (GKm 87/22, Faliszewska Barbara vs WOODHOME sp. z o.o.), potwierdzona struktura 8 dokumentów `[1-4][5-6][7-8][9-10][11-12][13-14][15-16][17-20]`. Kanarek dla: segmentacji wyroku zaocznego wewnątrz paczki komorniczej, rozdzielenia dwóch sąsiadujących pism komorniczych mimo zniekształconych OCR nagłówków, i tolerowania przez ostrzeżenie "różne sprawy" odwróconej kolejności nazwiska ORAZ pojedynczej literówki OCR bez mylenia naprawdę różnych osób (np. "Wiśniewska"/"Wiśniewski"). Jedna świadomie nienaprawiona luka: literówka OCR + reorder tokenów RAZEM w jednym przypadku nie zawsze jest łapana — patrz `memory/project_unrelated_docs_warning.md` po uzasadnienie, czemu szerszy fuzzy-match odrzucono (zamazałby naprawdę różne osoby o nazwiskach różniących się końcówką rodzajową).

### Ekstrakcja AI jako główna ścieżka (od 01.07.2026)
Po czterech z rzędu przypadkach "nowy dokument = nowa gramatyczna odmiana formuły, której regex nie przewidział", `doc_processor.py` przełączył się na Claude Haiku (`ai_extractor.extract_fields_ai()`) jako GŁÓWNĄ ścieżkę ekstrakcji dla każdego dokumentu w paczce; regex w `doc_extractor.py` jest tanim fallbackiem. Koszt ~$0,001-0,002/dokument. Prompt mówi wprost, że kalkulator obsługuje wyłącznie sprawy odpowiedzialności członków zarządu, więc pozwany-osoba-fizyczna zawsze implikuje "czlonek_zarzadu", nawet gdy dany dokument nie wymienia art. 299 wprost (wcześniejszy, bardziej restrykcyjny prompt dawał regresję na `Lublin_pozew_pko.pdf`, który nie wspomina art. 299 bezpośrednio).

## Zasady pracy Claude Code w tym projekcie

### Synchronizacja dokumentacji (obowiązkowe)
- **Po każdej zmianie kodu lub danych**: zaktualizuj CLAUDE.md (sekcja doc_*.py, test documents) oraz odpowiedni plik w `memory/` (patrz indeks `memory/MEMORY.md` — osobny plik per temat, nie jeden monolityczny plik stanu) — jeszcze w tej samej sesji, przed commitem. CLAUDE.md ma opisywać BIEŻĄCY stan zwięźle (kilka zdań na moduł) — szczegółową narrację ("kto zgłosił, jaki zrzut ekranu, ile razy zweryfikowano") trzymaj w `memory/`, nie tutaj, żeby plik nie rósł bez końca.
- **Nie czekaj do końca rozmowy** z aktualizacją dokumentacji — rób to na bieżąco po każdym zakończonym kroku.

### Ostrzeżenie o limicie tokenów
Przed przystąpieniem do zadania, które może wymagać dużej liczby tokenów (wiele plików, skomplikowane refaktoryzacje, analizy wielu arkuszy), pokaż użytkownikowi ostrzeżenie:

```
⚠️ OSTRZEŻENIE: To zadanie może być długie (szacuję: [liczba] plików / [zakres] zmian).
Jeśli rozmowa zostanie przerwana z powodu limitu, zrób checkpoint — zatrzymaj się i powiedz
co zostało zrobione, a co jeszcze pozostaje. Kontynuować?
```

Próg ostrzeżenia: zadanie dotyka >4 plików LUB >80 linii kodu do zmiany LUB >3 arkuszy CSV/Excel jednocześnie.

### Ciągłość pracy między komputerami (obowiązkowe, od 07.07.2026)
Użytkownik pracuje na kilku komputerach. Pliki trybu planowania
(`~/.claude/plans/...`) i pamięć projektu (`~/.claude/projects/.../memory/`)
są zapisywane **lokalnie, per komputer** — bez poniższych zasad kontynuacja
pracy gubi się przy zmianie komputera.

- **Plany**: po zaakceptowaniu planu (koniec trybu plan mode), skopiuj jego
  finalną treść do `plany/<opisowa-nazwa>.md` w repo i zacommituj razem z
  resztą zmian tej sesji (albo od razu, jeśli implementacja się jeszcze nie
  zaczyna). Lokalny plik planu zostaje jak jest — to mechanizm harnessu — ale
  kopia w `plany/` jest źródłem prawdy dla kontynuacji między komputerami.
- **Pamięć**: po każdej aktualizacji pliku w `~/.claude/projects/.../memory/`,
  skopiuj ten sam plik do `memory/` w repo i zacommituj. `memory/MEMORY.md`
  w repo ma być zawsze aktualną kopią lokalnego indeksu pamięci.
- **Na starcie sesji**: jeśli lokalna pamięć/plany różnią się od tego, co
  jest w `plany/`/`memory/` w repo (bo poprzednia sesja toczyła się na innym
  komputerze) — repo wygrywa, zsynchronizuj z niego do lokalnego magazynu.
  Jeśli użytkownik odwołuje się do "ostatniego planu"/kontynuacji, sprawdź
  najpierw `plany/` i `memory/` w repo (posortowane po dacie modyfikacji),
  nie tylko lokalne katalogi.
- **Nie commituj** surowych logów sesji (`~/.claude/projects/.../*.jsonl`,
  `subagents/`, `tool-results/`) — to nieustrukturyzowane transkrypty
  rozmów, potencjalnie duże i wrażliwe, nie "pamięć" w sensie użytecznym dla
  kontynuacji. Tylko pliki `.md` z folderu `memory/` mają trafiać do repo.

## Communication rules (non-negotiable)

- Never show technical codes (K1–K7, RISK_*, HRxx, scenario_id) to the client
- Never use the word "użytkownik" in client-facing output; use "W formularzu wskazano…", "Zaznaczono…", "Na tym etapie…"
- Never generate "sprzeciw od nakazu" or "odpowiedź na pozew" for ZUS/agency letters — only "złożenie wyjaśnień"
- Always state that deadlines include weekends and holidays ("wliczają się soboty, niedziele i dni świąteczne")
- If a specific day count is available, show the exact number — never a range
- End every result with a CTA toward Audyt 48h without using hard-sell language
