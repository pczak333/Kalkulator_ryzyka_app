# Naprawa: przedsądowe wezwania do zapłaty (Typ 1 sp. z o.o. vs Typ 2 art.299)

## Kontekst

Użytkownik zgłosił dwa powiązane, ale różne problemy dot. przedsądowych
wezwań do zapłaty:

**Typ 2 — `WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU`** (wezwanie powołujące się
na art. 299 KSH, skierowane do byłego/obecnego członka zarządu, plik
`299_przeds._wezw._do_zap..pdf`): dokument jest już poprawnie
**klasyfikowany** — panel techniczny to potwierdza (pewność 0.52,
`Status: GLOWNY`). Mimo to Krok 1 formularza pokazuje "Inne / nie wiem",
a ocena ryzyka twierdzi "Rodzaj pisma nie został jednoznacznie ustalony" —
sprzeczność między panelem technicznym a wynikiem (zrzuty obraz1-4).

**Przyczyna (zweryfikowana w kodzie):** `WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU`
nigdy nie dostało własnego kodu K1 (CSV 08), wpisu w `_DOC_TYPE_TO_K1`
(`app/doc_processor.py:17-37`, oba warianty spadają na domyślne
`"K1_INNE_NIE_WIEM"`, linie 155/340), wpisu w `_K1_TO_DOC_TYPE`
(`app/scenario_selector.py:7-29`), punktacji (CSV 09) ani scenariuszy
(CSV 12). To ten sam wzorzec błędu, naprawiony wcześniej dla pism
komorniczych (05.07.2026) — rozwiązanie jest analogiczne.

**Typ 1 — `WEZWANIE_PRZEDSADOWE_SPOLKA`** (zwykłe wezwanie do zapłaty za
fakturę, skierowane do spółki, bez art. 299 — pliki `przed._wez_do_zap..pdf`,
`przeds._wezw._do_zap2.pdf`): użytkownik zdecydował, że kalkulator **nie
powinien pchać tego typu w pełną analizę ryzyka** — to zwykła sprawa
handlowa spółki, niepowiązana (na tym etapie) z osobistą odpowiedzialnością
członka zarządu. Ostateczna decyzja: **miękkie ostrzeżenie, formularz
pozostaje dostępny pod spodem — dokładnie ten sam mechanizm, co dziś dla
`DOKUMENT_NIEPRAWNY`/`ODPIS_KRS`** (`_NON_LEGAL_MAIN_TYPES` w `app.py`),
tylko z innym, trafnym tekstem (to REALNE pismo, tylko nie o odpowiedzialność
osobistą — inaczej niż np. potwierdzenie przelewu).

**Wniosek:** Typ 1 wymaga WYŁĄCZNIE zmiany w `app.py` (nowy branch
ostrzeżenia, wzorem istniejącego). Typ 2 wymaga pełnej ścieżki K1 →
punktacja → scenariusze, analogicznie do pism komorniczych.

Wszystko inne działa już poprawnie i nie wymaga zmian: klasyfikator (słowo
kluczowe "art. 299 KSH" + bonus adresata odróżniają oba warianty), bramka
art. 299 (uruchamia się jednolicie dla każdego `_CZLONEK_ZARZADU` — **bez
zmian**, potwierdzone przez użytkownika), baner "dokument dotyczy spółki"
(nadal odpala się dla innych typów `_SPOLKA`, np. nakaz/pozew/komornik —
Typ 1 dostanie teraz odrębne, bardziej bezpośrednie ostrzeżenie zamiast
tego ogólnego banera).

**Potwierdzona waga Typu 2:** C=2 w CSV 09 (jak "Wezwanie sądowe (członek
zarządu)") — poważne, bezpośrednio wymierzone w osobę, ale to jeszcze nie
dokument sądowy.

⚠️ To zadanie dotyka CSV 08/09/12 + Excel (synchronizacja obowiązkowa per
CLAUDE.md) + 3 pliki Python + regression_expected.json + CLAUDE.md + memory.
To przekracza próg ostrzeżenia z CLAUDE.md (>4 plików) — checkpoint po
każdym kroku, dokumentacja aktualizowana na bieżąco.

## Kroki implementacji

### A. Typ 1 (WEZWANIE_PRZEDSADOWE_SPOLKA) — tylko `app/app.py`

