# Redesign wizualny kalkulatora + wynik jako raport PDF/HTML

## Kontekst

Kalkulator działa poprawnie, ale wygląda jak standardowy, nieforemny formularz
Streamlit: kroki oddzielone tylko `st.divider()`, kolory dobierane osobno przy
każdym elemencie (brak spójnego systemu), a finalna ocena ryzyka wyświetla się
jako jeden długi blok markdown bezpośrednio pod formularzem. To nie buduje
zaufania do narzędzia, które ma kierować klienta do płatnego "Audytu 48h" —
usługa prawna powinna sprawiać wrażenie dopracowanej i profesjonalnej.

Cel: (1) spójna, przemyślana szata graficzna całego formularza z wyraźnie
oddzielonymi blokami, (2) finalny wynik NIE wyświetla się jako surowy tekst pod
formularzem, tylko jako krótka zajawka + wyraźne akcje "Zobacz pełny raport" /
"Pobierz jako PDF", prowadzące do ładnie sformatowanego dokumentu.

Zdecydowałem samodzielnie (na prośbę użytkownika) trzy kwestie techniczne:
- **Silnik PDF: WeasyPrint** — renderuje bezpośrednio z HTML+CSS, więc podgląd
  na stronie i plik PDF pochodzą z JEDNEGO szablonu (spójność, mniej pracy przy
  przyszłych zmianach wyglądu). Wymaga bibliotek systemowych (Pango/Cairo) —
  na Streamlit Cloud dodaje się je przez `packages.txt` (standardowa,
  wspierana ścieżka), lokalnie na Windows instalacja bywa kłopotliwa (do
  ewentualnego doinstalowania przy pierwszym uruchomieniu).
- **Logo**: NIE używamy logo firmowego "KRS Guard" z folderu poza repo
  (feedback użytkownika: kalkulator ma dostać WŁASNE, osobne logo, odrębne od
  logo kancelarii/firmy) — projektuję nowy, oryginalny znak graficzny
  wyłącznie dla kalkulatora, patrz "Propozycja logo kalkulatora" niżej. Zero
  emoji jako namiastki logo (dotąd ⚖️).
- **Podgląd wyniku na stronie**: krótka "zajawka" (kolorowa pigułka poziomu
  ryzyka + jedno zdanie) + wyraźne przyciski akcji — nie zupełna pustka, nie
  pełny tekst.

## Propozycja logo kalkulatora (nowy, oryginalny znak — nie logo kancelarii)

Skoro to ma być osobna tożsamość wizualna, a nie emoji ani przeniesione logo
firmowe: projektuję prosty, abstrakcyjny znak SVG (nie clipart wagi/szali —
to zbyt dosłowne i generyczne) w duchu "ochrona + ocena": stylizowana forma
tarczy/łuku z rosnącym wskaźnikiem wewnątrz, sugerująca jednocześnie
"zabezpieczenie" i "pomiar ryzyka" — w kolorze głównym z systemu tokenów
(granat `#1a3a5c` lub jego odcień). Budowany jako inline SVG (kod, nie plik
graficzny z zewnątrz) — skalowalny, ostry w każdym rozmiarze, łatwy do
przekolorowania przez CSS, zero zależności od plików spoza repo. Ten sam znak
używany w nagłówku aplikacji (Faza A) i w nagłówku raportu PDF/HTML (Faza B) —
spójna, samodzielna tożsamość kalkulatora. Nazwa tekstowa przy znaku zostaje
bez zmian ("KRS Guard — Kalkulator Ryzyka Prawnego") — zmienia się wyłącznie
sam graficzny symbol, nie tekst.

Favicon karty przeglądarki (`st.set_page_config(page_icon=...)`): dokładny
mechanizm dostarczenia tego samego znaku jako favicon (Streamlit natywnie
wspiera emoji/obraz/PIL Image, nie zawsze surowe SVG) zostanie potwierdzony
przez `developing-with-streamlit` skill na etapie implementacji — w
najgorszym razie favicon dostanie wyeksportowaną rastrową wersję tego samego
znaku, nadal bez emoji.

## Materiały źródłowe do wykorzystania (znalezione w eksploracji)

- **Istniejący prototyp** `krs_guard_kalkulator_ryzyka_v5.html` (poza repo,
  `C:\Users\User\Desktop\próby\...`) — gotowy, już zaakceptowany wcześniej
  język wizualny: ciemny granatowy gradient tła, białe "karty" z cieniem i
  zaokrągleniem, pigułki statusu ryzyka w 4 wariantach kolorystycznych, czarne
  przyciski CTA, pasek postępu kroku. Element `<details class="why">` z tego
  prototypu już wcześniej przeniesiono do `st.expander("Dlaczego pytamy?")` —
  ten redesign kontynuuje ten sam kierunek zamiast wymyślać nowy.
