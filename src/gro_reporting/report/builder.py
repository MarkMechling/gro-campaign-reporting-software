"""Data -> Template-Context -> HTML -> PDF."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..config import ClientConfig, RoasMode
from ..formatting import (
    format_currency,
    format_currency_suffix,
    format_date_short,
    format_month_year,
    format_number,
    format_percent,
    format_roas,
)

CONV_NAME_MAP = {
    "Google PMAX Kampagnen": "PMAX",
}
from ..models import ReportData
from .renderer import render_pdf

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class ReportBuilder:
    def __init__(self, config: ClientConfig, data: ReportData):
        self.config = config
        self.data = data
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        self.env.filters["fmt_number"] = format_number
        self.env.filters["fmt_currency"] = format_currency
        self.env.filters["fmt_percent"] = format_percent
        self.env.filters["fmt_roas"] = format_roas

    def build(self, output_path: Path):
        context = self._build_context()
        css_path = TEMPLATES_DIR / "style.css"
        context["css"] = css_path.read_text(encoding="utf-8")
        template = self.env.get_template("base.html")
        html = template.render(**context)
        render_pdf(html, output_path, base_url=str(TEMPLATES_DIR))

    def _build_context(self) -> dict:
        data = self.data
        config = self.config
        sq = config.status_quo

        date_range = f"{format_date_short(data.date_from)} - {format_date_short(data.date_to)}{data.date_to.year}"
        month_year = format_month_year(data.date_from)
        total_perf = data.total_performance
        total_conv = data.total_conversions

        perf_rows = []
        for ch in data.channels:
            perf_rows.append({
                "name": ch.name,
                "impressions": format_number(ch.performance.impressions),
                "clicks": format_number(ch.performance.clicks),
                "ctr": format_percent(ch.performance.ctr),
                "avg_cpc": format_currency(ch.performance.avg_cpc),
                "cost": format_currency(ch.performance.cost),
            })

        perf_total = {
            "name": "GESAMT",
            "impressions": format_number(total_perf.impressions),
            "clicks": format_number(total_perf.clicks),
            "ctr": format_percent(total_perf.ctr),
            "avg_cpc": format_currency(total_perf.avg_cpc),
            "cost": format_currency(total_perf.cost),
        }

        conv_rows = []
        for ch in data.channels:
            conv_rows.append({
                "name": CONV_NAME_MAP.get(ch.name, ch.name),
                "purchases": format_number(ch.conversions.purchases),
                "revenue": format_currency(ch.conversions.revenue),
            })

        merchant_row = None
        if data.merchant_center:
            mc = data.merchant_center
            merchant_row = {
                "name": "Unbezahlter Traffic durch Merchant Center**",
                "purchases": format_number(mc.purchases),
                "revenue": format_currency(mc.revenue),
            }

        conv_total = {
            "name": "GESAMT",
            "purchases": format_number(total_conv.purchases),
            "revenue": format_currency(total_conv.revenue),
        }

        ad_spend, revenue, roas, pmax_roas = self._calc_status_quo()

        perf_summary = (
            f"Mit {format_number(total_perf.impressions)} Impressionen "
            f"konnten wir wertvolle Kontaktpunkte zur Zielgruppe schaffen."
        )
        roas_summary = (
            f"Für jeden investierten Euro in Google Ads "
            f"kommen im Schnitt {format_roas(roas)} € Umsatz zurück."
        )

        cover_image_path = self._resolve_asset(config.cover_image)
        client_logo_path = self._resolve_asset(config.client_logo)
        logo_path = str(ASSETS_DIR / "massiveart-logo.jpg")

        return {
            "client_name": data.client_name,
            "month_year": month_year,
            "date_range": date_range,
            "cover_image": cover_image_path,
            "logo_path": logo_path,
            "client_logo_path": client_logo_path,
            "perf_rows": perf_rows,
            "perf_total": perf_total,
            "perf_summary": perf_summary,
            "conv_rows": conv_rows,
            "merchant_row": merchant_row,
            "conv_total": conv_total,
            "footnotes": sq.footnotes,
            "ad_spend": format_currency_suffix(ad_spend),
            "revenue": format_currency_suffix(revenue),
            "roas": format_roas(roas),
            "pmax_roas": format_roas(pmax_roas),
            "roas_summary": roas_summary,
            "next_steps": sq.next_steps,
        }

    @staticmethod
    def _resolve_asset(path_str: str | None) -> str | None:
        """Asset-Pfad aus der Config aufloesen (relativ zum Projekt-Root)."""
        if not path_str:
            return None
        candidate = Path(path_str)
        if not candidate.is_absolute():
            candidate = Path(__file__).resolve().parent.parent.parent.parent / candidate
        return str(candidate) if candidate.exists() else None

    def _calc_status_quo(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        data = self.data
        sq = self.config.status_quo

        if sq.roas_mode == RoasMode.GOOGLE_ONLY:
            ad_spend = data.google_ad_spend()
            revenue = data.google_revenue()
        elif sq.roas_mode == RoasMode.GOOGLE_PLUS_MERCHANT:
            ad_spend = data.google_ad_spend()
            revenue = data.google_revenue()
            if data.merchant_center:
                revenue += data.merchant_center.revenue
        else:
            ad_spend = data.total_performance.cost
            revenue = data.total_conversions.revenue

        roas = (revenue / ad_spend).quantize(Decimal("0.01")) if ad_spend else Decimal("0")

        pmax = next((c for c in data.channels if c.name == "Google PMAX Kampagnen"), None)
        if pmax and pmax.performance.cost:
            pmax_roas = (pmax.conversions.revenue / pmax.performance.cost).quantize(Decimal("0.01"))
        else:
            pmax_roas = Decimal("0")

        return ad_spend, revenue, roas, pmax_roas
