---
name: project-form-content-audit
description: "22.07.2026 — audyt treści pytań K1-K7 z perspektywy potencjalnego klienta (profesjonalizm/zaufanie), naprawa bramki art. 299 KSH i checkboxa EPU (jedyne miejsca bez 'Dlaczego pytamy?'/gęste żargonowo), odkrycie i naprawa martwej kolumny question_text w CSV 08, oraz ważna lekcja o dwukierunkowej synchronizacji tekstu (K3/K6 'masło maślane')."
metadata:
  node_type: memory
  type: project
  originSessionId: 6c39c185-9261-4919-b8c9-2ce13b654a86
---

## Co i dlaczego

Użytkownik poprosił o ocenę pytań formularza K1-K7 z perspektywy
potencjalnego klienta — czy brzmią fachowo/profesjonalnie i budują zaufanie
do narzędzia, czy raczej je podważają.

## Metodologia (ważne dla przyszłych podobnych audytów)

Zebrano DOSŁOWNY korpus tekstu bezpośrednio ze źródeł — `dane_wejściowe/csv/
08_4_Formularz_6_krokow.csv` (wszystkie opcje K1-K7 + `why_we_ask`) i
`app/app.py` (realne etykiety pytań, sekcja EPU, bramka art. 299, komunikat
walidacji) — zamiast opierać wnioski na pamięci/domysłach o tym, co
formularz "pewnie" pokazuje. Wnioski przedstawione użytkownikowi na czacie
PRZED jakąkolwiek zmianą kodu; użytkownik zweryfikował i skorygował
konkretną propozycję (patrz niżej) — dopiero potem wdrożenie.

## Wnioski audytu

Większość formularza (K2-K7) była już dobrze napisana: konkretna,
empatyczna, bez żargonu, z bezpieczną furtką "nie wiem" niemal wszędzie. K2
(kalkulator terminu) to wzorcowy fragment — dokładna data, cytat art. 115
KPC, jasne wliczanie weekendów/świąt. Dwa miejsca odstawały, oba na samym
POCZĄTKU ścieżki (moment najważniejszy dla pierwszego wrażenia):

1. **Bramka art. 299 KSH** — gęste, urzędnicze zdanie bez wyjaśnienia; jedyne
   miejsce w całej ścieżce BEZ "Dlaczego pytamy?" (wszystkie kroki K1-K7 taki
   expander mają — niespójne zastosowanie dobrego wzorca).
2. **Checkbox EPU** — żargon sądowy ("sygnatura Nc-e") wprost w głównej
   etykiecie, zanim ktokolwiek otworzy pomocniczy expander (który sam w
   sobie jest dobry).

Odkrycie techniczne przy okazji: kolumna `question_text` w CSV 08 jest
MARTWA (nigdzie nie odczytywana w kodzie — `grep question_text app/` = 0
wyników). Realne pytania są zahardkodowane w `labeled_radio(...)` w
`app.py` i w 6 z 7 kroków (wszystkie oprócz K2) różniły się treścią od CSV —
naruszenie własnej zasady projektu ("nigdy nie hardkoduj tekstów
sterowalnych z CSV").

Poza zakresem (świadomie odłożone, zbyt duża zmiana na "poprawkę tekstu"):
K1 ma 14 opcji wymagających od użytkownika rozróżnienia spółka/członek
zarządu — dokładnie tej wiedzy, po którą przyszedł do kalkulatora (błędne
koło), plus brak opcji "Wezwanie przedsądowe (spółka)" w ścieżce ręcznej.
Wymagałoby zmian w CSV 08 (nowa opcja) + CSV 09 (punktacja) + potencjalnie
CSV 12 (scenariusze) + Excel.

## Ważna lekcja: synchronizacja tekstu NIE jest jednokierunkowa

Pierwsza wersja planu naprawy `question_text` zakładała "zawsze
synchronizuj martwy CSV pod realny tekst z app.py" (bo app.py to
"rzeczywistość"). **Użytkownik to poprawił** — dla K3 i K6 taki kierunek
byłby błędem: realne etykiety `"Czego teraz potrzebujesz?"` (K3) i `"Czego
przede wszystkim potrzebujesz?"` (K6) brzmią niemal identycznie ("masło
maślane" — dosłowne określenie użytkownika) mimo że pytają o zupełnie różne
rzeczy (K3 = zakres wsparcia od kancelarii, K6 = cel klienta w sprawie).
CSV miało od początku lepsze, wyraźnie odróżnione wersje. **Lekcja ogólna:
przy synchronizowaniu zdublowanego/rozjechanego tekstu nie zakładaj z góry,
która wersja jest "poprawna" (np. "kod = rzeczywistość, więc kod wygrywa")
— sprawdź każdą wersję pod kątem CAŁEGO kontekstu (czy nie koliduje/nie
brzmi jak duplikat innego elementu w tym samym flow), bo krótsza/bardziej
"naturalna" wersja może być gorsza w kontekście sąsiednich pytań.** Po
korekcie: sprawdzono pozostałe 4 propozycje (K1/K4/K5/K7) pod tym samym
kątem — żadna nie koliduje z żadnym innym pytaniem w formularzu, więc tam
oryginalny kierunek (CSV dogania app.py) został.

## Wdrożenie

- `app/app.py`: bramka art. 299 przepisana (prostszy język, podstawa prawna
  jako doprecyzowanie w nawiasie nie warunek zrozumienia, dodany "Dlaczego
  pytamy?", ok. linii 962-999) + etykieta EPU skrócona (ok. linii 1066-1069,
  szczegóły rozpoznawcze zostają w istniejącym expanderze) + K3/K6 etykiety
  cofnięte do wersji z CSV (2 literały, linie ~1145/~1169).
- `dane_wejściowe/csv/08_4_Formularz_6_krokow.csv` + arkusz Excela
  `4_Formularz_6_krokow`: `question_text` zsynchronizowany z `app.py` dla
  K1/K4/K5/K7 (26 komórek w Excelu, zmienione skryptem openpyxl z asercją —
  każda komórka sprawdzona względem oczekiwanej starej wartości przed
  nadpisaniem, zero nieoczekiwanych wierszy). K3 CSV bez zmian (już miało
  docelowy tekst).
- Zweryfikowane żywym testem w przeglądarce: K1 wybór opcji, nowa etykieta
  EPU, Krok 4 (K3) i Krok 6 (K6) pokazujące teraz odróżnialne pytania.
  Bramka art. 299 NIE zweryfikowana żywym renderem — wymaga wgranego
  dokumentu z pozwanym-osobą-fizyczną; `mcp__claude-in-chrome__file_upload`
  odrzucił upload pliku spoza katalogów udostępnionych tej sesji (ten sam
  rodzaj ograniczenia co wcześniej znany brak działania uploadu w
  agent-browser, patrz [[project_visual_redesign]]) — zweryfikowana
  wyłącznie przeglądem kodu (składnia, zbalansowane `**`, logika gate'u bez
  zmian).
