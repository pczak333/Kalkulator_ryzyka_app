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
├── app.py               # Streamlit entry point — UI, form flow, result display
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
├── doc_extractor.py     # Regex extraction: EPU signals, delivery date, deadline (also word-form: "dwóch tygodni"), amount, addressee (header-only detection + post-correction); powód/pozwany extracted from parties_text only (before UZASADNIENIE/POUCZENIE — prevents grabbing parties from plea body); sygnatura rejects Km/KM prefix (bailiff reference) oraz prefiksy faktur FV/FA/F-VAT/FAKTURA (`_SYGNATURA_EXCLUDE_RE`, myląco pasują do wzorca sygnatury); new Nc-e pattern for long EPU case numbers; _KWOTA_PATTERNS ma dedykowany wzorzec "Wartość przedmiotu sporu" (najwyższy priorytet w pozwie) oraz "kwotę łączną" (nakaz) — oba warianty tolerują "l" zamiast "ł" (częsty artefakt OCR); `_find_deadline_near_keyword()` (01.07.2026) wybiera w oknie ±800 zn. wokół słowa kluczowego NAJBLIŻSZY (najwcześniejszy w oknie) wzorzec terminu z `_TERMIN_WRITTEN`, nie pierwszy wg kolejności listy (lista była posortowana wg długości terminu, 90 dni pierwsze — błędnie wygrywało z bliższym i poprawnym "w terminie dwóch tygodni", gdy okno obejmowało też sąsiedni fragment pouczenia o doręczeniu zagranicznym "w terminie trzech miesięcy"); to samo dla fallbacku "Przebieg 2" na całym tekście
├── doc_classifier.py    # Classifies document type using keywords from CSV 07; bonus/penalty logic: +20 for "nakazuję pozwanemu" → NAKAZ, +20 for "wnosimy o"/"P O Z E W" → POZEW (bonus replaces old penalty — OCR-resilient); early return PISMO_PROCESOWE_SADOWE when UZASADNIENIE in head_500; no module-level CSV cache (always reads fresh)
├── doc_splitter.py      # Segments multi-page PDF into logical documents via _classify_page_segment(); rule order (CRITICAL): Rule 0 (KOD [hash] — EPU form code, only on EPU header, never in uzasadnienie) → Rule 1 (art.299→pozew) → Rule 5a (P O Z E W before Rule 2!) → Rule 5a' (P O Z E W anywhere) → Rule 2d (UZASADNIENIE guard→None) → Rule 2/2b (NAKAZ at line-start (?m)^\s* within 200 chars — strict to avoid false-positives from pozew body text) → Rule 3 (wezwanie) → Rule 4 (POUCZENIE→None) → Rule 5b (POZEW, full text) → Rule 6 (fallback); Rule 2c REMOVED; post-processing: Krok 0 upgrades unknown→pozew if [unknown→nakaz_noKOD→nakaz_KOD]; Krok 1 nuclear: scala CAŁY blok przed PIERWSZYM segmentem typu nakaz (niezależnie od tego, czy KOD został wykryty!) w jeden "pozew" — granica oparta na KOD okazała się krucha (różne silniki OCR różnie transkrybują linię "KOD [hash]"; gdy żaden segment nakazu nie ma wykrytego KOD, merge w ogóle się nie uruchamiał i cały pozew ginął w filtrze "unknown"). KEY INSIGHT: Lublin_pozew_nak._zap..pdf jest SKANOWANY — pdfplumber=0 tekstu, Azure DI robi OCR; str.4 (tabela dowodów) ma "Wezwanie do zapłaty" jako tytuł dowodu → Rule 3 odpala → segment wezwanie; nuclear merge to naprawia niezależnie od etykiety. `_is_evidence_citation()` (nowa funkcja, 01.07.2026): sprawdza ~40 znaków PRZED dopasowaniem "WEZWANIE DO ZAPŁATY" pod kątem etykiety "Dowód:" lub wypunktowania ("-"/"–"/"—"/"•") — jeśli fraza jest cytowaniem dowodu/załącznika (np. w uzasadnieniu pozwu: "Dowód: wezwanie do zapłaty z dnia..." albo w liście "W załączeniu przedkładam: - wezwanie do zapłaty..."), NIE klasyfikuje strony jako osobne "Wezwanie do zapłaty". Guard zastosowany zarówno w Rule 3, jak i w fallback Rule 6 (`_PAGE_DOC_PATTERNS`) — to Rule 6 (bez kotwicy początku linii) był faktyczną przyczyną błędu, nie Rule 3.
├── doc_selector.py      # Scores candidates (CSV 02) + tie-breaking (CSV 04) → main document; hard rules: (1) any NAKAZ always wins over POZEW — zastosowane BEZWARUNKOWO gdy oba typy współistnieją wśród kandydatów (01.07.2026: wcześniej reguła sprawdzała tylko czy best_doc akurat jest pozwem — przy remisie punktowym nakaz+pozew trafiały do `_tiebreak()`, gdzie R1 (adresat) sprawdzany jest PRZED R3 (nakaz>pozew) i mógł błędnie wybrać pozew, gdy jego adresat jest źle sklasyfikowany — patrz znana niespójność SPOLKA/CZLONEK_ZARZADU w doc_classifier.py); (2) among nakazy, nakaz WITH deadline_days wins over nakaz without (prevents misclassified uzasadnienie pages from beating actual EPU nakaz) — teraz scalone w regułę (1); R17 scoring fires for deadline_days alone (no delivery_date needed); bundle upgrade: SPOLKA→CZLONEK_ZARZADU when art.299 OR "czlonek zarządu" found in any bundle doc
├── doc_processor.py     # Orchestrator: returns ProcessedDocument dataclass; maps doc_type_code → k1_code via _DOC_TYPE_TO_K1
│
├── requirements.txt     # All dependencies including pdfplumber, python-docx, Pillow, anthropic, azure-ai-documentintelligence, pytesseract
└── .streamlit/
    ├── config.toml      # Streamlit theme/config
    └── secrets.toml     # LOCAL ONLY (in .gitignore): TEST_PANEL_PASSWORD, ANTHROPIC_API_KEY
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

