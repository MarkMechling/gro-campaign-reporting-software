"""GRO Campaign Reporting — Self-Service Web UI (Streamlit).

Start: streamlit run app.py
"""

from __future__ import annotations

import tempfile
from datetime import date, timedelta
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from gro_reporting.config import list_clients, load_client_config
from gro_reporting.models import ChannelScope
from gro_reporting.report.builder import ReportBuilder

load_dotenv()

ASSETS_DIR = Path(__file__).parent / "src" / "gro_reporting" / "assets"

st.set_page_config(
    page_title="GRO Campaign Reporting",
    page_icon=str(ASSETS_DIR / "massiveart-logo.jpg"),
    layout="centered",
)
st.logo(str(ASSETS_DIR / "logo_m_white.png"), size="large")


def last_full_month() -> tuple[date, date]:
    today = date.today()
    last_day = today.replace(day=1) - timedelta(days=1)
    return last_day.replace(day=1), last_day


def month_options(n: int = 24) -> list[tuple[date, date]]:
    """Letzte n vollen Monate, neueste zuerst."""
    options = []
    first, last = last_full_month()
    for _ in range(n):
        options.append((first, last))
        last = first - timedelta(days=1)
        first = last.replace(day=1)
    return options


MONTH_NAMES_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def format_month(d: date) -> str:
    return f"{MONTH_NAMES_DE[d.month - 1]} {d.year}"


@st.cache_resource
def get_storage():
    from gro_reporting.storage.bigquery import BigQueryStorage

    return BigQueryStorage()


st.title("GRO Campaign Reporting")
st.caption("Kampagnen-Report als PDF erstellen — Kunde und Zeitraum wählen.")

slugs = list_clients()
if not slugs:
    st.error("Keine Kunden konfiguriert (Ordner `clients/`).")
    st.stop()

configs = {slug: load_client_config(slug) for slug in slugs}
slug = st.selectbox(
    "Kunde",
    options=slugs,
    format_func=lambda s: configs[s].client.name,
)
config = configs[slug]

SCOPE_LABELS = {
    ChannelScope.GOOGLE: "Google Ads",
    ChannelScope.META: "Meta Ads",
    ChannelScope.ALL: "Kombiniert",
}

scope_options = []
if config.google_ads:
    scope_options.append(ChannelScope.GOOGLE)
if config.meta_ads:
    scope_options.append(ChannelScope.META)
if config.google_ads and config.meta_ads:
    scope_options.append(ChannelScope.ALL)

if len(scope_options) > 1:
    scope = st.radio(
        "Kanäle",
        options=scope_options,
        format_func=lambda s: SCOPE_LABELS[s],
        horizontal=True,
    )
else:
    scope = scope_options[0] if scope_options else ChannelScope.ALL

mode = st.radio("Zeitraum", ["Monat", "Benutzerdefiniert"], horizontal=True)

if mode == "Monat":
    months = month_options()
    selected = st.selectbox(
        "Monat wählen",
        options=months,
        format_func=lambda m: format_month(m[0]),
    )
    date_from, date_to = selected
else:
    default_from, default_to = last_full_month()
    col1, col2 = st.columns(2)
    date_from = col1.date_input("Von", value=default_from, format="DD.MM.YYYY")
    date_to = col2.date_input("Bis", value=default_to, format="DD.MM.YYYY")
    if date_from > date_to:
        st.error("Das Startdatum muss vor dem Enddatum liegen.")
        st.stop()

st.divider()

# --- Datenabdeckung in BigQuery ---
try:
    storage = get_storage()
except RuntimeError as e:
    st.warning(f"BigQuery nicht konfiguriert: {e}")
    st.stop()

total_days = (date_to - date_from).days + 1

try:
    covered = storage.get_coverage(slug, date_from, date_to)
except Exception as e:
    st.error(f"BigQuery-Abfrage fehlgeschlagen: {e}")
    st.stop()

missing = total_days - len(covered)
if missing == 0:
    st.success(f"Daten vollständig: alle {total_days} Tage in BigQuery vorhanden.")
else:
    st.warning(
        f"{missing} von {total_days} Tagen fehlen in BigQuery. "
        f"Bitte zuerst synchronisieren."
    )

col_sync, col_pdf = st.columns(2)

with col_sync:
    if st.button("Daten synchronisieren", use_container_width=True):
        from gro_reporting.sync import sync_client

        with st.spinner("Synchronisiere Daten aus Google Ads und Meta..."):
            try:
                result = sync_client(config, date_from, date_to, storage=storage)
                st.session_state["sync_message"] = result.summary()
                st.rerun()
            except Exception as e:
                st.error(f"Sync fehlgeschlagen: {e}")

if "sync_message" in st.session_state:
    st.info(st.session_state.pop("sync_message"))

with col_pdf:
    if st.button("PDF erstellen", type="primary", use_container_width=True, disabled=missing == total_days):
        with st.spinner("Report wird erstellt..."):
            try:
                report_data = storage.query_report_data(
                    slug,
                    config.client.name,
                    date_from,
                    date_to,
                    conversion_groups=config.conversion_groups,
                ).for_scope(scope)
                builder = ReportBuilder(config, report_data)
                scope_suffix = "" if scope == ChannelScope.ALL else f"_{scope.value}"
                filename = f"{date_from.strftime('%Y-%m')}_{slug}_Kampagnenupdate{scope_suffix}.pdf"
                with tempfile.TemporaryDirectory() as tmpdir:
                    output_path = Path(tmpdir) / filename
                    builder.build(output_path)
                    st.session_state["pdf_bytes"] = output_path.read_bytes()
                    st.session_state["pdf_filename"] = filename
            except Exception as e:
                st.error(f"PDF-Erstellung fehlgeschlagen: {e}")

if "pdf_bytes" in st.session_state:
    st.download_button(
        label=f"{st.session_state['pdf_filename']} herunterladen",
        data=st.session_state["pdf_bytes"],
        file_name=st.session_state["pdf_filename"],
        mime="application/pdf",
        use_container_width=True,
    )
