"""The receipt verifier must refuse partial/all-choice gate evidence."""
import copy
import unittest
from unittest.mock import patch
import p49d_cpu_gate as gate

class CaseCoverageTests(unittest.TestCase):
    def cases(self):
        return [dict(zip(('class','candidate','m','row','scenario'), (cls,choice,m,row,scenario)), passed=True)
                for cls, choices in gate.CHOICES.items() for choice in choices
                for m in (1,2) for row in range(m)
                for scenario in ((0,6,7,8) if cls=='small.ffn.q6' else range(9))]

    def test_complete_choices_rows_and_controls(self):
        self.assertEqual(gate.validate_cases(self.cases()), 402)

    def test_missing_candidate_refused(self):
        rows=[r for r in self.cases() if r['candidate']!='rows8-shared']
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            gate.validate_cases(rows)

    def test_missing_serial_second_row_refused(self):
        rows=[r for r in self.cases() if r['row']==0]
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            gate.validate_cases(rows)

    def test_duplicate_cannot_replace_missing_case(self):
        rows=self.cases(); rows[-1]=copy.deepcopy(rows[0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            gate.validate_cases(rows)

    def test_failed_case_refused(self):
        rows=self.cases(); rows[0]['passed']=False
        with self.assertRaisesRegex(ValueError, 'failed'):
            gate.validate_cases(rows)

    def test_unknown_choice_refused(self):
        rows=self.cases(); rows[0]['candidate']='norm-subgroup128'
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            gate.validate_cases(rows)

    def test_immutable_source_change_refused(self):
        receipt={'schema':'packet49d.all-choice-cpu-gate.v1','passed':True,'device_executed':False,'source_hashes':{'old':'hash'}}
        with patch.object(gate,'read_json',return_value=receipt), patch.object(gate,'source_bindings',return_value={'new':'hash'}):
            with self.assertRaisesRegex(ValueError, 'immutable source closure'):
                gate.verify()

if __name__=='__main__': unittest.main()