**Weryfikacja synchronizacji CSV ↔ Excel**: Mapowanie CSV → arkusz Excel przez auto-detekcję z nazwy pliku (usuń prefix `NN_` i `.csv`). Ostatni audyt: 27.06.2026 — 41/41 plików zsynchronizowanych.

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
- `Lublin_pozew_nak._zap.2.pdf` — nowszy wariant tego samego typu bundla (4 str.: pozew str.1-2, nakaz str.3-4); VI Nc-e 1707736/22, Marcin Pycek vs WOODHOME sp. z o.o. (SPÓŁKA, nie członek zarządu — pozwanym jest sama spółka); "Wartość przedmiotu sporu 11 286,00 PLN" na str.1 pozwu. Ujawnił 01.07.2026: (1) segmentacja gubiła str.1 pozwu gdy Rule 0 (KOD) nie wykryła nakazu — naprawione uogólnieniem Kroku 1 (patrz doc_splitter.py wyżej); (2) ekstraktor kwoty łapał wartość faktury z listy dowodów zamiast "Wartość przedmiotu sporu"/"kwotę łączną" — naprawione nowymi wzorcami w `_KWOTA_PATTERNS`; (3) ekstraktor sygnatury łapał numer faktury "FV 135/2021" — naprawione `_SYGNATURA_EXCLUDE_RE`; (4) kaskada OCR nie eskalowała do Claude Haiku przy niskiej jakości Azure — naprawione (patrz doc_ocr.py wyżej). ZNANY, NIENAPRAWIONY problem: ekstrakcja powód/pozwany dla dokumentów typu NAKAZ zwraca pogubiony tekst (chwyta fragment zdania z formuły "nakazuje pozwanemu...", nie samą nazwę) — występuje też w pozostałych plikach testowych z nakazem, więc to niezależny, przedistniejący bug w doc_extractor.py, nie regresja z tej sesji. Dodatkowo: dla tego pliku dokument pomocniczy (Pozew) klasyfikuje się jako `EPU_POZEW_CZLONEK_ZARZADU` mimo że pozwanym jest spółka (powinno być `EPU_POZEW_SPOLKA`, tak jak dokument główny) — niespójność do zbadania osobno w doc_classifier.py.
- `nakaz_zapłaty+pozew.pdf` — 12 stron: nakaz str.1-7 (str.2/8 puste — plik drukowany dwustronnie i zeskanowany), pozew str.9-11 (str.10 pusta); Sąd Rejonowy dla Krakowa-Śródmieścia V Wydział Gospodarczy (NIE EPU/e-sąd — postępowanie "zwykłe"); Sygn. V GNc 1235/22/S; powód: Mariusz Szewłoga; pozwany: Woodhome sp. z o.o.; kwota: 34 230,43 zł (nakaz) / 34 231,00 zł (wartość przedmiotu sporu pozwu). Ujawnił 01.07.2026: str.11 (uzasadnienie pozwu + lista załączników) błędnie klasyfikowana jako osobny dokument "Wezwanie sądowe", bo str.11 wymienia "Dowód: wezwanie do zapłaty z dnia..." oraz w liście załączników "- wezwanie do zapłaty z dnia..." — to CYTOWANIA dowodu/załącznika, nie nagłówek strony. Prawdziwa przyczyna: Rule 6 (fallback `_PAGE_DOC_PATTERNS`, wzorzec bez kotwicy początku linii, przeszukiwany w pierwszych 2000 zn.) dopasowywał frazę gdziekolwiek — nie Rule 3 (ta poprawnie odrzucała dzięki kotwicy `^\s*`, ale mogłaby zawieść przy innym łamaniu linii przez inny silnik OCR). Naprawione `_is_evidence_citation()` — patrz doc_splitter.py wyżej. Dodatkowo naprawiono (01.07.2026, ta sama sesja): `deadline_days` dla nakazu pokazywał 90 zamiast 14 — ekstraktor terminu łapał "w terminie trzech miesięcy" (klauzula o doręczeniu zagranicznym w pouczeniu) zamiast bliższego, poprawnego "w terminie dwóch tygodni od doręczenia nakazu"; naprawione w `_find_deadline_near_keyword()` (wybór najbliższego, nie pierwszego wg listy, dopasowania — patrz doc_extractor.py wyżej). Naprawa terminu podniosła punktację nakazu do remisu z pozwem, co ujawniło DRUGI błąd: `doc_selector.py`'s hard rule "nakaz>pozew" nie obejmowała remisu punktowego, więc `_tiebreak()` (R1: adresat) błędnie wybierał pozew (jego adresat błędnie "czlonek_zarzadu" — ta sama niespójność SPOLKA/CZLONEK_ZARZADU) — naprawione uczynieniem reguły nakaz>pozew bezwarunkową (patrz doc_selector.py wyżej). Po obu poprawkach: main=NAKAZ_SPOLKA str.1-7 deadline_days=14, aux=POZEW_CZLONEK_ZARZADU str.9-11 — zweryfikowane, 5/5 testów regresji bez zmian. ZNANA, NIENAPRAWIONA niespójność (osobna od powyższych): aux nadal klasyfikuje się jako `POZEW_CZLONEK_ZARZADU` mimo że pozwanym jest spółka — to samo źródło co niespójność opisana w `Lublin_pozew_nak._zap.2.pdf` powyżej, do naprawy w `doc_classifier.py`.

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
