**KRS Guard - Kalkulator Ryzyka**

**Specyfikacja funkcjonalna, logiczna i tekstowa dla zbudowania kalkulatora ryzyka**

Wersja dokumentu: 2.0 | Charakter dokumentu: instrukcja projektowa | Źródło reguł: KRS_Guard_specyfikacja_AI.xlsx

# 1. Cel dokumentu

Celem dokumentu jest opisanie zasad, kryteriów, punktacji, reguł tekstowych i wymagań jakościowych, na podstawie których można zbudować kalkulator ryzyka dla spraw związanych z odpowiedzialnością członków zarządu, osób zarządzających oraz ryzykiem wynikającym z dokumentów sądowych, urzędowych i publicznoprawnych.

Dokument nie narzuca jednej technologii ani jednego sposobu implementacji. Ma być instrukcją dla zespołu technicznego, programisty albo modelu AI, który ma opracować własną wersję kalkulatora zgodną z zasadami i danymi znajdującymi się w pliku Excel KRS_Guard_specyfikacja_AI.xlsx.

Najważniejsza zasada: Excel jest źródłem reguł, kodów, punktacji, tekstów i testów. Dokument Word wyjaśnia sens tych danych, ich wzajemne relacje oraz wymagania dotyczące końcowego działania kalkulatora.

Specyfikacja nie jest instrukcją kopiowania żadnej wcześniejszej implementacji. Jej celem jest zbudowanie własnego kalkulatora na podstawie wypracowanych reguł.

# 2. Cel biznesowy i praktyczny kalkulatora

Kalkulator ma służyć jako narzędzie wstępnej kwalifikacji spraw, w których klient otrzymał dokument mogący mieć znaczenie dla odpowiedzialności członka zarządu albo dla dalszego ryzyka spółki i osób zarządzających. Narzędzie ma pomóc klientowi zrozumieć, czy sprawa wymaga szybkiej reakcji i czy zasadne jest przekazanie dokumentów do Audytu 48h.

- wstępnie rozpoznać typ dokumentu i jego adresata;

- ustalić, czy dokument dotyczy członka zarządu, spółki, organu publicznego czy dokumentu nieustalonego;

- sprawdzić, czy dokument może pochodzić z EPU / e-Sądu;

- ustalić czas na reakcję i podkreślić, że chodzi o dni kalendarzowe;

- uwzględnić kwotę roszczenia jako element ciężaru sprawy;

- wskazać główne niepewności, np. brak dokumentów, nieznany status KRS, niepewny typ dokumentu;

- wygenerować krótki, zrozumiały, klientocentryczny wynik;

- zachęcić do Audytu 48h bez sztucznej presji sprzedażowej.

# 3. Użytkownik docelowy i styl komunikacji

Użytkownikiem kalkulatora jest najczęściej laik, który nie rozróżnia pozwu, nakazu zapłaty, wezwania sądowego, pisma z ZUS, dokumentu z EPU ani skutków wpisu w KRS. Komunikaty muszą być proste, konkretne i wolne od żargonu technicznego.

- Nie używać w wyniku klienta słowa "użytkownik". Stosować formy: "W formularzu wskazano...", "Zaznaczono...", "Na tym etapie...".

- Nie pokazywać kodów technicznych: K1-K7, RISK_..., HRxx, scenario_id, risk_level_code.

- Nie używać w wyniku klienta określeń: scenariusz bazowy, moduł, fallback, dynamiczne dodawanie, reguła techniczna.

- Wyjaśniać, dlaczego sprawa jest pilna albo ma wysokie ryzyko.

- Nie straszyć klienta, ale jasno wskazywać konsekwencje braku reakcji.

- Kończyć wyniki krótkim wezwaniem do działania, czyli CTA - call to action, po polsku: wezwaniem do kolejnego kroku, np. Audytu 48h.

# 4. Pakiet wejściowy dla modelu AI albo programisty

