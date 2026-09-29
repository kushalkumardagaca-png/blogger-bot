"""Canonical Daily Yield social identity cleanup for existing and future content."""
import html
import json
import re

LINKEDIN = "https://www.linkedin.com/in/dailyyeild"
PUBLIC_EMAIL = "dailyyield.official@gmail.com"
# Active, public channels shown across the static Page family. LinkedIn remains
# paused, X is closed, and Reddit is intentionally omitted until approved.
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
OLD_LINKEDIN = (
    "https://www.linkedin.com/in/finance-by-kushal/",
    "https://www.linkedin.com/in/finance-by-kushal",
)
CLOSED_X_RE = re.compile(r"https?://(?:www\.)?(?:x|twitter)\.com/CAKUSHAL2509/?", re.I)
JSON_LD_RE = re.compile(
    r"(<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>)(.*?)(</script\s*>)",
    re.I | re.S,
)


def _rewrite_json(node):
    if isinstance(node, list):
        out = []
        for value in node:
            if isinstance(value, str) and CLOSED_X_RE.fullmatch(value.strip()):
                continue
            out.append(_rewrite_json(value))
        return out
    if isinstance(node, dict):
        return {key: _rewrite_json(value) for key, value in node.items()}
    if isinstance(node, str):
        for old in OLD_LINKEDIN:
            node = node.replace(old, LINKEDIN)
        return node
    return node


def ensure_social_identity(content):
    """Remove the closed X account and canonicalize LinkedIn, idempotently."""
    content = content or ""
    for old in OLD_LINKEDIN:
        content = content.replace(old, LINKEDIN)
    for old in OLD_PUBLIC_EMAILS:
        content = re.sub(re.escape(old), PUBLIC_EMAIL, content, flags=re.I)

    # Keep structured data valid while removing the discontinued X identity.
    def json_repl(match):
        try:
            data = json.loads(html.unescape(match.group(2)).strip())
        except Exception:
            return match.group(0)
        return match.group(1) + json.dumps(_rewrite_json(data), ensure_ascii=False, indent=2) + match.group(3)
    content = JSON_LD_RE.sub(json_repl, content)

    # Remove visible links to the closed account, including common strong wrappers.
    x_anchor = r"<a\b[^>]*href=[\"']" + CLOSED_X_RE.pattern + r"[\"'][^>]*>.*?</a\s*>"
    content = re.sub(r"<strong\b[^>]*>\s*" + x_anchor + r"\s*</strong\s*>", "", content, flags=re.I | re.S)
    content = re.sub(x_anchor, "", content, flags=re.I | re.S)

    # Clean conjunctions/punctuation left by removing X from contact sentences.
    content = re.sub(r"\bor\s+via\s*(?:</?strong\b[^>]*>\s*)*\band\s+", "or via ", content, flags=re.I)
    content = re.sub(r"\bvia\s*(?:,|and)\s*", "via ", content, flags=re.I)
    content = re.sub(r"\s+,", ",", content)
    content = re.sub(r" {2,}", " ", content)
    return content
