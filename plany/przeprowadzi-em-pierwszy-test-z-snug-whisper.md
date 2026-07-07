# Plan naprawczy — Stage 2: analiza dokumentów

## Context

Pierwszy test Stage 2 na pliku `nak.zap.3.pdf` (6-stronicowy skan nakazu zapłaty, 0 znaków embedded text — w całości oparty na OCR). Wynik: niski poziom pewności klasyfikacji, dokument podzielony na dwa fragmenty, pola K2 i K7 ustawione jako UNKNOWN — przez co cały dalszy scoring (scenariusz, tekst ryzyka) nie oparł się na danych z dokumentu.

Użytkownik stwierdził: "wyniki totalnie wzięte z sufitu" i "nie zastosowano żadnych zasad z KRS_Guard". Diagnoza potwierdza: reguły z CSV 07/02/09/11/12 są technicznie załadowane, ale **dane wejściowe do nich są błędne** (K2=UNKNOWN, K7=UNKNOWN, confidence <0.75), bo pipeline ekstrakcji ma konkretne bugi.

---

## Zdiagnozowane błędy (priorytet malejący)

### BUG 1 — KRYTYCZNY: Segmentacja rozbija jeden dokument na dwa
**Plik:** `app/doc_processor.py`, `_segment_pages()` (linie 122–142)

Każdy PDF >3 stron jest mechanicznie cięty na chunki po 3 strony. Skan 6-stronicowy → 2 "dokumenty":
- Chunk A (str. 1–3): OCR z połowy treści → GLOWNY
- Chunk B (str. 4–6): OCR z drugiej połowy → POMOCNICZY

Skutki: każdy chunk ma ułamkowy tekst (brak pełnego kontekstu), niski score klasyfikatora, data doręczenia/kwota mogą być w innym chunku niż klasyfikowany fragment. Stąd: K2=UNKNOWN, K7=UNKNOWN.

**Fix:** Całe załadowane PDF traktuj jako jeden dokument. Porzuć mechaniczne dzielenie na chunki — to był `# TODO` w kodzie ("właściwa segmentacja wymaga szybkiej wstępnej klasyfikacji per stronę"):

```python
def _segment_pages(pages: list[PageDict], api_key: str | None) -> list[dict]:
    if not pages:
        return []
    return [_process_single_doc(pages, api_key)]
```

---

### BUG 2 — KRYTYCZNY: Parser kwot nie obsługuje polskiego formatu liczb
**Plik:** `app/doc_extractor.py`, `_parse_amount()` (linie 90–95)

Polski format: `10.000,00 zł` (kropka = separator tysięcy, przecinek = decimal). Kod robi `s.replace(",", ".")` → `"10.000.00"` → `float()` rzuca ValueError → kwota nigdy nie jest wyodrębniana. K7 = UNKNOWN.

**Fix:**
```python
def _parse_amount(s: str) -> float | None:
    s = re.sub(r"\s", "", s)
    if "," in s:
        # Polskie formatowanie: 10.000,00 → usuń separatory tysięcy → 10000.00
        s = s.replace(".", "").replace(",", ".")
    try:
        val = float(s)
        return val if val > 0 else None
    except ValueError:
        return None
```

---

### BUG 3 — WYSOKI: Fałszywy sygnał EPU — "VI Wydział Cywilny"
**Plik:** `app/doc_extractor.py`, `_EPU_PATTERNS` (linia 14)

Pattern `r"VI\s+Wydzia[łl]\s+Cywilny"` klasyfikuje każdy nakaz z tradycyjnego sądu jako EPU. CSV 07 sam ostrzega: *"Samo oznaczenie VI Wydzial Cywilny nie musi oznaczac e-Sadu"*.

**Fix:** Usuń ten pattern z `_EPU_PATTERNS`. Zostają tylko jednoznaczne sygnały: `Nc-e`, `e-Sąd`, `EPU`, `Elektroniczne Postępowanie Upominawcze`, `Lublin-Zachód`.

---

