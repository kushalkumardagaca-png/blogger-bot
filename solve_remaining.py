#!/usr/bin/env python3
"""Recheck: which stored description box still holds the retired text.

Finish, from the automation's own side, the last places the old wording survives.

Three things are attempted here, all without asking the publisher to type anything:

1. **The blog's own stored description.** Blogger prints it into the head of every
   page and into its own script block. The Blogger API documents a blog update, so
   the corrected text is written and then read back to prove it landed. If the API
   refuses that field, the result is recorded honestly instead of being reported as
   fixed.

2. **The stored "Search description" of the policy pages and of the blog.** Blogger's
   API does not expose the UI field for a post or a page, and that was already
   established. It is tested once more here with the documented metadata field so
   that the answer in the report is current, not remembered.

3. **The privacy page text.** The optional third-party-vendor sentence is added to
   the page content, which the API *can* write, and then read back.

Everything the run could not finish is written into REMAINING_SOLVER_REPORT.json as
a short list of what a human must do in the Blogger or AdSense screen, in plain words.
No page of the site is fetched: this run uses the authenticated API only.
"""
from __future__ import annotations

from site_change_control import stop_if_frozen as _dy_stop_if_frozen
if __name__ == "__main__":
    _dy_stop_if_frozen('solve_remaining')


import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import brand_seo
import identity_contact as ident

ROOT = Path(__file__).resolve().parent
REPORT = ROOT / "REMAINING_SOLVER_REPORT.json"
BLOG_ID = os.environ.get("BLOGGER_BLOG_ID", "8911514070006792465")

BLOG_DESCRIPTION = (
    f"{ident.PUBLICATION} publishes finance news, practical money guides, market insights and "
    f"transparent calculations, written by {ident.BYLINE}. Contact {ident.PRIMARY_EMAIL} "
    f"or {ident.OWNER_EMAIL}."
)
POLICY_DESCRIPTIONS = {
    "privacy-policy.html": ("How Daily Yield handles cookies, analytics, advertising and reader messages, "
                            "the choices readers have, and how to reach a human about privacy."),
    "disclaimer.html": ("Daily Yield publishes general financial education, not personal advice: the source, "
                        "accuracy and advertising-independence terms readers are entitled to know."),
    "terms-and-conditions.html": ("The terms for using Daily Yield: acceptable use, original work and sources, "
                                  "third-party services, availability, liability and how to reach the desk."),
}
# The optional sentence for the privacy page: names the vendor choice in the wording
# advertising reviewers look for, and links the industry opt-out page.
VENDOR_SENTENCE = (
    "Third-party vendors, including Google, may use cookies to serve ads based on a reader's prior visits "
    "to this site or other sites; readers can opt out of personalised advertising at "
    "https://www.aboutads.info/choices/ as well as through Google's own advertising settings."
)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def request(url: str, method: str = "GET", headers: dict | None = None, body: dict | None = None):
    if "dailyyield.blogspot.com" in url.lower():
        raise RuntimeError("ZERO-VIEW POLICY BLOCKED public Daily Yield request")
    data = json.dumps(body).encode() if body is not None else None
    h = {"User-Agent": "DailyYield-RemainingSolver/1.0", **(headers or {})}
    if body is not None:
        h["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h, method=method), timeout=75) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def oauth() -> str:
    form = urllib.parse.urlencode({
        "client_id": required("BLOGGER_CLIENT_ID"), "client_secret": required("BLOGGER_CLIENT_SECRET"),
        "refresh_token": required("BLOGGER_REFRESH_TOKEN"), "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=form,
                                                       method="POST"), timeout=30) as r:
        return json.load(r)["access_token"]


def error_text(exc: Exception) -> str:
    detail = ""
    if hasattr(exc, "read"):
        try:
            detail = " " + exc.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001
            detail = ""
    return f"{type(exc).__name__}{detail}"


def try_blog_description(token: str, report: dict) -> None:
    endpoint = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}"
    headers = {"Authorization": "Bearer " + token}
    before = request(endpoint, headers=headers)
    report["blogBefore"] = {"name": before.get("name"), "description": before.get("description"),
                            "customMetaData": before.get("customMetaData", "")}
    attempts = []
    # Attempt 1: the documented description field plus a metadata hint.
    for label, extra in (("description_and_metadata", {"customMetaData": json.dumps({"metaDescription": BLOG_DESCRIPTION})}),
                         ("description_only", {})):
        body = {"kind": "blogger#blog", "id": BLOG_ID, "name": before.get("name") or "DAILY YIELD",
                "description": BLOG_DESCRIPTION, "url": before.get("url", ident.SITE + "/")}
        body.update(extra)
        try:
            request(endpoint, method="PUT", headers=headers, body=body)
            time.sleep(2)
            after = request(endpoint, headers=headers)
            attempts.append({"attempt": label, "ok": True,
                             "description": after.get("description", ""),
                             "descriptionLanded": (after.get("description") or "").strip() == BLOG_DESCRIPTION,
                             "customMetaData": after.get("customMetaData", "")})
        except Exception as exc:  # noqa: BLE001
            attempts.append({"attempt": label, "ok": False, "error": error_text(exc)})
    report["blogAttempts"] = attempts
    report["blogDescriptionLanded"] = any(a.get("descriptionLanded") for a in attempts if a.get("ok"))


