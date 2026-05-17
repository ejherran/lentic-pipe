#!/usr/bin/env bash
set -euo pipefail

MAX_TRACKED_BYTES="${MAX_TRACKED_BYTES:-52428800}"
status=0

echo "Checking tracked files before publication..."

large_files=()
while IFS= read -r -d '' path; do
  [[ -f "$path" ]] || continue
  size="$(wc -c < "$path")"
  if (( size > MAX_TRACKED_BYTES )); then
    large_files+=("${size} ${path}")
  fi
done < <(git ls-files -z)

if (( ${#large_files[@]} > 0 )); then
  status=1
  echo
  echo "Tracked files over ${MAX_TRACKED_BYTES} bytes:"
  printf '  %s\n' "${large_files[@]}"
fi

forbidden_paths=()
while IFS= read -r -d '' path; do
  case "$path" in
    data/raw/.gitkeep|data/raw/*.dvc|data/raw/.gitignore)
      ;;
    data/raw/*)
      forbidden_paths+=("$path")
      ;;
    data/interim/.gitkeep|data/interim/*.dvc|data/interim/.gitignore)
      ;;
    data/interim/*)
      forbidden_paths+=("$path")
      ;;
    data/panel/*.parquet|data/panel/*.csv|data/panel/*.feather)
      forbidden_paths+=("$path")
      ;;
    data/targets/*.parquet|data/splits/*.parquet|data/diagnostics/*.parquet|data/diagnostics/*.csv)
      forbidden_paths+=("$path")
      ;;
    data/fuzzy/*|data/pipe_grud/*)
      case "$path" in
        *.dvc|*/.gitignore)
          ;;
        *)
          forbidden_paths+=("$path")
          ;;
      esac
      ;;
    models/*)
      case "$path" in
        *.dvc|*.json|*/README.md|*/model_card.md|*/.gitignore)
          ;;
        *)
          forbidden_paths+=("$path")
          ;;
      esac
      ;;
  esac
done < <(git ls-files -z)

if (( ${#forbidden_paths[@]} > 0 )); then
  status=1
  echo
  echo "Tracked heavy-data paths that should be DVC pointers, not Git blobs:"
  printf '  %s\n' "${forbidden_paths[@]}"
fi

secret_paths=()
while IFS= read -r -d '' path; do
  case "$path" in
    .env|.env.*|.dvc/config.local|private/*.json|*.pem|*.key|*service-account*.json|*gcloud*.json)
      secret_paths+=("$path")
      ;;
  esac
done < <(git ls-files -z)

if (( ${#secret_paths[@]} > 0 )); then
  status=1
  echo
  echo "Tracked secret-looking files:"
  printf '  %s\n' "${secret_paths[@]}"
fi

tracked_secret_content_hits="$(
  git grep -nE '"type"[[:space:]]*:[[:space:]]*"service_account"|"private_key"[[:space:]]*:' \
    -- . \
    ':!scripts/check_repo_publication_ready.sh' \
    || true
)"
untracked_secret_content_hits="$(
  git grep --untracked -nE '"type"[[:space:]]*:[[:space:]]*"service_account"|"private_key"[[:space:]]*:' \
    -- . \
    ':!private/**' \
    ':!scripts/check_repo_publication_ready.sh' \
    || true
)"
secret_content_hits="$(
  {
    printf '%s\n' "$tracked_secret_content_hits"
    printf '%s\n' "$untracked_secret_content_hits"
  } | sed '/^$/d'
)"
if [[ -n "$secret_content_hits" ]]; then
  status=1
  echo
  echo "Service-account credential content found in versionable files:"
  printf '%s\n' "$secret_content_hits"
fi

repo_language_hits="$(
  git grep --untracked -nE '([áéíóúÁÉÍÓÚñÑ¿¡]|(^|[^A-Za-z])(gestion|datos|codigo|documentacion|maquina|credenciales|fuentes|crudos|artefactos|proliferacion|simulacion|planificacion|trazabilidad|dependencias|instalacion|recuperar|publicar|actualizar|repositorio|pequenos|subir|bajar|configurar|diagnosticar|autorizada|cuenta|servicio|clave|trofico|lenticos|modelos|validar|regenerar|manifiestos|despues|politica)([^A-Za-z]|$))' \
    -- . \
    ':!private/**' \
    ':!.venv/**' \
    ':!.git/**' \
    ':!.pytest_cache/**' \
    ':!data/raw/**' \
    ':!scripts/check_repo_publication_ready.sh' \
    || true
)"
if [[ -n "$repo_language_hits" ]]; then
  status=1
  echo
  echo "Non-English repository text found in versionable files:"
  printf '%s\n' "$repo_language_hits"
fi

bucket_hits="$(git grep --untracked -nE 'gs://[A-Za-z0-9][A-Za-z0-9._/-]*' -- . ':!private/**' ':!scripts/check_repo_publication_ready.sh' || true)"
if [[ -n "$bucket_hits" ]]; then
  non_placeholder_hits="$(
    printf '%s\n' "$bucket_hits" \
      | grep -v 'YOUR_PRIVATE_BUCKET' \
      | grep -v '\${BUCKET}' \
      | grep -v 'gs://gs://' \
      || true
  )"
  if [[ -n "$non_placeholder_hits" ]]; then
    status=1
    echo
    echo "Tracked GCS URLs that are not placeholders:"
    printf '%s\n' "$non_placeholder_hits"
  fi
fi

if (( status == 0 )); then
  echo "OK: tracked files look publication-ready."
else
  echo
  echo "Publication readiness check failed."
fi

exit "$status"
