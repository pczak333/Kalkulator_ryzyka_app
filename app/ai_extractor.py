# -*- coding: utf-8 -*-
"""Ekstrakcja pól dokumentu przez Claude Haiku — główna ścieżka (nie regex).

Polska legalna korespondencja ma dużą liczbę gramatycznych odmian tej samej
formuły ("nakazuje pozwanemu", "strona pozwana", "stronie pozwanej", "stronę
powodową"...) — regex w doc_extractor.py musi znać każdą z góry. AI rozumie
tekst niezależnie od konkretnej odmiany, więc jest odporniejsza na nowe,
nieprzewidziane sformułowania. Koszt jest pomijalny (Haiku, ~$0,001-0,002 na
dokument), więc jest to teraz PIERWSZY wybór, a regex w doc_extractor.py
pozostaje tanim fallbackiem gdy brak klucza API lub AI zawiedzie.
"""
from __future__ import annotations
import json
import re

_MODEL = "claude-haiku-4-5-20251001"
_MAX_CHARS = 4000

_PROMPT_TEMPLATE = (
    "Masz przed sobą tekst polskiego dokumentu (po OCR) — zwykle jest to pismo "
    "sądowe lub prawne, ale może to być też dokument zupełnie innego rodzaju.\n"
    "Wyciągnij następujące informacje w formacie JSON (null jeśli nie znaleziono):\n"
    "{{\n"
    '  "czy_pismo_prawne": true lub false,\n'
    '  "rodzaj_pisma": "pozew" lub "nakaz_zaplaty" lub "wezwanie_do_zaplaty" '
    'lub "pismo_w_toku_postepowania" lub "pismo_komornicze" lub '
    '"decyzja_urzedowa" lub "inne" lub null,\n'
    '  "sygnatura": "sygnatura akt np. V GNc 2034/22/S",\n'
    '  "sad_organ": "pełna nazwa sądu lub organu",\n'
    '  "powod": "imię i nazwisko lub nazwa powoda/wierzyciela",\n'
    '  "pozwany": "imię i nazwisko lub nazwa pozwanego/dłużnika/wzywanego",\n'
    '  "termin_dni": liczba_lub_null,\n'
    '  "kwota_zl": liczba_lub_null,\n'
    '  "adresat": "czlonek_zarzadu" lub "spolka" lub "organ" lub null,\n'
    '  "epu": true lub false,\n'
    '  "opis_dokumentu": "krótki, przyjazny opis (3-8 słów) czym dokument '
    'faktycznie jest"\n'
    "}}\n\n"
    'Zasady dla pola "opis_dokumentu": wypełnij ZAWSZE, niezależnie od '
    "wartości innych pól. Krótki (3-8 słów), konkretny, po polsku, w języku "
    "zrozumiałym dla klienta bez wykształcenia prawniczego — nazwij CO to "
    "jest, nie oceniaj czy jest ważne. Przykłady dobrego opisu: \"faktura za "
    "usługi hostingowe\", \"bilet kolejowy\", \"paragon ze sklepu "
    "spożywczego\", \"prywatna korespondencja\", \"zeznanie podatkowe "
    "PIT-36\", \"potwierdzenie przelewu bankowego\", \"pozew o zapłatę\", "
    "\"nakaz zapłaty w postępowaniu upominawczym\", \"wezwanie do zapłaty od "
    "komornika\". Nie pisz \"dokument prawny\"/\"dokument nieprawny\" — "
    "zawsze podaj konkretną nazwę rodzaju dokumentu.\n\n"
    'Zasady dla pola "kwota_zl": gdy dokument rozbija roszczenie na należność '
    "GŁÓWNĄ i odsetki/koszty, zwróć NALEŻNOŚĆ GŁÓWNĄ (bez odsetek i kosztów). "
    "Kwotę łączną zwróć tylko wtedy, gdy dokument nie podaje osobno należności "
    "głównej.\n\n"
    'Zasady dla pola "termin_dni": zwróć SUBSTANTYWNY termin na odpowiedź, '
    "zapłatę albo inną czynność żądaną od adresata. NIE zwracaj terminu na "
    "wniesienie skargi na czynność komornika (art. 767 KPC, standardowo 7 dni) "
    "— to jest odrębny, opcjonalny termin na ZASKARŻENIE tej jednej czynności "
    "komornika, występujący jako stały akapit pouczenia w niemal każdym piśmie "
    "komorniczym, nie termin na odpowiedź czy spłatę. Jeśli dokument (np. "
    "postanowienie o podjęciu zawieszonego postępowania egzekucyjnego) nie "
    "żąda od adresata żadnej czynności w określonym terminie poza tym prawem "
    "do zaskarżenia, zwróć null.\n\n"
    'Zasady dla pola "sad_organ": zwróć organ WYDAJĄCY pismo (sąd, komornik, '
    "urząd). Jeśli pismo pochodzi od firmy lub pełnomocnika (np. przedsądowe "
    "wezwanie do zapłaty), zwróć null. IGNORUJ sąd rejestrowy wymieniony w "
    "stopce firmowej (linia z KRS/kapitałem zakładowym/NIP/REGON) — to dane "
    "rejestrowe nadawcy, nie organ wydający pismo.\n\n"
    'Zasady dla pola "czy_pismo_prawne":\n'
    '- false TYLKO wtedy, gdy tekst JEDNOZNACZNIE nie jest pismem sądowym, '
    "komorniczym, urzędowym ani pismem dotyczącym roszczeń/zobowiązań "
    "(np. potwierdzenie przelewu lub operacji bankowej, wyciąg z konta, "
    "faktura, paragon, bilet, reklama, artykuł, instrukcja, notatka prywatna).\n"
    "- false RÓWNIEŻ dla dokumentów, które klient SAM składa DO urzędu, a nie "
    "otrzymuje OD urzędu/sądu/komornika (np. własne zeznanie podatkowe PIT, "
    "deklaracja, wniosek, formularz rejestracyjny) — takie dokumenty są "
    "formalnie \"urzędowe\", ale nie są decyzją, wezwaniem ani żadnym pismem "
    "W SPRAWIE skierowanym do klienta, więc nie mieszczą się w zakresie tego "
    "kalkulatora.\n"
    "- true przy JAKIEJKOLWIEK wątpliwości — tekst po OCR bywa zniekształcony, "
    "a fragment uzasadnienia, pouczenia czy załącznika pisma procesowego też "
    "jest pismem prawnym.\n\n"
    'Zasady dla pola "rodzaj_pisma" — wybierz kategorię GŁÓWNEGO pisma w '
    "tekście (pomiń sądowe pismo przewodnie doręczające odpis, jeśli po nim "
    "następuje właściwe pismo):\n"
    '- "pozew": pozew inicjujący sprawę (tytuł POZEW, żądanie zasądzenia).\n'
    '- "nakaz_zaplaty": nakaz zapłaty wydany przez sąd/e-sąd.\n'
    '- "wezwanie_do_zaplaty": wezwanie do zapłaty (przedsądowe lub sądowe).\n'
    '- "pismo_w_toku_postepowania": pismo w JUŻ TOCZĄCEJ SIĘ sprawie — pismo '
    "przygotowawcze, odpowiedź na pozew/sprzeciw, replika, stanowisko strony, "
    "sądowe pismo przewodnie doręczające odpisy pism (uwaga: takie pismo "
    "często cytuje żądania pozwu i przepisy, np. art. 299 KSH — to NIE czyni "
    "go pozwem).\n"
    '- "pismo_komornicze": pismo komornika w postępowaniu egzekucyjnym '
    "(zawiadomienie o wszczęciu egzekucji, zajęcie, wezwanie do wykazu "
    "majątku) lub wniosek egzekucyjny/postanowienie o umorzeniu egzekucji.\n"
    '- "decyzja_urzedowa": decyzja/zawiadomienie ZUS, urzędu skarbowego lub '
    "innego organu.\n"
    '- "inne": pismo prawne niepasujące do żadnej kategorii.\n'
    "- null: nie da się ustalić (tekst zbyt zniekształcony).\n\n"
    'Zasady dla pola "adresat" — decyduje WYŁĄCZNIE forma prawna pozwanego/'
    "wzywanego (nie szukaj wprost słów \"art. 299\"/\"członek zarządu\" — ten "
    "kalkulator dotyczy tylko spraw odpowiedzialności członków zarządu, więc "
    "gdy pozwanym jest osoba fizyczna, ZAWSZE zakładaj, że chodzi o członka "
    "zarządu, nawet jeśli podstawa prawna nie jest w tym piśmie wprost "
    "wspomniana — może wynikać z innych dokumentów w sprawie):\n"
    '- "czlonek_zarzadu": pozwany/wzywany to OSOBA FIZYCZNA (imię i nazwisko, '
    'PESEL, "Pan"/"Pani") — niezależnie od tego, czy dokument wprost wspomina '
    "art. 299 KSH czy nie.\n"
    '- "spolka": pozwany/wzywany to SPÓŁKA jako taka (Sp. z o.o., S.A., sp. k. '
    "itp. w NAZWIE POZWANEGO).\n"
    '- "organ": pozwanym/organem wydającym pismo jest ZUS, Urząd Skarbowy lub '
    "inny organ publiczny.\n"
    '- null: nie da się jednoznacznie ustalić.\n'
    '"epu" = true, jeśli pismo pochodzi z elektronicznego postępowania '
    'upominawczego (e-sąd, Sąd Rejonowy Lublin-Zachód, sygnatura "Nc-e").\n\n'
    "Odpowiedź TYLKO w formacie JSON, bez komentarzy.\n\nTekst dokumentu:\n"
)


def extract_fields_ai(text: str, api_key: str) -> dict:
    """Wyciąga pola dokumentu przez Claude Haiku → słownik z polami.

    Zwraca {} przy braku klucza, błędzie API lub niepoprawnym JSON — wołający
    ma wtedy użyć wyniku z doc_extractor.extract_fields() (regex) bez zmian.
    """
    if not api_key or not text:
        return {}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _PROMPT_TEMPLATE + text[:_MAX_CHARS]
        response = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}
