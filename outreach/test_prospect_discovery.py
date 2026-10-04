#!/usr/bin/env python3
import unittest

import prospect_discovery as app


class ProspectDiscoveryTests(unittest.TestCase):
    def test_accepts_same_domain_explicit_finance_invitation(self):
        raw = """<html><head><title>Clear Money Journal | Contributors</title></head><body>
        <h1>Personal finance contributor guidelines</h1>
        <p>We welcome original investing and saving story pitches. Email our editorial team at
        pitches@clearmoney.example to submit a concise pitch.</p></body></html>"""
        rows = app.classify("https://clearmoney.example/write-for-us", raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "pitches@clearmoney.example")
        self.assertEqual(rows[0]["automation_mode"], "auto_approved")

    def test_rejects_free_mail_and_unrelated_addresses(self):
        raw = """<html><head><title>Money Journal</title></head><body>
        Personal finance writers are welcome to send guest pitches to editor@gmail.com.
        </body></html>"""
        self.assertEqual(app.classify("https://moneyjournal.example/contribute", raw), [])

    def test_rejects_paid_or_backlink_routes(self):
        raw = """<html><head><title>Finance Posts</title></head><body>
        Submit a personal finance guest pitch to editor@financeposts.example.
        An editorial fee applies and each post includes dofollow backlinks.
        </body></html>"""
        self.assertEqual(app.classify("https://financeposts.example/write", raw), [])

    def test_ai_prohibition_is_human_only(self):
        raw = """<html><head><title>Evidence Finance</title></head><body>
        We welcome personal finance freelance pitches. Email editor@evidencefinance.example.
        Do not submit AI generated work.
        </body></html>"""
        rows = app.classify("https://evidencefinance.example/pitches", raw)
        self.assertEqual(rows[0]["automation_mode"], "human_only")


if __name__ == "__main__":
    unittest.main()