### BUG 4 — ŚREDNI: Znak "/" w sygnałach CSV traktowany literalnie
**Plik:** `app/doc_classifier.py`, `_score_text()` (linie 20–33)

CSV 07 definiuje sygnały z "/" jako alternatywy (np. `"osoba fizyczna/członek zarządu jako pozwany"`), ale `re.escape()` szuka tego ciągu dosłownie — z ukośnikiem — który nigdy nie pojawia się w dokumencie sądowym. Sygnały silne de facto nic nie punktują.

**Fix:** Po podziale po ";", rozbij każdy token po "/" i punktuj każdy wariant osobno (wystarczy jedno trafienie):
```python
for kw_raw in keywords_raw.split(";"):
    for kw in kw_raw.split("/"):
        kw = kw.strip()
        if kw and re.search(re.escape(kw), text, re.IGNORECASE):
            score += 1
            break  # liczymy raz za cały alternatywny zapis

for sig_raw in signals_raw.split(";"):
    for sig in sig_raw.split("/"):
        sig = sig.strip()
        if sig and re.search(re.escape(sig), text, re.IGNORECASE):
            score += 3
            break
```

---

### BUG 5 — ŚREDNI: Wzorce terminu nie obejmują słownych form
**Plik:** `app/doc_extractor.py`, `_TERMIN_PATTERNS` (linie 53–60)

Pouczenie w nakaz zapłaty często mówi "dwa tygodnie" lub "czternaście dni" zamiast cyfry. Obecne wzorce wymagają `(\d+)\s+dni`.

**Fix:** Dodaj mapowanie słowne przed pętlą wzorców:
```python
_TERMIN_WORD_MAP = {
    r"dw[aóu]\s+tygodni": 14,
    r"dwa\s+tygodnie": 14,
    r"miesi[aą]c": 30,
    r"czternastu\s+dni": 14,
    r"czternaście\s+dni": 14,
    r"siedmiu\s+dni": 7,
    r"siedem\s+dni": 7,
}
```

---

### BUG 6 — NISKI: Brak debugowania w panelu technicznym
**Plik:** `app/app.py` (panel techniczny, sekcja na końcu pliku)

Gdy OCR coś wykrywa ale klasyfikacja jest niepewna, nie ma sposobu zobaczyć co faktycznie odczytał OCR. Utrudnia to diagnozę.

**Fix:** W panelu technicznym (chroniony hasłem) dodaj:
- Surowy tekst głównego dokumentu (pierwsze 2000 znaków)
- Słownik wyekstrahowanych pól (`fields`) z `doc_extractor`
- Wyniki punktacji klasyfikatora per typ dokumentu (top 5)

---

## Pliki do modyfikacji

| Plik | Zmiany |
|------|--------|
| `app/doc_processor.py` | `_segment_pages()` — wyłącz chunking |
| `app/doc_extractor.py` | `_parse_amount()` + usuń EPU pattern + dodaj `_TERMIN_WORD_MAP` |
| `app/doc_classifier.py` | `_score_text()` — obsługa "/" w tokenach |
| `app/app.py` | Panel techniczny — surowy tekst OCR i pola |

---

## Weryfikacja

1. Uruchom `streamlit run app/app.py` lokalnie
2. Wgraj `C:\Users\User\Desktop\testy\nak.zap.3.pdf`
3. Kliknij "Analizuj dokumenty"
4. Oczekiwane wyniki po fixach:
   - Brak sekcji "Wykryto X dodatkowych dokumentów" (jeden dokument zamiast dwóch)
   - Pewność ≥ 0.75 → zielony boks "wykryto automatycznie" (lub żółty "sprawdź" jeśli OCR ma złą jakość — to akceptowalne)
   - Kwota wyświetlona (o ile pojawia się w tekście)
   - EPU = False dla tradycyjnego nakazu (brak fałszywego VI Wydział Cywilny)
5. Kliknij "Oblicz ryzyko" — sprawdź że scenariusz jest spójny z K1=nakaz/członek zarządu
6. Commit + push do `etap2`
