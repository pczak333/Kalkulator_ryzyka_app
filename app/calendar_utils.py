# -*- coding: utf-8 -*-
"""Obliczenia kalendarza sądowego — polskie święta, dni robocze, termin końcowy.
Źródło: adaptacja kodu archiwalnego (app_archiwalna.py, linie 764–824).

Art. 115 KPC: jeśli ostatni dzień terminu wypada w sobotę, niedzielę lub ustawowe
święto — termin upływa w najbliższy następny dzień roboczy.
"""
from __future__ import annotations
from datetime import date, timedelta


def easter_sunday(year: int) -> date:
    """Algorytm Meeus/Jones/Butcher — data Niedzieli Wielkanocnej."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def poland_public_holidays(year: int) -> set[date]:
    """Polskie święta ustawowe (Dz.U. 1951 nr 4 poz. 28 z późn. zm.)."""
    fixed = {
        date(year, 1, 1),    # Nowy Rok
        date(year, 1, 6),    # Trzech Króli (od 2011)
        date(year, 5, 1),    # Święto Pracy
        date(year, 5, 3),    # Święto Konstytucji 3 Maja
        date(year, 8, 15),   # Wniebowzięcie NMP
        date(year, 11, 1),   # Wszystkich Świętych
        date(year, 11, 11),  # Narodowe Święto Niepodległości
        date(year, 12, 25),  # Boże Narodzenie (1)
        date(year, 12, 26),  # Boże Narodzenie (2)
    }
    easter = easter_sunday(year)
    movable = {
        easter + timedelta(days=1),   # Poniedziałek Wielkanocny
        easter + timedelta(days=60),  # Boże Ciało
    }
    return fixed | movable


def is_working_day(d: date) -> bool:
    """Zwraca True jeśli dzień jest dniem roboczym (pn–pt, nie święto)."""
    if d.weekday() >= 5:  # sobota=5, niedziela=6
        return False
    if d in poland_public_holidays(d.year):
        return False
    return True


def adjust_to_working_day(d: date) -> date:
    """Art. 115 KPC: przesuwa termin na następny dzień roboczy jeśli wypada wolny."""
    while not is_working_day(d):
        d += timedelta(days=1)
    return d


def compute_deadline_date(delivery: date, term_days: int) -> date:
    """
    Oblicza datę końca terminu zgodnie z KPC:
    - termin biegnie od NASTĘPNEGO dnia po doręczeniu (art. 111 § 1 KPC)
    - liczymy kalendarzowo przez term_days dni
    - jeśli koniec wypada w dzień wolny → przesuwamy (art. 115 KPC)
    """
    start = delivery + timedelta(days=1)
    end = start + timedelta(days=term_days - 1)
    return adjust_to_working_day(end)
