# Plan: warianty znaku B3 (plakietka-monogram) dla kalkulatora ryzyka

## Context

W poprzednim kroku tej samej sesji przygotowano i opublikowano galerię 6
koncepcji znaku graficznego dla kalkulatora ryzyka (Artifact „Propozycje
znaku graficznego"). Użytkownik wybrał kierunek **B3 — plakietka-monogram**
(sześciokątna plakietka z literą „K"), ale zgłosił trafną uwagę: pierwsza
wersja budowała literę K z trzech kresek nawiązujących do idei „3 rosnące
słupki = skala ryzyka" (ten sam motyw co w koncepcjach A1/A2) — ale ta
narracja jest niewidoczna dla klienta końcowego. Dla niego to po prostu
biała litera K na plakietce, bez żadnego dodatkowego znaczenia. Wniosek:
**motyw słupków/skali w literze K nie ma sensu** — sam kształt litery i
plakietki musi nieść jakość wizualną bez ukrytej narracji.

Cel tego kroku: zaproponować **kilka wariantów samego B3** — różne style
litery K i/lub kształty plakietki — oceniane wyłącznie jako czysty
monogram, bez próby zaszycia w nim skali ryzyka. Nadal etap propozycji, bez
zmian w kodzie repo.

## Ustalone fakty (z poprzedniego kroku tej sesji — nie trzeba ponownej
eksploracji, `app/branding.py` już przeczytany w pełni)

- Token system: `navy #1a3a5c`, `navy_light #2c5580`, `ink #0f1b2d`,
  `paper #ffffff`, `mist #f0f4f8`/`mist_border #dbe4ee`; font display =
  Georgia/Iowan Old Style (serif) — dostępny jako oś do rozważenia w samym
  kroju litery K (wariant serifowy nawiązujący do fontu nagłówków appki).
- Ograniczenia bez zmian: bez emoji, forma odrębna od logo kancelarii,
  geometrycznie prosta (kontur + proste kształty), żeby dała się odtworzyć w
  3 technikach renderowania (inline SVG w appce, rastrowa favicona PIL,
  natywny rysunek reportlab w PDF — `Polygon`/`Rect`, bez gradientów/filtrów).
- Feedback z tej sesji (zapamiętać na przyszłość): **nie zaszywać w znaku
  narracji niewidocznej dla klienta** — jeśli wizualny motyw (np. „3 kreski =
  4-stopniowa skala") wymaga wyjaśnienia, żeby ktokolwiek go odczytał, to nie
  działa jako znak graficzny; oceniać kształt czysto na tym, co faktycznie
  widać.

## Warianty do zaproponowania (2 osie: krój litery × kształt plakietki)

1. **K geometryczne (monoline)** — czysta, jednogrubościowa kreska (trzon +
   dwie przekątne, zaokrąglone zakończenia) w sześciokątnej plakietce — ta
   sama konstrukcja co poprzednio, ale prezentowana i oceniana wyłącznie jako
   „czysta litera K", bez odwołania do słupków.
2. **K blokowe/solidne** — grubszy, wypełniony, bardziej „stemplowy" kształt
   litery (jak w krojach wyświetlaczowych/display) zamiast cienkich kresek —
   pewniejszy, lepiej czytelny w skali favicony 16-24px.
3. **K negatywowe (wycięte z plakietki)** — plakietka wypełniona w całości
   kolorem marki, litera K jako **ujemne wycięcie** (widoczne tło przez
   otwór) — inna relacja figura/tło, czyta się jak pieczęć/stempel zamiast
   naklejonej litery.
4. **K w kole** — ten sam krój litery co (1), ale plakietka okrągła zamiast
   sześciokątnej — łagodniejsza, bardziej przystępna sylwetka.
5. **K w zaokrąglonym kwadracie** — plakietka typu „ikona aplikacji"
   (zaokrąglony kwadrat/squircle) — najbardziej współczesny, „tech" wygląd.
6. **K serifowe** — litera K rysowana z delikatnymi szeryfowymi
   zakończeniami, nawiązującymi do kroju Georgia używanego już w nagłówkach
   appki — spina typografię marki ze znakiem, bardziej „prawniczy" charakter
   niż geometryczne warianty.

6 wariantów pokrywa dwie niezależne osie (krój litery: monoline / blokowe /
negatywowe / serifowe; kształt plakietki: sześciokąt / koło / zaokrąglony
kwadrat) bez nadmiaru.

## Deliverable

Nowy, samodzielny plik HTML (Artifact) — **nowa strona**, nie aktualizacja
poprzedniej galerii (inny zakres: to przegląd wariantów jednego wybranego
kierunku, nie porównanie 6 różnych koncepcji). Struktura analogiczna do
poprzedniej galerii dla spójności, ale prostsza:
- Krótki nagłówek: przypomnienie wyboru B3 i przyczyny wariantowania (bez
  narracji słupków, ocena czysto wizualna).
- 6 kart, każda: nazwa wariantu + jednozdaniowy opis różnicy, znak w 3
  kontekstach (duży podgląd na papierze, plakietka nagłówka na granacie,
  favicon 24px) — te same klasy/tokeny CSS co w poprzedniej galerii.
- Bez sekcji „warianty kolorów ryzyka" (świadomie pominięta — to właśnie ten
  motyw użytkownik odrzucił jako nieczytelny).
- Ten sam system tokenów (`branding.py`) i technika (inline `<symbol>`+`<use>`
  z CSS custom properties do przebarwiania) co poprzedni artifact.

Brak zmian w repozytorium — czysta prezentacja do wyboru.

## Kroki wykonania

1. Zbudować SVG dla 6 wariantów litery K (viewBox 0 0 32 32, proste
   kontury/kreski — bez krzywych wymagających dokładnej aproksymacji Beziera
   w PIL/reportlab tam, gdzie da się użyć linii prostych/łuków kołowych).
2. Zbudować galerię HTML (reużyć strukturę CSS z poprzedniego artifactu —
   `--fill-shield`/`--fill-bars` jako custom properties per instancja).
3. Opublikować jako nowy Artifact (osobny URL, favicon 🛡️ dla spójności z
   poprzednim).
4. Podsumowanie na czacie: 6 wariantów nazwanych + link + pytanie, który
   finalnie wdrożyć do `branding.py`/`generate_favicon.py`/`report_builder.py`.

## Verification

- Otworzyć Artifact, sprawdzić: każdy wariant litery K czytelny i
  jednoznaczny jako „K" w każdej z 3 skal (zwłaszcza 24px favicon — to był
  słaby punkt poprzedniej wersji, priorytet tej iteracji), kontrast na
  granacie/papierze poprawny, tryb jasny/ciemny strony działa.
- Zero zmian w kodzie aplikacji — weryfikacja czysto wizualna, bez
  `tools/regression_test.py`.
