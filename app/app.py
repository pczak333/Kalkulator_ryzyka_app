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
    "NAKAZ_CZLONEK_ZARZADU":              "Nakaz zapłaty",
    "NAKAZ_SPOLKA":                       "Nakaz zapłaty",
    "EPU_NAKAZ_SPOLKA":                   "Nakaz zapłaty (e-Sąd / EPU)",
    "EPU_NAKAZ_CZLONEK_ZARZADU":          "Nakaz zapłaty (e-Sąd / EPU)",
    "POZEW_CZLONEK_ZARZADU":              "Pozew",
    "POZEW_SPOLKA":                       "Pozew",
    "EPU_POZEW_SPOLKA":                   "Pozew (e-Sąd / EPU)",
    "EPU_POZEW_CZLONEK_ZARZADU":          "Pozew (e-Sąd / EPU)",
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU":    "Wezwanie sądowe",
    "WEZWANIE_SADOWE_SPOLKA":             "Wezwanie sądowe",
    "DECYZJA_ZUS_CZLONEK_ZARZADU":        "Decyzja ZUS",
    "DECYZJA_US_CZLONEK_ZARZADU":         "Decyzja urzędu skarbowego",
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU":    "Pismo organu publicznego",
    "PISMO_KOMORNIK_CZLONEK_ZARZADU":     "Pismo komornicze",
    "PISMO_KOMORNIK_SPOLKA":              "Pismo komornicze (spółka)",
    "UMORZENIE_EGZEKUCJI_BEZSKUTECZNOSC": "Postanowienie o umorzeniu egzekucji",
    "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU": "Wezwanie przedsądowe",
    "WEZWANIE_PRZEDSADOWE_SPOLKA":        "Wezwanie przedsądowe (spółka)",
    "DECYZJA_ZUS_US_SPOLKA":              "Decyzja ZUS / urzędu skarbowego (spółka)",
    "PISMO_PROCESOWE_SADOWE":             "Pismo procesowe w toczącym się postępowaniu",
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
    # Usuń całkowicie dane niebędące kluczami widżetów
    for key in ["krs_answers", "krs_epu", "krs_days_exact", "test_pwd",
                "doc_prefill", "doc_aux",
                "corr_kwota", "corr_powod", "corr_pozwany",
                "_last_uploaded_names", "_art299_gate",
                "k1", "k2", "k7", "epu", "delivery_date", "deadline_days"]:
        st.session_state.pop(key, None)
    # Klucze widżetów bez prefill — ustaw explicite na None/False, NIE pop.
    # Streamlit cachuje wewnętrznie ostatnią wartość widżetu; gdy klucz jest
    # nieobecny, używa cache zamiast parametru index=. Explicite None wymusza reset.
    st.session_state["k3"] = None
    st.session_state["k4"] = None
    st.session_state["k5"] = None
    st.session_state["k6"] = None
    st.session_state["use_dates"] = False


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

    _needs_ocr = main.ocr_engine in ("azure", "tesseract", "claude")
    _ext = (main.file_ext or "").lower()
    _IMAGE_EXTS = {"jpg", "jpeg", "png", "bmp", "tiff", "tif", "gif", "webp"}

    if _needs_ocr:
        if _ext in _IMAGE_EXTS:
            _src_label = "📷 Dokument to zdjęcie lub obraz (JPG/PNG)"
            _ocr_note = (
                "Tekst był odczytywany przez OCR ze zdjęcia. Jakość zależy od "
                "ostrości, oświetlenia i kąta fotografii — mogą wystąpić błędy "
                "w nazwach, sygnaturach i kwotach."
            )
        elif _ext == "pdf":
            _src_label = "🖨️ Dokument to skan PDF"
            _ocr_note = (
                "Tekst był odczytywany przez OCR ze zeskanowanego PDF. "
                "Mogą wystąpić drobne błędy w nazwach, sygnaturach i kwotach."
            )
        else:
            _src_label = "🖨️ Dokument wymagał OCR"
            _ocr_note = (
                "Tekst był odczytywany automatycznie. "
                "Mogą wystąpić drobne błędy w nazwach, sygnaturach i kwotach."
            )
        st.markdown(
            "<div style='background:#fff8e1;border:1px solid #f9a825;border-radius:6px;"
            "padding:12px 16px;margin-bottom:12px;'>"
            f"<strong>{_src_label}</strong> — {_ocr_note}<br>"
            "<span style='color:#b45309;'>⚠️ <strong>Pola wymagające ręcznej weryfikacji:</strong> "
            "Powód, Pozwany, Sygnatura akt, Kwota roszczenia</span> "
            "— sprawdź je bezpośrednio w dokumencie przed wypełnieniem formularza.<br>"
            "<span style='font-size:0.9em;'>Możesz poprawić błędne wartości klikając "
            "✏️ <strong>Popraw dane odczytu</strong> poniżej.</span></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='background:#e8f5e9;border:1px solid #43a047;border-radius:6px;"
            "padding:12px 16px;margin-bottom:12px;'>"
            "📄 <strong>Oryginalny dokument cyfrowy</strong> — tekst odczytany natywnie "
            "(PDF/DOCX z warstwą tekstową). Dane są w pełni wiarygodne.</div>",
            unsafe_allow_html=True,
        )

    # Baner dla pisma procesowego — brak pełnej dokumentacji
    if main.doc_type_code == "PISMO_PROCESOWE_SADOWE":
        st.warning(
            "**Uwaga: dokumentacja niekompletna.**\n\n"
            "Przesłane pismo wskazuje na toczące się postępowanie sądowe, "
            "lecz bez pełnej dokumentacji sprawy (pozwu, sprzeciwu, wcześniejszych pism) "
            "nie jest możliwa rzetelna ocena ryzyka.\n\n"
            "**Zdecydowanie zalecamy przesłanie pełnej dokumentacji w ramach Audytu 48h**, "
            "który pozwoli na kompleksową analizę Twojej sytuacji."
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
            if doc.amount:
                _kf = f"{doc.amount:,.2f}".replace(",", " ").replace(".", ",")
                kwota_info = f"Kwota: **{_kf} zł**"
            else:
                kwota_info = ""
            badge = " ⚠️ **WYMAGA REAKCJI**" if doc.deadline_days else ""
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

    # Detekcja usunięcia pliku → wyczyść prefill i formularz
    _cur_names = frozenset(f.name for f in (uploaded_files or []))
    _prev_names = st.session_state.get("_last_uploaded_names", frozenset())
    if _prev_names and not _cur_names:
        reset_calculator()
        st.session_state.pop("_last_uploaded_names", None)
        st.rerun()
    elif _cur_names != _prev_names:
        st.session_state["_last_uploaded_names"] = _cur_names

    if uploaded_files:
        _do_analyze = st.button(
            "Analizuj dokumenty", type="primary", use_container_width=True
        )

        if _do_analyze:
            secrets = {
                "AZURE_DI_KEY": st.secrets.get("AZURE_DI_KEY", ""),
                "AZURE_DI_ENDPOINT": st.secrets.get("AZURE_DI_ENDPOINT", ""),
                "ANTHROPIC_API_KEY": st.secrets.get("ANTHROPIC_API_KEY", ""),
            }
            # Klucze z prefill — usuń, prefill zastąpi przez index=
            for _k in ("k1", "k7", "k2", "epu", "delivery_date", "deadline_days",
                       "use_dates", "corr_kwota", "corr_powod", "corr_pozwany",
                       "_art299_gate"):
                st.session_state.pop(_k, None)
            # Klucze bez prefill — ustaw None (nie pop), żeby Streamlit nie użył cache
            st.session_state["k3"] = None
            st.session_state["k4"] = None
            st.session_state["k5"] = None
            st.session_state["k6"] = None
            try:
                with st.spinner("Krok 1/2 — Odczytuję dokument (OCR)..."):
                    main_doc, aux_docs = process_files(uploaded_files, secrets)

                # Automatyczna ekstrakcja AI — jeśli klucz Anthropic dostępny
                _api_key = secrets.get("ANTHROPIC_API_KEY", "")
                if _api_key and main_doc.raw_text:
                    with st.spinner("Krok 2/2 — Wyciągam dane przez AI (Claude Haiku)..."):
                        _ai_result = _ai_extract_fields(main_doc.raw_text, _api_key)
                    if _ai_result:
                        if _ai_result.get("sygnatura"):
                            main_doc.sygnatura = _ai_result["sygnatura"]
                        if _ai_result.get("sad_organ"):
                            main_doc.sad_organ = _ai_result["sad_organ"]
                        if _ai_result.get("powod"):
                            main_doc.powod = _ai_result["powod"]
                        if _ai_result.get("pozwany"):
                            main_doc.pozwany = _ai_result["pozwany"]
                        if _ai_result.get("termin_dni"):
                            try:
                                main_doc.deadline_days = int(_ai_result["termin_dni"])
                            except (ValueError, TypeError):
                                pass
                        if _ai_result.get("kwota_zl"):
                            try:
                                main_doc.amount = float(_ai_result["kwota_zl"])
                                main_doc.k7_code = _compute_k7_code(main_doc.amount)
                            except (ValueError, TypeError):
                                pass

                st.session_state["doc_prefill"] = main_doc
                st.session_state["doc_aux"] = aux_docs
                st.session_state["_last_uploaded_names"] = frozenset(
                    f.name for f in uploaded_files
                )
                st.rerun()
            except Exception as e:
                st.error(f"Błąd analizy dokumentu: {e}")

if "doc_prefill" in st.session_state:
    prefill: ProcessedDocument = st.session_state["doc_prefill"]
    aux_docs: list[ProcessedDocument] = st.session_state.get("doc_aux", [])
    _show_doc_summary(prefill, aux_docs)

    # Bramka art. 299 KSH — tylko gdy pozwany jest osobą fizyczną (nie spółką).
    # Dodatkowy warunek: sprawdzamy wyciągnięte pole pozwany — gdy zawiera formę spółkową,
    # nie pokazujemy bramki (dokument może mieć błędny kod lub być mieszanym PDF).
    _SPOLKA_FORMS = ("sp. z o.o.", "spółka z o.", "s.a.", "spółka akcyjna",
                     "sp. k.", "sp. j.", "s.k.a.", "spółka komandytowa",
                     "spółka jawna", "sp. z o. o.")
    _pozwany_lower = (prefill.pozwany or "").lower()
    _pozwany_is_company = any(f in _pozwany_lower for f in _SPOLKA_FORMS)
    _person_doc = (prefill.doc_type_code.endswith("_CZLONEK_ZARZADU")
                   and not _pozwany_is_company)
    if _person_doc:
        _gate = st.session_state.get("_art299_gate")
        if _gate is None:
            st.divider()
            st.markdown("### Potwierdzenie zakresu sprawy")
            st.info(
                "Dokument wskazuje, że pozwanym jest **osoba fizyczna**. "
                "Kalkulator KRS Guard służy wyłącznie do oceny ryzyka "
                "w sprawach o **odpowiedzialność członka zarządu spółki (art. 299 KSH)**."
            )
            st.markdown(
                "**Czy sprawa, której dotyczy ten dokument, wynika "
                "z odpowiedzialności za zobowiązania spółki z tytułu "
                "pełnienia funkcji członka zarządu?**"
            )
            _col1, _col2 = st.columns(2)
            with _col1:
                if st.button("Tak — sprawa dotyczy art. 299 KSH", type="primary", use_container_width=True):
                    st.session_state["_art299_gate"] = "yes"
                    st.rerun()
            with _col2:
                if st.button("Nie — to inna sprawa", use_container_width=True):
                    st.session_state["_art299_gate"] = "no"
                    st.rerun()
            st.stop()
        elif _gate == "no":
            st.divider()
            st.warning(
                "Kalkulator KRS Guard ocenia ryzyko wyłącznie w sprawach "
                "o odpowiedzialność członka zarządu spółki (art. 299 KSH). "
                "Jeśli sprawa dotyczy innego rodzaju zobowiązania osobistego, "
                "skonsultuj się bezpośrednio z prawnikiem."
            )
            st.stop()
        # _gate == "yes" → kontynuuj normalnie

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
    from calendar_utils import compute_deadline_date, is_working_day
    deadline_date = compute_deadline_date(delivery_date, int(deadline_days))
    days_exact = (deadline_date - date.today()).days
    _was_shifted = not is_working_day(
        delivery_date + timedelta(days=int(deadline_days))
    )
    _shift_note = " *(przesunięty z dnia wolnego — art. 115 KPC)*" if _was_shifted else ""
    st.info(
        f"Termin upływa **{deadline_date.strftime('%d.%m.%Y')}**{_shift_note} "
        f"— pozostało **{days_exact} dni** kalendarzowych."
    )
    st.caption(
        "Do tego terminu wliczają się soboty, niedziele i dni świąteczne. "
        "Jeśli ostatni dzień wypada w dzień wolny, termin przesuwa się na "
        "następny dzień roboczy (art. 115 KPC)."
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

    _prefill = st.session_state.get("doc_prefill")
    state = {
        **answers,
        "EPU": epu,
        "DOC_TYPE": _prefill.doc_type_code if _prefill else "",
    }

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

    # Jeśli OCR zidentyfikował PISMO_PROCESOWE_SADOWE — nadpisz doc_type i tekst scenariusza.
    # Scenariusz pochodzi z DOKUMENT_NIEUSTALONY_PRAWNY (K1_INNE_NIE_WIEM), więc jego
    # treść trzeba tu zastąpić, by nie mówiło "rodzaj pisma nie ustalony".
    if state.get("DOC_TYPE") == "PISMO_PROCESOWE_SADOWE":
        doc_type = "PISMO_PROCESOWE_SADOWE"
        scenario["user_risk_explanation_base"] = (
            "Dokumentacja wskazuje na toczące się postępowanie sądowe. "
            "Bez dostępu do pełnych akt sprawy trudno ocenić bieżącą pozycję procesową — "
            "znane są sygnatura sprawy i kwota roszczenia, ale nie historia i pisma obu stron."
        )
        scenario["user_practical_meaning_base"] = (
            "W praktyce kluczowe jest zebranie kompletnej dokumentacji sprawy: pozwu, "
            "wcześniejszych pism obu stron, odpowiedzi na pozew i zarządzeń sądu. "
            "Dopiero pełne akta umożliwią ocenę pozycji procesowej i dostępnych kroków."
        )
        scenario["user_next_step_base"] = (
            "zebrać pełną dokumentację sprawy i przekazać do analizy w ramach Audytu 48h"
        )

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
    st.header("Ocena ryzyka")

    # Wykrycie "zagubionego klienta" — brak daty + brak statusu + brak celu
    _lost_client = (
        answers.get("K2A") == "K2A_DELIVERY_DATE_UNKNOWN"
        and answers.get("K4") in ("K4_BOARD_UNKNOWN", "", None)
        and answers.get("K6") in ("K6_GOAL_UNKNOWN", "", None)
    )
    if _lost_client:
        _deadline_hint = {
            "K2_DAYS_LEFT_0_3": "3 dni",
            "K2_DAYS_LEFT_4_7": "7 dni",
            "K2_DAYS_LEFT_8_14": "14 dni",
        }.get(answers.get("K2", ""), "")
        _time_pressure = (
            f" Z dokumentu wynika termin {_deadline_hint} — jeśli pismo leży "
            f"kilka dni, czas może być bardzo krótki."
            if _deadline_hint else ""
        )
        st.warning(
            "**⚠️ Nie znasz jeszcze kluczowych faktów tej sprawy.**\n\n"
            f"Nie wiesz kiedy dokument został Ci doręczony — a od tej daty biegnie termin "
            f"na reakcję.{_time_pressure} "
            "Nie wiesz też jaki jest Twój status prawny w zarządzie — "
            "a to wpływa bezpośrednio na zakres Twojej odpowiedzialności.\n\n"
            "**Co zrobić TERAZ (zanim cokolwiek innego):**\n"
            "1. Sprawdź datę na kopercie lub potwierdzeniu odbioru — to wyznacza termin.\n"
            "2. Sprawdź w KRS czy widniejesz jako aktualny lub były członek zarządu.\n"
            "3. Skontaktuj się z nami — **Audyt 48h** pozwoli ustalić te fakty i ułożyć "
            "plan działania zanim termin minie."
        )

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
    if st.button("🔄 Wyczyść kalkulator i wprowadź nowe dane", use_container_width=True):
        reset_calculator()
        st.rerun()

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

            # ── Analiza dokumentu (Etap 2) ────────────────────────────────
            if prefill:
                st.subheader("Analiza dokumentu (Etap 2)")
                c1, c2 = st.columns(2)
                c1.write(f"**Silnik OCR:** `{prefill.ocr_engine}`")
                c2.write(f"**Jakość OCR:** `{prefill.ocr_quality}`")
                c1.write(f"**Pewność klasyfikacji:** {prefill.classifier_confidence:.2f}")
                c2.write(f"**Pewność ogólna:** {prefill.confidence:.2f}")
                c1.write(f"**Typ dokumentu:** `{prefill.doc_type_code}`")
                c2.write(f"**Kod K1:** `{prefill.k1_code}`")
                c1.write(f"**Zakres stron:** {prefill.page_range}")
                c2.write(f"**Status:** `{prefill.status}`")
                st.json({
                    "epu": prefill.epu,
                    "delivery_date": str(prefill.delivery_date),
                    "deadline_days": prefill.deadline_days,
                    "amount": prefill.amount,
                    "k7_code": prefill.k7_code,
                    "sygnatura": prefill.sygnatura,
                    "sad_organ": prefill.sad_organ,
                    "powod": prefill.powod,
                    "pozwany": prefill.pozwany,
                    "addressee": prefill.addressee,
                })
                if prefill.ocr_notes:
                    st.info(f"ℹ️ Notatki OCR: {prefill.ocr_notes}")
                st.markdown("**Surowy tekst OCR (pierwsze 3000 znaków):**")
                st.code(prefill.raw_text[:3000] if prefill.raw_text else "(brak)", language=None)
                if prefill.splitter_segments:
                    st.markdown("**Segmentacja stron (doc_splitter):**")
                    for _s in prefill.splitter_segments:
                        _sp = _s.get("pages", [])
                        _sp_txt = f"str. {_sp[0]}–{_sp[-1]}" if len(_sp) > 1 else (f"str. {_sp[0]}" if _sp else "?")
                        st.write(f"- {_sp_txt} → `{_s.get('doc_type','?')}` ({_s.get('label','?')}) [{_s.get('role','?')}]")
                _panel_aux = st.session_state.get("doc_aux", [])
                for _i, _aux in enumerate(_panel_aux, 1):
                    st.markdown(f"**Dokument pomocniczy {_i}: `{_aux.doc_type_code}`**")
                    st.write(f"Silnik: `{_aux.ocr_engine}` | Jakość: `{_aux.ocr_quality}` | Strony: {_aux.page_range}")
                    if _aux.ocr_notes:
                        st.info(f"ℹ️ {_aux.ocr_notes}")
                    st.code(_aux.raw_text[:3000] if _aux.raw_text else "(brak)", language=None)
                st.divider()

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
