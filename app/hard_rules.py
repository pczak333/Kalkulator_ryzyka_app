"""Stosuje twarde reguły bezpieczeństwa HR01–HR10 z CSV 11."""
from __future__ import annotations
from dataclasses import dataclass, field
from scoring_engine import elevate_risk


@dataclass
class HardRuleResult:
    triggered: list[str] = field(default_factory=list)   # id reguł
    warnings: list[str] = field(default_factory=list)     # komunikaty dla klienta
    minimum_risk_code: str = ""                           # najwyższe wymagane minimum


# Komunikaty z CSV 11 (hard-coded odzwierciedlenie Excela; nie na stałe – patrz uwaga poniżej)
# Reguły są utrzymywane w CSV 11; poniżej odwzorowanie logiki warunków.
_RULE_DEFS = [
    {
        "id": "HR01",
        "condition": lambda s: (
            s.get("K1") == "K1_POZEW_CZLONEK_ZARZADU"
            and s.get("K2") == "K2_DAYS_LEFT_0_3"
        ),
        "min_risk": "RISK_URGENT",
        "warning": (
            "Na reakcję pozostało bardzo mało czasu. "
            "Nie warto odkładać sprawy — najważniejsze jest szybkie potwierdzenie "
            "terminu i przygotowanie właściwej reakcji."
        ),
    },
    {
        "id": "HR02",
        "condition": lambda s: (
            s.get("K1") == "K1_NAKAZ_CZLONEK_ZARZADU"
            and s.get("K2") == "K2_DAYS_LEFT_0_3"
        ),
        "min_risk": "RISK_URGENT",
        "warning": (
            "Na reakcję pozostało bardzo mało czasu. "
            "Nie warto odkładać sprawy — najważniejsze jest szybkie potwierdzenie "
            "terminu i przygotowanie właściwej reakcji."
        ),
    },
    {
        "id": "HR03",
        "condition": lambda s: (
            s.get("K1") == "K1_POZEW_CZLONEK_ZARZADU"
            and s.get("K2") == "K2_DAYS_LEFT_4_7"
        ),
        "min_risk": "RISK_HIGH",
        "warning": (
            "Czas na reakcję jest ograniczony. Warto działać bez zwłoki: "
            "potwierdzić termin, sprawdzić dokument i ustalić najbezpieczniejszy "
            "sposób reakcji."
        ),
    },
    {
        "id": "HR04",
        "condition": lambda s: (
            s.get("K1") == "K1_NAKAZ_CZLONEK_ZARZADU"
            and s.get("K2") == "K2_DAYS_LEFT_4_7"
        ),
        "min_risk": "RISK_HIGH",
        "warning": (
            "Czas na reakcję jest ograniczony. Warto działać bez zwłoki: "
            "potwierdzić termin, sprawdzić dokument i ustalić najbezpieczniejszy "
            "sposób reakcji."
        ),
    },
    {
        "id": "HR05",
        # CSV 11 pełny warunek: K2_DAYS_LEFT_UNKNOWN AND dokument_glowny_zawiera_termin = TAK.
        # Drugi człon wymaga OCR – brak go w MVP, reguła działa konserwatywnie
        # (strzela zawsze gdy deadline nieznany).
        "condition": lambda s: s.get("K2") == "K2_DAYS_LEFT_UNKNOWN",
        "min_risk": "RISK_MEDIUM",
        "warning": (
            "Nie udało się jednoznacznie ustalić terminu reakcji. "
            "W pierwszej kolejności trzeba sprawdzić datę doręczenia, "
            "treść pouczenia i sposób liczenia terminu."
        ),
    },
    {
        "id": "HR06",
        "condition": lambda s: (
            s.get("EPU") is True
            and s.get("K2") == "K2_DAYS_LEFT_0_3"
        ),
        "min_risk": "RISK_URGENT",
        "warning": (
            "Dokument może pochodzić z EPU / e-Sądu, a czas na reakcję jest "
            "bardzo krótki. Przy tak krótkim terminie trzeba przede wszystkim "
            "zachować termin i prawidłowo oznaczyć nakaz albo pismo."
        ),
    },
    {
        "id": "HR07",
        "condition": lambda s: (
            s.get("EPU") is True
            and s.get("K2") == "K2_DAYS_LEFT_4_7"
        ),
        "min_risk": "RISK_HIGH",
        "warning": (
            "Dokument może pochodzić z EPU / e-Sądu, a czas na reakcję jest "
            "ograniczony. Warto szybko potwierdzić termin, pouczenie i właściwy "
            "tryb reakcji."
        ),
    },
    {
        "id": "HR08",
        "condition": lambda s: (
            s.get("K4") == "K4_BOARD_UNKNOWN"
            and s.get("K5") == "K5_KRS_UNKNOWN"
        ),
        "min_risk": "",
        "warning": (
            "Nie ma pewności co do statusu w zarządzie ani aktualności wpisu "
            "w KRS. Warto szybko uporządkować te informacje, żeby nie oprzeć "
            "decyzji na błędnych założeniach."
        ),
    },
    {
        "id": "HR09",
        "condition": lambda s: (
            s.get("K4") == "K4_BOARD_RESIGNED"
            and s.get("K5") == "K5_KRS_NOT_UPDATED"
        ),
        "min_risk": "",
        "warning": (
            "Wskazano rezygnację albo odwołanie, ale wpis w KRS może być "
            "nieaktualny. Trzeba porównać dokument źródłowy, datę skuteczności "
            "i aktualny odpis KRS."
        ),
    },
]


def apply(state: dict, current_risk_code: str) -> tuple[str, HardRuleResult]:
    """
    Stosuje twarde reguły i zwraca (nowy_kod_ryzyka, HardRuleResult).

    Parameters
    ----------
    state : dict
        Słownik z kluczami K1, K2, K3, K4, K5, K6, K7, EPU.
    current_risk_code : str
        Aktualny kod ryzyka przed twardymi regułami.
    """
    result = HardRuleResult(minimum_risk_code=current_risk_code)
    final_risk = current_risk_code

    for rule in _RULE_DEFS:
        try:
            triggered = rule["condition"](state)
        except Exception:
            triggered = False

        if triggered:
            result.triggered.append(rule["id"])
            result.warnings.append(rule["warning"])
            if rule["min_risk"]:
                final_risk = elevate_risk(final_risk, rule["min_risk"])

    # HR11 — pismo procesowe w toku sprawy: brak pełnej dokumentacji
    if state.get("DOC_TYPE") == "PISMO_PROCESOWE_SADOWE":
        result.triggered.append("HR11")
        result.warnings.append(
            "Przesłana dokumentacja wskazuje na toczące się postępowanie sądowe. "
            "Bez dostępu do kompletnych akt sprawy (pozwu, odpowiedzi na pozew, "
            "sprzeciwu i wcześniejszych pism) rzetelna ocena nie jest możliwa. "
            "Zalecamy przesłanie pełnej dokumentacji w ramach Audytu 48h."
        )
        final_risk = elevate_risk(final_risk, "RISK_HIGH")

    # HR10 — niska jakość OCR (aktywna od etapu 2)
    if state.get("OCR_QUALITY") == "LOW":
        result.triggered.append("HR10")
        result.warnings.append(
            "Jakość odczytu dokumentu jest niepewna. "
            "Dane powinny zostać zweryfikowane ręcznie przed wyciągnięciem wniosków."
        )

    result.minimum_risk_code = final_risk
    return final_risk, result
