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

cat > devvit.json <<'DY_DEVVIT_JSON'
{
  "$schema": "https://developers.reddit.com/schema/config-file.v1.json",
  "name": "dailyyield-feed",
  "post": {
    "entrypoints": {
      "default": { "entry": "splash.html" },
      "game": { "entry": "game.html" }
    }
  },
  "server": {},
  "permissions": {
    "http": {
      "enable": true,
      "domains": ["dailyyield.blogspot.com"]
    },
    "redis": true,
    "reddit": { "enable": true }
  },
  "menu": {
    "items": [
      {
        "label": "Daily Yield: publish latest article",
        "description": "Publish the latest eligible Daily Yield master article",
        "forUserType": "moderator",
        "location": "subreddit",
        "endpoint": "/internal/menu/publish-now"
      }
    ]
  },
  "scheduler": {
    "tasks": {
      "daily-yield-publish-1": { "endpoint": "/internal/scheduler/daily-publish", "cron": "30 4 * * *" },
      "daily-yield-publish-2": { "endpoint": "/internal/scheduler/daily-publish", "cron": "30 7 * * *" },
      "daily-yield-publish-3": { "endpoint": "/internal/scheduler/daily-publish", "cron": "30 10 * * *" },
      "daily-yield-publish-4": { "endpoint": "/internal/scheduler/daily-publish", "cron": "30 13 * * *" },
      "daily-yield-publish-5": { "endpoint": "/internal/scheduler/daily-publish", "cron": "30 16 * * *" }
    }
  },
  "scripts": {
    "dev": "npm run watch"
  }
}
DY_DEVVIT_JSON

cat > src/server/server.ts <<'DY_SERVER_TS'
import { createServer, getServerPort, context, reddit, redis } from '@devvit/web/server';
import type { IncomingMessage, ServerResponse } from 'node:http';

type FeedEntry = {
  title?: { $t?: string };
  content?: { $t?: string };
  summary?: { $t?: string };
  link?: Array<{ rel?: string; href?: string }>;
  category?: Array<{ term?: string }>;
};
type FeedPayload = { feed?: { entry?: FeedEntry[] } };
type PublishResult = { status: string; title?: string; url?: string; postUrl?: string; reason?: string };

const FEED_URL = 'https://dailyyield.blogspot.com/feeds/posts/default?alt=json&max-results=50';
const HISTORY_KEY = 'dailyyield:published-url-history';
const MAX_DAILY_POSTS = 5;

function istDayKey(): string {
  return new Date(Date.now() + 330 * 60 * 1000).toISOString().slice(0, 10);
}

function entryUrl(entry: FeedEntry): string {
  return entry.link?.find((item) => item.rel === 'alternate')?.href ?? '';
}

async function publishedHistory(): Promise<string[]> {
  const raw = await redis.get(HISTORY_KEY);
  if (!raw) return [];
  try {
    const value = JSON.parse(raw) as unknown;
    return Array.isArray(value) ? value.filter((url): url is string => typeof url === 'string').slice(0, 200) : [];
  } catch {
    return [];
  }
}

function decodeHtml(value: string): string {
  return value
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/\s+/g, ' ')
    .trim();
}

function suitable(entry: FeedEntry): boolean {
  const labels = (entry.category ?? []).map((item) => (item.term ?? '').toLowerCase());
  return !labels.some((label) => label === 'news' || label.includes('daily news'));
}

async function publishLatest(): Promise<PublishResult> {
  const countKey = `dailyyield:post-count:${istDayKey()}`;
  const dailyCount = Number((await redis.get(countKey)) ?? '0');
  if (dailyCount >= MAX_DAILY_POSTS) {
    return { status: 'skipped', reason: `Daily quota of ${MAX_DAILY_POSTS} reached` };
  }

  const response = await fetch(FEED_URL, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`Daily Yield feed returned HTTP ${response.status}`);
  const payload = (await response.json()) as FeedPayload;
  const history = await publishedHistory();
  const entry = (payload.feed?.entry ?? []).find((candidate) => {
    const url = entryUrl(candidate);
    return suitable(candidate) && url.startsWith('https://dailyyield.blogspot.com/') && !history.includes(url);
  });
  if (!entry) return { status: 'skipped', reason: 'No new eligible master article in feed' };

  const title = decodeHtml(entry.title?.$t ?? '').slice(0, 260);
  const url = entryUrl(entry);
  if (!title || !url.startsWith('https://dailyyield.blogspot.com/')) {
    throw new Error('Feed entry failed title or official-domain validation');
  }

  const source = decodeHtml(entry.content?.$t ?? entry.summary?.$t ?? '');
  const summary = source.length > 520 ? `${source.slice(0, 517).trim()}…` : source;
  const body = [
    summary || 'A practical Daily Yield analysis for today’s money decisions.',
    '',
    `**Read the complete analysis:** [${title}](${url})`,
    '',
    '**Discussion:** Which assumption in this analysis would you challenge first—and why?',
    '',
    '*Published automatically by the official Daily Yield app. Educational information, not individualized financial advice.*',
  ].join('\n');

  const post = await reddit.submitPost({
    subredditName: context.subredditName,
    title: `Daily Yield | ${title}`.slice(0, 300),
    text: body,
    sendreplies: true,
    runAs: 'APP',
  });
  await redis.set(HISTORY_KEY, JSON.stringify([url, ...history.filter((item) => item !== url)].slice(0, 200)));
  await redis.set(countKey, String(dailyCount + 1));
  return { status: 'published', title, url, postUrl: post.url };
}

function sendJson(res: ServerResponse, status: number, value: unknown): void {
  const body = JSON.stringify(value);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

export async function onReq(req: IncomingMessage, res: ServerResponse): Promise<void> {
  try {
    const path = new URL(req.url ?? '/', 'http://devvit.local').pathname;
    const allowed = path === '/internal/scheduler/daily-publish' || path === '/internal/menu/publish-now';
    if (req.method !== 'POST' || !allowed) {
      sendJson(res, 404, { error: 'not found' });
      return;
    }
    const result = await publishLatest();
    if (path === '/internal/menu/publish-now') {
      sendJson(res, 200, {
        showToast: {
          text: result.status === 'published' ? `Published: ${result.title}` : `Skipped: ${result.reason}`,
          appearance: result.status === 'published' ? 'success' : 'neutral',
        },
      });
    } else {
      sendJson(res, 200, result);
    }
  } catch (error) {
    console.error('Daily Yield publisher failed', error);
    sendJson(res, 500, { error: error instanceof Error ? error.message : 'unknown error' });
  }
}

const server = createServer(onReq);
server.listen(getServerPort());
DY_SERVER_TS

python3 -m json.tool devvit.json >/dev/null
npm run test:types
npm run build

echo
echo "DAILY YIELD DEVVIT AUTOMATION INSTALLED AND BUILT"
echo "Backup: .dailyyield-backup-$stamp"
echo "Schedule: five daily slots at 10:00, 13:00, 16:00, 19:00 and 22:00 IST"
echo "Next commands:"
echo "  npx devvit upload"
echo "  npx devvit publish"
echo "After Reddit approves the fetch domain/version:"
echo "  npx devvit install DailyYield"
