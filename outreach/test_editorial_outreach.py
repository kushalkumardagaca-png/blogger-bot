#!/usr/bin/env python3
import json
import shutil
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path

import editorial_outreach as app


class OutreachSafetyTests(unittest.TestCase):
    def test_registry_and_lock_are_valid(self):
        self.assertEqual(app.validation_errors(), [])
        lock = json.loads(app.SEND_LOCK.read_text())
        self.assertIsInstance(lock["sending_enabled"], bool)
        self.assertIsInstance(lock["gmail_oauth_configured"], bool)
        self.assertFalse(lock["tracking_pixels_allowed"])
        self.assertFalse(lock["synthetic_pageviews_allowed"])
        if lock["sending_enabled"]:
            self.assertTrue(lock["gmail_oauth_configured"])

    def test_only_explicitly_eligible_contacts_can_be_drafted(self):
        eligible = [
            row for row in app.read_csv(app.PROSPECTS)
            if row["eligibility"] == "eligible" and row["automation_mode"] == "auto_approved"
        ]
        self.assertEqual({row["prospect_id"] for row in eligible}, {"ft-opinion", "money-newsroom"})

    def test_specific_article_match(self):
        articles = app.load_articles()
        for prospect in app.read_csv(app.PROSPECTS):
            if prospect["prospect_id"] in {"ft-opinion", "money-newsroom"}:
                article, score = app.match_article(prospect, articles)
                self.assertEqual(article.title, "Emergency Fund Size by Job Type")
                self.assertGreater(score, 0)

    def test_generated_messages_are_review_only_and_pixel_free(self):
        self.assertEqual(app.draft(10), 0)
        manifest = json.loads(app.MANIFEST.read_text())
        self.assertEqual(manifest["mode"], "REVIEW_ONLY_NO_SEND_CAPABILITY")
        self.assertEqual(len(manifest["selected"]), 2)
        self.assertEqual({x["state"] for x in manifest["selected"]}, {"AUTOMATION_APPROVED_NOT_SENT"})
        for path in app.QUEUE.glob("*.eml"):
            message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            self.assertEqual(message["X-Daily-Yield-State"], "AUTOMATION-APPROVED-NOT-SENT")
            body = message.get_body(preferencelist=("plain",)).get_content()
            self.assertNotIn("<img", body.lower())
            self.assertIn("utm_source=editorial_outreach", body)


if __name__ == "__main__":
    unittest.main()
