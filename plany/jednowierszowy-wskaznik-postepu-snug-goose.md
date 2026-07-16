# Jednowierszowy, anonimowy wskaźnik postępu OCR/AI

## Kontekst

Wskaźnik postępu (`st.status`, wdrożony 15.07.2026 jako zamiennik statycznego
`st.spinner`) działa technicznie poprawnie, ale renderuje się nieprofesjonalnie:
każde wywołanie `on_progress(msg)` woła `status.write(msg)`, a `st.status.write()`
w Streamlicie **zawsze dopisuje nowy wiersz** — nie ma trybu nadpisywania w
miejscu. Przy długim skanowaniu (Azure poll co 2s) albo wielostronicowym
dokumencie (Tesseract/Claude po jednej stronie) to setki rosnących wierszy w
jednej sesji (zrzut ekranu użytkownika, obraz1).

Dodatkowo część komunikatów wprost ujawnia, z jakiego silnika OCR korzysta
aplikacja ("(Azure Document Intelligence)", "(Claude)", "(Tesseract)") — to
szczegół implementacyjny, który nie powinien być widoczny dla klienta.

Cel: jeden wiersz, który aktualizuje się w miejscu (nie mnoży się), bez nazw
silników w treści.

## Podejście

Wykorzystać wbudowany mechanizm `st.status`: kontener ma jeden `label`, który
można nadpisywać przez `status.update(label=...)` — to jest natywny,
"jednowierszowy" odpowiednik tego, czego chce użytkownik (Streamlit renderuje
go jako pojedynczą linię obok ikony spinnera/✓/✗, bez akumulacji).

**Zmiana 1 — `app/app.py` (~linia 729–743):**
- Callback przekazywany do `process_files()`: zamienić
  `on_progress=lambda msg: status.write(msg)` na
  `on_progress=lambda msg: status.update(label=msg)`.
- `expanded=True` → `expanded=False` w wywołaniu `st.status(...)` (linia ~731)
  — skoro w środku nic już nie jest zapisywane (`.write()` usunięte), rozwinięty
  kontener pokazywałby pustą przestrzeń pod nagłówkiem; zwinięty pokazuje
  wyłącznie aktualizowany nagłówek, dokładnie jeden wiersz.
- Wywołania `status.update(label="Analiza nie powiodła się", state="error")`
  i `status.update(label="Analiza zakończona ✓", state="complete", expanded=False)`
  zostają bez zmian (już nadpisują ten sam label, zgodne z nowym zachowaniem).

**Zmiana 2 — `app/doc_ocr.py`: usunięcie nazw silników z treści komunikatów**
(sam kod kaskady OCR — który silnik jest wołany — bez zmian, zmienia się
wyłącznie tekst przekazywany do `on_progress`):
| Linia | Przed | Po |
|---|---|---|
| 46 | `"OCR: analizuję dokument (Azure Document Intelligence)..."` | `"OCR: analizuję dokument..."` |
| 70 | `"OCR: jakość Azure poniżej progu — eskaluję do Claude Haiku..."` | `"OCR: doprecyzowuję odczyt dokumentu..."` |
| 116 | `f"OCR: strona {i}/{len(scan_pages)} (Tesseract)..."` | `f"OCR: strona {i}/{len(scan_pages)}..."` |
| 164 | `f"OCR: przetwarzam dokument (Azure)... {elapsed}s"` | `f"OCR: przetwarzam dokument... {elapsed}s"` |
| 220 | `f"OCR: strona {i}/{len(pages)} (Claude)..."` | `f"OCR: strona {i}/{len(pages)}..."` |

Komentarze/docstringi w kodzie (np. `# Silnik 1: Azure Document Intelligence`)
zostają bez zmian — to nie jest tekst widoczny dla użytkownika, tylko
dokumentacja wewnętrzna.

**Bez zmian:** `app/doc_processor.py` (komunikaty "Analizuję dokument N/M w
paczce...", "Wczytuję plik N/M: nazwa...") już nie wspominają silnika — trafiają
do tego samego callbacku, więc automatycznie skorzystają z jednowierszowego
zachowania po Zmianie 1.

## Weryfikacja

`tools/regression_test.py` nie renderuje UI Streamlit (woła `process_files()`
bezpośrednio, bez `on_progress`) — nie wykryje regresji ani nie potwierdzi
poprawki. Zgodnie z doświadczeniem z sesji 15.07 (ten sam widget, złapany wtedy
błąd zagnieżdżenia expanderów niewidoczny w diffie) zmiana **wymaga żywego testu
w przeglądarce** (skill `agent-browser`): wgrać wielostronicowy plik testowy
(np. z `C:\Users\User\Desktop\testy\`), obserwować, że w trakcie analizy
widoczny jest DOKŁADNIE jeden aktualizujący się wiersz (bez przyrastającej
listy), że żaden komunikat nie wspomina Azure/Claude/Tesseract, oraz że po
zakończeniu kontener poprawnie pokazuje "Analiza zakończona ✓" (stan `complete`)
bez błędów w konsoli.

Po potwierdzeniu: zaktualizować `CLAUDE.md` (sekcja `app.py`/`doc_ocr.py`) i
`memory/project_progress_indicator.md` zgodnie z zasadą projektu "dokumentacja
na bieżąco", a następnie commit + push na `etap2`.

## Wynik implementacji (16.07.2026)

Zaimplementowane dokładnie wg planu, plus dodatkowa zmiana zrealizowana w tej
samej sesji przed tym zadaniem: guard dla Fix B w `doc_selector.py` (patrz
`memory/project_unrelated_docs_warning.md`), która wymagała przeniesienia
`_normalize_party_name`/`_parties_differ` z `app.py` do `doc_selector.py` —
stąd diff w `app/app.py` obejmuje też usunięcie tych funkcji i nieużywanego
`import re`, niezwiązane z samym wskaźnikiem postępu.

Zweryfikowane żywym testem w przeglądarce (`nakaz_zapłaty+pozew.pdf`, 12 stron):
dokładnie jeden aktualizujący się wiersz przez cały czas trwania analizy, bez
nazw silników, wynik końcowy zgodny z udokumentowanymi wartościami tego pliku
— brak regresji. Szczegóły w `memory/project_progress_indicator.md`.
