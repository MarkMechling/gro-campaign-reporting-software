#!/usr/bin/env bash
# E-Mail-Notification-Channel + Alert bei fehlgeschlagenen Job-Executions.
# Idempotent — ueberspringt Vorhandenes.
set -euo pipefail
source "$(dirname "$0")/env.sh"

echo "=== Notification Channel ==="
channel=$(gcloud beta monitoring channels list --project "$PROJECT" \
  --filter="type=\"email\" AND labels.email_address=\"$NOTIFY_EMAIL\"" \
  --format="value(name)" | head -1)
if [ -z "$channel" ]; then
  channel=$(gcloud beta monitoring channels create --project "$PROJECT" \
    --display-name="GRO Ops — Mark (E-Mail)" --type=email \
    --channel-labels="email_address=$NOTIFY_EMAIL" --format="value(name)")
fi
echo "Channel: $channel"

echo "=== Alert Policy ==="
existing=$(gcloud alpha monitoring policies list --project "$PROJECT" \
  --filter='displayName="GRO Reporting — Cloud Run Job fehlgeschlagen"' \
  --format="value(name)" | head -1)
if [ -n "$existing" ]; then
  echo "Alert Policy existiert bereits: $existing"
  exit 0
fi

tmp=$(mktemp)
sed "s|CHANNEL_NAME_PLACEHOLDER|$channel|" \
  "$(dirname "$0")/alert_policy.json" > "$tmp"
gcloud alpha monitoring policies create --project "$PROJECT" \
  --policy-from-file="$tmp"
rm -f "$tmp"
echo "Alert Policy angelegt."
