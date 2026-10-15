import unittest
from content_policy_guard import audit_text,assert_social_compliant,automation_disclosure
class ContentPolicyGuardTests(unittest.TestCase):
 def test_deceptive_promise_fails_but_warning_context_passes(self):
  self.assertIn('deceptive financial or commercial promise',audit_text('x','This product offers guaranteed returns.'))
  self.assertNotIn('deceptive financial or commercial promise',audit_text('x','No investment offers guaranteed returns.'))
 def test_private_data_and_fake_experience_fail(self):
  issues=audit_text('x','I personally tested this investment. Card 4111 1111 1111 1111.')
  self.assertTrue(any('experience' in x for x in issues));self.assertTrue(any('payment-card' in x for x in issues))
 def test_disclosure_is_machine_verifiable_and_human_readable(self):
  block=automation_disclosure('article');self.assertIn('DY_AUTOMATION_DISCLOSURE_GREEN_V2',block);self.assertIn('does not state',block)
 def test_social_manufactured_urgency_fails(self):
  with self.assertRaisesRegex(RuntimeError,'manufactured urgency'):assert_social_compliant('Act now and read this')
 def test_repeated_substantive_sentence_fails(self):
  sentence='This sufficiently long substantive sentence explains a distinct financial mechanism for readers to evaluate carefully.'
  self.assertIn('repeated substantive sentence within the content',audit_text('x',sentence+' '+sentence))
 def test_accessibility_hidden_carousel_clone_is_not_editorial_repetition(self):
  sentence='This sufficiently long substantive sentence explains a distinct financial mechanism for readers to evaluate carefully.'
  content=f'<p>{sentence}</p><div aria-hidden="true"><p>{sentence}</p></div>'
  self.assertNotIn('repeated substantive sentence within the content',audit_text('x',content))
 def test_source_ledger_repeat_is_not_counted_as_repeated_editorial_prose(self):
  sentence='This sufficiently long source title describes a financial document for readers who want to inspect the evidence.'
  content=f'<p>{sentence}</p><section class="dy2-links"><ol><li>{sentence}</li></ol></section>'
  self.assertNotIn('repeated substantive sentence within the content',audit_text('x',content))
if __name__=='__main__':unittest.main()
