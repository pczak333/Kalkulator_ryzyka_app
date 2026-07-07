# Plan implementacji: Naprawa segmentacji PDF i błędów klasyfikacji

## Kontekst

Dwa zgłoszone bugi + wyniki audytu 3 agentów ujawniły **wspólną przyczynę źródłową**:
system traktuje każdy wgrany plik PDF jako jeden dokument, zamiast dzielić go na logiczne
sekcje (np. nakaz + pozew w jednym PDF). To powoduje:

1. **Błędna klasyfikacja** — `nakaz_zapłaty+pozew.pdf` klasyfikuje się jako POZEW zamiast
   NAKAZ, bo cały tekst trafia do `classify_document()` i słowa kluczowe POZEW wygrywają
2. **Zestawienie pokazuje (1)** — `aux_docs` zawsze puste gdy wgrany 1 plik, bo 1 plik → 1
   kandydat → 1 dokument główny, lista pomocniczych pusta
3. **Generalizacja** — system sprawdza się tylko na dokumentach wcześniej debugowanych;
   na nowych dokumentach mieszanych (wielosegmentowych) jest zawodny

Kod archiwalny (`app_archiwalna.py`) miał pełne rozwiązanie: separatory stron w tekście OCR
+ `_classify_page_segment()` per strona + `detect_documents_by_pages()` grupujący strony
w logiczne dokumenty.

---

## Lista zmian (priorytetyzowana)

### BLOK 1 — Segmentacja PDF (KRYTYCZNE — root cause)

#### 1a. `app/doc_ocr.py` — dodaj separatory stron we wszystkich silnikach OCR

- `_ocr_azure()` (linia 120–133): w pętli `for page in result.pages` zamiast
  `lines.append(line.content)` — dodawaj `f"\n--- STRONA {page.page_number} ---"` przed
  liniami każdej strony
- `_ocr_tesseract_pages()` (linia 76–93): zamiast `texts.append(text)` daj
  `texts.append(f"--- STRONA {page['page_num']} ---\n{text}")`
- `_ocr_claude()` (linia 154–195): analogicznie — przed `texts.append(text)` dodaj nagłówek
  `f"--- STRONA {page['page_num']} ---\n"`

#### 1b. `app/doc_processor.py` — separator dla natywnych PDF (bez OCR)

W `_process_single_doc()` (linia 91):
```python
# PRZED (bez separatorów):
full_text = "\n".join(p["text"] for p in pages)

# PO:
if ocr_engine != "native":
    pass  # tekst już ma separatory z OCR (patrz 1a)
else:
    full_text = "\n".join(
        f"--- STRONA {p['page_num']} ---\n{p['text']}"
        for p in pages if p["text"]
    )
```

#### 1c. Nowy plik `app/doc_splitter.py` — segmentacja na dokumenty

Zawiera dwie funkcje zaadaptowane z archiwum (`app_archiwalna.py` linia 4209–4468):

```python
def classify_page_segment(page_text: str) -> tuple[str, str] | None:
    """
    Klasyfikuje JEDNĄ stronę wg jej nagłówka (pierwsze 600 znaków).
    Zwraca (doc_type_code, role) lub None jeśli to kontynuacja poprzedniego.

    Logika (w kolejności):
    1. art. 299 KSH w tekście strony → ("POZEW_*", "primary")
    2. "NAKAZ ZAP[LŁ]ATY ... W POST[EĘ]POWANIU" w nagłówku (≤600 zn.) → ("NAKAZ_*", "primary")
       wariant bez polskich znaków ("NAKAZ ZAPLATY ... W POSTEPOWANIU") — OCR fallback
    3. Strona pouczenia (POUCZENIE / SPOSÓB ZASKARŻENIA NAKAZU) → None (kontynuacja)
    4. "POZEW" na początku linii w nagłówku (≤800 zn.) → ("POZEW_*", "primary")
    5. Wzorce na inne typy (wezwanie przedsądowe, komornik, decyzja ZUS itd.)
    6. None = kontynuacja poprzedniego segmentu
    """
    ...

def detect_documents_by_pages(full_text: str) -> list[dict]:
    """
    Dzieli tekst (z separatorami --- STRONA X ---) na logiczne dokumenty.
    Zwraca listę słowników: {doc_type_code, page_range, text, role}

    Logika (z archiwum linia 4342–4468):
    - Podziel wg separatorów
    - Dla każdej strony wywołaj classify_page_segment()
    - Grupuj kolejne strony tego samego typu (np. 3 strony pozwu → 1 segment)
    - Gdy nakaz + pozew w tym samym pliku:
        * art. 299 bundle → POZEW jest primary, NAKAZ jest evidence
        * Tradycyjny nakaz (bez art. 299 skierowanego do człon. zarz.) →
          NAKAZ jest primary (wymaga sprzeciwu/zarzutów), POZEW jest evidence
    - Jeśli tylko 1 segment → zwróć []  (nie ma sensu zestawienia)
    """
    ...
```

