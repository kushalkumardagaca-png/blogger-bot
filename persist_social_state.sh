#!/usr/bin/env bash
set -euo pipefail

if (( $# == 0 )); then
  echo "usage: persist_social_state.sh <state-file> [...]" >&2
  exit 2
fi

stash="$(mktemp -d)"
trap 'rm -rf "$stash"' EXIT
for file in "$@"; do
  test -f "$file" || { echo "missing social state file: $file" >&2; exit 1; }
  mkdir -p "$stash/$(dirname "$file")"
  cp "$file" "$stash/$file"
done

for attempt in 1 2 3; do
  git fetch origin main
  git reset --hard origin/main
  for file in "$@"; do
    mkdir -p "$(dirname "$file")"
    if [[ "$file" == *_tracker.json ]] && [[ -f "$file" ]]; then
      python merge_social_tracker.py "$file" "$stash/$file" "$file.merged"
      mv "$file.merged" "$file"
    else
      cp "$stash/$file" "$file"
    fi
  done
  git add -- "$@"
  if git diff --staged --quiet; then
    echo "No social state change to persist."
    exit 0
  fi
  git commit -m "Persist coordinated social publication state [skip ci]"
  if git push origin HEAD:main; then
    exit 0
  fi
  echo "Concurrent social-state update detected; retrying ($attempt/3)."
  sleep $((attempt * 2))
done

echo "Unable to persist social state after three attempts." >&2
exit 1
