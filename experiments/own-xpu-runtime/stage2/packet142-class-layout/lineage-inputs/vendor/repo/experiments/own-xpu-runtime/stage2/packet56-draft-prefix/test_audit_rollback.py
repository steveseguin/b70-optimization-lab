#!/usr/bin/env python3
"""Bounded CPU-only tests of strict rollback byte accounting and evidence guards."""
import copy,hashlib,json,unittest
from unittest.mock import patch
import audit_rollback as a

class RollbackAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence=a.strict_evidence()
    def test_hand_formula(self):
        rows=[dict(row_bytes=8,pooled=False),dict(row_bytes=2,pooled=True)]
        self.assertEqual(a.payload_bytes(1000,7,rows),942)
        self.assertEqual(a.payload_bytes(1000,8,rows),932)
    def test_bounds(self):
        with self.assertRaises(AssertionError):a.payload_bytes(1,2,[dict(row_bytes=1,pooled=False)])
        with self.assertRaises(AssertionError):a.payload_bytes(100,-1,[])
    def test_real_capacity(self):
        self.assertEqual(self.evidence['capacity_bytes'],319074840)
        self.assertEqual([x['snapshot_device_to_device_bytes'] for x in self.evidence['examples']],[318976536,318961176])
    def test_corrupt_payload_rejected(self):
        original=a.archive_members
        def corrupt(*args):
            result=original(*args);result['rank0/speculative-snapshot.json']['snapshot_payload_bytes']+=1;return result
        with patch.object(a,'archive_members',side_effect=corrupt),self.assertRaises(AssertionError):a.strict_evidence()
    def test_model_scrub_rejected(self):
        original=a.archive_members
        def corrupt(*args):
            result=original(*args);result['rank0/speculative-snapshot.json']['committed_state_scrubbed']=True;return result
        with patch.object(a,'archive_members',side_effect=corrupt),self.assertRaises(AssertionError):a.strict_evidence()
    def test_plan_change_rejected(self):
        original=a.archive_members
        def corrupt(*args):
            result=original(*args);result['rank0/launch-plan.json']['buffers'][0]['bytes']+=1;return result
        with patch.object(a,'archive_members',side_effect=corrupt),self.assertRaises(AssertionError):a.strict_evidence()
    def test_source_change_rejected(self):
        original=a.sha
        with patch.object(a,'sha',side_effect=lambda path:'0'*64 if str(path).endswith('rank.hpp') else original(path)),self.assertRaises(AssertionError):a.strict_evidence()
    def test_inventory_census(self):
        self.assertEqual(len(a.bs),len(a.temporal)+len(a.external)+len(a.overwrite))
        self.assertEqual(sum(x['bytes'] for x in a.banked),29601792)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RollbackAudit))
    receipt=dict(passed=result.wasSuccessful(),tests=result.testsRun,device_executed=False,models_loaded=False,
                 source_sha256={name:a.sha(a.P/name) for name in ['audit_rollback.py','test_audit_rollback.py','strict_snapshot.hpp','rank.hpp']})
    (a.P/'rollback-audit-unit-tests.json').write_text(json.dumps(receipt,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
