"""Einheitliche KPI-Datenmodelle fuer alle Kanaele."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, computed_field


class ChannelPerformance(BaseModel):
    impressions: int = 0
    clicks: int = 0
    cost: Decimal = Decimal("0")

    @computed_field
    @property
    def ctr(self) -> Decimal:
        if self.impressions == 0:
            return Decimal("0")
        return (Decimal(self.clicks) / Decimal(self.impressions) * 100).quantize(Decimal("0.01"))

    @computed_field
    @property
    def avg_cpc(self) -> Decimal:
        if self.clicks == 0:
            return Decimal("0")
        return (self.cost / self.clicks).quantize(Decimal("0.01"))


class ChannelConversions(BaseModel):
    purchases: int = 0
    revenue: Decimal = Decimal("0")


class ChannelData(BaseModel):
    name: str
    performance: ChannelPerformance = ChannelPerformance()
    conversions: ChannelConversions = ChannelConversions()


class DailyMetrics(BaseModel):
    report_date: date
    client_slug: str
    channel: str  # "Google PMAX Kampagnen" | "Suchanzeigen" | "Meta Anzeigen" | "merchant_center"
    impressions: int = 0
    clicks: int = 0
    cost: Decimal = Decimal("0")
    purchases: int = 0
    revenue: Decimal = Decimal("0")


class ReportData(BaseModel):
    client_name: str
    slug: str
    date_from: date
    date_to: date
    channels: list[ChannelData] = []
    merchant_center: ChannelConversions | None = None

    @computed_field
    @property
    def total_performance(self) -> ChannelPerformance:
        return ChannelPerformance(
            impressions=sum(c.performance.impressions for c in self.channels),
            clicks=sum(c.performance.clicks for c in self.channels),
            cost=sum(c.performance.cost for c in self.channels),
        )

    @computed_field
    @property
    def total_conversions(self) -> ChannelConversions:
        all_sources = [c.conversions for c in self.channels]
        if self.merchant_center:
            all_sources.append(self.merchant_center)
        return ChannelConversions(
            purchases=sum(s.purchases for s in all_sources),
            revenue=sum(s.revenue for s in all_sources),
        )

    def google_channels(self) -> list[ChannelData]:
        return [c for c in self.channels if c.name != "Meta Anzeigen"]

    def google_ad_spend(self) -> Decimal:
        return sum((c.performance.cost for c in self.google_channels()), Decimal("0"))

    def google_purchases(self) -> int:
        return sum(c.conversions.purchases for c in self.google_channels())

    def google_revenue(self) -> Decimal:
        return sum((c.conversions.revenue for c in self.google_channels()), Decimal("0"))
