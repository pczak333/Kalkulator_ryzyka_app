# Diagnoza: „stare, naprawione błędy wróciły" — przyczyna źródłowa i zabezpieczenie

## Context (dlaczego to się dzieje)

Użytkownik zgłasza, że po wgraniu kilku dokumentów wróciły błędy dawno
naprawione:
1. W odczycie brakuje ustalonych rubryk (pozwany, powód/powódka, termin
   reakcji), a część jest błędnie przypisana (obrazy 1–3).
2. Dokument niezwiązany z tematem kalkulatora dostaje generyczny komunikat
   „oderwany" od jego treści, zamiast rozpoznania („Rozpoznaliśmy ten dokument
   jako: …") — mimo że to było naprawione (obraz 4).

**Przyczyna źródłowa (potwierdzona fizycznie, nie hipoteza):**
`app/.streamlit/secrets.toml` na TYM komputerze ma placeholder zamiast klucza:

```
ANTHROPIC_API_KEY = "wklej-tutaj-nowy-klucz-z-console.anthropic.com"
```

- Plik zmodyfikowany **16.07 o 21:48** (koniec ostatniej sesji) — klucz został
  wtedy usunięty/zrotowany i zostawiono notatkę „wklej NOWY klucz", nigdy nie
  wklejono realnego.
- **Klucz Azure jest prawdziwy** → OCR działa, tekst jest poprawnie odczytany.
- Ale **cała ekstrakcja pól i opis dokumentu idą przez Anthropic (Claude
  Haiku)**, nie przez Azure. Bez ważnego klucza `ai_extractor.extract_fields_ai()`
  nie zwraca danych → pipeline po cichu spada na słabszy regex z
  `doc_extractor.py`.

