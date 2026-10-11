import json, os, tempfile, unittest
from datetime import date
from unittest.mock import patch
import growth_control_tower as tower
from growth_opportunity_engine import build

class GrowthSystemTest(unittest.TestCase):
 def test_control_tower_never_infers_readers(self):
  with patch.dict(os.environ,{},clear=True):
   report=tower.build(date(2026,10,11))
  self.assertIsNone(report['pace']['currentVerifiedDAU'])
  self.assertEqual(report['integrity']['syntheticViews'],0)
  self.assertFalse(report['integrity']['searchClicksAreReaders'])
 def test_opportunity_is_evidence_driven_and_guarded(self):
  report=build({'searchAcquisition':{'queryPage28Days':[{'query':'emergency fund size','page':'https://dailyyield.blogspot.com/x','impressions':1000,'clicks':5,'ctr':.005,'averagePosition':8}]}})
  self.assertEqual(report['status'],'READY');self.assertEqual(len(report['queue']),1)
  self.assertFalse(report['releasePolicy']['automaticPublishing'])
 def test_engaged_reader_instrumentation_is_strict(self):
  from pathlib import Path
  text=Path('apply_site_enhancements.py').read_text(encoding='utf-8')
  self.assertIn("active>=30&&depth>=50",text)
  self.assertIn("safeGet('dy-consent')==='all'",text)
  self.assertIn("gtag('event','article_read'",text)
  self.assertNotIn("gtag('event','page_view'",text)
if __name__=='__main__':unittest.main()
