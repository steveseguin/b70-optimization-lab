"""V6 accepts observed rolling coverage without relaxing frozen v5 guards."""
import copy
import json
import unittest
from pathlib import Path

import test_compare_pending_provider_state as fixture
COMPARE,digest=fixture.COMPARE,fixture.digest
import compare_rolling_provider_survival as rolling
import compare_provider_survival as scripted


class RollingComparisonTests(unittest.TestCase):
    def setUp(self):
        fixture.PendingComparisonTests.setUp(self)
        self.spec.update(schema='ownrt.pipeline-state-set.v6', controller_mode='rolling-ring-live-depth2-qualification',
                         actual_proposals_only=True, required_provider_pending_depths=[])
        self.path.write_text(json.dumps(self.spec))

    def write_records(self, records):
        fixture.PendingComparisonTests.write_records(self, records)

    def test_actual_coverage_matches_all_target_state(self):
        self.assertTrue(COMPARE.compare(COMPARE.load_set(self.gold), COMPARE.load_set(self.path))['passed'])

    def test_no_advance_is_exact_survival_not_fabricated_coverage(self):
        records=copy.deepcopy(self.records)
        for record in records:
            p=json.loads(record['before_payload'])
            for capture in record['provider_at_capture']:
                capture['position']=capture['serial']=p['position']
            record['provider_advanced_since_snapshot']=False
        self.att['provider_survival_advanced_records']=0
        self.write_records(records)
        self.assertTrue(COMPARE.load_set(self.path)['canonical'])
        self.spec['schema']='ownrt.pipeline-state-set.v5'
        self.spec['required_provider_pending_depths']=[1,2]
        self.path.write_text(json.dumps(self.spec))
        with self.assertRaisesRegex(ValueError,'accounting|advance'):
            COMPARE.load_set(self.path)

    def test_zero_aborts_retains_empty_receipt_and_explicit_zero_coverage(self):
        for key in ('tentative_rows','accepted_tentative_rows','abort_count','discarded_rows',
                    'snapshot_captures','snapshot_releases','byteverified_restore_count','saved_bytes'):
            self.att[key]=0
        self.att.update(rows=7,max_pending=1,trace_records=14,provider_pending_borrows={'1':0,'2':0},
                        provider_quiescent_borrows=6,provider_borrows_while_target_pending=0)
        for key in list(self.att):
            if key.startswith('provider_survival_') and type(self.att[key]) is int:
                self.att[key]=0
        self.write_records([])
        self.assertTrue(COMPARE.load_set(self.path)['canonical'])
        self.rp.write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'SHA'):
            COMPARE.load_set(self.path)

    def test_downstream_target_abort_has_no_provider_inventory(self):
        stage=self.spec['stages'][1];att=json.loads((self.path.parent/stage['quiescence']).read_text())
        att.update(tentative_rows=2,abort_count=1)
        metadata=json.loads((self.path.parent/stage['metadata']).read_text())
        metadata['final']=False
        self.assertEqual(rolling.validate_survival(self.path,stage,None,self.spec,{},metadata,att),[])
        with self.assertRaisesRegex(ValueError,'only first-stage'):
            scripted.validate_survival(self.path,stage,None,self.spec,{},metadata,att)

    def test_lied_advancement_or_missing_explicit_capability_refused(self):
        records=copy.deepcopy(self.records);records[0]['provider_advanced_since_snapshot']=False
        self.write_records(records)
        with self.assertRaisesRegex(ValueError,'advancement'):
            COMPARE.load_set(self.path)
        self.write_records(self.records)
        for key in ('actual_proposals_only','require_provider_survival_checks'):
            spec=dict(self.spec);spec[key]=False;self.path.write_text(json.dumps(spec))
            with self.subTest(key=key),self.assertRaises(ValueError):
                COMPARE.load_set(self.path)


if __name__=='__main__':unittest.main()
