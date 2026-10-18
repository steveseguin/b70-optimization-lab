"""CPU mocks only: lane coordination, runner, isolation, accounting and request flow."""
import contextlib
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
import jobs
import run
import screen
import devices
import tp2_worker
import compare
from common import D, HERE, METRICS, P56, SUPPORT, module, read, save
from conditions import LANES
from lane_admission import Reservation


class QuickTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_runner_mock_both_full_orders_and_seven_90_second_gaps(self):
        for lane in ('A', 'B'):
            rows = jobs.jobs(jobs.QUICK / ('jobs-' + lane + '-r3.txt'), lane)
            commands, gaps = [], []
            with contextlib.redirect_stdout(io.StringIO()):
                run.run_jobs(rows, lane, '/review', lambda c: commands.append(c) or 0, gaps.append)
            self.assertEqual(len(commands), 8)
            self.assertEqual(gaps, [90] * 7)
            self.assertEqual([Path(c[c.index('--lineage')+1]).name for c in commands], list(jobs.ORDERS[lane]))
            self.assertTrue(all(c[c.index('--timing')+1] == 'token' for c in commands))
            self.assertTrue(all(c[c.index('--placement')+1] == '1' for c in commands))

    def test_runner_never_retries_or_skips_failure(self):
        rows = jobs.jobs(jobs.QUICK / 'jobs-A-r3.txt', 'A')
        commands=[]
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'no retry'):
            run.run_jobs(rows, 'A', '/review', lambda c: commands.append(c) or 75, lambda n: self.fail('gap'))
        self.assertEqual(len(commands),1)

    def test_revision_outputs_are_fresh_with_original_eight_screen_order(self):
        for lane in ('A', 'B'):
            before = jobs.jobs(jobs.QUICK / f'jobs-{lane}.txt', lane)
            after = jobs.jobs(jobs.QUICK / f'jobs-{lane}-r3.txt', lane)
            self.assertEqual([r['choice'] for r in before], [r['choice'] for r in after])
            self.assertEqual(sum(r['choice'] == 'combined' for r in after), 1)
            self.assertFalse({r['out'] for r in before} & {r['out'] for r in after})

    def test_fixed_order_rejects_missing_combined_reorder_and_duplicate(self):
        original = [s for s in (jobs.QUICK / 'jobs-A-r3.txt').read_text().splitlines()
                    if s and not s.startswith('#')]
        variants = [original[:6] + original[7:],
                    [original[0], original[2], original[1], *original[3:]],
                    [*original[:-1], original[0]]]
        for lines in variants:
            path = self.root / 'jobs.txt'
            path.write_text('\n'.join(lines) + '\n')
            with self.assertRaises(ValueError):
                jobs.jobs(path, 'A')

    def test_runner_refuses_any_existing_output_before_subprocess(self):
        import sys
        path = jobs.QUICK / 'jobs-A-r3.txt'
        row = jobs.jobs(path, 'A')[3]
        (self.root / 'evidence' / row['out']).mkdir(parents=True)
        with patch.object(run, 'HERE', self.root), patch.object(run, 'cpu_gate'), \
             patch.object(run, 'verify'), \
             patch.object(sys, 'argv', ['run.py', '--lane', 'A', '--jobs', str(path), '--plan']), \
             patch.object(run.subprocess, 'run', side_effect=AssertionError('subprocess')):
            with self.assertRaisesRegex(ValueError, 'all outputs must be fresh'):
                run.main()

    def test_lanes_overlap_without_whole_host_hold(self):
        with Reservation('A', window='screen', root=self.root) as a:
            with Reservation('B', window='screen', root=self.root) as b:
                self.assertEqual(a.scope, 'lane-A')
                self.assertEqual(b.scope, 'lane-B')
                self.assertFalse((self.root/'hold-lane-B').exists())
                b.complete(drained=True)
            a.complete(drained=True)
        self.assertFalse(list(self.root.glob('active-*')))

    def test_failure_retains_lane_marker(self):
        with Reservation('B', root=self.root):
            pass
        self.assertTrue((self.root/'active-lane-B.json').exists())
        with self.assertRaisesRegex(ValueError, 'coordinator review'):
            with Reservation('B',root=self.root):
                self.fail('stale marker admitted')

    def test_whole_host_hold_blocks_b_before_screen(self):
        with Reservation('A', window='WS128', root=self.root) as a:
            def stop():
                raise ValueError('bounded mock wait')
            with self.assertRaisesRegex(ValueError,'bounded mock wait'):
                with Reservation('B',root=self.root,check=stop):
                    self.fail('B admitted')
            self.assertTrue((self.root/'hold-lane-B').exists())
            a.complete(drained=True)

    def test_plan_has_no_device_or_journal_or_output(self):
        row = jobs.jobs(jobs.QUICK/'jobs-A-r3.txt','A')[0]
        with patch.object(screen.subprocess,'Popen',side_effect=AssertionError('device')),\
             patch.object(screen.S,'journal',side_effect=AssertionError('journal')),\
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(screen.main(jobs.command(row,'A',plan=True)[3:]),0)
        import json
        plan=json.loads(output.getvalue())
        self.assertEqual(plan['reservation_scope'],'lane-A')
        self.assertGreaterEqual(plan['watchdog_seconds'],4*210)
        self.assertFalse((HERE/'evidence'/row['out']).exists())

    def test_other_lane_allowed_but_selected_foreign_client_refused(self):
        for pid,pci in ((101,LANES['A']['pci'][0]),(102,LANES['A']['pci'][1]),(999,LANES['B']['pci'][0])):
            path=self.root/str(pid)/'fdinfo/3';path.parent.mkdir(parents=True)
            path.write_text('drm-driver: xe\ndrm-pdev: '+pci+'\n')
        with patch.object(SUPPORT,'process_start',return_value=77):
            monitor=devices.DeviceMonitor('A',self.root,proc=self.root)
            monitor.register(101);monitor.register(102);monitor.poll(ready=True)
            (self.root/'999/fdinfo/3').write_text('drm-driver: xe\ndrm-pdev: '+LANES['A']['pci'][0]+'\n')
            with self.assertRaisesRegex(ValueError,'selected pair occupied'):
                monitor.poll(ready=True)

    def test_class_balancing_and_token_mismatch(self):
        rows=[]
        for i,prompt in enumerate(D.CHECK.PROMPT_IDS):
            rate=10+i
            rows.append(dict(prompt_id=prompt,prompt_class=METRICS.PROMPT_CLASSES[prompt],tokens=list(range(128)),
                             token_timestamps=[n/rate for n in range(128)],tok_s_1_100_intervals_after_ttft=rate,
                             cached_tokens=0,passed=True,exact_oracle=True))
        summary=dict(requests=rows,cached_tokens=0,requested_max_new=128,request_count=12,passed=True)
        rate,exact=compare.checked_rate(summary,lambda p:list(range(128)))
        self.assertTrue(exact)
        self.assertAlmostEqual(rate,METRICS.aggregate(rows)['class_balanced_tok_s_1_100_intervals_after_ttft']['median'])
        rows[-1]['tokens'][-1]=-1
        self.assertFalse(compare.checked_rate(summary,lambda p:list(range(128)))[1])
        self.assertEqual(compare.baseline([dict(choice='production',rate=10,exact=True),dict(choice='production',rate=20,exact=True)]),15)

    def test_full_worker_mock_incident_then_twelve_requests_and_drain(self):
        import sys
        sys.path.insert(0,str(P56))
        self.addCleanup(lambda:sys.path.remove(str(P56)))
        import pipeline,suite,storage
        entries=[dict(prompt_id=p) for p in D.CHECK.PROMPT_IDS]
        snapshots={e['prompt_id']:(self.root,[1,2,3]) for e in entries}
        calls=[]
        class Transport:
            def __init__(self,*a,**kw):calls.append('load')
            def close(self,success):calls.append(('close',success))
        def reset(t,path):path.mkdir();calls.append(('reset',path.name))
        def request(t,args,prompt,count):
            calls.append(('request',count))
            return dict(tokens=list(range(count)),passed=True,prompt_tokens=3)
        def monitor(lane,output):
            def poll(**kw):save(output/'device-isolation.json',dict(passed=True))
            return types.SimpleNamespace(poll=poll,register=lambda pid:None)
        identity=dict(lineage=str(P56),binary='/mock',dispatch='/mock',selection_sha256='a'*64,
                      lane='A',timing='token',placement=dict(draft_rank=1,target_split=0))
        old=(pipeline.P,storage.P,storage.B,storage.admit)
        try:
            with patch.object(D,'oracle_inputs',return_value={'prompts':entries}),patch.object(D.CHECK,'token_record',return_value=list(range(128))),patch.object(pipeline,'Transport',Transport),patch.object(suite,'checker_module'),patch.object(suite,'admit_inputs',return_value=snapshots),patch.object(suite,'reset',side_effect=reset),patch.object(suite,'run_request',side_effect=request),patch('placement.verify_identity',return_value=(identity['placement'],module('mock_memory',P56/'memory_gate.py'))),patch.object(tp2_worker,'Teardown'),patch.object(tp2_worker,'masked_environment',return_value={}),patch.object(tp2_worker,'DeviceMonitor',side_effect=monitor):
                self.assertEqual(tp2_worker.run(identity,self.root/'run',3600),0)
        finally:
            pipeline.P,storage.P,storage.B,storage.admit=old
        self.assertEqual([c for c in calls if isinstance(c,tuple) and c[0]=='request'],[('request',64)]+[('request',128)]*12)
        self.assertEqual(calls[-1],('close',True))
        self.assertTrue(read(self.root/'run/report-inputs.json')['passed'])


if __name__=='__main__':
    unittest.main()
