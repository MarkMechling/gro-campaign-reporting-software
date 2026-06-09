"""Test-PDF-Generierung mit den exakten Daten aus der Referenz-PDF."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from gro_reporting.config import ClientConfig, ClientInfo, StatusQuoConfig
from gro_reporting.models import (
    ChannelConversions,
    ChannelData,
    ChannelPerformance,
    ReportData,
)
from gro_reporting.report.builder import ReportBuilder

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _reference_data() -> ReportData:
    return ReportData(
        client_name="Cafe-Konditorei Fürst",
        slug="fuerst",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 4, 8),
        channels=[
            ChannelData(
                name="Google PMAX Kampagnen",
                performance=ChannelPerformance(
                    impressions=338544,
                    clicks=11923,
                    cost=Decimal("1347.27"),
                ),
                conversions=ChannelConversions(
                    purchases=152,
                    revenue=Decimal("4097.84"),
                ),
            ),
            ChannelData(
                name="Suchanzeigen",
                performance=ChannelPerformance(
                    impressions=36807,
                    clicks=10142,
                    cost=Decimal("1021.69"),
                ),
                conversions=ChannelConversions(
                    purchases=306,
                    revenue=Decimal("4651.70"),
                ),
            ),
            ChannelData(
                name="Meta Anzeigen",
                performance=ChannelPerformance(
                    impressions=408834,
                    clicks=8544,
                    cost=Decimal("1429.00"),
                ),
                conversions=ChannelConversions(
                    purchases=4,
                    revenue=Decimal("62.30"),
                ),
            ),
        ],
        merchant_center=ChannelConversions(
            purchases=4,
            revenue=Decimal("283.64"),
        ),
    )


def _reference_config() -> ClientConfig:
    return ClientConfig(
        client=ClientInfo(name="Cafe-Konditorei Fürst", slug="fuerst"),
        status_quo=StatusQuoConfig(
            min_order_value=50.0,
            roas_mode="google_only",
            next_steps=(
                "Strategie: Optimierung auf Ziel-ROAS (Target ROAS)\n"
                "Zielwert: 5-7,5 (Sicheres Wachstum bei hohem Volumen)"
            ),
            footnotes=[
                "*Eventstracking seit 30.03. live",
                "**Merchant Center seit 05.03. live",
            ],
        ),
    )


def test_reference_pdf_generation():
    data = _reference_data()
    config = _reference_config()

    assert data.total_performance.impressions == 784185
    assert data.total_performance.clicks == 30609
    assert data.total_performance.cost == Decimal("3797.96")

    assert data.total_conversions.purchases == 466
    assert data.google_ad_spend() == Decimal("2368.96")
    assert data.google_purchases() == 458

    builder = ReportBuilder(config, data)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "test_reference.pdf"
    builder.build(output_path)
    assert output_path.exists()
    assert output_path.stat().st_size > 0
