"""CPU-only plan, receipt and watchdog tests. No accelerator imports/calls."""
import copy
import json
from pathlib import Path
import signal
import tempfile
import unittest
from unittest.mock import patch
import jsonschema
import device_timing as window
from timing_plan import make_plan, metrics, summarize, event_ms, HERE, OWNER, validate_census


def fake_native(plan):
    kernels = []
    for l in plan['layers']:
        for j in l['jobs']:
            kernels.append(dict(name=j['name'], events=[dict(start_ns=1000+i*2000, end_ns=2000+i*2000) for i in range(20)],
                                route_status=[0]*10 if j['routes'] else []))
    return dict(schema='own-runtime.iq3.packet2.timing-native.v1', device='mock CPU test only', error='', kernels=kernels,
        sequence=dict(layer=0, launches_per_layer=plan['layers'][0]['launches_per_layer'], iterations=[
            dict(events=[dict(start_ns=1000+i*2000, end_ns=2000+i*2000) for i in range(plan['layers'][0]['launches_per_layer'])],
                 host_submit_ms=.1, host_wall_ms=.2) for _ in range(20)]),
        teardown=dict(schema='own-xpu-runtime.teardown.v1', backend='mock CPU test only', status='complete',
            exit_code=0, safe_to_exit=True, idle_marker_complete=True, live_bytes=0, in_flight=0, error='',
            sequence=['quiesce', 'drain', 'idle-marker-complete', 'events-released', 'queue-released', 'context-released']))


class Plan(unittest.TestCase):
    def test_roofline_reconciliation(self):
        p = make_plan()
        self.assertEqual([l['roofline']['packed_active_bytes'] for l in p['layers']],
                         [92186496, 127289216, 106722176, 87867392])
        for l in p['layers']:
            self.assertEqual(l['gemv_active_bytes'] + sum(t['bytes'] for t in l['excluded']), l['roofline']['packed_active_bytes'])
            self.assertEqual(l['launches_per_layer'], len(l['jobs']))
            self.assertEqual(sum(j['packed_active_bytes'] for j in l['jobs'] if j['routes']), l['roofline']['top10_expert_bytes'])
        self.assertLess(p['event_count_upper_bound'], 4096)

    def test_real_shapes_and_bank_sizes(self):
        p = make_plan()
        g = {j['name']: j for l in p['layers'] for j in l['jobs']}
        for n, k, rows, rb in [('blk.0.ffn_gate_exps.weight', 2560, 640, 820),
                              ('blk.2.ffn_gate_exps.weight', 2560, 640, 1100),
                              ('blk.0.ffn_down_exps.weight', 640, 2560, 360)]:
            j = g[n]
            self.assertEqual((j['columns'], j['rows'], j['row_bytes']), (k, rows, rb))
            self.assertEqual(j['weight_bytes'], rb*rows*512)
            self.assertEqual(j['packed_active_bytes'], rb*rows*10)
            self.assertEqual(len(set(j['routes'])), 10)
            self.assertEqual(j['routes'][-1], 511)
        self.assertEqual(g['blk.1.ple_key.weight']['weight_bytes'], 27852800)
        self.assertEqual(g['blk.3.attn_q.weight']['rows'], 12288)
        self.assertEqual(g['blk.0.ffn_gate_inp_shexp.weight']['rows'], 1)
        for j in g.values():
            self.assertLessEqual(j['seed_bytes'], 65536)
            self.assertNotIn('conv1d', j['name'])
            self.assertNotIn('norm', j['name'])

    def test_plan_does_not_open_models_or_run_commands(self):
        original = Path.open
        def restricted(path, *a, **k):
            self.assertFalse(str(path).startswith('/mnt/'))
            return original(path, *a, **k)
        with patch.object(Path, 'open', restricted), patch.object(window.subprocess, 'Popen', side_effect=AssertionError('launch')):
            make_plan()

    def test_metrics_decimal_units(self):
        r = metrics([2.0]*10 + [4.0]*10, 507000000)
        self.assertEqual(r['median_ms'], 3)
        self.assertEqual(r['min_ms'], 2)
        self.assertEqual(r['effective_GB_s'], 169)
        self.assertEqual(r['bandwidth_ratio']['507'], 1/3)
        self.assertEqual(r['latency_over_floor']['507'], 3)

    def test_bad_samples(self):
        for values in ([], [0]*20, [-1]*20, [float('nan')]*20, [float('inf')]*20, [1]*19):
            with self.subTest(values=values), self.assertRaises(ValueError):
                metrics(values, 100)
        with self.assertRaises(ValueError):
            event_ms([dict(start_ns=4, end_ns=3)]*20)
        with self.assertRaises(ValueError):
            event_ms([dict(start_ns=1, end_ns=3)]*20)


