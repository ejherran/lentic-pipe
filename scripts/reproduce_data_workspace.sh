#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
DVC_BIN="${DVC_BIN:-.venv/bin/dvc}"
RUN_PULL=0
RUN_DVC_STATUS=1
RUN_FULL_REBUILD=0
ALLOW_PATH_SET_CHANGE=0
RUN_PYTEST=0
RUN_TY=0

DERIVED_MANIFEST="data/freeze/derived_file_manifest_v0.csv"
REFERENCE_PATHS_FILE=""
NEW_PATHS_FILE=""

usage() {
  cat <<'EOF'
Usage:
  scripts/reproduce_data_workspace.sh [options]

Purpose:
  Rebuild all lightweight, reproducible workspace artifacts after DVC has been
  configured and data has been restored. This is the recommended post-pull
  recovery command for a new machine.

Default workflow:
  1. Check DVC status.
  2. Validate source metadata.
  3. Regenerate raw source manifests with hash reuse when possible.
  4. Regenerate canonical observation summaries.
  5. Regenerate the data freeze.
  6. Verify expected regenerated files exist.
  7. Fail if the derived-manifest path set changed unexpectedly.

Options:
  --pull                   Run scripts/dvc_data_assistant.sh pull first.
  --full-rebuild           Rebuild heavy derived data from raw inputs before the
                           lightweight recovery steps. This can take hours.
  --allow-path-set-change  Do not fail when the derived manifest gains or loses
                           paths. Use only for intentional freeze changes.
  --skip-dvc-status        Do not run the initial DVC status check.
  --pytest                 Run poetry run pytest after regeneration.
  --ty                     Run poetry run ty check after regeneration.
  -h, --help               Show this help.

Environment:
  PYTHON_BIN               Python executable. Default: .venv/bin/python
  DVC_BIN                  DVC executable. Default: .venv/bin/dvc
EOF
}

cleanup() {
  if [[ -n "$REFERENCE_PATHS_FILE" && -f "$REFERENCE_PATHS_FILE" ]]; then
    rm -f "$REFERENCE_PATHS_FILE"
  fi
  if [[ -n "$NEW_PATHS_FILE" && -f "$NEW_PATHS_FILE" ]]; then
    rm -f "$NEW_PATHS_FILE"
  fi
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pull)
      RUN_PULL=1
      shift
      ;;
    --full-rebuild)
      RUN_FULL_REBUILD=1
      shift
      ;;
    --allow-path-set-change)
      ALLOW_PATH_SET_CHANGE=1
      shift
      ;;
    --skip-dvc-status)
      RUN_DVC_STATUS=0
      shift
      ;;
    --pytest)
      RUN_PYTEST=1
      shift
      ;;
    --ty)
      RUN_TY=1
      shift
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

if [[ ! -d .git ]]; then
  echo "Run this from the repository root."
  exit 2
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python || true)"
fi
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "Python is not available. Install the project environment first:"
  echo "  poetry install --with dev,modeling,sources,data-versioning"
  exit 2
fi

if [[ ! -x "$DVC_BIN" ]]; then
  DVC_BIN="$(command -v dvc || true)"
fi

run_step() {
  local label="$1"
  shift
  echo
  echo "==> $label"
  "$@"
}

capture_reference_paths() {
  if (( ALLOW_PATH_SET_CHANGE == 1 )); then
    return
  fi
  if [[ ! -f "$DERIVED_MANIFEST" ]]; then
    return
  fi
  REFERENCE_PATHS_FILE="$(mktemp)"
  awk -F, 'NR > 1 { sub(/\r$/, "", $2); print $2 }' "$DERIVED_MANIFEST" | sort > "$REFERENCE_PATHS_FILE"
}

