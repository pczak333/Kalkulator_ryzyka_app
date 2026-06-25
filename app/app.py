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

_DOC_TYPE_LABELS: dict[str, str] = {
    "NAKAZ_CZLONEK_ZARZADU":           "Nakaz zapłaty",
    "NAKAZ_SPOLKA":                    "Nakaz zapłaty",
    "EPU_NAKAZ_SPOLKA":                "Nakaz zapłaty (e-Sąd / EPU)",
    "EPU_NAKAZ_CZLONEK_ZARZADU":       "Nakaz zapłaty (e-Sąd / EPU)",
    "POZEW_CZLONEK_ZARZADU":           "Pozew",
    "POZEW_SPOLKA":                    "Pozew",
    "EPU_POZEW_SPOLKA":                "Pozew (e-Sąd / EPU)",
    "EPU_POZEW_CZLONEK_ZARZADU":       "Pozew (e-Sąd / EPU)",
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU": "Wezwanie sądowe",
    "WEZWANIE_SADOWE_SPOLKA":          "Wezwanie sądowe",
    "DECYZJA_ZUS_CZLONEK_ZARZADU":     "Decyzja ZUS",
    "DECYZJA_US_CZLONEK_ZARZADU":      "Decyzja urzędu skarbowego",
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU": "Pismo organu publicznego",
}

_K7_BUCKETS_UI = [
    (10_000,  "K7_AMOUNT_UP_TO_10K"),
    (50_000,  "K7_AMOUNT_10K_50K"),
    (150_000, "K7_AMOUNT_50K_150K"),
    (500_000, "K7_AMOUNT_150K_500K"),
]


def _compute_k7_code(amount: float) -> str:
    for threshold, code in _K7_BUCKETS_UI:
        if amount <= threshold:
            return code
    return "K7_AMOUNT_ABOVE_500K"


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
                "doc_prefill", "doc_aux",
                "corr_kwota", "corr_powod", "corr_pozwany"]:
        st.session_state.pop(key, None)


def _ai_extract_fields(text: str, api_key: str) -> dict:
    """Wyciąga pola dokumentu przez Claude Haiku → słownik z polami."""
    import re as _re
    import json as _json
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "Masz przed sobą tekst polskiego pisma sądowego lub prawnego (po OCR).\n"
            "Wyciągnij następujące informacje w formacie JSON (null jeśli nie znaleziono):\n"
            '{"sygnatura":"sygnatura akt np. V GNc 2034/22/S","sad_organ":"pełna nazwa sądu lub organu",'
            '"powod":"imię i nazwisko lub nazwa powoda","pozwany":"imię i nazwisko lub nazwa pozwanego",'
            '"termin_dni":liczba_lub_null,"kwota_zl":liczba_lub_null}\n'
            "Odpowiedź TYLKO w formacie JSON, bez komentarzy.\n\nTekst dokumentu:\n"
            + text[:4000]
        )
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = _re.sub(r"^```\w*\n?", "", raw)
        raw = _re.sub(r"\n?```$", "", raw)
        return _json.loads(raw)
    except Exception:
        return {}


def _doc_type_label(doc_type_code: str) -> str:
    return _DOC_TYPE_LABELS.get(
        doc_type_code,
        doc_type_code.replace("_", " ").title()
    )


