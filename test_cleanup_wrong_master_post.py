import sys,unittest
from unittest.mock import patch
import cleanup_wrong_master_post as cleanup

class CleanupWrongMasterTests(unittest.TestCase):
 def test_status_may_be_omitted_for_live_get_by_path_response(self):
  duplicate='https://example.test/wrong';replacement='https://example.test/right'
  rows={replacement:{'id':'2','title':'Right','url':replacement},duplicate:{'id':'1','title':'Budget Airlines Lose Their Cost Edge','url':duplicate}}
  calls=[]
  def by_url(url,access):return rows.get(url)
  def call(path,access,method='GET'):calls.append((path,method));return {}
  argv=['cleanup','--duplicate-url',duplicate,'--replacement-url',replacement,'--expected-title-phrase','Budget Airlines']
  with patch.object(sys,'argv',argv),patch.object(cleanup,'token',return_value='token'),patch.object(cleanup,'by_url',side_effect=by_url),patch.object(cleanup,'call',side_effect=call):cleanup.main()
  self.assertEqual(calls,[('/posts/1','DELETE')])

if __name__=='__main__':unittest.main()
