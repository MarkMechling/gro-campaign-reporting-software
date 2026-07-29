#!/usr/bin/env bash
# API-Credentials aus der lokalen .env in den Secret Manager schreiben.
# Werte werden gepiped, nie geechot. Wiederholtes Ausfuehren legt neue
# Versionen an (Jobs referenzieren :latest — Rotation = Skript neu ausfuehren).
set -euo pipefail
source "$(dirname "$0")/env.sh"

GRO_ENV="$ROOT/.env"

put_secret() {
  local name="$1" key="$2"
  local value
  value=$(env_val "$GRO_ENV" "$key")
  if [ -z "$value" ]; then
    echo "SKIP $name — $key ist leer in $GRO_ENV" >&2
    return 0
  fi
  gcloud secrets describe "$name" --project "$PROJECT" >/dev/null 2>&1 \
    || gcloud secrets create "$name" --project "$PROJECT" \
         --replication-policy=user-managed --locations="$REGION"
  printf '%s' "$value" | gcloud secrets versions add "$name" \
    --project "$PROJECT" --data-file=-
  echo "OK $name"
}

put_secret google-ads-developer-token GOOGLE_ADS_DEVELOPER_TOKEN
put_secret google-ads-client-id       GOOGLE_ADS_CLIENT_ID
put_secret google-ads-client-secret   GOOGLE_ADS_CLIENT_SECRET
put_secret google-ads-refresh-token   GOOGLE_ADS_REFRESH_TOKEN
put_secret meta-app-secret            META_APP_SECRET
put_secret meta-access-token          META_ACCESS_TOKEN
