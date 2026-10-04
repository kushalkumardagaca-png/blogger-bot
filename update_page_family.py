#!/usr/bin/env python3
"""Install the shared Daily Yield family directory on every active static page."""
from pathlib import Path
import html, json, os, re, requests
from page_family import ACTIVE_PAGES, BLOG, END, START, ensure_family
from social_identity import SOCIAL_PROFILES

BLOG_ID = os.environ["BLOGGER_BLOG_ID"]
BASE = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}"
TERMS_PATH = "/p/terms-and-conditions.html"
TERMS_CONTENT = """
<style>
#dyTerms{--ink:#241610;--muted:#6e5d4b;--copper:#9c4522;--line:#eadcc8;--paper:#fffdf8;max-width:1120px;margin:0 auto;padding:clamp(24px,5vw,64px) clamp(16px,4vw,42px);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;box-sizing:border-box}#dyTerms *{box-sizing:border-box}#dyTerms .dyt-hero{position:relative;overflow:hidden;padding:clamp(28px,6vw,66px);border:1px solid var(--line);border-radius:26px;background:radial-gradient(circle at 88% 12%,rgba(188,91,51,.16),transparent 30%),linear-gradient(145deg,#fffdf8,#fbf1df)}#dyTerms .dyt-kicker{margin:0 0 12px;color:var(--copper);font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}#dyTerms h1{max-width:780px;margin:0;font:700 clamp(42px,8vw,82px)/.98 Georgia,serif;letter-spacing:-.045em}#dyTerms .dyt-lede{max-width:720px;margin:20px 0 0;color:var(--muted);font-size:clamp(15px,2vw,18px);line-height:1.75}#dyTerms .dyt-meta{display:flex;flex-wrap:wrap;gap:8px;margin:24px 0 0}#dyTerms .dyt-meta span{padding:8px 11px;border:1px solid var(--line);border-radius:999px;background:rgba(255,255,255,.72);font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}#dyTerms .dyt-jump{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 0}#dyTerms .dyt-jump a{padding:9px 12px;border-radius:10px;background:#241610;color:#fffaf1;text-decoration:none;font-size:11px;font-weight:800}#dyTerms .dyt-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:24px 0}#dyTerms .dyt-card{scroll-margin-top:24px;padding:clamp(20px,3vw,30px);border:1px solid var(--line);border-radius:18px;background:var(--paper)}#dyTerms .dyt-num{display:inline-grid;width:30px;height:30px;margin-bottom:13px;place-items:center;border-radius:9px;background:#f6e8cf;color:var(--copper);font-size:11px;font-weight:900}#dyTerms h2{margin:0 0 10px;font:700 clamp(22px,3vw,30px)/1.15 Georgia,serif}#dyTerms p{margin:0;color:var(--muted);font-size:14px;line-height:1.78}#dyTerms a{color:var(--copper)}#dyTerms .dyt-contact{padding:clamp(24px,4vw,38px);border-radius:20px;background:linear-gradient(120deg,#241610,#512618);color:#fff8ee}#dyTerms .dyt-contact h2{color:#fff;margin-bottom:10px}#dyTerms .dyt-contact p{color:#e6d5c4}#dyTerms .dyt-contact a{color:#f1b383;font-weight:800}@media(max-width:720px){#dyTerms{padding-inline:14px}#dyTerms .dyt-hero{border-radius:19px}#dyTerms .dyt-grid{grid-template-columns:1fr}#dyTerms h1{font-size:clamp(38px,14vw,58px)}}@media(prefers-reduced-motion:reduce){#dyTerms *{scroll-behavior:auto!important}}
</style>
<main id="dyTerms">
<header class="dyt-hero"><p class="dyt-kicker">Daily Yield · Clear rules, plain language</p><h1>Terms &amp; Conditions</h1><p class="dyt-lede">The practical boundaries for using Daily Yield’s website and educational material—written to be read, not hidden.</p><div class="dyt-meta"><span>Effective 4 October 2026</span><span>Education, not personal advice</span></div><nav aria-label="Terms sections" class="dyt-jump"><a href="#dyt-scope">Scope</a><a href="#dyt-use">Acceptable use</a><a href="#dyt-contact">Contact</a></nav></header>
<div class="dyt-grid">
<section class="dyt-card" id="dyt-scope"><span class="dyt-num">01</span><h2>Acceptance and scope</h2><p>These terms apply when you use Daily Yield’s website and public educational material. By using the service, you agree to these terms and applicable law. If you do not agree, do not use the service.</p></section>
<section class="dyt-card"><span class="dyt-num">02</span><h2>Educational information only</h2><p>Daily Yield provides general financial education, reporting, calculations and commentary—not individualized investment, tax, accounting or legal advice. Illustrations may use assumptions and delayed data. Verify dates, figures, local law and suitability with an appropriately qualified professional before acting.</p></section>
<section class="dyt-card" id="dyt-use"><span class="dyt-num">03</span><h2>Acceptable use</h2><p>Do not misuse the service, attempt unauthorized access, evade platform restrictions, impersonate others, interfere with operation or use Daily Yield material unlawfully.</p></section>
<section class="dyt-card"><span class="dyt-num">04</span><h2>Original work and sources</h2><p>Daily Yield’s original wording, design and branding remain protected by applicable law. Linked third-party sources, quotations, trademarks and platform services remain the property and responsibility of their respective owners. Reasonable sharing through links and platform tools is welcome; substantial republication requires permission unless law provides otherwise.</p></section>
<section class="dyt-card"><span class="dyt-num">05</span><h2>Third-party services</h2><p>The service may depend on Blogger, follow.it, market-data providers and other linked services. Their terms and privacy practices apply separately. Daily Yield does not control their availability, policies or processing.</p></section>
<section class="dyt-card"><span class="dyt-num">06</span><h2>Availability and changes</h2><p>The service is provided on an “as available” basis. Features may be corrected, limited, suspended or withdrawn for security, accuracy, legal or platform-compliance reasons. Updated terms will carry a revised effective date.</p></section>
<section class="dyt-card"><span class="dyt-num">07</span><h2>Liability</h2><p>To the extent permitted by law, Daily Yield is not liable for losses arising from reliance on educational content, market movements, third-party services or interruptions. Nothing here excludes rights or liabilities that cannot lawfully be excluded.</p></section>
</div>
<section class="dyt-contact" id="dyt-contact"><h2>Questions should have a clear route.</h2><p>Email <a href="mailto:dailyyield.official@gmail.com">dailyyield.official@gmail.com</a>, use the <a href="https://dailyyield.blogspot.com/p/contact-us_01883938366.html">Contact desk</a>, or review the <a href="https://dailyyield.blogspot.com/p/privacy-policy.html">Privacy Policy</a> and <a href="https://dailyyield.blogspot.com/p/disclaimer.html">Disclaimer</a>.</p></section>
</main>
"""


