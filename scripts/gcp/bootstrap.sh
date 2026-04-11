#!/usr/bin/env bash
# One-time GCP API enablement and reminders. Requires gcloud and a configured project.
# Usage: GCP_PROJECT_ID=my-proj GCP_REGION=us-central1 ./scripts/gcp/bootstrap.sh
set -euo pipefail

PROJECT="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"

echo "Using project=${PROJECT} region=${REGION}"

gcloud config set project "${PROJECT}"

APIS=(
  run.googleapis.com
  artifactregistry.googleapis.com
  sqladmin.googleapis.com
  secretmanager.googleapis.com
  vpcaccess.googleapis.com
  redis.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  cloudresourcemanager.googleapis.com
  servicenetworking.googleapis.com
)

gcloud services enable "${APIS[@]}"

echo "
Done enabling APIs.

Next (Console or gcloud — not automated here):
  1) Serverless VPC Access connector in ${REGION} (same VPC as Memorystore).
  2) Cloud SQL for PostgreSQL instance + database + user; note instance connection name project:region:instance.
  3) Memorystore (Redis) on that VPC; note host IP and port.
  4) Artifact Registry Docker repository in ${REGION}.
  5) Runtime service account: roles/cloudsql.client, roles/secretmanager.secretAccessor, VPC access via connector.
  6) GitHub Actions deployer SA + Workload Identity Federation (pool + provider) mapping your repo to that SA.
     Grant deploy SA at least: roles/run.admin, roles/artifactregistry.writer, roles/iam.serviceAccountUser on the runtime SA, roles/run.developer (or admin) for Cloud Run Jobs.
  7) Secret Manager secrets (e.g. django-secret-key, database-url, api-key-pepper, celery-broker-url, celery-result-backend).

See .github/workflows/deploy-gcp.yml for variable/secret names expected by CI.
"
