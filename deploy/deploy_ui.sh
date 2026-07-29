#!/usr/bin/env bash
# Streamlit-UI als Cloud-Run-Service deployen, geschuetzt via IAP
# (Google-Login, Zugriff fuer $IAP_MEMBER). Idempotent.
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

echo "=== Cloud Run Service ==="
# Streamlit haelt WebSocket-Verbindungen -> Session Affinity
gcloud run deploy "$UI_SERVICE" \
  --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE:latest" \
  --service-account "$RUNNER_SA" \
  --no-allow-unauthenticated \
  --session-affinity \
  --port 8080 \
  --cpu 1 --memory 2Gi \
  --min-instances 0 --max-instances 3 \
  --timeout 600 \
  --set-env-vars "^|^$ENV_COMMON" \
  --set-secrets "$SECRETS"

echo "=== IAP aktivieren ==="
# IAP-Service-Agent anlegen und ihm erlauben, den Service aufzurufen
gcloud beta services identity create --service=iap.googleapis.com \
  --project "$PROJECT" >/dev/null 2>&1 || true
IAP_SA="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"
gcloud run services add-iam-policy-binding "$UI_SERVICE" \
  --project "$PROJECT" --region "$REGION" \
  --member="serviceAccount:$IAP_SA" --role=roles/run.invoker -q >/dev/null

gcloud beta run services update "$UI_SERVICE" \
  --project "$PROJECT" --region "$REGION" --iap

echo "=== IAP-Zugriff fuer $IAP_MEMBER ==="
gcloud beta iap web add-iam-policy-binding \
  --project "$PROJECT" \
  --resource-type=cloud-run --service="$UI_SERVICE" --region="$REGION" \
  --member="$IAP_MEMBER" --role=roles/iap.httpsResourceAccessor

URL=$(gcloud run services describe "$UI_SERVICE" --project "$PROJECT" \
  --region "$REGION" --format="value(status.url)")
echo "Fertig: $URL"
