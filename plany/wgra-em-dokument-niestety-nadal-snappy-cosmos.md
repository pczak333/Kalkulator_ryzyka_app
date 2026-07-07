# Plan: Naprawa kwoty + zestawienie + diagnoza klasyfikacji

## Dokument testowy

`art.299_pismow_przygot._powoda.pdf` — pismo przygotowawcze powoda (10 stron, OCR: Azure, conf 0.987)  
Sprawa: art. 299 KSH, pozwany: Piotr Czak (Woodhome sp. z o.o.)

---

## Problem 1 — Błędna kwota: 12 110,53 zł zamiast 19 142,36 zł

### Dlaczego

Dokument zawiera dwie kwoty w różnych kontekstach:

| Fragment tekstu | Forma słowa | Waluta | Znaczenie |
|---|---|---|---|
| `zasądzenie od pozwanego... kwoty **19.142,36** złotych` | "kwoty" (dopełniacz) | "złotych" | **CAŁKOWITE ROSZCZENIE** ← poprawna kwota |
| `a) kwota **12.110,53** złotych tytułem zobowiązania...` | "kwota" (mianownik) | "złotych" | składnik cząstkowy |

Aktualne wzorce `_KWOTA_PATTERNS` (linie 85–95 `doc_extractor.py`):
```python
_KWOTA_PATTERNS = [
    rf"({_POLISH_NUM})\s*(?:z[łl]|PLN)\b",          # ogólny
    rf"kwot[ęa]\s+({_POLISH_NUM})",                  # kwotę / kwota
    rf"roszczeni[ae].*?({_POLISH_NUM})\s*(?:z[łl]|PLN)",
    rf"nakazuj[eę].*?kwot[ęa]\s+({_POLISH_NUM})\s*(?:z[łl]|PLN)",  # nakaz
]
```

**Dwa problemy jednocześnie:**