- `app/.streamlit/config.toml` ma już ustawiony granatowy `primaryColor =
  "#1a3a5c"` — punkt wyjścia dla systemu tokenów kolorystycznych.
- `text_builder.py`'s `build()` (linie 345-358) zwraca już **ustrukturyzowany
  słownik** (`risk_label`, `lead`, `practical`, `warnings`, `next_steps`,
  `cta`, `disclaimer`, `epu_block_*`), wszystko przepuszczone przez `_clean()`
  (usuwa kody techniczne). Szablon raportu ma korzystać z TYCH pól, nie z
  `full_text` — nie trzeba niczego parsować z powrotem.
- Specyfikacja funkcjonalna: zero kodów technicznych widocznych dla klienta —
  już wymuszone przez `_clean()`/`sanitize_check()`, redesign tego nie zmienia.
- `frontend-design` skill (zainstalowany w `.claude/skills/`) — proces
  projektowania (token system → krytyczna rewizja → build) do przeprowadzenia
  faktycznej implementacji CSS, żeby uniknąć "domyślnego wyglądu AI".
- `developing-with-streamlit` skill — do sprawdzenia dokładnych możliwości
  zainstalowanej wersji Streamlit (1.45.1) przed pisaniem CSS celującego w
  wewnętrzne selektory (np. stylowanie `st.radio`, `st.container(border=True)`).

## Zakres — dwie fazy w jednym planie

### Faza A: redesign wizualny formularza (Streamlit)

Plik główny: `app/app.py`; dotyka też `app/.streamlit/config.toml`, nowy
moduł `app/branding.py` (stała ze znacznikiem SVG znaku kalkulatora,
współdzielona z `report_builder.py` w Fazie B, żeby znak nie był
zduplikowany w dwóch miejscach).

1. Jeden scentralizowany blok CSS wstrzyknięty raz na górze `app.py`
   (`st.markdown("<style>...</style>", unsafe_allow_html=True)`) definiujący
   zmienne CSS (kolory, promień zaokrąglenia, cień, odstępy) w duchu
   prototypu — zamiast rozproszonych, osobno dobieranych kolorów hex w każdym
   miejscu (`colored_risk_box`, banery OCR, tabela dokumentu, itd.).
2. Nagłówek aplikacji: nowy własny znak SVG kalkulatora (patrz "Propozycja
   logo kalkulatora" wyżej) + tytuł + podtytuł w jednym pasku (zamiast samego
   `st.title()` i emoji ⚖️), stylizowany zgodnie z tokenami.
3. Każdy Krok 0-7 opakowany w `st.container(border=True)` (natywny,
   wspierany przez zainstalowaną wersję Streamlit) — realna, wyraźna
   separacja bloków zamiast samego `st.divider()`.
4. Ujednolicenie `RISK_COLORS`/`RISK_ICONS` (linie 45-57 `app.py`) z nowym
   systemem tokenów — te same kolory co pigułki statusu w raporcie (Faza B),
   żeby aplikacja i dokument wyglądały spójnie.
5. Odświeżenie stylu przycisków (`st.button`) i pól radio przez CSS, zgodnie
   z tokenami — bez zmiany logiki formularza, walidacji ani treści pytań.

### Faza B: wynik jako raport HTML/PDF zamiast bloku markdown pod formularzem

Nowy plik: `app/report_builder.py`. Zmieniany: `app/app.py` (blok
renderowania wyniku, obecnie linie ~1198-1247), `app/requirements.txt`
(+ `weasyprint`), nowy `app/packages.txt` (zależności systemowe WeasyPrint dla
Streamlit Cloud: `libpango-1.0-0`, `libpangocairo-1.0-0`, `libcairo2`,
`libgdk-pixbuf2.0-0`, `libffi-dev`).

