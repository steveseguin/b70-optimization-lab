import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import suite_driver as D
import views as V
import analyze
from test_bracket import SummaryTests
P=Path(__file__).resolve().parent
class ResidentReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):SummaryTests.setUpClass()
    def fixture(self,out,view='smoke'):
        f=SummaryTests();f.fixture(out,view)
        lookup=json.loads((P.parent/'lineage/synthetic-lookup-receipt.json').read_text())
        receipt=D.read(out/'run/receipt.json');receipt['lookup_residency']=lookup;D.save(out/'run/receipt.json',receipt)
        for label,_,_ in V.bracket(view):D.save(out/'run'/label/'lookup-backing.json',dict(resident=True,copies=lookup))
        if view=='resident':
            for label,_,_ in V.bracket(view):
                for entry in f.manifest['prompts']:
                    request=out/'run'/label/entry['prompt_id']
                    D.save(request/'owner-cpu.json',dict(cpu_seconds=1.0,wall_seconds=2.0,one_core_percent=50.0))
                    for leaf in ('timings.jsonl','prefill-timings.jsonl'):
                        (request/leaf).write_text('{"wall_ms":1.0}\n')
        D.save(out/'receipt.json',dict(window='WSCREEN',gpu_count=1))
        return f
    def test_new_lookup_gate_refuses_missing_changed_and_wrong_backing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);self.fixture(out,'resident');self.assertTrue(D.verify_lookup_views(out,'resident'))
            file=out/'run/B1/lookup-backing.json';original=D.read(file)
            for value in (dict(original,resident=False),dict(original,copies=dict(original['copies'],bytes=1))):
                D.save(file,value)
                with self.assertRaises(ValueError):D.verify_lookup_views(out,'resident')
            file.unlink()
            with self.assertRaises(FileNotFoundError):D.verify_lookup_views(out,'resident')
    def test_smoke_analyzes_own_output_before_data_and_as_data_arrives(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);f=self.fixture(out)
            first=analyze.partial(out,f.manifest)
            self.assertTrue(first['passed']);self.assertEqual(first['timing_rows_checked'],0)
            request=out/'run/S0'/f.manifest['prompts'][0]['prompt_id']
            timing=request/'timings.jsonl'
            row=dict(prepare_major_faults=0,prepare_minor_faults=0,process_major_faults=0,prepare_ms=.5,resident_lookups=True)
            timing.write_text(json.dumps(row)+'\n{"partial":')
            self.assertEqual(analyze.partial(out,f.manifest)['timing_rows_checked'],1)
            (request/'lookup-request-complete.json').write_text('{}')
            self.assertEqual(analyze.partial(out,f.manifest)['complete_exact_requests'],1)
            timing.write_text(json.dumps(dict(row,resident_lookups=False))+'\n')
            with self.assertRaises(ValueError):analyze.partial(out,f.manifest)
if __name__=='__main__':unittest.main()
