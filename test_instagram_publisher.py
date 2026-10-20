#!/usr/bin/env python3
"""Instagram must behave like the rest of the operation: prove first, post once.

These tests hold the route to the rules that already protect the site: no public
request to a Daily Yield URL, no image that is not licensed and already held, no
phantom announcement for an article that never published, no duplicate post, and no
write when the account's own quota says stop.
"""
import datetime as dt
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import instagram_publisher as ig
from PIL import Image


class TempHome(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._paths = {}
        for name in ("TOKEN_FILE", "STATE", "TRACKER", "PLAN", "STATUS", "HEALTH", "SLOT_EVIDENCE",
                     "EDITIONS", "MASTER_TRACKER"):
            self._paths[name] = getattr(ig, name)
            setattr(ig, name, self.tmp / self._paths[name].name)
        self._assets = ig.ROOT
        ig.ROOT = self.tmp
        (self.tmp / "assets" / "master").mkdir(parents=True)
        (self.tmp / "scheduled_ready").mkdir()

    def tearDown(self):
        ig.ROOT = self._assets
        for name, value in self._paths.items():
            setattr(ig, name, value)


def real_photo(folder: Path, slug: str, placement: int = 1):
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1600, 900), (120, 130, 140))
    draw = image.load()
    for y in range(900):
        for x in range(0, 1600, 40):
            draw[x, y] = (255, 255, 255)
    path = folder / f"photo-{placement}.jpg"
    image.save(path, "JPEG", quality=80)
    return path


def evidence(day="2026-10-20"):
    json.dump({"rows": [
        {"key": "master-evergreen-0", "live": True, "state": "on time",
         "url": f"https://dailyyield.blogspot.com/2026/10/emergency-fund-guide-{day}.html",
         "title": "Emergency fund sizing for a two-income household"},
        {"key": "news-india", "live": True, "state": "on time",
         "url": f"https://dailyyield.blogspot.com/2026/10/india-finance-news-{day}.html",
         "title": "India Finance News"},
        {"key": "master-trending-1", "live": False, "state": "overdue", "url": "",
         "title": "Never announced"},
    ]}, (ig.ROOT / "SLOT_GUARANTEE_STATUS.json").open("w"))


class MediaRules(TempHome):
    def test_a_daily_yield_page_is_never_fetched_by_this_job(self):
        self.assertTrue(ig.blocked_url("https://dailyyield.blogspot.com/2026/10/x.html"))
        self.assertEqual(ig.public_jpeg("https://dailyyield.blogspot.com/2026/10/x.html"), "")

    def test_jpeg_is_demanded_from_hosts_that_negotiate_formats(self):
        url = ig.public_jpeg("https://images.unsplash.com/photo-abc?auto=format&fit=crop&w=1200&h=630")
        self.assertIn("fm=jpg", url)
        self.assertEqual(ig.public_jpeg("https://example.com/a.png"), "",
                         "Instagram publishes JPEG only, so a PNG is refused, not converted blindly")

    def test_the_picture_is_the_article_s_own_licensed_photograph(self):
        item = {"url": "https://dailyyield.blogspot.com/2026/10/emergency-fund-guide-2026-10-20.html"}
        slug = ig.slug_of(item["url"])
        real_photo(ig.ROOT / "assets" / "master" / slug, slug)
        image = ig.image_for(item)
        self.assertTrue(image["url"].startswith(ig.RAW_ASSET_BASE))
        self.assertTrue(image["url"].endswith(".jpg"))
        self.assertEqual(image["basis"], "repository-asset")

    def test_no_photograph_means_no_post_rather_than_a_substitute(self):
        image = ig.image_for({"url": "https://dailyyield.blogspot.com/2026/10/orphan-article.html"})
        self.assertEqual(image["url"], "")
        self.assertEqual(image["basis"], "none")


class WordingLimits(TempHome):
    def test_caption_stays_inside_instagram_limits_and_keeps_the_brand_lines(self):
        item = {"title": "Guide " * 900, "lead": "x" * 1200}
        text = ig.caption(item)
        self.assertLessEqual(len(text), ig.MAX_CAPTION)
        for line in ig.BRAND_LINES:
            self.assertIn(line, text)
        self.assertLessEqual(text.count("#"), ig.MAX_HASHTAGS)
        self.assertLessEqual(text.count("@"), ig.MAX_MENTIONS)

    def test_alt_text_is_capped(self):
        self.assertLessEqual(len(ig.alt_text({"title": "y" * 4000}, {})), ig.MAX_ALT)

    def test_the_plan_file_is_the_only_cadence_switch_and_it_is_clamped(self):
        (ig.ROOT / "INSTAGRAM_PLAN.json").write_text(json.dumps({"postsPerDay": 900,
                                                                  "minSpacingMinutes": 1}))
        configuration = ig.plan()
        self.assertEqual(configuration["postsPerDay"], 24)
        self.assertEqual(configuration["minSpacingMinutes"], 5)


