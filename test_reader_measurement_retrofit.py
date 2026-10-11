import unittest
from pathlib import Path
import reader_measurement_retrofit as r
class ReaderMeasurementRetrofitTests(unittest.TestCase):
 def test_threshold_consent_and_idempotent_marker(self):
  self.assertIn('active>=30&&depth>=50',r.SNIPPET)
  self.assertIn("localStorage.getItem('dy-consent')==='all'",r.SNIPPET)
  self.assertIn("gtag('event','article_read'",r.SNIPPET)
  self.assertEqual(r.SNIPPET.count(r.MARK),2)
 def test_no_public_site_request(self):
  text=Path('reader_measurement_retrofit.py').read_text()
  self.assertNotIn('requests.get',text);self.assertNotIn('dailyyield.blogspot.com',text)
if __name__=='__main__':unittest.main()
