#!/usr/bin/env python3
import unittest
from datetime import datetime, timezone

import gmail_sender as app


class GmailSenderPolicyTests(unittest.TestCase):
    def test_recipient_local_business_window(self):
        instant = datetime(2026, 10, 5, 3, 30, tzinfo=timezone.utc)  # 09:00 India, 23:30 New York (prior day)
        self.assertTrue(app.prospect_due({"timezone": "Asia/Kolkata"}, instant))
        self.assertFalse(app.prospect_due({"timezone": "America/New_York"}, instant))

    def test_invalid_timezone_fails_closed(self):
        self.assertFalse(app.prospect_due({"timezone": "Not/AZone"}, datetime.now(timezone.utc)))


if __name__ == "__main__":
    unittest.main()
