"""CPU-only negative tests: no watcher/device child is called."""
import copy
import unittest
from common import HERE, load, plan

harness = load('_packet6_timing', HERE / 'tests/device_timing.py')


def events(n=20, ns=1000):
    return [dict(start_ns=i * ns * 2, end_ns=i * ns * 2 + ns) for i in range(n)]


def native(layer):
    rows = []
    for j in layer['jobs']:
        for variant in ('baseline', 'kopt_sg16', 'kopt_sg32'):
            rows.append(dict(name=j['name'], variant=variant, events=events(ns=2000 if variant == 'baseline' else 1000),
                             route_status=[0] * 10 if j['experts'] == 512 else []))
    return dict(schema='own-runtime.iq3.packet6.timing-native.v1', error='', device='mock', kernels=rows, sequence=[], fused=None,
        teardown=dict(safe_to_exit=True, idle_marker_complete=True, live_bytes=0, in_flight=0, exit_code=0,
            status='complete', error='', backend='mock', sequence=['context-released']))


class Protocol(unittest.TestCase):
    def setUp(self):
        self.layer = plan()['layers'][1]
        self.raw = native(self.layer)

    def test_matched_ratio_and_bytes(self):
        result = harness.summarize(self.raw, self.layer)
        row = result['kernels'][1]
        self.assertEqual(row['baseline_over_candidate'], 2)
        self.assertEqual(row['packed_bytes'], self.layer['jobs'][0]['packed_active_bytes'])
        self.assertEqual(row['effective_GB_s'], row['packed_bytes'] / 1000)

    def test_coverage_refused(self):
        self.raw['kernels'].pop()
        with self.assertRaises(ValueError):
            harness.summarize(self.raw, self.layer)

    def test_variant_order_refused(self):
        self.raw['kernels'][1]['variant'] = 'baseline'
        with self.assertRaises(ValueError):
            harness.summarize(self.raw, self.layer)

    def test_route_failure_refused(self):
        next(r for r in self.raw['kernels'] if r['route_status'])['route_status'][0] = 1
        with self.assertRaises(ValueError):
            harness.summarize(self.raw, self.layer)

    def test_unsafe_teardown_refused(self):
        self.raw['teardown']['in_flight'] = 1
        with self.assertRaises(ValueError):
            harness.summarize(self.raw, self.layer)

    def test_short_event_set_refused(self):
        self.raw['kernels'][0]['events'].pop()
        with self.assertRaises(ValueError):
            harness.summarize(self.raw, self.layer)

    def test_overlap_refused(self):
        self.raw['kernels'][0]['events'][1]['start_ns'] = 0
        with self.assertRaises(ValueError):
            harness.summarize(self.raw, self.layer)

    def test_bool_timestamp_refused(self):
        with self.assertRaises(ValueError):
            harness.spans([dict(start_ns=False, end_ns=100)])

    def test_owner_budget(self):
        p = plan()
        self.assertEqual(p['owner_sessions'], 4)
        self.assertTrue(all(l['event_count_upper_bound'] < 4096 for l in p['layers']))

    def test_fused_and_sequences(self):
        layer = plan()['layers'][0]
        raw = native(layer)
        raw['sequence'] = [dict(variant=v, layer=0, launches_per_layer=len(layer['jobs']),
            iterations=[dict(events=events(len(layer['jobs']))) for _ in range(20)])
            for v in ('baseline', 'kopt_sg16')]
        raw['fused'] = dict(names=['blk.0.' + n + '.weight' for n in
            ('hc_attn_inject', 'ssm_alpha', 'ssm_beta', 'hc_attn_down')],
            variant='kopt_fused_sg16', events=events(), separate_iterations=[events(4) for _ in range(20)])
        result = harness.summarize(raw, layer)
        self.assertEqual(result['fused']['separate_over_fused'], 7)
        raw['fused']['separate_iterations'][0].pop()
        with self.assertRaises(ValueError):
            harness.summarize(raw, layer)

if __name__ == '__main__':
    unittest.main()
