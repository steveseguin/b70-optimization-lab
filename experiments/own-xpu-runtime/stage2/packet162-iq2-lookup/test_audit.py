import copy
import json
import unittest
from analyze import P, limits
from audit import summarize


class Gates(unittest.TestCase):
    def setUp(self):
        self.proof=json.loads((P/'evidence/cpu-proof.json').read_text())

    def test_real_evidence_refuses(self):
        r=summarize(self.proof)
        self.assertFalse(r['cpu_strict_exact'])
        self.assertFalse(r['build_brief_gate_passed'])
        self.assertTrue(all(c['finite_exact'] and c['native_output_and_status_exact'] for c in r['compilers']))

    def test_fast_cpu_is_never_device_evidence(self):
        for run in self.proof['results']:
            for row in run['results']:
                if 'columns' in row:
                    row['logic_cpu_ratio_diagnostic_only']=0.01
                    row['enum_cpu_ratio_diagnostic_only']=0.01
        self.assertFalse(summarize(self.proof)['build_brief_gate_passed'])

    def test_missing_adversarial_fixture_refuses(self):
        self.proof['results'][0]['results']=[r for r in self.proof['results'][0]['results'] if r.get('fixture')!=2]
        with self.assertRaises(AssertionError):summarize(self.proof)

    def test_wrong_shape_refuses(self):
        next(r for r in self.proof['results'][0]['results'] if 'columns' in r)['columns']=128
        with self.assertRaises(AssertionError):summarize(self.proof)

    def test_missing_compiler_refuses(self):
        self.proof['results'].pop()
        with self.assertRaises(AssertionError):summarize(self.proof)

    def test_truthy_string_does_not_pass(self):
        for run in self.proof['results']:
            for row in run['results']:
                if 'columns' in row:
                    for k in ('logic_chain_bytes_equal','logic_bf16_bytes_equal','enum_chain_bytes_equal','enum_bf16_bytes_equal'):
                        row[k]='true'
        self.assertFalse(summarize(self.proof)['cpu_strict_exact'])


if __name__=='__main__':
    limits()
    unittest.main()
