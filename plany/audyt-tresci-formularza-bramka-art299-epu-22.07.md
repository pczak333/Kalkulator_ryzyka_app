# Plan: konkretne poprawki tekstów w formularzu (bramka art. 299 + EPU)

## Context

Audyt treści formularza K1-K7 (przeprowadzony w tej samej sesji, wnioski
przedstawione użytkownikowi na czacie) wykazał, że większość formularza
(K2-K7) jest napisana dobrze — konkretnie, empatycznie, bez żargonu. Dwa
miejsca odstają i akurat leżą na samym początku ścieżki użytkownika (moment,
który najbardziej waży na pierwszym wrażeniu o profesjonalizmie narzędzia):

1. **Bramka art. 299 KSH** (`app/app.py` ok. linii 962-991) — gęste,
   urzędnicze zdanie bez wyjaśnienia, żadnego "Dlaczego pytamy?" (w
   odróżnieniu od WSZYSTKICH kroków K1-K7, które taki expander mają).
2. **Sekcja EPU / Krok 2** (`app/app.py` ok. linii 1066-1081) — checkbox z
   żargonem sądowym ("sygnatura Nc-e") wprost w treści etykiety, zanim
   ktokolwiek otworzy pomocniczy expander.

Użytkownik zaakceptował kierunek: zaproponować konkretne przeformułowania
tych dwóch miejsc (nie ruszamy K1's problemu strukturalnego — 14 opcji i
brak "Wezwanie przedsądowe (spółka)" — to osobna, dużo większa zmiana
wymagająca CSV+Excel+scoring, celowo NIE w zakresie tego kroku).

Przy okazji audytu wykryto też: kolumna `question_text` w CSV 08 (
`dane_wejściowe/csv/08_4_Formularz_6_krokow.csv`) jest martwa (nigdzie nie
odczytywana w kodzie — `grep question_text app/` = brak wyników), a realny,
wyświetlany tekst pytań jest zahardkodowany w `app.py` i w 6 z 7 kroków
(K1, K3, K4, K5, K6, K7 — tylko K2 się zgadza) różni się od tego, co jest w
CSV. To narusza własną zasadę projektu ("nigdy nie hardkoduj tekstów
sterowalnych z CSV, jeśli CSV ma tę kolumnę") dla najważniejszego tekstu w
formularzu. Proponuję to naprawić przy okazji — nie zmieniając zachowania
appki (nadal hardkodowany tekst w `app.py` pozostaje źródłem wyświetlanym),
tylko synchronizując CSV+Excel tak, by `question_text` opisywał to, co
FAKTYCZNIE jest pokazywane (dokumentacja ma opisywać rzeczywistość, nie
odwrotnie — przepisywanie 6 wywołań `labeled_radio()` pod CSV byłoby
ryzykowniejszą, kosmetyczną zmianą bez żadnej korzyści dla użytkownika).

## Zmiana 1 — Bramka art. 299 KSH (`app/app.py`, ok. linii 962-991)

**Dziś:**
```
### Potwierdzenie zakresu sprawy
[info] Dokument wskazuje, że pozwanym jest **osoba fizyczna**. Kalkulator
KRS Guard służy wyłącznie do oceny ryzyka w sprawach o **odpowiedzialność
członka zarządu spółki (art. 299 KSH)**.

**Czy sprawa, której dotyczy ten dokument, wynika z odpowiedzialności za
zobowiązania spółki z tytułu pełnienia funkcji członka zarządu?**

[Tak — sprawa dotyczy art. 299 KSH]   [Nie — to inna sprawa]
```

**Propozycja** (prostszy język na pierwszym planie, podstawa prawna jako
doprecyzowanie w nawiasie, nie jako warunek zrozumienia pytania; dodany
"Dlaczego pytamy?" — ten sam wzorzec co K1-K7):
```
### Zanim przejdziemy dalej — jedno pytanie

[info] Dokument, który wgrano, jest skierowany do **konkretnej osoby**, nie
do spółki. Ten kalkulator ocenia jeden, konkretny rodzaj ryzyka: sytuację, w
której wierzyciel spółki próbuje ściągnąć jej dług od Ciebie osobiście, jako
od członka zarządu — bo spółka nie zapłaciła (prawnicy nazywają to
odpowiedzialnością z art. 299 Kodeksu spółek handlowych).

**Czy to Twoja sytuacja: pełnisz lub pełniłeś/pełniłaś funkcję w zarządzie
spółki, a teraz ktoś próbuje ściągnąć od Ciebie osobiście dług tej spółki?**

[Tak, to moja sytuacja]   [Nie, to inna sprawa]

[expander "Dlaczego pytamy?"] Kalkulator obejmuje wyłącznie tę jedną
sytuację prawną. Jeśli sprawa dotyczy czegoś innego (np. Twojego prywatnego
zobowiązania niezwiązanego ze spółką), ocena ryzyka w tym narzędziu nie
byłaby trafna — dlatego pytamy na samym początku, zanim przejdziesz przez
cały formularz.
```
Reguła "nigdy nie używaj słowa 'użytkownik'" z CLAUDE.md zachowana (już było
OK, zostaje OK — forma bezpośrednia "Ty/Twoja").

## Zmiana 2 — Checkbox EPU (`app/app.py`, ok. linii 1066-1081)

**Dziś:** `"Dokument pochodzi z EPU / e-Sądu (sygnatura Nc-e lub Sąd
Rejonowy Lublin-Zachód w Lublinie)"` — techniczny szczegół (sygnatura Nc-e)
wprost w etykiecie głównej, zanim ktokolwiek otworzy pomoc.

**Propozycja:** `"Dokument pochodzi z e-Sądu (Elektronicznego Postępowania
Upominawczego, EPU)"` — szczegóły rozpoznawcze (sygnatura Nc-e, nazwa sądu)
ZOSTAJĄ tam, gdzie już są dobrze wyjaśnione: w istniejącym expanderze "Jak
rozpoznać dokument z EPU / e-Sądu?" (treść tego expandera bez zmian — jest
dobra, tylko obecnie trzeba go dopiero otworzyć, żeby zobaczyć wyjaśnienie
tego, co i tak już rzuca się w oczy w samej etykiecie).

