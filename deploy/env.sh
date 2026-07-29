#!/usr/bin/env bash
# Gemeinsame Variablen fuer alle Deploy-Skripte (Muster: geo-monitor).
set -euo pipefail

PROJECT="llm-reporting-493211"
PROJECT_NUMBER="1050864803780"
REGION="europe-west3"
AR_REPO="gro-reporting"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${AR_REPO}/app"
RUNNER_SA="gro-runner@${PROJECT}.iam.gserviceaccount.com"
SCHEDULER_SA="gro-scheduler@${PROJECT}.iam.gserviceaccount.com"
UI_SERVICE="gro-reporting"
NOTIFY_EMAIL="mark.mechling@massiveart.com"
# Wer die UI nutzen darf (IAP): gesamte MASSIVE ART Google-Workspace-Domain
IAP_MEMBER="domain:massiveart.com"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Wert einer Variable aus einer .env-Datei lesen (ohne export/Quotes)
env_val() {
  local file="$1" key="$2"
  grep -E "^${key}=" "$file" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"
}