Do przygotowania kalkulatora należy przekazać co najmniej:

- niniejszą specyfikację funkcjonalną, logiczną i tekstową;

- plik Excel KRS_Guard_specyfikacja_AI.xlsx jako źródło danych sterujących;

- wymagania techniczne wybranej platformy, jeżeli kalkulator ma działać w konkretnym środowisku, np. Streamlit, aplikacja webowa, formularz www albo backend API.

Kod kalkulatora powinien czytać możliwie dużo logiki z Excela: pytania, kody odpowiedzi, punktację, reguły, moduły tekstowe i testy. Nie należy twardo zaszywać w kodzie tekstów i punktacji, jeżeli mogą być utrzymywane w Excelu.

# 5. Rola pliku Excel KRS_Guard_specyfikacja_AI.xlsx

Excel jest głównym źródłem danych i zasad działania kalkulatora. Specyfikacja opisuje, jak te dane interpretować. Dla potrzeb budowy kalkulatora należy zachować arkusze kluczowe dla logiki, reguł kontekstowych, punktacji, modułów tekstowych i testów. Arkusze historyczne, archiwalne i notatki robocze mogą zostać pominięte w wersji przekazywanej innemu modelowi AI, o ile nie zawierają aktywnych reguł.

| **Grupa arkuszy** | **Przykładowe arkusze** | **Rola** |
| --- | --- | --- |
| Słownik i typy dokumentów | 1_Slownik_pojec_KRS_Guard; 3_Typy_dokumentow | Definicje pojęć, kodów i typów dokumentów. |
| Wybór dokumentu głównego | 2_Reguly_wyboru_dok_glownego; 2A; 2B; 2C; 2D | Punktacja i hierarchia wyboru dokumentu wymagającego najpilniejszej reakcji. |
| Formularz i punktacja | 4_Formularz_6_krokow; 5_Punktacja_formularza; 5A; 5B | Pytania, odpowiedzi, kody, C/P/H/W, interpretacja wyniku i twarde reguły. |
| Scenariusze i moduły | 6_Biblioteka_scenariuszy; 6A_Moduly_K3_K6; Blok_EPU | Scenariusze bazowe oraz teksty doprecyzowujące wynik. |
| Reguły kontekstowe | 6D-6U oraz arkusze EPU, KRS, kwoty, spółki, członka zarządu, ZUS/urzędu | Reguły modyfikujące tekst i priorytety zależnie od sytuacji. |
| Instrukcje i kontrola | 7_Instrukcja_dzialania_AI; 9_Instrukcja_dla_AI; 10_Testy_kontrolne; 14_Kontrola_jakosci | Instrukcje dla implementacji, testy i wymagania regresyjne. |

# 6. Ogólny przebieg działania kalkulatora

1. Klient wgrywa dokumenty albo wypełnia formularz ręcznie.

2. Kalkulator identyfikuje dokument główny albo pozwala klientowi potwierdzić wybór.

3. Kalkulator ocenia zgodność EPU / e-Sądu z typem dokumentu.

4. Klient wskazuje lub potwierdza kwotę roszczenia.

5. Klient oblicza czas na reakcję albo wybiera przedział ręcznie.

6. Klient odpowiada na pytania K3-K6.

7. Kalkulator pobiera punkty C, P, H, W z Excela.

8. Kalkulator stosuje twarde reguły bezpieczeństwa.

9. Kalkulator dobiera scenariusz bazowy oraz właściwe reguły kontekstowe i moduły tekstowe.

10. Kalkulator generuje krótką ocenę ryzyka prawniczego dla klienta.

11. Panel testowy pokazuje informacje techniczne tylko osobie testującej lub administratorowi.

# 7. Reguły wyboru dokumentu głównego

Wybór dokumentu głównego jest jednym z kluczowych elementów kalkulatora. Dokument główny to dokument, który wymaga najpilniejszej uwagi i najmocniej wpływa na ryzyko klienta. Nie należy wybierać dokumentu głównego wyłącznie według daty dokumentu, kolejności przesłania plików ani nazwy pliku.