class Eligibility(TempHome):
    def test_only_articles_proven_live_are_candidates(self):
        evidence()
        keys = {row["key"] for row in ig.eligible("2026-10-20")}
        self.assertEqual(keys, {"master-evergreen-0", "news-india"})

    def test_the_queue_is_master_articles_plus_one_digest_not_the_news_firehose(self):
        evidence()
        chosen, digest = ig.masters_only(ig.eligible("2026-10-20"), True)
        self.assertEqual([row["key"] for row in chosen], ["master-evergreen-0"])
        self.assertEqual(digest["key"], "instagram-digest")


class FakeGraph:
    """Answers exactly the endpoints the publisher is allowed to call."""

    RequestException = Exception

    def __init__(self, *, quota_remaining=10, container="FINISHED", publish_ok=True):
        self.calls = []
        self.quota_remaining = quota_remaining
        self.container = container
        self.publish_ok = publish_ok

    def get(self, url, params=None, timeout=None, **kwargs):
        return self.request("GET", url, params=params, timeout=timeout)

    def request(self, method, url, params=None, timeout=None, **kwargs):
        response = mock.Mock()
        response.ok = True
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        self.calls.append((method, url.split("/")[-1] if "/" in url else url, dict(params or {})))
        if "content_publishing_limit" in url:
            response.json = lambda: {"data": [{"quota_usage_total": {"quota_usage": 50 - self.quota_remaining,
                                                                     "quota_total": 50}}]}
            return response
        if url.endswith("/media_publish"):
            if not self.publish_ok:
                response.ok = False
                response.json = lambda: {"error": {"code": 9, "error_subcode": 2207042,
                                                    "message": "daily publishing limit reached"}}
            else:
                response.json = lambda: {"id": "900"}
            return response
        if url.endswith("/media"):
            response.json = lambda: {"id": "container-1"}
            return response
        if str((params or {}).get("fields", "")) == "status_code":
            response.json = lambda: {"status_code": self.container}
            return response
        response.json = lambda: {"id": "1784", "username": "daily_yield", "account_type": "BUSINESS"}
        return response


