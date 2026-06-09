"""Daten-Fetcher fuer verschiedene Werbeplattformen."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..config import ClientConfig
from ..models import ChannelConversions, ChannelData, ChannelPerformance, ReportData


def fetch_all_channels(
    config: ClientConfig,
    date_from: date,
    date_to: date,
    skip_fetch: bool = False,
) -> ReportData:
    channels: list[ChannelData] = []
    merchant_center: ChannelConversions | None = None

    if config.google_ads and not skip_fetch:
        from .google_ads import GoogleAdsFetcher

        fetcher = GoogleAdsFetcher(config.google_ads)
        google_channels = fetcher.fetch(date_from, date_to)
        channels.extend(google_channels)

    if config.meta_ads and not skip_fetch:
        from .meta_ads import MetaAdsFetcher

        fetcher = MetaAdsFetcher(config.meta_ads)
        meta_data = fetcher.fetch(date_from, date_to)
        channels.append(meta_data)

    if config.ga4 and not skip_fetch:
        from .ga4 import GA4Fetcher

        fetcher = GA4Fetcher(config.ga4)
        merchant_center = fetcher.fetch_merchant_center(date_from, date_to)

    if not channels and skip_fetch:
        channels = _placeholder_channels()

    return ReportData(
        client_name=config.client.name,
        slug=config.client.slug,
        date_from=date_from,
        date_to=date_to,
        channels=channels,
        merchant_center=merchant_center,
    )


def _placeholder_channels() -> list[ChannelData]:
    return [
        ChannelData(
            name="Google PMAX Kampagnen",
            performance=ChannelPerformance(impressions=0, clicks=0, cost=Decimal("0")),
            conversions=ChannelConversions(),
        ),
        ChannelData(
            name="Suchanzeigen",
            performance=ChannelPerformance(impressions=0, clicks=0, cost=Decimal("0")),
            conversions=ChannelConversions(),
        ),
        ChannelData(
            name="Meta Anzeigen",
            performance=ChannelPerformance(impressions=0, clicks=0, cost=Decimal("0")),
            conversions=ChannelConversions(),
        ),
    ]
