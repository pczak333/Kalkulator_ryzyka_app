# Audyt kalkulatora przed publikacją strony KRS Guard — 04.08.2026

Kalkulator był w stanie „praca zamknięta" od 22.07 (patrz
[[project_calculator_paused_new_project]]). Wrócono do niego, bo powstaje
strona KRS Guard, która do niego linkuje, a właściciel uznał, że od poprawnego
działania kalkulatora zależy, czy klient zaufa kancelarii i kupi Audyt 48h.

Przeprowadzono **wielowymiarowy audyt** (6 niezależnych recenzji + adwersaryjna
weryfikacja każdego znaleziska, 13 agentów): 43 zgłoszenia → 19 potwierdzonych.
Recenzje „zgodność kodu z regułami CSV" i „ścieżka dokumentu" nie dały ani
jednego potwierdzonego znaleziska — kod się tam obronił.

## Najważniejsze: kalkulator WYSYŁA dane do firm zewnętrznych

Strona KRS Guard obiecywała w 4 miejscach, że dane „nigdzie nie są przesyłane"
i są „usuwane po 24 godzinach". **Oba twierdzenia były nieprawdziwe:**

- **Odpowiedzi z formularza** — faktycznie nie idą do usług AI (to prawda),
  ale przechodzą przez serwer aplikacji (Streamlit działa server-side; wcześniejszy
  skrót myślowy „nie opuszczają przeglądarki" był nieścisły).
- **Wgrany dokument** — `doc_ocr.py` wysyła cały plik do **Microsoft Azure**
  (tylko gdy dokument zawiera skany), a `ai_extractor.py` wysyła pierwsze 4000
  znaków tekstu do **Anthropic** przy KAŻDYM wykrytym dokumencie (`doc_processor.py:162`),
  niezależnie od tego, czy to skan. W tym tekście są imiona, nazwiska, sygnatura, kwoty.
- **Mechanizmu usuwania po 24h NIE MA w kodzie w ogóle.** Nic nie jest zapisywane
  na dysk ani do bazy (zweryfikowane grepem po zapisach) — dane żyją w pamięci
  sesji i znikają po jej zakończeniu, czyli SZYBCIEJ niż obiecywano.

**Decyzja właściciela: Wariant A** — opisać uczciwie, nie wyłączać wgrywania
(odczyt dokumentów zwiększa wiarygodność narzędzia). Wdrożone: notka PRZED
przyciskiem wgrywania (nie po analizie), poprawiony baner po analizie, notka
o danych na początku formularza (widoczna też przy ręcznym wypełnianiu),
plus przepisane teksty na 4 podstronach strony KRS Guard i w polityce prywatności
(Microsoft, Anthropic, Snowflake/Streamlit wymienieni z nazwy + przekazanie poza EOG).

## Naprawione błędy (każdy zweryfikowany testem, nie tylko wzrokowo)

1. **Wynik nie przeliczał się po zmianie odpowiedzi** (`app.py`) — sekcja wyniku
   renderowała się ze starej migawki; klient widział nieaktualną ocenę i mógł
   pobrać niezgodny PDF. Teraz `_state_now` porównywane przy każdym przeładowaniu.
2. **Wyrok zaoczny → porada o nakazie zapłaty** — podmiana tekstów odpalała się
   tylko po wgraniu pliku. Naprawione przez `_K1_IMPLIES_DOC_TYPE`. **Ale pierwsza
   wersja poprawki była niekompletna** — patrz sekcja niżej.
3. **Ostrzeżenie o niepewnym odczycie nie docierało** (`text_builder.py`) —
   raport brał `warnings[:2]`, a HR10/HR11 są dopisywane na końcu listy.
   W 4 z 4 realistycznych scenariuszy ginęło. Teraz mają pierwszeństwo.
4. **„pozostało -201 dni"** — ujemna liczba wyglądała jak awaria. Teraz spokojny
   komunikat, że termin minął + info o możliwości przywrócenia.
5. **Sprzeczność przy minionym terminie** — raport pisał jednocześnie „termin mógł
   już upłynąć" i „pozostało bardzo mało czasu". Dodano `warning_passed` do
   HR01/HR02/HR06, sterowane przez `state["DEADLINE_PASSED"]`. Ryzyko bez zmian.
6. **Obietnica, że Audyt zdąży przed terminem** przy 2–3 dniach → pilny kontakt.
   Plus: nie powołuj się na „dokument", gdy klient nic nie wgrał.
7. **Czerwony błąd zamiast formularza** — `deadline_days` z OCR poza zakresem pola
   wywalał `st.number_input`. Teraz przycinany z informacją dla klienta.

## LEKCJA: podmiana tekstu scenariusza po frazie jest krucha

Poprawka wyroku zaocznego (pkt 2) początkowo **nie działała w większości spraw**.
Kod podmieniał nazwę dokumentu, wyliczając warianty zdania RĘCZNIE — pokrywał
3 z 5 wariantów faktycznie występujących w CSV 12, brakowało m.in. wersji
z EPU/e-Sądu. Efekt: **204 z 360 osiągalnych kombinacji dla członka zarządu**
nadal mówiło klientowi „nakaz zapłaty".

Wykryte dopiero po pytaniu właściciela („czy poprawiłeś dokumentację, zwłaszcza
scenariusze?") — czyli **nie przez test, tylko przez czyjeś dobre pytanie.**

Naprawione regexem `_RE_NAZWA_DOKUMENTU` łapiącym każdy wariant; zweryfikowane
na wszystkich **720 osiągalnych kombinacjach** (0 błędów).

**Jak weryfikować takie zmiany w przyszłości:** nie wystarczy sprawdzić, że
podmiana działa na jednym przykładzie. Trzeba przejść wszystkie osiągalne
kombinacje przez prawdziwy łańcuch `calculate()` → `apply_hard_rules()` →
`find_scenario()` (bo poziom ryzyka nie jest dowolny — wyznacza go punktacja
i twarde reguły, więc wiele kombinacji K2×RISK jest nieosiągalnych i mierzenie
ich zawyża albo zaniża wynik).

## Klucze API — stan na 04.08.2026

- **ANTHROPIC_API_KEY** w `app/.streamlit/secrets.toml` — **działa**. W pliku
  `KALKULATOR_RYZYKA_TOTAL/klucze.txt` są DWA klucze Anthropic; pierwszy jest
  martwy, drugi działa i to on jest w secrets.toml (rozstrzyga notatkę „sprawdzić,
  który jest aktualny").
- **AZURE_DI_KEY** — **NIE działa (401)**, oba klucze z `klucze.txt` odrzucone.
  Zweryfikowane oficjalnym SDK, tak jak woła je aplikacja. Zasób
  `krs-guard.cognitiveservices.azure.com` istnieje i odpowiada (HTTP 200), więc
  problem to same klucze (najpewniej zregenerowane w portalu albo wygasła
  subskrypcja). **Do sprawdzenia w portalu Azure → zasób krs-guard → Keys and Endpoint.**
- Skutek: każdy skan spada na Claude (kaskada Azure→Claude→Tesseract działa
  poprawnie). Odczyt jest bezbłędny, ale **55–65 s na stronę** i drożej.
- **NIE zweryfikowano**, co jest w panelu Streamlit Cloud (produkcja ma własne
  sekrety, niezależne od pliku lokalnego).

## Jakość odczytu — przetestowana realnie

Zbudowano 6 realistycznych polskich dokumentów prawnych ze znaną prawidłową
odpowiedzią i przepuszczono przez prawdziwy silnik. **Wszystkie 6 odczytane
bezbłędnie** (typ, sygnatura, kwota, strony, termin, EPU):
nakaz EPU · pozew art. 299 · decyzja ZUS · faktura za prąd (poprawnie odrzucona
jako niesądowa, pewność 0,9) · skan 300 dpi · **celowo zepsute zdjęcie z telefonu**
(45% rozdzielczości, obrót 1,7°, przyciemnienie, szum) — też bezbłędnie.

Zastrzeżenie: dokumenty generowane, więc mają regularny układ. Prawdziwe pisma
bywają gorsze (pieczątki, dwie kolumny, dopiski). Warto powtórzyć na 2–3
prawdziwych, zanonimizowanych pismach.

## Dokumentacja zaktualizowana

- `CLAUDE.md` — sekcje app.py (4 zmiany „nie cofać bez zrozumienia"),
  hard_rules.py, text_builder.py.
- `dane_wejściowe/csv/11_5B_Twarde_reguly.csv` — warianty `warning_passed`
  dla HR01/HR02/HR06 i priorytet HR10 dopisane w `uwagi_dla_AI`; HR10 ma teraz
  `status_w_kodzie = TAK`. **UWAGA: `load_hard_rules()` jest zdefiniowane, ale
  nigdzie nie wywoływane** — reguły są zaszyte w `hard_rules.py`, CSV to
  dokumentacja. Zmieniając regułę trzeba zaktualizować OBA miejsca.
- **CSV 12 (Biblioteka scenariuszy) świadomie NIE zmieniana** — wyrok zaoczny
  nadal reużywa wierszy nakazu i jest łatany w locie (decyzja produktowa z 07.07).
  Alternatywa (własne wiersze scenariuszy dla wyroku zaocznego) to duża zmiana
  w pliku 472 KB — do rozważenia, jeśli łatanie w locie okaże się dalej kruche.
