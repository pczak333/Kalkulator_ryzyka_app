"""KRS Guard — Kalkulator Ryzyka Prawnego (Streamlit MVP)."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
from datetime import date, timedelta

from data_loader import load_form_questions
from scoring_engine import calculate, risk_label_for_code
from hard_rules import apply as apply_hard_rules
from scenario_selector import find_scenario, resolve_doc_type
from context_modules import collect as collect_context
from text_builder import build as build_text, sanitize_check
from doc_processor import process_files, ProcessedDocument

# ── Konfiguracja strony ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="KRS Guard — Kalkulator Ryzyka",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Pomocniki ─────────────────────────────────────────────────────────────────

EPU_COMPATIBLE = {
    "K1_NAKAZ_CZLONEK_ZARZADU": "TAK",
    "K1_NAKAZ_SPOLKA": "TAK",
    "K1_POZEW_CZLONEK_ZARZADU": "OSTROZNE",
    "K1_POZEW_SPOLKA": "NIE",
    "K1_WEZWANIE_SADOWE_SPOLKA": "NIE",
    "K1_WEZWANIE_SADOWE_CZLONEK_ZARZADU": "NIE",
    "K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU": "NIE",
    "K1_INNE_NIE_WIEM": "NIE",
}

RISK_COLORS = {
    "RISK_LOW":    "#2e7d32",
    "RISK_MEDIUM": "#f57c00",
    "RISK_HIGH":   "#c62828",
    "RISK_URGENT": "#6a1b9a",
}

RISK_ICONS = {
    "RISK_LOW":    "🟢",
    "RISK_MEDIUM": "🟡",
    "RISK_HIGH":   "🔴",
    "RISK_URGENT": "🚨",
}


@st.cache_data
def get_form_data():
    return load_form_questions()


def get_answers_for_step(step_id: str) -> list[tuple[str, str]]:
    """Zwraca listę (etykieta, kod) dla danego kroku formularza."""
    df = get_form_data()
    rows = df[df["step_id"] == step_id]
    return [(r["answer_label_user"], r["answer_code_AI"])
            for _, r in rows.iterrows()
            if str(r.get("answer_label_user", "")).strip() not in ("", "nan")]


def get_label_for_code(step_id: str, code: str) -> str:
    """Zwraca polską etykietę dla danego kodu odpowiedzi."""
    for lbl, c in get_answers_for_step(step_id):
        if c == code:
            return lbl
    return ""


def labeled_radio(
    label: str, step_id: str, key: str, prefill_code: str | None = None
) -> str | None:
    options = get_answers_for_step(step_id)
    if not options:
        return None
    labels = [o[0] for o in options]
    codes = [o[1] for o in options]
    # Ustaw indeks na podstawie prefill (jeśli kod pasuje do opcji)
    default_idx = None
    if prefill_code and prefill_code in codes:
        default_idx = codes.index(prefill_code)
    idx = st.radio(
        label, range(len(labels)),
        format_func=lambda i: labels[i],
        key=key,
        index=default_idx,
    )
    return codes[idx] if idx is not None else None


def reset_calculator():
    for key in ["krs_answers", "krs_epu", "krs_days_exact",
                "k1", "epu", "use_dates", "k2", "k3", "k4", "k5", "k6", "k7",
                "delivery_date", "deadline_days", "test_pwd",
                "doc_prefill", "doc_aux"]:
        st.session_state.pop(key, None)


def _confidence_indicator(label: str, confidence: float, value: str):
    """Wyświetla pole z wykrytą wartością i wskaźnikiem pewności."""
    if confidence >= 0.75:
        st.success(f"**{label}:** {value} ✓ _(wykryto automatycznie)_")
    elif confidence >= 0.5:
        st.warning(f"**{label}:** {value} _(sprawdź — nie jestem pewny)_")
    else:
        st.error(f"**{label}:** {value} _(niska pewność — uzupełnij ręcznie)_")


def _show_doc_summary(main: ProcessedDocument, aux: list[ProcessedDocument]):
    """Pokazuje podsumowanie analizy dokumentów po wgraniu."""
    st.markdown("### Wyniki analizy dokumentu")

    col1, col2 = st.columns(2)
    with col1:
        _confidence_indicator(
            "Typ dokumentu", main.classifier_confidence,
            main.doc_type_code.replace("_", " ").title()
        )
        if main.epu:
            st.info("EPU / e-Sąd: wykryto oznaczenia e-Sądu")
        if main.delivery_date:
            _confidence_indicator(
                "Data doręczenia", 0.8,
                main.delivery_date.strftime("%d.%m.%Y")
            )
        if main.deadline_days:
            _confidence_indicator(
                "Termin z pouczenia", 0.8,
                f"{main.deadline_days} dni"
            )
    with col2:
        if main.amount:
            _confidence_indicator(
                "Kwota roszczenia", 0.85,
                f"{main.amount:,.0f} zł".replace(",", " ")
            )
        if main.days_left is not None:
            days = main.days_left
            if days <= 3:
                st.error(f"Pozostało **{days} dni** do terminu!")
            elif days <= 7:
                st.warning(f"Pozostało **{days} dni** do terminu")
            else:
                st.info(f"Pozostało **{days} dni** do terminu")

    if aux:
        with st.expander(f"Wykryto {len(aux)} dodatkowych dokumentów w pliku"):
            for i, doc in enumerate(aux, 1):
                st.markdown(
                    f"**Dokument {i}:** {doc.doc_type_code.replace('_', ' ').title()} "
                    f"— status: _{doc.status}_"
                )

    st.markdown(
        "_Sprawdź wykryte dane i popraw w formularzu poniżej jeśli coś jest nie tak._"
    )


def colored_risk_box(risk_code: str, risk_label: str):
    color = RISK_COLORS.get(risk_code, "#1a3a5c")
    icon = RISK_ICONS.get(risk_code, "⚖️")
    st.markdown(
        f"""<div style="background:{color};color:#fff;padding:16px 20px;
        border-radius:8px;font-size:1.3rem;font-weight:bold;margin-bottom:12px;">
        {icon} {risk_label}</div>""",
        unsafe_allow_html=True,
    )


# ── Nagłówek ──────────────────────────────────────────────────────────────────
st.title("⚖️ KRS Guard — Kalkulator Ryzyka Prawnego")
st.markdown(
    "_Bezpłatna, orientacyjna ocena ryzyka w sprawach odpowiedzialności "
    "członków zarządu spółek._"
)
st.divider()

# ── Krok 0: Wgraj dokumenty (opcjonalnie) ────────────────────────────────────
st.subheader("Krok 0 — Wgraj dokumenty (opcjonalnie)")
st.caption(
    "Wgraj pismo, nakaz lub inny dokument — kalkulator spróbuje wypełnić "
    "formularz automatycznie. Możesz też pominąć ten krok i wypełnić ręcznie."
)

with st.expander("📎 Wgraj dokumenty (PDF, DOCX, JPG, PNG)", expanded=False):
    uploaded_files = st.file_uploader(
        "Wybierz plik lub pliki",
        type=["pdf", "docx", "jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="doc_upload",
    )
    if uploaded_files:
        if st.button("Analizuj dokumenty", type="primary"):
            api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
            with st.spinner("Analizuję dokumenty..."):
                try:
                    main_doc, aux_docs = process_files(uploaded_files, api_key)
                    st.session_state["doc_prefill"] = main_doc
                    st.session_state["doc_aux"] = aux_docs
                    st.success("Analiza zakończona — dane zostały wstępnie wypełnione poniżej.")
                except Exception as e:
                    st.error(f"Błąd analizy dokumentu: {e}")

if "doc_prefill" in st.session_state:
    prefill: ProcessedDocument = st.session_state["doc_prefill"]
    aux_docs: list[ProcessedDocument] = st.session_state.get("doc_aux", [])
    _show_doc_summary(prefill, aux_docs)
    st.divider()
else:
    prefill = None

st.divider()

# ── Formularz ─────────────────────────────────────────────────────────────────

# K1 – Rodzaj pisma
st.subheader("Krok 1 — Rodzaj pisma")
k1 = labeled_radio(
    "Jakie pismo lub dokument dotyczy Twojej sprawy?",
    "K1", "k1",
    prefill_code=prefill.k1_code if prefill else None,
)

# EPU – checkbox zależny od K1
st.subheader("Krok 2 — E-Sąd / EPU")
epu_compat = EPU_COMPATIBLE.get(k1, "NIE")
epu_disabled = (epu_compat == "NIE")

if epu_disabled:
    if k1 in ("K1_POZEW_SPOLKA", "K1_POZEW_CZLONEK_ZARZADU"):
        st.info(
            "Pozew pochodzi z sądu tradycyjnego — nie jest wydawany "
            "przez e-Sąd ani Elektroniczne Postępowanie Upominawcze (EPU). "
            "To pytanie Cię nie dotyczy."
        )
    elif k1 in ("K1_WEZWANIE_SADOWE_SPOLKA", "K1_WEZWANIE_SADOWE_CZLONEK_ZARZADU"):
        st.info(
            "Wezwania sądowe są doręczane przez sąd tradycyjny — "
            "nie dotyczą e-Sądu ani EPU. To pytanie Cię nie dotyczy."
        )
    else:
        st.info(
            "Ten typ dokumentu nie jest wydawany przez e-Sąd "
            "ani Elektroniczne Postępowanie Upominawcze (EPU). "
            "To pytanie Cię nie dotyczy."
        )
    epu = False
else:
    if epu_compat == "OSTROZNE":
        st.warning(
            "Pozwy mogą, ale nie zawsze, pochodzić z EPU. "
            "Sprawdź pouczenie w dokumencie, zanim zaznaczysz tę opcję."
        )
    epu = st.checkbox(
        "Dokument pochodzi z EPU / e-Sądu "
        "(sygnatura Nc-e lub Sąd Rejonowy Lublin-Zachód w Lublinie)",
        key="epu",
    )
    with st.expander("Jak rozpoznać dokument z EPU / e-Sądu?"):
        st.markdown(
            "Zaznacz tę opcję, jeżeli na dokumencie widzisz oznaczenia takie jak: "
            "e-Sąd; EPU; Elektroniczne Postępowanie Upominawcze; sygnaturę "
            "z oznaczeniem Nc-e; Sad Rejonowy Lublin-Zachod w Lublinie - "
            "VI Wydzial Cywilny; albo informacje, ze nakaz zaplaty zostal wydany "
            "w elektronicznym postepowaniu upominawczym. "
            "Samo oznaczenie VI Wydzial Cywilny nie musi oznaczac e-Sadu. "
            "Dokument z EPU / e-Sądu to nie każdy dokument otrzymany elektronicznie."
        )

# K2 – Czas na reakcję
st.subheader("Krok 3 — Czas na reakcję")
# Jeśli prefill znalazł datę i termin — automatycznie zaznacz checkbox
_prefill_has_dates = prefill and prefill.delivery_date and prefill.deadline_days
use_dates = st.checkbox(
    "Znam datę doręczenia — oblicz za mnie ile zostało dni",
    key="use_dates",
    value=bool(_prefill_has_dates),
)

days_exact: int | None = None
k2: str = ""

if use_dates:
    col1, col2 = st.columns(2)
    with col1:
        delivery_date = st.date_input(
            "Data doręczenia dokumentu",
            value=prefill.delivery_date if _prefill_has_dates else date.today(),
            key="delivery_date",
        )
    with col2:
        deadline_days = st.number_input(
            "Termin z pouczenia (dni)", min_value=1, max_value=365,
            value=int(prefill.deadline_days) if _prefill_has_dates else 14,
            key="deadline_days",
        )
    deadline_date = delivery_date + timedelta(days=int(deadline_days))
    days_exact = (deadline_date - date.today()).days
    st.info(
        f"Termin upływa **{deadline_date.strftime('%d.%m.%Y')}** "
        f"— pozostało **{days_exact} dni** kalendarzowych."
    )
    st.caption(
        "Do tego terminu wliczają się soboty, niedziele i dni świąteczne."
    )
    if days_exact < 0:
        k2 = "K2_DAYS_LEFT_0_3"
    elif days_exact <= 3:
        k2 = "K2_DAYS_LEFT_0_3"
    elif days_exact <= 7:
        k2 = "K2_DAYS_LEFT_4_7"
    elif days_exact <= 14:
        k2 = "K2_DAYS_LEFT_8_14"
    else:
        k2 = "K2_DAYS_LEFT_ABOVE_14"
else:
    k2 = labeled_radio(
        "Ile czasu zostało na reakcję?",
        "K2", "k2"
    )

# K3 – Zakres wsparcia
st.subheader("Krok 4 — Zakres wsparcia")
k3 = labeled_radio("Czego teraz potrzebujesz?", "K3", "k3")

# K4 – Status w zarządzie
st.subheader("Krok 5 — Status w zarządzie")
k4 = labeled_radio("Jaki jest Twój status w zarządzie?", "K4", "k4")

# K5 – KRS (tylko gdy rezygnacja/odwołanie)
# Spec: gdy K4_BOARD_UNKNOWN — ustaw K5_KRS_UNKNOWN bez pytania
k5: str = "K5_NOT_APPLICABLE"
if k4 == "K4_BOARD_RESIGNED":
    st.subheader("Krok 5b — Wpis w KRS")
    k5 = labeled_radio(
        "Czy zmiana w zarządzie została ujawniona w KRS?", "K5", "k5"
    )
elif k4 == "K4_BOARD_UNKNOWN":
    k5 = "K5_KRS_UNKNOWN"
elif k4 == "K4_BOARD_ACTIVE":
    k5 = "K5_NOT_APPLICABLE"

# K6 – Cel klienta
st.subheader("Krok 6 — Twój cel")
k6 = labeled_radio("Czego przede wszystkim potrzebujesz?", "K6", "k6")

# K7 – Kwota roszczenia
st.subheader("Krok 7 — Kwota roszczenia")
k7 = labeled_radio(
    "Jaka kwota roszczenia jest wskazana w dokumencie?", "K7", "k7",
    prefill_code=prefill.k7_code if prefill else None,
)

st.divider()
if st.button("Oblicz ryzyko →", use_container_width=True, type="primary"):
    missing_labels = []
    if not k1:
        missing_labels.append("Krok 1 — Rodzaj pisma")
    if not use_dates and not k2:
        missing_labels.append("Krok 3 — Czas na reakcję")
    if not k3:
        missing_labels.append("Krok 4 — Zakres wsparcia")
    if not k4:
        missing_labels.append("Krok 5 — Status w zarządzie")
    if k4 == "K4_BOARD_RESIGNED" and not k5:
        missing_labels.append("Krok 5b — Wpis w KRS")
    if not k6:
        missing_labels.append("Krok 6 — Twój cel")
    if not k7:
        missing_labels.append("Krok 7 — Kwota roszczenia")

    if missing_labels:
        st.warning("Zaznacz brakujące opcje w: " + ", ".join(missing_labels))
    else:
        _ocr_quality = (
            prefill.ocr_quality if prefill else "HIGH"
        )
        st.session_state["krs_answers"] = {
            "K1": k1 or "", "K2": k2 or "", "K3": k3 or "",
            "K4": k4 or "", "K5": k5 or "", "K6": k6 or "", "K7": k7 or "",
            "K2A": "K2A_DELIVERY_DATE_KNOWN" if use_dates else "K2A_DELIVERY_DATE_UNKNOWN",
            "OCR_QUALITY": _ocr_quality,
        }
        st.session_state["krs_epu"] = epu
        st.session_state["krs_days_exact"] = days_exact

# ── Obliczenia i wynik ────────────────────────────────────────────────────────
if "krs_answers" in st.session_state:
    answers    = st.session_state["krs_answers"]
    epu        = st.session_state["krs_epu"]
    days_exact = st.session_state["krs_days_exact"]

    state = {**answers, "EPU": epu}

    # 1. Punktacja
    score_result = calculate(answers)

    # 2. Twarde reguły
    final_risk_code, hard_result = apply_hard_rules(state, score_result.risk_level_code)
    final_risk_label = risk_label_for_code(final_risk_code)

    # 3. Scenariusz bazowy
    scenario = find_scenario(
        k1_code=answers["K1"],
        k2_code=answers["K2"],
        risk_level_code=final_risk_code,
        epu=epu,
    )

    # 4. Moduły kontekstowe
    doc_type = resolve_doc_type(answers["K1"], epu)
    context = collect_context(state, doc_type, days_exact, risk_code=final_risk_code)

    # 5. Tekst końcowy
    labels = {
        "K1": get_label_for_code("K1", answers["K1"]),
        "K4": get_label_for_code("K4", answers["K4"]),
        "K5": get_label_for_code("K5", answers["K5"]) if answers["K5"] not in (
            "K5_NOT_APPLICABLE", "K5_KRS_UNKNOWN", ""
        ) else "",
        "K7": get_label_for_code("K7", answers["K7"]),
    }
    output = build_text(scenario, context, hard_result, final_risk_code, days_exact,
                        k4_code=answers["K4"], labels=labels, doc_type=doc_type)

    # ── Wyświetlenie wyniku ────────────────────────────────────────────────
    st.divider()
    st.header("Twoja ocena ryzyka")
    colored_risk_box(final_risk_code, output["risk_label"])
    st.markdown(output["full_text"])

    # ── Blok EPU (uzupełnienie, gdy EPU=TAK) ──────────────────────────────
    if output.get("epu_block_text"):
        heading = output.get("epu_block_heading") or "Dodatkowa informacja: EPU / e-Sąd"
        with st.expander(f"ℹ️ {heading}", expanded=True):
            st.markdown(output["epu_block_text"])
            if output.get("epu_block_disclaimer"):
                st.caption(output["epu_block_disclaimer"])

    # ── Reset ─────────────────────────────────────────────────────────────
    st.divider()
    st.button(
        "🔄 Wyczyść kalkulator i wprowadź nowe dane",
        on_click=reset_calculator,
        use_container_width=True,
    )

    # ── Panel testowy (ukryty za hasłem) ──────────────────────────────────
    st.divider()
    with st.expander("🔧 Panel techniczny (dla testera / administratora)"):
        pwd = st.text_input("Hasło dostępu", type="password", key="test_pwd")
        try:
            panel_pwd = st.secrets.get("TEST_PANEL_PASSWORD", "krs-test-2024")
        except Exception:
            panel_pwd = "krs-test-2024"
        if pwd == panel_pwd:
            st.success("Dostęp przyznany")

            st.subheader("Punktacja")
            cols = st.columns(5)
            for i, (lbl, val) in enumerate(
                [("C", score_result.C), ("P", score_result.P),
                 ("H", score_result.H), ("W", score_result.W),
                 ("S", score_result.S)]
            ):
                cols[i].metric(lbl, val)

            st.subheader("Ryzyko przed/po twardych regułach")
            st.write(
                f"Przed: `{score_result.risk_level_code}` ({score_result.risk_level_label})"
            )
            st.write(f"Po: `{final_risk_code}` ({final_risk_label})")

            st.subheader("Odpowiedzi")
            st.json(state)

            st.subheader("Twarde reguły")
            if hard_result.triggered:
                st.write("Wyzwolone:", hard_result.triggered)
            else:
                st.write("Żadna twarda reguła nie wyzwolona.")

            st.subheader("Scenariusz bazowy")
            scen_id = scenario.get("scenario_id_base", "brak")
            st.write(f"ID: `{scen_id}`")
            st.write(f"Typ dokumentu: `{doc_type}`")
            st.write(f"EPU: `{epu}`")

            st.subheader("Moduły kontekstowe")
            for lbl, txt in [
                ("K3", context.k3_text), ("K4", context.k4_text),
                ("K5", context.k5_text), ("K6", context.k6_text),
                ("Termin", context.deadline_text), ("KRS", context.krs_note),
                ("ZUS", context.zus_note), ("Pilność", context.urgency_note),
                ("EPU sprzeciw", context.epu_text), ("Kwota", context.quantity_note),
            ]:
                if txt:
                    st.write(f"**{lbl}:** {txt}")

            st.subheader("Kontrola sanitizacji")
            found = sanitize_check(output["full_text"])
            if found:
                st.error(f"Znaleziono kody techniczne w wyniku: {found}")
            else:
                st.success("Wynik klienta wolny od kodów technicznych ✓")
        elif pwd:
            st.error("Nieprawidłowe hasło.")

# ── Stopka ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "KRS Guard to narzędzie orientacyjnej oceny ryzyka. "
    "Nie stanowi porady prawnej. © KRS Guard Kancelaria"
)
