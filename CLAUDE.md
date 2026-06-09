# GRO Campaign Reporting Software

Automatisiertes Kampagnen-Reporting fuer MASSIVEART-Kunden mit BigQuery-Speicher und Self-Service Web UI (Streamlit). Generiert 4-seitige PDF-Reports (Titelseite, Performance, Conversions, Status Quo) aus Google Ads, Meta Ads und GA4 Daten. Weiterentwicklung des CLI-Tools in `/Users/mark.mechling/PycharmProjects/GRO-campaign-reporting` (bleibt unveraendert).

## Schnellstart

```bash
# Aktivierung
source .venv/bin/activate

# Dependencies installieren
pip install -e ".[dev]"

# System-Dependencies (macOS, fuer WeasyPrint)
brew install pango gdk-pixbuf libffi

# Tests
pytest

# CLI
gro-report list
gro-report validate fuerst
gro-report init-bq                                  # BQ-Dataset + Tabelle anlegen
gro-report sync fuerst --month 2026-05              # Tagesdaten nach BigQuery
gro-report sync all --from 2026-05-01 --to 2026-05-31 --force
gro-report generate fuerst --month 2026-05          # Live-APIs (wie bisher)
gro-report generate fuerst --month 2026-05 --source bq  # Aus BigQuery

# Web UI
streamlit run app.py
```

## Projektstruktur

```
app.py            # Streamlit Self-Service UI (Kunde + Zeitraum -> PDF)
.streamlit/       # Theme (MASSIVEART CI)
Dockerfile        # Cloud-Run-ready (python:3.12-slim + WeasyPrint-Deps)
src/gro_reporting/
  cli.py          # Click CLI: generate, sync, init-bq, list, validate
  config.py       # Pydantic-Modelle fuer YAML-Kundenconfig (inkl. client_logo)
  models.py       # KPI-Datenmodelle (ChannelPerformance, ChannelConversions, ReportData, DailyMetrics)
  formatting.py   # Deutsche Zahlen/Waehrung/Datum (kein locale)
  sync.py         # sync_client: fehlende Tage fetchen -> BigQuery
  fetchers/       # API-Adapter: google_ads.py, meta_ads.py, ga4.py (je fetch + fetch_daily)
  storage/
    bigquery.py   # BigQueryStorage: ensure_schema, write_daily, get_coverage, query_report_data
  report/
    builder.py    # Data -> Template-Context -> HTML -> PDF
    renderer.py   # WeasyPrint-Wrapper
  templates/      # Jinja2 HTML-Templates + style.css + Fonts (GT Walsheim Pro)
  assets/         # MASSIVEART-Logos (massiveart-logo.jpg, logo_m.svg)
assets/clients/   # Kunden-Assets (Cover-Bilder, Logos: assets/clients/<slug>/logo.png)
clients/          # YAML-Config pro Kunde (fuerst.yaml, _example.yaml)
output/           # Generierte PDFs (gitignored)
tests/
```

## Architektur

```
Sync:    APIs (Google Ads / Meta / GA4) --Tageszeilen--> BigQuery (daily_metrics)
Report:  Streamlit UI --Kunde+Zeitraum--> BQ-Aggregat --> ReportData --> ReportBuilder (Jinja2+WeasyPrint) --> PDF
```

- Kunden-Configs liegen als YAML in `clients/`. Slug = Dateiname ohne Extension.
- BigQuery-Tabelle `daily_metrics`: eine Zeile pro Kunde/Kanal/Tag, partitioniert nach `report_date`, geclustert nach `client_slug`. Kanaele: `Google PMAX Kampagnen`, `Suchanzeigen`, `Meta Anzeigen`, `merchant_center`.
- `write_daily` ist idempotent: DELETE fuer (Kunde, Zeitraum), dann query-basiertes INSERT (kein Streaming-Buffer).
- Sync ist inkrementell: `get_coverage` ermittelt fehlende Tage; `--force` laedt alles neu.
- Live-Pfad (`--source live`, Default) funktioniert weiterhin ohne BigQuery.
- PDF ist 16:9 Landscape (338mm x 190mm), passend zu Keynote-Vorlagen.

## BigQuery-Setup

In `.env` (gitignored):

```
GRO_BQ_PROJECT=<gcp-projekt-id>
GRO_BQ_DATASET=gro_reporting          # optional, Default
GRO_BQ_LOCATION=EU                    # optional, Default EU
GOOGLE_APPLICATION_CREDENTIALS=/pfad/zu/service-account.json
```

Service Account braucht die Rollen **BigQuery Data Editor** und **BigQuery Job User**. Danach einmalig `gro-report init-bq`.

