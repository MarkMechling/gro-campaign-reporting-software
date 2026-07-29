#!/usr/bin/env bash
# Image mit Cloud Build bauen und in die Artifact Registry pushen.
# .gcloudignore haelt .env und *.json (SA-Key) aus dem Build-Kontext;
# clients/ und assets/ werden bewusst mit hochgeladen (ins Image gebacken) —
# nach Aenderungen an Kunden-YAMLs/Assets also neu bauen + deployen.
set -euo pipefail
source "$(dirname "$0")/env.sh"

cd "$ROOT"
if [ ! -f .gcloudignore ]; then
  echo "FATAL: .gcloudignore fehlt — der Build wuerde .env und Keys hochladen" >&2
  exit 1
fi

gcloud builds submit --project "$PROJECT" --region "$REGION" \
  --tag "$IMAGE:latest" .

echo "Image gepusht: $IMAGE:latest"
echo "Jobs/Service uebernehmen es erst nach erneutem create_jobs.sh / deploy_ui.sh."
