"""CPU-only negative tests: no watcher/device child is called."""
import copy
import unittest
from common import HERE, load, plan, VARIANTS, SMALL, EXPERTS, ceiling_summary

harness = load('_packet7_timing', HERE / 'tests/device_timing.py')


def events(n=20, ns=1000):
    return [dict(start_ns=i * ns * 2, end_ns=i * ns * 2 + ns) for i in range(n)]


def native(layer):
    rows = []
    for j in layer['jobs']:
        for variant in VARIANTS:
            rows.append(dict(name=j['name'], variant=variant, events=events(ns=2000 if variant == 'kopt_sg32' else 1000), pass_events=[[dict(start_ns=e['start_ns'],end_ns=e['start_ns']+400),dict(start_ns=e['start_ns']+500,end_ns=e['end_ns'])] if variant.startswith('splitk') else [e] for e in events(ns=2000 if variant == 'kopt_sg32' else 1000)],
                             route_status=[0] * 10 if j['experts'] == 512 else []))
    return dict(schema='own-runtime.iq3.packet7.timing-native.v1', error='', device='mock', phase='kernels', kernels=rows, sequence=[], fused=[],
        teardown=dict(safe_to_exit=True, idle_marker_complete=True, live_bytes=0, in_flight=0, exit_code=0,
            status='complete', error='', backend='mock', sequence=['context-released']))


class Protocol(unittest.TestCase):
    def setUp(self):
        self.layer = plan()['layers'][1]
        self.raw = native(self.layer)

    def test_matched_ratio_and_bytes(self):
        result = harness.summarize(self.raw, self.layer)
        row = result['kernels'][1]
        self.assertEqual(row['round1_over_candidate'], 2)
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
        self.assertEqual(p['owner_sessions'], 6)
        self.assertTrue(all(l['event_count_upper_bound'] < 4096 for l in p['layers']))

    def test_fused_and_sequences(self):
        layer = plan()['layers'][0]
        raw = native(layer);raw.update(phase='groups',kernels=[],fused=[])
        raw['sequence'] = [dict(variant=v, layer=0, launches_per_layer=len(layer['jobs']),
            iterations=[dict(events=events(len(layer['jobs']))) for _ in range(20)]) for v in ('kopt_sg32','rows2_vec32_v1')]
        for kind, names in (('small',SMALL),('routed_experts',EXPERTS)):
            for v in ('rows2_vec32_v1','rows2_vec64_v1'):
                raw['fused'].append(dict(names=['blk.0.'+n+'.weight' for n in names],kind=kind,variant=v,events=events(),separate_iterations=[events(len(names)) for _ in range(20)]))
        result=harness.summarize(raw,layer)
        self.assertEqual(result['fused'][0]['separate_over_fused'],11)
        raw['fused'][0]['separate_iterations'][0].pop()
        with self.assertRaises(ValueError):harness.summarize(raw,layer)

    def test_split_pass_inclusive(self):
        self.raw['kernels'][1]['events'][0]['start_ns']=500
        with self.assertRaises(ValueError):harness.summarize(self.raw,self.layer)

    def test_split_missing_pass(self):
        self.raw['kernels'][1]['pass_events'][0].pop()
        with self.assertRaises(ValueError):harness.summarize(self.raw,self.layer)

    def ceiling(self):
        raw=native(self.layer)
        raw.update(schema='own-runtime.iq3.packet7.ceiling.v1',checks=12,
            device_properties={k:1 for k in ('max_compute_units','max_work_group_size','local_mem_bytes','global_mem_cache_line_bytes','threads_per_eu','eus_per_subslice','subslices_per_slice','slices')},
            results=[dict(bytes=n,salt=s,variant=v,exact=True,events=events()) for n in (64*1024**2,128*1024**2,256*1024**2) for s in (0,97) for v in ('stream16_sum_u64_v1','device_memcpy')])
        return raw

    def test_ceiling_copy_numerator(self):
        r=ceiling_summary(self.ceiling())
        self.assertEqual(r[1]['read_plus_write_GB_s'],2*r[1]['payload_GB_s'])
        self.assertEqual(r[0]['read_plus_write_GB_s'],r[0]['payload_GB_s'])

    def test_ceiling_missing_size(self):
        raw=self.ceiling();raw['results'].pop()
        with self.assertRaises(ValueError):ceiling_summary(raw)

    def test_ceiling_missing_capacity(self):
        raw=self.ceiling();raw['device_properties'].pop('threads_per_eu')
        with self.assertRaises(ValueError):ceiling_summary(raw)

    def test_ceiling_mismatch(self):
        raw=self.ceiling();raw['results'][0]['exact']=False
        with self.assertRaises(ValueError):ceiling_summary(raw)

if __name__ == '__main__':
    unittest.main()
