"""Click CLI fuer gro-report."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import click
from dotenv import load_dotenv

from .config import ClientConfig, list_clients, load_client_config
from .models import ChannelScope
from .report.builder import ReportBuilder

load_dotenv()

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


def parse_month(month_str: str) -> tuple[date, date]:
    year, month = month_str.split("-")
    first = date(int(year), int(month), 1)
    if int(month) == 12:
        last = date(int(year) + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(int(year), int(month) + 1, 1) - timedelta(days=1)
    return first, last


def generate_for_client(
    config: ClientConfig,
    date_from: date,
    date_to: date,
    output_dir: Path,
    dry_run: bool = False,
    skip_fetch: bool = False,
    source: str = "live",
    scope: ChannelScope = ChannelScope.ALL,
) -> Path | None:
    if source == "bq":
        from .storage.bigquery import BigQueryStorage

        click.echo(f"  Daten aus BigQuery laden fuer {config.client.name}...")
        try:
            storage = BigQueryStorage()
        except RuntimeError as e:
            raise click.ClickException(str(e))
        report_data = storage.query_report_data(
            config.client.slug, config.client.name, date_from, date_to
        ).for_scope(scope)
    else:
        from .fetchers import fetch_all_channels

        click.echo(f"  Daten abrufen fuer {config.client.name}...")
        report_data = fetch_all_channels(
            config, date_from, date_to, skip_fetch=skip_fetch, scope=scope
        )

    if dry_run:
        click.echo(f"  [dry-run] Daten abgerufen, kein PDF generiert.")
        tp = report_data.total_performance
        tc = report_data.total_conversions
        click.echo(f"    Impressionen: {tp.impressions:,}")
        click.echo(f"    Klicks: {tp.clicks:,}")
        click.echo(f"    Kosten: {tp.cost}")
        click.echo(f"    Purchases: {tc.purchases}")
        click.echo(f"    Umsatz: {tc.revenue}")
        return None

    click.echo(f"  PDF generieren...")
    builder = ReportBuilder(config, report_data)
    output_dir.mkdir(parents=True, exist_ok=True)

    month_str = date_from.strftime("%Y-%m")
    scope_suffix = "" if scope == ChannelScope.ALL else f"_{scope.value}"
    filename = f"{month_str}_{config.client.slug}_Kampagnenupdate{scope_suffix}.pdf"
    output_path = output_dir / filename

    builder.build(output_path)
    click.echo(f"  -> {output_path}")
    return output_path


@click.group()
def cli():
    """GRO Campaign Reporting Tool."""
    pass


@cli.command()
@click.argument("client")
@click.option("--month", "-m", help="Monat im Format YYYY-MM")
@click.option("--from", "date_from_str", help="Startdatum YYYY-MM-DD")
@click.option("--to", "date_to_str", help="Enddatum YYYY-MM-DD")
@click.option("--dry-run", is_flag=True, help="Nur Daten abrufen, kein PDF")
@click.option("--skip-fetch", is_flag=True, help="Gecachte Daten verwenden")
@click.option("--output", "-o", type=click.Path(), help="Output-Verzeichnis")
@click.option(
    "--source",
    type=click.Choice(["live", "bq"]),
    default="live",
    show_default=True,
    help="Datenquelle: live APIs oder BigQuery",
)
@click.option(
    "--channels",
    type=click.Choice([s.value for s in ChannelScope]),
    default=ChannelScope.ALL.value,
    show_default=True,
    help="Kanaele im Report: google, meta oder all (kombiniert)",
)
def generate(
    client: str,
    month: str | None,
    date_from_str: str | None,
    date_to_str: str | None,
    dry_run: bool,
    skip_fetch: bool,
    output: str | None,
    source: str,
    channels: str,
):
    """Report fuer einen oder alle Kunden generieren."""
    if month:
        date_from, date_to = parse_month(month)
    elif date_from_str and date_to_str:
        date_from = date.fromisoformat(date_from_str)
        date_to = date.fromisoformat(date_to_str)
    else:
        click.echo("Fehler: --month oder --from/--to angeben.", err=True)
        sys.exit(1)

    output_dir = Path(output) if output else OUTPUT_DIR
    scope = ChannelScope(channels)

    if client == "all":
        slugs = list_clients()
        if not slugs:
            click.echo("Keine Kunden konfiguriert.", err=True)
            sys.exit(1)
        click.echo(f"Generiere Reports fuer {len(slugs)} Kunden...")
        for slug in slugs:
            click.echo(f"\n[{slug}]")
            config = load_client_config(slug)
            generate_for_client(
                config, date_from, date_to, output_dir, dry_run, skip_fetch, source, scope
            )
    else:
        config = load_client_config(client)
        click.echo(f"[{config.client.name}]")
        generate_for_client(
            config, date_from, date_to, output_dir, dry_run, skip_fetch, source, scope
        )


@cli.command()
@click.argument("client")
@click.option("--month", "-m", help="Monat im Format YYYY-MM")
@click.option("--from", "date_from_str", help="Startdatum YYYY-MM-DD")
@click.option("--to", "date_to_str", help="Enddatum YYYY-MM-DD")
@click.option("--force", is_flag=True, help="Auch bereits synchronisierte Tage neu laden")
def sync(
    client: str,
    month: str | None,
    date_from_str: str | None,
    date_to_str: str | None,
    force: bool,
):
    """Tagesdaten fuer einen oder alle Kunden nach BigQuery synchronisieren."""
    from .sync import sync_client

    if month:
        date_from, date_to = parse_month(month)
    elif date_from_str and date_to_str:
        date_from = date.fromisoformat(date_from_str)
        date_to = date.fromisoformat(date_to_str)
    else:
        click.echo("Fehler: --month oder --from/--to angeben.", err=True)
        sys.exit(1)

    slugs = list_clients() if client == "all" else [client]
    if not slugs:
        click.echo("Keine Kunden konfiguriert.", err=True)
        sys.exit(1)

    for slug in slugs:
        config = load_client_config(slug)
        click.echo(f"[{config.client.name}] Sync {date_from} bis {date_to}...")
        try:
            result = sync_client(config, date_from, date_to, force=force)
        except RuntimeError as e:
            raise click.ClickException(str(e))
        click.echo(f"  {result.summary()}")


@cli.command("init-bq")
def init_bq():
    """BigQuery-Dataset und -Tabelle anlegen."""
    from .storage.bigquery import BigQueryStorage

    try:
        storage = BigQueryStorage()
    except RuntimeError as e:
        raise click.ClickException(str(e))
    storage.ensure_schema()
    click.echo(f"Schema bereit: {storage.table_id}")


@cli.command("list")
def list_cmd():
    """Konfigurierte Kunden auflisten."""
    slugs = list_clients()
    if not slugs:
        click.echo("Keine Kunden konfiguriert.")
        return
    for slug in slugs:
        config = load_client_config(slug)
        click.echo(f"  {slug:20s} {config.client.name}")


@cli.command()
@click.argument("client", required=False)
def validate(client: str | None):
    """Config-Dateien pruefen."""
    slugs = [client] if client else list_clients()
    if not slugs:
        click.echo("Keine Kunden konfiguriert.")
        return
    ok = True
    for slug in slugs:
        try:
            config = load_client_config(slug)
            click.echo(f"  {slug}: OK ({config.client.name})")
        except Exception as e:
            click.echo(f"  {slug}: FEHLER - {e}", err=True)
            ok = False
    if not ok:
        sys.exit(1)
