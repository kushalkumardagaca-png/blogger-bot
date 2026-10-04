import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import auto_blogger_publisher as publisher


class MasterPublisherTests(unittest.TestCase):
    def test_master_build_includes_required_context_and_related_shelf_before_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracker = {
                "next_topic_index": 0,
                "last_published_timestamp": None,
                "published_posts": [{
                    "topic_id": "old", "title": "Emergency Fund Size by Job Type",
                    "category": "Cash Savings and Emergency Funds",
                    "published_at": "2026-10-03 08:00",
                    "blogger_url": "https://dailyyield.blogspot.com/2026/10/emergency-fund-size.html",
                }],
            }
            (root / "published_tracker.json").write_text(json.dumps(tracker))
            with (root / "topics.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["#", "Category", "Video Idea", "Video Description", "Punchy Title"])
                writer.writeheader()
                writer.writerow({
                    "#": "1", "Punchy Title": "Put Money on the Calendar, Not Your Mood",
                    "Category": "Rich Habits vs Broke Habits",
                    "Video Idea": "Use calendar-based money reviews instead of emotional reactions.",
                    "Video Description": "A practical system for scheduled saving and deliberate spending.",
                })
            old = os.getcwd(); os.chdir(root)
            try:
                with patch.object(publisher, "TRACKER_FILE", "published_tracker.json"), \
                     patch.object(publisher, "CSV_FILE", "topics.csv"), \
                     patch.object(publisher, "SOCIAL_EVENTS_FILE", "social_events.json"), \
                     patch.object(publisher, "generate_hero_image_figure", return_value='<figure><img src="https://images.unsplash.com/test.jpg" alt="Calendar based money plan"></figure>'), \
                     patch.object(publisher, "fetch_public_posts", return_value=[]), \
                     patch("publication_preflight.image_works", return_value=True), \
                     patch.object(publisher, "publish_to_blogger", return_value={"id": "1", "url": "https://dailyyield.blogspot.com/2026/10/put-money-on-calendar.html"}) as publish:
                    publisher.main()
                content = publish.call_args.args[1]
                self.assertIn('class="dy-context"', content)
                self.assertIn('class="dy-related"', content)
                updated = json.loads((root / "published_tracker.json").read_text())
                self.assertEqual(updated["next_topic_index"], 1)
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
