"""Meta Marketing API Adapter."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

from ..config import MetaAdsConfig
from ..models import ChannelConversions, ChannelData, ChannelPerformance, DailyMetrics
from .base import BaseFetcher


class MetaAdsFetcher(BaseFetcher):
    def __init__(self, config: MetaAdsConfig):
        self.config = config
        self._init_api()

    def _init_api(self):
        from facebook_business.api import FacebookAdsApi

        FacebookAdsApi.init(
            app_id=os.environ["META_APP_ID"],
            app_secret=os.environ["META_APP_SECRET"],
            access_token=os.environ["META_ACCESS_TOKEN"],
        )

    def fetch(self, date_from: date, date_to: date) -> ChannelData:
        from facebook_business.adobjects.adaccount import AdAccount

        account = AdAccount(self.config.ad_account_id)
        params = {
            "time_range": {
                "since": date_from.isoformat(),
                "until": date_to.isoformat(),
            },
            "level": "account",
        }
        fields = [
            "impressions",
            "clicks",
            "spend",
            "actions",
            "action_values",
        ]
        insights = account.get_insights(params=params, fields=fields)

        if not insights:
            return ChannelData(name="Meta Anzeigen")

        row = insights[0]
        actions = {a["action_type"]: int(a["value"]) for a in row.get("actions", [])}
        action_values = {
            a["action_type"]: Decimal(a["value"]) for a in row.get("action_values", [])
        }

        return ChannelData(
            name="Meta Anzeigen",
            performance=ChannelPerformance(
                impressions=int(row.get("impressions", 0)),
                clicks=int(row.get("clicks", 0)),
                cost=Decimal(row.get("spend", "0")),
            ),
            conversions=ChannelConversions(
                purchases=actions.get("purchase", 0),
                revenue=action_values.get("purchase", Decimal("0")),
            ),
        )

    def fetch_daily(
        self, client_slug: str, date_from: date, date_to: date
    ) -> list[DailyMetrics]:
        from facebook_business.adobjects.adaccount import AdAccount

        account = AdAccount(self.config.ad_account_id)
        params = {
            "time_range": {
                "since": date_from.isoformat(),
                "until": date_to.isoformat(),
            },
            "level": "account",
            "time_increment": 1,
        }
        fields = [
            "impressions",
            "clicks",
            "spend",
            "actions",
            "action_values",
        ]
        insights = account.get_insights(params=params, fields=fields)

        rows: list[DailyMetrics] = []
        for row in insights:
            actions = {a["action_type"]: int(a["value"]) for a in row.get("actions", [])}
            action_values = {
                a["action_type"]: Decimal(a["value"]) for a in row.get("action_values", [])
            }
            rows.append(
                DailyMetrics(
                    report_date=date.fromisoformat(row["date_start"]),
                    client_slug=client_slug,
                    channel="Meta Anzeigen",
                    impressions=int(row.get("impressions", 0)),
                    clicks=int(row.get("clicks", 0)),
                    cost=Decimal(row.get("spend", "0")),
                    purchases=actions.get("purchase", 0),
                    revenue=action_values.get("purchase", Decimal("0")),
                )
            )
        return rows
