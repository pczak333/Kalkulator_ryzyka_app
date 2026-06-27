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
├── doc_ocr.py           # OCR kaskada: Azure Document Intelligence → Tesseract (pol) → Claude Haiku (ostatni resort)
├── doc_extractor.py     # Regex extraction: EPU signals, delivery date, deadline (also word-form: "dwóch tygodni"), amount, addressee (header-only detection + post-correction: if "Pozwany:" header section has no company form but adresat="spolka", corrects to "czlonek_zarzadu" — prevents plaintiff's "S.A." from polluting addressee detection)
├── doc_classifier.py    # Classifies document type using keywords from CSV 07; uses sad_organ to disambiguate court vs. bailiff; no module-level CSV cache (always reads fresh)
├── doc_selector.py      # Scores candidates (CSV 02) + tie-breaking (CSV 04) → main document
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
- `Lublin_nakaz_zapłaty_pko.pdf` — EPU nakaz zapłaty (VI Nc-e 236/25, Sąd Rejonowy Lublin-Zachód); powód: PKO Bank Polski S.A.; pozwany: PIOTR CZAK; kwota: 80 460,82 zł; termin: 14 dni; should classify as `EPU_NAKAZ_CZLONEK_ZARZADU`
- `Lublin_pozew_pko.pdf` — EPU pozew o zapłatę (VI Nc-e 1245792/25, Sąd Rejonowy Lublin-Zachód); powód: PKO Bank Polski S.A.; pozwany: PIOTR CZAK; kwota: 85 463,92 zł; tytuł dokumentu: "P O Z E W" (ze spacjami); should classify as `EPU_POZEW_CZLONEK_ZARZADU`; triggered fix: penalizacja EPU_NAKAZ gdy brak "nakazuję pozwanemu"
- `obraz1.png` — aktualny zrzut ekranu z wynikiem analizy w aplikacji

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
