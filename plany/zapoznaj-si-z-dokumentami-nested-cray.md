# "Dlaczego pytamy?" — wyjaśnienia pod każdym krokiem formularza K1-K7

## Kontekst

Użytkownik chce, żeby na końcu każdego kroku formularza (K1-K7) pojawiało się
zwijane wyjaśnienie "Dlaczego pytamy?" — po kliknięciu ikonki pokazuje krótki
tekst tłumaczący sens pytania. Wzorzec zaczerpnięty z prototypu HTML
(`C:\Users\User\Desktop\testy\krs_guard_kalkulator_ryzyka_v5.html`):
`<details class="why"><summary>ℹ️ Dlaczego pytamy?</summary><div>...</div></details>`
— zwinięty domyślnie element z ikonką ℹ️ przed tekstem podsumowania.

Odkryte podczas researchu: CSV 08 (`dane_wejściowe/csv/08_4_Formularz_6_krokow.csv`,
arkusz Excela `4_Formularz_6_krokow`) ma już kolumnę `why_we_ask` z gotowymi,
klientowskimi tekstami PER KROK (nieużywaną nigdzie w aplikacji) — zgodnie z
regułą projektu "nigdy nie hardkoduj tekstów, które mogą być sterowane z
CSV/Excela", to jest właściwe źródło treści, nie nowy tekst wpisany wprost w
app.py. Użytkownik zaakceptował użycie tych tekstów wprost.

**Zaakceptowane teksty (do wyświetlenia bez zmian):**

| Krok | Tekst |
|---|---|
| K1 | Różne pisma mają różną wagę — to wpływa na pilność i końcową ocenę ryzyka. |
| K2 | Najczęściej o wyniku decyduje czas — nawet dobra obrona nie zadziała, jeśli termin ucieknie. |
| K3 | Ocena bez dokumentów może być tylko orientacyjna. Audyt 48h daje większą pewność, ale wymaga przesłania kompletu dokumentów. |
| K4 | Status i daty pełnienia funkcji wpływają na ryzyka oraz na to, co warto zabezpieczyć dowodowo. |
| K5 | W praktyce wiele sytuacji opiera się o wpis w KRS — brak aktualizacji potrafi zwiększać chaos formalny. |
| K6 | Cel pomaga dobrać charakter komunikatu: ocena szans, bezpieczne przygotowanie obrony, konkretne pismo procesowe albo uporządkowanie sytuacji. |
| K7 | Kwota wpływa na ciężar gatunkowy sprawy, skalę ryzyka finansowego i priorytet działań. |