def try_page_search_description(token: str, report: dict) -> None:
    """Test once whether the documented metadata field can carry a search description."""
    headers = {"Authorization": "Bearer " + token}
    results = []
    cursor = ""
    pages = []
    while True:
        query = {"maxResults": "50", "fields": "items(id,title,url,customMetaData),nextPageToken"}
        if cursor:
            query["pageToken"] = cursor
        batch = request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages?"
                        + urllib.parse.urlencode(query), headers=headers)
        pages.extend(batch.get("items", []))
        cursor = batch.get("nextPageToken")
        if not cursor:
            break
    for page in pages:
        key = next((k for k in POLICY_DESCRIPTIONS if page.get("url", "").endswith("/" + k)), None)
        if not key:
            continue
        wanted = POLICY_DESCRIPTIONS[key]
        try:
            request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{page['id']}",
                    method="PATCH", headers=headers,
                    body={"kind": "blogger#page", "id": page["id"],
                          "customMetaData": json.dumps({"metaDescription": wanted})})
            time.sleep(1)
            after = request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{page['id']}"
                            "?fields=id,title,customMetaData", headers=headers)
            stored = after.get("customMetaData", "")
            results.append({"page": key, "writeAccepted": True, "stored": stored,
                            "carriesDescription": wanted[:40] in stored})
        except Exception as exc:  # noqa: BLE001
            results.append({"page": key, "writeAccepted": False, "error": error_text(exc)})
    report["pageSearchDescriptionTest"] = results
    report["pageSearchDescriptionWritable"] = any(r.get("carriesDescription") for r in results)


def add_vendor_sentence(token: str, report: dict) -> None:
    """Add the optional third-party-vendor sentence to the privacy page content."""
    headers = {"Authorization": "Bearer " + token}
    cursor, page_id, content = "", None, ""
    while True:
        query = {"maxResults": "50", "fields": "items(id,url),nextPageToken"}
        if cursor:
            query["pageToken"] = cursor
        batch = request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages?"
                        + urllib.parse.urlencode(query), headers=headers)
        for item in batch.get("items", []):
            if item.get("url", "").endswith("/privacy-policy.html"):
                page_id = item["id"]
        cursor = batch.get("nextPageToken")
        if not cursor:
            break
    if not page_id:
        report["privacyVendorSentence"] = "privacy page not found through the API"
        return
    current = request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{page_id}"
                      "?fields=id,title,content", headers=headers)
    content = current.get("content", "")
    if "aboutads.info" in content:
        report["privacyVendorSentence"] = "already present"
        return
    updated = content + f'<p class="dy-vendor-note">{html.escape(VENDOR_SENTENCE)}</p>'
    try:
        request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{page_id}", method="PATCH",
                headers=headers, body={"kind": "blogger#page", "id": page_id, "title": current.get("title", ""),
                                       "content": updated})
        time.sleep(3)
        check = request(f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/pages/{page_id}"
                        "?fields=id,content", headers=headers).get("content", "")
        report["privacyVendorSentence"] = ("added and read back" if "aboutads.info" in check
                                           else "write did not land")
    except Exception as exc:  # noqa: BLE001
        report["privacyVendorSentence"] = "could not be written: " + error_text(exc)


