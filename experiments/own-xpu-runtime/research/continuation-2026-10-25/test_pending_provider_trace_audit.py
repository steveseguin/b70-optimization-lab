"""Audit actual fragmented-socket fixture traces and adversarial provenance edits."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pending_provider_trace_audit as audit
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'engine/tools'))
import test_pending_ring_live_driver as fixture


class PendingTraceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples=[];original=fixture.pending.drive
        def wrapped(stages,plan,guard,output):
            result=original(stages,plan,guard,output)
            schedule=[json.loads(row) for row in (output/'schedule.jsonl').read_text().splitlines()]
            args=[schedule,plan['prompt_tokens']+result['output_ids'][:-1],plan['request_sha256'],len(stages)]
            cls.samples.append(args);return result
        with patch.object(fixture.pending,'drive',side_effect=wrapped):
            fixture.PendingTests('test_two_slot_then_older_accept_one_slot_actual_truth_two_four_six').test_two_slot_then_older_accept_one_slot_actual_truth_two_four_six()

    def test_two_four_six_real_socket_schedules_replay(self):
        self.assertEqual([r[3] for r in self.samples],[2,4,6])
        for args in self.samples:
            result=audit.audit_controller(*args)
            self.assertEqual([len(r['discarded']) for r in result['aborts']],[2,1])
            self.assertEqual([len(r['pending']) for r in result['providers'] if r['pending']],[2,2,1])
            self.assertTrue(all(r['provider_position']>r['oldest']['provider_position_at_capture'] for r in result['aborts']))

    def test_issued_identity_accept_flag_and_provider_pending_tamper_refused(self):
        for kind,field,value in [('row','parent',999),('accept','original_tentative',True),
                                 ('provider','pending_rows',[999]),('provider','serial',999),
                                 ('target-verified-suffix-abort','provider_serial',0),
                                 ('target-verified-suffix-abort','actual_target_token',999)]:
            args=copy.deepcopy(self.samples[0]);event=next(r for r in args[0] if r['event']==kind)
            event[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):audit.audit_controller(*args)

    def test_missing_and_reordered_commands_refused(self):
        for mode in ('missing','duplicate','before-parent'):
            args=copy.deepcopy(self.samples[0]);events=args[0]
            index=next(i for i,r in enumerate(events) if r['event']=='provider' and r['pending_depth'])
            if mode=='missing':events.pop(index)
            elif mode=='duplicate':events.insert(index,copy.deepcopy(events[index]))
            else:events[index],events[index-1]=events[index-1],events[index]
            with self.subTest(mode=mode),self.assertRaises(ValueError):audit.audit_controller(*args)


if __name__=='__main__':unittest.main()
