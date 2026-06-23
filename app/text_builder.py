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
    r"[Ww]skazano, że nadal pełni funkcję w zarządzie\.?",
    r"[Nn]adal pełni funkcję w zarządzie\.?",
]
_K4_PHRASES_RESIGNED = [
    r"[Ww]skazano rezygnację lub odwołanie\s+oraz aktualny wpis w KRS\.?",
    r"[Dd]odatkowo wskazano rezygnację lub odwołanie.*?KRS\.?",
]
_K4_ACTIVE_RE = re.compile("|".join(_K4_PHRASES_ACTIVE))
_K4_RESIGNED_RE = re.compile("|".join(_K4_PHRASES_RESIGNED))

# Zastąpienia "Użytkownik" formami bezosobowymi – spec. zabrania tego słowa w wyniku klienta
_UZYTKOWNIK_SUBS = [
    (re.compile(r"[Uu]żytkownik wskazał[,\s]+że\s+"), "Wskazano, że "),
    (re.compile(r"[Uu]żytkownik może\s+"), "Można "),
    (re.compile(r"[Uu]żytkownik jest gotowy przekazać\s+"), "Jeśli dokumenty zostaną przekazane "),
    (re.compile(r"\b[Uu]żytkownik\b"), "W formularzu wskazano"),
]

_LEGAL_DISCLAIMER = "Ocena orientacyjna — nie stanowi porady prawnej."

# CTA dobierane dynamicznie — nie używać tego bezpośrednio; używać _cta_for_doc_type()
_CTA_PERSONAL = (
    "Dokument jest skierowany **bezpośrednio do Ciebie** — decyzja procesowa musi być trafna. "
    "**Audyt 48h** to pisemna opinia prawna sporządzona przez radcę prawnego w ciągu 48 godzin. "
    "Nie automatyczna ocena — dokument, na którym możesz oprzeć konkretny krok procesowy."
)
_CTA_COMPANY = (
    "Brak reakcji w terminie może otworzyć wierzycielowi drogę do pozwu "
    "**bezpośrednio przeciwko Tobie** jako członkowi zarządu (art. 299 KSH). "
    "**Audyt 48h** to pisemna opinia prawna sporządzona przez radcę prawnego — "
    "nie automatyczna ocena, ale dokument, na którym możesz oprzeć swoją decyzję."
)


def _cta_for_doc_type(doc_type: str) -> str:
    """Wybiera CTA zależnie od tego, czy dokument jest już skierowany do członka zarządu."""
    if "CZLONEK_ZARZADU" in doc_type:
        return _CTA_PERSONAL
    return _CTA_COMPANY


def _clean(text: str, k4_code: str = "") -> str:
    """Usuwa techniczne kody i sprzeczne frazy K4 z tekstu."""
    if k4_code is None:
        k4_code = ""
    text = _FORBIDDEN_RE.sub("", str(text)).strip()
    # Usuń frazy sprzeczne z odpowiedzią K4 (przed ogólną zamianą "Użytkownik")
    if k4_code in ("K4_BOARD_RESIGNED", "K4_BOARD_UNKNOWN"):
        text = _K4_ACTIVE_RE.sub("", text)
    elif k4_code == "K4_BOARD_ACTIVE":
        text = _K4_RESIGNED_RE.sub("", text)
    # Zastąp pozostałe "Użytkownik" formami bezosobowymi
    for pattern, replacement in _UZYTKOWNIK_SUBS:
        text = pattern.sub(replacement, text)
    # Usuń wielokrotne puste zdania/spacje
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _nonblank(text: str) -> bool:
    return bool(text and str(text).strip() and str(text).strip() != "nan")


def _as_sentence(text: str) -> str:
    """Zamienia fragment bezokolicznikowy na pełne zdanie z 'Warto '."""
    text = text.strip()
    if not text:
        return text
    if text[0].islower():
        text = "Warto " + text
    if text[-1] not in ".!?":
        text += "."
    return text