## 7.1. Relacja hierarchii oceny do punktacji

Arkusz 2_Reguly_wyboru_dok_glownego zawiera punktowy mechanizm wyboru dokumentu głównego. Zapis o kolejności oceny należy traktować jako hierarchię merytoryczną, a punktację jako techniczne odwzorowanie tej hierarchii.

| **Kolejność oceny** | **Znaczenie** | **Wniosek dla punktacji** |
| --- | --- | --- |
| 1. Czy dokument dotyczy członka zarządu? | Bezpośrednie ryzyko osobiste jest najwyżej ważone. | Wysoka premia punktowa. |
| 2. Czy dokument uruchamia termin na reakcję? | Termin może decydować o utracie możliwości działania. | Wysoka premia punktowa. |
| 3. Czy dokument dotyczy odpowiedzialności z art. 299 KSH lub analogicznej odpowiedzialności zarządu? | Dokument może mieć znaczenie dla odpowiedzialności majątkowej. | Dodatkowa premia punktowa. |
| 4. Czy dokument pochodzi z sądu, komornika albo organu? | Źródło dokumentu wpływa na wagę i tryb reakcji. | Dodatkowa premia punktowa. |
| 5. Czy dokument jest aktualny i ma bieżący termin? | Dokument aktualny ma wyższy priorytet niż archiwalny. | Premia za aktualność. |
| 6. Jaka jest data dokumentu? | Data jest kryterium pomocniczym, szczególnie przy remisie. | Stosować na końcu. |

## 7.2. Statusy dokumentów po analizie

Po analizie plików każdy dokument powinien otrzymać status. Dokument główny steruje oceną ryzyka. Pozostałe dokumenty powinny być oznaczone jako pomocnicze, terminowe, dowodowe, nieczytelne albo nieistotne dla bieżącej reakcji, zgodnie z regułami w Excelu.

# 8. Formularz K1-K7

Formularz powinien opierać się na kodach i etykietach z Excela. Kody nie są widoczne dla klienta.

| **Kod** | **Zakres** | **Cel** |
| --- | --- | --- |
| K1 | Dokument wymagający najpilniejszej uwagi | Określa ciężar dokumentu i jego charakter. |
| K2 | Czas na reakcję | Określa presję czasu. |
| K3 | Zakres potrzebnego wsparcia | Określa poziom kompletności danych i gotowość do Audytu 48h. |
| K4 | Status w zarządzie | Określa znaczenie okresu pełnienia funkcji, rezygnacji albo odwołania. |
| K5 | Aktualność wpisu w KRS | Określa niepewność co do danych rejestrowych. |
| K6 | Główny cel klienta | Określa kierunek reakcji: obrona, czas, pismo, plan albo uporządkowanie sytuacji. |
| K7 | Kwota roszczenia | Określa wartość roszczenia i ciężar finansowy sprawy. |

# 9. Punktacja C + P + H + W

Wynik punktowy powinien być liczony jako S = C + P + H + W. Poszczególne wartości należy pobierać z arkusza 5_Punktacja_formularza. Nie należy pomijać W, ponieważ kwota roszczenia wpływa na ciężar gatunkowy sprawy.

| **Symbol** | **Znaczenie** | **Źródło** |
| --- | --- | --- |
| C | Ciężar dokumentu / charakter sprawy | Głównie K1. |
| P | Presja czasu | Głównie K2 i reguły terminu. |
| H | Niepewność, braki danych, potrzeba ostrożności | K3, K4, K5, K6, dokument nieustalony, brak kwoty. |
| W | Wartość roszczenia | K7 - kwota roszczenia. |

| **Suma punktów** | **Kod techniczny** | **Etykieta dla klienta** |
| --- | --- | --- |
| 0-3 | RISK_LOW | Niższe ryzyko / prewencja |
| 4-5 | RISK_MEDIUM | Średnie ryzyko / braki danych |
| 6-7 | RISK_HIGH | Wysokie ryzyko |
| 8 i więcej | RISK_URGENT | Sprawa pilna |

