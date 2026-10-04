"""Canonical Daily Yield contact and active-social identity cleanup."""
import html
import json
import re

PUBLIC_EMAIL = "dailyyield.official@gmail.com"
SOCIAL_PROFILES = (
    ("Facebook", "https://www.facebook.com/1303333369533572", "Daily Yield on Facebook"),
    ("Bluesky", "https://bsky.app/profile/dailyyield.bsky.social", "@dailyyield.bsky.social"),
    ("Tumblr", "https://www.tumblr.com/dailyyield-official", "dailyyield-official"),
    ("Mastodon", "https://mastodon.social/@dailyyield", "@dailyyield@mastodon.social"),
)
OLD_PUBLIC_EMAILS = (
    "kushalkumardaga.ca@gmail.com",
    "kushalkumadaga.ca@gmail.com",
)
INACTIVE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:linkedin\.com/[^\s\"'<>]+|(?:x|twitter)\.com/[^\s\"'<>]+|reddit\.com/[^\s\"'<>]+)",
    re.I,
)
JSON_LD_RE = re.compile(
    r"(<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>)(.*?)(</script\s*>)",
    re.I | re.S,
)


def _inactive_url(value):
    return isinstance(value, str) and bool(INACTIVE_URL_RE.fullmatch(value.strip()))


def _rewrite_json(node):
    if isinstance(node, list):
        return [_rewrite_json(value) for value in node if not _inactive_url(value)]
    if isinstance(node, dict):
        return {key: _rewrite_json(value) for key, value in node.items()}
    if isinstance(node, str):
        return INACTIVE_URL_RE.sub("", node)
    return node


def ensure_social_identity(content):
    """Keep active channels and remove LinkedIn, X/Twitter and Reddit links."""
    content = content or ""
    for old in OLD_PUBLIC_EMAILS:
        content = re.sub(re.escape(old), PUBLIC_EMAIL, content, flags=re.I)

    def json_repl(match):
        try:
            data = json.loads(html.unescape(match.group(2)).strip())
        except Exception:
            return match.group(0)
        return match.group(1) + json.dumps(_rewrite_json(data), ensure_ascii=False, indent=2) + match.group(3)
    content = JSON_LD_RE.sub(json_repl, content)

    # Delete visible inactive-channel anchors, including common strong wrappers.
    anchor = r"<a\b[^>]*href=[\"']" + INACTIVE_URL_RE.pattern + r"[\"'][^>]*>.*?</a\s*>"
    content = re.sub(r"<strong\b[^>]*>\s*" + anchor + r"\s*</strong\s*>", "", content, flags=re.I | re.S)
    content = re.sub(anchor, "", content, flags=re.I | re.S)
    content = INACTIVE_URL_RE.sub("", content)

    # Clean punctuation left by removing an inactive contact route.
    content = re.sub(r"\b(?:or\s+)?via\s*(?:</?strong\b[^>]*>\s*)*(?:,|and|\.)", ".", content, flags=re.I)
    content = re.sub(r"\bvia\s*(?:,|and)\s*", "via ", content, flags=re.I)
    content = re.sub(r"\s+([,.;])", r"\1", content)
    content = re.sub(r" {2,}", " ", content)
    return content