def headers():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["BLOGGER_CLIENT_ID"],
        "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def list_pages(h):
    out, token = [], None
    while True:
        params = {"fetchBodies": "true", "maxResults": "50"}
        if token:
            params["pageToken"] = token
        r = requests.get(BASE + "/pages", headers=h, params=params, timeout=90)
        r.raise_for_status()
        data = r.json()
        out.extend(data.get("items", []))
        token = data.get("nextPageToken")
        if not token:
            return out


def page_path(page):
    url = page.get("url", "")
    return url[len(BLOG):] if url.startswith(BLOG) else ""


def update(h, page, content):
    body = {"kind": "blogger#page", "id": page["id"], "title": page["title"], "content": content}
    r = requests.put(f"{BASE}/pages/{page['id']}", headers=h, json=body, timeout=120)
    r.raise_for_status()
    return r.json()


def create_terms(h):
    body = {"kind": "blogger#page", "title": "Terms and Conditions",
            "content": ensure_family(TERMS_CONTENT, TERMS_PATH)}
    r = requests.post(BASE + "/pages", headers=h, params={"isDraft": "false"}, json=body, timeout=120)
    r.raise_for_status()
    page = r.json()
    if page_path(page) != TERMS_PATH:
        raise RuntimeError(f"Blogger created unexpected Terms URL: {page.get('url', '')}")
    return page