Kody techniczne ryzyka nie mogą być widoczne dla klienta. Klient widzi wyłącznie etykietę użytkową.

# 10. Twarde reguły bezpieczeństwa

Twarde reguły bezpieczeństwa mogą podnieść minimalny poziom ryzyka niezależnie od sumy punktów. Reguły te powinny być przechowywane w Excelu i stosowane po obliczeniu punktów, ale przed wygenerowaniem tekstu końcowego.

- dokument bezpośrednio przeciwko członkowi zarządu + 0-3 dni = co najmniej sprawa pilna;

- dokument bezpośrednio przeciwko członkowi zarządu + 4-7 dni = co najmniej wysokie ryzyko albo sprawa pilna zgodnie z punktacją;

- pismo ZUS / urzędu dotyczące odpowiedzialności członka zarządu + krótki termin = podwyższona pilność;

- rezygnacja / odwołanie + KRS nieznany albo nieaktualny = dodatkowe ostrzeżenie diagnostyczne;

- dokument nieustalony + krótki termin = priorytet identyfikacji dokumentu i terminu.

Komunikaty dla klienta w twardych regułach powinny być ludzkie, nie tylko techniczne. Dopuszczalne są sformułowania: "nie warto odkładać sprawy", "warto działać bez zwłoki", "najważniejsze jest szybkie potwierdzenie terminu i przygotowanie właściwej reakcji".

# 11. Scenariusz bazowy i reguły kontekstowe

Model powinien rozdzielać scenariusz bazowy od modułów i reguł kontekstowych. Scenariusz bazowy nie jest pełnym opisem sytuacji klienta. Jest techniczną ramą opartą głównie na dokumencie, EPU, czasie i poziomie ryzyka.

W dokumentacji należy używać określenia "reguły kontekstowe", a nie niejasnego określenia "reguły specjalne".

| **Element** | **Rola** |
| --- | --- |
| Scenariusz bazowy | Ogólna rama sprawy: dokument, EPU, czas, poziom ryzyka. |
| Moduły K3-K7 | Doprecyzowanie wyniku według odpowiedzi klienta. |
| Reguły kontekstowe | Reguły EPU, dni kalendarzowych, KRS, spółki, członka zarządu, ZUS/urzędu, dokumentu nieustalonego i kwoty. |

# 12. Reguły EPU / e-Sądu

EPU nie jest zwykłym checkboxem zawsze dostępnym. Musi być zależne od typu dokumentu.

| **Grupa dokumentów** | **Przykłady** | **Zachowanie EPU** |
| --- | --- | --- |
| Zgodne z EPU | Nakaz zapłaty przeciwko członkowi zarządu; nakaz zapłaty przeciwko spółce | Checkbox aktywny. |
| Ostrożne | Pozew przeciwko członkowi zarządu; pozew przeciwko spółce | Checkbox aktywny, ale z ostrzeżeniem i koniecznością sprawdzenia pouczenia. |
| Niezgodne z EPU | Wezwania; pisma ZUS / urzędu; dokument nieustalony | Checkbox wyłączony. |

Pod checkboxem EPU należy pokazać rozwijaną pomoc: "Jak rozpoznać dokument z EPU / e-Sądu?". Wyróżniki należy oddzielać średnikami, aby klient nie potraktował każdego fragmentu jako samodzielnego kryterium.

Przykład treści pomocy: Zaznacz tę opcję, jeżeli na dokumencie widzisz oznaczenia takie jak: e-Sąd; EPU; Elektroniczne Postępowanie Upominawcze; sygnaturę z oznaczeniem "Nc-e"; Sąd Rejonowy Lublin-Zachód w Lublinie - VI Wydział Cywilny; albo informację, że nakaz zapłaty został wydany w elektronicznym postępowaniu upominawczym. Samo oznaczenie "VI Wydział Cywilny" nie musi oznaczać e-Sądu. Dokument z EPU / e-Sądu to nie każdy dokument otrzymany elektronicznie.

