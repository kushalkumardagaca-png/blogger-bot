#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f package.json || ! -f devvit.json || ! -d src/server ]]; then
  echo "ERROR: Run this from inside the generated dailyyield-feed directory." >&2
  exit 1
fi
if ! grep -q '"name"[[:space:]]*:[[:space:]]*"dailyyield-feed"' devvit.json; then
  echo "ERROR: This is not the dailyyield-feed Devvit project." >&2
  exit 1
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p ".dailyyield-backup-$stamp/src/server"
cp devvit.json ".dailyyield-backup-$stamp/devvit.json"
cp src/server/server.ts ".dailyyield-backup-$stamp/src/server/server.ts"

curl -fsSLo devvit.json https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/reddit_devvit/devvit.json
curl -fsSLo src/server/server.ts https://raw.githubusercontent.com/kushalkumardagaca-png/blogger-bot/main/reddit_devvit/server.ts

python3 -m json.tool devvit.json >/dev/null
npm run test:types
npm run build

echo
echo "DAILY YIELD DEVVIT AUTOMATION INSTALLED AND BUILT"
echo "Backup: .dailyyield-backup-$stamp"
echo "Schedule: 04:30 UTC / 10:00 IST daily"
echo "Next commands:"
echo "  npx devvit upload"
echo "  npx devvit publish"
echo "After Reddit approves the fetch domain/version:"
echo "  npx devvit install DailyYield"