## Konventionen

- Python 3.14 lokal (venv unter `.venv/`), Container pinnt 3.12 (Wheel-Verfuegbarkeit)
- Deutsche Formatierung: `1.234.567` (Tausender-Punkt), `€ 1.234,56`, `3,52 %`, `01.01.2026`
- Formatierungsfunktionen in `formatting.py` -- kein `locale.setlocale()`
- MASSIVEART CI-Farben: Panel `#1d3c4b` (colorBlueItems), Akzent `#36f5cf` (colorGreenTurquoise), Dunkel `#161b20` (colorGreySeven), Primaer-Gruen `#009d77` (colorGreenHaze)
- Font: GT Walsheim Pro (Light 300 + Black 900)
- Per-Kunde-Branding: `cover_image` + `client_logo` in der Kunden-YAML (Pfade relativ zum Projekt-Root); MASSIVEART-Logo und CI bleiben fix
- ROAS-Berechnung basiert auf tatsaechlichem Umsatz (nicht Mindestwarenkorbwert), konfigurierbar pro Kunde via `roas_mode`: `google_only`, `google_plus_merchant`, `total`
- PMAX ROAS wird separat berechnet und auf der Status-Quo-Seite als eigene KPI-Zeile angezeigt
- Conversions-Tabelle zeigt nur Purchase + Umsatz, Kurznamen via `builder.py:CONV_NAME_MAP`
- Google Ads Kampagnennamen nutzen Wildcard-Patterns (z.B. `*PMAX*`, `*GSU*`) da Kampagnen mit Datum-Prefix benannt sind
- Google Ads Conversion-Action-Namen werden normalisiert (Leerzeichen -> Unterstriche) fuer zuverlaessiges Matching
- UI-Texte auf Deutsch (Streamlit + CLI)

## CLI-Flags

- `--month YYYY-MM` oder `--from/--to YYYY-MM-DD`: Zeitraum (generate + sync)
- `--source live|bq`: Datenquelle fuer generate (Default: live)
- `--force`: sync laedt auch bereits vorhandene Tage neu
- `--dry-run`: Nur Daten abrufen, kein PDF
- `--skip-fetch`: Gecachte/Placeholder-Daten, fuer Template-Iteration
- `--output PATH`: Alternatives Output-Verzeichnis

## Credentials

Ueber `.env` (gitignored). Vorlage: `.env.example`.

- **Google Ads + GA4:** Gleiche OAuth-Credentials (Client ID, Secret, Refresh Token). Der Refresh Token hat Scopes fuer `adwords` und `analytics.readonly`.
- **Meta Ads:** System User Token aus dem Business Manager (laeuft nicht ab).
- **Login Customer ID:** MCC-ID von MASSIVEART (631-570-0134).
- **BigQuery:** Service Account JSON via `GOOGLE_APPLICATION_CREDENTIALS`.

## Tests

```bash
pytest                           # Alle Tests
pytest tests/test_formatting.py  # Nur Formatierung
pytest tests/test_report_generation.py  # PDF mit Referenz-Daten generieren
```

Der Report-Test generiert `output/test_reference.pdf` mit den exakten Zahlen aus der Referenz-PDF.

## Deployment (Cloud Run, spaeter)

```bash
docker build -t gro-reporting .
docker run -p 8080:8080 --env-file .env gro-reporting   # lokaler Smoke-Test

# Deploy-Skizze (nicht automatisiert):
# gcloud run deploy gro-reporting --source . --region europe-west1 \
#   --set-env-vars GRO_BQ_PROJECT=...,GRO_BQ_DATASET=gro_reporting
```

Hinweise: Auf Cloud Run laeuft die Auth ueber den Service Account des Dienstes (kein `GOOGLE_APPLICATION_CREDENTIALS` noetig); Secrets (.env-Inhalte) via Secret Manager. Zugriffsschutz z.B. via IAP oder `--no-allow-unauthenticated` + Proxy.

## LLM-Wiki Integration

Pfad: `/Users/mark.mechling/Documents/llm-wiki`

- **Session-Start:** Lies die CLAUDE.md aus dem llm-wiki (`/Users/mark.mechling/Documents/llm-wiki/CLAUDE.md`), um den aktuellen Wiki-Kontext zu haben.
- **Session-Ende:** Aktualisiere das llm-wiki mit relevanten Informationen aus dieser Session (neue Erkenntnisse, Entscheidungen, Patterns, Troubleshooting). Folge dabei dem Ingest-Workflow und den Konventionen aus der llm-wiki CLAUDE.md. Wiki-Inhalte immer auf Englisch schreiben.
