#!/usr/bin/env python3
"""Instagram may be unarmed, but it must never be wrong: no double posts, no fake success,
no unfinished image published, no public page read, and no token written anywhere."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import instagram_publisher as ig

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def post(url='https://dailyyield.blogspot.com/2026/10/example-article.html'):
    return {'id': '1', 'title': 'Build a Stronger Cash Buffer', 'url': url,
            'published': (NOW - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'content': '<p>' + ('The reserve decision changes how a household absorbs a missed payday. ' * 4) +
                       '</p><p><img src="https://lh3.googleusercontent.com/img/a=photo-one"></p>'}


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (ig.STATUS_PATH, ig.TRACKER_PATH)
        ig.STATUS_PATH, ig.TRACKER_PATH = self.tmp / 'status.json', self.tmp / 'tracker.json'
        self.env = mock.patch.dict(os.environ, {'BLOGGER_BLOG_ID': '7', 'FACEBOOK_SYSTEM_USER_TOKEN': 'secret-token',
                                                'INSTAGRAM_BUSINESS_ACCOUNT_ID': '17841400000000000'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(lambda: setattr(ig, 'STATUS_PATH', self.saved[0]) or setattr(ig, 'TRACKER_PATH', self.saved[1]))

    def run_with(self, calls, posts):
        seen = []
        def graph_call(path, params):
            seen.append((path, dict(params)))
            return calls[len(seen) - 1] if len(seen) <= len(calls) else {}
        with mock.patch.object(ig, 'candidates', return_value=posts), \
             mock.patch.object(ig, 'blogger_token', return_value='b'):
            return ig.run(now=NOW, token_provider=lambda: 'b', graph_call=graph_call), seen


class Arming(Harness):
    def test_an_unarmed_channel_reports_the_gap_and_does_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            report = ig.run(now=NOW, token_provider=lambda: 'b', graph_call=lambda p, x: {})
        self.assertEqual('NOT_CONFIGURED', report['status'])
        self.assertEqual(0, report['attempted'])
        self.assertTrue(report['config']['waitingOnOwner'], 'the owner has to be told exactly what is missing')

    def test_the_account_number_and_token_are_the_only_two_things_missing(self):
        report = ig.run(now=NOW, token_provider=lambda: 'b', graph_call=lambda p, x: {})
        self.assertTrue(ig.config()['ready'], 'with the secret present the job is ready to run')

    def test_the_token_is_never_written_into_any_file_this_job_owns(self):
        calls = [{'id': 'c1'}, {'status_code': 'FINISHED'}, {'id': 'm1'}]
        self.run_with(calls, [post()])
        for path in (ig.STATUS_PATH, ig.TRACKER_PATH):
            if path.exists():
                self.assertNotIn('secret-token', path.read_text(), 'a token must never reach a committed file')
        text = Path('instagram_publisher.py').read_text()
        self.assertNotIn('print(env("FACEBOOK_SYSTEM_USER_TOKEN")', text)
        for forbidden in ('urllib.parse.urlencode({"access_token"', 'open("instagram_token'):
            self.assertNotIn(forbidden, text)


class Publishing(Harness):
    def test_the_container_is_published_only_after_instagram_finishing_the_image(self):
        calls = [{'id': 'c1'}, {'status_code': 'IN_PROGRESS'}, {'status_code': 'FINISHED'}, {'id': 'm1'}]
        with mock.patch.object(ig, 'POLL_SECONDS', 0):
            report, seen = self.run_with(calls, [post()])
        self.assertEqual('PUBLISHED', report['status'])
        self.assertEqual('/17841400000000000/media_publish', seen[-1][0])
        self.assertEqual({'creation_id': 'c1'}, seen[-1][1], 'publish takes the container id and nothing else')

    def test_an_image_instagram_rejected_is_recorded_and_never_published(self):
        calls = [{'id': 'c1'}, {'status_code': 'ERROR', 'status_message': 'unsuccessful download'}]
        with mock.patch.object(ig, 'POLL_SECONDS', 0):
            report, seen = self.run_with(calls, [post()])
        self.assertEqual(0, report['posted'])
        self.assertEqual('ATTACHED_BUT_NOT_PUBLISHED', report['status'])
        self.assertNotIn('media_publish', ' '.join(path for path, _ in seen))
        self.assertIn('unsuccessful download', report['rows'][0]['reason'])

    def test_the_same_article_is_never_posted_twice(self):
        calls = [{'id': 'c1'}, {'status_code': 'FINISHED'}, {'id': 'm1'}]
        with mock.patch.object(ig, 'POLL_SECONDS', 0):
            self.run_with(calls, [post()])
            second, seen = self.run_with(calls, [post()])
        self.assertEqual('NOTHING_DUE', second['status'])
        self.assertEqual(0, second['posted'])
        self.assertEqual([], seen, 'a deduplicated run must not call Instagram at all')

    def test_two_articles_a_day_at_most(self):
        posts = [post('https://dailyyield.blogspot.com/2026/10/a.html'),
                 post('https://dailyyield.blogspot.com/2026/10/b.html'),
                 post('https://dailyyield.blogspot.com/2026/10/c.html')]
        calls = [{'id': 'c1'}, {'status_code': 'FINISHED'}, {'id': 'm1'},
                 {'id': 'c2'}, {'status_code': 'FINISHED'}, {'id': 'm2'}]
        with mock.patch.object(ig, 'POLL_SECONDS', 0):
            report, _ = self.run_with(calls, posts)
        self.assertEqual(2, report['posted'])
        self.assertEqual(2, report['attempted'])

    def test_an_article_without_a_photograph_is_skipped_not_padded_with_a_substitute(self):
        bare = {'id': '2', 'title': 'A text-only article',
                'url': 'https://dailyyield.blogspot.com/2026/10/text.html',
                'published': (NOW - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'content': '<p>' + 'Nothing visual here, only sourced sentences about household reserves. ' * 3 + '</p>'}
        report, seen = self.run_with([], [bare])
        self.assertEqual('SKIPPED', report['rows'][0]['status'])
        self.assertEqual(0, report['posted'])
        self.assertEqual([], seen, 'no photograph means no call to Instagram')


class Honesty(Harness):
    def test_the_caption_fits_instagram_and_points_at_the_bio(self):
        text = ig.caption_for({'title': 'T' * 400, 'content': '<p>' + 'word ' * 900 + '</p>'}, 'link in bio')
        self.assertLessEqual(len(text), ig.MAX_CAPTION)
        self.assertIn('link in bio', text)
        self.assertTrue(text.strip())

    def test_the_work_never_requests_a_public_daily_yield_page(self):
        source = Path('instagram_publisher.py').read_text()
        self.assertIn('blogger/v3', source, 'candidates must come from the authenticated Blogger API')
        self.assertNotIn('requests.get(post["url"]', source)
        self.assertNotIn('requests.get(item["url"]', source)
        self.assertEqual(1, source.count('graph.facebook.com'), 'one graph host, built in one place')

    def test_the_workflow_stays_asleep_until_the_owner_arms_it(self):
        workflow = Path('.github/workflows/instagram_publisher.yml').read_text()
        self.assertIn("vars.INSTAGRAM_AUTOMATION_ENABLED == 'true'", workflow)
        self.assertIn('test_instagram_publisher', workflow)
        self.assertNotIn('contents: write\n    # nothing else', workflow)


if __name__ == '__main__':
    unittest.main()
