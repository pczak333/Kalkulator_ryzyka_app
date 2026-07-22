---
name: session-2026-06-24
description: "Podsumowanie sesji 2026-06-24 i 2026-06-25 — OCR kaskada 3 silników, naprawa ekstrakcji pól. Najstarsza zachowana sesja Etapu 2 (kickoff); szczegóły techniczne w dużej mierze przykryte późniejszymi, znacznie obszerniejszymi wpisami (patrz project_etap2_classifier.md i nowsze), zachowana jako historyczny punkt startowy."
metadata:
  node_type: memory
  type: project
  originSessionId: ab9a4781-82d2-4a30-a89e-7c9008b75373
---

## Co zostało zrobione (2026-06-24, ~16:00–koniec)

### Testy kontrolne (17_10_Testy_kontrolne.csv)
- T01, T02 → status ODŁOŻONY – poza MVP (wielodokumentowość nie w MVP)
- T33 → zaktualizowany: EPU wyłączone dla K1_POZEW_SPOLKA
- T35 → dodane konkretne dane K1–K7
- T37–T43 → 7 nowych testów kluczowych

### Checkpoint Etapu 1
- Tag `v1.0-etap1` założony i wypchnięty na GitHub
- `main` → produkcja Etap 1, udostępniona drugiej osobie przez share.streamlit.io — NIE RUSZAĆ (HISTORYCZNE: od 16.07.2026 repo ma jedną gałąź `main`, patrz [[project_branch_consolidation]])

### Etap 2 — implementacja (gałąź etap2)
Nowe pliki: doc_ingestion.py, doc_ocr.py, doc_extractor.py, doc_classifier.py, doc_selector.py, doc_processor.py
Zmiany: app.py (Krok 0 upload), hard_rules.py (HR10), requirements.txt

---

## Co zostało zrobione (2026-06-25)

### Rewizja OCR — kaskada 3 silników (commit a8b58fc)

Poprzedni silnik (Claude Haiku) nie radził sobie z polskimi pismami prawnymi. Wdrożono kaskadę:
1. **Azure Document Intelligence** (`prebuilt-read`) — wysyła CAŁY plik naraz (nie strony PNG); najlepsza dokładność
2. **Tesseract + pol** — per strona, fallback gdy Azure niedostępny
3. **Claude Haiku** — per strona, absolutny ostatni resort

**Klucze w secrets.toml:** AZURE_DI_KEY, AZURE_DI_ENDPOINT (już ustawione przez użytkownika)
**Pakiet:** azure-ai-documentintelligence 1.0.2 zainstalowany

Zmiany plików:
- `doc_ocr.py` — pełny rewrite: `ocr_with_fallback(pages, raw_bytes, ext, secrets)` + 3 prywatne silniki
- `doc_processor.py` — `process_files(files, secrets: dict)` zamiast `api_key`; raw_bytes przed extract_pages(); pole `ocr_engine` w ProcessedDocument
- `app.py` — przekazuje dict z 3 kluczami do process_files()
- `requirements.txt` — azure-ai-documentintelligence>=1.0.0, pytesseract>=0.3.10

**Napotkany błąd:** secrets.toml miał AZURE_DI_ENDPOINT rozbitą na 2 linie → naprawiono (TOML wymaga klucz=wartość w jednej linii)

### Naprawa 3 błędów ekstrakcji pól (commit f3f4d21)

Test z prawdziwym dokumentem (nak.zap.3.pdf — Nakaz Zapłaty Woodhome sp. z o.o.) ujawnił błędy:

| Bug | Przyczyna | Naprawa |
|---|---|---|
| Adresat = czlonek_zarzadu zamiast spolka | Pouczenie (str 3-6) zawierało "osobą fizyczną" → fałszywy hit w całym tekście | Limit adresata do tekstu PRZED słowem POUCZENIE lub max 2000 znaków |
| Wzorce spolka nie działały | W polskim k→c w celowniku: spółk-a → spółc-e. Wzorzec wymagał 'k', nie znajdował 'c' | Zmieniono `k` na `[ck]` w kluczowym miejscu wzorca |
| Termin = None zamiast 14 dni | "dwóch tygodni" nie pasowało do wzorców szukających cyfr + "dni" | Dodano _TERMIN_WRITTEN: "dwóch tygodni"→14, "miesiąca"→30, "trzech miesięcy"→90 itp. |

**Plik doc_extractor.py:** 3 zmiany — `_HEADER_MAX_CHARS`, `header_end = text.find("POUCZENIE")`, `[ck]` w wzorcach spółka, lista `_TERMIN_WRITTEN`

### Co wymagało przetestowania przy następnej sesji (HISTORYCZNE, dawno wykonane)
1. Wgrać nak.zap.3.pdf → sprawdzić czy typ = NAKAZ_SPOLKA + termin = 14 dni
2. Wgrać dokument adresowany do osoby fizycznej → sprawdzić czy nadal wykrywa czlonek_zarzadu
3. Wgrać plik bez POUCZENIE → sprawdzić czy fallback 2000 znaków działa
4. Sprawdzić panel testowy → ocr_engine (azure/tesseract/claude/native)
5. Sprawdzić ścieżkę ręczną (bez uploadu) — musi działać jak Etap 1

**How to apply:** Ten wpis jest wyłącznie historycznym rekordem kickoffu Etapu 2 (OCR jest od tego czasu wielokrotnie przebudowany — patrz doc_ocr.py w CLAUDE.md dla aktualnego stanu kaskady). Nie traktować szczegółów technicznych jako aktualnego stanu kodu.
