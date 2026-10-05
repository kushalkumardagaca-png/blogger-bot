import csv,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import auto_blogger_publisher as publisher

class MasterPublisherTests(unittest.TestCase):
 def test_master_v2_is_published_without_legacy_context_or_four_item_shelf(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);tracker={'next_topic_index':0,'last_published_timestamp':None,'published_posts':[]}
   (root/'published_tracker.json').write_text(json.dumps(tracker))
   with (root/'topics.csv').open('w',newline='',encoding='utf-8') as handle:
    writer=csv.DictWriter(handle,fieldnames=['#','Category','Video Idea','Video Description','Punchy Title']);writer.writeheader();writer.writerow({'#':'1','Punchy Title':'Build a Stronger Cash Buffer','Category':'Cash Savings and Emergency Funds','Video Idea':'Evidence-led cash reserve analysis.','Video Description':'Household liquidity and competing priorities.'})
   v2='''<!-- DY_MASTER_V2 --><article><h1>Build a Stronger Cash Buffer</h1><div id="dyPageFamily"></div><!-- DY_CONTINUOUS_MOTION_START --></article>'''
   old=os.getcwd();os.chdir(root)
   try:
    with patch.object(publisher,'TRACKER_FILE','published_tracker.json'),patch.object(publisher,'CSV_FILE','topics.csv'),patch.object(publisher,'SOCIAL_EVENTS_FILE','social_events.json'),patch.object(publisher,'build_reader_value_article',return_value=('Build a Stronger Cash Buffer','build-a-stronger-cash-buffer','A compliant description.',['Cash Savings and Emergency Funds','Kushal K. Daga'],v2)),patch.object(publisher,'assert_publishable',return_value=True),patch.object(publisher,'publish_to_blogger',return_value={'id':'1','url':'https://dailyyield.blogspot.com/2026/10/build-a-stronger-cash-buffer.html'}) as publish:
     publisher.main()
    content=publish.call_args.args[1]
    self.assertIn('DY_MASTER_V2',content);self.assertNotIn('class="dy-context"',content);self.assertNotIn('class="dy-related"',content)
    self.assertEqual(json.loads((root/'published_tracker.json').read_text())['next_topic_index'],1)
   finally:os.chdir(old)
if __name__=='__main__':unittest.main()
