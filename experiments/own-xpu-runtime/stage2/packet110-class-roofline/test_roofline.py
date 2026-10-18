"""CPU-only validation of recorded-event accounting and the new byte identity."""
import copy
import gzip
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from byte_model import account
from roofline import P, validate, rank, ingest

class AccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [json.loads(x) for x in gzip.decompress((P/'evidence/timing-qsa-B-1.jsonl.gz').read_bytes()).splitlines()]
    def test_complete_recorded_calls(self):
        data=validate(self.rows,3)
        self.assertEqual(len(data),50)
        self.assertEqual({len(x) for x in data.values()},{40})
    def test_missing_iteration_refused(self):
        with self.assertRaises(AssertionError): validate(self.rows[2:],3)
    def test_duplicate_iteration_refused(self):
        x=copy.deepcopy(self.rows);[r for r in x if r['mode']=='current'][1]['iteration']=0
        with self.assertRaises(AssertionError):validate(x,3)
    def test_warmup_leak_refused(self):
        x=copy.deepcopy(self.rows);x[0]['warmup']=False
        with self.assertRaises(AssertionError):validate(x,3)
    def test_wrong_context_refused(self):
        x=copy.deepcopy(self.rows);x[0]['position']=128
        with self.assertRaises(AssertionError):validate(x,3)
    def test_class_aggregate_mismatch_refused(self):
        x=copy.deepcopy(self.rows);x[0]['classes_ns']['attention']+=1
        with self.assertRaises(AssertionError):validate(x,3)
    def test_total_mismatch_refused(self):
        x=copy.deepcopy(self.rows);x[0]['gpu_ns']+=1
        with self.assertRaises(AssertionError):validate(x,3)
    def test_duplicate_event_refused(self):
        x=copy.deepcopy(self.rows);x[0]['events'][1]['id']=x[0]['events'][0]['id']
        with self.assertRaises(AssertionError):validate(x,3)
    def test_other_layer_refused(self):
        with self.assertRaises(AssertionError):validate(self.rows,4)
    def test_gdn_rejects_specialised_rows(self):
        with self.assertRaisesRegex(AssertionError,'specialised arm forbidden'):
            validate(self.rows,4)
    def test_archived_qsa_without_original_raw_tree(self):
        with tempfile.TemporaryDirectory(dir=P/'build',prefix='offline-') as tmp:
            root=Path(tmp)/'packet';root.mkdir()
            for name in ('dispatch-speed6.json','selection.json'):
                shutil.copyfile(P/name,root/name)
            data,pin=ingest(root/'evidence/micro-B-1','qsa-B-1',3)
            self.assertEqual(len(data),50)
            self.assertEqual(pin['sha256'],'627e99fd5d73e6aaa2738801ac495b881e12951ff0ce38937cacaefb91fed143')
    def test_expanded_q6_not_gguf_or_stride(self):
        r=account(3,'qsa.qgate',127)
        self.assertEqual(r['runtime_weight_read_bytes'],12288*3200)
        self.assertNotEqual(r['runtime_weight_read_bytes'],r['gguf_weight_bytes'])
    def test_halfcache_stride_count(self):
        self.assertEqual(account(3,'expsgate',127)['runtime_weight_read_bytes'],2*10*640*840)
    def test_gdn_tuple_and_state(self):
        self.assertEqual(account(4,'small.gdn.ab',127)['read_bytes'],988160)
        self.assertEqual(account(4,'gdn.recurrence',4095)['write_bytes'],1585152)
    def test_context_and_missing_class(self):
        self.assertGreater(account(3,'qsa.attention',4095)['read_bytes'],account(3,'qsa.attention',127)['read_bytes'])
        with self.assertRaises(ValueError):account(4,'unknown-class',127)
    def test_pending_ranking_does_not_fill_gdn(self):
        out='\n'.join(rank([],False))
        self.assertIn('pending',out)

if __name__=='__main__':
    from build_engine import limits
    limits()
    unittest.main()
