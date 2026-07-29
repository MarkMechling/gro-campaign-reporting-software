#!/usr/bin/env bash
# Einmaliges Infrastruktur-Setup. Idempotent — gefahrlos wiederholbar.
# Erstellt: APIs, Service Accounts, IAM-Bindings, Artifact-Registry-Repo.
# Keine SA-Keys in der Cloud: der Runner-SA nutzt ADC.
set -euo pipefail
source "$(dirname "$0")/env.sh"

echo "=== APIs ==="
gcloud services enable \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  monitoring.googleapis.com \
  iap.googleapis.com \
  --project "$PROJECT"

echo "=== Service Accounts ==="
gcloud iam service-accounts describe "$RUNNER_SA" --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud iam service-accounts create gro-runner --project "$PROJECT" \
       --display-name="GRO Reporting Laufzeit (Sync-Jobs + UI)"
gcloud iam service-accounts describe "$SCHEDULER_SA" --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud iam service-accounts create gro-scheduler --project "$PROJECT" \
       --display-name="GRO Reporting Scheduler-Trigger"

# Frisch erstellte SAs sind eventually consistent
sleep 15

echo "=== IAM ==="
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$RUNNER_SA" \
  --role=roles/bigquery.jobUser --condition=None -q >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$RUNNER_SA" \
  --role=roles/bigquery.dataEditor --condition=None -q >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$RUNNER_SA" \
  --role=roles/secretmanager.secretAccessor --condition=None -q >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$SCHEDULER_SA" \
  --role=roles/run.invoker --condition=None -q >/dev/null

echo "=== Artifact Registry ==="
gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" \
  --project "$PROJECT" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "$AR_REPO" --repository-format=docker \
       --location "$REGION" --project "$PROJECT" \
       --description="GRO Reporting Images"

echo "Fertig. Weiter mit: create_secrets.sh -> build_push.sh -> create_jobs.sh -> deploy_ui.sh -> alerting.sh"
