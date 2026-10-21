import unittest
from unittest.mock import patch
import preapproval_progress_report as report

class ProgressCountTest(unittest.TestCase):
    def test_durable_removals_not_only_latest_empty_cleanup(self):
        data={'facebook_tracker.json':{'deleted':[{'facebook_post_id':'first','reason':'same live article, verified duplicate'},{'facebook_post_id':'first','reason':'same live article, verified duplicate'}]},'mastodon_tracker.json':{'deleted':[{'mastodon_status_id':'second','reason':'same live article, verified duplicate'}]}}
        with patch.object(report,'load',side_effect=lambda name:data.get(name,{})):
            counts=report.verified_social_removals()
        self.assertEqual(sum(counts.values()),2)
        self.assertEqual(counts['facebook'],1);self.assertEqual(counts['mastodon'],1)

if __name__=='__main__':unittest.main()
