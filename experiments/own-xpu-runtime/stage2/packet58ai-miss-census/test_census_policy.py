import json,tempfile,unittest
from pathlib import Path
import coordinator_gate,views,window,launch_env,queue_runner
P=Path(__file__).resolve().parent
class Policy(unittest.TestCase):
    def test_all_views_keep_record_config(self):
        self.assertEqual([v for _,v in views.bracket('p60fusion')],['p60fusion']*5)
    def test_unit_gate_real_proposal_name(self):
        from launch_identity import unit_name
        job=coordinator_gate.proposal_jobs()[0]
        window.user_unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/'+unit_name(job)+'\n')
        with self.assertRaises(ValueError):window.user_unit_gate('0::/system.slice/other.service\n')
    def test_closed_environment(self):
        window.closed_environment(launch_env.environment())
        with self.assertRaises(ValueError):window.closed_environment(dict(launch_env.environment(),ZE_AFFINITY_MASK='0'))
    def test_queues_must_be_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for lane in 'AB':(p/f'queue-{lane}.txt').write_text('# empty\n')
            self.assertTrue(coordinator_gate.check(p)['queues_drained'])
            (p/'queue-B.txt').write_text(json.dumps(dict(name='packet-other'))+'\n')
            with self.assertRaises(ValueError):coordinator_gate.check(p)
    def test_missing_queue_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):coordinator_gate.check(d)
    def test_current_proposal_inflight_and_queued_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);job=coordinator_gate.proposal_jobs()[0]
            (p/'queue-A.txt').write_text(json.dumps(job)+'\n')
            (p/'queue-B.txt').write_text('# empty\n')
            (p/'inflight-A.json').write_text(json.dumps(dict(job=job)))
            self.assertTrue(coordinator_gate.check(p)['passed'])
            self.assertEqual(queue_runner.output_root(),Path(coordinator_gate.identity(job)[2]).parent)
    def test_foreign_jobs_refused_on_either_lane(self):
        for lane in 'AB':
            for inflight in (False,True):
                for change in ('name','output','entry'):
                    with self.subTest(lane=lane,inflight=inflight,change=change),tempfile.TemporaryDirectory() as d:
                        p=Path(d);job=coordinator_gate.proposal_jobs()[0]
                        for q in 'AB':(p/f'queue-{q}.txt').write_text('# empty\n')
                        if change=='name':job['name']+='-foreign'
                        elif change=='output':job['argv'][job['argv'].index('--output')+1]+='-foreign'
                        else:job['argv'][2]='foreign/queue_runner.py'
                        path=p/(f'inflight-{lane}.json' if inflight else f'queue-{lane}.txt')
                        path.write_text(json.dumps(dict(job=job) if inflight else job)+'\n')
                        with self.assertRaises(ValueError):coordinator_gate.check(p)
    def test_empty_queues_with_inflight_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for lane in 'AB':(p/f'queue-{lane}.txt').write_text('# empty\n')
            (p/'inflight-B.json').write_text(json.dumps(dict(job=dict(name='packet-other'))))
            with self.assertRaises(ValueError):coordinator_gate.check(d)
    def test_native_source_no_new_wait_or_arithmetic(self):
        partition=(P/'native/partition.hpp').read_text()
        self.assertNotIn('.wait(',partition);self.assertNotIn('get_profiling_info',partition)
        measure=(P/'native/measure.hpp').read_text()
        self.assertIn('command_execution_status',measure);self.assertNotIn('.wait(',measure)
        self.assertIn('if(!ownrt::submission_capture)',partition)
    def test_watchdog_and_current_cache_admission(self):
        job=next(json.loads(x) for x in (P.parents[1]/'ops/lane-queue/proposed-p58ai-census-A.txt').read_text().splitlines() if x.startswith('{'))
        self.assertGreaterEqual(job['plan']['watchdog_seconds'],4*job['plan']['expected_seconds'])
        self.assertEqual(window.M.CACHE_BYTES,21552729600)
        self.assertEqual(queue_runner.ORDER,('K1a','K1b','WSCREEN'))
if __name__=='__main__':unittest.main()
