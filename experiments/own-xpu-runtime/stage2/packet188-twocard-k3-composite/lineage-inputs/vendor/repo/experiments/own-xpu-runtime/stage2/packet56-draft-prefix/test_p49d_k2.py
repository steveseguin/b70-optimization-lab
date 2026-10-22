"""Synthetic K2 protocol cases; these numbers are never measurements."""
import json
from pathlib import Path
import tempfile
import unittest
import p49d_k2 as k


class CoverageTests(unittest.TestCase):
    def fixture(self, root):
        rows=[]
        for cls, variants in k.CENSUS.items():
            for candidate in variants:
                for i in range(210):
                    passes=4 if cls=='route' else 1
                    base=100+len(rows)*100
                    events=[dict(event=j+1,start_ns=base+j*20,end_ns=base+10+j*20) for j in range(passes)]
                    rows.append(dict(**{'class':cls}, candidate=candidate, iteration=i,
                        m=1,row=0,byte_exact=True,warmup=i<10,events=events,passes=passes,gpu_ns=10*passes))
        receipt=dict(schema='packet49d.all-choice-fixtures.v1',passed=True,device_executed=True,
            timing=True,card=0,reference_exact=True,checks=len(rows)+48,
            teardown=dict(safe_to_exit=True,exit_code=0,live_bytes=0,in_flight=0),
            coverage={cls+':'+v:210 for cls, vs in k.CENSUS.items() for v in vs})
        (root/'receipt.json').write_text(json.dumps(receipt))
        return rows

    def test_complete_and_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=self.fixture(root)
            selection=dict(choices=dict(route='production',recurrence='rows8-shared',hc='mix-vector4'))
            def write(value):
                (root/'timings.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in value))
            write(rows)
            result=k.measured_coverage(root,selection)
            self.assertEqual(result['measured_choices'],16)
            self.assertEqual(result['selection']['recurrence'],'rows8-shared')
            for bad in (rows[:-1],rows+[rows[0]]):
                write(bad)
                with self.assertRaises(ValueError):k.measured_coverage(root,selection)
            for key,value in (('gpu_ns',999),('byte_exact',False),('m',2),('warmup',False)):
                bad=list(rows);bad[0]=dict(bad[0],**{key:value});write(bad)
                with self.assertRaises(ValueError):k.measured_coverage(root,selection)


if __name__=='__main__':unittest.main()
