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

    def fetch(self, date_from: date, date_to: date) -> list[ChannelData]:
        ga_service = self.client.get_service("GoogleAdsService")
        customer_id = self.config.customer_id

        perf_by_campaign = self._fetch_performance(ga_service, customer_id, date_from, date_to)
        conv_by_campaign = self._fetch_conversions(ga_service, customer_id, date_from, date_to)

        channels = []
        for channel_key, patterns in self.config.campaigns.items():
            label = CHANNEL_LABELS.get(channel_key, channel_key)
            matching = [
                name for name in perf_by_campaign
                if any(fnmatch.fnmatch(name, p) for p in patterns)
            ]

            perf = ChannelPerformance(
                impressions=sum(perf_by_campaign[n]["impressions"] for n in matching),
                clicks=sum(perf_by_campaign[n]["clicks"] for n in matching),
                cost=sum(perf_by_campaign[n]["cost"] for n in matching),
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

        perf_daily = self._fetch_performance_daily(ga_service, customer_id, date_from, date_to)
        conv_daily = self._fetch_conversions_daily(ga_service, customer_id, date_from, date_to)

        rows: list[DailyMetrics] = []
        for channel_key, patterns in self.config.campaigns.items():
            label = CHANNEL_LABELS.get(channel_key, channel_key)

            by_date: dict[date, dict] = {}
            for (day, name), metrics in perf_daily.items():
                if not any(fnmatch.fnmatch(name, p) for p in patterns):
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
                if not any(fnmatch.fnmatch(name, p) for p in patterns):
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
    ) -> dict:
        query = f"""
            SELECT
                segments.date,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
              AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        result: dict = {}
        for row in response:
            key = (date.fromisoformat(row.segments.date), row.campaign.name)
            if key not in result:
                result[key] = {"impressions": 0, "clicks": 0, "cost": Decimal("0")}
            result[key]["impressions"] += row.metrics.impressions
            result[key]["clicks"] += row.metrics.clicks
            result[key]["cost"] += Decimal(row.metrics.cost_micros) / 1_000_000
        return result

    def _fetch_conversions_daily(
        self, ga_service, customer_id: str, date_from: date, date_to: date
    ) -> dict:
        query = f"""
            SELECT
                segments.date,
                campaign.name,
                segments.conversion_action_name,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
              AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        result: dict = {}
        for row in response:
            key = (date.fromisoformat(row.segments.date), row.campaign.name)
            action = row.segments.conversion_action_name.lower().replace(" ", "_")
            if key not in result:
                result[key] = {"purchase": Decimal("0"), "revenue": Decimal("0")}
            if "purchase" in action:
                result[key]["purchase"] += Decimal(str(row.metrics.conversions))
                result[key]["revenue"] += Decimal(str(row.metrics.conversions_value))
        return result

    def _fetch_performance(
        self, ga_service, customer_id: str, date_from: date, date_to: date
    ) -> dict:
        query = f"""
            SELECT
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
              AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        result: dict = {}
        for row in response:
            name = row.campaign.name
            if name not in result:
                result[name] = {"impressions": 0, "clicks": 0, "cost": Decimal("0")}
            result[name]["impressions"] += row.metrics.impressions
            result[name]["clicks"] += row.metrics.clicks
            result[name]["cost"] += Decimal(row.metrics.cost_micros) / 1_000_000
        return result

    def _fetch_conversions(
        self, ga_service, customer_id: str, date_from: date, date_to: date
    ) -> dict:
        query = f"""
            SELECT
                campaign.name,
                segments.conversion_action_name,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
              AND campaign.status != 'REMOVED'
        """
        response = ga_service.search(customer_id=customer_id, query=query)
        result: dict = {}
        action_map = {
            "purchase": "purchase",
        }
        for row in response:
            name = row.campaign.name
            action = row.segments.conversion_action_name.lower().replace(" ", "_")
            if name not in result:
                result[name] = {
                    "purchase": Decimal("0"),
                    "revenue": Decimal("0"),
                }
            for key, mapped in action_map.items():
                if key in action:
                    result[name][mapped] += Decimal(str(row.metrics.conversions))
                    if mapped == "purchase":
                        result[name]["revenue"] += Decimal(str(row.metrics.conversions_value))
                    break
        return result