Wynikowe `doc_type_code` z segmentu mapuje się na istniejące kody:
- nakaz_upominawczy → `NAKAZ_CZLONEK_ZARZADU` lub `NAKAZ_SPOLKA` (wg `adresat`)
- nakaz_nakazowy → j.w.
- pozew → `POZEW_CZLONEK_ZARZADU` lub `POZEW_SPOLKA` (wg `adresat`)

#### 1d. `app/doc_processor.py` — integracja segmentacji

Zrefaktoruj `_process_single_doc()` tak, żeby zwracał `list[dict]` (może być 1 lub N):

```python
def _process_single_file(
    pages, raw_bytes, ext, secrets, file_ext=""
) -> list[dict]:
    """
    Przetwarza JEDEN plik → zwraca listę kandydatów (1 jeśli jednolity, N jeśli multi-doc).
    """
    # 1. OCR → full_text z separatorami stron (patrz 1a-1b)
    # 2. Próba segmentacji
    from doc_splitter import detect_documents_by_pages
    segments = detect_documents_by_pages(full_text)

    if segments:
        # Wiele logicznych dokumentów — tekst już po OCR (seg["text"]),
        # NIE uruchamiamy ponownie OCR. extract_fields + classify_document per segment.
        candidates = []
        for seg in segments:
            seg_text = clean_ocr_text(seg["text"])
            seg_fields = extract_fields(seg_text)
            doc_type_code, confidence = classify_document(seg_text, seg_fields)
            candidates.append({
                "raw_text":      seg_text,
                "doc_type_code": doc_type_code,
                "confidence":    confidence,
                "epu":           seg_fields.get("epu", False),
                "addressee":     seg_fields.get("adresat"),
                "days_left":     seg_fields.get("deadline_days"),
                "delivery_date": seg_fields.get("delivery_date"),
                "ocr_quality":   "HIGH" if confidence >= 0.75 else "LOW",
                "filename":      filename,
                "page_range":    seg.get("pages", []),
            })
        return candidates
    else:
        # Jednolity dokument — dotychczasowy flow
        return [_process_single_doc(pages, raw_bytes, ext, secrets, file_ext)]
```

Zaktualizuj `process_files()` (linia 164–171) żeby używało nowej funkcji:
```python
for uf in uploaded_files:
    ...
    candidates = _process_single_file(pages, raw_bytes, ext, secrets, ext)
    all_candidates.extend(candidates)  # extend zamiast append
```

---

### BLOK 2 — Poprawki scoringu w `doc_selector.py` (WYSOKI priorytet)

#### 2a. Dodaj brakującą regułę R17 (termin reaktji → +35 pkt)

W `score_candidate()` po bloku R22:
```python
# R17: dokument zawiera wyraźny termin reaktji (sprzeciw, zarzuty, odpowiedź...)
if doc.get("deadline_days") is not None:
    total += 35
```

R17 i R22 mogą oba zadziałać (R22 mówi o BRAKU terminu = +10 dla niepewności,
R17 mówi o OBECNOŚCI terminu = +35). Niespójność do sprawdzenia z CSV — jeśli R17 i R18–R21
są addytywne, kodu nie zmieniam; jeśli R17 zastępuje R22, to `if-elif`.

#### 2b. Napraw R19–R21 — błędna punktacja o +5

W `_deadline_score()` (linia 64–75):
```python
# OBECNY (błędny):    35 / 30 / 20
# POPRAWNY wg CSV:    30 / 20 / 10
if days_left <= 7:   return 30   # był 35
if days_left <= 14:  return 20   # był 30
return 10                         # był 20
```

#### 2c. Dodaj brakujące reguły remisu R5–R6

W `_tiebreak()` (linia 126), po R4 (EPU > inne), przed R7 (data):
```python
# R5: sąd > wierzyciel
a_court = a.get("doc_type_code") in _COURT_TYPES
b_court = b.get("doc_type_code") in _COURT_TYPES
a_cred  = a.get("doc_type_code") in _CREDITOR_TYPES
b_cred  = b.get("doc_type_code") in _CREDITOR_TYPES
if a_court and b_cred: return a
if b_court and a_cred: return b

# R6: komornik > wierzyciel
a_bail = a.get("doc_type_code") in _BAILIFF_TYPES
b_bail = b.get("doc_type_code") in _BAILIFF_TYPES
if a_bail and b_cred: return a
if b_bail and a_cred: return b
```

---

### BLOK 3 — Poprawki UI w `app.py` (WYSOKI priorytet)

#### 3a. Dodaj brakujące etykiety w `_DOC_TYPE_LABELS`

