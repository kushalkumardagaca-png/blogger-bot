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

    # Never run prose punctuation cleanup through CSS or executable JavaScript.
    # The former whole-document `\s+([,.;])` substitution interpreted the dot
    # in a descendant CSS selector (`#root .card`) as punctuation and silently
    # changed it to `#root.card`, disabling the Page design.
    protected = re.split(r"(<(?:style|script)\b[^>]*>.*?</(?:style|script)\s*>)", content, flags=re.I | re.S)
    anchor = r"<a\b[^>]*href=[\"']" + INACTIVE_URL_RE.pattern + r"[\"'][^>]*>.*?</a\s*>"
    for i in range(0, len(protected), 2):
        part = protected[i]
        part = re.sub(r"<strong\b[^>]*>\s*" + anchor + r"\s*</strong\s*>", "", part, flags=re.I | re.S)
        part = re.sub(anchor, "", part, flags=re.I | re.S)
        part = INACTIVE_URL_RE.sub("", part)
        part = re.sub(r"\b(?:or\s+)?via\s*(?:</?strong\b[^>]*>\s*)*(?:,|and|\.)", ".", part, flags=re.I)
        part = re.sub(r"\bvia\s*(?:,|and)\s*", "via ", part, flags=re.I)
        part = re.sub(r"\s+([,.;])", r"\1", part)
        part = re.sub(r" {2,}", " ", part)
        protected[i] = part
    return "".join(protected)
