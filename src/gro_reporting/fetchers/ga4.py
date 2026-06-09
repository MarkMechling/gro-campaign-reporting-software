"""GA4 Data API Adapter fuer Merchant-Center-Daten."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

from datetime import datetime

from ..config import GA4Config
from ..models import ChannelConversions, DailyMetrics
from .base import BaseFetcher


class GA4Fetcher(BaseFetcher):
    def __init__(self, config: GA4Config):
        self.config = config
        self.client = self._build_client()

    def _build_client(self):
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=None,
            refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
            client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        creds.refresh(Request())
        return BetaAnalyticsDataClient(credentials=creds)

    def fetch(self, date_from: date, date_to: date):
        return self.fetch_merchant_center(date_from, date_to)

    def fetch_merchant_center(self, date_from: date, date_to: date) -> ChannelConversions:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            FilterExpression,
            Filter,
            Metric,
            RunReportRequest,
        )

        client = self.client

        request = RunReportRequest(
            property=self.config.property_id,
            dimensions=[
                Dimension(name="sessionDefaultChannelGroup"),
                Dimension(name="eventName"),
            ],
            metrics=[
                Metric(name="eventCount"),
                Metric(name="eventValue"),
            ],
            date_ranges=[
                DateRange(
                    start_date=date_from.isoformat(),
                    end_date=date_to.isoformat(),
                )
            ],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name="sessionDefaultChannelGroup",
                    string_filter=Filter.StringFilter(
                        value="Organic Shopping",
                    ),
                )
            ),
        )

        response = client.run_report(request)

        purchases = 0
        revenue = Decimal("0")

        for row in response.rows:
            event_name = row.dimension_values[1].value
            count = int(row.metric_values[0].value)
            value = Decimal(row.metric_values[1].value)

            if event_name == "purchase":
                purchases += count
                revenue += value

        return ChannelConversions(
            purchases=purchases,
            revenue=revenue,
        )

    def fetch_merchant_center_daily(
        self, client_slug: str, date_from: date, date_to: date
    ) -> list[DailyMetrics]:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            FilterExpression,
            Filter,
            Metric,
            RunReportRequest,
        )

        request = RunReportRequest(
            property=self.config.property_id,
            dimensions=[
                Dimension(name="date"),
                Dimension(name="sessionDefaultChannelGroup"),
                Dimension(name="eventName"),
            ],
            metrics=[
                Metric(name="eventCount"),
                Metric(name="eventValue"),
            ],
            date_ranges=[
                DateRange(
                    start_date=date_from.isoformat(),
                    end_date=date_to.isoformat(),
                )
            ],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name="sessionDefaultChannelGroup",
                    string_filter=Filter.StringFilter(
                        value="Organic Shopping",
                    ),
                )
            ),
        )

        response = self.client.run_report(request)

        by_date: dict[date, dict] = {}
        for row in response.rows:
            event_name = row.dimension_values[2].value
            if event_name != "purchase":
                continue
            day = datetime.strptime(row.dimension_values[0].value, "%Y%m%d").date()
            agg = by_date.setdefault(day, {"purchases": 0, "revenue": Decimal("0")})
            agg["purchases"] += int(row.metric_values[0].value)
            agg["revenue"] += Decimal(row.metric_values[1].value)

        return [
            DailyMetrics(
                report_date=day,
                client_slug=client_slug,
                channel="merchant_center",
                purchases=agg["purchases"],
                revenue=agg["revenue"],
            )
            for day, agg in sorted(by_date.items())
        ]
