#!/usr/bin/env python3
"""Install the shared Daily Yield family directory on every active static page."""
from pathlib import Path
import json, os, re, requests
from page_family import ACTIVE_PAGES, BLOG, END, START, ensure_family
from social_identity import SOCIAL_PROFILES

BLOG_ID = os.environ["BLOGGER_BLOG_ID"]
BASE = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}"
TERMS_PATH = "/p/terms-and-conditions.html"
TERMS_CONTENT = """
<section style="max-width:900px;margin:0 auto;padding:clamp(20px,4vw,42px);color:#241610;line-height:1.72">
<p style="color:#9c4522;font-size:11px;font-weight:800;letter-spacing:.14em;text-transform:uppercase">Daily Yield · Site and official Reddit app</p>
<h1 style="font:700 clamp(34px,7vw,64px)/1.05 Georgia,serif;margin:.2em 0">Terms &amp; Conditions</h1>
<p><strong>Effective:</strong> 30 September 2026</p>
<h2>1. Acceptance and scope</h2><p>These terms apply when you use Daily Yield’s website, public educational material or official Reddit Devvit app in r/DailyYield. By using those services, you agree to these terms and to the applicable platform rules. If you do not agree, do not use the service.</p>
<h2>2. Educational information only</h2><p>Daily Yield provides general financial education, reporting, calculations and commentary. It does not provide individualized investment, tax, accounting or legal advice. Illustrations may use assumptions and delayed data. Verify dates, figures, local law and suitability with an appropriately qualified professional before acting.</p>
<h2>3. Reddit app operation</h2><p>The official Daily Yield app retrieves the public Daily Yield Blogger feed, excludes designated News-wire entries, prevents repeat publication of the same article URL and may publish no more than one eligible summary post per day in r/DailyYield. It does not authorize mass posting, automated private messages, voting or activity in unrelated communities.</p>
<h2>4. Acceptable use</h2><p>Do not misuse the service, attempt unauthorized access, evade platform restrictions, impersonate others, interfere with operation, or use Daily Yield material unlawfully. Reddit participation remains subject to Reddit’s User Agreement, Content Policy and community rules.</p>
<h2>5. Intellectual property and sources</h2><p>Daily Yield’s original wording, design and branding remain protected by applicable law. Linked third-party sources, quotations, trademarks and platform services remain the property and responsibility of their respective owners. Reasonable sharing through links and platform tools is welcome; republication of substantial original material requires permission unless the law provides otherwise.</p>
<h2>6. Third-party services</h2><p>The service may depend on Blogger, Reddit, market-data providers and other linked services. Their terms and privacy practices apply separately. Daily Yield does not control their availability, policies or processing.</p>
<h2>7. Availability and changes</h2><p>The service is provided on an “as available” basis. Features may be corrected, limited, suspended or withdrawn for security, accuracy, legal or platform-compliance reasons. These terms may be updated when the service or applicable requirements change; the effective date will identify the current version.</p>
<h2>8. Liability</h2><p>To the extent permitted by law, Daily Yield is not liable for losses arising from reliance on educational content, market movements, third-party services or interruptions. Nothing in these terms excludes rights or liabilities that cannot lawfully be excluded.</p>
<h2>9. Contact</h2><p>Questions, corrections and policy requests may be sent to <a href="mailto:dailyyield.official@gmail.com">dailyyield.official@gmail.com</a>. See the <a href="https://dailyyield.blogspot.com/p/privacy-policy.html">Privacy Policy</a> for data-use information.</p>
</section>
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
        new = ensure_family(old, path)
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
        ok = (content.count(START) == 1 and content.count('id="dyPageFamily"') == 1
              and managed.count('class="dyf-social"') == 1
              and all(count == 1 for count in social_counts.values())
              and "/p/markets-today.html" in managed and "/p/global-snapshot.html" in managed
              and "/p/share-market_0718113516.html" not in managed and "Market Explorer" not in managed)
        checks.append({"path": path, "title": p["title"], "verified": ok,
                       "managed_block_found": bool(match), "social_counts": social_counts})

    verified = all(c["verified"] for c in checks)
    result = {"changed": changed, "unchanged": unchanged, "verified_pages": checks, "verified": verified}
    Path("page_family_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not verified:
        raise RuntimeError("one or more managed family blocks failed verification; inspect page_family_result.json")


if __name__ == "__main__":
    main()
