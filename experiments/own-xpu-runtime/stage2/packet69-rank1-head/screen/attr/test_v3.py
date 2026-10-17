"""Small CPU fixtures only: orchestration, byte identity, fault and report gates."""
import io
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import sys

import common as C
import conditions as K
import fault_review as F
import screen
import ab
import tp2_worker


class V3Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=C.HERE)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def identity(self, lane='A', timing='token', lineage=C.P56):
        return dict(lineage=str(lineage), binary='/sealed/binary', dispatch='/sealed/dispatch',
                    selection_sha256='a'*64, lane=lane, timing=timing,
                    placement=dict(name='1-split23', draft_rank=1, target_split=23, supported=True))

    def rows(self, scale=1.):
        rows = []
        for index, pid in enumerate(C.D.CHECK.PROMPT_IDS):
            stamps = [10+i*.02/scale for i in range(128)]
            row = C.METRICS.request_metrics(dict(tokens=list(range(128)),
                timing_rows=[dict(completed_monotonic=t) for t in stamps]),60,128,'none',start=9.,end=13.,device=True)
            row.update(tokens=list(range(128)), passed=True, exact_oracle=True, prompt_id=pid, prompt_class=C.METRICS.PROMPT_CLASSES[pid],
                       stats=dict(guesses=70,hits=56,misses=14,no_guess=1),acceptance=.8,
                       hit_miss_cycles={'hit':{'mean_ms':18},'miss':{'mean_ms':33}})
            rows.append(row)
        return rows

    def test_fixed_lane_priority_and_affinity(self):
        for lane in K.LANES:
            with patch.object(os,'getpriority',return_value=0), patch.object(os,'sched_getaffinity',return_value=K.LANES[lane]['cores']):
                K.lane_gate(lane)
            with patch.object(os,'getpriority',return_value=19), patch.object(os,'sched_getaffinity',return_value=K.LANES[lane]['cores']):
                with self.assertRaises(ValueError):K.lane_gate(lane)
        self.assertEqual(K.LANES['B']['cards'], [2,3])
        self.assertEqual(K.LANES['A']['pci'], ['0000:23:00.0','0000:27:00.0'])

    def test_selected_pair_rejects_either_card_unknown_allows_other(self):
        d=self.root/'123/fdinfo';d.mkdir(parents=True)
        for pci in ('0000:43:00.0','0000:47:00.0',''):
            (d/'7').write_text('drm-driver: xe\ndrm-pdev: '+pci+'\n')
            with self.assertRaises(ValueError):K.selected_clients('B',self.root)
        (d/'7').write_text('drm-driver: xe\ndrm-pdev: 0000:23:00.0\n')
        self.assertEqual(len(K.selected_clients('B',self.root)['other']),1)

    def journal(self, messages):
        return '\n'.join(json.dumps(dict(_BOOT_ID='a'*32,__REALTIME_TIMESTAMP=str(1700000000000000+i),MESSAGE=m)) for i,m in enumerate(messages))

    def test_boundary_exact_count_deleted_exclusion_and_wrong_boot(self):
        messages=['ordinary','Fault response','engine reset','coredump has been deleted']
        row=F.inspect(self.journal(messages),'a'*32,'cursor')
        self.assertEqual(row['fault_count'],2)
        self.assertEqual(row['through_us'],1700000000000003)
        for bad in (messages[:2],messages+['Hardware Error']):
            with self.assertRaises(ValueError):F.inspect(self.journal(bad),'a'*32,'cursor')
        with self.assertRaises(ValueError):F.inspect(self.journal(messages),'b'*32,'cursor')
        self.assertFalse(F.S.FAULT.search('coredump has been deleted'))
        self.assertTrue(F.S.FAULT.search('GPU HANG'))

    def test_teardowns_are_spaced_after_complete_drain(self):
        now=[100.]
        def sleep(n):now[0]+=n
        for index in range(4):
            out=self.root/str(index);out.mkdir()
            with K.Teardown(out,root=self.root,now=lambda:now[0],sleep=sleep):
                now[0]+=7
        rows=[C.read(self.root/str(i)/'teardown.json') for i in range(4)]
        self.assertTrue(all(rows[i+1]['started_monotonic']-rows[i]['completed_monotonic']>=60 for i in range(3)))
        self.assertEqual(rows[1]['started_monotonic'],167)

    def test_incomplete_teardown_remains_blocked(self):
        out=self.root/'run';out.mkdir()
        with self.assertRaises(RuntimeError):
            with K.Teardown(out,root=self.root):raise RuntimeError('undrained')
        self.assertFalse(C.read(self.root/'teardown-state.json')['drained'])
        with self.assertRaises(ValueError):
            with K.Teardown(out,root=self.root):pass

    def test_stop_during_finish_drains_under_same_permit(self):
        calls=[]
        class Transport:
            closed=False
            def stop(self, reason):calls.append('stop')
            def close(self, success):
                calls.append(('close',success))
                if success:raise ValueError('cancellation during FINISH')
                self.check();self.closed=True
        t=Transport()
        with patch.object(tp2_worker,'Teardown') as gate:
            with self.assertRaisesRegex(ValueError,'cancellation during FINISH'):
                tp2_worker.drain(t,self.root,True)
            self.assertEqual(gate.call_count,1)
        self.assertTrue(t.closed)
        self.assertEqual(calls,[('close',True),'stop',('close',False)])

    def test_pair_commands_swap_and_pass_timing(self):
        self.assertEqual(ab.orders(),({'A':'x','B':'y'},{'A':'y','B':'x'}))
        ident=dict(self.identity('B','attribution'),seal='/sealed/seal')
        cmd=ab.lane_command(ident,'B',self.root/'B',self.root/'review',self.root)
        self.assertEqual(cmd[2],'4-7,20-23')
        self.assertEqual(cmd[cmd.index('--timing')+1],'attribution')
        self.assertNotIn('nice',cmd)

    def test_report_cancels_lane_bias_preserves_both_orders(self):
        def summary(scale):return C.summary(self.rows(scale),dict(passed=True),'tp2')
        # X is 10% faster; lane B independently runs 20% faster.
        summaries=[{'A':summary(1.1),'B':summary(1.2)}, {'A':summary(1),'B':summary(1.32)}]
        with patch.object(C.D.CHECK,'token_record',return_value=list(range(128))):
            result=ab.paired_report(summaries)
            self.assertAlmostEqual(result['overall']['geometric_paired_difference_percent'],10)
            self.assertEqual(len(result['orders']),2)
            self.assertEqual(len(result['per_class']),6)
            self.assertLess(result['orders'][0]['overall']['difference_percent'],0)
            self.assertFalse(result['submission_eligible'])
            summaries[1]['B']['requests'][-1]['tokens'][-1]=-1
            with self.assertRaises(ValueError):ab.paired_report(summaries)

    def test_bad_timing_is_refused_without_device(self):
        args=types.SimpleNamespace(lineage=C.P56,profile='tp2',binary=None,dispatch=None,seal=None,timing='attribution')
        with self.assertRaisesRegex(ValueError,'timing mode unsupported'):C.sealed(args)


    def test_concurrent_admission_barrier_then_drains_and_summary(self):
        pair=self.root/'pair';events=[]
        summaries={lane:C.summary(self.rows(),dict(passed=True),'tp2') for lane in ('A','B')}
        class Child:
            returncode=None
            def __init__(child,cmd,**kwargs):
                child.lane=cmd[cmd.index('--lane')+1]
                child.out=Path(cmd[cmd.index('--output')+1]);child.out.mkdir()
                events.append(('launch',child.lane,(pair/'GO').exists()))
                C.save(pair/(child.lane+'-ready.json'),dict(ready=True))
            def poll(child):
                if (pair/'GO').exists():
                    events.append(('released',child.lane))
                    (child.out/'run').mkdir(exist_ok=True)
                    start=100 if child.lane=='A' else 165
                    C.save(child.out/'run/teardown.json',dict(drained=True,started_monotonic=start,completed_monotonic=start+5))
                    C.save(child.out/'summary.json',summaries[child.lane])
                    child.returncode=0
                return child.returncode
            def send_signal(child,sig):self.fail('unexpected stop')
        identities={role:dict(self.identity(),seal='/seal') for role in ('x','y')}
        with patch.object(ab,'teardown_admit'),patch.object(ab,'selected_clients'),patch.object(F,'validate'),patch.object(C.M,'meminfo',return_value={'MemAvailable':106*C.M.GIB}),patch.object(C.SUPPORT,'storage'),patch.object(ab.subprocess,'Popen',side_effect=Child),patch.object(ab.time,'sleep'):
            result=ab.run_pair(pair,ab.orders()[0],identities,self.root/'review',{},[])
        self.assertEqual(events[:2],[('launch','A',False),('launch','B',False)])
        self.assertEqual(set(result),{'A','B'})

    def test_unit_requires_no_hard_kill_or_restart(self):
        cgroup='0::/user.slice/user-1000.slice/user@1000.service/app.slice/screen-ab.service'
        valid='Restart=no\nSendSIGKILL=no\nKillMode=process\nExitType=cgroup\nTimeoutStopUSec=infinity\n'
        for text,ok in ((valid,True),(valid.replace('Restart=no','Restart=always'),False),
                        (valid.replace('SendSIGKILL=no','SendSIGKILL=yes'),False)):
            with patch.object(screen.subprocess,'run',return_value=types.SimpleNamespace(stdout=text)):
                if ok:self.assertEqual(screen.unit_conditions(cgroup)['Restart'],'no')
                else:
                    with self.assertRaises(ValueError):screen.unit_conditions(cgroup)


if __name__=='__main__':unittest.main()
