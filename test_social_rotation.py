import datetime as dt
import unittest

from social_rotation import (
    HEADER_PAGES, NEWS_KEYS, platform_for, resource_url, make_plan,
)


class SocialRotationTests(unittest.TestCase):
    def test_established_daily_distribution_pattern(self):
        day = dt.date(2026, 10, 1)
        news = [f"news-{desk}" for desk in NEWS_KEYS]
        resources = [f"resource-{i}" for i in range(5)]
        news_totals = {name: 0 for name in ("facebook", "bluesky", "tumblr", "mastodon")}
        resource_totals = dict.fromkeys(news_totals, 0)
        for key in news:
            news_totals[platform_for(key, day)] += 1
        for key in resources:
            resource_totals[platform_for(key, day)] += 1
        self.assertEqual(sorted(news_totals.values()), [4, 4, 6, 6])
        self.assertEqual(sorted(resource_totals.values()), [1, 1, 1, 2])

    def test_each_item_rotates_to_another_platform_next_day(self):
        day = dt.date(2026, 10, 1)
        keys = ([f"news-{desk}" for desk in NEWS_KEYS] +
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