## Zmiana 3 — synchronizacja pytań K1-K7 (poprawiona po uwadze użytkownika)

**Poprawka względem pierwszej wersji tego planu**: pierwotna propozycja
("zawsze synchronizuj CSV pod realny tekst z app.py") była błędna dla K3 i
K6 — zauważone przez użytkownika: realne etykiety w app.py dla tych dwóch
kroków, `"Czego teraz potrzebujesz?"` (K3) i `"Czego przede wszystkim
potrzebujesz?"` (K6), brzmią niemal identycznie ("masło maślane") mimo że
pytają o zupełnie różne rzeczy (K3 = zakres wsparcia od kancelarii, K6 = cel
klienta w sprawie) — realne ryzyko, że użytkownik pomyśli, że to duplikat
pytania, i się zgubi. CSV miało od początku lepsze, wyraźnie odróżnione
wersje tych dwóch pytań — więc dla K3/K6 kierunek synchronizacji jest
ODWRÓCONY: to `app.py` dostosowuje się do CSV, nie odwrotnie. Dla
pozostałych kroków (K1, K4, K5, K7) taki problem nie występuje (sprawdzone:
żadna z propozycji nie brzmi podobnie do żadnego INNEGO pytania w
formularzu) — tam zostaje pierwotny kierunek (CSV dogania już dobry tekst
z app.py).

