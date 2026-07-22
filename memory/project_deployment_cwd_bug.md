---
name: project-deployment-cwd-bug
description: "22.07.2026 — krytyczny bug: doc_classifier.py miał zahardkodowaną, gołą względną ścieżkę do CSV 07, która działała tylko przypadkiem (lokalny dev zawsze robi `cd app` najpierw). Streamlit Cloud uruchamia aplikację z katalogiem roboczym = korzeń repo, nie app/ — ścieżka rozjeżdżała się i KAŻDA klasyfikacja dokumentu padała z FileNotFoundError na świeżym wdrożeniu Cloud. Nigdy niewykryte lokalnie, mimo wielu żywych testów w przeglądarce w tej samej sesji."
metadata:
  node_type: memory
  type: project
  originSessionId: 6c39c185-9261-4919-b8c9-2ce13b654a86
---

## Co się stało

Użytkownik musiał odtworzyć wdrożenie na Streamlit Community Cloud od zera
(`https://kalkulatorryzyka.streamlit.app/`). Po wgraniu dokumentu dostawał
błąd. Pierwsza, rozsądna hipoteza (moja): brakujące klucze API w panelu
Secrets nowego wdrożenia (bo tak wygląda 90% takich problemów — patrz
[[project_ai_key_silent_fallback]]). Użytkownik wkleił klucze poprawnie
(zweryfikowane zrzutem ekranu), ale błąd nie zniknął — okazał się zupełnie
inny: `[Errno 2] No such file or directory: '../dane_wejściowe/csv/
07_3_Typy_dokumentow.csv'`.

## Prawdziwa przyczyna

`app/doc_classifier.py` miał `_CSV_PATH = "../dane_wejściowe/csv/
07_3_Typy_dokumentow.csv"` — goły, względny string, bez odniesienia do
`__file__`. Taka ścieżka jest wrażliwa na **katalog roboczy procesu w
momencie uruchomienia**, nie na lokalizację samego pliku `.py`:

- **Lokalnie** działało zawsze, bo `CLAUDE.md` (sekcja "To run locally")
  jednoznacznie każe najpierw `cd app`, więc katalog roboczy to zawsze
  `app/` → `../dane_wejściowe/...` poprawnie trafia w korzeń repo.
- **Streamlit Community Cloud** (Main file path = `app/app.py`) uruchamia
  proces z katalogiem roboczym = **korzeń repo**, nie `app/` —
  `../dane_wejściowe/...` rozwiązuje się wtedy do katalogu JEDEN POZIOM NAD
  repo, którego nie ma. Efekt: `FileNotFoundError` przy KAŻDEJ próbie
  klasyfikacji dokumentu — całkowita, natychmiastowa awaria funkcji uploadu
  na dowolnym świeżym wdrożeniu Cloud.

`data_loader.py` (inny moduł ładujący CSV) miał od początku POPRAWNY wzorzec
— `os.path.join(os.path.dirname(__file__), "..", "dane_wejściowe", "csv")`
— odporny na katalog roboczy, bo `__file__` zawsze wskazuje na realną
lokalizację skryptu. `doc_classifier.py` był jedynym miejscem w całym `app/`
z tym antywzorcem (potwierdzone grepem `\.\./`/`read_csv\(`/`read_excel\(`
na całym katalogu — zero innych wystąpień).

## Dlaczego to przeszło niezauważone tak długo

Ten sam dzień, ta sama sesja: WIELE żywych testów w przeglądarce
(`streamlit run app.py` z katalogu `app/`, zgodnie z instrukcją) — wszystkie
przechodziły bez problemu, bo lokalny cwd zawsze był poprawny. Błąd jest
strukturalnie niewidoczny dla jakiegokolwiek testowania, które nie
odtwarza DOKŁADNIE środowiska uruchomieniowego produkcji (katalog roboczy
włącznie). Ogólna lekcja: **"działa lokalnie" nie jest dowodem, że kod jest
odporny na katalog roboczy — trzeba albo (a) zawsze budować ścieżki plików
względem `__file__`, nigdy względem bieżącego katalogu, albo (b) explicite
przetestować z innym cwd niż development'owy, przynajmniej raz.**

## Naprawa i weryfikacja

`_CSV_PATH` przebudowany na wzorzec `data_loader.py`
(`os.path.join(os.path.dirname(__file__), "..", ...)`). Zweryfikowane:
1. Odtworzony błąd bezpośrednim wywołaniem `doc_classifier._load_doc_types()`
   z katalogu roboczego = korzeń repo (identyczny `FileNotFoundError`).
2. Po poprawce: działa identycznie z korzenia repo i z `app/` (29 wierszy
   w obu przypadkach).
3. Pełny syntetyczny test `classify_document()` z korzenia repo (symulacja
   cwd Cloud) — poprawny wynik (`NAKAZ_CZLONEK_ZARZADU`, pewność 0.507).

Realnego pliku testowego z folderu `testy` NIE było w tym momencie na tym
komputerze (ten sam nawracający, znany problem znikania plików testowych
między sesjami — patrz notatki przy `wyrok.pdf`/`postanowienie.pdf` w
CLAUDE.md) — stąd weryfikacja syntetycznym tekstem zamiast pełnego
`tools/regression_test.py`. Warto przy najbliższej okazji z prawdziwymi
plikami uruchomić pełną regresję dla pewności, choć logika klasyfikacji
sama w sobie się nie zmieniła (zmieniło się wyłącznie znajdowanie pliku).

## Rozwiązane — potwierdzone przez użytkownika

Auto-deploy po pushu NIE zadziałał od razu (błąd nadal widoczny ~10 minut
po pushu, identyczny komunikat) — potrzebny był RĘCZNY restart z panelu
Streamlit Cloud (`⋮` przy aplikacji → "Reboot app"), potem twarde odświeżenie
strony (Ctrl+F5). Po tym kalkulator zadziałał poprawnie. Warto pamiętać na
przyszłość: po pushu poprawki na świeżo utworzoną (albo długo nieaktywną)
aplikację Cloud, jeśli błąd nie znika mimo upływu paru minut — nie czekać
dalej na auto-deploy, tylko od razu zrobić ręczny "Reboot app".

Przy okazji: zakładka "General" w panelu ustawień aplikacji Streamlit Cloud
NIE pokazuje gałęzi/repo (tylko App URL/subdomenę i wersję Pythona) — brak
widocznej nazwy `main` tam nie jest niczym niepokojącym, to po prostu nie ta
zakładka. Fakt, że aplikacja poprawnie działa po restarcie, jest wystarczającym
potwierdzeniem poprawnej konfiguracji repo/gałęzi/pliku głównego.

Link `https://kalkulatorryzyka.streamlit.app/` jest teraz w pełni sprawny i
gotowy do wysłania drugiej osobie do testów.