# 13. Reguły dla typów dokumentów

## 13.1. Dokument bezpośrednio przeciwko członkowi zarządu

Dotyczy pozwu, nakazu, wezwania oraz pisma ZUS / urzędu skierowanego do członka zarządu. Tekst powinien wyjaśniać, że ryzyko jest osobiste, a brak właściwej reakcji może mieć znaczenie dla odpowiedzialności majątkowej.

## 13.2. Dokument przeciwko spółce

Przy dokumentach przeciwko spółce należy wyjaśnić ryzyko pośrednie. Dokument nie jest jeszcze skierowany bezpośrednio przeciwko członkowi zarządu, ale sposób reakcji spółki może wpływać na dalszy rozwój sprawy i późniejszą odpowiedzialność osób zarządzających.

## 13.3. Nakaz a pozew

Nakaz zapłaty ma inny ciężar gatunkowy niż pozew. Przy nakazie trzeba akcentować ryzyko uprawomocnienia się nakazu i konieczność sprzeciwu. Przy pozwie trzeba mówić o sporze, przygotowaniu stanowiska i odpowiedzi na pozew.

## 13.4. Pismo ZUS / urzędu

Pismo ZUS / urzędu dotyczące odpowiedzialności członka zarządu nie jest pismem z sądu cywilnego. Nie wolno generować sprzeciwu od nakazu ani odpowiedzi na pozew. Tekst powinien mówić o złożeniu wyjaśnień, przedstawieniu dowodów, okresie zaległości, okresie pełnienia funkcji i przesłankach wyłączających odpowiedzialność.

## 13.5. Dokument nieustalony

Opcja "Inny dokument / nie mam pewności" nie jest typem dokumentu. To sygnał, że klient nie potrafi zakwalifikować pisma. Priorytetem jest identyfikacja dokumentu, a dopiero potem ocena terminu, kwoty i rodzaju reakcji.

# 14. Reguły terminu i dni kalendarzowych

| **Termin** | **Język oceny** | **Znaczenie** |
| --- | --- | --- |
| 0-3 dni | bardzo ograniczony czas | Mocny komunikat o pilności. |
| 4-5 dni | czas ograniczony | Mocny, ale spokojny komunikat. |
| 6-7 dni | krótki czas | Pilnie, ale bez przesady. |
| 8-14 dni | jest czas na uporządkowanie | Nie zwlekać, ale nie pisać o bardzo krótkim czasie. |
| powyżej 14 dni | więcej czasu | Uporządkować sprawę i pilnować terminu. |
| termin nieznany | brak danych | Najpierw ustalić datę doręczenia i pouczenie. |

Jeżeli dostępna jest konkretna liczba dni, wynik musi pokazywać konkretną liczbę, np. 6 dni kalendarzowych, a nie przedział 4-7 dni.

W ocenie należy zawsze dodać zdanie: Do tego terminu wliczają się także soboty, niedziele i dni świąteczne.

# 15. Reguły KRS i statusu w zarządzie

| **Odpowiedź** | **Reguła tekstowa** |
| --- | --- |
| KRS aktualny | Nie pisać, że trzeba ustalić aktualny wpis w KRS jako pierwszy krok. Można wskazać potwierdzenie odpisu i daty wpisu. |
| KRS nieaktualny | Wskazać potrzebę porównania dokumentów korporacyjnych z wpisem w KRS. |
| KRS nie wiem | Wskazać potrzebę sprawdzenia aktualnego odpisu KRS. |
| Rezygnacja / odwołanie | Sprawdzić dokument rezygnacji albo odwołania oraz datę skuteczności. |
| Nadal pełnię funkcję | Znaczenie ma bieżąca reakcja i zakres możliwej odpowiedzialności. |