1. Dodać nowy zbiór obok `_NON_LEGAL_MAIN_TYPES` (linia ~89), np.
   `_SPOLKA_OUT_OF_SCOPE_TYPES = {"WEZWANIE_PRZEDSADOWE_SPOLKA"}` — osobny
   od `_NON_LEGAL_MAIN_TYPES`, bo to jest realne pismo prawne (nie
   "niezwiązane ze sprawą"), tylko poza zakresem oceny ryzyka osobistego.
2. W `_show_doc_summary()` (~linia 297) rozszerzyć warunek obok
   `_is_non_legal_main` o nowy branch z odrębnym, trafnym tekstem, np.:
   "**Ten dokument dotyczy zobowiązania spółki, a nie odpowiedzialności
   osobistej członka zarządu.** Przesłane pismo to przedsądowe wezwanie do
   zapłaty skierowane do spółki — nie zawiera odniesienia do
   odpowiedzialności osobistej z art. 299 KSH. Ten kalkulator ocenia
   wyłącznie ryzyko osobiste członków zarządu. **Co można zrobić:** jeśli
   egzekucja wobec spółki okazała się już bezskuteczna albo sprawa dotyczy
   też członka zarządu, prześlij właściwy dokument — albo wypełnij
   formularz poniżej ręcznie."
   Ten branch zastępuje w tym przypadku generyczny baner "dotyczy spółki"
   (CSV 35) — jest bardziej bezpośredni, bo tu nie ma jeszcze żadnego
   postępowania w toku, w przeciwieństwie do nakazu/pozwu/komornika
   przeciwko spółce.
3. Wzorem `_NON_LEGAL_MAIN_TYPES`: ukryć tabelę odczytu (sygnatura/kwota/
   termin), ukryć expander "Popraw dane odczytu", wyzerować
   amount/k7_code/deadline_days/delivery_date/epu po `process_files()` —
   ten sam mechanizm co dla `DOKUMENT_NIEPRAWNY`, żeby dane z faktury nie
   zasilały cicho formularza. K1 spada na `K1_INNE_NIE_WIEM` (istniejąca
   ścieżka 6S) — celowo, formularza dla tego typu nie budujemy.
4. **Brak zmian** w CSV 08/09/12, `doc_processor.py`, `scenario_selector.py`
   dla `WEZWANIE_PRZEDSADOWE_SPOLKA`/`K1_WEZWANIE_PRZEDSADOWE_SPOLKA` — nie
   powstają.

### B. Typ 2 (WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU) — pełna ścieżka K1

1. **CSV 08** (`08_4_Formularz_6_krokow.csv`): dopisać na końcu (po
   `K1_PISMO_KOMORNIK_CZLONEK_ZARZADU`, wiersz 40) jeden nowy wiersz K1:
   `K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU` — "Wezwanie przedsądowe
   (członek zarządu)", te same kolumny co pozostałe K1.
2. **CSV 09** (`09_5_Punktacja_formularza.csv`): dopisać jeden wiersz
   (klon wzorca linii 7-8, `K1_document_weight`): C=2, P=0, H=0, W=0.
3. **CSV 12** (`12_6_Biblioteka_scenariuszy.csv`): dopisać ~15 scenariuszy
   zaczynając od `BASE_210` (plik kończy się na `BASE_209` bez luk),
   klonując pokrycie K2×ryzyko z `WEZWANIE_SADOWE_CZLONEK_ZARZADU`
   (`BASE_141`-`BASE_155`, 15 wierszy, `epu_flag=NIE`). Teksty narracyjne
   przepisać (nie kopiować dosłownie z "wezwania sądowego"): wezwanie już
   powołuje się na art. 299 KSH i bezskuteczność egzekucji wobec spółki —
   poważny sygnał, ale to jeszcze nie pozew ani nakaz; właściwa reakcja to
   odpowiedź na wezwanie / zakwestionowanie roszczenia / negocjacje, NIE
   "sprzeciw"/"odpowiedź na pozew" (to nie jest pismo procesowe, więc też
   K6_GOAL_PROCEDURAL_LETTER tekst w context_modules.py — już obsłużony
   ogólnie przez `"WEZWANIE_PRZEDSADOWE" in doc_type`, bez zmian).
