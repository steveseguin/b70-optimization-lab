import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import memory_plan as M
import window as W

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE.parent/'packet58g-onecard/evidence/58b-kd'

class SensorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.budget = M.plan()
        cls.receipt = json.loads((EVIDENCE/'window.json').read_text())
        cls.baseline = cls.receipt['memory_admission']['baseline_gpuactive_bytes']

    def account(self, growth=0, pinned=0, anon=0, available=None):
        return W.account_memory({'anonymous_bytes': anon, 'root_seen': True},
            {'MemAvailable': M.HOST_RESERVE if available is None else available,
             'GPUActive': self.baseline+growth}, self.baseline, pinned, self.budget)

    def test_actual_retained_samples(self):
        # No timestamps bind these snapshots to progress. Use ZERO credit,
        # never pretend the terminal progress count was present at each sample.
        samples = [json.loads(line) for line in (EVIDENCE/'run/run/host-memory.jsonl').read_text().splitlines()]
        last = self.receipt['memory_last_sample']
        for host in samples+[last['host']]:
            if max(0,host['GPUActive']-self.baseline)>4*M.GIB:
                # Historical unbound progress cannot justify pin credit under 58u.
                with self.assertRaisesRegex(ValueError,'shadow exceeds'):
                    W.account_memory({'anonymous_bytes':last['anonymous_bytes']},host,self.baseline,0,self.budget)
            else:
                result=W.account_memory({'anonymous_bytes':last['anonymous_bytes']},host,self.baseline,0,self.budget)
                self.assertLessEqual(result['gpuactive_shadow_bytes'],4*M.GIB)
        self.assertEqual(len(samples), 2)

    def test_actual_pinned_progress(self):
        tracker = W.PinnedExpertProgress(EVIDENCE/'run/run/progress.jsonl', self.budget)
        self.assertEqual(tracker.read(), 26424115200)
        self.assertEqual(len(tracker.seen), 78)
        self.assertEqual(tracker.read(), 26424115200)  # Repeated polls cannot double credit.
        self.assertLess(tracker.total, self.budget['device_owned_bound_bytes'])

    def test_crossing_reconstruction_explicitly_synthetic(self):
        # Failed GPUActive sample was not retained by 58b. This is the
        # hypothesized crossing, NOT a lab memory measurement.
        pinned = 26424115200
        self.assertLess(pinned, self.budget['device_owned_bound_bytes'])
        self.assertEqual(self.account(growth=pinned, pinned=pinned)['gpuactive_shadow_bytes'], 0)

    def test_all_pins_and_max_true_shadow_pass(self):
        pinned = self.budget['census']['pinned_expert_bytes']
        shadow = self.budget['host_categories']['gpuactive_shadow_bound']
        self.assertEqual(self.account(growth=pinned+shadow, pinned=pinned)['gpuactive_shadow_bytes'], shadow)

    def test_true_shadow_over_bound_stops_at_each_load_stage(self):
        shadow = self.budget['host_categories']['gpuactive_shadow_bound']
        for pinned in (0, 26424115200, self.budget['census']['pinned_expert_bytes']):
            with self.assertRaisesRegex(ValueError, 'shadow exceeds'):
                self.account(growth=pinned+shadow+1, pinned=pinned)

    def test_combined_total_stops_even_with_legal_shadow_and_old_anon_limit(self):
        pinned = self.budget['census']['pinned_expert_bytes']
        host = self.budget['host_categories']
        anon_bound = host['resident_lookup_bytes']+host['measured_process_overhead_allowance']+host['capacity_backing_metadata_staging']+host['new_observed_peak_increment']
        self.account(growth=pinned+host['gpuactive_shadow_bound'], pinned=pinned, anon=anon_bound)
        with self.assertRaisesRegex(ValueError, 'combined host memory'):
            self.account(growth=pinned+host['gpuactive_shadow_bound'], pinned=pinned, anon=anon_bound+1)

    def test_host_floor_and_missing_sensor_still_stop(self):
        with self.assertRaisesRegex(ValueError, '8 GiB'):
            self.account(available=M.HOST_RESERVE-1)
        with self.assertRaisesRegex(ValueError, 'GPUActive sensor missing'):
            W.account_memory({'anonymous_bytes':0},{'MemAvailable':M.HOST_RESERVE},0,0,self.budget)
        self.assertEqual(self.budget['host_required_available_bytes'],100487123456)
        self.assertEqual(self.budget['host_reserve_bytes'],8589934592)
        with self.assertRaises(ValueError):M.admit({'MemAvailable':98989727743},self.budget)

    def test_credit_cannot_be_declared_before_progress(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'progress.jsonl';t=W.PinnedExpertProgress(p,self.budget)
            self.assertEqual(t.read(),0)
            name=next(iter(t.expected));row=json.dumps(dict(phase='pinned-expert',name=name,bytes=t.expected[name]))
            p.write_text(row)
            self.assertEqual(t.read(),0)
            with p.open('a') as f:f.write('\n')
            self.assertEqual(t.read(),t.expected[name])
            with p.open('a') as f:f.write(row+'\n')
            with self.assertRaisesRegex(ValueError,'duplicate'):t.read()

    def test_bad_pin_rows_fail_closed(self):
        for row in (dict(phase='pinned-expert',name='bogus',bytes=1),
                    dict(phase='pinned-expert',name='blk.0.ffn_gate_exps.weight',bytes=1)):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'p';p.write_text(json.dumps(row)+'\n')
                with self.assertRaises(ValueError):W.PinnedExpertProgress(p,self.budget).read()

    def test_disappearance_and_truncation_fail_closed(self):
        for truncate in (True,False):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'p';p.write_text('{"phase":"upload"}\n')
                t=W.PinnedExpertProgress(p,self.budget);t.read()
                if truncate:p.write_text('')
                else:p.unlink()
                with self.assertRaises(ValueError):t.read()

    def test_k1_does_not_get_model_pin_credit(self):
        with self.assertRaisesRegex(ValueError,'shadow exceeds'):
            W.account_memory({'anonymous_bytes':0},{'MemAvailable':M.HOST_RESERVE,'GPUActive':4*M.GIB+1},0,0,self.budget,False)

    def test_live_wiring_and_failed_sample_retention(self):
        class Tracker:
            def read(self):return 26424115200
        log=io.StringIO();shadow=self.budget['device_owned_bound_bytes']
        with patch.object(W.SUPPORT,'process_tree_anon',return_value=dict(root_seen=True,anonymous_bytes=0)), \
             patch.object(W.M,'meminfo',return_value={'MemAvailable':M.HOST_RESERVE,'GPUActive':26424115200+shadow+1}):
            with self.assertRaisesRegex(ValueError,'shadow exceeds'):
                W.live_memory_sensor(42,budget=self.budget,pinned_progress=Tracker(),sample_log=log)
        sample=json.loads(log.getvalue())
        self.assertEqual(sample['pinned_expert_bytes'],26424115200)
        self.assertEqual(sample['gpuactive_shadow_bytes'],shadow+1)
        self.assertIn('sensor_error',sample)

    def test_debug_keys_remain_forbidden(self):
        self.assertNotIn('EnableDeferBacking', self.receipt['environment'])
        self.assertNotIn('NEOReadDebugKeys', self.receipt['environment'])
        for key in ('EnableDeferBacking','NEOReadDebugKeys'):
            with self.assertRaises(ValueError):W.closed_environment({'LD_LIBRARY_PATH':'/lib',key:'0'})

if __name__=='__main__':unittest.main()
