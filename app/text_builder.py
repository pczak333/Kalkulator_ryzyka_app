"""Składa i sanitizuje tekst końcowy dla klienta."""
from __future__ import annotations
import re
from context_modules import ContextOutput
from hard_rules import HardRuleResult
from scoring_engine import risk_label_for_code

# Wzorce technikaliów zakazanych w wyniku klienta
_FORBIDDEN_PATTERNS = [
    r"\bRISK_\w+\b",
    r"\bK[1-7]_\w+\b",
    r"\bHR\d{2}\b",
    r"\bscenario_id\b",
    r"\brisk_level_code\b",
    r"\bscenariusz bazowy\b",
    r"\bmoduł\b",
    r"\bdynamicznie\b",
    r"\bfallback\b",
    r"\breguła techniczna\b",
    r"\binstrukcja dla AI\b",
    r"\bSCN_\d+\b",
    r"\bBASE_\d+\b",
    r"\bMOD_\w+\b",
]
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS), re.IGNORECASE)

# Frazy K4 sprzeczne z odpowiedzią – usuwane podczas sanitizacji
_K4_PHRASES_ACTIVE = [
    r"[Uu]żytkownik wskazał[,\s]+że nadal pełni funkcję w zarządzie\.?",
    r"[Nn]adal pełni funkcję w zarządzie\.?",
]
_K4_PHRASES_RESIGNED = [
    r"[Ww]skazano rezygnację lub odwołanie\s+oraz aktualny wpis w KRS\.?",
    r"[Dd]odatkowo wskazano rezygnację lub odwołanie.*?KRS\.?",
]
_K4_ACTIVE_RE = re.compile("|".join(_K4_PHRASES_ACTIVE))
_K4_RESIGNED_RE = re.compile("|".join(_K4_PHRASES_RESIGNED))

_LEGAL_DISCLAIMER = (
    "To jest automatyczna, orientacyjna ocena ryzyka i pilności sprawy. "
    "Nie stanowi porady prawnej, opinii prawnej ani rekomendacji procesowej. "
    "Indywidualna rekomendacja ścieżki obrony może zostać przygotowana dopiero "
    "po analizie dokumentów w ramach Audytu 48h."
)

_CTA = (
    "Jeśli chcesz uzyskać pełną, indywidualną analizę — warto rozważyć "
    "**Audyt 48h**, w którym prawnik sprawdza dokumenty, terminy i możliwe "
    "kierunki reakcji."
)


def _clean(text: str, k4_code: str = "") -> str:
    """Usuwa techniczne kody i sprzeczne frazy K4 z tekstu."""
    text = _FORBIDDEN_RE.sub("", str(text)).strip()
    # Usuń frazy sprzeczne z odpowiedzią K4
    if k4_code in ("K4_BOARD_RESIGNED", "K4_BOARD_UNKNOWN"):
        text = _K4_ACTIVE_RE.sub("", text)
    elif k4_code == "K4_BOARD_ACTIVE":
        text = _K4_RESIGNED_RE.sub("", text)
    # Usuń wielokrotne puste zdania/spacje
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _nonblank(text: str) -> bool:
    return bool(text and str(text).strip() and str(text).strip() != "nan")


