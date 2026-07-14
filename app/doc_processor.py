# -*- coding: utf-8 -*-
"""Orkiestrator etapu 2: łączy ingestion → OCR → ekstrakcję → klasyfikację → selekcję."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta

from doc_ingestion import extract_pages, PageDict
from doc_ocr import ocr_with_fallback
from doc_extractor import extract_fields, _amount_to_k7
from ai_extractor import extract_fields_ai
from doc_classifier import classify_document
from doc_selector import select_main_document
from ocr_cleanup import clean_ocr_text
from calendar_utils import compute_deadline_date

# Mapowanie doc_type_code → kod K1 formularza
_DOC_TYPE_TO_K1: dict[str, str] = {
    "POZEW_CZLONEK_ZARZADU":              "K1_POZEW_CZLONEK_ZARZADU",
    "POZEW_SPOLKA":                       "K1_POZEW_SPOLKA",
    "NAKAZ_CZLONEK_ZARZADU":              "K1_NAKAZ_CZLONEK_ZARZADU",
    "NAKAZ_SPOLKA":                       "K1_NAKAZ_SPOLKA",
    "EPU_NAKAZ_SPOLKA":                   "K1_NAKAZ_SPOLKA",
    "EPU_POZEW_SPOLKA":                   "K1_POZEW_SPOLKA",
    "EPU_POZEW_CZLONEK_ZARZADU":          "K1_POZEW_CZLONEK_ZARZADU",
    "EPU_NAKAZ_CZLONEK_ZARZADU":          "K1_NAKAZ_CZLONEK_ZARZADU",
    "WEZWANIE_SADOWE_CZLONEK_ZARZADU":    "K1_WEZWANIE_SADOWE_CZLONEK_ZARZADU",
    "WEZWANIE_SADOWE_SPOLKA":             "K1_WEZWANIE_SADOWE_SPOLKA",
    "DECYZJA_ZUS_CZLONEK_ZARZADU":        "K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
    "DECYZJA_US_CZLONEK_ZARZADU":         "K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
    "ORGAN_PUBLICZNY_CZLONEK_ZARZADU":    "K1_ORGAN_PUBLICZNY_CZLONEK_ZARZADU",
    "PISMO_PROCESOWE_SADOWE":             "K1_INNE_NIE_WIEM",
    # (05.07.2026) Pisma komornicze mają własną opcję K1 (CSV 08) i własne
    # scenariusze (CSV 12) — wcześniej spadały na K1_INNE_NIE_WIEM, przez co
    # ocena ryzyka twierdziła "nie wiadomo jakiego rodzaju jest pismo".
    "PISMO_KOMORNIK_SPOLKA":              "K1_PISMO_KOMORNIK_SPOLKA",
    "PISMO_KOMORNIK_CZLONEK_ZARZADU":     "K1_PISMO_KOMORNIK_CZLONEK_ZARZADU",
    # (06.07.2026) Przedsądowe wezwanie do zapłaty do członka zarządu (powołuje
    # się na art. 299 KSH) dostało własną opcję K1 (CSV 08) i scenariusze
    # (CSV 12, BASE_210-224) — wcześniej spadało na K1_INNE_NIE_WIEM, przez co
    # ocena ryzyka twierdziła "rodzaj pisma nie został ustalony" mimo
    # poprawnej klasyfikacji. Wariant SPOLKA celowo NIE ma tu wpisu — zwykła
    # faktura do spółki dostaje w app.py odrębny mechanizm ostrzeżenia
    # (_SPOLKA_OUT_OF_SCOPE_TYPES), a nie ścieżkę K1/scenariusza.
    "WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU": "K1_WEZWANIE_PRZEDSADOWE_CZLONEK_ZARZADU",
    # (07.07.2026) Wyrok zaoczny — lekka integracja (decyzja produktowa):
    # zamiast własnej kategorii scenariuszy w CSV 12, scoring i tekst scenariusza
    # są reużyte z NAKAZ_SPOLKA/NAKAZ_CZLONEK_ZARZADU (ten sam 2-tygodniowy
    # termin na sprzeciw) — patrz scenario_selector.py _K1_TO_DOC_TYPE i app.py
    # (nadpisuje fragmenty tekstu scenariusza, żeby poprawnie mówiły o wyroku
    # zaocznym, nie o nakazie zapłaty). (14.07.2026) Kod K1 dostał WŁASNE
    # wartości K1_WYROK_ZAOCZNY_* (zamiast K1_NAKAZ_*) — poprzednie reużycie
    # kodu K1 nakazu wyciekało do UI: Krok 1 formularza pre-zaznaczał etykietę
    # "Nakaz zapłaty (spółka)", a panel techniczny pokazywał "Kod K1:
    # K1_NAKAZ_SPOLKA" dla dokumentu poprawnie rozpoznanego i wyświetlanego
    # jako "Wyrok zaoczny (spółka)" — zgłoszenie użytkownika na żywym teście.
    # Scoring (CSV 09) i mapowanie zwrotne do scenariusza (scenario_selector.py)
    # dla nowych kodów są identyczne jak dla NAKAZ_*, więc treść wyniku się nie
    # zmienia — zmienia się tylko widoczna etykieta/kod w Kroku 1 i panelu.
    "WYROK_ZAOCZNY_SPOLKA":                "K1_WYROK_ZAOCZNY_SPOLKA",
    "WYROK_ZAOCZNY_CZLONEK_ZARZADU":       "K1_WYROK_ZAOCZNY_CZLONEK_ZARZADU",
}

# Mapowanie liczby dni na bucket K2
def _days_to_k2(days: int) -> str:
    if days <= 0:
        return "K2_DAYS_LEFT_0_3"
    if days <= 3:
        return "K2_DAYS_LEFT_0_3"
    if days <= 7:
        return "K2_DAYS_LEFT_4_7"
    if days <= 14:
        return "K2_DAYS_LEFT_8_14"
    return "K2_DAYS_LEFT_ABOVE_14"


@dataclass
class ProcessedDocument:
    doc_type_code: str
    k1_code: str
    epu: bool
    delivery_date: date | None
    deadline_days: int | None
    days_left: int | None
    k2_code: str
    days_left_exact: int | None
    amount: float | None
    k7_code: str
    addressee: str | None
    confidence: float
    ocr_quality: str          # "HIGH" | "LOW"
    ocr_engine: str           # "azure" | "tesseract" | "claude" | "native" | "none"
    raw_text: str
    status: str               # "GLOWNY" | "POMOCNICZY" | ...
    deadline_date: date | None = None
    page_range: tuple[int, int] = field(default_factory=lambda: (1, 1))
    classifier_confidence: float = 0.0
    sygnatura: str | None = None
    sad_organ: str | None = None
    powod: str | None = None
    pozwany: str | None = None
    ocr_notes: str = ""
    file_ext: str = ""
    splitter_segments: list | None = None  # DEBUG: segmenty ze splitter dla panelu
    # (05.07.2026) Etykieta segmentu ze splittera (np. "Zajęcie rachunku
    # bankowego") — UI dopisuje ją w "Zestawieniu dokumentów", żeby odróżnić
    # od siebie pisma komornicze tej samej kategorii (wcześniej 7 pism jednej
    # egzekucji wyświetlało się jako 7x identyczne "Pismo komornicze (spółka)").
    splitter_label: str = ""


def _build_candidate_dict(
    text: str,
    ocr_quality: str,
    ocr_engine: str,
    ocr_notes: str,
    file_ext: str,
    page_range: tuple[int, int],
    api_key: str = "",
    splitter_kind: str = "",
) -> dict:
    """Buduje słownik kandydata z przetworzonego tekstu dokumentu.

    Ekstrakcja AI (Claude Haiku) jest GŁÓWNĄ ścieżką dla powód/pozwany/
    sygnatura/sąd/kwota/termin/adresat/epu — regex (extract_fields) to tani
    fallback użyty w całości, gdy brak klucza API, oraz pole-po-polu, gdy AI
    nie zwróciła wartości dla danego pola. Scalenie dzieje się PRZED
    classify_document(), więc "adresat" od AI (bardziej odporny na nowe
    odmiany gramatyczne niż regexowe _ADRESAT) zasila bonus klasyfikacyjny
    dla KAŻDEGO segmentu w paczce, nie tylko głównego dokumentu.
    """
    fields = extract_fields(text)
    ai_fields = extract_fields_ai(text, api_key)
    if ai_fields:
        if ai_fields.get("sygnatura"):
            fields["sygnatura"] = ai_fields["sygnatura"]
        if ai_fields.get("sad_organ"):
            fields["sad_organ"] = ai_fields["sad_organ"]
        if ai_fields.get("powod"):
            fields["powod"] = ai_fields["powod"]
        if ai_fields.get("pozwany"):
            fields["pozwany"] = ai_fields["pozwany"]
        if ai_fields.get("adresat") in ("czlonek_zarzadu", "spolka", "organ"):
            fields["adresat"] = ai_fields["adresat"]
            fields["adresat_confidence"] = max(fields.get("adresat_confidence", 0.0), 0.9)
        if ai_fields.get("epu") is not None:
            fields["epu"] = bool(ai_fields["epu"])
        if ai_fields.get("termin_dni") is not None:
            try:
                fields["deadline_days"] = int(ai_fields["termin_dni"])
            except (ValueError, TypeError):
                pass
        if ai_fields.get("kwota_zl") is not None:
            try:
                fields["amount"] = float(ai_fields["kwota_zl"])
                fields["k7_code"] = _amount_to_k7(fields["amount"])
            except (ValueError, TypeError):
                pass
        # Werdykt AI "czy to w ogóle pismo prawne" — classify_document() używa
        # go (w koniunkcji ze słabym wynikiem słów kluczowych) do wykrycia
        # dokumentów niezwiązanych ze sprawą (przelew, faktura, wyciąg itp.).
        if ai_fields.get("czy_pismo_prawne") is not None:
            fields["czy_pismo_prawne"] = bool(ai_fields["czy_pismo_prawne"])
        # (05.07.2026) Kategoria pisma wg AI — classify_document() używa jej
        # jako bonusu (+15, tylko w koniunkcji z trafieniem tekstowym) i weta
        # bonusu POZEW. Odpowiedź na meta-problem "nowy rodzaj dokumentu =
        # nowa pułapka regexowa": AI rozumie rodzaj pisma niezależnie od
        # konkretnego układu tekstu.
        if ai_fields.get("rodzaj_pisma"):
            fields["rodzaj_pisma"] = str(ai_fields["rodzaj_pisma"])

    # Kind segmentu ze splittera (04.07.2026) — deterministyczny sygnał
    # oparty na nagłówku strony (kancelaria komornicza itp.); classify_document
    # używa go, żeby segmenty boilerplate'u pism komorniczych (pouczenia
    # k.p.c. cytujące "nakaz zapłaty") nie klasyfikowały się jako NAKAZ/POZEW.
    if splitter_kind:
        fields["splitter_kind"] = splitter_kind

    doc_type, clf_conf = classify_document(text, fields)
    k1_code = _DOC_TYPE_TO_K1.get(doc_type, "K1_INNE_NIE_WIEM")

    days_left: int | None = None
    deadline_date_val: date | None = None
    k2_code = "K2_DAYS_LEFT_UNKNOWN"
    if fields["delivery_date"] and fields["deadline_days"]:
        deadline_date_val = compute_deadline_date(
            fields["delivery_date"], fields["deadline_days"]
        )
        days_left = (deadline_date_val - date.today()).days
        k2_code = _days_to_k2(days_left)

    confidence = round(
        clf_conf * 0.6
        + (fields["adresat_confidence"] * 0.2)
        + (0.2 if fields["delivery_date"] else 0.0),
        3,
    )

    return {
        "doc_type_code": doc_type,
        "k1_code": k1_code,
        "epu": fields["epu"],
        "delivery_date": fields["delivery_date"],
        "deadline_days": fields["deadline_days"],
        "days_left": days_left,
        "k2_code": k2_code,
        "days_left_exact": days_left,
        "amount": fields["amount"],
        "k7_code": fields["k7_code"],
        "addressee": fields["adresat"],
        "confidence": confidence,
        "ocr_quality": ocr_quality,
        "ocr_engine": ocr_engine,
        "raw_text": text,
        "classifier_confidence": clf_conf,
        "page_range": page_range,
        "sygnatura": fields.get("sygnatura"),
        "sad_organ": fields.get("sad_organ"),
        "powod": fields.get("powod"),
        "pozwany": fields.get("pozwany"),
        "ocr_notes": ocr_notes,
        "file_ext": file_ext,
        "deadline_date": deadline_date_val,
    }


def _process_single_doc(
    pages: list[PageDict],
    raw_bytes: bytes,
    ext: str,
    secrets: dict,
    file_ext: str = "",
) -> list[dict]:
    """
    Przetwarza jeden plik → lista kandydatów.
    Zwraca N > 1 elementów gdy PDF zawiera wiele logicznych dokumentów.
    """
    from doc_splitter import detect_documents_by_pages

    has_scans = any(p["is_scan"] for p in pages)

    ocr_notes = ""
    if has_scans:
        full_text, ocr_confidence, ocr_engine, ocr_notes = ocr_with_fallback(
            pages, raw_bytes, ext, secrets
        )
    else:
        # Natywny PDF — dodaj separatory stron (wymagane przez segmentację)
        full_text = "\n".join(
            f"--- STRONA {p['page_num']} ---\n{p['text']}"
            for p in pages if p["text"]
        )
        ocr_confidence = 1.0
        ocr_engine = "native"

    full_text = full_text.strip()
    if ocr_engine != "native":
        full_text = clean_ocr_text(full_text)
    ocr_quality = "LOW" if ocr_confidence < 0.75 else "HIGH"

    # Próba segmentacji na logiczne dokumenty
    segments = detect_documents_by_pages(full_text)
    api_key = secrets.get("ANTHROPIC_API_KEY", "")

    if segments:
        # Wiele logicznych dokumentów — process each segment (text already OCR'd)
        candidates = []
        for seg in segments:
            seg_text = seg["text"]
            pages_in_seg = seg.get("pages", [])
            p_start = pages_in_seg[0] if pages_in_seg else pages[0]["page_num"]
            p_end   = pages_in_seg[-1] if pages_in_seg else pages[-1]["page_num"]
            cand = _build_candidate_dict(
                seg_text, ocr_quality, ocr_engine, ocr_notes, file_ext, (p_start, p_end),
                api_key=api_key,
                splitter_kind=seg.get("doc_type", ""),
            )
            # Zachowaj info o segmentacji dla panelu diagnostycznego
            cand["splitter_doc_type"] = seg.get("doc_type", "?")
            cand["splitter_label"]    = seg.get("label", "?")
            cand["splitter_role"]     = seg.get("role", "?")
            candidates.append(cand)
        # Dodaj listę segmentów do pierwszego kandydata (do wyświetlenia w panelu).
        # "final_type" to wynik classify_document() dla TEGO SAMEGO segmentu (cand,
        # sparowany po indeksie z segments) — bez tego panel "Segmentacja stron"
        # pokazywał tylko surowy typ ze splittera (sprzed klasyfikacji), co mogło
        # nie zgadzać się z typem finalnie użytym w "Zestawieniu dokumentów" i
        # "Dokumencie pomocniczym N".
        if candidates:
            candidates[0]["splitter_segments"] = [
                {
                    "pages": seg.get("pages", []),
                    "doc_type": seg.get("doc_type", "?"),
                    "label": seg.get("label", "?"),
                    "role": seg.get("role", "?"),
                    "final_type": cand.get("doc_type_code", "?"),
                }
                for seg, cand in zip(segments, candidates)
            ]
        return candidates

    # Plik jednolity — klasyfikuj cały tekst
    return [_build_candidate_dict(
        full_text, ocr_quality, ocr_engine, ocr_notes, file_ext,
        (pages[0]["page_num"], pages[-1]["page_num"]),
        api_key=api_key,
    )]


def process_files(
    uploaded_files,
    secrets: dict | None = None,
) -> tuple[ProcessedDocument, list[ProcessedDocument]]:
    """
    Główna funkcja etapu 2. Przyjmuje listę UploadedFile ze Streamlit.
    Zwraca (dokument_główny, [dokumenty_pomocnicze]) jako ProcessedDocument.
    secrets: słownik z kluczami AZURE_DI_KEY, AZURE_DI_ENDPOINT, ANTHROPIC_API_KEY.
    """
    if secrets is None:
        secrets = {}
    all_candidates: list[dict] = []

    for uf in uploaded_files:
        raw_bytes = uf.read()
        uf.seek(0)
        ext = uf.name.rsplit(".", 1)[-1].lower()
        pages = extract_pages(uf)
        if pages:
            candidates = _process_single_doc(pages, raw_bytes, ext, secrets, file_ext=ext)
            all_candidates.extend(candidates)

    if not all_candidates:
        # Fallback — pusty dokument nieustalony
        empty = ProcessedDocument(
            doc_type_code="DOKUMENT_NIEUSTALONY_PRAWNY",
            k1_code="K1_INNE_NIE_WIEM",
            epu=False,
            delivery_date=None,
            deadline_days=None,
            days_left=None,
            k2_code="K2_DAYS_LEFT_UNKNOWN",
            days_left_exact=None,
            amount=None,
            k7_code="K7_AMOUNT_UNKNOWN",
            addressee=None,
            confidence=0.0,
            ocr_quality="LOW",
            ocr_engine="none",
            raw_text="",
            status="GLOWNY",
        )
        return empty, []

    main_dict, aux_dicts = select_main_document(all_candidates)

    # Przepisz splitter_segments do main_dict (może być w dowolnym kandydacie)
    _segs = next((c["splitter_segments"] for c in all_candidates if c.get("splitter_segments")), None)
    if _segs:
        main_dict["splitter_segments"] = _segs

    def to_pd(d: dict) -> ProcessedDocument:
        _doc_type = d.get("doc_type_code", "DOKUMENT_NIEUSTALONY_PRAWNY")
        return ProcessedDocument(
            doc_type_code=_doc_type,
            k1_code=_DOC_TYPE_TO_K1.get(_doc_type, d.get("k1_code", "K1_INNE_NIE_WIEM")),
            epu=d.get("epu", False),
            delivery_date=d.get("delivery_date"),
            deadline_days=d.get("deadline_days"),
            days_left=d.get("days_left"),
            k2_code=d.get("k2_code", "K2_DAYS_LEFT_UNKNOWN"),
            days_left_exact=d.get("days_left_exact"),
            amount=d.get("amount"),
            k7_code=d.get("k7_code", "K7_AMOUNT_UNKNOWN"),
            addressee=d.get("addressee"),
            confidence=d.get("confidence", 0.0),
            ocr_quality=d.get("ocr_quality", "HIGH"),
            ocr_engine=d.get("ocr_engine", "none"),
            raw_text=d.get("raw_text", ""),
            status=d.get("status", "GLOWNY"),
            page_range=d.get("page_range", (1, 1)),
            classifier_confidence=d.get("classifier_confidence", 0.0),
            sygnatura=d.get("sygnatura"),
            sad_organ=d.get("sad_organ"),
            powod=d.get("powod"),
            pozwany=d.get("pozwany"),
            ocr_notes=d.get("ocr_notes", ""),
            file_ext=d.get("file_ext", ""),
            deadline_date=d.get("deadline_date"),
            splitter_segments=d.get("splitter_segments"),
            splitter_label=d.get("splitter_label", ""),
        )

    return to_pd(main_dict), [to_pd(d) for d in aux_dicts]
