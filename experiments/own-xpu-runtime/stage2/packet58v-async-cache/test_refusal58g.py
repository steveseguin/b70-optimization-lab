"""CPU-only drain and CPU-placement regressions, all state under TemporaryDirectory."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock
import onecard_admission as A
import queue_runner as Q
import test_admission58e as F


def proof():
    return dict(passed=False, safe_to_exit=True, compute_started=False,
                device_executed=True, owner_cards=1,
                teardown=[dict(status='complete', safe_to_exit=True,
                    idle_marker_complete=True, error='', exit_code=0, live_bytes=0, in_flight=0)])

class RefusalTests(unittest.TestCase):
    def run_case(self, change=lambda x: None, reasons=(), live=False, seen=True):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); proc=root/'proc'; proc.mkdir(); drain=root/'drain'; drain.mkdir()
            with A.Admission('KD',root/'out',lambda:None,root=root/'lanes',drain_root=drain,proc=proc) as admission:
                admission.before_launch()
                if seen or live:
                    owner=F.AdmissionTests().proc_owner(proc,42,'0000:23:00.0')
                    admission.observe({'processes':[{'pid':42}]})
                    if not live:shutil.rmtree(owner)
                child=Mock();child.poll.return_value=1;child.returncode=1
                row=proof();change(row)
                bad=bool(reasons or live or row!=proof())
                if bad:
                    with self.assertRaises(ValueError):admission.refusal_drained(child,row,list(reasons))
                else:
                    admission.refusal_drained(child,row,[])
                    self.assertFalse(admission.record['passed'])
                self.assertEqual(json.loads((drain/'teardown-state.json').read_text())['drained'],not bad)
                self.assertEqual((root/'lanes/active-lane-A.json').exists(),bad)
    def test_clean_precompute_refusal_releases(self):self.run_case()
    def test_fast_refusal_without_poll_owner_releases(self):self.run_case(seen=False)
    def test_live_owner_retained(self):self.run_case(live=True)
    def test_fault_retained(self):self.run_case(reasons=['postflight GPU fault'])
    def test_unknown_journal_retained(self):self.run_case(reasons=['journal unavailable'])
    def test_compute_started_retained(self):self.run_case(lambda r:r.update(compute_started=True))
    def test_missing_compute_proof_retained(self):self.run_case(lambda r:r.pop('compute_started'))
    def test_inflight_retained(self):self.run_case(lambda r:r['teardown'][0].update(in_flight=1))
    def test_live_allocations_retained(self):self.run_case(lambda r:r['teardown'][0].update(live_bytes=16))
    def test_missing_idle_retained(self):self.run_case(lambda r:r['teardown'][0].update(idle_marker_complete=False))
    def test_foreign_client_retained(self):
        from unittest.mock import patch
        with patch.object(A.D,'admit_clients',side_effect=[{}, {}, {}, ValueError('foreign owner')]):
            with self.assertRaisesRegex(ValueError,'foreign owner'):self.run_case(seen=False)

if __name__=='__main__':unittest.main()
