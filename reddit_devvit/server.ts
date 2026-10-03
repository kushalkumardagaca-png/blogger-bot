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

function firstPhoto(entry: FeedEntry): string {
  const source = entry.content?.$t ?? '';
  const match = source.match(/<img\b[^>]*\bsrc=["']([^"']+)["']/i);
  if (!match) return '';
  const value = match[1].replace(/&amp;/gi, '&');
  try {
    const host = new URL(value).hostname.toLowerCase();
    return host === 'images.unsplash.com' || host === 'upload.wikimedia.org' ||
      host === 'thumb.wikimedia.org' || host === 'blogger.googleusercontent.com' ||
      host.endsWith('.bp.blogspot.com') ? value : '';
  } catch {
    return '';
  }
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
  const summary = source.length > 360 ? `${source.slice(0, 357).trim()}…` : source;
  const photo = firstPhoto(entry);
  const body = [
    `**Read:** ${url}`,
    '',
    `## ${title}`,
    '',
    '**By Kushal K. Daga**',
    ...(photo ? ['', `![${title}](${photo})`] : []),
    '',
    summary || 'A practical Daily Yield analysis for today’s money decisions.',
    '',
    '*Educational information, not individualized financial advice.*',
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
