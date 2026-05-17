#!/usr/bin/env bash
set -euo pipefail

LARGE_BYTES="${PUBLICATION_CANDIDATE_LARGE_BYTES:-5242880}"
VERSIONABLE_EXCLUDE='^[?!][?!] (data/raw/|data/interim/observations/.+\.parquet$|data/panel/.+\.(parquet|csv|feather)$|data/targets/.+\.parquet$|data/diagnostics/.+\.(parquet|csv)$|data/fuzzy/|data/pipe_grud/|models/|private/|\.dvc/config\.local)'

echo "Publication candidate inventory"
echo
echo "Review this output before the first commit. It is intentionally read-only."
echo

versionable_changes="$(
  git status --short --untracked-files=all \
    | grep -vE "$VERSIONABLE_EXCLUDE" \
    || true
)"

echo "== Versionable changes =="
if [[ -n "$versionable_changes" ]]; then
  printf '%s\n' "$versionable_changes"
else
  echo "  none"
fi

echo
echo "== Versionable summary by top-level path =="
if [[ -n "$versionable_changes" ]]; then
  printf '%s\n' "$versionable_changes" \
    | awk '{ path=substr($0,4); split(path, parts, "/"); print parts[1] }' \
    | sort \
    | uniq -c \
    | sort -nr
else
  echo "  none"
fi

echo
echo "== Large versionable file candidates > ${LARGE_BYTES} bytes =="
large_candidates="$(
  if [[ -n "$versionable_changes" ]]; then
    while IFS= read -r status_line; do
      path="${status_line:3}"
      [[ -f "$path" ]] || continue
      size="$(wc -c < "$path")"
      if (( size > LARGE_BYTES )); then
        printf '%012d %s\n' "$size" "$path"
      fi
    done <<< "$versionable_changes"
  fi
)"
if [[ -n "$large_candidates" ]]; then
  printf '%s\n' "$large_candidates" | sort -nr
else
  echo "  none"
fi

echo
echo "== DVC pointer candidates =="
git status --short --untracked-files=all \
  | grep -E '\.dvc$|^A  \.dvc/|^\?\? \.dvcignore$' \
  || true

echo
echo "== Local-only ignored paths to keep out of Git =="
git status --short --ignored --untracked-files=all \
  | grep -E '^!! (\.dvc/config\.local|private/|data/raw/|data/interim/observations/.+\.parquet|data/panel/.+\.(parquet|csv|feather)|data/targets/.+\.parquet|data/diagnostics/.+\.(parquet|csv)|data/fuzzy/|data/pipe_grud/|models/)' \
  | sed -n '1,120p' \
  || true

echo
echo "== Required checks =="
echo "  /home/wolf/.local/bin/poetry run ty check"
echo "  /home/wolf/.local/bin/poetry run pytest"
echo "  /home/wolf/.local/bin/poetry check"
echo "  scripts/check_repo_publication_ready.sh"
