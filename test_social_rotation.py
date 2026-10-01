import datetime as dt
import unittest

from social_rotation import (
    HEADER_PAGES, NEWS_KEYS, platform_for, resource_url, make_plan,
)


class SocialRotationTests(unittest.TestCase):
    def test_daily_quota_and_every_content_type_on_every_platform(self):
        day = dt.date(2026, 10, 1)
        classes = {
            "master": [f"master-{i}" for i in range(5)],
            "news": [f"news-{desk}" for desk in NEWS_KEYS],
            "resource": [f"resource-{i}" for i in range(5)],
        }
        all_keys = sum(classes.values(), [])
        totals = {name: 0 for name in ("facebook", "bluesky", "tumblr", "mastodon")}
        for key in all_keys:
            totals[platform_for(key, day)] += 1
        self.assertEqual(totals, {"facebook": 10, "bluesky": 8, "tumblr": 6, "mastodon": 6})
        for keys in classes.values():
            self.assertEqual(set(platform_for(key, day) for key in keys), set(totals))

    def test_each_item_moves_to_another_platform_next_day(self):
        day = dt.date(2026, 10, 1)
        keys = ([f"master-{i}" for i in range(5)] +
                [f"news-{desk}" for desk in NEWS_KEYS] +
                [f"resource-{i}" for i in range(5)])
        for key in keys:
            self.assertNotEqual(platform_for(key, day), platform_for(key, day + dt.timedelta(days=1)), key)

    def test_homepage_plus_four_distinct_rotating_header_pages(self):
        day = dt.date(2026, 10, 1)
        urls = [resource_url(i, day) for i in range(5)]
        self.assertEqual(urls[0], "https://dailyyield.blogspot.com/")
        self.assertEqual(len(set(urls)), 5)
        self.assertTrue(set(urls[1:]).issubset(set(HEADER_PAGES)))
        tomorrow = [resource_url(i, day + dt.timedelta(days=1)) for i in range(1, 5)]
        self.assertNotEqual(urls[1:], tomorrow)

    def test_article_wait_is_fifteen_minutes(self):
        now = dt.datetime(2026, 10, 1, 5, 0, tzinfo=dt.timezone.utc)
        published = now.isoformat()
        plan = make_plan("news-india", "https://dailyyield.blogspot.com/2026/10/india.html",
                         "post", published, "", now=now)
        self.assertEqual(plan["delay_seconds"], 900)

    def test_rejects_non_official_destination(self):
        with self.assertRaises(ValueError):
            make_plan("news-india", "https://example.com/story", "post", "", "")


if __name__ == "__main__":
    unittest.main()