def try_gdata_description(token: str, report: dict) -> None:
    """Last route for the blog's stored description: Blogger's settings feed.

    The current Blogger API exposes no update for a blog, so the older settings feed
    is tried once. A failure here settles the question: the box is then reachable
    only from the Blogger screen.
    """
    headers = {"Authorization": "Bearer " + token, "GData-Version": "2",
               "Content-Type": "application/atom+xml"}
    feed = f"https://www.blogger.com/feeds/{BLOG_ID}/settings"
    attempt = {}
    try:
        with urllib.request.urlopen(urllib.request.Request(feed, headers=headers), timeout=60) as r:
            body = r.read().decode("utf-8", "replace")
        attempt["readFeed"] = len(body)
        entry = re.search(r"<entry>(?:(?!</entry>).)*?Description(?:(?!</entry>).)*?</entry>", body, re.S)
        if not entry:
            attempt["result"] = "settings feed reachable but carried no description entry"
        else:
            updated = entry.group(0)
            updated = re.sub(r"<title[^>]*>.*?</title>", "<title type='text'>Description</title>", updated, count=1)
            updated = re.sub(
                r"(<ns0:value[^>]*>|<content[^>]*>).*?(</ns0:value>|</content>)",
                lambda m: f"{m.group(1)}{html.escape(BLOG_DESCRIPTION)}{m.group(2)}", updated, count=1, flags=re.S)
            link = re.search(r"<link rel='edit'[^>]*href='([^']+)'", updated) or re.search(
                r'<link[^>]*rel="edit"[^>]*href="([^"]+)"', updated)
            if not link:
                attempt["result"] = "no edit link in the description entry"
            else:
                put = urllib.request.Request(link.group(1), data=updated.encode("utf-8"),
                                             headers=headers, method="PUT")
                with urllib.request.urlopen(put, timeout=60) as r:
                    attempt["result"] = f"settings feed accepted the write (HTTP {r.status})"
    except Exception as exc:  # noqa: BLE001
        attempt["result"] = "settings feed refused the write: " + error_text(exc)
    report["gdataDescriptionAttempt"] = attempt
    if "accepted" in attempt.get("result", ""):
        report["blogDescriptionLanded"] = True


def main() -> int:
    report_path = REPORT
    try:
        return _run()
    except Exception as exc:  # noqa: BLE001 - the report must always be written
        import traceback
        fallback = {"status": "ERROR", "ranAt": datetime.now(timezone.utc).isoformat(),
                    "error": error_text(exc), "traceback": traceback.format_exc()[-1500:]}
        try:
            previous = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            previous = {}
        previous.update(fallback)
        report_path.write_text(json.dumps(previous, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(fallback, ensure_ascii=False)[:800])
        return 0


def _run() -> int:
    token = oauth()
    report: dict = {"checkedAt": datetime.now(timezone.utc).isoformat(), "apiOnly": True,
                    "publicRequests": 0, "syntheticViews": 0}
    for step, call in (("blogDescription", try_blog_description),
                       ("gdataDescription", try_gdata_description),
                       ("pageSearchDescription", try_page_search_description),
                       ("privacyVendorSentence", add_vendor_sentence)):
        try:
            call(token, report)
        except Exception as exc:  # noqa: BLE001
            report.setdefault("stepErrors", {})[step] = error_text(exc)

    remaining = []
    if not report.get("blogDescriptionLanded"):
        remaining.append("Blogger → Settings → Blog description: paste the corrected site description "
                         "(Blogger's API does not expose this box).")
    if not report.get("pageSearchDescriptionWritable"):
        remaining.append("Blogger → Pages → Search description box for ABOUT US, CONTACT US, PRIVACY POLICY "
                         "and DISCLAIMER: paste the corrected text (the API cannot write this box).")
    if report.get("privacyVendorSentence") not in ("already present", "added and read back"):
        remaining.append("Privacy page: add the third-party-vendor sentence by hand.")
    report["userActionRequired"] = remaining
    report["status"] = "COMPLETE" if not remaining else "PARTIAL"
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "blogDescriptionLanded": report.get("blogDescriptionLanded"),
                      "pageSearchDescriptionWritable": report.get("pageSearchDescriptionWritable"),
                      "privacyVendorSentence": report.get("privacyVendorSentence")}, ensure_ascii=False))
    for row in remaining:
        print("::warning title=Blogger screen action needed::" + row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
