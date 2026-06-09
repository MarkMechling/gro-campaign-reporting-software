"""Sync: API-Tagesdaten nach BigQuery schreiben."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .config import ClientConfig
from .models import DailyMetrics
from .storage.bigquery import NO_DATA_CHANNEL, BigQueryStorage


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
    fetch_days = _date_range(fetch_from, fetch_to)

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

    # Tage ohne Aktivitaet liefern keine API-Zeilen. Marker-Zeile schreiben,
    # damit get_coverage sie als synchronisiert erkennt (sonst wuerden sie
    # bei jedem Sync neu geholt und die UI meldet sie dauerhaft als fehlend).
    days_with_data = {r.report_date for r in rows}
    for day in fetch_days:
        if day not in days_with_data:
            rows.append(DailyMetrics(report_date=day, client_slug=slug, channel=NO_DATA_CHANNEL))

    written = storage.write_daily(rows)
    return SyncResult(slug, fetch_from, fetch_to, len(fetch_days), written)
