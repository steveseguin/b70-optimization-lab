"""CPU-only fail-closed timing, projection and census tests; no device import."""
import copy
import json
import unittest
from common import HERE, load, plan, MODES, passes
h=load('_packet11_timing',HERE/'tests/device_timing.py')

def native(layer):
    dispatch={t['name']:t['variant'] for t in json.loads((HERE/'dispatch.json').read_text())['tensors']}
    shape=[]
    for j in layer['jobs']:
        if 'ffn_gate_exps' in j['name']:shape.extend([1,1,1])
        elif j['experts']==1:shape.append(passes(dispatch[j['name']]))
    def rows(shape):
        output=[]
        for variant in MODES:
            iterations=[]
            for i in range(20):
                parts=[]
                for index,n in enumerate(shape):
                    start=i*100000+index*2000
                    parts.append([dict(start_ns=start,end_ns=start+400)] if n==1 else [dict(start_ns=start,end_ns=start+400),dict(start_ns=start+500,end_ns=start+900)])
                events=[dict(start_ns=p[0]['start_ns'],end_ns=p[-1]['end_ns']) for p in parts]
                iterations.append(dict(events=events,pass_events=parts,host_submit_ms=.1,host_wall_ms=.2))
            output.append(dict(variant=variant,layer=layer['layer'],launches=sum(shape),iterations=iterations))
        return output
    return dict(schema='own-runtime.iq3.packet11.timing-native.v1',device='mock',error='',
        route_status=[[0]*10]*3 if layer['expert_active_bytes'] else [],
        sequence=rows(shape),fused=rows([1,1,1]) if layer['expert_active_bytes'] else [],
        teardown=dict(safe_to_exit=True,idle_marker_complete=True,live_bytes=0,in_flight=0,exit_code=0,status='complete',error='',backend='mock',sequence=['context-released']))

class Protocol(unittest.TestCase):
    def setUp(self):self.p=plan();self.layer=self.p['layers'][0];self.raw=native(self.layer)
    def reject(self):
        with self.assertRaises(ValueError):h.summarize(self.raw,self.layer)
    def test_full_sequences_and_bytes(self):
        s=h.summarize(self.raw,self.layer);r=s['fused'][1]
        self.assertEqual(r['packed_bytes'],19712000);self.assertEqual(r['work_groups'],[3200,6400,20])
        self.assertAlmostEqual(r['median_ms'],.0044);self.assertEqual(r['launches'],3)
    def test_all_shapes(self):
        for l in self.p['layers']:h.summarize(native(l),l)
    def test_missing_fused(self):self.raw['fused']=[];self.reject()
    def test_missing_sequence(self):self.raw['sequence'].pop();self.reject()
    def test_missing_epilogue(self):self.raw['fused'][0]['iterations'][0]['events'].pop();self.reject()
    def test_short_samples(self):self.raw['fused'][0]['iterations'].pop();self.reject()
    def test_wrong_launches(self):self.raw['sequence'][0]['launches']-=1;self.reject()
    def test_missing_split_pass(self):
        next(p for p in self.raw['sequence'][0]['iterations'][0]['pass_events'] if len(p)==2).pop();self.reject()
    def test_inclusive_span(self):self.raw['sequence'][0]['iterations'][0]['events'][0]['end_ns']+=1;self.reject()
    def test_overlap(self):self.raw['fused'][0]['iterations'][0]['events'][1]['start_ns']=0;self.reject()
    def test_cross_iteration_overlap(self):self.raw['fused'][0]['iterations'][1]=copy.deepcopy(self.raw['fused'][0]['iterations'][0]);self.reject()
    def test_boolean_timestamp(self):
        with self.assertRaises(ValueError):h.spans([dict(start_ns=False,end_ns=10)])
    def test_bad_host_clock(self):self.raw['sequence'][0]['iterations'][0]['host_wall_ms']=float('nan');self.reject()
    def test_bad_status(self):self.raw['route_status'][0][0]=1;self.reject()
    def test_unsafe_teardown(self):self.raw['teardown']['live_bytes']=10;self.reject()
    def test_wrong_layer(self):self.raw['fused'][0]['layer']=3;self.reject()
    def test_owner_budget(self):
        self.assertEqual(self.p['owner_sessions'],10)
        self.assertTrue(all(l['event_count_upper_bound']<4096 for l in self.p['layers']))
    def test_dispatch(self):
        dispatch=load('_packet11_dispatch',HERE/'dispatch.py');d=dispatch.calculate()
        self.assertEqual(d,json.loads((HERE/'dispatch.json').read_text()));self.assertEqual(dispatch.header(d),(HERE/'dispatch.hpp').read_text())
        self.assertEqual(len(d['tensors']),1224);self.assertEqual(len(d['table']),25)
    def test_head_is_real_shape(self):
        head=self.p['layers'][-1]['jobs'][-1];self.assertEqual((head['rows'],head['columns'],head['weight_bytes']),(248320,2560,521472000))
    def test_projection(self):
        records=[dict(repeat=repeat,layer=l['layer'],summary=h.summarize(native(l),l)) for repeat in range(2) for l in self.p['layers']]
        result=h.project(records,self.p);self.assertFalse(result['measured']);self.assertEqual(len(result['rows']),8)
        row=result['rows'][0];self.assertEqual((row['gdn_layers'],row['qsa_layers']),(36,12))
        self.assertAlmostEqual(row['projected_tok_s'],1000/row['projected_ms_per_token'])
        with self.assertRaises(ValueError):h.project(records[:-1],self.p)
    def test_census_fail_closed(self):
        with self.assertRaises(ValueError):h.validate_census([],self.layer)
    def test_forecast_not_measurement(self):
        import sys
        sys.path.insert(0,str(HERE));a=load('_packet11_analysis',HERE.parent/'packet9-kopt4/analysis.py').calculate()
        self.assertFalse(a['measured']);self.assertEqual(a['corrections']['selected_expert_bytes_per_token'],949760000)
        self.assertGreater(a['scenarios'][0]['predicted_ms_range'][0],a['scenarios'][0]['bandwidth_only_590_floor_ms'])

