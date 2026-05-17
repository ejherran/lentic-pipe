#!/usr/bin/env bash
set -euo pipefail

check_bucket=0
if [[ "${1:-}" == "--check-bucket" ]]; then
  check_bucket=1
fi

credential_path="${DVC_GCS_CREDENTIALPATH:-${GOOGLE_APPLICATION_CREDENTIALS:-}}"
credential_source=""

if [[ -n "$credential_path" ]]; then
  if [[ ! -f "$credential_path" ]]; then
    echo "A Google credential path is set, but the file does not exist."
    echo "Current value points to:"
    echo "  $credential_path"
    exit 2
  fi
  if [[ -n "${DVC_GCS_CREDENTIALPATH:-}" ]]; then
    credential_source="DVC_GCS_CREDENTIALPATH"
  else
    credential_source="GOOGLE_APPLICATION_CREDENTIALS"
  fi
  echo "OK: $credential_source points to an existing credential file."
else
  credential_source="ADC"
fi

if [[ "$credential_source" == "ADC" ]] && ! command -v gcloud >/dev/null 2>&1; then
  echo "No ADC found and gcloud is not installed or not on PATH."
  echo
  echo "Install Google Cloud CLI, then run:"
  echo "  gcloud auth application-default login"
  echo "  gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID"
  echo
  echo "Alternative: set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON file outside the repo."
  exit 2
fi

if [[ "$credential_source" == "ADC" ]] && ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo "Google Application Default Credentials are not configured."
  echo
  echo "Run:"
  echo "  gcloud auth application-default login"
  echo "  gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID"
  echo
  echo "Then rerun:"
  echo "  scripts/check_gcs_credentials.sh"
  exit 2
fi

if [[ "$credential_source" == "ADC" ]]; then
  echo "OK: Google Application Default Credentials are available."
fi

if (( check_bucket == 0 )); then
  exit 0
fi

remote_url="${DVC_REMOTE_URL:-}"
if [[ -z "$remote_url" && -n "${DVC_BUCKET:-}" ]]; then
  bucket="${DVC_BUCKET#gs://}"
  bucket="${bucket%/}"
  bucket="${bucket%/dvc}"
  remote_url="gs://${bucket}/dvc"
fi

if [[ -z "$remote_url" ]]; then
  echo "Skipping bucket access check. Set DVC_BUCKET or DVC_REMOTE_URL to check remote access."
  exit 0
fi

if [[ "$credential_source" != "ADC" ]]; then
  echo "Skipping bucket access check here because gcloud does not use the JSON key automatically."
  echo "Run setup_dvc_gcs.sh with DVC_GCS_CREDENTIALPATH, then verify with:"
  echo "  .venv/bin/dvc push"
  echo "or activate the service account in gcloud before using --check-bucket."
  exit 0
fi

if gcloud storage ls "$remote_url" >/dev/null 2>&1; then
  echo "OK: credentials can access the configured DVC GCS remote."
else
  echo "Credentials exist, but bucket access check failed."
  echo "Verify project, bucket permissions, and that the DVC remote path exists or can be created."
  exit 2
fi
