# Trzy naprawy dla `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf`

## Kontekst

Użytkownik ponownie wgrał plik testowy `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf`
(20-stronicowy skan: paczka egzekucyjna komornika ZAWIERAJĄCA też wyrok zaoczny —
ten plik był dotąd zweryfikowany tylko RAZ, flagowany do re-checku w sesji 15.07).
Uwagi spisane w `C:\Users\User\Desktop\testy\uwagi.docx` + 3 zrzuty ekranu
(`obraz1-3.png`) ujawniają TRZY niezależne błędy:

1. **Fałszywe ostrzeżenie "różne sprawy"** — mechanizm z 14.07.2026
   (`_parties_differ()`) porównuje wierzyciela dokumentu głównego z
   pomocniczymi. "Faliszewska Barbara" (główny) vs "Barbara Faliszewska"
   (pomocniczy) to TA SAMA osoba — tylko imię i nazwisko zamienione
   miejscami — a mechanizm (czysty substring-check) błędnie je flaguje
   jako różne podmioty.
2. **Brak podpisu rodzaju kwoty** — rubryka "Kwota roszczenia" (805,05 zł,
   dokument komorniczy) nie ma dopisku "(należność główna...)" / "(kwota
   łączna...)" wprowadzonego 14.07.2026 — bo prompt AI dla pola
   `kwota_zl_rodzaj` mówi wyłącznie językiem pozwu/nakazu ("rozbicie na
   należność główną i odsetki/koszty"), nigdy nie wspomina pism
   komorniczych, więc pole prawdopodobnie wychodzi `null`.
3. **Błędna segmentacja stron** — użytkownik potwierdza, że plik ma 8
   dokumentów: str.1-4, 5-6, 7-8, 9-10, 11-12, 13-14, 15-16, 17-20. Aplikacja
   pokazuje tylko 6 (dwa złe sklejenia: 1-4+5-6→1-6, 11-12+13-14→11-14).
   Przyczyna sklejenia 1-4+5-6: `doc_splitter.py` NIE MA żadnej reguły
   rozpoznającej stronę "WYROK ZAOCZNY" (w odróżnieniu od `doc_classifier.py`,
   który ma taką regułę od 07.07.2026, ale działa na poziomie już
   sklejonego segmentu — za późno, by wytyczyć granicę strony). Strony
   wyroku wpadają w `None`/kontynuację i są cicho doklejane do sąsiedniego
   pisma komorniczego. Przyczyna sklejenia 11-12+13-14 NIE jest jeszcze
   potwierdzona (wymaga odczytu realnego OCR tych stron przed naprawą).

Wszystkie trzy naprawy zweryfikowane researchem kodu (3 agenty Explore +
1 agent Plan + bezpośredni odczyt plików) — dokładne linie i logika
potwierdzone poniżej.

⚠️ Zadanie dotyka >4 plików (app.py, ai_extractor.py, doc_splitter.py,
regression_expected.json, CLAUDE.md, memory/*.md) — zgodnie z konwencją
projektu warto zatrzymać się na checkpoint, jeśli sesja zostanie przerwana.

---

## Naprawa 1 — `_parties_differ()` (app.py, linie ~149-164)

Dodać nową funkcję pomocniczą `_same_person_reordered(na, nb)`: gdy OBIE
znormalizowane nazwy mają 2-3 tokeny (typowe imię+nazwisko, ew. z drugim
imieniem) I ich zbiory tokenów są identyczne niezależnie od kolejności →
traktuj jako tę samą osobę. To DODATKOWY warunek obok istniejącego
substring-checku (który już poprawnie obsługuje warianty zapisu firm), nie
jego zamiennik.

```python
_PERSON_NAME_MAX_TOKENS = 3

def _same_person_reordered(na: str, nb: str) -> bool:
    ta, tb = na.split(), nb.split()
    if not (2 <= len(ta) <= _PERSON_NAME_MAX_TOKENS
            and 2 <= len(tb) <= _PERSON_NAME_MAX_TOKENS):
        return False
    return set(ta) == set(tb)

def _parties_differ(a, b):
    if not a or not b:
        return False
    na, nb = _normalize_party_name(a), _normalize_party_name(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return False
    if _same_person_reordered(na, nb):
        return False
    return True
```

Weryfikacja bez uruchamiania pipeline'u (manualny trace, opisać w
`memory/project_unrelated_docs_warning.md` jako rozszerzenie 7 istniejących
przypadków):
- "Faliszewska Barbara" vs "Barbara Faliszewska" → NIE różni się (naprawione).
- "Jan Kowalski" vs "Piotr Kowalski" (to samo nazwisko, różna osoba) → nadal
  różni się (zbiory tokenów różne).
- "MIPROMET Sp. z o.o." vs "KILOUTOU Polska sp. z o.o." (istniejący,
  potwierdzony przypadek) → nadal różni się (MIPROMET ma 1 token po
  usunięciu formy spółkowej, poniżej progu 2-3 → `_same_person_reordered`
  zwraca False, substring-check i tak łapie różnicę).
- "PKO Bank Polski S.A." vs pełna forma → bez zmian (identyczne po
  normalizacji, substring check łapie to PRZED nowym warunkiem).

Udokumentować świadomie zaakceptowane ryzyko szczątkowe: dwie RÓŻNE firmy,
których nazwy po usunięciu formy spółkowej są dokładną permutacją 2-3
tokenów (np. hipotetyczne "Auto Serwis" vs "Serwis Auto"), zostaną błędnie
uznane za tę samą — brak takiego przypadku w obecnym zestawie testowym,
niskie ryzyko (nazwy firm z AI zachowują kanoniczną kolejność, w
odróżnieniu od nazwisk osobowych, które legalnie różnią się między
formularzami).

---

## Naprawa 2 — prompt `kwota_zl_rodzaj` (ai_extractor.py, po linii 59)

Potwierdzone: `doc_processor.py`/`app.py` są całkowicie type-agnostic wobec
`amount_type` — to czysta zmiana promptu, zero zmian w kodzie ścieżki
danych.

Dopisać nowy akapit zasad (po istniejącym akapicie `kwota_zl_rodzaj`,
przed akapitem `wartosc_przedmiotu_sporu_zl`), rozszerzający słownictwo na
pisma komornicze — analogiczna zasada "glowna"/"laczna", ale z przykładami
z języka egzekucyjnego (należność główna / odsetki / koszty egzekucyjne /
koszty zastępstwa procesowego jako rozbicie → "glowna"; "kwota
zadłużenia"/"kwota do zapłaty"/"suma egzekwowana" bez rozbicia → "laczna").
Jawnie zaznaczyć: nie zostawiać `null` tylko dlatego, że to pismo
komornicze, a nie pozew/nakaz.

**Wymagana weryfikacja na żywo** (nie da się ustalić z samego kodu, czy dla
TEGO konkretnego dokumentu (805,05 zł) poprawną wartością jest "glowna" czy
"laczna" — zależy od realnej treści strony):
1. `python tools/regression_test.py --only "wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf"`
2. Skrypt diagnostyczny w scratchpadzie: jedno wywołanie
   `doc_processor.process_files()`, zapis `main.raw_text`/`amount`/
   `amount_type` do pliku, odczyt bez ponownego OCR (wzorem sesji
   05.07.2026/14.07.2026 — unikanie wariancji między przebiegami).

---

## Naprawa 3 — segmentacja w doc_splitter.py

### 3a. Nowa reguła "wyrok zaoczny" (przyczyna potwierdzona)

Umieścić NOWĄ regułę zaraz PO Regule 1a (pismo procesowe, ~linia 143) i
PRZED Regułą 1 (art. 299 → pozew, ~linia 145) — analogicznie do
`doc_classifier.py`, ten sam sygnał: "W IMIENIU RZECZYPOSPOLITEJ POLSKIEJ"
+ "WYROK...ZAOCZN" w oknie pierwszych ~800 zn. Musi być PRZED Regułą 1, bo
uzasadnienie wyroku przeciw spółce mogłoby (teoretycznie) cytować art. 299
KSH.

```python
_head_800 = tu[:800]
if (re.search(r"(?m)^\s{0,5}WYROK\b[\s\S]{0,20}?ZAOCZN\w*", _head_800)
        and re.search(r"W\s+IMIENIU\s+RZECZYPOSPOLITEJ\s+POLSKIEJ", _head_800)):
    return ("wyrok_zaoczny", "Wyrok zaoczny", "primary")
```

**Ryzyko stron kontynuacji** (uzasadnienie wyroku, str. 2-4): nie mają
własnego "W IMIENIU..." więc nie złapią nowej reguły — jeśli zawierają
"art. 299 KSH", Reguła 1 (działająca wcześniej niż nowa reguła na TEJ
stronie, bo to inna strona, nie ten sam if) mogłaby je błędnie odciąć jako
"pozew". To DOKŁADNIE ten sam problem, który Krok -3 już rozwiązuje dla
`pismo_procesowe` — rozszerzyć zbiór celów Kroku -3 (obecnie hardcoded na
`"pismo_procesowe"`) o `"wyrok_zaoczny"`, zachowując istniejące guardy
(`_POZEW_TITLE_RE`/`_KOD_RE` — prawdziwy, samodzielny pozew/formularz EPU
nigdy nie zostanie połknięty).

**Decyzje o zbiorach scalania**:
- DODAĆ `"wyrok_zaoczny"` do `_KOMORNIK_MERGE_TARGETS` (Krok -2, ~linia
  481-486) — strona kontynuacji wyroku złapana przez generyczny fallback
  Reguły 6 (kind `"komornik"`) powinna doklejać się z powrotem do wyroku,
  nie stawać się osobnym segmentem. Bezpieczne: ten krok reaguje TYLKO na
  generyczny kind `"komornik"`, nigdy na konkretnie nazwany
  `komornik_wszczecie_egzekucji` itp., więc nie skleiy wyroku z sąsiednim,
  odrębnie tytułowanym pismem komorniczym.
- NIE DODAWAĆ `"wyrok_zaoczny"` do `_komornik_kinds` (Krok -1, ~linia
  509-514) — ten zbiór chroni scalanie nakazu/pozwu WCIŚNIĘTEGO między
  segmenty komornicze (ochrona łańcucha art. 299); wyrok to odrębny
  dokument egzekwowany przez otaczające pisma komornicze, analogicznie do
  celowo wykluczonego `wniosek_egzekucyjny`.

### 3b. Sklejenie str.11-12 + str.13-14 (przyczyna NIEPOTWIERDZONA)

WYMAGANY krok diagnostyczny PRZED napisaniem poprawki — nie zgadywać:
1. Najpierw wdrożyć i przetestować 3a (zmiana segmentacji str.1-8 może
   przesunąć/odsłonić inny obraz dla str.11-14 — diagnozować B na świeżym
   stanie, nie na nieaktualnym).
2. `python tools/regression_test.py --only "wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf"`
   — sprawdzić zakresy stron/kindy dla obszaru str.11-14.
3. Jeśli nadal sklejone: jednorazowy skrypt w scratchpadzie — zapisany
   surowy OCR z separatorami stron (bez ponownego kosztownego OCR), wywołać
   `doc_splitter._classify_page_segment()` bezpośrednio na tekście stron
   11/12/13/14 osobno, wydrukować wynik (kind/label/role albo None) per
   strona.
4. Drzewo decyzyjne:
   - Jeśli str.13 sama klasyfikuje się na inny kind niż
     `komornik_zajecie_rachunku` (np. pasuje do wzorca
     `komornik_wezwanie_wykaz` — "WEZWANIE DO ZŁOŻENIA WYKAZU"), ale
     scalony segment i tak pokazuje tylko `komornik_zajecie_rachunku` — to
     boilerplate na str.13 (np. wzmianka "rachunku bankowego" wewnątrz
     szablonu wezwania-do-wykazu) wygrywa dopasowaniem-wg-najwcześniejszej-
     pozycji w `_KOMORNIK_TITLES`; naprawa = zawężenie/silniejsza kotwica
     wzorca `komornik_wezwanie_wykaz`, tym samym sposobem co naprawa
     `komornik_skarga` vs `komornik_podjecie_zawieszonego` z 14.07.2026.
   - Jeśli str.13 zwraca `None` (pochłonięta jako kontynuacja) — żaden
     wzorzec z `_KOMORNIK_TITLES`/`_KOMORNIK_FORM_TITLES` nie pasuje do jej
     tytułu (zniekształcony OCR albo brakujący wzorzec) — naprawa = dodać/
     poluzować wzorzec w stylu już istniejących, odpornych na artefakty OCR.

---

## Weryfikacja końcowa

1. Pełna regresja (`python tools/regression_test.py`, bez `--only`) po
   KAŻDEJ z trzech napraw — zmiany w `doc_splitter.py` dotykają wspólnej
   logiki Krok -1/-2/-3 używanej przez wszystkie paczki komornicze/art. 299
   (`egzekucja+zaj._rach.+wyk._majatku.pdf`, `wyrok.pdf`,
   `art299_pozew_nakaz_umorz._egzek..pdf`, `nakaz_zapłaty.pdf`, itd.) —
   wszystkie muszą pozostać PASS.
2. Wpis `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf` w
   `tools/regression_expected.json` (obecnie `main_pages: [1, 6]` — ta
   wartość KODUJE dzisiejszy błąd) zaktualizować DOPIERO po potwierdzeniu
   na żywo, jaki zakres stron/typ wygrywa jako główny po naprawie (może się
   przesunąć na str. 5-6, ale reguła "wszczęcie-first" w `doc_selector.py`
   powinna nadal preferować wszczęcie egzekucji — potwierdzić, nie zakładać).
3. Skrypt diagnostyczny na `main.splitter_segments` (już dostępne w
   `ProcessedDocument`) — potwierdzić DOKŁADNIE 8 segmentów zgodnych z
   granicami użytkownika: [1-4][5-6][7-8][9-10][11-12][13-14][15-16][17-20].
4. Żywy test w Streamlit na realnym pliku: "Zestawienie dokumentów w
   pliku" pokazuje 8 pozycji z poprawnymi zakresami/etykietami (w tym nowa
   pozycja "Wyrok zaoczny"); dokument 805,05 zł ma poprawny dopisek rodzaju
   kwoty; ostrzeżenie "różne sprawy" NIE pojawia się dla pary
   Faliszewska/Barbara Faliszewska.
5. Naprawa 1 nie ma dziś automatycznego testu regresji (banner Streamlit
   nie jest wywoływany przez `regression_test.py`) — dopisać manualne
   sprawdzenie `_parties_differ()`/`_same_person_reordered()` (skrypt
   importujący funkcje z `app.py`) do `memory/project_unrelated_docs_warning.md`,
   tym samym wzorcem co oryginalne 7 przypadków.

## Obowiązkowa synchronizacja dokumentacji (ta sama sesja, przed commitem)

- `CLAUDE.md`: dopisać do istniejących akapitów 14.07.2026 (ostrzeżenie o
  różnych sprawach, WPS/rodzaj kwoty) zamiast tworzyć nowe wpisy dla tej
  samej funkcji; sekcja `doc_splitter.py`/`doc_classifier.py` — nowa
  reguła + decyzje o zbiorach scalania; nowy wpis w "Test documents" dla
  `wyrok_egzekucja+zaj._rach.+wyk._majatku.pdf` (obecnie brak, mimo że plik
  jest testowany od dawna).
- `memory/project_unrelated_docs_warning.md` — dopisać naprawę + ryzyko
  szczątkowe permutacji nazw.
- `memory/project_wyrok_zaoczny.md` — dopisać trzeci błąd tego typu
  dokumentu (07.07 błędna klasyfikacja, 14.07 wyciek kodu K1, teraz brak
  granicy segmentu).
- Nowy wpis lub rozszerzenie `memory/project_komornik_boilerplate_deadlines.md`
  albo `memory/project_wps_amount_labeling.md` (wybrać bliższy tematycznie)
  dla luki w prompt komorniczym.
- Skopiować finalną treść tego planu do `plany/` i zacommitować razem ze
  zmianami kodu (zasada ciągłości pracy między komputerami).
