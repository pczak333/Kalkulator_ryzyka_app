
# Plan: Poprawa opisów oceny ryzyka dla wezwań sądowych (32 scenariusze)

## Kontekst

Użytkownik wybrał "wezwanie sądowe (spółka / członek zarządu)" i stwierdził, że opisy są całkowicie generyczne — identyczne szablony dla wszystkich wariantów, np. „Sprawa wymaga uporządkowania i szybkiej weryfikacji... Na ocenę wpływają rodzaj dokumentu, czas, EPU...". Brakuje:
- wyjaśnienia czym jest wezwanie sądowe i jakie są konsekwencje braku reakcji (wyrok zaoczny)
- mechanizmu art. 299 KSH dla WEZWANIE_SPOLKA
- rozróżnienia: wezwanie może dotyczyć stawiennictwa, pisma procesowego lub dokumentów
- słowa "byłego" w kontekście byłego członka zarządu

**Co już działa (nie wymaga zmian):**
- `text_builder.py` wyświetla `user_risk_explanation_base` i stosuje filtry K4
- Filtr `_K4_BYLEGO_RE` usuwa "byłego" gdy K4=BOARD_ACTIVE
- Filtr `_K4_PELNOMOCNIK_RE` zastępuje zdanie o pełnomocniku gdy K4=BOARD_ACTIVE

---

## Zakres: 32 scenariusze, brak wariantów EPU

| Typ | Scenariusze | Warianty K2 | Warianty ryzyka |
|---|---|---|---|
| WEZWANIE_SADOWE_CZLONEK_ZARZADU | BASE_141–155 (15 szt.) | 0–3, 4–7, 8–14, >14, nieznany | URGENT, HIGH, MEDIUM, LOW |
| WEZWANIE_SADOWE_SPOLKA | BASE_156–172 (17 szt.) | 0–3, 4–7, 8–14, >14, nieznany | URGENT, HIGH, MEDIUM, LOW |

Brak wariantów EPU (epu_flag = NIE dla wszystkich 32).

---

## Nowe teksty (wzorce)

### WEZWANIE_SADOWE_CZLONEK_ZARZADU

**user_risk_explanation_base** (różnicowany wg risk_level):

- **RISK_URGENT**: „Wezwanie sądowe skierowane bezpośrednio do Ciebie jako byłego członka zarządu oznacza, że postępowanie jest już w toku i sąd wymaga Twojego działania w ściśle określonym terminie. Brak reakcji może skutkować wyrokiem zaocznym lub utratą możliwości obrony."
- **RISK_HIGH**: „Wezwanie sądowe skierowane bezpośrednio do Ciebie jako byłego członka zarządu oznacza, że sąd wymaga Twojej odpowiedzi lub stawiennictwa. Masz jeszcze czas na weryfikację, ale termin i zakres wymaganej reakcji muszą zostać ustalone natychmiast."
- **RISK_MEDIUM**: „Wezwanie sądowe skierowane do Ciebie jako byłego członka zarządu wymaga sprawdzenia treści i terminu. Ryzyko jest umiarkowane, ale brak weryfikacji może spowodować utratę możliwości procesowego działania."
- **RISK_LOW**: „Wezwanie sądowe skierowane do Ciebie jako byłego członka zarządu jest na tym etapie oceniane jako niższe ryzyko. Warto jednak potwierdzić treść wezwania i termin, aby nie przeoczyć wymaganych działań."

**user_practical_meaning_base** (wspólny dla CZLONEK_ZARZADU):

„Wezwanie sądowe jest skierowane bezpośrednio do Ciebie jako byłego członka zarządu. Kluczowe jest ustalenie czego dokładnie sąd wymaga: stawiennictwa na rozprawie, złożenia pisma procesowego, dostarczenia dokumentów czy złożenia wyjaśnień. Termin wskazany w wezwaniu jest ściśle określony przez sąd i nie podlega automatycznemu przedłużeniu — brak reakcji może skutkować wyrokiem zaocznym lub ograniczeniem możliwości obrony."

