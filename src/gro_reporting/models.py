"""Einheitliche KPI-Datenmodelle fuer alle Kanaele."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from pydantic import BaseModel, computed_field

META_CHANNEL = "Meta Anzeigen"


class ChannelScope(str, Enum):
    """Kanal-Auswahl fuer einen Report: nur Google, nur Meta oder kombiniert."""

    GOOGLE = "google"
    META = "meta"
    ALL = "all"


def round_conversions(value: Decimal | int | float) -> int:
    """Fraktionale Conversions (data-driven attribution) einmalig am Ende runden."""
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


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
    channel: str  # "Google PMAX Kampagnen" | "Suchanzeigen" | "Meta Anzeigen"
    impressions: int = 0
    clicks: int = 0
    cost: Decimal = Decimal("0")
    # Decimal statt int: Google Ads liefert fraktionale Conversions (data-driven
    # attribution); gerundet wird erst beim Aggregieren auf Kanal-Ebene.
    purchases: Decimal = Decimal("0")
    revenue: Decimal = Decimal("0")


class ReportData(BaseModel):
    client_name: str
    slug: str
    date_from: date
    date_to: date
    channels: list[ChannelData] = []

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
        return ChannelConversions(
            purchases=sum(c.conversions.purchases for c in self.channels),
            revenue=sum(c.conversions.revenue for c in self.channels),
        )

    def for_scope(self, scope: ChannelScope) -> ReportData:
        """Kanaele auf den gewaehlten Scope einschraenken (Meta vs. Google)."""
        if scope == ChannelScope.ALL:
            return self
        keep_meta = scope == ChannelScope.META
        channels = [c for c in self.channels if (c.name == META_CHANNEL) == keep_meta]
        return self.model_copy(update={"channels": channels})
