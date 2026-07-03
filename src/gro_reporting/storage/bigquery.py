"""BigQuery-Storage fuer taegliche KPI-Daten.

Konfiguration via Umgebungsvariablen:
- GRO_BQ_PROJECT: GCP-Projekt-ID (Pflicht)
- GRO_BQ_DATASET: Dataset-Name (Default: gro_reporting)
- GOOGLE_APPLICATION_CREDENTIALS: Service-Account-JSON
  (Rollen: BigQuery Data Editor + BigQuery Job User)
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

from ..models import (
    ChannelConversions,
    ChannelData,
    ChannelPerformance,
    DailyMetrics,
    ReportData,
    round_conversions,
)

TABLE_NAME = "daily_metrics"

# BigQuery NUMERIC hat maximal 9 Nachkommastellen
_NUMERIC_SCALE = Decimal("0.000000001")

# Reihenfolge der Kanaele in der Report-Tabelle
CHANNEL_ORDER = [
    "Google PMAX Kampagnen",
    "Suchanzeigen",
    "Demand Gen Kampagnen",
    "Display Kampagnen",
    "YouTube Kampagnen",
    "Shopping Kampagnen",
    "Meta Anzeigen",
]
# Historischer Kanal (GA4 Organic Shopping); Feature entfernt, Altdaten
# bleiben in der Tabelle und werden von Report-Queries ausgeschlossen.
LEGACY_MERCHANT_CENTER_CHANNEL = "merchant_center"
# Marker fuer synchronisierte Tage ohne Aktivitaet (zaehlt fuer get_coverage,
# wird in Reports ignoriert)
NO_DATA_CHANNEL = "_no_data"


class BigQueryStorage:
    def __init__(self, project: str | None = None, dataset: str | None = None):
        self.project = project or os.environ.get("GRO_BQ_PROJECT")
        if not self.project:
            raise RuntimeError(
                "GRO_BQ_PROJECT ist nicht gesetzt (.env). "
                "BigQuery-Funktionen benoetigen eine GCP-Projekt-ID."
            )
        self.dataset = dataset or os.environ.get("GRO_BQ_DATASET", "gro_reporting")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google.cloud import bigquery

            self._client = bigquery.Client(project=self.project)
        return self._client

    @property
    def table_id(self) -> str:
        return f"{self.project}.{self.dataset}.{TABLE_NAME}"

    def ensure_schema(self) -> None:
        """Dataset und Tabelle anlegen, falls nicht vorhanden."""
        from google.cloud import bigquery

        dataset_ref = bigquery.Dataset(f"{self.project}.{self.dataset}")
        dataset_ref.location = os.environ.get("GRO_BQ_LOCATION", "EU")
        self.client.create_dataset(dataset_ref, exists_ok=True)

        schema = [
            bigquery.SchemaField("report_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("client_slug", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("channel", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("impressions", "INT64"),
            bigquery.SchemaField("clicks", "INT64"),
            bigquery.SchemaField("cost", "NUMERIC"),
            # NUMERIC: Google Ads liefert fraktionale Conversions (data-driven
            # attribution); gerundet wird erst beim Aggregieren
            bigquery.SchemaField("purchases", "NUMERIC"),
            bigquery.SchemaField("revenue", "NUMERIC"),
            bigquery.SchemaField("synced_at", "TIMESTAMP"),
        ]
        table = bigquery.Table(self.table_id, schema=schema)
        table.time_partitioning = bigquery.TimePartitioning(field="report_date")
        table.clustering_fields = ["client_slug"]
        self.client.create_table(table, exists_ok=True)

    def write_daily(self, rows: list[DailyMetrics]) -> int:
        """Idempotent schreiben: vorhandene Zeilen fuer (Kunde, Zeitraum) ersetzen.

        Query-basiertes INSERT (kein Streaming), damit das vorausgehende
        DELETE sofort wirksam ist.
        """
        from google.cloud import bigquery

        if not rows:
            return 0

        slug = rows[0].client_slug
        date_from = min(r.report_date for r in rows)
        date_to = max(r.report_date for r in rows)

        delete_query = f"""
            DELETE FROM `{self.table_id}`
            WHERE client_slug = @slug
              AND report_date BETWEEN @date_from AND @date_to
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("slug", "STRING", slug),
                bigquery.ScalarQueryParameter("date_from", "DATE", date_from),
                bigquery.ScalarQueryParameter("date_to", "DATE", date_to),
            ]
        )
        self.client.query(delete_query, job_config=job_config).result()

        struct_params = [
            bigquery.StructQueryParameter(
                None,
                bigquery.ScalarQueryParameter("report_date", "DATE", r.report_date),
                bigquery.ScalarQueryParameter("client_slug", "STRING", r.client_slug),
                bigquery.ScalarQueryParameter("channel", "STRING", r.channel),
                bigquery.ScalarQueryParameter("impressions", "INT64", r.impressions),
                bigquery.ScalarQueryParameter("clicks", "INT64", r.clicks),
                bigquery.ScalarQueryParameter("cost", "NUMERIC", r.cost.quantize(_NUMERIC_SCALE)),
                bigquery.ScalarQueryParameter("purchases", "NUMERIC", r.purchases.quantize(_NUMERIC_SCALE)),
                bigquery.ScalarQueryParameter("revenue", "NUMERIC", r.revenue.quantize(_NUMERIC_SCALE)),
            )
            for r in rows
        ]
        insert_query = f"""
            INSERT INTO `{self.table_id}`
                (report_date, client_slug, channel, impressions, clicks,
                 cost, purchases, revenue, synced_at)
            SELECT row.report_date, row.client_slug, row.channel, row.impressions,
                   row.clicks, row.cost, row.purchases, row.revenue, CURRENT_TIMESTAMP()
            FROM UNNEST(@rows) AS row
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("rows", "STRUCT", struct_params)]
        )
        self.client.query(insert_query, job_config=job_config).result()
        return len(rows)

    def get_coverage(self, slug: str, date_from: date, date_to: date) -> set[date]:
        """Welche Tage im Zeitraum haben bereits Daten?"""
        from google.cloud import bigquery

        query = f"""
            SELECT DISTINCT report_date
            FROM `{self.table_id}`
            WHERE client_slug = @slug
              AND report_date BETWEEN @date_from AND @date_to
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("slug", "STRING", slug),
                bigquery.ScalarQueryParameter("date_from", "DATE", date_from),
                bigquery.ScalarQueryParameter("date_to", "DATE", date_to),
            ]
        )
        result = self.client.query(query, job_config=job_config).result()
        return {row.report_date for row in result}

    def query_report_data(
        self, slug: str, client_name: str, date_from: date, date_to: date
    ) -> ReportData:
        """Tagesdaten zu ReportData aggregieren (Ersatz fuer Live-Fetch)."""
        from google.cloud import bigquery

        query = f"""
            SELECT
                channel,
                SUM(impressions) AS impressions,
                SUM(clicks) AS clicks,
                SUM(cost) AS cost,
                SUM(purchases) AS purchases,
                SUM(revenue) AS revenue
            FROM `{self.table_id}`
            WHERE client_slug = @slug
              AND report_date BETWEEN @date_from AND @date_to
              AND NOT STARTS_WITH(channel, '_')
              AND channel != @legacy_merchant
            GROUP BY channel
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("slug", "STRING", slug),
                bigquery.ScalarQueryParameter("date_from", "DATE", date_from),
                bigquery.ScalarQueryParameter("date_to", "DATE", date_to),
                bigquery.ScalarQueryParameter(
                    "legacy_merchant", "STRING", LEGACY_MERCHANT_CENTER_CHANNEL
                ),
            ]
        )
        result = self.client.query(query, job_config=job_config).result()

        by_channel: dict[str, ChannelData] = {}
        for row in result:
            by_channel[row.channel] = ChannelData(
                name=row.channel,
                performance=ChannelPerformance(
                    impressions=int(row.impressions or 0),
                    clicks=int(row.clicks or 0),
                    cost=Decimal(str(row.cost or 0)),
                ),
                conversions=ChannelConversions(
                    purchases=round_conversions(row.purchases or 0),
                    revenue=Decimal(str(row.revenue or 0)),
                ),
            )

        ordered = [by_channel.pop(name) for name in CHANNEL_ORDER if name in by_channel]
        ordered.extend(by_channel.values())

        return ReportData(
            client_name=client_name,
            slug=slug,
            date_from=date_from,
            date_to=date_to,
            channels=ordered,
        )