| Krok | CSV `question_text` dziś | Realny tekst w `app.py` dziś | **Docelowy tekst na ekranie (dosłownie)** | Gdzie zmiana |
|---|---|---|---|---|
| K1 | Rodzaj pisma, którego dotyczy sprawa | Jakie pismo lub dokument dotyczy Twojej sprawy? | **Jakie pismo lub dokument dotyczy Twojej sprawy?** | CSV 08 + Excel (app.py bez zmian) |
| K2 | Ile czasu zostało na reakcję? | Ile czasu zostało na reakcję? | **Ile czasu zostało na reakcję?** (już zgodne) | — |
| **K3** | Jakiego wsparcia teraz potrzebujesz? | Czego teraz potrzebujesz? | **Jakiego wsparcia teraz potrzebujesz?** | **`app.py` (1 linia); CSV bez zmian** |
| K4 | Status w zarządzie w okresie sprawy | Jaki jest Twój status w zarządzie? | **Jaki jest Twój status w zarządzie?** | CSV 08 + Excel (app.py bez zmian) |
| K5 | Czy zmiana została ujawniona w KRS? | Czy zmiana w zarządzie została ujawniona w KRS? | **Czy zmiana w zarządzie została ujawniona w KRS?** | CSV 08 + Excel (app.py bez zmian) |
| **K6** | Jaki jest Twój główny cel? | Czego przede wszystkim potrzebujesz? | **Jaki jest Twój główny cel?** | **`app.py` (1 linia); CSV bez zmian** |
| K7 | Jaka jest kwota roszczenia wskazana w dokumencie? | Jaka kwota roszczenia jest wskazana w dokumencie? | **Jaka kwota roszczenia jest wskazana w dokumencie?** | CSV 08 + Excel (app.py bez zmian) |

Efekt: K3 pyta wyraźnie o **zakres wsparcia** ("Jakiego wsparcia teraz
potrzebujesz?"), K6 wyraźnie o **cel** ("Jaki jest Twój główny cel?") — dwa
odróżnialne pytania zamiast dwóch podobnie brzmiących. Dla K1/K4/K5/K7 zero
zmian zachowania appki (`question_text` nadal nigdzie nie jest odczytywany w
kodzie — to naprawa dokumentacji). Dla K3/K6 to jedyne dwie realne zmiany w
`app.py` w ramach tego punktu (proste podmiany literału w wywołaniu
`labeled_radio(...)`, linie ~1145 i ~1169).

## Poza zakresem (świadomie odłożone)

- Restrukturyzacja K1 (14 opcji, brak "Wezwanie przedsądowe (spółka)",
  wymaganie wiedzy spółka/członek-zarządu od użytkownika) — realna,
  wartościowa poprawka, ale wymaga zmian w CSV 08 (nowa opcja) + CSV 09
  (punktacja) + potencjalnie CSV 12 (scenariusze) + Excel — znacznie większy
  zakres niż "poprawka tekstu". Do osobnej rozmowy, jeśli użytkownik zechce.

## Weryfikacja

- Żywy test w przeglądarce (`streamlit run app.py`, zrzut ekranu) na
  dokumencie, który uruchamia bramkę art. 299 (np. dowolny plik z
  `_person_doc=True`) — sprawdzić nowy tekst bramki + nowy "Dlaczego
  pytamy?" renderuje się poprawnie, przyciski działają (gate nadal ustawia
  `_art299_gate` yes/no).
- Sprawdzić sekcję EPU na dokumencie z `epu_compat != "NIE"` — nowa,
  krótsza etykieta checkboxa + istniejący expander bez zmian.
- Sprawdzić Krok 4 (K3) i Krok 6 (K6) w tym samym żywym teście — upewnić się,
  że wyświetlają się odróżnialne pytania ("Jakiego wsparcia teraz
  potrzebujesz?" vs "Jaki jest Twój główny cel?"), nie dwie niemal
  identyczne frazy.
- Audyt synchronizacji CSV↔Excel (patrz CLAUDE.md) po zmianie 4 wierszy w
  CSV 08 (K1/K4/K5/K7) — zweryfikować komórka-po-komórce zgodność z arkuszem
  `4_Formularz_6_krokow`.
- `tools/regression_test.py` NIE jest wymagany — zmiana czysto tekstowa,
  zero zmian w `doc_*.py`/logice ekstrakcji/punktacji (kody K3_.../K6_...
  bez zmian, zmienia się wyłącznie etykieta/question_text).