---

### WEZWANIE_SADOWE_SPOLKA

**user_risk_explanation_base** (różnicowany wg risk_level):

- **RISK_URGENT**: „Wezwanie sądowe dotyczące spółki wymaga pilnej reakcji — jeśli spółka nie odpowie w terminie, sąd może wydać wyrok zaoczny. Po bezskutecznej egzekucji wobec spółki wierzyciel może skierować roszczenie bezpośrednio do Ciebie jako byłego członka zarządu z art. 299 KSH."
- **RISK_HIGH**: „Wezwanie sądowe dotyczące spółki jest istotne z Twojej perspektywy jako byłego członka zarządu — jeśli spółka przegra sprawę lub nie zareaguje, wierzyciel może dochodzić roszczeń bezpośrednio od Ciebie z art. 299 KSH. Masz jeszcze czas na weryfikację, ale działanie jest potrzebne."
- **RISK_MEDIUM**: „Wezwanie sądowe dotyczące spółki wymaga sprawdzenia, czy spółka podjęła już działania. Brak reakcji spółki może w przyszłości przełożyć się na ryzyko z art. 299 KSH dla byłego członka zarządu."
- **RISK_LOW**: „Wezwanie sądowe dotyczące spółki jest na tym etapie oceniane jako niższe ryzyko bezpośrednie. Warto jednak sprawdzić, czy spółka jest aktywnie reprezentowana w postępowaniu — brak reakcji mógłby doprowadzić do wyroku zaocznego."

**user_practical_meaning_base** (wspólny dla SPOLKA):

„Wezwanie sądowe jest skierowane do spółki. Właściwa reakcja zależy od treści wezwania: może to być stawiennictwo pełnomocnika spółki na rozprawie, złożenie pisma procesowego lub dostarczenie dokumentów. Brak reakcji spółki może doprowadzić do wyroku zaocznego i egzekucji, a po jej bezskuteczności — do roszczenia bezpośrednio wobec Ciebie jako byłego członka zarządu z art. 299 KSH. Kluczowe jest ustalenie, czy spółka ma pełnomocnika procesowego i czy planuje zareagować na wezwanie."

*(Zdanie o pełnomocniku zastępowane automatycznie przez `_K4_PELNOMOCNIK_RE` gdy K4=BOARD_ACTIVE)*

---

## Implementacja

### Krok 1 — Aktualizacja CSV 12
Plik: `dane_wejściowe/csv/12_6_Biblioteka_scenariuszy.csv`

Skrypt Python (pandas):
- Warunek A: `main_document_type_code == 'WEZWANIE_SADOWE_CZLONEK_ZARZADU'`
- Warunek B: `main_document_type_code == 'WEZWANIE_SADOWE_SPOLKA'`
- Update `user_risk_explanation_base` wg `(doc_type, risk_level_code)` + `user_practical_meaning_base` wspólny dla doc_type

### Krok 2 — Aktualizacja Excel
`dane_wejściowe/KRS_Guard_reguly_i_zasady_funkcjonowania.xlsx`, arkusz `6_Biblioteka_scenariuszy` — openpyxl, ta sama logika co przy nakaz/EPU.

### Krok 3 — Brak zmian w kodzie aplikacji
`text_builder.py` i `context_modules.py` nie wymagają zmian.

### Krok 4 — Commit i push (jeden commit: CSV + Excel)

---

## Weryfikacja

1. `streamlit run app/app.py`
2. **Test A**: Wezwanie sądowe (członek zarządu) + 14 dni + Była rezygnacja → powinno pojawić się "byłego członka zarządu" i opis wyroku zaocznego
3. **Test B**: Wezwanie sądowe (spółka) + 14 dni + Nadal pełnię funkcję → "byłego" znika, zdanie o pełnomocniku zastąpione aktywną reakcją
4. **Test C**: Wezwanie sądowe (członek zarządu) + 0–3 dni → RISK_URGENT z konkretnym opisem wyroku zaocznego