# 16. Kwota roszczenia

Kwota roszczenia wpływa na ciężar gatunkowy sprawy i musi być interpretowana kontekstowo. Przy dokumencie przeciwko członkowi zarządu wysoka kwota oznacza ryzyko osobiste. Przy dokumencie przeciwko spółce wysoka kwota oznacza ryzyko dla spółki oraz pośrednio dla osób zarządzających. Przy dokumencie nieustalonym brak kwoty ogranicza pewność oceny.

| **Przedział kwoty** | **Znaczenie** |
| --- | --- |
| Nie wiem / nie widzę kwoty | Ogranicza pewność oceny. |
| Do 10 000 zł | Niski ciężar finansowy, ale termin i typ dokumentu nadal są ważne. |
| 10 001-50 000 zł | Kwota umiarkowana. |
| 50 001-150 000 zł | Kwota zwiększa ciężar sprawy. |
| 150 001-500 000 zł | Wysoka kwota. |
| Powyżej 500 000 zł | Bardzo wysoka kwota. |

# 17. Budowa tekstu końcowego dla klienta

Końcowa ocena powinna być krótka, konkretna i uporządkowana. Zalecana struktura:

1. Etykieta poziomu ryzyka.

2. Pierwszy akapit: co wybrano i ile dni pozostało.

3. Wyjaśnienie, dlaczego ryzyko ma taki poziom.

4. Kontekst dokumentu: członek zarządu, spółka, ZUS/urząd, EPU albo dokument nieustalony.

5. Najważniejsze niepewności, np. KRS, brak dokumentów, brak kwoty.

6. Krótki akapit: co teraz jest najważniejsze.

7. CTA / wezwanie do działania do Audytu 48h.

8. Zastrzeżenie prawne.

Nie należy wypisywać długich list audytowych. Nie należy doklejać technicznych notatek z Excela. Teksty z kolumn pomocniczych, takich jak uwagi dla AI, mogą być wykorzystane tylko po redakcji na język klienta.

# 18. Panel testowy i dane techniczne

Kalkulator powinien mieć tryb testowy albo diagnostyczny dla osoby rozwijającej narzędzie. W tym trybie można pokazać kody K1-K7, punkty C/P/H/W, scenariusz bazowy, twarde reguły, status EPU, użyte moduły tekstowe, ostrzeżenia techniczne i dokument główny. Tych informacji nie wolno pokazywać klientowi.

# 19. Wymagania regresyjne

Każda zmiana musi być sprawdzona nie tylko na aktualnym przykładzie, ale na wszystkich wariantach, których może dotyczyć. Poniższa tabela to minimalna lista testów, a nie lista zamknięta. Przy każdej zmianie trzeba ustalić zakres wpływu i sprawdzić odpowiednie kombinacje typu dokumentu, adresata, EPU, terminu, KRS, statusu w zarządzie, kwoty i celu.

| **Test minimalny** | **Oczekiwany kierunek wyniku** |
| --- | --- |
| EPU + nakaz członek zarządu + 0-7 dni | Priorytet: sprzeciw w EPU, termin, prawidłowe oznaczenie nakazu. |
| EPU + pozew | Ostrożny komunikat: ustalić tryb i pouczenie, nie traktować jak zwykłego pozwu. |
| Wezwanie + EPU | EPU wyłączone, ostrzeżenie o możliwej pomyłce. |
| Pismo ZUS / urząd | Ścieżka publicznoprawna, bez pozwu, nakazu i EPU. |
| Nakaz spółka + wysoka kwota | Ryzyko dla spółki i pośrednio dla zarządu. |
| Nakaz członek zarządu + wysoka kwota | Ryzyko osobiste, nie pisać o konsekwencjach dla spółki jako głównych. |
| Inny dokument / nie wiem | Najpierw identyfikacja dokumentu. |
| KRS aktualny | Nie generować niepotrzebnego wezwania do ustalenia aktualnego wpisu jako priorytetu. |

