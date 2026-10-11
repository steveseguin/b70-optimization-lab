"""CPU-only negative tests: no watcher/device child is called."""
import copy
import unittest
from common import HERE, load, plan, VARIANTS, SMALL, EXPERTS, phase_variants, passes

harness = load('_packet8_timing', HERE / 'tests/device_timing.py')


def events(n=20, ns=1000):
    return [dict(start_ns=i * ns * 2, end_ns=i * ns * 2 + ns) for i in range(n)]


def native(layer):
    rows = []
    for j in layer['jobs']:
        for variant in phase_variants('kernels'):
            rows.append(dict(name=j['name'], variant=variant, events=events(ns=2000 if variant == 'kopt_sg32' else 1000), pass_events=[[dict(start_ns=e['start_ns'],end_ns=e['start_ns']+400),dict(start_ns=e['start_ns']+500,end_ns=e['end_ns'])] if passes(variant)==2 else [e] for e in events(ns=2000 if variant == 'kopt_sg32' else 1000)],
                             route_status=[0] * 10 if j['experts'] == 512 else []))
    return dict(schema='own-runtime.iq3.packet8.timing-native.v1', error='', device='mock', phase='kernels', kernels=rows, sequence=[], fused=[],
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
        self.assertEqual(p['owner_sessions'], 9)
        self.assertTrue(all(l['event_count_upper_bound'] < 4096 for l in p['layers']))

    def test_fused_and_sequences(self):
        layer = plan()['layers'][0]
        raw = native(layer);raw.update(phase='groups',kernels=[],fused=[])
        raw['sequence'] = [dict(variant=v, layer=0, launches_per_layer=len(layer['jobs']),
            iterations=[dict(events=events(len(layer['jobs']))) for _ in range(20)]) for v in ('kopt_sg32','shape_dispatch_v1')]
        import json
        dispatch={t['name']:t['variant'] for t in json.loads((HERE/'dispatch.json').read_text())['tensors']}
        for seq in raw['sequence']:
            ns=[passes(dispatch[j['name']]) if seq['variant']=='shape_dispatch_v1' else 1 for j in layer['jobs']]
            seq['native_events_per_layer']=sum(ns)
            for iteration in seq['iterations']:
                iteration['pass_events']=[[dict(start_ns=e['start_ns'],end_ns=e['start_ns']+400),dict(start_ns=e['start_ns']+500,end_ns=e['end_ns'])] if n==2 else [e] for e,n in zip(iteration['events'],ns)]
        for kind, names in (('small',SMALL),('expert_gate_up',EXPERTS[:2]),('expert_down',EXPERTS[2:])):
            for v in ('decode_const_sg32_v1','decode_slm_sg32_v1'):
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


    def test_dispatch_all_production_tensors(self):
        dispatch=load('_dispatch', HERE/'dispatch.py')
        data=dispatch.calculate()
        self.assertEqual(len(data['tensors']),1224)
        for tensor in data['tensors']:
            if tensor['kind']=='gemv':
                matches=[r for r in data['table'] if r['key']==tensor['key']]
                self.assertEqual(len(matches),1)
                self.assertEqual(tensor['variant'],matches[0]['variant'])
        import json
        self.assertEqual(data,json.loads((HERE/'dispatch.json').read_text()))
        self.assertEqual(dispatch.header(data),(HERE/'dispatch.hpp').read_text())

    def test_dispatch_shapes(self):
        dispatch=load('_dispatch', HERE/'dispatch.py')
        rows={t['name']:t['variant'] for t in dispatch.calculate()['tensors']}
        self.assertEqual(rows['blk.0.hc_attn_down.weight'],'splitk4_v1')
        self.assertEqual(rows['blk.0.hc_attn_up.weight'],'kopt_sg32')
        self.assertEqual(rows['blk.0.ffn_gate_exps.weight'],'kopt_sg32')

    def test_split_candidate_pass_count(self):
        self.assertEqual(passes('decode_slm_split4_v1'),2)
        self.assertEqual(passes('decode_const_sg32_v1'),1)

    def test_shape_dispatch_missing_row(self):
        layer=plan()['layers'][0];raw=native(layer)
        raw.update(phase='groups',kernels=[],fused=[],sequence=[])
        with self.assertRaises(ValueError):harness.summarize(raw,layer)

    def test_pass_span_count_refused(self):
        self.raw['kernels'][1]['pass_events'].pop()
        with self.assertRaises(ValueError):harness.summarize(self.raw,self.layer)

    def test_source_cost_counts(self):
        import sys
        sys.path.insert(0,str(HERE))
        analysis=load('_analysis',HERE/'analysis.py').calculate_analysis()
        self.assertFalse(analysis['measured'])
        self.assertEqual(len(analysis['counts']),8)
        self.assertTrue(all(r['round2']['fma']==r['round3']['fma']==0 for r in analysis['counts']))
        self.assertTrue(all(0<r['predicted_GB_s'][0]<=r['predicted_GB_s'][1]<=590 for r in analysis['forecasts']))

if __name__ == '__main__':
    unittest.main()
