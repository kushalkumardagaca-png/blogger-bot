import unittest
import adsense_readiness as a

class AdSenseReadinessTests(unittest.TestCase):
 def test_every_required_policy_surface_has_a_specific_disclosure(self):
  self.assertEqual(set(a.POLICY_BLOCKS),{'privacy-policy.html','terms-and-conditions.html','disclaimer.html','about-us_02080501126.html','contact-us_01883938366.html'})
  for key,block in a.POLICY_BLOCKS.items():
   self.assertIn('<h2',block,key);self.assertNotIn('<h1',block,key)

 def test_policy_url_matching_is_exact(self):
  self.assertEqual(a.policy_key('https://dailyyield.blogspot.com/p/privacy-policy.html'),'privacy-policy.html')
  self.assertIsNone(a.policy_key('https://dailyyield.blogspot.com/2026/10/privacy-policy-explained.html'))

 def test_disclosure_is_repeat_safe_and_preserves_unrelated_content(self):
  original='<article><h1>Privacy Policy</h1><p>Existing text remains.</p></article>'
  once=a.ensure_block(original,'privacy-policy.html');twice=a.ensure_block(once,'privacy-policy.html')
  self.assertEqual(once,twice)
  self.assertIn(original,once)
  self.assertEqual(once.count(a.START),1);self.assertEqual(once.count(a.END),1)

 def test_existing_marked_block_is_replaced_not_duplicated(self):
  old='before'+a.START+'old wording'+a.END+'after'
  new=a.ensure_block(old,'disclaimer.html')
  self.assertIn('before',new);self.assertIn('after',new);self.assertNotIn('old wording',new)
  self.assertEqual(new.count(a.START),1)

 def test_alt_repair_result_is_unpacked_before_policy_insertion(self):
  repaired,count=a.repair_image_alts('<p>Text</p><img src="x">','Example')
  self.assertIsInstance(repaired,str);self.assertEqual(count,1)
  final=a.ensure_block(repaired,'privacy-policy.html')
  self.assertIn('alt="Example — editorial photograph"',final)

if __name__=='__main__':unittest.main()


class AdSenseIdentityTests(unittest.TestCase):
 def test_identity_block_names_both_monitored_addresses(self):
  import identity_contact as ident
  block=ident.identity_block('page')
  self.assertIn(ident.PRIMARY_EMAIL,block)
  self.assertIn(ident.OWNER_EMAIL,block)
  self.assertIn('Kushal K. Daga',block)
  self.assertIn('no postal address is published',block)

 def test_identity_block_is_repeat_safe_on_the_policy_pages(self):
  original='<article><h1>Contact Us</h1><p>Existing text remains.</p></article>'
  once=a.ensure_identity(original,'contact-us_01883938366.html')
  twice=a.ensure_identity(once,'contact-us_01883938366.html')
  self.assertEqual(once.count(a.IDENTITY_START),1)
  self.assertEqual(once,twice)
  self.assertIn(original.split('</h1>')[0],once)

 def test_contradictory_reply_time_is_replaced(self):
  page='<p>Replies in 24–48 hrs</p><p>Reply lands within 2–3 working days</p>'
  out=a.ensure_identity(page,'contact-us_01883938366.html')
  self.assertNotIn('24–48',out)
  self.assertIn('Replies usually within 2–3 working days',out)

 def test_pages_without_the_identity_requirement_are_left_alone(self):
  page='<p>Fine print stays exactly as written.</p>'
  self.assertEqual(a.ensure_identity(page,'terms-and-conditions.html'),page)

 def test_article_footer_routes_to_both_inboxes(self):
  from content_policy_guard import automation_disclosure
  block=automation_disclosure('article')
  self.assertIn('dailyyield.official@gmail.com',block)
  self.assertIn('kushalkumardaga.ca@gmail.com',block)
  self.assertIn('Report abuse',block)