1. `kwot[ęa]` (pattern 2) nie pasuje do "kwoty" (dopełniacz „y") → wzorzec nie trafia w 19.142,36
2. `z[łl]|PLN` nie pasuje do "złotych" → żaden wzorzec nie może dopasować 19.142,36 z "złotych"

Efekt: pattern 2 odpada dla 19.142,36, przesuwa się dalej, trafia w "kwota 12.110,53 złotych"
— ale znów "złotych" ≠ `z[łl]|PLN`, więc pattern 2 też nie daje wyniku w normalnym trybie.

**Chwila** — pattern 2 nie wymaga waluty na końcu! `kwot[ęa]\s+({_POLISH_NUM})` — brak `z[łl]`.  
Czyli: `kwot[ęa]` → "kwota" (mianownik) ✓ + `{_POLISH_NUM}` → "12.110,53" ✓ → MATCH.  
Natomiast `kwot[ęa]` dla "kwoty" → dopełniacz "y" nie jest w `[ęa]` → BRAK DOPASOWANIA.  
`re.search()` pomija 19.142,36 i trafia w 12.110,53.

### Fix w `doc_extractor.py`

**Zmiana 1** — rozszerz klasę `kwot[ęa]` o "y" (dopełniacz):
```python
# Było:
rf"kwot[ęa]\s+({_POLISH_NUM})",
# Będzie:
rf"kwot[ęayo]\s+({_POLISH_NUM})",
```
Dopasowuje: "kwotę", "kwota", "kwoty", "kwoto".

**Zmiana 2** — dodaj "złotych"/"złote" do wzorca waluty w patternach 1 i 3:
```python
# Stary fragment z[łl]|PLN → nowy:
(?:z[łl](?:otych?|ote)?|PLN)
```
Dopasowuje: "zł", "zl", "złotych", "złote".

**Zmiana 3 (nowy wzorzec priorytetowy)** — "zasądzenie od pozwanego kwoty X złotych":
```python
# Dodać jako 5. element (sprawdzany PIERWSZY w pętli reversed):
rf"zasądzen\w{{0,4}}[^\n]{{0,150}}kwot\w{{0,3}}\s+({_POLISH_NUM})\s*(?:z[łl](?:otych?|ote)?|PLN)",
```
- `zasądzen\w{0,4}` → "zasądzenie", "zasądzenia", "zasądzić" itd.
- `[^\n]{0,150}` → max 150 znaków na tej samej linii (nie przekracza końca zdania)
- Celuje bezpośrednio w "zasądzenie od pozwanego ... kwoty 19.142,36 złotych"

---

## Problem 2 — Niespójna kwota w zestawieniu: "12 111 zł" vs "12 110,53 zł"

### Dlaczego

W pliku `app.py`, dwa miejsca formatują tę samą kwotę inaczej:

| Miejsce | Kod | Wynik |
|---|---|---|
| Tabela (główna) | `f"{disp_amount:,.2f} zł".replace(",", " ").replace(".", ",")` | **12 110,53 zł** |
| Zestawienie | `f"Kwota: **{doc.amount:,.0f} zł**".replace(",", " ")` | **12 111 zł** ← zaokrąglone |

`.0f` zaokrągla do całości: 12110.53 → 12111 (Python `round(0.53)` = 1). Użytkownik widzi dwie różne liczby.

### Fix w `app.py` (linia ~321)

```python
# Było:
kwota_info = (
    f"Kwota: **{doc.amount:,.0f} zł**".replace(",", " ")
    if doc.amount else ""
)
# Będzie:
kwota_fmt = f"{doc.amount:,.2f}".replace(",", " ").replace(".", ",")
kwota_info = f"Kwota: **{kwota_fmt} zł**" if doc.amount else ""
```

---

## Problem 3 — Błędna klasyfikacja "Pismo Komornik Spolka" (DIAGNOZA — wymaga zmian w CSV)

### Dlaczego (mechanizm)

Pismo przygotowawcze powoda w sprawie art. 299 KSH omawia przeszłe postępowania egzekucyjne
(komornik okazał egzekucję bezskuteczną) — to właśnie UZASADNIA roszczenie z art. 299 KSH.  
Skutek: dokument zawiera masę słów kluczowych dla PISMO_KOMORNIK_SPOLKA:
- "komornik": 13x, "bezskuteczność": 6x, "wierzyciel": 8x, "egzekucja": 3x, "dłużnik": 3x
- PISMO_KOMORNIK_SPOLKA uzyskuje ~33 pkt + bonus adresata +15 (spółka w nagłówku) = ~48 pkt
- POZEW_CZLONEK_ZARZADU uzyskuje ~43 pkt ale bez bonusu adresata = ~43 pkt
- PISMO_KOMORNIK_SPOLKA wygrywa mimo że jest złym typem

### Dlaczego to trudne do naprawienia w kodzie

W CSV 07 (`07_3_Typy_dokumentow.csv`) nie ma typu "pismo przygotowawcze powoda w sprawie art. 299".
To luka w danych wejściowych. Zgodnie z CLAUDE.md: reguły klasyfikacji żyją w CSV, nie w kodzie.

### Rekomendacja

Dodać nowy wiersz do CSV 07 lub zaktualizować istniejący:
- **Opcja A**: Wzmocnić sygnały silne POZEW_CZLONEK_ZARZADU — dodać "pismo przygotowawcze"
  i "art. 299 ksh" jako sygnały silne (+3 każdy) → uzyska więcej punktów niż PISMO_KOMORNIK_SPOLKA
- **Opcja B**: Nowy typ `PISMO_PRZYGOTOWAWCZE_CZLONEK_ZARZADU` z kluczowymi słowami
  "pismo przygotowawcze; art. 299 ksh; strona powodowa; uzasadnienie; wierzytelność"
  i sygnałem "pismo procesowe strony powodowej w sprawie art. 299"

Nie jest to zmiana kodu — wymaga edycji pliku Excel i re-eksportu CSV.
Do realizacji w osobnym kroku (poza tym PR-em).

---

## Pliki do zmiany

| Plik | Co |
|---|---|
| `app/doc_extractor.py` | `_KWOTA_PATTERNS` (nowy wzorzec + rozszerzone klasy), `_parse_amount` (bez zmian — już naprawiony) |
| `app/app.py` | formatowanie kwoty w zestawieniu (linia ~321) |

---

## Weryfikacja

```python
import sys; sys.path.insert(0, 'app')
from doc_extractor import extract_fields

text = '1) zasądzenie od pozwanego na rzecz strony powodowej kwoty 19.142,36 złotych wraz a) kwota 12.110,53 złotych tytułem zobowiązania'
r = extract_fields(text)
assert r['amount'] == 19142.36, f'Oczekiwano 19142.36, dostano {r["amount"]}'
print('OK:', r['amount'])
```

W UI: wgrać `art.299_pismow_przygot._powoda.pdf` → kwota w tabeli i zestawieniu powinna być **19 142,36 zł**.
