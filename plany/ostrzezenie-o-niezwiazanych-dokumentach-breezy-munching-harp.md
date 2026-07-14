# Ostrzeżenie, gdy wgrane dokumenty dotyczą różnych spraw (różny wierzyciel)

## Twoje pytanie i moja odpowiedź

Tak, mam pomysł — i da się go zrobić bez nowego wywołania AI, bo pole `powod`
(wierzyciel) jest już wyciągane dla KAŻDEGO dokumentu w paczce (nie tylko głównego).
Wystarczy porównać `powod` dokumentu głównego z `powod` dokumentów pomocniczych —
gdy są WYRAŹNIE różne, pokazać jawną adnotację.

## Kontekst (test case)

Wgrałeś dwa pliki: `299_przeds._wezw._do_zap..pdf` (wybrany jako główny — Wezwanie
przedsądowe, wierzyciel **MIPROMET Sp. z o.o.**, kwota 1 067,03 zł, termin 3 dni) i
`art.299_nak_zap.pdf` (pomocniczy — Nakaz zapłaty, sygn. V GNc 1138/23/S, wierzyciel
**KILOUTOU Polska sp. z o.o.**, kwota 2 000,00 zł). Zweryfikowałem: oba pola `powod`
faktycznie wychodzą z ekstrakcji AI poprawnie (MIPROMET / KILOUTOU) — dwaj RÓŻNI
wierzyciele. Wybór dokumentu głównego był poprawny (wezwanie z krótszym terminem 3 dni
ma wyższy priorytet), ale nigdzie nie ma adnotacji, że dokument pomocniczy dotyczy
INNEJ sprawy/wierzyciela niż główny — użytkownik może błędnie założyć, że to jeden,
spójny przypadek (tak jak przy prawdziwych bundlach: nakaz+pozew tej samej sprawy,
łańcuch art. 299 pozew+nakaz+egzekucja+umorzenie).

**Dlaczego akurat `powod`, nie `sygnatura`**: sygnatura NIE jest wiarygodnym sygnałem
"różne sprawy" — ten kalkulator ma już rozbudowaną, poprawną obsługę bundli, w których
sygnatura LEGALNIE się różni w obrębie JEDNEJ sprawy (sygnatura sądowa nakazu vs numer
Km komornika w łańcuchu nakaz→egzekucja→umorzenie). Wierzyciel (`powod`) natomiast NIE
zmienia się w obrębie jednej, spójnej sprawy — różny wierzyciel to zawsze dwie odrębne
sprawy, nawet jeśli dotyczą tego samego dłużnika. To dokładnie ten sam typ sygnału,
którego już użyliśmy wcześniej w tej sesji (strukturalne pola zamiast zgadywania).

## Rozwiązanie

**`app/app.py`** (`_show_doc_summary()`): nowa funkcja pomocnicza `_parties_differ(a, b)`
— normalizuje dwie nazwy (uppercase, usuwa formy spółkowe "sp. z o.o."/"S.A." itd.,
normalizuje spacje) i sprawdza, czy żadna nie jest podciągiem drugiej (toleruje drobne
różnice OCR/zapisu, np. "MIPROMET Sp. z o.o." vs "MIPROMET Spółka z ograniczoną
odpowiedzialnością"). Nowy blok: dla każdego `aux_docs`, gdy `main.powod` i `doc.powod`
są oba niepuste i `_parties_differ()` zwraca True — zbierz do listy "dokumentów innej
sprawy". Gdy lista niepusta — `st.warning()` z jawną treścią, np.:

> **Uwaga: część przesłanych dokumentów może dotyczyć innej sprawy.** Dokument główny
> wskazuje wierzyciela **{main.powod}**, ale dokument pomocniczy "{etykieta}" wskazuje
> innego wierzyciela: **{doc.powod}**. Jeśli to pomyłka, prześlij dokumenty każdej
> sprawy osobno w oddzielnych analizach. Jeśli to zamierzone (np. kilku wierzycieli
> tego samego dłużnika) — możesz kontynuować, ale ocena ryzyka poniżej dotyczy
> WYŁĄCZNIE dokumentu głównego.

Umieszczone w `_show_doc_summary()` przed "Zestawienie dokumentów w pliku" (widoczne
zanim użytkownik przejdzie do szczegółów). Działa niezależnie od tego, czy dokumenty
pochodzą z jednego, czy z dwóch osobno wgranych plików — nie trzeba rozróżniać
pochodzenia, samo porównanie `powod` wystarcza i jest bezpieczne dla prawdziwych
bundli (tam wierzyciel jest zawsze ten sam, więc reguła nigdy fałszywie nie odpali).

**Bez zmian**: logika wyboru dokumentu głównego (`doc_selector.py`) — to osobny temat.
Przy okazji odkryty, ale NIE naprawiany w tym kroku: `doc_selector.py`'s "Fix B"
(upgrade SPOLKA→CZLONEK_ZARZADU) skanuje CAŁY tekst paczki pod kątem "art. 299"/"członek
zarządu", więc teoretycznie mógłby się mylnie aktywować pod wpływem dokumentu z innej
sprawy w paczce. W tym konkretnym przypadku nieistotne (dokument główny już poprawnie
ma sufiks `_CZLONEK_ZARZADU` z własnej treści), ale warto to zanotować w pamięci
projektu jako temat do obserwacji przy przyszłych zgłoszeniach.

## Weryfikacja

1. Test `_parties_differ()` na parach: "MIPROMET Sp. z o.o." vs "KILOUTOU Polska sp. z
   o.o." → True; "MIPROMET Sp. z o.o." vs "MIPROMET Spółka z ograniczoną
   odpowiedzialnością" → False (ta sama firma, inny zapis); brak jednej z wartości →
   False (brak fałszywego alarmu).
2. Żywy test w Streamlit z tymi dwoma plikami — baner pojawia się z poprawną treścią
   (nazwy wierzycieli, etykieta dokumentu pomocniczego).
3. Sanity check na prawdziwym, spójnym bundlu z tym samym wierzycielem w każdym
   dokumencie (jeśli dostępny plik testowy) — baner NIE pojawia się.
4. `tools/regression_test.py` — bez regresji (nowy banner nie zmienia main_type/
   amount/deadline/gate sprawdzanych przez regression_expected.json).
5. Zaktualizować CLAUDE.md (`app.py`) i pamięć projektu przed commitem.

---

**Status: w pełni zaimplementowane i zweryfikowane w tej samej sesji (14.07.2026).**
Zobacz `memory/project_unrelated_docs_warning.md` po pełne wyniki weryfikacji i commit
`cce132b` w historii gita gałęzi `etap2`.