```python
"PISMO_KOMORNIK_CZLONEK_ZARZADU":       "Pismo komornicze",
"PISMO_KOMORNIK_SPOLKA":                "Pismo komornicze (spółka)",
"UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC":   "Postanowienie o umorzeniu egzekucji",
"WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU": "Wezwanie przedsądowe",
"WEZWANIE_PRZEDSADOWE_SPOLKA":          "Wezwanie przedsądowe (spółka)",
"DECYZJA_ZUS_US_SPOLKA":                "Decyzja ZUS / urzędu skarbowego (spółka)",
"PISMO_PROCESOWE_SADOWE":               "Pismo procesowe w toczącym się postępowaniu",
```

#### 3b. Napraw badge "WYMAGA REAKCJI" — pokazuj dla każdego doc z terminem

W `_show_doc_summary()` (linia 336):
```python
# PRZED: tylko gdy status == "GLOWNY"
badge = " ⚠️ **WYMAGA REAKCJI**" if doc.status == "GLOWNY" and doc.deadline_days else ""

# PO: dla każdego dokumentu z terminem
badge = " ⚠️ **WYMAGA REAKCJI**" if doc.deadline_days else ""
```

---

### BLOK 4 — Uzupełnienie K1 mappings w `doc_processor.py` (NISKI priorytet)

Typy bez K1 w formularzu (komornik, umorzenie, wezwanie przedsądowe do spółki itd.)
powinny mapować się na `K1_INNE_NIE_WIEM` — to poprawne zachowanie, bo formularz
nie ma opcji dla tych typów. **Nie wymaga zmian** — obecny fallback `_DOC_TYPE_TO_K1.get(doc_type, "K1_INNE_NIE_WIEM")` jest właściwy.

---

## Pliki do modyfikacji / utworzenia

| Plik | Akcja | Blok |
|---|---|---|
| `app/doc_splitter.py` | **NOWY** — segmentacja per-strona | 1c |
| `app/doc_ocr.py` | Separatory w Azure/Tesseract/Claude | 1a |
| `app/doc_processor.py` | Separatory native, integracja segmentacji | 1b, 1d |
| `app/doc_selector.py` | R17, R19-R21, R5-R6 | 2a, 2b, 2c |
| `app/app.py` | Etykiety, badge | 3a, 3b |

---

## Weryfikacja

### Test 1: `nakaz_zapłaty+pozew.pdf` (nowy dokument)
- **Oczekiwane:** Zestawienie pokazuje (2): [1/2] Nakaz zapłaty ⚠️ WYMAGA REAKCJI + [2/2] Pozew
- **K1:** Pre-fill = Nakaz zapłaty (spółka) lub (członek zarządu) wg adresata
- **Termin:** 14 dni (lub według treści nakazu)
- **Wcześniej:** (1) Pozew — BŁĄD

### Test 2: `Lublin_pozew_nak._zap..pdf` (wcześniej debugowany)
- **Oczekiwane:** Zachowanie bez regresji — EPU Nakaz zapłaty (członek zarządu), termin 14 dni
- Ewentualnie zestawienie (2) jeśli pozew też wykryty jako osobny segment

### Test 3: dokumenty jednolite (samo nakaz, sam pozew, decyzja ZUS)
- **Oczekiwane:** Zestawienie (1), brak fałszywych podziałów, klasyfikacja bez zmian

### Test 4: scoring
- Dokument z terminem 5 dni: R17(+35) + R19(+30) = +65 zamiast tylko R19(+35) — wyraźnie wyższy priorytet
- Remis między pismem sądowym a wezwaniem wierzyciela → sądowe wygrywa (R5)

---

## Ryzyka i uwagi

1. **Azure DI** nie zwraca `page.page_number` w każdej wersji SDK — sprawdzić czy pole
   istnieje i użyć `enumerate()` jako fallback
2. **Nakaz zapłaty w postępowaniu nakazowym** (V GNc jak w `nakaz_zapłaty+pozew.pdf`)
   vs. **nakaz zapłaty w postępowaniu upominawczym** (EPU, Nc-e) — oba muszą być wykryte
   przez `classify_page_segment()`; wzorzec `"NAKAZ ZAP[LŁ]ATY[\s\S]{0,80}W POST[EĘ]POWANIU"`
   pokrywa oba
3. **Fałszywe podziały** — strony pouczenia (POUCZENIE, SPOSÓB ZASKARŻENIA) muszą być
   traktowane jako kontynuacja nakazu, nie nowy dokument; warunek `_is_pouczenie_page`
   z archiwum musi być zachowany
4. **Regresja R17** — jeśli R17(+35) + R18-R21 są addytywne, dokumenty z terminem zyskują
   znacznie (np. nakaz 4-7 dni: +35+30+55+25 = +145). Przed implementacją sprawdzić w CSV
   czy R17 jest łączony z R18-R21 czy zamiennik.
