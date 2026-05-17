#!/usr/bin/env bash
set -euo pipefail

COMMAND="${1:-wizard}"
if [[ $# -gt 0 ]]; then
  shift
fi

REMOTE_NAME="${DVC_REMOTE_NAME:-gcsremote}"
DVC_BIN="${DVC_BIN:-.venv/bin/dvc}"
SITE_CACHE_DIR="${DVC_SITE_CACHE_DIR:-$PWD/.dvc/tmp/site-cache}"
BUCKET="${DVC_BUCKET:-}"
REMOTE_URL="${DVC_REMOTE_URL:-}"
CREDENTIAL_PATH="${DVC_GCS_CREDENTIALPATH:-${GOOGLE_APPLICATION_CREDENTIALS:-}}"
JOBS="${DVC_JOBS:-}"
TARGETS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/dvc_data_assistant.sh wizard
  scripts/dvc_data_assistant.sh setup --bucket YOUR_PRIVATE_BUCKET --credentialpath /path/key.json
  scripts/dvc_data_assistant.sh pull --bucket YOUR_PRIVATE_BUCKET --credentialpath /path/key.json
  scripts/dvc_data_assistant.sh push --bucket YOUR_PRIVATE_BUCKET --credentialpath /path/key.json
  scripts/dvc_data_assistant.sh status
  scripts/dvc_data_assistant.sh doctor

Commands:
  wizard   Interactive local setup for a new machine.
  setup    Configure local DVC remote/cache/credentials only.
  pull     Configure if needed, then download DVC-tracked data.
  push     Configure if needed, run publication checks, then upload DVC data.
  status   Show DVC status.
  doctor   Check repo, credentials, DVC config, and DVC status.

Options:
  --bucket NAME             Bucket name only, without gs://.
  --remote-url URL          Full DVC remote URL, for example gs://YOUR_PRIVATE_BUCKET/dvc.
  --credentialpath PATH     Service-account JSON path, kept in .dvc/config.local.
  --jobs N                  DVC transfer jobs.
  --target PATH             Limit pull/push to a DVC target. Can be repeated.

Environment equivalents:
  DVC_BUCKET, DVC_REMOTE_URL, DVC_GCS_CREDENTIALPATH, DVC_JOBS, DVC_BIN.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket)
      BUCKET="${2:?Missing value for --bucket}"
      shift 2
      ;;
    --remote-url)
      REMOTE_URL="${2:?Missing value for --remote-url}"
      shift 2
      ;;
    --credentialpath)
      CREDENTIAL_PATH="${2:?Missing value for --credentialpath}"
      shift 2
      ;;
    --jobs)
      JOBS="${2:?Missing value for --jobs}"
      shift 2
      ;;
    --target)
      TARGETS+=("${2:?Missing value for --target}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 2
      ;;
  esac
done

ensure_repo_root() {
  if [[ ! -d .git ]]; then
    echo "Run this from the repository root."
    exit 2
  fi
}

resolve_dvc_bin() {
  if [[ ! -x "$DVC_BIN" ]]; then
    DVC_BIN="$(command -v dvc || true)"
  fi
  if [[ -z "$DVC_BIN" || ! -x "$DVC_BIN" ]]; then
    echo "DVC is not installed in this environment."
    echo "Install the project environment first:"
    echo "  poetry install --with dev,modeling,data-versioning"
    exit 2
  fi
}

export_runtime_env() {
  mkdir -p "$SITE_CACHE_DIR"
  export DVC_SITE_CACHE_DIR="$SITE_CACHE_DIR"
  if [[ -n "$BUCKET" ]]; then
    export DVC_BUCKET="$BUCKET"
  fi
  if [[ -n "$REMOTE_URL" ]]; then
    export DVC_REMOTE_URL="$REMOTE_URL"
  fi
  if [[ -n "$CREDENTIAL_PATH" ]]; then
    export DVC_GCS_CREDENTIALPATH="$CREDENTIAL_PATH"
  fi
  if [[ -n "$JOBS" ]]; then
    export DVC_JOBS="$JOBS"
  fi
}

configure_if_requested() {
  if [[ -n "$BUCKET" || -n "$REMOTE_URL" || -n "$CREDENTIAL_PATH" ]]; then
    scripts/setup_dvc_gcs.sh
  fi
}

require_configured_remote_for_transfer() {
  if [[ ! -f .dvc/config.local && -z "$BUCKET" && -z "$REMOTE_URL" ]]; then
    echo "No local DVC remote configuration found."
    echo "Run one of:"
    echo "  scripts/dvc_data_assistant.sh wizard"
    echo "  scripts/dvc_data_assistant.sh setup --bucket YOUR_PRIVATE_BUCKET --credentialpath /path/key.json"
    exit 2
  fi
}

configured_credential_path() {
  if [[ -n "$CREDENTIAL_PATH" ]]; then
    printf '%s\n' "$CREDENTIAL_PATH"
    return
  fi
  "$DVC_BIN" config "remote.${REMOTE_NAME}.credentialpath" 2>/dev/null || true
}

dvc_transfer_args() {
  if [[ -n "$JOBS" ]]; then
    printf '%s\n' "--jobs"
    printf '%s\n' "$JOBS"
  fi
  for target in "${TARGETS[@]}"; do
    printf '%s\n' "$target"
  done
}

cmd_wizard() {
  ensure_repo_root
  resolve_dvc_bin

  echo "DVC data assistant"
  echo
  echo "This writes machine-specific settings only to .dvc/config.local."
  echo "Use placeholders in committed docs and keep credential JSON files out of Git."
  echo

  if [[ -z "$BUCKET" && -z "$REMOTE_URL" ]]; then
    read -r -p "Private GCS bucket name, without gs://: " BUCKET
  fi
  if [[ -z "$CREDENTIAL_PATH" ]]; then
    read -r -p "Service-account JSON path, blank to use ADC: " CREDENTIAL_PATH
  fi

  export_runtime_env
  scripts/check_gcs_credentials.sh
  scripts/setup_dvc_gcs.sh
  "$DVC_BIN" status

  echo
  echo "Setup complete. To download data on this machine:"
  echo "  scripts/dvc_data_assistant.sh pull"
}

cmd_setup() {
  ensure_repo_root
  resolve_dvc_bin
  export_runtime_env
  scripts/check_gcs_credentials.sh
  scripts/setup_dvc_gcs.sh
  "$DVC_BIN" status
}

cmd_pull() {
  ensure_repo_root
  resolve_dvc_bin
  export_runtime_env
  configure_if_requested
  require_configured_remote_for_transfer
  "$DVC_BIN" status
  mapfile -t transfer_args < <(dvc_transfer_args)
  "$DVC_BIN" pull "${transfer_args[@]}"
}

cmd_push() {
  ensure_repo_root
  resolve_dvc_bin
  export_runtime_env
  configure_if_requested
  require_configured_remote_for_transfer
  scripts/check_repo_publication_ready.sh
  "$DVC_BIN" status
  mapfile -t transfer_args < <(dvc_transfer_args)
  "$DVC_BIN" push "${transfer_args[@]}"
  scripts/check_repo_publication_ready.sh
}

cmd_status() {
  ensure_repo_root
  resolve_dvc_bin
  export_runtime_env
  "$DVC_BIN" status
}

cmd_doctor() {
  ensure_repo_root
  resolve_dvc_bin
  export_runtime_env

  echo "Checking publication guard..."
  scripts/check_repo_publication_ready.sh

  echo
  echo "Checking DVC binary..."
  "$DVC_BIN" --version

  echo
  if [[ -f .dvc/config.local ]]; then
    echo "OK: local DVC config exists at .dvc/config.local."
  else
    echo "WARN: .dvc/config.local does not exist. Run setup or wizard before pull/push."
  fi

  local configured_credential
  configured_credential="$(configured_credential_path)"
  if [[ -n "$configured_credential" ]]; then
    DVC_GCS_CREDENTIALPATH="$configured_credential" scripts/check_gcs_credentials.sh
  else
    scripts/check_gcs_credentials.sh
  fi

  echo
  echo "Checking DVC status..."
  "$DVC_BIN" status
}

case "$COMMAND" in
  wizard)
    cmd_wizard
    ;;
  setup)
    cmd_setup
    ;;
  pull)
    cmd_pull
    ;;
  push)
    cmd_push
    ;;
  status)
    cmd_status
    ;;
  doctor)
    cmd_doctor
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $COMMAND"
    usage
    exit 2
    ;;
esac