def _show_doc_summary(main: ProcessedDocument, aux: list[ProcessedDocument]):
    """Pokazuje wyniki odczytu dokumentów — układ tabelaryczny."""
    st.markdown("## Wyniki odczytu dokumentów")

    is_scan = main.ocr_engine in ("azure", "tesseract", "claude")
    if is_scan:
        st.markdown(
            "<div style='background:#fff8e1;border:1px solid #f9a825;border-radius:6px;"
            "padding:12px 16px;margin-bottom:12px;'>"
            "🖨️ <strong>Dokument to skan PDF</strong> — tekst był odczytywany przez OCR, "
            "co może powodować drobne błędy w nazwach, sygnaturach i kwotach.<br>"
            "<span style='color:#b45309;'>⚠️ <strong>Pola wymagające ręcznej weryfikacji:</strong> "
            "Powód, Pozwany, Sygnatura akt, Kwota roszczenia</span> "
            "— sprawdź je bezpośrednio w dokumencie przed wypełnieniem formularza.<br>"
            "<span style='font-size:0.9em;'>Możesz poprawić błędne wartości klikając "
            "✏️ <strong>Popraw dane odczytu</strong> poniżej.</span></div>",
            unsafe_allow_html=True,
        )

    # Bieżące wartości z uwzględnieniem korekt
    corr_kwota = st.session_state.get("corr_kwota")
    corr_powod = st.session_state.get("corr_powod")
    corr_pozwany = st.session_state.get("corr_pozwany")
    disp_amount  = corr_kwota  if corr_kwota  else main.amount
    disp_powod   = corr_powod  if corr_powod  else main.powod
    disp_pozwany = corr_pozwany if corr_pozwany else main.pozwany

    doc_label = _doc_type_label(main.doc_type_code)

    termin_str = (
        f"{main.deadline_days} dni (liczony od dnia dostarczenia dokumentu)"
        if main.deadline_days else None
    )
    kwota_str = (
        f"{disp_amount:,.2f} zł".replace(",", " ").replace(".", ",")
        if disp_amount else None
    )

    def _row(label: str, value: str | None, color: str = "#1a1a1a") -> str:
        if not value:
            return ""
        return (
            f"<tr>"
            f"<td style='color:#6b7280;padding:8px 12px;width:38%;"
            f"border-bottom:1px solid #e5e7eb;font-size:0.9rem;'>{label}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;"
            f"font-weight:500;color:{color};'>{value}</td>"
            f"</tr>"
        )

    rows = (
        _row("Sygnatura akt", main.sygnatura)
        + _row("Sąd / organ", main.sad_organ)
        + _row("Kwota roszczenia", kwota_str, "#c62828")
        + _row("Termin na reakcję", termin_str, "#c62828")
        + _row("Powód", disp_powod)
        + _row("Pozwany", disp_pozwany)
    )

    if rows:
        st.markdown(
            f"<div style='border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;"
            f"margin-bottom:12px;'>"
            f"<div style='background:#f8fafc;padding:10px 16px;"
            f"border-bottom:1px solid #e5e7eb;font-weight:600;'>📄 {doc_label}</div>"
            f"<table style='width:100%;border-collapse:collapse;'>{rows}</table>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info(f"📄 {doc_label} — nie udało się wyciągnąć szczegółów automatycznie.")

    # Popraw dane odczytu
    with st.expander("✏️ Popraw dane odczytu", expanded=False):
        st.caption("Uzupełnij lub popraw pola, które kalkulator odczytał błędnie.")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.number_input(
                "Kwota roszczenia (zł)",
                min_value=0.0,
                value=float(main.amount) if main.amount else 0.0,
                step=100.0,
                format="%.2f",
                key="corr_kwota",
            )
        with c2:
            st.text_input("Powód", value=main.powod or "", key="corr_powod")
        with c3:
            st.text_input("Pozwany", value=main.pozwany or "", key="corr_pozwany")

    # Ochrona danych
    st.markdown(
        "<div style='background:#fffbeb;border:1px solid #fbbf24;border-radius:6px;"
        "padding:8px 14px;font-size:0.85rem;margin-top:8px;margin-bottom:4px;'>"
        "🔒 <strong>Ochrona Twoich danych:</strong> Przesłane dokumenty są przetwarzane "
        "wyłącznie w celu wstępnej analizy i "
        "<strong>automatycznie usuwane po 48 godzinach</strong>. "
        "Nie są przechowywane ani udostępniane osobom trzecim.</div>",
        unsafe_allow_html=True,
    )

    # Zestawienie wszystkich dokumentów
    all_docs = [main] + aux
    total = len(all_docs)
    with st.expander(f"📋 Zestawienie dokumentów w pliku ({total})", expanded=False):
        for i, doc in enumerate(all_docs, 1):
            lbl = _doc_type_label(doc.doc_type_code)
            p_start, p_end = doc.page_range
            page_info = f"str. {p_start}–{p_end}" if p_start != p_end else f"str. {p_start}"
            date_info = doc.delivery_date.strftime("%d.%m.%Y r.") if doc.delivery_date else ""
            syg_info = f"Sygn.: **{doc.sygnatura}**" if doc.sygnatura else ""
            kwota_info = (
                f"Kwota: **{doc.amount:,.0f} zł**".replace(",", " ")
                if doc.amount else ""
            )
            badge = " ⚠️ **WYMAGA REAKCJI**" if doc.status == "GLOWNY" and doc.deadline_days else ""
            meta_parts = [x for x in [date_info, syg_info, kwota_info] if x]
            meta = " · ".join(meta_parts)
            st.markdown(
                f"**[{i}/{total}] {lbl}**{badge}  \n"
                f"<span style='font-size:0.85rem;color:#6b7280;'>{page_info}"
                + (f" · {meta}" if meta else "")
                + "</span>",
                unsafe_allow_html=True,
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
        try:
            _secrets_obj = st.secrets
            _has_anthropic = bool(_secrets_obj.get("ANTHROPIC_API_KEY", ""))
        except Exception:
            _has_anthropic = False

        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            _do_analyze = st.button(
                "Analizuj dokumenty", type="primary", use_container_width=True
            )
        with btn_col2:
            _prefill_ready = "doc_prefill" in st.session_state
            _do_ai = st.button(
                "Uruchom analizę AI pliku głównego",
                disabled=not (_prefill_ready and _has_anthropic),
                use_container_width=True,
            )

        if _do_analyze:
            secrets = {
                "AZURE_DI_KEY": st.secrets.get("AZURE_DI_KEY", ""),
                "AZURE_DI_ENDPOINT": st.secrets.get("AZURE_DI_ENDPOINT", ""),
                "ANTHROPIC_API_KEY": st.secrets.get("ANTHROPIC_API_KEY", ""),
            }
            # Wyczyść korekty z poprzedniej analizy
            for _k in ("corr_kwota", "corr_powod", "corr_pozwany"):
                st.session_state.pop(_k, None)
            with st.spinner("Analizuję dokumenty..."):
                try:
                    main_doc, aux_docs = process_files(uploaded_files, secrets)
                    st.session_state["doc_prefill"] = main_doc
                    st.session_state["doc_aux"] = aux_docs
                    st.success(f"Przeanalizowano {len(uploaded_files)} plik(ów). Formularz wyczyszczony.")
                except Exception as e:
                    st.error(f"Błąd analizy dokumentu: {e}")

        if _do_ai and _prefill_ready:
            _prefill_ai: ProcessedDocument = st.session_state["doc_prefill"]
            _api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
            with st.spinner("Analizuję plik przez AI..."):
                _ai_result = _ai_extract_fields(_prefill_ai.raw_text, _api_key)
            if _ai_result:
                if _ai_result.get("sygnatura"):
                    _prefill_ai.sygnatura = _ai_result["sygnatura"]
                if _ai_result.get("sad_organ"):
                    _prefill_ai.sad_organ = _ai_result["sad_organ"]
                if _ai_result.get("powod"):
                    _prefill_ai.powod = _ai_result["powod"]
                if _ai_result.get("pozwany"):
                    _prefill_ai.pozwany = _ai_result["pozwany"]
                if _ai_result.get("termin_dni"):
                    try:
                        _prefill_ai.deadline_days = int(_ai_result["termin_dni"])
                    except (ValueError, TypeError):
                        pass
                if _ai_result.get("kwota_zl"):
                    try:
                        _prefill_ai.amount = float(_ai_result["kwota_zl"])
                        _prefill_ai.k7_code = _compute_k7_code(_prefill_ai.amount)
                    except (ValueError, TypeError):
                        pass
                # Wyczyść korekty ręczne — AI nadpisuje
                for _k in ("corr_kwota", "corr_powod", "corr_pozwany"):
                    st.session_state.pop(_k, None)
                st.success("Analiza AI zakończona — dane zaktualizowane.")
            else:
                st.warning("Analiza AI nie zwróciła wyników. Sprawdź klucz API.")

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
        value=prefill.epu if prefill else False,
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

# K7 – Kwota roszczenia (uwzględnij korektę kwoty jeśli użytkownik ją zmienił)
st.subheader("Krok 7 — Kwota roszczenia")
_corr_kwota_val = st.session_state.get("corr_kwota")
_k7_prefill = None
if _corr_kwota_val and float(_corr_kwota_val) > 0:
    _k7_prefill = _compute_k7_code(float(_corr_kwota_val))
elif prefill:
    _k7_prefill = prefill.k7_code
k7 = labeled_radio(
    "Jaka kwota roszczenia jest wskazana w dokumencie?", "K7", "k7",
    prefill_code=_k7_prefill,
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
