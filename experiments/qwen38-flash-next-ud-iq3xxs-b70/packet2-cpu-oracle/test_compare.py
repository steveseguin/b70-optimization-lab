"""Reporting regression tests; mocked metadata, no model reads or tensor math."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import compare as C

class Store:
    meta = {}
    def close(self): pass

class Tokenizer:
    def __init__(self, meta): pass
    def encode(self, text): return list(map(ord,text))
    def decode(self, ids): return ''.join(map(chr,ids))

class Comparison(unittest.TestCase):
    def test_empty_prefill_and_immediate_baseline_eos(self):
        with tempfile.TemporaryDirectory(prefix='iq3-comparison-') as tmp:
            root=Path(tmp); run=root/'run'; baseline=root/'baseline'
            run.mkdir(); baseline.mkdir()
            (run/'receipt.json').write_text('{}')
            records=[]
            for name,tokens,output in [('partial',[], 'answer\n\n'),('eos', [35], ' [end of text]\n\n')]:
                d=run/name; d.mkdir()
                (d/'result.json').write_text(json.dumps(dict(id=name,tokens=tokens,status='wall-limit-or-stop' if not tokens else 'token-cap')))
                (baseline/f'repeat1-{name}.stdout').write_text(output)
                records.append(dict(id=name,repeat=1,returncode=0,failed=False))
            (baseline/'runs.json').write_text(json.dumps(records))
            with patch.object(C,'Store',Store),patch.object(C,'Tokenizer',Tokenizer):
                rows={r['id']:r for r in C.compare(run,baseline)}
            saved=json.loads((run/'baseline-comparison.json').read_text())
            self.assertEqual(rows['partial']['status'],'oracle-prefill-incomplete')
            self.assertNotIn('text_prefix_agrees',rows['partial'])
            self.assertEqual(saved['missing_oracle_ids'],['partial'])
            self.assertFalse(rows['eos']['completion_prefix_agrees'])
            self.assertEqual(rows['eos']['first_termination_divergence']['index'],0)
            self.assertEqual(rows['eos']['first_termination_divergence']['oracle_text'],'#')
    def test_text_prefix_and_real_mismatch(self):
        self.assertIsNone(C.text_comparison('abc','abcd')['first_text_divergence'])
        self.assertEqual(C.text_comparison('abç','abé')['agreement_characters'],2)
        self.assertEqual(C.text_comparison('abc','abd')['first_text_divergence']['index'],2)

if __name__=='__main__': unittest.main(verbosity=2)
