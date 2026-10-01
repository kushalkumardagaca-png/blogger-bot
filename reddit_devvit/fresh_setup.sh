#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/dailyyield-feed"
INSTALLER_URL="https://gist.githubusercontent.com/kushalkumardagaca-png/32181e3ae9fcc2833e27d58f2fb9124c/raw/install.sh"

echo "Starting a clean Daily Yield Devvit rebuild..."
rm -rf "$APP_DIR"
git clone --depth 1 https://github.com/reddit/devvit-template-vibe-coding.git "$APP_DIR"
cd "$APP_DIR"
rm -rf .git

python3 - <<'PY'
import json
from pathlib import Path
p = Path('package.json')
data = json.loads(p.read_text())
data['name'] = 'dailyyield-feed'
p.write_text(json.dumps(data, indent=2) + '\n')
p = Path('devvit.json')
data = json.loads(p.read_text())
data['name'] = 'dailyyield-feed'
p.write_text(json.dumps(data, indent=2) + '\n')
PY

# The reviewed publisher is the only server entrypoint.
cat > src/server/index.ts <<'TS'
export * from './server';
TS
: > src/server/server.ts

npm install --legacy-peer-deps --no-audit --no-fund
curl -fsSL "$INSTALLER_URL" -o "$HOME/dailyyield-reddit-install.sh"
bash "$HOME/dailyyield-reddit-install.sh"
rm -rf .dailyyield-backup-*

touch .env
grep -qxF 'DEVVIT_ALLOW_SOURCE_UPLOAD=1' .env || printf '\nDEVVIT_ALLOW_SOURCE_UPLOAD=1\n' >> .env

if [[ "${DY_SKIP_REDDIT:-0}" == "1" ]]; then
  echo "Clean local build completed; Reddit account steps skipped."
  exit 0
fi

echo
echo "Reddit will now ask you to authorize the official Devvit CLI."
npx devvit login

# Remove the app from Reddit's automatic test community. Reddit itself may retain
# the empty private subreddit because Reddit does not support deleting communities.
npx devvit uninstall dailyyield_feed_dev dailyyield-feed || true

# Submit as unlisted for Reddit review. Production installation happens only after approval.
npx devvit publish

echo
echo "SUBMITTED FOR REDDIT REVIEW"
echo "Production community preserved: r/DailyYield"
echo "Do not install until Reddit approves the version and fetch domain."
