# GRO Campaign Reporting Software

Automatisiertes Kampagnen-Reporting fuer MASSIVEART-Kunden mit BigQuery-Speicher und Self-Service Web UI (Streamlit). Generiert 4-seitige PDF-Reports (Titelseite, Performance, Conversions, Status Quo) aus Google Ads und Meta Ads Daten -- pro Kanal getrennt oder kombiniert. Weiterentwicklung des CLI-Tools in `/Users/mark.mechling/PycharmProjects/GRO-campaign-reporting` (bleibt unveraendert).

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
gro-report generate fuerst --month 2026-05 --source bq --channels google  # Nur Google Ads

# Web UI
streamlit run app.py
```

## Projektstruktur

```
app.py            # Streamlit Self-Service UI (Kunde + Zeitraum -> PDF)
.streamlit/       # Theme (MASSIVEART CI inkl. GT-Walsheim-fontFaces)
static/           # Fonts fuer die Streamlit-UI (Kopien aus src/gro_reporting/templates/)
Dockerfile        # Cloud-Run-ready (python:3.12-slim + WeasyPrint-Deps)
src/gro_reporting/
  cli.py          # Click CLI: generate, sync, init-bq, list, validate
  config.py       # Pydantic-Modelle fuer YAML-Kundenconfig (inkl. client_logo)
  models.py       # KPI-Datenmodelle (ChannelPerformance, ChannelConversions, ReportData, DailyMetrics)
  formatting.py   # Deutsche Zahlen/Waehrung/Datum (kein locale)
  sync.py         # sync_client: fehlende Tage fetchen -> BigQuery
  fetchers/       # API-Adapter: google_ads.py, meta_ads.py (je fetch + fetch_daily)
  storage/
    bigquery.py   # BigQueryStorage: ensure_schema, write_daily, get_coverage, query_report_data
  report/
    builder.py    # Data -> Template-Context -> HTML -> PDF
    renderer.py   # WeasyPrint-Wrapper
  templates/      # Jinja2 HTML-Templates + style.css + Fonts (GT Walsheim Pro)
  assets/         # MASSIVEART-Logos (massiveart-logo.jpg, logo_m_white.png, logo_m.svg)