class RunModes(TempHome):
    def _run(self, argv, graph, *, token="tok"):
        env = {"INSTAGRAM_ACCESS_TOKEN": token, "INSTAGRAM_IG_USER_ID": "1784"}
        with mock.patch.dict(ig.os.environ, env, clear=False), mock.patch.object(ig, "requests", graph), \
             mock.patch("sys.argv", ["instagram_publisher.py"] + argv):
            code = ig.main()
        return code, json.loads((ig.ROOT / "INSTAGRAM_ROUTE_STATUS.json").read_text())

    def test_missing_credentials_report_themselves_without_failing_the_day(self):
        (ig.ROOT / "INSTAGRAM_ACCESS_TOKEN").unlink(missing_ok=True)
        with mock.patch.dict(ig.os.environ, {}, clear=True), mock.patch("sys.argv", ["x"]):
            code = ig.main()
        health = json.loads((ig.ROOT / "SOCIAL_CREDENTIAL_HEALTH.json").read_text())
        self.assertEqual(code, 0)
        self.assertIs(health["instagram"]["ok"], False)
        self.assertIn("not connected", health["instagram"]["reason"].lower())

    def test_a_personal_account_is_refused_before_any_write(self):
        graph = FakeGraph()
        graph.request = lambda method, url, params=None, timeout=None, **k: (
            type("R", (), {"ok": False, "status_code": 400,
                           "json": staticmethod(lambda: {"error": {"message": "not professional"}}),
                           "headers": {"content-type": "application/json"}})())
        with mock.patch.dict(ig.os.environ, {"INSTAGRAM_ACCESS_TOKEN": "t", "INSTAGRAM_IG_USER_ID": "1"},
                             clear=False), mock.patch.object(ig, "requests", graph), \
             mock.patch("sys.argv", ["x", "--mode", "health"]):
            ig.main()
        health = json.loads((ig.ROOT / "SOCIAL_CREDENTIAL_HEALTH.json").read_text())
        self.assertIs(health["instagram"]["ok"], False)

    def test_preflight_builds_the_post_and_sends_nothing(self):
        evidence()
        slug = "emergency-fund-guide-2026-10-20"
        real_photo(ig.ROOT / "assets" / "master" / slug, slug)
        graph = FakeGraph()
        code, report = self._run(["--mode", "preflight"], graph)
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "PREFLIGHT")
        self.assertTrue(report["published"], "the digest or a master should have been built")
        self.assertEqual([call for call in graph.calls if call[0] == "POST"], [],
                         "preflight must not create a container")

    def test_a_finished_container_is_published_once_and_recorded(self):
        evidence()
        slug = "emergency-fund-guide-2026-10-20"
        real_photo(ig.ROOT / "assets" / "master" / slug, slug)
        graph = FakeGraph()
        self._run(["--mode", "sweep", "--force"], graph)
        tracker = json.loads((ig.ROOT / "instagram_tracker.json").read_text())
        posted = [row for row in tracker["published"] if not row.get("dryRun")]
        self.assertEqual(len(posted), 1)
        self.assertEqual(posted[0]["key"], "master-evergreen-0")
        self.assertTrue(posted[0]["instagramMediaId"])

    def test_a_second_sweep_never_repeats_the_same_article(self):
        evidence()
        slug = "emergency-fund-guide-2026-10-20"
        real_photo(ig.ROOT / "assets" / "master" / slug, slug)
        graph = FakeGraph()
        self._run(["--mode", "sweep", "--force"], graph)
        second = FakeGraph()
        self._run(["--mode", "sweep", "--force"], second)
        self.assertEqual([call for call in second.calls if call[0] == "POST"], [],
                         "an already-posted article must not be posted again")
        tracker = json.loads((ig.ROOT / "instagram_tracker.json").read_text())
        self.assertEqual(len([r for r in tracker["published"] if not r.get("dryRun")]), 1)

    def test_a_container_that_never_finishes_is_reported_and_not_published(self):
        evidence()
        slug = "emergency-fund-guide-2026-10-20"
        real_photo(ig.ROOT / "assets" / "master" / slug, slug)
        graph = FakeGraph(container="ERROR")
        _code, report = self._run(["--mode", "sweep", "--force"], graph)
        self.assertEqual([call for call in graph.calls if call[1] == "media_publish"], [])
        self.assertTrue(any("did not become publishable" in row["reason"] for row in report["skipped"]))

    def test_the_accounts_own_quota_stops_the_route_before_the_api_says_no(self):
        evidence()
        slug = "emergency-fund-guide-2026-10-20"
        real_photo(ig.ROOT / "assets" / "master" / slug, slug)
        graph = FakeGraph(quota_remaining=1)
        _code, report = self._run(["--mode", "sweep", "--force"], graph)
        self.assertEqual(report["status"], "QUOTA_PAUSE")
        self.assertEqual([call for call in graph.calls if call[0] == "POST"], [])

    def test_the_daily_cap_and_the_spacing_rule_are_both_respected(self):
        evidence()
        day = dt.datetime.now(IG_IST).strftime("%Y-%m-%d")
        (ig.ROOT / "instagram_tracker.json").write_text(json.dumps({"version": 1, "published": [
            {"url": "https://dailyyield.blogspot.com/2026/10/other.html", "key": "master-evergreen-1",
             "published_at": dt.datetime.now(dt.timezone.utc).isoformat()}] * 24}))
        graph = FakeGraph()
        _code, report = self._run(["--mode", "sweep"], graph)
        self.assertIn(report["status"], ("DAY_COMPLETE", "SPACING_PAUSE"))
        self.assertEqual([call for call in graph.calls if call[0] == "POST"], [])


IG_IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


class IdentityFromTokenOnly(TempHome):
    """The owner pastes one token into GitHub. Nothing else should be required."""

    def test_the_token_supplies_its_own_account_id(self):
        graph = FakeGraph()
        with mock.patch.dict(ig.os.environ, {"INSTAGRAM_ACCESS_TOKEN": "tok"}, clear=True), \
             mock.patch.object(ig, "requests", graph):
            self.assertEqual(ig.ig_user_id(), "1784")
        self.assertTrue(any(call[0] == "GET" and call[1] == "me" and call[2].get("fields") == "id"
                            for call in graph.calls), graph.calls)

    def test_facebook_login_still_demands_the_id_because_me_is_a_person_there(self):
        graph = FakeGraph()
        with mock.patch.dict(ig.os.environ, {"INSTAGRAM_ACCESS_TOKEN": "tok"}, clear=True), \
             mock.patch.object(ig, "requests", graph), mock.patch.object(ig, "MODE", "facebook_login"):
            with self.assertRaises(RuntimeError) as caught:
                ig.ig_user_id()
        self.assertIn("facebook", str(caught.exception).lower())
        self.assertEqual([call for call in graph.calls if call[0] == "GET"], [],
                         "a Facebook-mode /me would be the wrong id, so it must not even be asked")

    def test_a_token_that_cannot_identify_its_account_says_so(self):
        graph = FakeGraph()
        graph.request = lambda method, url, params=None, timeout=None, **k: (
            type("R", (), {"ok": False, "status_code": 400, "headers": {"content-type": "application/json"},
                           "json": staticmethod(lambda: {"error": {"message": "invalid token"}})})())
        with mock.patch.dict(ig.os.environ, {"INSTAGRAM_ACCESS_TOKEN": "bad"}, clear=True), \
             mock.patch.object(ig, "requests", graph):
            with self.assertRaises(RuntimeError) as caught:
                ig.ig_user_id()
        self.assertIn("invalid token", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
