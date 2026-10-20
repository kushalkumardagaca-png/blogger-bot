#!/usr/bin/env python3
"""The hub pages have to hand out real links, and the freeze rules still have to hold.

Live measurement this encodes (20 October 2026): /p/daily-news.html carries 53 anchor tags and
none of them points at a blog post, so the crawl path the whole operation depends on - story ->
hub -> today's articles - only exists after JavaScript runs.
"""
import json
import os
import pathlib
import re
import tempfile
import unittest

import frozen_hub_refresh as hubs


def make_post(index: int, news: bool) -> dict:
    title = (f"Economy, Trade & Jobs News — 2{index} October 2026" if news
             else f"Payoneer: How Stablecoin is Scaling in Cross-Border Payments {index}")
    return {"id": f"{index}", "title": title, "labels": ["News"] if news else ["Master Article"],
            "url": f"https://dailyyield.blogspot.com/2026/10/edition-{index}.html" if news
                   else f"https://dailyyield.blogspot.com/2026/10/article-{index}.html",
            "published": f"2026-10-{index:02d}T00:45:00+00:00",
            "content": f"<p>body {index}</p>"}


class HubLinkIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.cwd = os.getcwd()
        os.chdir(self.tmp)
        self.posts = [make_post(index, index <= 20) for index in range(1, 31)]
        self.news = "".join(f"<a href=\"https://dailyyield.blogspot.com/2026/10/edition-{i}.html\">e{i}</a>"
                            for i in range(1, 4))

    def tearDown(self):
        os.chdir(self.cwd)

    def run_hub(self, content: str, path: str = "/p/daily-news.html"):
        writes = []

        def put(kind, item, headers, body=None, labels=None):
            writes.append({"kind": kind, "id": item["id"], "content": body})
            return {}

        page = {"id": "1", "url": f"https://dailyyield.blogspot.com{path}", "title": "hub",
                "content": content, "labels": []}
        report = hubs.refresh_existing_hubs({}, self.posts, [page], put,
                                           lambda post, cat: "<a></a>", lambda post: {"title": post["title"]},
                                           [])
        return writes, report

    def test_the_news_hub_gets_plain_href_links_to_the_newest_editions(self):
        writes, _ = self.run_hub(f"<div>window.ENH_NEWS_SNAPSHOT=[];{self.news}</div>")
        self.assertEqual(len(writes), 1, "the hub must be written once")
        body = writes[0]["content"]
        hrefs = re.findall(r"DY_HUB_LINK_INDEX_START.*?DY_HUB_LINK_INDEX_END", body, re.S)
        self.assertEqual(len(hrefs), 1)
        links = re.findall(r'href="(https://dailyyield\.blogspot\.com/2026/10/edition-(\d+)\.html)"', hrefs[0])
        self.assertEqual(len(links), 12, "twelve crawlable links, no more")
        self.assertEqual(max(int(number) for _, number in links), 20, "newest first, capped")
        self.assertNotIn("article-", hrefs[0], "the news hub lists editions, not master articles")

    def test_the_article_hub_links_the_masters_instead(self):
        writes, _ = self.run_hub("<div>cards</div>", path="/p/article.html")
        body = writes[0]["content"]
        block = re.search(r"DY_HUB_LINK_INDEX_START.*?DY_HUB_LINK_INDEX_END", body, re.S).group(0)
        self.assertIn("article-30.html", block)
        self.assertNotIn("edition-", block)

    def test_a_second_run_writes_nothing_new(self):
        first, _ = self.run_hub(f"<div>window.ENH_NEWS_SNAPSHOT=[];{self.news}</div>")
        second, _ = self.run_hub(first[0]["content"])
        self.assertEqual(second, [], "the block is replaced in place, so the hub stops changing")

    def test_the_freeze_rules_still_hold_after_the_link_index(self):
        before = f"<div>window.ENH_NEWS_SNAPSHOT=[];<style>.a{{color:red}}</style><h2>Hub</h2>{self.news}</div>"
        writes, report = self.run_hub(before)
        after = writes[0]["content"]
        for pattern in (r"<style\b.*?</style>", r"<script\b[^>]*>", r"<h[1-6]\b.*?</h[1-6]>"):
            self.assertEqual(re.findall(pattern, before, re.S | re.I), re.findall(pattern, after, re.S | re.I),
                             f"{pattern} must be untouched during the freeze")
        row = report["routineHubDataRefreshes"][0]
        self.assertEqual(row["linkIndexHrefs"], 12)
        self.assertTrue(row["linkIndexWritten"])
        self.assertEqual(report["mode"], "FREEZE_DATA_ONLY")
        self.assertEqual(report["posts_rewritten"], 0)
        status = json.loads((self.tmp / "CONTENT_EXPERIENCE_REPAIR_STATUS.json").read_text())
        self.assertEqual(status["routineHubDataRefreshes"][0]["linkIndexHrefs"], 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