1. `report_builder.build_report_html(output: dict, risk_code: str, ...) ->
   str` — samodzielny dokument HTML (inline `<style>`, ten sam znak SVG
   kalkulatora z `branding.py` osadzony bezpośrednio jako znacznik `<svg>`
   — zero emoji, zero zależności od plików zewnętrznych, plik w pełni
   przenośny) w tym samym języku wizualnym co aplikacja: nagłówek ze znakiem
   i pigułką ryzyka, osobne, wyraźnie oddzielone
   sekcje dla `lead`/uzasadnienia ryzyka/`practical`/`warnings`/`next_steps`,
   blok EPU (`epu_block_*`, dotąd osobny expander na stronie — teraz część
   raportu), sekcja CTA do Audytu 48h, zastrzeżenie prawne (`disclaimer`).
   Źródło danych: gotowy słownik z `text_builder.build()` — bez zmian w
   `text_builder.py` poza ewentualnym jednym nowym polem `teaser` (krótkie
   1-zdaniowe podsumowanie do zajawki na stronie, też przepuszczone przez
   `_clean()`).
2. `report_builder.build_report_pdf(html: str) -> bytes` — cienki wrapper na
   `weasyprint.HTML(string=html).write_pdf()`.
3. W `app.py`: obecny blok `colored_risk_box(...)` + `st.markdown(full_text)`
   + expander EPU zastąpiony:
   - kompaktową zajawką (mniejsza pigułka koloru ryzyka + `output["teaser"]`),
   - przyciskiem `st.download_button("⬇ Pobierz jako PDF", ...)`,
   - przełącznikiem/expanderem "📄 Zobacz pełny raport" renderującym ten sam
     HTML przez `st.components.v1.html(html, height=1400, scrolling=True)` —
     podgląd bez opuszczania aplikacji.
   - Panel techniczny (hasło) i przycisk resetu — bez zmian.

## Kolejność wykonania i ryzyko

Faza A jest czysto addytywna wizualnie (CSS + `st.container(border=True)`,
zero zmian w logice formularza) — mniejsze ryzyko, natychmiast widoczny
efekt. Faza B wprowadza nową zależność (WeasyPrint) i zmienia architekturę
wyświetlania wyniku — większe ryzyko, wymaga osobnej weryfikacji. Wykonam obie
w ramach tej sesji, ale z przerwą na żywy test w przeglądarce po Fazie A,
zanim przejdę do Fazy B — łatwiej wyłapać problem, gdy fazy są odseparowane.

## Weryfikacja

`tools/regression_test.py` NIE renderuje UI Streamlit (woła `process_files()`
bezpośrednio) — nie wykryje żadnej z tych zmian, a same zmiany nie dotykają
warstwy klasyfikacji dokumentów, więc pełna regresja (per polityka projektu)
nie jest tu wymagana. Zamiast tego, zgodnie z doświadczeniem z sesji 15.07/16.07
(zmiany UI w Streamlit dotykające kontenerów łapią błędy niewidoczne w diffie):

1. **Po Fazie A** — żywy test w przeglądarce (`agent-browser`): sprawdzić, że
   strona renderuje się bez błędów (`agent-browser console`), bloki kroków są
   wyraźnie oddzielone wizualnie (zrzut ekranu), logo się wyświetla, kolory są
   spójne.
2. **Po Fazie B** — żywy test pełnego przebiegu: wypełnić formularz (lub
   wgrać dokument testowy), kliknąć "Oblicz ryzyko", potwierdzić że POD
   FORMULARZEM nie pojawia się już pełny tekst oceny, tylko zajawka +
   przyciski; kliknąć "Zobacz pełny raport" i sprawdzić poprawność renderowania
   sekcji; kliknąć "Pobierz jako PDF", zweryfikować że plik faktycznie się
   pobiera i (jeśli to możliwe w tym środowisku) otwiera się poprawnie.
3. Sanity-check `python -c "import text_builder"` / krótkie ręczne wywołanie
   `report_builder.build_report_html()` na przykładowym słowniku wynikowym,
   zanim przejdzie się do testu w przeglądarce (szybsza pętla iteracji niż
   klikanie w UI za każdym razem).

Po potwierdzeniu: aktualizacja CLAUDE.md (`app.py`, nowy wpis
`report_builder.py`, `requirements.txt`/`packages.txt`) i pliku pamięci
projektu, zgodnie ze stałą zasadą projektu, następnie commit + push na
`etap2` (osobny od już zacommitowanych dziś zmian w `doc_selector.py`/
`doc_splitter.py`).

## Uwaga o rozmiarze zadania

To zadanie dotyka więcej niż 4 plików i prawdopodobnie więcej niż 80 linii
kodu (spory blok CSS + nowy moduł `report_builder.py` + zmiany w layoucie
`app.py`) — zgodnie z zasadą projektu (CLAUDE.md) zasygnalizuję to przed
startem implementacji i będę robił checkpointy (zwłaszcza między Fazą A i B),
żeby w razie przerwania sesji było jasne, co zostało zrobione, a co nie.
