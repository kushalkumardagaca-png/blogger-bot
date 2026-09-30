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
const LAST_URL_KEY = 'dailyyield:last-published-url';

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
  const response = await fetch(FEED_URL, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`Daily Yield feed returned HTTP ${response.status}`);
  const payload = (await response.json()) as FeedPayload;
  const entry = (payload.feed?.entry ?? []).find(suitable);
  if (!entry) return { status: 'skipped', reason: 'No eligible master article in feed' };

  const title = decodeHtml(entry.title?.$t ?? '').slice(0, 260);
  const url = entry.link?.find((item) => item.rel === 'alternate')?.href ?? '';
  if (!title || !url.startsWith('https://dailyyield.blogspot.com/')) {
    throw new Error('Feed entry failed title or official-domain validation');
  }
  if ((await redis.get(LAST_URL_KEY)) === url) {
    return { status: 'skipped', title, url, reason: 'Already published' };
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
  await redis.set(LAST_URL_KEY, url);
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
