"""Sync: API-Tagesdaten nach BigQuery schreiben."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .config import ClientConfig
from .models import DailyMetrics
from .storage.bigquery import BigQueryStorage


@dataclass
class SyncResult:
    slug: str
    date_from: date
    date_to: date
    days_synced: int
    rows_written: int
    skipped: bool = False

    def summary(self) -> str:
        if self.skipped:
            return f"{self.slug}: Zeitraum bereits vollstaendig synchronisiert."
        return (
            f"{self.slug}: {self.days_synced} Tage synchronisiert "
            f"({self.date_from} bis {self.date_to}), {self.rows_written} Zeilen geschrieben."
        )


def _date_range(date_from: date, date_to: date) -> list[date]:
    return [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]


def sync_client(
    config: ClientConfig,
    date_from: date,
    date_to: date,
    force: bool = False,
    storage: BigQueryStorage | None = None,
) -> SyncResult:
    """Fehlende Tage ermitteln, taeglich fetchen und nach BigQuery schreiben.

    Ohne force werden nur fehlende Tage geholt (zusammenhaengender Bereich
    von erstem bis letztem fehlenden Tag, da die APIs Zeitraeume abfragen).
    """
    slug = config.client.slug
    storage = storage or BigQueryStorage()
    storage.ensure_schema()

    if force:
        fetch_from, fetch_to = date_from, date_to
    else:
        covered = storage.get_coverage(slug, date_from, date_to)
        missing = [d for d in _date_range(date_from, date_to) if d not in covered]
        if not missing:
            return SyncResult(slug, date_from, date_to, 0, 0, skipped=True)
        fetch_from, fetch_to = min(missing), max(missing)

    rows: list[DailyMetrics] = []

    if config.google_ads:
        from .fetchers.google_ads import GoogleAdsFetcher

        rows.extend(GoogleAdsFetcher(config.google_ads).fetch_daily(slug, fetch_from, fetch_to))

    if config.meta_ads:
        from .fetchers.meta_ads import MetaAdsFetcher

        rows.extend(MetaAdsFetcher(config.meta_ads).fetch_daily(slug, fetch_from, fetch_to))

    if config.ga4:
        from .fetchers.ga4 import GA4Fetcher

        rows.extend(
            GA4Fetcher(config.ga4).fetch_merchant_center_daily(slug, fetch_from, fetch_to)
        )

    written = storage.write_daily(rows)
    days = (fetch_to - fetch_from).days + 1
    return SyncResult(slug, fetch_from, fetch_to, days, written)
