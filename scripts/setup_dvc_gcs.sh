#!/usr/bin/env bash
set -euo pipefail

REMOTE_NAME="${DVC_REMOTE_NAME:-gcsremote}"
BUCKET="${DVC_BUCKET:-YOUR_PRIVATE_BUCKET}"
DVC_BIN="${DVC_BIN:-.venv/bin/dvc}"
SITE_CACHE_DIR="${DVC_SITE_CACHE_DIR:-$PWD/.dvc/tmp/site-cache}"
CREDENTIAL_PATH="${DVC_GCS_CREDENTIALPATH:-${GOOGLE_APPLICATION_CREDENTIALS:-}}"

if [[ -n "${DVC_REMOTE_URL:-}" ]]; then
  REMOTE_URL="$DVC_REMOTE_URL"
else
  BUCKET="${BUCKET#gs://}"
  BUCKET="${BUCKET%/}"
  BUCKET="${BUCKET%/dvc}"
  REMOTE_URL="gs://${BUCKET}/dvc"
fi

if [[ "$REMOTE_URL" == "gs://YOUR_PRIVATE_BUCKET/dvc" ]]; then
  echo "Set DVC_BUCKET or DVC_REMOTE_URL before running this script."
  echo "Example:"
  echo "  DVC_BUCKET=YOUR_PRIVATE_BUCKET scripts/setup_dvc_gcs.sh"
  echo "  DVC_REMOTE_URL=gs://YOUR_PRIVATE_BUCKET/dvc scripts/setup_dvc_gcs.sh"
  exit 2
fi

if [[ "$REMOTE_URL" != gs://* || "$REMOTE_URL" == *"gs://gs://"* ]]; then
  echo "Invalid DVC remote URL: $REMOTE_URL"
  echo "Use DVC_BUCKET without gs://, or use DVC_REMOTE_URL with a full gs://.../dvc URL."
  exit 2
fi

if [[ -n "$CREDENTIAL_PATH" && ! -f "$CREDENTIAL_PATH" ]]; then
  echo "Credential file does not exist:"
  echo "  $CREDENTIAL_PATH"
  exit 2
fi

if [[ ! -x "$DVC_BIN" ]]; then
  DVC_BIN="$(command -v dvc || true)"
fi

if [[ -z "$DVC_BIN" || ! -x "$DVC_BIN" ]]; then
  echo "dvc is not installed in this environment."
  echo "Install it with:"
  echo "  poetry install --with dev,modeling,data-versioning"
  exit 2
fi

if [[ ! -d .git ]]; then
  echo "Run this from the repository root."
  exit 2
fi

mkdir -p "$SITE_CACHE_DIR"
export DVC_SITE_CACHE_DIR="$SITE_CACHE_DIR"

if [[ ! -d .dvc ]]; then
  "$DVC_BIN" init
else
  echo "DVC is already initialized."
fi

"$DVC_BIN" config --local core.site_cache_dir "$SITE_CACHE_DIR"

if "$DVC_BIN" remote list | awk '{print $1}' | grep -Fxq "$REMOTE_NAME"; then
  "$DVC_BIN" remote modify --local "$REMOTE_NAME" url "$REMOTE_URL"
else
  "$DVC_BIN" remote add --local -d "$REMOTE_NAME" "$REMOTE_URL"
fi

if [[ -n "$CREDENTIAL_PATH" ]]; then
  "$DVC_BIN" remote modify --local "$REMOTE_NAME" credentialpath "$CREDENTIAL_PATH"
fi

"$DVC_BIN" remote default --local "$REMOTE_NAME"

echo "DVC remote configured:"
"$DVC_BIN" remote list
echo
echo "The real remote URL is stored in .dvc/config.local."
if [[ -n "$CREDENTIAL_PATH" ]]; then
  echo "The service-account credential path is stored in .dvc/config.local."
fi
echo "The local DVC state cache is stored under .dvc/tmp/site-cache."
echo "Do not commit .dvc/config.local or credentials."
