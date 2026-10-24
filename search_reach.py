#!/usr/bin/env python3
"""Zero-view search reach readiness, Google side only since 23 October 2026.

This file used to do two jobs: record crawler policy, and submit the two Blogger sitemaps to Bing
Webmaster Tools. The second job is gone - the owner deleted the property on 23 October 2026 and asked
for the Bing machinery to be deleted with it, so nothing here reads a Bing key, holds a Bing endpoint
or claims a submission was made. Until this edit the file still called a submit function that had
already been removed, which would have crashed the run on any day the secret happened to be present.
The fix is to say what is true: Google state belongs to `gsc_rebuild.py`, and this is a readiness note.

No Daily Yield public page is opened, and no figure is invented: everything reported is either a
constant of this blog's own addresses or a rule a crawler publishes about itself.
"""
from pathlib import Path
from datetime import datetime, timezone
import json

SITE = "https://dailyyield.blogspot.com/"
SITEMAPS = [SITE + "sitemap.xml", SITE + "sitemap-pages.xml"]
RETIRED = "retired by the owner on 23 October 2026"

# what each crawler has said it wants, and what we allow. This is a record of a public rule, not a
# request: Blogger answers robots.txt itself, so this job never fetches or edits that file.
CRAWLER_POLICY = {
    "Googlebot": "allow public indexable content",
    "bingbot": "allow public indexable content - Bing is not submitted to any more, but its crawler is "
               "not blocked either, and blocking it would only hide the site from one more reader",
    "ChatGPT-User": "allow discovery",
    "OAI-SearchBot": "allow discovery",
    "GPTBot": "publisher choice; not required for ChatGPT search",
}
NOTES = [
    "Blogger controls robots.txt from its Search preferences; this job never requests the public robots.txt URL.",
    "No crawler permission guarantees indexing, citation, ranking or traffic.",
    f"Bing Webmaster Tools: {RETIRED}; no submission is made or needed, and no key is read.",
    "Google indexing state and any Request-indexing step live in the Search Console workflows, not here.",
]


def main():
    rows = [{"sitemap": x,
             "status": "READY",
             "detail": "registered through Search Console by the dedicated workflow; Google side only since "
                       f"the owner retired Bing on 23 October 2026"} for x in SITEMAPS]
    report = {"checkedAt": datetime.now(timezone.utc).isoformat(),
              "mode": "ZERO_SYNTHETIC_VIEWS", "syntheticViews": 0, "site": SITE,
              "bingWebmasterTools": RETIRED, "sitemaps": rows,
              "crawlerPolicy": CRAWLER_POLICY, "notes": NOTES}
    Path("SEARCH_REACH_STATUS.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Daily Yield Search Reach", "",
             f"- Checked: {report['checkedAt']}",
             "- Mode: zero synthetic views",
             "- Google Search Console: managed by the dedicated authenticated `gsc_rebuild.py` workflow",
             f"- Bing Webmaster Tools: {RETIRED} - nothing is submitted there and nothing waits on it",
             "", "## Sitemaps"] + [f"- `{x['sitemap']}` - {x['status']}" for x in rows] + [
        "", "## Responsible crawler policy"] + [f"- {k}: {v}" for k, v in CRAWLER_POLICY.items()] + [
        "", "## Notes"] + [f"- {n}" for n in NOTES] + [""]
    Path("SEARCH_REACH_STATUS.md").write_text("\n".join(lines))
    print(json.dumps({"sitemaps": len(rows), "syntheticViews": 0, "bingWebmasterTools": RETIRED}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