def ensure_image_alts(content, title):
    """Add descriptive alt text only where an img has no alt attribute.

    Explicit alt="" remains untouched because it denotes a decorative image.
    """
    fallback = html.escape(f"Daily Yield {title} visual", quote=True)
    def repair(match):
        tag = match.group(0)
        if re.search(r"\balt\s*=", tag, re.I):
            return tag
        if tag.endswith("/>"):
            return tag[:-2].rstrip() + f' alt="{fallback}" />'
        return tag[:-1].rstrip() + f' alt="{fallback}">'
    # Never interpret JavaScript strings/regex literals containing "<img" as
    # markup. A previous whole-document substitution corrupted the News parser.
    parts = re.split(r"(<script\b[^>]*>.*?</script>)", content or "", flags=re.I | re.S)
    return "".join(part if re.match(r"<script\b", part, re.I) else re.sub(r"<img\b[^>]*>", repair, part, flags=re.I) for part in parts)


def main():
    h = headers()
    pages = list_pages(h)
    by_path = {page_path(p): p for p in pages}
    if TERMS_PATH not in by_path:
        create_terms(h)
        pages = list_pages(h)
        by_path = {page_path(p): p for p in pages}
    missing = [path for path in ACTIVE_PAGES if path not in by_path]
    if missing:
        raise RuntimeError("active Blogger pages missing: " + ", ".join(missing))

    backup = []
    for path in ACTIVE_PAGES:
        p = by_path[path]
        backup.append({"id": p["id"], "title": p["title"], "url": p["url"], "content": p.get("content", "")})
    Path("page_family_backup.json").write_text(json.dumps(backup, ensure_ascii=False), encoding="utf-8")

    changed, unchanged = [], []
    for path in ACTIVE_PAGES:
        p = by_path[path]
        old = p.get("content", "")
        base = TERMS_CONTENT if path == TERMS_PATH else old
        base = ensure_image_alts(base, p["title"])
        new = ensure_family(base, path)
        if new == old:
            unchanged.append(path)
        else:
            update(h, p, new)
            changed.append(path)

    refreshed = {page_path(p): p for p in list_pages(h)}
    checks = []
    social_urls = [url for _name, url, _handle in SOCIAL_PROFILES]
    for path in ACTIVE_PAGES:
        p = refreshed[path]
        content = p.get("content", "")
        match = re.search(re.escape(START) + r".*?" + re.escape(END), content, re.S)
        managed = match.group(0) if match else ""
        social_counts = {url: managed.count(url) for url in social_urls}
        images_without_alt = len([tag for tag in re.findall(r"<img\b[^>]*>", content, re.I)
                                  if not re.search(r"\balt\s*=", tag, re.I)])
        ok = (content.count(START) == 1 and content.count('id="dyPageFamily"') == 1
              and images_without_alt == 0
              and managed.count('class="dyf-social"') == 1
              and all(count == 1 for count in social_counts.values())
              and "/p/markets-today.html" in managed and "/p/global-snapshot.html" in managed
              and "/p/share-market_0718113516.html" not in managed and "Market Explorer" not in managed)
        checks.append({"path": path, "title": p["title"], "verified": ok,
                       "managed_block_found": bool(match), "images_without_alt": images_without_alt,
                       "social_counts": social_counts})

    verified = all(c["verified"] for c in checks)
    result = {"changed": changed, "unchanged": unchanged, "verified_pages": checks, "verified": verified}
    Path("page_family_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not verified:
        raise RuntimeError("one or more managed family blocks failed verification; inspect page_family_result.json")


if __name__ == "__main__":
    main()