verify_manifest_path_set() {
  if (( ALLOW_PATH_SET_CHANGE == 1 )); then
    return
  fi
  if [[ -z "$REFERENCE_PATHS_FILE" || ! -f "$REFERENCE_PATHS_FILE" ]]; then
    return
  fi
  if [[ ! -f "$DERIVED_MANIFEST" ]]; then
    echo "Missing regenerated derived manifest: $DERIVED_MANIFEST"
    exit 1
  fi

  NEW_PATHS_FILE="$(mktemp)"
  awk -F, 'NR > 1 { sub(/\r$/, "", $2); print $2 }' "$DERIVED_MANIFEST" | sort > "$NEW_PATHS_FILE"

  local missing_paths added_paths
  missing_paths="$(comm -23 "$REFERENCE_PATHS_FILE" "$NEW_PATHS_FILE" || true)"
  added_paths="$(comm -13 "$REFERENCE_PATHS_FILE" "$NEW_PATHS_FILE" || true)"

  if [[ -n "$missing_paths" || -n "$added_paths" ]]; then
    echo
    echo "Derived manifest path set changed."
    if [[ -n "$missing_paths" ]]; then
      echo
      echo "Missing paths:"
      printf '%s\n' "$missing_paths"
    fi
    if [[ -n "$added_paths" ]]; then
      echo
      echo "Added paths:"
      printf '%s\n' "$added_paths"
    fi
    echo
    echo "If this is intentional, rerun with --allow-path-set-change and document the new freeze."
    exit 1
  fi

  echo "OK: derived manifest path set is unchanged."
}

verify_expected_outputs() {
  local expected_paths=(
    "data/catalog/raw_file_manifest.csv"
    "data/catalog/source_catalog.json"
    "reports/data/source_inventory.md"
    "data/interim/observations/observations_summary.csv"
    "reports/data/observations_report.md"
    "data/freeze/derived_file_manifest_v0.csv"
    "data/freeze/data_freeze_manifest_v0.json"
    "data/freeze/DATA_FREEZE.md"
  )

  local missing=()
  for path in "${expected_paths[@]}"; do
    if [[ ! -f "$path" ]]; then
      missing+=("$path")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    echo
    echo "Missing expected regenerated files:"
    printf '  %s\n' "${missing[@]}"
    exit 1
  fi

  echo "OK: expected regenerated files exist."
}

if (( RUN_PULL == 1 )); then
  run_step "Pull DVC data" scripts/dvc_data_assistant.sh pull
fi

if (( RUN_DVC_STATUS == 1 )); then
  if [[ -z "$DVC_BIN" || ! -x "$DVC_BIN" ]]; then
    echo "DVC is not available. Install the data-versioning dependency group first."
    exit 2
  fi
  run_step "Check DVC workspace status" "$DVC_BIN" status
fi

capture_reference_paths

if (( RUN_FULL_REBUILD == 1 )); then
  echo
  echo "Full rebuild requested. This can take hours and rewrites heavy DVC-managed artifacts."
  run_step "Rebuild LakeBeD-US-CSE canonical observations" "$PYTHON_BIN" src/data/build_observations.py --source lakebed_us_cse --chunksize 250000 --overwrite
  run_step "Rebuild AquaMatch canonical observations" "$PYTHON_BIN" src/data/build_observations.py --source aquamatch_chla --chunksize 250000 --overwrite
  run_step "Rebuild WQP canonical observations" "$PYTHON_BIN" src/data/build_observations.py --source wqp --chunksize 250000 --overwrite
  run_step "Rebuild site registry" "$PYTHON_BIN" src/data/site_registry.py
  run_step "Rebuild monthly panel" "$PYTHON_BIN" src/data/build_panel.py --overwrite --progress-every-parts 25
  run_step "Rebuild targets" "$PYTHON_BIN" src/data/build_targets.py --overwrite
  run_step "Rebuild panel diagnostics" "$PYTHON_BIN" src/data/diagnose_panel_targets.py --overwrite
fi

run_step "Validate source registry" "$PYTHON_BIN" src/data/validate_sources.py
run_step "Regenerate raw source manifest" "$PYTHON_BIN" src/data/raw_manifest.py --reuse-existing
run_step "Regenerate canonical observation summaries" "$PYTHON_BIN" src/data/report_observations.py
run_step "Regenerate data freeze" "$PYTHON_BIN" src/data/freeze.py --overwrite

run_step "Verify expected regenerated files" verify_expected_outputs
run_step "Verify derived manifest path set" verify_manifest_path_set

if (( RUN_TY == 1 )); then
  run_step "Run static type check" poetry run ty check
fi

if (( RUN_PYTEST == 1 )); then
  run_step "Run tests" poetry run pytest
fi

echo
echo "Reproducible data workspace is regenerated."