**Dlaczego to DOKŁADNIE odtwarza „stare" błędy:** wszystkie naprawy z ostatnich
tygodni (czyste nazwy stron, należność główna zamiast WPS, `opis_dokumentu` do
banera out-of-scope, brak fałszywej „grzywny 2000 zł") zostały zbudowane NA
ścieżce AI. Gdy AI nie działa, zostaje regex sprzed tych napraw:
- obraz 1: kwota `2 000,00 zł` (znana fałszywa „grzywna" z boilerplate'u), brak
  powoda/pozwanego/terminu;
- obraz 2: pozwany = fragment zdania („WOODHOME… w ciągu dwóch tygodni…
  zapłacić powodowi kwotę łączną 11 286"), kwota = WPS `11 286` zamiast
  należności głównej `10 530` — klasyczna porażka regexu, którą guard
  `_looks_like_party_name()` łata tylko częściowo;
- obraz 3: powód w bierniku „Radosława Zientarę" (regex łapie odmienioną formę),
  brak pozwanego;
- obraz 4: baner generyczny zamiast „Rozpoznaliśmy ten dokument jako: …", bo
  `doc_description` (= `opis_dokumentu` z AI) jest puste.

**Dlaczego „kręcimy się w kółko" (przyczyna SYSTEMOWA):** fallback AI→regex jest
**całkowicie cichy**. Nigdzie — ani w UI, ani w panelu technicznym — nie ma
sygnału „AI nie zadziałało, widzisz zdegradowany wynik regex". Więc problem
konfiguracyjny (placeholder klucza) albo awaria API (dziś w tej samej sesji
trafiliśmy na błąd 522 z api.anthropic.com) wygląda IDENTYCZNIE jak regresja
kodu. Za każdym razem zgłaszane jest „wróciły stare błędy" i zaczyna się
polowanie w kodzie, który jest poprawny.

Wątek wiąże się z dzisiejszym tematem pracy na wielu komputerach: `secrets.toml`
jest w `.gitignore` (słusznie — sekret nie trafia do repo), więc każdy komputer
ma własną kopię i realny klucz trzeba wkleić lokalnie. Na tym „bazowym"
komputerze nigdy go nie wklejono po rotacji z 16.07.

## Rozwiązanie

Dwie warstwy: (A) natychmiastowa naprawa środowiska, (B) trwałe zabezpieczenie,
żeby ten sam objaw NIGDY więcej nie udawał regresji kodu.

### A. Natychmiast — przywrócić działanie AI (poza kodem)
Wkleić prawdziwy `ANTHROPIC_API_KEY` (z console.anthropic.com) do
`app/.streamlit/secrets.toml`. To sam użytkownik — sekret nie przechodzi przez
repo. Po tym wszystkie 4 objawy znikają bez żadnej zmiany kodu (kod jest
poprawny). Weryfikacja: ponowne wgranie tych samych plików → pola i baner
poprawne.

### B. Trwałe zabezpieczenie — uwidocznić brak AI (zmiana kodu)
Cel: gdy AI nie działa (brak/placeholder klucza LUB awaria API), użytkownik i
panel techniczny MUSZĄ to widzieć — zamiast cicho pokazywać zdegradowany regex.

**Potwierdzone punkty ciszy (z eksploracji kodu):**
- `ai_extractor.py:155-156` — `if not api_key or not text: return {}` (pusty
  klucz łapany, ale placeholder przechodzi dalej).
- `ai_extractor.py:157-172` — jeden `try` wokół całości, `except Exception:
  return {}` bez logu; placeholder → błąd auth → ciche `{}` (raz na segment).
- `doc_processor.py:154` — `if ai_fields:`; `{}` pomija cały blok nadpisań
  (155-203) → czysty regex. Brak jakiejkolwiek flagi statusu.
- `ProcessedDocument` (`doc_processor.py:~117`) nie ma pola statusu ekstrakcji;
  `doc_description=None` to treść, nie sygnał (jest None też, gdy AI działa, ale
  nic nie opisało).
- `app.py:806-811` — klucz czytany dopiero przy „Analizuj", `st.secrets.get(
  "ANTHROPIC_API_KEY","")`, zero walidacji. Brak jakiegokolwiek startowego
  sprawdzenia (potwierdzone: NIE istnieje).

**Elementy naprawy (kolejność wg wartości):**
1. **Walidacja klucza przy analizie** (`app.py`, tuż po zbudowaniu `secrets`
   w ~807-811): jeśli `ANTHROPIC_API_KEY` jest pusty LUB placeholderem
   (heurystyka: nie zaczyna się od `sk-` / zawiera „wklej"/„tutaj"), pokazać
   wyraźny `st.warning`: „Ekstrakcja AI jest wyłączona — odczyt oparty tylko na
   OCR i regułach, pola mogą być niepełne lub błędnie przypisane". Świadomie
   ostrzeżenie, nie twarda blokada (aplikacja ma działać awaryjnie na OCR+regex;
   ten sam wzorzec „ostrzeżenie, nie blok" co inne banery). To JEDNO wystarcza,
   by zdarzenie z dziś nigdy więcej nie udawało regresji kodu.
2. **Flaga `ai_extraction_ok` per dokument** (opcjonalne, mocniejsze): odróżnić
   w `extract_fields_ai` „klucza brak" (pusty → oczekiwane) od „wywołanie padło"
   (wyjątek → sygnał awarii/klucza), przenieść przez `_build_candidate_dict`
   (`doc_processor.py:154`) → dict kandydata → nowe pole `ProcessedDocument`
   (obok `doc_description`, ~117) → mapper `to_pd` (~457). To łapie też **awarię
   API przy poprawnym kluczu** (dziś w tej samej sesji trafiliśmy na 522 z
   api.anthropic.com — placeholder to nie jedyna droga do cichej degradacji).
3. **Status w panelu technicznym** (`app.py`, tuż po `st.subheader("Analiza
   dokumentu (Etap 2)")` ~1389): wyświetlić „Ekstrakcja: AI OK / fallback regex
   / błąd API" per dokument, żeby przyszła diagnoza zajmowała sekundy.

## Verification
- A: po wklejeniu realnego klucza uruchomić `cd app && streamlit run app.py`,
  wgrać pliki z obrazów 1–4 → sprawdzić, że pola (powód/pozwany/termin) są
  kompletne i poprawne, kwoty to należność główna, a baner out-of-scope pokazuje
  rozpoznany opis. Alternatywnie `tools/regression_test.py` (używa tej samej
  ścieżki AI) — powinien wrócić do zieleni.
- B: przetestować OBA stany — z placeholderem klucza (ostrzeżenie widoczne,
  panel pokazuje „fallback regex") i z realnym kluczem (brak ostrzeżenia, panel
  „AI OK”); potwierdzić brak regresji `tools/regression_test.py`.

## Zakres (potwierdzony z użytkownikiem)
- **A — wklejenie klucza**: akcja użytkownika (sekret nie idzie przez repo).
  Wystarcza w 100%, żeby wszystkie 4 objawy zniknęły JUŻ TERAZ — to nie błąd
  kodu, tylko środowiska.
- **B — pełne zabezpieczenie (WYBRANE)**: wszystkie trzy elementy —
  (1) `st.warning` przy pustym/placeholderowym kluczu, (2) flaga
  `ai_extraction_ok` per dokument (łapie też awarię API mimo dobrego klucza),
  (3) status ekstrakcji w panelu technicznym. B nie naprawia bieżących objawów
  (to robi A) — zapobiega temu, żeby przyszła rotacja klucza/awaria API znów
  wyglądała jak regresja i pochłaniała całą sesję.

## Stan bieżący (aktualizacja)
- Użytkownik utworzył NOWY klucz w konsoli (prefiks `kb2...`, nie stare
  `Tzd`/`tA8` — stary `krs-guard-key` żyje na drugim komputerze, do którego nie
  ma teraz dostępu; wartości starych kluczy są nieodzyskiwalne — konsola pokazuje
  tylko zamaskowany podgląd) i wkleił go do `app/.streamlit/secrets.toml`.
- Sprawdzian formatu (read-only) = zielony: `sk-ant-api03-...`, poprawny TOML,
  108 znaków, nie placeholder. Funkcjonalnie NIEPOTWIERDZONY (wymaga wywołania
  API — poza trybem read-only).

## Kolejność wdrożenia
1. **Weryfikacja klucza (najpierw)** — jedno tanie wywołanie: uruchomić
   `extract_fields_ai()` na krótkim syntetycznym tekście prawnym i potwierdzić,
   że zwraca wypełnione pola (klucz autoryzuje się, ścieżka AI żyje). Jeśli OK —
   opcjonalnie przepuścić 1 realny dokument z obrazów 1–4 przez `process_files()`
   i sprawdzić, że pola/baner są poprawne. To dowodzi, że A rozwiązało 4 objawy.
2. **B jako osobny commit** — zmiany w `ai_extractor.py` (rozróżnienie pusty-klucz
   vs wyjątek), `doc_processor.py` (przeniesienie flagi przez candidate →
   ProcessedDocument), `app.py` (walidacja klucza + status w panelu). Czysto
   addytywne — brak zmian w istniejących ścieżkach danych; wg polityki regresji
   pełen `tools/regression_test.py` po zmianie (dotyka warstwy decyzji, choć
   sama ekstrakcja bez zmian — bezpieczniej potwierdzić).
