#!/usr/bin/env python3
import json
import shutil
import tempfile
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

    def test_generated_messages_are_branded_multipart_and_pixel_free(self):
        original = (app.INTERACTIONS, app.QUEUE, app.MANIFEST)
        with tempfile.TemporaryDirectory(dir=app.OUTREACH) as directory:
            temporary = Path(directory)
            app.INTERACTIONS = temporary / "interactions.csv"
            app.INTERACTIONS.write_text("interaction_id,prospect_id,email,message_fingerprint,status,created_at,updated_at,follow_up_count,notes\n")
            app.QUEUE = temporary / "review_queue"
            app.MANIFEST = temporary / "manifest.json"
            try:
                self.assertEqual(app.draft(10), 0)
                manifest = json.loads(app.MANIFEST.read_text())
                self.assertEqual(manifest["mode"], "REVIEW_ONLY_NO_SEND_CAPABILITY")
                self.assertEqual(len(manifest["selected"]), 3)
                self.assertEqual({x["state"] for x in manifest["selected"]}, {"AUTOMATION_APPROVED_NOT_SENT", "REVIEW_REQUIRED_NOT_SENT"})
                for path in app.QUEUE.glob("*.eml"):
                    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
                    self.assertIn(message["X-Daily-Yield-State"], {"AUTOMATION-APPROVED-NOT-SENT", "REVIEW-REQUIRED-NOT-SENT"})
                    body = message.get_body(preferencelist=("plain",)).get_content()
                    html_body = message.get_body(preferencelist=("html",)).get_content()
                    self.assertNotIn("<img", body.lower())
                    self.assertIn("utm_source=editorial_outreach", body)
                    self.assertIn("cid:daily-yield-header", html_body)
                    self.assertNotIn("<script", html_body.lower())
                    self.assertNotIn("tracking", html_body.lower().replace("no tracking pixel", ""))
                    gifs = [part for part in message.walk() if part.get_content_type() == "image/gif"]
                    self.assertEqual(len(gifs), 1)
                    self.assertLess(len(gifs[0].get_payload(decode=True)), 100_000)
            finally:
                app.INTERACTIONS, app.QUEUE, app.MANIFEST = original


if __name__ == "__main__":
    unittest.main()