class NativeIssueAnalysis(unittest.TestCase):
    def test_native_regions_and_spill_penalty(self):
        a=load('_packet11_analysis',HERE/'analysis.py').calculate()
        self.assertFalse(a['measured']);self.assertFalse(a['assumptions']['verified'])
        self.assertEqual(len(a['predictions']),8)
        self.assertEqual([r['table_loads'] for r in a['native_regions']],[1,2])
        self.assertEqual([r['integer_to_float'] for r in a['native_regions']],[8,8])
        for r in a['predictions']:
            self.assertGreater(r['native_region_instructions'],0)
            self.assertTrue(0<r['predicted_GB_s'][0]<=r['predicted_GB_s'][1]<=590)
    def test_modes_and_hash_sources(self):
        from common import sources
        self.assertEqual(tuple(MODES),('experts_sg32','register_grid','slm_pair','packed_pipeline'))
        self.assertIn(HERE/'decode.hpp',sources())
        self.assertIn(HERE/'kernels.cpp',sources())

class ExactnessWindow(unittest.TestCase):
    def run_window(self, raw, fault_at=None, stop_reason=None):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch, Mock
        import watcher
        exact=load('_packet11_exactness',HERE/'tests/device_window.py')
        with tempfile.TemporaryDirectory(dir=HERE/'build') as tmp:
            root=Path(tmp);out=root/'window';latch=root/'latch.json'
            fault='xe: Fault response for engine 0'
            tails=iter(range(22))
            def journal(*args):
                n=next(tails,99)
                return (fault+'\n' if n==fault_at else '', 'cursor')
            def launch(command, **kwargs):
                if raw is not None:Path(command[4]).write_text(json.dumps(raw))
                child=Mock(pid=123,returncode=1 if raw is None or raw.get('error') else 0)
                child.poll.return_value=child.returncode
                return child
            with patch.object(exact,'admit',return_value=(out,dict(fixture_cases={m:26 for m in MODES}))), \
                 patch.object(exact,'sha',return_value='prepared'), patch.object(exact,'LATCH',latch), \
                 patch.object(watcher,'LATCH',latch), patch.object(watcher,'journal',side_effect=journal), \
                 patch.object(watcher.subprocess,'Popen',side_effect=launch) as child, \
                 patch.object(watcher.time,'sleep'), patch.object(watcher.signal,'signal'), \
                 patch.object(watcher.signal,'getsignal'):
                if stop_reason:
                    with patch.object(watcher.time,'monotonic',side_effect=[0,121,122]):exact.execute(3,out)
                else:exact.execute(3,out)
                record=json.loads((out/'window.json').read_text())
                saved=json.loads(latch.read_text()) if latch.exists() else None
                self.assertEqual(child.call_count,4 if record['passed'] else 1)
                return record,saved
    def raw(self, error='', checks=26, failure_kind=''):
        return dict(checks=checks,error=error,failure_kind=failure_kind,teardown=native(plan()['layers'][0])['teardown'])
    def test_native_aborted_before_checks(self):
        r,latch=self.run_window(self.raw('duplicate allocation label',0,'infrastructure'))
        self.assertEqual(r['error'],'aborted: duplicate allocation label');self.assertEqual(r['outcome'],'aborted')
        self.assertFalse(r['passed']);self.assertIsNone(latch)
    def test_actual_exactness_failure_in_first_case(self):
        r,latch=self.run_window(self.raw('device/CPU byte mismatch',0,'exactness'))
        self.assertEqual(r['outcome'],'exactness_failed');self.assertIn('exactness failed',latch['reason'])
    def test_kernel_fault_before_native_receipt(self):
        r,latch=self.run_window(None,fault_at=1)
        self.assertEqual(r['outcome'],'kernel_fault');self.assertIn('Fault response',latch['fault_lines'][0])
    def test_post_exit_fault_overrides_native_abort(self):
        r,latch=self.run_window(self.raw('duplicate allocation label',0,'infrastructure'),fault_at=2)
        self.assertEqual(r['outcome'],'kernel_fault');self.assertEqual(len(latch['fault_lines']),1)
    def test_missing_native_receipt_is_abort(self):
        r,latch=self.run_window(None);self.assertEqual(r['outcome'],'aborted');self.assertIsNone(latch)
    def test_incomplete_coverage_is_abort(self):
        r,latch=self.run_window(self.raw(checks=0));self.assertEqual(r['outcome'],'aborted');self.assertIsNone(latch)
    def test_both_variants_pass(self):
        r,latch=self.run_window(self.raw());self.assertTrue(r['passed']);self.assertIsNone(latch)
    def test_deadline_still_latches(self):
        r,latch=self.run_window(self.raw('cooperative stop',0,'infrastructure'),stop_reason='deadline')
        self.assertEqual(r['outcome'],'window_stopped');self.assertEqual(latch['reason'],'window deadline')
    def test_unsafe_teardown_still_latches(self):
        raw=self.raw('allocation failed',0,'infrastructure');raw['teardown']['safe_to_exit']=False
        r,latch=self.run_window(raw);self.assertFalse(r['passed']);self.assertIn('unsafe teardown',latch['reason'])

if __name__=='__main__':unittest.main()
