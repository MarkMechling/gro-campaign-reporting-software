"""Google Ads API Adapter."""

from __future__ import annotations

import fnmatch
import os
from datetime import date
from decimal import Decimal

from ..config import GoogleAdsConfig
from ..models import (
    ChannelConversions,
    ChannelData,
    ChannelPerformance,
    DailyMetrics,
    round_conversions,
)
from .base import BaseFetcher

CHANNEL_LABELS = {
    "pmax": "Google PMAX Kampagnen",
    "search": "Suchanzeigen",
    "demand_gen": "Demand Gen Kampagnen",
    "display": "Display Kampagnen",
    "youtube": "YouTube Kampagnen",
}

# Auto-Kategorisierung nach advertising_channel_type, wenn in der Kunden-YAML
# keine campaigns-Patterns konfiguriert sind (= ganzer Account im Report)
TYPE_LABELS = {
    "SEARCH": "Suchanzeigen",
    "PERFORMANCE_MAX": "Google PMAX Kampagnen",
    "DEMAND_GEN": "Demand Gen Kampagnen",
    "DISPLAY": "Display Kampagnen",
    "VIDEO": "YouTube Kampagnen",
    "SHOPPING": "Shopping Kampagnen",
}


class GoogleAdsFetcher(BaseFetcher):
    def __init__(self, config: GoogleAdsConfig):
        self.config = config
        self.client = self._build_client()

    def _build_client(self):
        from google.ads.googleads.client import GoogleAdsClient

        return GoogleAdsClient.load_from_dict(
            {
                "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
                "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
                "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
                "login_customer_id": os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", ""),
                "use_proto_plus": True,
            }
        )

    def _channel_groups(self, campaign_types: dict[str, str]) -> list[tuple[str, list[str]]]:
        """Kampagnen zu Report-Kanaelen gruppieren.

        Mit campaigns-Patterns in der YAML: Name-Matching wie bisher.
        Ohne Patterns: automatisch nach advertising_channel_type (ganzer Account).
        """
        if self.config.campaigns:
            return [
                (
                    CHANNEL_LABELS.get(key, key),
                    [
                        name for name in campaign_types
                        if any(fnmatch.fnmatch(name, p) for p in patterns)
                    ],
                )
                for key, patterns in self.config.campaigns.items()
            ]

        groups: dict[str, list[str]] = {}
        for name, ctype in campaign_types.items():
            label = TYPE_LABELS.get(ctype, ctype)
            groups.setdefault(label, []).append(name)
        order = list(dict.fromkeys(["Google PMAX Kampagnen", *TYPE_LABELS.values()]))
        return sorted(
            groups.items(),
            key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order),
        )

    def fetch(self, date_from: date, date_to: date) -> list[ChannelData]:
        ga_service = self.client.get_service("GoogleAdsService")
        customer_id = self.config.customer_id

        perf_by_campaign, perf_types = self._fetch_performance(
            ga_service, customer_id, date_from, date_to
        )
        conv_by_campaign, conv_types = self._fetch_conversions(
            ga_service, customer_id, date_from, date_to
        )

        channels = []
        for label, matching in self._channel_groups({**conv_types, **perf_types}):
            perf = ChannelPerformance(
                impressions=sum(perf_by_campaign.get(n, {}).get("impressions", 0) for n in matching),
                clicks=sum(perf_by_campaign.get(n, {}).get("clicks", 0) for n in matching),
                cost=sum(
                    (perf_by_campaign.get(n, {}).get("cost", Decimal("0")) for n in matching),
                    Decimal("0"),
                ),
            )
            conv = ChannelConversions(
                purchases=round_conversions(
                    sum(
                        (conv_by_campaign.get(n, {}).get("purchase", Decimal("0")) for n in matching),
                        Decimal("0"),
                    )
                ),
                revenue=sum(conv_by_campaign.get(n, {}).get("revenue", Decimal("0")) for n in matching),
            )
            channels.append(ChannelData(name=label, performance=perf, conversions=conv))

        return channels

    def fetch_daily(
        self, client_slug: str, date_from: date, date_to: date
    ) -> list[DailyMetrics]:
        ga_service = self.client.get_service("GoogleAdsService")
        customer_id = self.config.customer_id

        perf_daily, perf_types = self._fetch_performance_daily(
            ga_service, customer_id, date_from, date_to
        )
        conv_daily, conv_types = self._fetch_conversions_daily(
            ga_service, customer_id, date_from, date_to
        )

        rows: list[DailyMetrics] = []
        for label, matching in self._channel_groups({**conv_types, **perf_types}):
            names = set(matching)

            by_date: dict[date, dict] = {}
            for (day, name), metrics in perf_daily.items():
                if name not in names:
                    continue
                agg = by_date.setdefault(
                    day,
                    {"impressions": 0, "clicks": 0, "cost": Decimal("0"),
                     "purchases": Decimal("0"), "revenue": Decimal("0")},
                )
                agg["impressions"] += metrics["impressions"]
                agg["clicks"] += metrics["clicks"]
                agg["cost"] += metrics["cost"]
            for (day, name), metrics in conv_daily.items():
                if name not in names:
                    continue
                agg = by_date.setdefault(
                    day,
                    {"impressions": 0, "clicks": 0, "cost": Decimal("0"),
                     "purchases": Decimal("0"), "revenue": Decimal("0")},
                )
                agg["purchases"] += metrics["purchase"]
                agg["revenue"] += metrics["revenue"]

            for day, agg in sorted(by_date.items()):
                rows.append(
                    DailyMetrics(
                        report_date=day,
                        client_slug=client_slug,
                        channel=label,
                        **agg,
                    )
                )
        return rows

    def _fetch_performance_daily(
        self, ga_service, customer_id: str, date_from: date, date_to: date
    ) -> tuple[dict, dict[str, str]]:
        query = f"""
            SELECT
                segments.date,
                campaign.name,
                campaign.advertising_channel_type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
              AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        result: dict = {}
        types: dict[str, str] = {}
        for row in response:
            key = (date.fromisoformat(row.segments.date), row.campaign.name)
            types[row.campaign.name] = row.campaign.advertising_channel_type.name
            if key not in result:
                result[key] = {"impressions": 0, "clicks": 0, "cost": Decimal("0")}
            result[key]["impressions"] += row.metrics.impressions
            result[key]["clicks"] += row.metrics.clicks
            result[key]["cost"] += Decimal(row.metrics.cost_micros) / 1_000_000
        return result, types

    def _fetch_conversions_daily(
        self, ga_service, customer_id: str, date_from: date, date_to: date
    ) -> tuple[dict, dict[str, str]]:
        query = f"""
            SELECT
                segments.date,
                campaign.name,
                campaign.advertising_channel_type,
                segments.conversion_action_name,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
              AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        result: dict = {}
        types: dict[str, str] = {}
        for row in response:
            key = (date.fromisoformat(row.segments.date), row.campaign.name)
            types[row.campaign.name] = row.campaign.advertising_channel_type.name
            action = row.segments.conversion_action_name.lower().replace(" ", "_")
            if key not in result:
                result[key] = {"purchase": Decimal("0"), "revenue": Decimal("0")}
            if "purchase" in action:
                result[key]["purchase"] += Decimal(str(row.metrics.conversions))
                result[key]["revenue"] += Decimal(str(row.metrics.conversions_value))
        return result, types

    def _fetch_performance(
        self, ga_service, customer_id: str, date_from: date, date_to: date
    ) -> tuple[dict, dict[str, str]]:
        query = f"""
            SELECT
                campaign.name,
                campaign.advertising_channel_type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
              AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        result: dict = {}
        types: dict[str, str] = {}
        for row in response:
            name = row.campaign.name
            types[name] = row.campaign.advertising_channel_type.name
            if name not in result:
                result[name] = {"impressions": 0, "clicks": 0, "cost": Decimal("0")}
            result[name]["impressions"] += row.metrics.impressions
            result[name]["clicks"] += row.metrics.clicks
            result[name]["cost"] += Decimal(row.metrics.cost_micros) / 1_000_000
        return result, types

    def _fetch_conversions(
        self, ga_service, customer_id: str, date_from: date, date_to: date
    ) -> tuple[dict, dict[str, str]]:
        query = f"""
            SELECT
                campaign.name,
                campaign.advertising_channel_type,
                segments.conversion_action_name,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
              AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        result: dict = {}
        types: dict[str, str] = {}
        for row in response:
            name = row.campaign.name
            types[name] = row.campaign.advertising_channel_type.name
            action = row.segments.conversion_action_name.lower().replace(" ", "_")
            if name not in result:
                result[name] = {
                    "purchase": Decimal("0"),
                    "revenue": Decimal("0"),
                }
            if "purchase" in action:
                result[name]["purchase"] += Decimal(str(row.metrics.conversions))
                result[name]["revenue"] += Decimal(str(row.metrics.conversions_value))
        return result, types
