#!/usr/bin/env bash
# Image mit Cloud Build bauen und in die Artifact Registry pushen.
# .gcloudignore haelt .env und *.json (SA-Key) aus dem Build-Kontext;
# clients/ und assets/ werden bewusst mit hochgeladen (ins Image gebacken) —
# nach Aenderungen an Kunden-YAMLs/Assets also neu bauen + deploy_ui.sh.
set -euo pipefail
source "$(dirname "$0")/env.sh"

cd "$ROOT"
if [ ! -f .gcloudignore ]; then
  echo "FATAL: .gcloudignore fehlt — der Build wuerde .env und Keys hochladen" >&2
  exit 1
fi

# Test-Gate (22.09.2026, Muster geo-monitor): die Sync-Jobs loesen :latest
# beim Start jeder Execution auf — ein gepushtes Image laeuft ohne Re-Deploy
# beim naechsten gro-sync-daily (05:00). Kaputter Build = kaputter Sync, daher
# erst die Suite. Ueberspringen nur mit SKIP_TESTS=1.
PY="${PYTHON:-$ROOT/.venv/bin/python}"
if [ "${SKIP_TESTS:-0}" != "1" ]; then
  echo "=== pytest (tests/) ==="
  if ! "$PY" -m pytest tests -q; then
    echo "FATAL: Tests fehlgeschlagen — Image nicht gebaut" >&2
    exit 1
  fi
fi

gcloud builds submit --project "$PROJECT" --region "$REGION" \
  --tag "$IMAGE:latest" .

echo "Image gepusht: $IMAGE:latest"
echo "Sync-Jobs: ab der naechsten Execution live (Tag wird zur Laufzeit aufgeloest, verifiziert 22.09.2026)."
echo "UI-Service: erst nach ./deploy/deploy_ui.sh (Revision pinnt den Digest) — direkt ausfuehren."
echo "create_jobs.sh nur bei Aenderungen an Job-Einstellungen (Args, Env, Secrets, Ressourcen, Scheduler)."