**Naprawiona przy okazji niespójność danych**: w CSV 08 wiersz K1 dla odpowiedzi
`K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU` (wiersz ~40) ma INNY tekst `why_we_ask`
("Pisma organów publicznych dotyczące odpowiedzialności członka zarządu
wymagają innej ścieżki niż pozew/nakaz sądowy.") niż pozostałe 13 wierszy K1
(tekst generyczny powyżej) — wygląda na przeoczenie z dopisania tej kategorii
05.07.2026, nie zamierzoną wariację (wyjaśnienie dotyczy KROKU, użytkownik
czyta je PRZED wybraniem odpowiedzi). Użytkownik zaakceptował wyrównanie tego
wiersza do generycznego tekstu K1 — poprawić w CSV 08 ORAZ w odpowiadającym
arkuszu Excela `4_Formularz_6_krokow` w tej samej operacji (zasada projektu:
CSV i Excel muszą być zawsze zsynchronizowane), tym samym sposobem co
poprzednie edycje Excela w tym repo (jednorazowy skrypt openpyxl, edycja
komórki po indeksie wiersza, nie ręcznie).

## Implementacja

### 1. `app/app.py` — nowa funkcja `get_why_we_ask(step_id)` (obok istniejącego `get_answers_for_step`/`get_label_for_code`, ~linia 234)

Używa już istniejącego `get_form_data()` (cache'owany DataFrame z CSV 08).
Filtruje po `step_id`, zbiera niepuste wartości `why_we_ask`, zwraca
NAJCZĘSTSZĄ wartość (mode) — odporne na ewentualne przyszłe niespójności typu
opisanej wyżej, nie tylko na tę jedną (naprawioną) w CSV. Przykład:

```python
def get_why_we_ask(step_id: str) -> str:
    """Zwraca tekst 'Dlaczego pytamy?' dla danego kroku (najczęstsza
    wartość why_we_ask wśród wierszy tego step_id — odporne na ewentualne
    niespójności per-odpowiedź w CSV, wyjaśnienie dotyczy całego kroku)."""
    df = get_form_data()
    values = [
        str(v).strip() for v in df[df["step_id"] == step_id]["why_we_ask"]
        if str(v).strip() not in ("", "nan")
    ]
    if not values:
        return ""
    return Counter(values).most_common(1)[0][0]
```
(`from collections import Counter` w nagłówku importów app.py, jeśli jeszcze
nie zaimportowane.)

### 2. Helper renderujący expander (obok `labeled_radio`, ~linia 260)

```python
def render_why_expander(step_id: str) -> None:
    why = get_why_we_ask(step_id)
    if why:
        with st.expander("ℹ️ Dlaczego pytamy?", expanded=False, key=f"why_{step_id}"):
            st.markdown(why)
```
`key=` konieczny, bo tytuł "ℹ️ Dlaczego pytamy?" powtarza się 7 razy na tej
samej stronie — bez unikalnego klucza Streamlit może zgłosić kolizję ID
(potwierdzone: zainstalowany Streamlit 1.45.1, `st.expander` wspiera `key`
od dawna przed tą wersją). Wzorzec ikonki ℹ️ + zwinięty domyślnie dokładnie
odwzorowuje prototyp HTML użytkownika i pasuje do istniejącego
`st.expander(f"ℹ️ {heading}", expanded=True)` już używanego w app.py:1224.

### 3. Wywołania `render_why_expander(...)` w 7 punktach formularza (`app/app.py`, sekcja `── Formularz ──`, linie ~864-1016)

Każde wywołanie na końcu bloku danego kroku, przed nagłówkiem kolejnego kroku:

- Po K1 (`labeled_radio(...)` kończy się w linii 870) → `render_why_expander("K1")`
- Po K2 (po całym bloku `if use_dates: ... else: k2 = labeled_radio(...)`,
  linia 976 — WAŻNE: jedno wywołanie PO obu gałęziach if/else, bo wyjaśnienie
  dotyczy kroku niezależnie od tego, którą ścieżką użytkownik poszedł)
  → `render_why_expander("K2")`
- Po K3 (linia 980) → `render_why_expander("K3")`
- Po K4 (linia 984) → `render_why_expander("K4")`
- Po K5 — TYLKO wewnątrz bloku `if k4 == "K4_BOARD_RESIGNED":` (linia 993,
  zaraz po `labeled_radio(...)` dla K5) → `render_why_expander("K5")`;
  krok K5 nie jest w ogóle pokazywany w pozostałych gałęziach, więc nie ma
  czego tłumaczyć poza tym blokiem
- Po K6 (linia 1001) → `render_why_expander("K6")`
- Po K7 (linia 1014, przed `st.divider()` w linii 1016) → `render_why_expander("K7")`

Nie dotyczy: checkboxa EPU ("Krok 2 — E-Sąd / EPU" w UI, linie 873-917) —
to nie jest krok K1-K7 z CSV 08, ma już własny dedykowany expander
"Jak rozpoznać dokument z EPU / e-Sądu?" (linia 908) pełniący analogiczną
funkcję.

### 4. `dane_wejściowe/csv/08_4_Formularz_6_krokow.csv` + Excel `4_Formularz_6_krokow`

Wiersz K1/`K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU`: pole `why_we_ask` zmienione z
obecnego tekstu na generyczny tekst K1 ("Różne pisma mają różną wagę — to
wpływa na pilność i końcową ocenę ryzyka."), identycznie w CSV i w
odpowiadającej komórce arkusza Excel (jednorazowy skrypt openpyxl, wzorem
poprzednich edycji Excela w tym repo — bezpośrednia edycja komórki po
indeksie wiersza, nie ręcznie w interfejsie).

## Weryfikacja

1. `streamlit run app/app.py` — przejść formularz krok po kroku, kliknąć
   każdy z 7 expanderów "ℹ️ Dlaczego pytamy?", potwierdzić poprawny tekst i
   brak błędu duplikatu ID w konsoli/UI.
2. Potwierdzić, że K5 pokazuje swój expander TYLKO gdy pytanie faktycznie
   się wyświetla (wybór "Była rezygnacja / odwołanie" w K4).
3. `python tools/regression_test.py` (pełna regresja) — ta zmiana nie dotyka
   `doc_*.py`/`ai_extractor.py`, więc nie powinno być regresji w wyniku
   OCR/klasyfikacji; uruchomić mimo to, bo `app.py` jest współdzielony i
   projekt wymaga tego po każdej zmianie.
4. Odczytać zaktualizowaną komórkę w Excelu (otwarcie pliku / odczyt przez
   openpyxl) — potwierdzić zgodność z CSV.

## Dokumentacja (zgodnie z zasadami projektu)

Zaktualizować `CLAUDE.md` (sekcja `app.py`, nowy wpis datowany) opisujący
nowy mechanizm `get_why_we_ask()`/`render_why_expander()` i naprawę
niespójności CSV/Excel; dopisać krótką notatkę do pamięci projektu
(nowy plik `memory/project_why_we_ask_expanders.md` lub rozszerzenie
istniejącego, jeśli znajdzie się tematycznie bliższy).

---

# Część 2: rzeczywisty postęp analizy dokumentów zamiast statycznego kółka

## Kontekst

Podczas wgrywania dokumentów aplikacja pokazuje `st.spinner("Analizuję
dokumenty (OCR + ekstrakcja danych)...")` — jedno stałe zdanie z obracającą
się ikonką przez CAŁY czas trwania analizy (zrzut ekranu użytkownika:
`C:\Users\User\Desktop\testy\obraz1.png`). Dla dużych paczek (wielostronicowe
skany komornicze, wiele dokumentów w jednej paczce) to może trwać od
kilkudziesięciu sekund do kilku minut — z pamięci projektu wiadomo, że
przetwarzanie 20-stronicowego bundla komorniczego bywa długie, a w jednej z
sesji testowych wystąpiło nawet ~1,5-godzinne zawieszenie tła (patrz
`memory/session_2026-07-15_full_regression.md`). Statyczny spinner nie daje
żadnego sygnału, czy aplikacja rzeczywiście pracuje, czy się zawiesiła —
użytkownik chce widocznej progresji, żeby nie było wątpliwości.

## Analiza architektury (co jest realnie instrumentowalne)

`process_files()` (`app/doc_processor.py:361`) to POJEDYNCZE synchroniczne
wywołanie z app.py (`app/app.py:744`), owinięte w `st.spinner`. Streamlit
działa jednowątkowo — jedyny sposób na pokazanie PRAWDZIWEGO postępu w
trakcie tego wywołania to przekazanie do środka callbacku, który aktualizuje
widget UI z tego samego wątku głównego (nie wymaga threadingu, bo wywołania
callbacku i tak dzieją się synchronicznie wewnątrz tego samego "rerun" skryptu
Streamlit).

Zidentyfikowane naturalne punkty postępu (bez zgadywania — potwierdzone
czytaniem kodu):

1. **`process_files()`** (`doc_processor.py:374`) — pętla `for uf in
   uploaded_files:` — jeden plik na iterację → "Wczytuję plik N/M: nazwa...".
2. **`_process_single_doc()`** (`doc_processor.py:262`) — wywołuje
   `ocr_with_fallback()` (OCR — DOMINUJĄCY koszt czasowy), potem
   `detect_documents_by_pages()` (szybkie), potem PĘTLĘ po segmentach
   (`doc_processor.py:303`) wywołującą `_build_candidate_dict()` per
   dokument w paczce (klasyfikacja + wywołanie AI Claude Haiku per
   dokument — drugi co do wielkości koszt czasowy, mnożony przez liczbę
   dokumentów w paczce) → "Analizuję dokument N/M w pliku...".
3. **`ocr_with_fallback()`** (`doc_ocr.py:17`) — kaskada silników:
   - **`_ocr_azure()`** (`doc_ocr.py:111`): `poller = client.
     begin_analyze_document(...)`, obecnie `result = poller.result()` —
     JEDNO blokujące wywołanie BEZ żadnej pośredniej informacji zwrotnej.
     Zweryfikowane: zainstalowany `azure-ai-documentintelligence==1.0.2`
     zwraca standardowy `LROPoller` ze wsparciem `.done()` — da się
     zastąpić `.result()` ręczną pętlą odpytującą co ~2s, wywołującą
     callback z narastającym czasem ("OCR: przetwarzam (Azure)... Ns").
     To jest NAJWAŻNIEJSZY punkt do naprawienia — to pojedyncze wywołanie
     jest najbardziej prawdopodobnym sprawcą wrażenia "zawieszenia się"
     dla dużych skanów (żadna z pozostałych pętli nie jest aż tak długim,
     całkowicie nieprzezroczystym pojedynczym blokiem).
   - **`_ocr_claude()`** (`doc_ocr.py:170`): JUŻ ma pętlę per strona
     (`for i, page in enumerate(pages, start=1):`) — trywialne dodanie
     callbacku per iterację: "OCR: strona N/M (Claude)...".
   - `_ocr_tesseract_pages()`: analogiczna pętla per strona, ten sam wzorzec
     (fallback bez klucza Anthropic — rzadsza ścieżka, ale dla spójności
     też dostanie callback).

## Implementacja

Wszędzie NOWY, opcjonalny parametr `on_progress: Callable[[str], None] |
None = None` na końcu listy argumentów — czysto addytywne, zero zmian w
istniejących wywołaniach pozycyjnych/bez tego argumentu.
`tools/regression_test.py` woła `process_files(uploaded_files, secrets)` bez
`on_progress` → zachowanie identyczne jak dziś (domyślne `None`, wszystkie
wywołania callbacku owinięte w `if on_progress: on_progress(...)`) —
zweryfikować pełną regresją po zmianie, mimo że nie dotyka logiki OCR/AI
per se, tylko opakowuje ją callbackiem.

1. **`app/doc_ocr.py`**
   - `import time` w nagłówku.
   - `_ocr_azure(raw_bytes, key, endpoint, pages, on_progress=None)`:
     zastąpić `result = poller.result()` pętlą:
     ```python
     elapsed = 0
     while not poller.done():
         time.sleep(2)
         elapsed += 2
         if on_progress:
             on_progress(f"OCR: przetwarzam dokument (Azure)... {elapsed}s")
     result = poller.result()
     ```
   - `_ocr_claude(pages, api_key, on_progress=None)`: na początku pętli
     `for i, page in enumerate(pages, start=1):` dodać
     `if on_progress: on_progress(f"OCR: strona {i}/{len(pages)} (Claude)...")`.
   - `_ocr_tesseract_pages(scan_pages, on_progress=None)`: analogicznie w
     pętli `for i, page in enumerate(scan_pages, start=1):`.
   - `ocr_with_fallback(pages, raw_bytes, ext, secrets, on_progress=None)`:
     przekazać `on_progress` do `_ocr_azure`/`_ocr_claude`/`_ocr_tesseract`
     (przez `_ocr_tesseract` do `_ocr_tesseract_pages`); opcjonalnie
     zgłosić przejścia między silnikami ("Jakość OCR poniżej progu —
     eskaluję do Claude Haiku...", zgodnie z istniejącym komentarzem o
     progu 0.75 w tym pliku).

2. **`app/doc_processor.py`**
   - `_process_single_doc(pages, raw_bytes, ext, secrets, file_ext="",
     on_progress=None)`: przekazać do `ocr_with_fallback(...)`; w pętli po
     `segments` (linia ~303) przed każdym `_build_candidate_dict(...)`:
     `if on_progress: on_progress(f"Analizuję dokument {idx}/{len(segments)}
     w paczce...")`; analogicznie dla ścieżki "plik jednolity" (pojedynczy
     kandydat, linia ~351) — "Analizuję dokument...".
   - `process_files(uploaded_files, secrets=None, on_progress=None)`: w
     pętli `for uf in uploaded_files:` (linia 374) przed wywołaniem
     `_process_single_doc(...)`, gdy `len(uploaded_files) > 1`:
     `if on_progress: on_progress(f"Wczytuję plik {idx}/{len(uploaded_files)}:
     {uf.name}...")` (pomijalne dla pojedynczego pliku — nie ma co
     numerować "1/1").

3. **`app/app.py`** (~linia 739-744) — zastąpić `st.spinner(...)`
   kontenerem `st.status(...)` (dostępny od Streamlit 1.28+, zainstalowana
   wersja 1.45.1 — potwierdzone):
   ```python
   with st.status("Analizuję dokumenty (OCR + ekstrakcja danych)...", expanded=True) as status:
       main_doc, aux_docs = process_files(
           uploaded_files, secrets,
           on_progress=lambda msg: status.write(msg),
       )
       status.update(label="Analiza zakończona ✓", state="complete", expanded=False)
   ```
   Zachowuje pojedynczy `try:` już otaczający ten blok (linia 739) bez
   zmian — wyjątek nadal propaguje się do istniejącej obsługi błędu (do
   zweryfikowania podczas implementacji, czy warto dodatkowo ustawić
   `status.update(state="error")` w bloku `except`, żeby widget nie
   zostawał wizualnie w stanie "running" po błędzie — sprawdzić dokładny
   zakres istniejącego `except` przed decyzją, nie zgadywać).

## Weryfikacja

1. **Skill `developing-with-streamlit`** — wywołać PRZED implementacją
   (obowiązkowe wg CLAUDE.md dla KAŻDEGO zadania Streamlit) — potwierdzić
   dokładną sygnaturę `st.status()`/`.update()` dla zainstalowanej wersji
   1.45.1 (label/expanded/state), zanim kod zostanie napisany.
2. `streamlit run app/app.py` — wgrać: (a) pojedynczy krótki dokument
   (natywny PDF, bez OCR — potwierdzić że status i tak ładnie się kończy
   mimo braku wywołań `on_progress` z OCR), (b) wielostronicowy skan
   (Azure OCR — potwierdzić WIDOCZNE tykanie "...Ns" podczas oczekiwania,
   nie tylko na końcu), (c) paczkę wielodokumentową (kilka pozycji w
   "Analizuję dokument N/M..." przewijających się w widgetcie).
3. `python tools/regression_test.py` (pełna regresja) — potwierdzić 0
   regresji mimo że zmiana jest "tylko" opakowaniem callbackiem — dotyka
   `doc_ocr.py`/`doc_processor.py`, więc obowiązkowe wg zasad projektu.
4. Potwierdzić, że `on_progress=None` (domyślne, ścieżka
   `regression_test.py`) nie powoduje żadnych wyjątków ani zmiany
   zachowania — przeczytać finalny diff pod kątem, czy każde wywołanie
   callbacku jest bezpiecznie owinięte `if on_progress:`.

⚠️ To jest większa zmiana niż wygląda na pierwszy rzut oka — dotyka
architektury OCR (`doc_ocr.py`, `doc_processor.py`) używanej przez CAŁY
pipeline, nie tylko UI. Warto zrobić checkpoint po każdym z 3 plików
(doc_ocr.py → doc_processor.py → app.py) z osobną weryfikacją regresji po
pierwszych dwóch, zanim dotknięty zostanie interfejs.

## Dokumentacja

`CLAUDE.md`: nowy wpis w sekcjach `doc_ocr.py`/`doc_processor.py`/`app.py`
opisujący mechanizm `on_progress` i motywację (zawieszenie-wyglądający
spinner, memory 15.07). Nowy plik `memory/project_progress_indicator.md`
lub rozszerzenie istniejącej notatki o incydencie zawieszenia (sesja
15.07) — połączyć przyczynę (brak informacji zwrotnej podczas długiego
Azure poll) ze skutkiem (ten sam incydent, teraz naprawiony architekturalnie,
nie tylko operacyjnie).