class Receipt(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan()
        self.raw = fake_native(self.plan)

    def test_residency_census(self):
        censuses = []
        for layer in self.plan['layers']:
            rows = [dict(label=j['name']+'/weights', bytes=j['weight_bytes'], live=True,
                         memory='device', category='weights') for j in layer['jobs']]
            censuses.append(dict(allocations=rows, totals={'device':sum(r['bytes'] for r in rows),
                                                          'host-pinned':0, 'host-shadow':0}))
        censuses.append(dict(allocations=[], totals={'device':0, 'host-pinned':0, 'host-shadow':0}))
        validate_census(censuses, self.plan)
        bad=copy.deepcopy(censuses);bad[0]['allocations'][0]['memory']='host-pinned'
        with self.assertRaises(ValueError): validate_census(bad, self.plan)
        bad=copy.deepcopy(censuses);bad[0]['allocations'][0]['bytes'] //= 512
        with self.assertRaises(ValueError): validate_census(bad, self.plan)
        bad=copy.deepcopy(censuses);bad[-1]['totals']['device']=1
        with self.assertRaises(ValueError): validate_census(bad, self.plan)

    def test_sequence_gaps(self):
        s = summarize(self.raw, self.plan)['sequence']
        n = self.plan['layers'][0]['launches_per_layer']
        self.assertAlmostEqual(s['median_kernel_sum_ms'], n*.001)
        self.assertAlmostEqual(s['median_queue_gap_ms'], (n-1)*.001)
        self.assertAlmostEqual(s['median_ms'], (2*n-1)*.001)

    def test_incomplete_or_unsafe_native(self):
        for field, value in [('safe_to_exit', False), ('in_flight', 1), ('live_bytes', 1), ('idle_marker_complete', False), ('error', 'fault')]:
            bad = copy.deepcopy(self.raw); bad['teardown'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                summarize(bad, self.plan)
        bad = copy.deepcopy(self.raw); bad['kernels'].pop()
        with self.assertRaises(ValueError): summarize(bad, self.plan)
        bad = copy.deepcopy(self.raw); bad['kernels'][0]['events'].pop()
        with self.assertRaises(ValueError): summarize(bad, self.plan)
        bad = copy.deepcopy(self.raw); next(k for k in bad['kernels'] if k['route_status'])['route_status'][0] = 1
        with self.assertRaises(ValueError): summarize(bad, self.plan)
        bad = copy.deepcopy(self.raw); bad['sequence']['iterations'][0]['events'].pop()
        with self.assertRaises(ValueError): summarize(bad, self.plan)

    def test_schema_success_and_mutations(self):
        schema = json.loads((HERE/'tests/timing.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        record = dict(schema='own-runtime.iq3.packet2.timing.v1', passed=True, device_executed=True,
            card=3, binary_sha256='a'*64, kernel_journal_sha256='b'*64, environment={}, error='',
            prepared_manifest=dict(source_sha256={}, seeds=[], binary_sha256='a'*64, commands=[]), plan=self.plan,
            window=dict(start_utc='test', boot_id='test', pid=123, initial_cursor='a', final_cursor='b', returncode=0,
                        stop_reason=None, elapsed_seconds=1, external_idle_health_still_required=True),
            native=self.raw, summary=summarize(self.raw, self.plan),
            census=[dict(schema='own-xpu-runtime.census.v1', allocations=[], totals={},
                         unmeasured_driver_shadow_bytes=None, unmeasured_library_pool_bytes=None)])
        jsonschema.validate(record, schema)
        failed=copy.deepcopy(record);failed['passed']=False;failed['native']['device']='';failed['native']['kernels']=[];failed['native']['sequence']=None
        failed['error']='native failure';failed.pop('summary');jsonschema.validate(failed, schema)
        jsonschema.validate(self.raw['teardown'], json.loads((OWNER/'tests/teardown.schema.json').read_text()))
        for field in ('binary_sha256', 'plan', 'native', 'census', 'summary', 'kernel_journal_sha256'):
            bad=copy.deepcopy(record);del bad[field]
            with self.subTest(field=field), self.assertRaises(jsonschema.ValidationError): jsonschema.validate(bad, schema)
        for target, field, value in [('window', 'stop_reason', 'GPU fault'), ('window', 'returncode', 1), ('teardown', 'live_bytes', 1)]:
            bad=copy.deepcopy(record); (bad['native']['teardown'] if target=='teardown' else bad[target])[field]=value
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(bad, schema)


class Watcher(unittest.TestCase):
    def simulate(self, case):
        build=HERE/'build';build.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=build, prefix='timing-watch-test-') as td:
            path=Path(td); calls=[]
            class Child:
                pid=123
                returncode=None
                def poll(self):
                    if case=='clean': self.returncode=0
                    return self.returncode
                def send_signal(self, sig):
                    calls.append(sig);self.returncode=1
            def fake_journal(cursor=None):
                if case=='unavailable': raise RuntimeError('journal unavailable')
                if cursor and case=='fault': return 'xe Fault response\n', 'b'
                if cursor and case=='journal_error': raise RuntimeError('lost journal')
                return 'clean\n', 'a'
            with patch.object(window, 'journal', side_effect=fake_journal), patch.object(window, 'LATCH', path/'latch.json'), \
                 patch.object(window.subprocess, 'Popen', return_value=Child()) as launch, \
                 patch.object(window.time, 'sleep'), patch.object(window.time, 'monotonic', side_effect=range(100)):
                if case=='unavailable':
                    with self.assertRaises(RuntimeError): window.watch(['fake'], path/'out', 1)
                    launch.assert_not_called();return
                r=window.watch(['fake'], path/'out', 1 if case=='timeout' else 120)
                self.assertEqual(launch.call_count, 1)
                self.assertEqual(calls, [] if case=='clean' else [signal.SIGTERM])
                self.assertEqual((path/'latch.json').exists(), case!='clean')
                self.assertEqual(r['stop_reason'] is None, case=='clean')
    def test_clean(self): self.simulate('clean')
    def test_fault_latches_single_cooperative_stop(self): self.simulate('fault')
    def test_timeout(self): self.simulate('timeout')
    def test_journal_failure(self): self.simulate('journal_error')
    def test_preflight_failure_never_launches(self): self.simulate('unavailable')


if __name__ == '__main__':
    unittest.main()
