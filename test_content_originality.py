import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from content_originality import assert_cross_corpus_original,contextualize_cross_corpus_repeats

class ContentOriginalityTests(unittest.TestCase):
 def test_exact_prior_sentence_is_contextualized_then_still_checked(self):
  repeated='This sufficiently long substantive sentence explains one bounded financial mechanism without promising any result.'
  with TemporaryDirectory() as folder:
   root=Path(folder);packages=root/'master_packages'/'dynamic';packages.mkdir(parents=True)
   (packages/'prior.json').write_text(json.dumps({'sections':[{'heading':'Prior evidence','paragraphs':[repeated]}]}))
   unique=' '.join(f'Unique current context number {i} examines a separate mechanism, jurisdiction, evidence limit, and reader question in careful detail.' for i in range(12))
   target=packages/'current.json';package={'sections':[{'heading':'Current evidence angle','paragraphs':[repeated+' '+unique]}]}
   contextualize_cross_corpus_repeats(package,target,root)
   self.assertTrue(package['sections'][0]['paragraphs'][0].startswith('For Current evidence angle,'))
   self.assertTrue(assert_cross_corpus_original(package,target,root))

if __name__=='__main__':unittest.main()
