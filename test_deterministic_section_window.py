import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import master_v3_generator as gen  # noqa: E402

# The validator's window is ninety words wide and a fallback paragraph is about a hundred words, so the
# length a section arrives at is decided by how the top-up is admitted, not by how much evidence exists.
# On 24 October 2026 an evergreen slot reached 392 words - eight short - with three substitute topics
# refused the same way, and the day's slot was lost to a repairable rounding problem. The fallback now
# admits single sentences once whole paragraphs can no longer land inside the window, and it searches
# further through the same cited records while it does so.
LOW, HIGH = 400, 490

SENTENCES = [
    "Indian banks advanced rupee loans to small firms at the slowest pace in six months in October as risk weights tightened.",
    "Deposit costs stayed near 7.4 per cent while the share of sanctioned but undisbursed limits rose to 18 per cent.",
    "The supervisory note attributes roughly 40 per cent of the compression to revised risk weights rather than the policy rate.",
    "Central government grant schemes disbursed 1,84,000 crore rupees to micro and small enterprises in the fiscal year.",
    "Of that total, 62 per cent reached firms with fewer than twenty workers and the rest went to exporters.",
    "Across 10,480 surveyed manufacturers in nine states, 31 per cent reported a rejected or withdrawn application.",
    "A change to the risk-weight framework raises the capital charge on unsecured small business exposure by 12 per cent.",
    "For a borrower repaying 45 lakh rupees over eight years at 11.5 per cent, the deduction cap raises the effective cost.",
]


def sources(count, sentences):
    out = []
    for index in range(count):
        text = ' '.join(SENTENCES[(index * 3 + offset) % len(SENTENCES)] for offset in range(sentences))
        out.append((index + 1, {'name': 'Source Desk %d' % (index + 1),
                                'title': 'Quarterly credit conditions note %d' % (index + 1),
                                'text': text}))
    return out


class TheWindowIsTheContract(unittest.TestCase):
    """Whatever the fallback does internally, what the site publishes has to satisfy validate_section."""

    def test_every_source_shape_that_has_enough_evidence_lands_inside_the_window(self):
        for count in (2, 3, 4, 5, 6, 8):
            for sentences in (2, 3, 4, 6, 8):
                with self.subTest(records=count, sentences=sentences):
                    srcs = sources(count, sentences)
                    if count * sentences < 8:
                        # Too little to attribute: the fallback is allowed to refuse, and it must say so
                        # with the honest reason rather than hand over a section the validator would bury.
                        try:
                            gen.deterministic_section('Evidence angle 1: small business credit', srcs)
                        except RuntimeError as exc:
                            self.assertTrue(str(exc), 'a refusal has to name its reason')
                        continue
                    paragraphs = gen.deterministic_section(
                        'Evidence angle 1: small business credit and the cost of waiting', srcs)
                    total = gen.words(' '.join(paragraphs))
                    self.assertGreaterEqual(total, LOW, 'the fallback stopped %d words short' % (LOW - total))
                    self.assertLessEqual(total, HIGH, 'the fallback overshot the window by %d words' % (total - HIGH))
                    ok, error = gen.validate_section(paragraphs, gen.evidence_text(srcs))
                    self.assertTrue(ok, 'the validator refused a section the fallback returned: ' + error)
                    self.assertGreaterEqual(len(paragraphs), 4)
                    ids = list(gen.evidence_text(srcs))
                    for paragraph in paragraphs:
                        self.assertTrue(any('[[S%s|' % i in paragraph for i in ids),
                                        'a paragraph was handed to the article without a citation')

    def test_records_that_all_tell_the_same_story_still_reach_the_window(self):
        """Five near-identical records, which is the shape that cost an evergreen slot on 24 October 2026:
        the passages were so alike that the candidate loop ran out before the count reached 400 words,
        the section was handed to the validator at 392 and refused, and the slot died. The fixture here is
        not a byte-for-byte reconstruction of that draft - the refused text was never stored, and saying
        otherwise would be pretending to a proof I do not have. What this pins is the contract the refused
        case broke: near-duplicate evidence still has to produce a section inside the window, with a
        citation in every paragraph and no figure that the records do not carry.
        """
        shared = ("Indian banks advanced rupee loans to small firms at the slowest pace in six months in "
                  "October as risk weights tightened and deposit costs stayed near 7.4 per cent. The "
                  "supervisory note attributes roughly 40 per cent of the compression to revised risk "
                  "weights rather than the policy rate move. Grant disbursements reached 1,84,000 crore "
                  "rupees across nine states in the fiscal year to March 2026. Researchers caution that "
                  "the sample over-represents firms that file audited accounts, and 31 per cent of them "
                  "reported a rejected or withdrawn application in the previous twelve months.")
        srcs = [(i + 1, {'name': 'Banking Standards', 'title': 'Quarterly credit conditions note',
                         'text': shared + ' Table %d records the 12 basis points added to unsecured '
                                          'small business pricing this quarter.' % (i + 1)})
                for i in range(5)]
        paragraphs = gen.deterministic_section(
            'Evidence angle 7: small business credit and the cost of waiting', srcs)
        total = gen.words(' '.join(paragraphs))
        self.assertGreaterEqual(total, LOW, 'the fallback stopped short of the window again')
        self.assertLessEqual(total, HIGH)
        ok, error = gen.validate_section(paragraphs, gen.evidence_text(srcs))
        self.assertTrue(ok, error)

    def test_nothing_is_invented_to_reach_the_count(self):
        # Every number the finished section asserts still has to appear in a cited record, measured the
        # way the validator measures it. A top-up that reached 400 words by writing new figures would
        # pass the length test and fail this one.
        srcs = sources(5, 3)
        blob = ' '.join(gen.evidence_text(srcs).values())
        for seed in range(6):
            with self.subTest(seed=seed):
                paragraphs = gen.deterministic_section(
                    'Evidence angle %d: small business credit and the cost of waiting' % seed, srcs)
                prose = re.sub(r'\[\[S\d+\|[^]]+\]\]', ' ', ' '.join(paragraphs))
                for number in re.findall(r'(?<![SI])\b\d[\d,.]*%?\b', prose):
                    self.assertIn(number, blob, 'the top-up asserted a figure no source carries')


if __name__ == '__main__':
    unittest.main()
