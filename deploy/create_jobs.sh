#!/usr/bin/env bash
# Sync-Jobs + Scheduler anlegen/aktualisieren. Idempotent.
#
# gro-sync-daily:   taeglich 05:00 Wien — letzte 7 Tage --force (faengt
#                   Googles nachtraegliche Conversion-Restatements laufend ein)
# gro-sync-monthly: am 3. des Monats 05:30 Wien — kompletter Vormonat --force
set -euo pipefail
source "$(dirname "$0")/env.sh"

GRO_ENV="$ROOT/.env"

ENV_COMMON="GRO_BQ_PROJECT=$PROJECT"
ENV_COMMON="$ENV_COMMON|GRO_BQ_DATASET=gro_reporting"
ENV_COMMON="$ENV_COMMON|GRO_BQ_LOCATION=EU"
ENV_COMMON="$ENV_COMMON|GOOGLE_ADS_LOGIN_CUSTOMER_ID=$(env_val "$GRO_ENV" GOOGLE_ADS_LOGIN_CUSTOMER_ID)"
ENV_COMMON="$ENV_COMMON|META_APP_ID=$(env_val "$GRO_ENV" META_APP_ID)"

SECRETS="GOOGLE_ADS_DEVELOPER_TOKEN=google-ads-developer-token:latest"
SECRETS="$SECRETS,GOOGLE_ADS_CLIENT_ID=google-ads-client-id:latest"
SECRETS="$SECRETS,GOOGLE_ADS_CLIENT_SECRET=google-ads-client-secret:latest"
SECRETS="$SECRETS,GOOGLE_ADS_REFRESH_TOKEN=google-ads-refresh-token:latest"
SECRETS="$SECRETS,META_APP_SECRET=meta-app-secret:latest"
SECRETS="$SECRETS,META_ACCESS_TOKEN=meta-access-token:latest"

deploy_job() {
  local name="$1" timeout="$2" args="$3"
  gcloud run jobs deploy "$name" \
    --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE:latest" \
    --command gro-report \
    --args "$args" \
    --tasks 1 --parallelism 1 --max-retries 1 \
    --task-timeout "$timeout" \
    --cpu 1 --memory 2Gi \
    --service-account "$RUNNER_SA" \
    --set-env-vars "^|^$ENV_COMMON" \
    --set-secrets "$SECRETS"
}

echo "=== Cloud Run Jobs ==="
deploy_job gro-sync-daily   1h "sync,all,--last-days,7,--force"
deploy_job gro-sync-monthly 2h "sync,all,--previous-month,--force"

upsert_scheduler() {
  local name="$1" schedule="$2" job="$3"
  local uri="https://run.googleapis.com/v2/projects/$PROJECT/locations/$REGION/jobs/$job:run"
  if gcloud scheduler jobs describe "$name" --location "$REGION" \
       --project "$PROJECT" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "$name" --location "$REGION" \
      --project "$PROJECT" \
      --schedule "$schedule" --time-zone "Europe/Vienna" --uri "$uri"
  else
    gcloud scheduler jobs create http "$name" --location "$REGION" \
      --project "$PROJECT" \
      --schedule "$schedule" --time-zone "Europe/Vienna" \
      --uri "$uri" --http-method POST \
      --oauth-service-account-email "$SCHEDULER_SA" \
      --attempt-deadline 180s
  fi
}

echo "=== Scheduler (Europe/Vienna) ==="
upsert_scheduler gro-sync-daily-trigger   "0 5 * * *"  gro-sync-daily
upsert_scheduler gro-sync-monthly-trigger "30 5 3 * *" gro-sync-monthly

echo "Fertig."
