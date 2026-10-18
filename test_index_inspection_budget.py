import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import index_status_report as report

class InspectionBudgetTests(unittest.TestCase):
    def test_zero_budget_records_unknown_not_unindexed(self):
        with tempfile.TemporaryDirectory() as td,patch.object(report,'OUT',Path(td)/'out.json'),patch.object(report,'inspect') as inspect:
            result=report.inspect_inventory('not-a-real-token',['https://dailyyield.blogspot.com/'],0)
            inspect.assert_not_called();self.assertEqual(result['deferredInspections'],1)
            self.assertEqual(result['notIndexed'],0);self.assertEqual(result['unknown'],1);self.assertEqual(result['status'],'PARTIAL')
    def test_parallel_results_are_ordered_by_inventory_and_checkpointed(self):
        urls=['https://dailyyield.blogspot.com/'+str(i)+'.html' for i in range(30)]
        def inspect(token,url):return {'url':url,'verdict':'PASS','coverageState':'Submitted and indexed'}
        with tempfile.TemporaryDirectory() as td,patch.object(report,'OUT',Path(td)/'out.json'),patch.object(report,'inspect',side_effect=inspect),patch.object(report.InspectionPacer,'wait'):
            result=report.inspect_inventory('not-a-real-token',urls,5)
            self.assertEqual(result['indexed'],30);self.assertTrue(result['runComplete'])
            self.assertEqual([r['url'] for r in result['rows']],urls)
            self.assertEqual(result['deferredInspections'],0)
    def test_network_failure_is_unknown_error_not_non_indexing(self):
        with tempfile.TemporaryDirectory() as td,patch.object(report,'OUT',Path(td)/'out.json'),patch.object(report,'inspect',side_effect=TimeoutError),patch.object(report.InspectionPacer,'wait'):
            result=report.inspect_inventory('not-a-real-token',['https://dailyyield.blogspot.com/'],5)
            self.assertEqual(result['inspectionErrors'],1);self.assertEqual(result['notIndexed'],0)

if __name__=='__main__':unittest.main()
