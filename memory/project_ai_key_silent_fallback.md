---
name: ""
metadata: 
  node_type: memory
  originSessionId: 0762d789-aa1a-4a44-ad46-1b716f26f112
---

**Objaw:** użytkownik zgłasza, że dawno naprawione błędy odczytu wróciły —
brakuje pól (powód/pozwany/termin), pola błędnie przypisane (fragment zdania
jako "pozwany"), kwota = WPS zamiast należności głównej, powód w bierniku,
a dokument out-of-scope dostaje generyczny baner zamiast "Rozpoznaliśmy ten
dokument jako: ...".

**Przyczyna (21.07.2026, potwierdzona fizycznie):** `app/.streamlit/secrets.toml`
na danym komputerze miał PLACEHOLDER zamiast klucza:
`ANTHROPIC_API_KEY = "wklej-tutaj-nowy-klucz-z-console.anthropic.com"`.
Cała ekstrakcja pól + `opis_dokumentu` idą przez Claude Haiku (`ai_extractor.py`);
Azure (OCR) to osobny, prawdziwy klucz → tekst czytany poprawnie, ale ekstrakcja
AI martwa → pipeline PO CICHU spadał na słabszy regex z `doc_extractor.py`.
Wszystkie naprawy ostatnich tygodni zbudowano NA ścieżce AI, więc bez klucza
zostaje regex sprzed tych napraw = dokładnie "stare" błędy.

**DLACZEGO kręciliśmy się w kółko (przyczyna systemowa):** fallback AI→regex był
CAŁKOWICIE CICHY — `ai_extractor.py` łapał każdy błąd w `except Exception:
return {}`, `doc_processor.py` traktował `{}` jako "użyj regex", zero flagi,
zero sygnału w UI/panelu. Więc placeholder klucza / awaria API (dziś w tej samej
sesji trafiliśmy na 522 z api.anthropic.com) wyglądały IDENTYCZNIE jak regresja
kodu → polowanie w kodzie, który był poprawny.

**Kontekst wieloкomputerowy:** `secrets.toml` jest w `.gitignore` (słusznie —
sekret nie idzie do repo), więc każdy komputer ma własną kopię i klucz trzeba
wkleić lokalnie. Placeholder wstawiono 16.07 (rotacja klucza), nowego nie
wklejono na "bazowym" komputerze. Klucze Anthropic są NIEODZYSKIWALNE — konsola
pokazuje tylko zamaskowany podgląd (`sk-ant-api03-tA8...dAAA`); zgubioną wartość
trzeba skopiować z innego komputera albo utworzyć NOWY klucz. Powiązane:
[[project_branch_consolidation]] (ciągłość między komputerami), [[feedback_git_workflow]].

**Why:** identyczny objaw dla dwóch zupełnie różnych przyczyn (bug kodu vs brak
klucza) marnuje całe sesje. Diagnoza musi zaczynać się od TANIEGO sprawdzenia,
która to warstwa.

**How to apply:**
1. Gdy "naprawione błędy wróciły" i dotyczą JAKOŚCI ODCZYTU (pola/kwoty/opis) —
   NAJPIERW sprawdź klucz, nie koduj: `grep ANTHROPIC_API_KEY app/.streamlit/secrets.toml`
   (placeholder zaczyna się od "wklej"/nie od `sk-ant-`). Szybki test bez UI:
   `extract_fields_ai_with_status(krótki_tekst, klucz)` → status `"ok"` znaczy AI
   żyje; `"no_key"`/`"failed"` znaczy fallback regex.
2. Naprawa objawów = wkleić prawdziwy klucz (akcja użytkownika, sekret nie idzie
   przez rozmowę). To NIE jest bug kodu.

**Zabezpieczenie wdrożone tej sesji (commit — patrz git):** nowe
`ai_extractor.extract_fields_ai_with_status()` zwraca `(pola, status)` gdzie
status ∈ ok/no_key/failed (`extract_fields_ai` zostało jako cienki wrapper,
zgodność wsteczna); `ProcessedDocument.ai_extraction_status` (domyślnie "ok")
przeniesione przez `_build_candidate_dict`→dict→`to_pd`; `app.py` pokazuje
`st.warning` nad odczytem gdy status≠ok (persystentny po rerunie, czyta z
`prefill`, `getattr(...,"ok")` bezpieczny dla starego session_state) + wiersz
"Ekstrakcja AI: ✅/⚠️" w panelu technicznym. Świadomie OSTRZEŻENIE, nie blokada
(app ma działać awaryjnie na OCR+regex). Status z realnego przebiegu, nie ze
sprawdzenia formatu klucza — łapie też klucz o poprawnym formacie, ale
wygasły/odwołany. Czysto addytywne: pola ekstrakcji bez zmian, smoke-test
`regression_test.py --only "Lublin_pozew_nak._zap.2.pdf"` PASS.
