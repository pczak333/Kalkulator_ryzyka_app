# Plan: Wymiana silnika OCR + debug tekstu

## Context

Claude Vision (haiku) jako silnik OCR generuje dwa problemy:
1. **Koszt**: 6 wywołań API na dokument (jeden na stronę)
2. **Ucięty tekst**: `max_tokens=2000` jest za małe — nakaz zapłaty na 6 stronach
   ma ~2400+ tokenów OCR, więc daty i terminy z ostatnich stron są gubione
3. **Brak diagnozy**: panel techniczny nie pokazuje surowego tekstu OCR,
   więc nie widać co silnik wyciągnął z dokumentu

Claude Vision jest dobry w rozumieniu obrazów, ale słabszy od specjalistycznych
silników OCR dla standardowych drukowanych dokumentów. Nakazy zapłaty są
dokumentami laserowo drukowanymi — Tesseract radzi sobie z nimi lepiej,
szybciej i bezpłatnie.

---

## Rekomendacja: Tesseract (pytesseract) z językiem polskim

Dlaczego Tesseract (nie EasyOCR):
- Dojrzały silnik, sprawdzony na dokumentach prawnych
- Bezpłatny, offline — zero kosztu per strona
- Doskonałe wsparcie polskich znaków diakrytycznych (pol.traineddata)
- Instalacja systemowa przez `packages.txt` na Streamlit Cloud (niezawodna)
- Nie pobiera modeli przy starcie (EasyOCR pobiera ~1 GB przy pierwszym uruchomieniu)

---

## Zmiany do wdrożenia

### 1. `app/doc_ocr.py` — przepisać na Tesseract

Obecna logika (`if page["is_scan"] and api_key: ocr_page(...)`) pozostaje
w `doc_processor.py` bez zmian. Zmieniamy tylko wnętrze funkcji `ocr_page`.

Nowa implementacja:
```python
import pytesseract
from PIL import Image
import io

def ocr_page(page: PageDict, api_key: str | None = None) -> tuple[str, float]:
    image_bytes = page.get("image_bytes")
    if not image_bytes:
        return page.get("text", ""), 1.0
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image, lang="pol", config="--psm 1")
    confidence = 0.3 if not text.strip() else 0.9
    return text.strip(), confidence
```

Uwaga: parametr `api_key` zostaje w sygnaturze (nie zmienia się wywołujący kod),
ale jest ignorowany — Tesseract nie wymaga klucza.

### 2. `app/requirements.txt` — dodać pytesseract

Dodać linię:
```
pytesseract
```

### 3. `packages.txt` — NOWY PLIK w root projektu

Potrzebny dla Streamlit Cloud (instalacja pakietów systemowych):
```
tesseract-ocr
tesseract-ocr-pol
```

### 4. `app/app.py` — dodać surowy tekst OCR do panelu technicznego

W sekcji panelu technicznego (za hasłem `krs-test-2024`) dodać expander:
```python
with st.expander("🔍 Surowy tekst wyekstrahowany z dokumentu"):
    st.text(prefill.raw_text[:3000] if prefill else "(brak dokumentu)")
```

To pozwoli widzieć co Tesseract faktycznie odczytał i diagnozować problemy
klasyfikacji bez zgadywania.

---

## Pliki do zmiany

| Plik | Zmiana |
|---|---|
| `app/doc_ocr.py` | Całkowite przepisanie — Tesseract zamiast Claude Vision |
| `app/requirements.txt` | Dodać `pytesseract` |
| `packages.txt` | Nowy plik: `tesseract-ocr` + `tesseract-ocr-pol` |
| `app/app.py` | Dodać expander z surowym tekstem w panelu technicznym |

---

## Co się NIE zmienia

- `doc_processor.py` — wywołanie `ocr_page(page, api_key)` bez zmian
- `doc_ingestion.py` — wykrywanie skanów (is_scan=True) bez zmian
- `doc_extractor.py`, `doc_classifier.py`, `doc_selector.py` — bez zmian
- Cały formularz i silnik oceny ryzyka — bez zmian

---

## Weryfikacja po wdrożeniu

1. Zainstaluj lokalnie: `pip install pytesseract` + Tesseract z polskim językiem
   - Windows: pobierz instalator z github.com/UB-Mannheim/tesseract/wiki
   - Sprawdź: `tesseract --list-langs` powinno pokazać `pol`
2. Uruchom: `streamlit run app/app.py`
3. Wgraj `nak.zap.3.pdf`
4. W panelu technicznym → "Surowy tekst" sprawdź czy widać pełny tekst nakazu
5. Sprawdź czy wykryta jest data doręczenia i termin (były gubione przy Claude Vision)
6. Sprawdź czy typ dokumentu ma wyższą pewność (zielony tick)