def _lead_paragraph(labels: dict, days_exact: int | None, k4_code: str = "") -> str:
    """Generuje spersonalizowany nagłówek z konkretnych wyborów formularza."""
    parts = []
    k1_label = labels.get("K1", "")
    k7_label = labels.get("K7", "")
    k4_label = labels.get("K4", "")
    k5_label = labels.get("K5", "")

    if k1_label:
        if days_exact is not None and days_exact < 0:
            parts.append(
                f"Termin na reakcję na **{k1_label.lower()}** mógł już **upłynąć** — "
                "konieczne jest pilne sprawdzenie sytuacji procesowej."
            )
        elif days_exact is not None:
            day_word = "dzień" if days_exact == 1 else "dni"
            cal = " Termin wlicza soboty, niedziele i święta." if days_exact <= 14 else ""
            parts.append(
                f"Na **{k1_label.lower()}** masz **{days_exact} {day_word}**"
                f" kalendarzowych na reakcję.{cal}"
            )
        else:
            parts.append(f"Dokument: **{k1_label}**.")

    if k4_code in ("K4_BOARD_RESIGNED", "K4_BOARD_UNKNOWN") and k4_label:
        k5_part = f" ({k5_label})" if k5_label else ""
        parts.append(f"Status w zarządzie: {k4_label.lower()}{k5_part}.")

    if k7_label and not any(x in k7_label.lower() for x in ("nie wiem", "nie widzę")):
        parts.append(f"Kwota roszczenia: **{k7_label}**.")

    return " ".join(parts)


def build(
    scenario: dict,
    context: ContextOutput,
    hard_rule_result: HardRuleResult,
    final_risk_code: str,
    days_exact: int | None = None,
    k4_code: str = "",
    labels: dict | None = None,
    doc_type: str = "",
) -> dict:
    risk_label = risk_label_for_code(final_risk_code)
    lbl = labels or {}
    cta = _cta_for_doc_type(doc_type)

    # 1. Spersonalizowany nagłówek z konkretnych wyborów formularza
    lead = _lead_paragraph(lbl, days_exact, k4_code)

    # 2. Kontekst praktyczny z CSV 12 (najkonkretniejsza sekcja scenariusza)
    base_prac = str(scenario.get("user_practical_meaning_base", "") or "").strip()

    # 3. Kluczowy kontekst — jeden najważniejszy (priorytet: ZUS > KRS > pilność > nieznany dok.)
    key_context = (
        context.zus_note
        or context.krs_note
        or context.urgency_note
        or context.unknown_doc_note
        or ""
    )

    # 4. EPU sprzeciw — tylko przy krótkim lub nieznanym terminie
    epu_note = ""
    if context.epu_text and (days_exact is None or days_exact <= 14):
        epu_note = context.epu_text

    # 5. Kwota — tylko gdy konkretna (nie "nie wiem")
    qty_note = ""
    if context.quantity_note and not any(
        x in context.quantity_note.lower() for x in ("nie wskazano", "nie wiem")
    ):
        qty_note = context.quantity_note

    # 6. Następny krok z CSV 12
    next_step_base = str(scenario.get("user_next_step_base", "") or "").strip()

    # --- Składanie sekcji (max 8) ---
    sections = [f"### {risk_label}\n"]

    if lead:
        sections.append(lead)

    if _nonblank(base_prac):
        sections.append(base_prac)

    if _nonblank(key_context):
        sections.append(_as_sentence(key_context))

    if _nonblank(context.epu_block_text):
        sections.append(
            "**Uwaga — dokument z EPU / e-Sądu:** Postępowanie elektroniczne rządzi się "
            "własnymi zasadami (termin sprzeciwu, zakres zaskarzenia, skutki po sprzeciwie). "
            "Przeczytaj sekcję **Dodatkowa informacja: EPU / e-Sąd** poniżej "
            "— dotyczy bezpośrednio Twojej sprawy."
        )

    if _nonblank(epu_note):
        sections.append(epu_note)

    if _nonblank(qty_note):
        sections.append(qty_note)

    for w in hard_rule_result.warnings[:2]:
        sections.append(f"**Ważne:** {w}")

    if _nonblank(next_step_base):
        sections.append(f"**Co teraz warto zrobić:** {next_step_base}")

    sections.append(cta)
    sections.append(f"---\n_{_LEGAL_DISCLAIMER}_")

    full_text = "\n\n".join(s for s in sections if s)
    full_text = _clean(full_text, k4_code)
    if "Audyt 48h" not in full_text:
        full_text += "\n\n" + cta

    return {
        "risk_label": risk_label,
        "lead": lead,
        "practical": _clean(base_prac, k4_code),
        "warnings": [_clean(w) for w in hard_rule_result.warnings],
        "next_steps": _clean(next_step_base),
        "cta": cta,
        "disclaimer": _LEGAL_DISCLAIMER,
        "full_text": full_text,
        "epu_block_heading": context.epu_block_heading,
        "epu_block_text": context.epu_block_text,
        "epu_block_disclaimer": context.epu_block_disclaimer,
        "unknown_doc_note": context.unknown_doc_note,
    }


def sanitize_check(text: str) -> list[str]:
    """Zwraca listę znalezionych fragmentów technicznych (do panelu testowego)."""
    return _FORBIDDEN_RE.findall(text)
