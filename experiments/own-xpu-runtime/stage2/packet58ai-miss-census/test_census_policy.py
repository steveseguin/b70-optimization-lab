import json,tempfile,unittest
from pathlib import Path
import coordinator_gate,views,window,launch_env,queue_runner
P=Path(__file__).resolve().parent
class Policy(unittest.TestCase):
    def test_all_views_keep_record_config(self):
        self.assertEqual([v for _,v in views.bracket('p60fusion')],['p60fusion']*5)
    def test_unit_gate_real_proposal_name(self):
        window.user_unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/screen-packet58ai-census-A.service\n')
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