# 20. Pseudokod działania

Pseudokod nie jest gotowym kodem aplikacji. To uproszczony opis kolejności działań, który można zaimplementować w dowolnej technologii.

state = collect_form_state()

document_main = choose_or_confirm_main_document(state.documents)

epu_status = check_epu_compatibility(document_main.type)

if epu_status == "NIE": state.epu = False

if state.user_provided_dates:

state.days_left_exact = calculate_days_left(delivery_date, deadline_days, today)

state.k2 = bucket_from_days_left(state.days_left_exact)

else:

state.k2 = selected_deadline_bucket

points = get_points_for_codes([k1, k2, k3, k4, k5, k6, k7])

score = points.C + points.P + points.H + points.W

risk = interpret_risk(score)

risk = apply_hard_rules(state, risk)

base_scenario = find_base_scenario(state, risk)

modules = collect_contextual_modules(state)

assessment = build_client_assessment(state, base_scenario, modules, risk)

assessment = sanitize_user_text(assessment)

# 21. Sanitizacja tekstu klienta

Przed pokazaniem wyniku klientowi tekst musi przejść kontrolę sanitizacji. Należy usunąć albo zablokować techniczne treści: RISK_..., K1-K7, HRxx, scenario_id, risk_level_code, scenariusz bazowy, moduł, dynamicznie, fallback, reguła techniczna, instrukcja dla AI.

# 22. Etap z wgrywaniem dokumentów

Kolejny etap rozwoju kalkulatora powinien obejmować analizę wgrywanych plików. Jeżeli OCR albo klasyfikacja nie mają wysokiej pewności, klient musi potwierdzić dane ręcznie.

- obsługa PDF, DOCX, JPG, PNG;

- OCR dla skanów i zdjęć;

- klasyfikacja typu dokumentu;

- wykrywanie EPU, sygnatury Nc-e i oznaczeń e-Sądu;

- wykrywanie daty doręczenia, terminu z pouczenia i kwoty;

- wykrywanie adresata: członek zarządu, spółka, organ publiczny;

- wybór dokumentu głównego według reguł punktowych z Excela;

- status pozostałych dokumentów jako pomocniczych.

# 23. Definicja gotowości kalkulatora

- wynik klienta nie zawiera technicznych kodów ani żargonu;

- kalkulator rozróżnia członka zarządu i spółkę;

- kalkulator rozróżnia nakaz, pozew, wezwanie, pismo ZUS / urzędu i dokument nieustalony;

- EPU działa tylko przy logicznie zgodnych dokumentach;

- terminy są liczone i komunikowane jako dni kalendarzowe;

- kwota roszczenia wpływa na punktację i tekst;

- wynik jest krótki, zrozumiały i zawiera uzasadnienie poziomu ryzyka;

- CTA do Audytu 48h nie tworzy sztucznej presji;

- zmiany przechodzą testy regresyjne.

# 24. Słownik pojęć

| **Pojęcie** | **Znaczenie** |
| --- | --- |
| Audyt 48h | Pogłębiona analiza dokumentów, terminów i możliwych kierunków reakcji. |
| CTA | Call to action, czyli wezwanie do działania, np. przejścia do Audytu 48h. |
| EPU / e-Sąd | Elektroniczne postępowanie upominawcze. Nie każdy dokument elektroniczny jest dokumentem z EPU. |
| Scenariusz bazowy | Techniczna rama sprawy oparta na dokumencie, EPU, czasie i poziomie ryzyka. Nie jest widoczna dla klienta. |
| Moduł tekstowy | Krótki fragment tekstu przypisany do odpowiedzi klienta albo reguły kontekstowej. |
| K1-K7 | Techniczne kody odpowiedzi formularza. Nie wolno ich pokazywać klientowi. |
| C, P, H, W | Kategorie punktacji: ciężar dokumentu, presja czasu, niepewność, wartość roszczenia. |
