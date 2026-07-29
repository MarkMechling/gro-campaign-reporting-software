"""Data -> Template-Context -> HTML -> PDF."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..config import GRO_ROOT, ClientConfig
from ..formatting import (
    currency_symbol,
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
from ..models import META_CHANNEL, ReportData
from .renderer import render_pdf

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


class ReportBuilder:
    def __init__(self, config: ClientConfig, data: ReportData):
        self.config = config
        self.data = data
        self.currency = config.currency
        self.env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
        self.env.filters["fmt_number"] = format_number
        self.env.filters["fmt_currency"] = self._fmt_currency
        self.env.filters["fmt_percent"] = format_percent
        self.env.filters["fmt_roas"] = format_roas

    def _fmt_currency(self, n) -> str:
        return format_currency(n, currency=self.currency)

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
                "avg_cpc": self._fmt_currency(ch.performance.avg_cpc),
                "cost": self._fmt_currency(ch.performance.cost),
            })

        perf_total = {
            "name": "GESAMT",
            "impressions": format_number(total_perf.impressions),
            "clicks": format_number(total_perf.clicks),
            "ctr": format_percent(total_perf.ctr),
            "avg_cpc": self._fmt_currency(total_perf.avg_cpc),
            "cost": self._fmt_currency(total_perf.cost),
        }

        conv_rows = []
        for ch in data.channels:
            conv_rows.append({
                "name": CONV_NAME_MAP.get(ch.name, ch.name),
                "purchases": format_number(ch.conversions.purchases),
                "revenue": self._fmt_currency(ch.conversions.revenue),
            })

        conv_total = {
            "name": "GESAMT",
            "purchases": format_number(total_conv.purchases),
            "revenue": self._fmt_currency(total_conv.revenue),
        }

        # Konfigurierte Conversion-Gruppen ersetzen die Purchase/Umsatz-Tabelle
        conv_group_labels = data.group_labels
        # Key "cells" statt "values": row.values waere in Jinja2 die dict-Methode
        conv_group_rows = [
            {
                "name": CONV_NAME_MAP.get(ch.name, ch.name),
                "cells": [format_number(ch.groups.get(label, 0)) for label in conv_group_labels],
            }
            for ch in data.channels
        ]
        conv_group_total = {
            "name": "GESAMT",
            "cells": [format_number(v) for v in data.total_groups.values()],
        }

        ad_spend, revenue, roas, pmax_roas = self._calc_status_quo()

        perf_summary = (
            f"Mit {format_number(total_perf.impressions)} Impressionen "
            f"konnten wir wertvolle Kontaktpunkte zur Zielgruppe schaffen."
        )
        invested_unit = {"EUR": "Euro", "CHF": "Franken"}.get(
            self.currency, currency_symbol(self.currency)
        )
        roas_summary = (
            f"Für jeden investierten {invested_unit} in {self._scope_label()} "
            f"kommen im Schnitt {format_roas(roas)} {currency_symbol(self.currency)} Umsatz zurück."
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
            "conv_total": conv_total,
            "conv_group_labels": conv_group_labels,
            "conv_group_rows": conv_group_rows,
            "conv_group_total": conv_group_total,
            "footnotes": sq.footnotes,
            "ad_spend": format_currency_suffix(ad_spend, currency=self.currency),
            # Lead-Kunden (conversion_groups) haben kein Umsatz-Tracking --
            # Umsatz/ROAS auf der Status-Quo-Seite waeren fiktive Nullwerte
            "show_revenue": not conv_group_labels,
            "revenue": format_currency_suffix(revenue, currency=self.currency),
            "roas": format_roas(roas),
            "pmax_roas": format_roas(pmax_roas) if pmax_roas is not None else None,
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
            candidate = GRO_ROOT / candidate
        return str(candidate) if candidate.exists() else None

    def _scope_label(self) -> str:
        """Kanalbezeichnung fuer den ROAS-Satz, abhaengig von den Report-Kanaelen."""
        has_meta = any(c.name == META_CHANNEL for c in self.data.channels)
        has_google = any(c.name != META_CHANNEL for c in self.data.channels)
        if has_google and has_meta:
            return "Google & Meta Ads"
        if has_meta:
            return "Meta Ads"
        return "Google Ads"

    def _calc_status_quo(self) -> tuple[Decimal, Decimal, Decimal, Decimal | None]:
        """ROAS ueber die Kanaele des Reports; PMAX-ROAS nur wenn PMAX enthalten ist."""
        data = self.data

        ad_spend = data.total_performance.cost
        revenue = data.total_conversions.revenue
        roas = (revenue / ad_spend).quantize(Decimal("0.01")) if ad_spend else Decimal("0")

        pmax = next((c for c in data.channels if c.name == "Google PMAX Kampagnen"), None)
        if pmax is None:
            pmax_roas = None
        elif pmax.performance.cost:
            pmax_roas = (pmax.conversions.revenue / pmax.performance.cost).quantize(Decimal("0.01"))
        else:
            pmax_roas = Decimal("0")

        return ad_spend, revenue, roas, pmax_roas
