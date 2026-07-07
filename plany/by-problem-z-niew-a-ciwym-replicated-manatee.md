# Plan: Naprawa klasyfikacji PISMO_KOMORNIK_SPOLKA → PISMO_PROCESOWE_SADOWE

## Kontekst

Dokument `art.299_pismow_przygot._powoda.pdf` nadal klasyfikuje się jako `PISMO_KOMORNIK_SPOLKA` mimo dodania nowego typu `PISMO_PROCESOWE_SADOWE`. Trzy niezależne przyczyny:

### Przyczyna 1 — Cache CSV w doc_classifier.py (krytyczna)
`_DOC_TYPES_CACHE` (linia 10) to globalna zmienna modułu Pythona. CSV jest ładowane JEDEN raz na sesję procesu. Gdy aplikacja działa, nowy typ `PISMO_PROCESOWE_SADOWE` jest niewidoczny — niezależnie od zmian w CSV — dopóki nie nastąpi pełny restart (`Ctrl+C` → `streamlit run`).

### Przyczyna 2 — sad_organ zupełnie ignorowany przez klasyfikator
`doc_extractor.py` wyciąga `sad_organ = "Sąd Rejonowy dla Krakowa-Śródmieścia"` — czyli SĄDEM, nie komornikiem. Ale `doc_classifier.py` nigdzie tego pola nie używa. Komornicze typy nie są penalizowane, gdy dokument pochodzi z sądu.

### Przyczyna 3 — PISMO_PROCESOWE_SADOWE nie dostaje bonusu za adresata
Bonus adresata (`+15`) jest przyznawany tylko gdy w `code` jest `_CZLONEK_ZARZADU`, `_SPOLKA` itp. `PISMO_PROCESOWE_SADOWE` nie zawiera żadnego z tych wzorców → zero bonusu, podczas gdy `PISMO_KOMORNIK_SPOLKA` dostaje `+15` jeśli `adresat=spolka`.

---

## Pliki do zmiany

1. `app/doc_classifier.py` — trzy poprawki w jednym pliku

---

## Implementacja — tylko `app/doc_classifier.py`

### Zmiana 1: Usuń cache (linie 10–17)

Zamień:
```python
_DOC_TYPES_CACHE: pd.DataFrame | None = None

def _load_doc_types() -> pd.DataFrame:
    global _DOC_TYPES_CACHE
    if _DOC_TYPES_CACHE is None:
        _DOC_TYPES_CACHE = pd.read_csv(_CSV_PATH, sep=";", encoding="utf-8-sig", header=1)
    return _DOC_TYPES_CACHE
```

Na (zawsze odczytuj CSV, plik ma <3KB, koszt pomijalny):
```python
def _load_doc_types() -> pd.DataFrame:
    return pd.read_csv(_CSV_PATH, sep=";", encoding="utf-8-sig", header=1)
```

### Zmiana 2: Dodaj bonus adresata dla PISMO_PROCESOWE_SADOWE (linia ~65–66)

W bloku adresat-bonus, po ostatnim `elif adresat == "organ"...`, dopisać:
```python
elif code == "PISMO_PROCESOWE_SADOWE" and adresat in ("czlonek_zarzadu", "spolka"):
    base += 10
```

### Zmiana 3: Penalizuj typy komornicze gdy sad_organ to sąd (po pętli, przed `if not scores:`)

Po zamknięciu pętli `for _, row in df.iterrows():`, dopisać:
```python
# Disambiguacja: sąd vs. komornik na podstawie wyciągniętego sad_organ
_sad_organ = (fields.get("sad_organ") or "").lower()
if _sad_organ:
    _is_court   = "sąd" in _sad_organ or "sad" in _sad_organ
    _is_bailiff = "komornik" in _sad_organ
    if _is_court and not _is_bailiff:
        for _c in list(scores):
            if "KOMORNIK" in _c:
                scores[_c] = max(0, scores[_c] - 25)
    elif _is_bailiff and not _is_court:
        for _c in list(scores):
            if "KOMORNIK" not in _c and "UMORZENIE" not in _c:
                scores[_c] = max(0, scores[_c] - 15)
```

Wartość `-25` jest celowo silna: komornicze typy mają typowo 3–8 pkt z kw. + ew. +15 adresat = maks ~23 pkt. Odjęcie 25 zeruje je, gdy sad_organ wskazuje na sąd.

---

## Weryfikacja

1. Zrestartować aplikację (`Ctrl+C` → `streamlit run app/app.py`) — to czyści stary cache Python
2. Wgrać `art.299_pismow_przygot._powoda.pdf` → typ powinien pokazać się jako **"Pismo procesowe w toczącym się postępowaniu sądowym"**
3. Baner ostrzeżenia o niekompletnej dokumentacji powinien być widoczny
4. Test regresji: wgrać dokument komornicze (jeśli dostępny) → nadal powinien klasyfikować jako PISMO_KOMORNIK_*
5. Sprawdzić Panel techniczny → `doc_type_code`, `sad_organ`, `ocr_engine`, wyciągnięte pola