def build(
    scenario: dict,
    context: ContextOutput,
    hard_rule_result: HardRuleResult,
    final_risk_code: str,
    days_exact: int | None = None,
    k4_code: str = "",
) -> dict:
    """
    Buduje słownik z sekcjami tekstu dla klienta.

    Zwraca:
    -------
    dict z kluczami:
      - risk_label : str
      - summary    : str  (akapit 1 – co wybrano i termin)
      - explanation: str  (dlaczego takie ryzyko)
      - practical  : str  (kontekst dokumentu)
      - warnings   : list[str] (z twardych reguł)
      - next_steps : str  (co teraz najważniejsze)
      - cta        : str
      - disclaimer : str
      - full_text  : str  (gotowy do wyświetlenia)
    """
    risk_label = risk_label_for_code(final_risk_code)

    # --- Sekcja 1: podsumowanie ze scenariusza ---
    summary_base = str(scenario.get("user_summary_base", "") or "").strip()
    if not _nonblank(summary_base):
        summary_base = f"Sprawa została wstępnie zakwalifikowana jako: {risk_label}."

    # Wstaw konkretną liczbę dni jeśli znana
    if days_exact is not None and days_exact >= 0:
        day_word = "dzień" if days_exact == 1 else "dni"
        summary_base = re.sub(
            r"(około\s+)?\d+\s*[–-]\s*\d+\s*dni",
            f"{days_exact} {day_word}",
            summary_base,
        )

    # --- Sekcja 2: wyjaśnienie ryzyka ---
    explanation_parts = []
    base_exp = str(scenario.get("user_risk_explanation_base", "") or "").strip()
    if _nonblank(base_exp):
        explanation_parts.append(base_exp)
    if context.urgency_note:
        explanation_parts.append(context.urgency_note)
    if context.deadline_text:
        explanation_parts.append(context.deadline_text)

    # --- Sekcja 3: kontekst praktyczny ---
    practical_parts = []
    base_prac = str(scenario.get("user_practical_meaning_base", "") or "").strip()
    if _nonblank(base_prac):
        practical_parts.append(base_prac)
    if context.k4_text:
        practical_parts.append(context.k4_text)
    if context.k5_text:
        practical_parts.append(context.k5_text)
    if context.krs_note:
        practical_parts.append(context.krs_note)
    if context.zus_note:
        practical_parts.append(context.zus_note)

    # --- Sekcja 4: wsparcie K3, cel K6 ---
    support_parts = []
    if context.k3_text:
        support_parts.append(context.k3_text)
    if context.k6_text:
        support_parts.append(context.k6_text)

    # --- Sekcja 5: następny krok ---
    next_step_base = str(scenario.get("user_next_step_base", "") or "").strip()

    # --- Nota o dniach kalendarzowych ---
    cal_note = context.calendar_note or (
        "Do tego terminu wliczają się także soboty, niedziele i dni świąteczne."
    )

    # --- Budowa pełnego tekstu ---
    sections = []

    sections.append(f"### {risk_label}\n")

    sections.append(summary_base)

    if explanation_parts:
        sections.append("\n".join(p for p in explanation_parts if _nonblank(p)))

    if cal_note:
        sections.append(f"_{cal_note}_")

    if practical_parts:
        sections.append("\n".join(p for p in practical_parts if _nonblank(p)))

    if support_parts:
        sections.append("\n".join(p for p in support_parts if _nonblank(p)))

    if hard_rule_result.warnings:
        for w in hard_rule_result.warnings:
            sections.append(f"**Ważne:** {w}")

    if _nonblank(next_step_base):
        sections.append(f"**Co teraz warto zrobić:** {next_step_base}")

    sections.append(_CTA)
    sections.append(f"---\n_{_LEGAL_DISCLAIMER}_")

    full_text = "\n\n".join(s for s in sections if s)
    full_text = _clean(full_text, k4_code)

    return {
        "risk_label": risk_label,
        "summary": _clean(summary_base, k4_code),
        "explanation": _clean(" ".join(explanation_parts), k4_code),
        "practical": _clean(" ".join(practical_parts), k4_code),
        "warnings": [_clean(w) for w in hard_rule_result.warnings],
        "next_steps": _clean(next_step_base),
        "calendar_note": cal_note,
        "cta": _CTA,
        "disclaimer": _LEGAL_DISCLAIMER,
        "full_text": full_text,
    }


def sanitize_check(text: str) -> list[str]:
    """Zwraca listę znalezionych fragmentów technicznych (do panelu testowego)."""
    return _FORBIDDEN_RE.findall(text)