4. **`app/doc_processor.py`**: dodać do `_DOC_TYPE_TO_K1` (obok
   WEZWANIE_SADOWE, ok. linii 27):
   ```python
   "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU": "K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU",
   ```
5. **`app/scenario_selector.py`**: dodać do `_K1_TO_DOC_TYPE` (obok
   WEZWANIE_SADOWE, ok. linii 17), tylko wariant `epu=False`:
   ```python
   ("K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU", False): "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU",
   ```
6. **`app/app.py`**:
   - `EPU_COMPATIBLE` (linie 28-39): dodać `"K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU": "NIE"`.
   - `_DOC_TYPE_LABELS` (linia 73): zmienić etykietę z "Wezwanie przedsądowe"
     na "Wezwanie przedsądowe (członek zarządu)" dla symetrii z etykietą
     spółki (linia 74, już ma sufiks).
   - Bramka art.299 — **bez zmian** (już działa poprawnie, jednolicie dla
     każdego `_CZLONEK_ZARZADU`).

### C. Excel — synchronizacja obowiązkowa
Zsynchronizować zmiany z kroku B.1-B.3 (jeden nowy wiersz K1, jeden wiersz
punktacji, ~15 scenariuszy) w arkuszach `4_Formularz_6_krokow`,
`5_Punktacja_formularza`, `6_Biblioteka_scenariuszy` w tej samej operacji.

### D. `tools/regression_expected.json`
- `299_przeds._wezw._do_zap..pdf` → main_type
  `WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU`, `gate: true`.
- `przed._wez_do_zap..pdf` → `WEZWANIE_PRZEDSADOWE_SPOLKA`, `gate: false`
  (istniejący wpis z 04.07 — sprawdzić, czy oczekiwania trzeba zaktualizować
  po dodaniu nowego ostrzeżenia).
- `przeds._wezw._do_zap2.pdf` → nowy plik, sprawdzić realnym przebiegiem
  OCR przed wpisaniem oczekiwań (prawdopodobnie też `WEZWANIE_PRZEDSADOWE_SPOLKA`).

### E. Weryfikacja
- `python tools/regression_test.py` — pełen przebieg, upewnić się że stare
  przypadki nie regresują i 3 nowe pliki PASS.
- Ręczne uruchomienie `streamlit run app/app.py`:
  - Typ 2 (`299_przeds._wezw._do_zap..pdf`): Krok 1 pokazuje "Wezwanie
    przedsądowe (członek zarządu)" zaznaczone (nie "Inne/nie wiem"), tekst
    oceny ryzyka spójnie opisuje przedsądowe wezwanie z art. 299 (nie
    "rodzaj pisma nie ustalony").
  - Typ 1 (`przed._wez_do_zap..pdf`, `przeds._wezw._do_zap2.pdf`): zamiast
    tabeli odczytu pojawia się nowe, trafne ostrzeżenie; formularz nadal
    dostępny pod spodem do ręcznego wypełnienia.

### F. Dokumentacja (na bieżąco, przed commitem)
- CLAUDE.md: wpis pod `app.py`/`doc_processor.py`/`scenario_selector.py`
  z datą, opisem przyczyny i naprawy (wzorem wpisów komorniczych
  05.07.2026) — osobno dla Typu 1 (nowy branch ostrzeżenia) i Typu 2
  (nowy K1). Zaktualizować sekcję "Test documents" o 3 pliki.
- Memory projektu — dopisać stan po naprawie.

## Kluczowe pliki
- `app/app.py` (`_show_doc_summary`, nowy zbiór ostrzeżenia, `EPU_COMPATIBLE`, `_DOC_TYPE_LABELS`)
- `app/doc_processor.py` (`_DOC_TYPE_TO_K1`)
- `app/scenario_selector.py` (`_K1_TO_DOC_TYPE`)
- `dane_wejściowe/csv/08_4_Formularz_6_krokow.csv`
- `dane_wejściowe/csv/09_5_Punktacja_formularza.csv`
- `dane_wejściowe/csv/12_6_Biblioteka_scenariuszy.csv`
- `dane_wejściowe/KRS_Guard_reguly_i_zasady_funkcjonowania.xlsx`
- `tools/regression_expected.json`
- `CLAUDE.md`