assets/clients/   # Kunden-Assets (Cover-Bilder, Logos: assets/clients/<slug>/logo.png)
clients/          # YAML-Config pro Kunde (Vorlage: _example.yaml)
output/           # Generierte PDFs (gitignored)
tests/
```

## Kunden

Alle Google-Ads-Accounts liegen unter dem MASSIVEART-MCC (631-570-0134). Ohne
`campaigns`-Patterns wird der gesamte Account nach Kampagnentyp berichtet.

| Slug | Kunde | Customer ID | Besonderheiten |
|------|-------|-------------|----------------|
| `fuerst` | Cafe-Konditorei Fürst | 335-170-7731 | Einziger Kunde mit Meta Ads + E-Commerce (Purchases/Umsatz); nutzt campaigns-Patterns (`*PMAX*`, `*GSU*`); aktuell keine Ads geplant |
| `rhomberg-bau` | Rhomberg Bau | 233-324-1399 | Account enthaelt viele Alt-Kampagnen (RB-G**-Schema); Meta-Account existiert (act_1291854624802687, "Agenturkonto 2023", EUR), noch nicht in YAML konfiguriert |
| `lech-zuers` | Lech Zürs Tourismus | 229-519-9676 | Search + PMax + Demand Gen aktiv |
| `thun-thunersee` | Thun-Thunersee Tourismus | 358-472-4597 | `currency: CHF` |
| `ovd-kinegram` | OVD Kinegram | 970-611-7227 | Zweiter Account 433-518-0494 (DOVID-Kampagnen) wird nicht berichtet |
| `getzner-dach` | Getzner Werkstoffe DACH | 755-934-2141 | Getzner: 5 Regionen-Accounts, identische Kampagnennamen |
| `getzner-europa-au` | Getzner Europa & Australien | 929-806-0739 | |
| `getzner-usa` | Getzner USA | 576-881-7105 | |
| `getzner-en-world` | Getzner EN World | 680-764-3584 | |
| `getzner-fr` | Getzner Frankreich | 761-453-9762 | |

Offen bei den 2026-07 onboardeten Kunden: Cover-Bilder (alle), Logos
(Thun, OVD, Getzner), `next_steps`-Texte, ggf. Meta-Account-IDs. B2B-Kunden
haben kein Purchase-Tracking -- Conversions/ROAS zeigen 0, Lead-basiertes
Conversion-Reporting ist ein offenes Feature.

## Ad-hoc Kampagnen-Reviews (ausserhalb dieses Repos)

Einmalige Kampagnen-Abschlussreports (Kampagnen-/Asset-Gruppen-/Ad-Set-Ebene,
kuratierte Learnings-Slides) sind bewusst KEIN Feature dieses Tools. Sie leben
in `~/PycharmProjects/adhoc-campaign-reviews/<kunde-thema>/` und laden die
Credentials aus der `.env` dieses Repos (absoluter Pfad). Erstes Beispiel:
`rhomberg-immobilien/` (RHOG-27, Juli 2026) mit `pull.py` (Google
asset_group-Ebene inkl. `segments.conversion_action_name`, Meta Ad-Set-Insights
mit Lead-Actions), `verify.py` (UI-Gegenprobe) und `build_deck.py`
(WeasyPrint-Foliendeck im MASSIVE ART Look). Wird so etwas zum wiederkehrenden
Bedarf (>= 2-3 Kunden), als Feature hier designen -- die API-Learnings dazu
stehen im llm-wiki.

## Architektur

```
Sync:    APIs (Google Ads / Meta) --Tageszeilen--> BigQuery (daily_metrics)
Report:  Streamlit UI --Kunde+Zeitraum--> BQ-Aggregat --> ReportData --> ReportBuilder (Jinja2+WeasyPrint) --> PDF
```

- Kunden-Configs liegen als YAML in `clients/`. Slug = Dateiname ohne Extension.
- BigQuery-Tabelle `daily_metrics`: eine Zeile pro Kunde/Kanal/Tag, partitioniert nach `report_date`, geclustert nach `client_slug`. Kanaele: `Google PMAX Kampagnen`, `Suchanzeigen`, `Demand Gen Kampagnen`, `Display Kampagnen`, `YouTube Kampagnen`, `Shopping Kampagnen`, `Meta Anzeigen`. (Alt-Kanal `merchant_center` existiert noch als Fuerst-Altdaten, wird von Report-Queries ausgeschlossen -- Feature entfernt.)
- Kanal-Scope pro Report (`ChannelScope`: google/meta/all): UI-Radio bzw. CLI `--channels`; Sync holt immer alle konfigurierten Kanaele, gefiltert wird erst beim Report (`ReportData.for_scope`).
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

Aktuell konfiguriert: GCP-Projekt `llm-reporting-493211`, Service Account wiederverwendet aus `/Users/mark.mechling/PycharmProjects/massive-monitoring` (Key liegt gitignored als `service-account.json` im Root).

## Konventionen

- Python 3.14 lokal (venv unter `.venv/`), Container pinnt 3.12 (Wheel-Verfuegbarkeit)
- Deutsche Formatierung: `1.234.567` (Tausender-Punkt), `€ 1.234,56`, `3,52 %`, `01.01.2026`
- Formatierungsfunktionen in `formatting.py` -- kein `locale.setlocale()`
- MASSIVEART CI-Farben: Panel `#1d3c4b` (colorBlueItems), Akzent `#36f5cf` (colorGreenTurquoise), Dunkel `#161b20` (colorGreySeven), Primaer-Gruen `#009d77` (colorGreenHaze)
- Font: GT Walsheim Pro (Light 300 + Black 900)
- Streamlit-UI im MASSIVE ART Look: GT Walsheim via `theme.fontFaces` (Fonts aus `static/`, braucht `server.enableStaticServing`), Basis-/Heading-Gewicht 300, weisses M.-Logo (`logo_m_white.png`, aus `massiveart-logo.jpg` generiert) via `st.logo`
- `[tool.setuptools.package-data]` schliesst `templates/` + `assets/` ins Wheel ein -- ohne den Eintrag fehlen Templates/Fonts im Docker-Image (non-editable install)
- Per-Kunde-Branding: `cover_image` + `client_logo` in der Kunden-YAML (Pfade relativ zum Projekt-Root); MASSIVEART-Logo und CI bleiben fix
- Kundenlogos: transparente PNGs, bevorzugt als weisse Knockout-Variante (Titelseite ist dunkel; das blaue Fürst-Logo war auf dem Cover unleserlich, Original liegt als `logo_blue.png` daneben)
- Purchases sind fraktional (Google Ads data-driven attribution): als Decimal/NUMERIC durch die ganze Pipeline, gerundet wird genau einmal auf Kanal-Ebene via `models.round_conversions` -- nie `int()` auf Zeilen-Ebene (verfaelscht Summen je nach Granularitaet)
- Synchronisierte Tage ohne Aktivitaet bekommen eine `_no_data`-Markerzeile in BigQuery; Kanaele mit `_`-Prefix sind von Report-Queries ausgeschlossen
- Keine Emojis in der UI (Streamlit + CLI)
- ROAS-Berechnung basiert auf tatsaechlichem Umsatz und ergibt sich aus dem Kanal-Scope des Reports (Google-Report -> Google-ROAS usw.); kein `roas_mode` mehr in der Config
- PMAX ROAS wird separat berechnet und auf der Status-Quo-Seite als eigene KPI-Zeile angezeigt -- nur wenn der PMAX-Kanal im Report enthalten ist (entfaellt z.B. bei Meta-only)
- Merchant-Center-Daten (GA4) wurden entfernt (nur Fuerst hatte E-Commerce; alle anderen Kunden sind B2B)
- Conversions-Tabelle zeigt nur Purchase + Umsatz, Kurznamen via `builder.py:CONV_NAME_MAP`
- Google-Ads-Kanalzuordnung: ohne `campaigns`-Patterns in der YAML wird der gesamte Account automatisch nach `advertising_channel_type` kategorisiert (Search/PMax/Display/YouTube/DemandGen/Shopping, Mapping `fetchers/google_ads.py:TYPE_LABELS`) -- Default fuer alle Kunden ausser Fürst. Mit Patterns (z.B. `pmax: ["*PMAX*"]`) werden nur passende Kampagnen berichtet (Kategorien-Mapping `CHANNEL_LABELS`); Patterns duerfen sich nicht ueberlappen (sonst Doppelzaehlung).
- Waehrung pro Kunde via `currency` in der YAML (Default EUR; Thun-Thunersee rechnet in CHF ab); Formatierung inkl. ROAS-Satz passt sich an
- Google Ads Conversion-Action-Namen werden normalisiert (Leerzeichen -> Unterstriche) fuer zuverlaessiges Matching
- UI-Texte auf Deutsch (Streamlit + CLI)

## CLI-Flags

- `--month YYYY-MM` oder `--from/--to YYYY-MM-DD`: Zeitraum (generate + sync)
- `--source live|bq`: Datenquelle fuer generate (Default: live)
- `--channels google|meta|all`: Kanal-Scope fuer generate (Default: all); Dateiname bekommt Suffix `_google`/`_meta`
- `--force`: sync laedt auch bereits vorhandene Tage neu
- `--dry-run`: Nur Daten abrufen, kein PDF
- `--skip-fetch`: Gecachte/Placeholder-Daten, fuer Template-Iteration
- `--output PATH`: Alternatives Output-Verzeichnis

## Credentials

Ueber `.env` (gitignored). Vorlage: `.env.example`.

- **Google Ads:** OAuth-Credentials (Client ID, Secret, Refresh Token). Der Refresh Token hat Scopes fuer `adwords` und `analytics.readonly` (Analytics-Scope historisch, wird nicht mehr genutzt).
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
