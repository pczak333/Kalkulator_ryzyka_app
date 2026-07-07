---
name: project-etap2-classifier
description: Stan prac nad klasyfikatorem dokumentów (etap2) — nowy typ PISMO_PROCESOWE_SADOWE i historia napraw
metadata: 
  node_type: memory
  type: project
  originSessionId: d94f42e1-6df4-4837-945e-c734e22a79ae
---

## Zrealizowane (2026-06-25)

Dodano obsługę pisma przygotowawczego powoda (art. 299 KSH) — dokumentu wskazującego na toczący się spór bez kompletnej dokumentacji.

**Nowy typ dokumentu:** `PISMO_PROCESOWE_SADOWE` w `dane_wejściowe/csv/07_3_Typy_dokumentow.csv`  
**Mapowanie K1:** `K1_INNE_NIE_WIEM` (w `doc_processor.py`)  
**Reguła HR11:** w `hard_rules.py` — wymaga klucza `DOC_TYPE` w słowniku state (przekazywanego z `app.py`)  
**Baner UI:** w `_show_doc_summary()` w `app.py` gdy `doc_type_code == "PISMO_PROCESOWE_SADOWE"`

**Naprawa 1 (commit c6adb83):** Usunięto `_DOC_TYPES_CACHE`, dodano disambiguację `sad_organ`, dodano bonus +10 dla `PISMO_PROCESOWE_SADOWE`.

## Naprawa 2 (2026-06-26, commit 6f16b0e)

**Problem:** `art.299_pismow_przygot._powoda.pdf` nadal klasyfikowany jako `NAKAZ_CZLONEK_ZARZADU` (wyświetlało "Nakaz zapłaty").

**Przyczyny:**
1. Bonus adresata dla `PISMO_PROCESOWE_SADOWE` wynosił +10 zamiast +15 (nierówność)
2. Pismo przygotowawcze naturalnie zawiera słowa "nakaz zapłaty", "sprzeciw", "pozwany", "art. 299 KSH" jako kontekst narracyjny → NAKAZ_CZLONEK_ZARZADU wygrywał scoring (~22 vs ~15 pkt)

**Fix w `doc_classifier.py`:**
- Bonus adresata +10 → +15 dla `PISMO_PROCESOWE_SADOWE`
- Nowy check: jeśli tekst NIE zawiera `nakazuję pozwanemu` (formuła operatywna nakazu zapłaty) → typy `NAKAZ_*` i `EPU_NAKAZ_*` tracą 20 pkt. Prawdziwy nakaz zawsze ma tę formułę; pismo procesowe jej nie ma.

**Efekt:** Baner ostrzeżenia i HR11 odpaliły jako downstream od poprawnej klasyfikacji.

## Segmentacja PDF (2026-06-26, commit b2027e1)

**Problem:** `nakaz_zapłaty+pozew.pdf` (V GNc, Kraków) klasyfikował się jako POZEW zamiast NAKAZ; zestawienie zawsze pokazywało (1) dokument dla PDF z wieloma sekcjami.

**Przyczyna:** System traktował każdy wgrany plik jako JEDEN dokument. Brak separatorów stron → brak segmentacji → mieszany tekst nakaz+pozew → POZEW wygrywał scoring (art.299 KSH +35 pkt w R27).

**Nowy plik `app/doc_splitter.py`:**
- `_classify_page_segment()` — per-strona klasyfikacja (nagłówek ≤600 zn.)
- `detect_documents_by_pages()` — grupowanie stron w segmenty + przypisanie roli (primary/evidence); art.299 bundle = pozew primary; tradycyjny nakaz = nakaz primary

**Zmienione pliki:**
- `doc_ocr.py`: separatory `--- STRONA X ---` w Azure DI, Tesseract, Claude Haiku
- `ocr_cleanup.py`: zachowaj (nie usuwaj) linie `--- STRONA X ---`
- `doc_processor.py`: natywny PDF dodaje separatory; segmentacja → N kandydatów per plik; `extend` zamiast `append`
- `doc_selector.py`: R17 (+35 gdy deadline), R19-R21 poprawione (35/30/20→30/20/10), tiebreak R5-R6
- `app.py`: 7 brakujących etykiet UI, badge WYMAGA REAKCJI dla każdego doc z terminem

**Wynikowe zachowanie:**
- `nakaz_zapłaty+pozew.pdf` → zestawienie (2): [1/2] Nakaz zapłaty ⚠️ + [2/2] Pozew
- Lublin EPU nakaz: bez regresji (termin 14 dni, czlonek_zarzadu)

## Do zweryfikowania (2026-06-26)

- [ ] `nakaz_zapłaty+pozew.pdf` → zestawienie (2), K1 = Nakaz zapłaty
- [ ] `Lublin_pozew_nak._zap..pdf` → regresja sprawdzona: EPU Nakaz, termin 14 dni
- [ ] Dokumenty jednolite (samo nakaz / sam pozew) → zestawienie (1), brak fałszywych podziałów

## Wskazówka diagnostyczna

Przy kolejnych problemach z klasyfikacją — sprawdź w Panelu technicznym:
1. Wyciągnięte pole `sad_organ` (sąd vs komornik)
2. Czy tekst zawiera formułę operatywną dokumentu (`nakazuję pozwanemu` dla nakazu)
3. Jakie keywords/signals pasują z CSV 07 dla danego typu
4. Czy separatory STRONA X są w tekście (widoczne w raw_text w panelu)
