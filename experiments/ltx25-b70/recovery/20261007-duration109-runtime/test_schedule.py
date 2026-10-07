"""Pinned CPU schedule controls, including actual run_behind single-fill semantics."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('schedule_tested',HERE/'schedule.py')
S=importlib.util.module_from_spec(spec);spec.loader.exec_module(S)


class ScheduleControls(unittest.TestCase):
    def setUp(self):
        self.envelope=S.build_schedule();self.schedule=self.envelope['schedule']
        self.rows={r['kind']:r for r in self.schedule['rows']}

    def test_no_names_or_indices_collide_with_sealed_101_through_107b(self):
        plan=json.loads(S.PLAN.read_text())['plan']
        names={r['name'] for r in plan['requests']} | {r['name'] for r in self.schedule['rows']}
        indices={r['clip_index'] for r in plan['requests']} | set(S.CAPTURE_INDICES.values())
        self.assertEqual(len(names),29)
        self.assertEqual(len(indices),22)
        for revision in ('101','101b','101c','102','103','104','105','106','107','107b'):
            root=S.PARENT.parent/('prepared-sparse-transport-'+revision if revision in ('107','107b') else 'prepared-sampler-accounting-106' if revision=='106' else 'prepared-client-reverse-105' if revision=='105' else 'prepared-client-compare-104' if revision=='104' else 'prepared-resolution-w2-102' if revision=='102' else 'prepared-resolution-full-103' if revision=='103' else 'prepared-resolution-reference-'+revision)/'resolution'
            prior=json.loads((root/'candidate-plan.json').read_text())['plan']
            setup=json.loads((root/'setup-schedule.json').read_text())['schedule']
            oldnames={r['name'] for r in prior['requests']} | {r['name'] for r in setup['rows']}
            oldindices={r['clip_index'] for r in prior['requests']} | {
                r['clip_index'] for r in setup['rows'] if 'clip_index' in r}
            self.assertTrue(names.isdisjoint(oldnames))
            self.assertTrue(indices.isdisjoint(oldindices))
        for revision in ('108','108b'):
            root=S.PARENT.parent/('prepared-duration-pilot-'+revision)/'resolution'
            prior=json.loads((root/'candidate-plan.json').read_text())['plan']
            setup=json.loads((root/'setup-schedule.json').read_text())['schedule']
            self.assertTrue(names.isdisjoint({r['name'] for r in prior['requests']} | {r['name'] for r in setup['rows']}))
            self.assertTrue(indices.isdisjoint({r['clip_index'] for r in prior['requests']} | {
                r['clip_index'] for r in setup['rows'] if 'clip_index' in r}))
        self.assertTrue(all(99909000 <= i < 99910000 for i in indices))

    def test_named_placement_is_source_contract_not_silent_graph_hint(self):
        value=self.schedule['sampler_placement']
        self.assertEqual(value['name'],'two-way20-28')
        self.assertEqual(value['blocks'],[20,28])
        self.assertEqual(value['segments'],[['xpu:0',0,20],['xpu:1',20,48]])
        bad=copy.deepcopy(self.envelope);bad['schedule']['sampler_placement']['blocks']=[23,25]
        bad['schedule_sha256']=S.sha(S.canonical(bad['schedule']))
        with self.assertRaisesRegex(ValueError,'pinned reconstruction'):S.validate_schedule(bad)

    def test_frozen_setup_order_boundaries_and_budget(self):
        self.assertEqual(list(self.rows),['window-probe','prepare-native','pin0','capture0','pin1','capture1','coverage','decode-probe','freeze'])
        self.assertEqual(self.schedule['submitted_requests'],29)
        self.assertEqual(self.schedule['raw_capture_requests'],22)
        self.assertEqual(self.schedule['retry_or_extra_fill_requests'],0)
        self.assertEqual(self.schedule['capture_cap'],22)
        self.assertEqual(self.schedule['native_reference_captures'],6)
        self.assertEqual(self.schedule['candidate_compared_clips'],3)
        self.assertEqual(self.schedule['timed_compared_clips'],3)
        self.assertEqual(len(self.schedule['boundary_dependencies']['barrier:reference_verified']),6)
        self.assertEqual(len(self.schedule['boundary_dependencies']['barrier:candidate_verified']),7)
        self.assertEqual(self.rows['pin0']['depends_on'],['barrier:optimized_preparation'])
        self.assertEqual(self.rows['coverage']['depends_on'],[self.rows['capture1']['name']])
        self.assertEqual(self.schedule['boundary_dependencies']['resolution-duration109-20261007-candidate-check-00'],[self.rows['freeze']['name']])
        self.assertEqual(S.validate_schedule(self.envelope),self.envelope)

    def test_first_native_barrier_is_an_existing_request_not_an_extra_execution(self):
        plan=json.loads(S.PLAN.read_text())['plan'];deps=self.schedule['boundary_dependencies']
        self.assertEqual(deps['barrier:first_native_verified'],[plan['requests'][0]['name']])
        self.assertEqual(deps[plan['requests'][1]['name']],['barrier:first_native_verified'])
        self.assertEqual(self.schedule['first_native_verification_action'],'verify-first-native')
        self.assertEqual(self.schedule['timing_interval_count'],2)
        bad=copy.deepcopy(self.envelope)
        bad['schedule']['boundary_dependencies'].pop('barrier:first_native_verified')
        bad['schedule_sha256']=S.sha(S.canonical(bad['schedule']))
        with self.assertRaisesRegex(ValueError,'pinned reconstruction'):S.validate_schedule(bad)

    def test_both_workers_are_pinned_and_capture_actions_are_distinct(self):
        for worker in (0,1):
            kind='capture%d'%worker;row=self.rows[kind]
            self.assertEqual(self.rows['pin%d'%worker]['graph']['483']['inputs']['worker'],worker)
            self.assertEqual(row['worker'],worker)
            self.assertEqual(row['clip_index'],S.CAPTURE_INDICES[kind])
            self.assertEqual(row['admission_action'],'admit-'+kind)
            self.assertEqual(row['retirement_action'],'retire-'+kind+'-tails')
            self.assertEqual(row['graph']['428']['inputs']['depth'],1)
            self.assertEqual(row['depends_on'],[self.rows['pin%d'%worker]['name']])
        self.assertEqual(self.rows['pin1']['depends_on'],[self.rows['capture0']['name']])
        self.assertEqual(self.rows['capture1']['clip_index'] % 2,1)

    def test_final_fast_barrier_no_control_and_setup_policy_always(self):
        plan=json.loads(S.PLAN.read_text())['plan']
        fast=[r for r in plan['requests'] if r['phase']=='timed-fast']
        deps=self.schedule['boundary_dependencies']
        self.assertEqual(deps['barrier:fast_verified'],[r['name'] for r in fast])
        self.assertEqual(deps[fast[0]['name']],['barrier:timing'])
        self.assertNotIn('barrier:control_verified',deps)
        self.assertEqual(deps['barrier:timing'],['barrier:candidate_verified'])
        self.assertFalse(any(r['phase']=='timed' for r in plan['requests']))
        self.assertTrue(all(r['client_checkpoint_policy']=='always' for r in self.rows.values()))
        self.assertEqual(self.schedule['timed_control_compared_clips'],0)
        self.assertEqual(self.schedule['timed_fast_compared_clips'],3)
        self.assertEqual(self.schedule['final_verification_action'],'verify-fast-timed')

    def test_unchanged_setup_numerical_inputs(self):
        for kind in ('window-probe','pin0','coverage','decode-probe','freeze'):
            before=json.loads(S.read(S.PARENT/'graphs'/S.GRAPHS[kind][0]))
            after=copy.deepcopy(self.rows[kind]['graph'])
            for node in before:
                if 'run_name' in before[node]['inputs']:after[node]['inputs']['run_name']=before[node]['inputs']['run_name']
            self.assertEqual(before,after)

    def test_native_prepare_only_one_trusted_node(self):
        self.assertEqual(self.rows['prepare-native']['graph'],{'490':{'class_type':'LTXResolutionPrepareNative',
            'inputs':{'run_name':'resolution-duration109-20261007-prepare-native'}}})
        self.assertEqual(self.rows['prepare-native']['phase'],'native-setup')

    def test_successor_setup_namespace_matches_fresh_plan(self):
        plan=json.loads(S.read(S.PLAN))
        self.assertEqual(plan['plan_sha256'],S.PLAN_SHA)
        self.assertEqual(S.sha(S.canonical(plan['plan'])),S.PLAN_SHA)
        self.assertEqual(plan['plan']['qualification_id'],S.QUALIFICATION_ID)
        for row in self.rows.values():
            self.assertEqual(row['name'],'resolution-duration109-20261007-'+row['kind'])
            for node in row['graph'].values():
                if 'run_name' in node['inputs']:
                    self.assertEqual(node['inputs']['run_name'],row['name'])
        names=[r['name'] for r in plan['plan']['requests']]
        self.assertEqual(len(names),20)
        self.assertTrue(all(n.startswith('resolution-duration109-20261007-') for n in names))
        self.assertFalse(set(names)&{r['name'] for r in self.rows.values()})

    def test_capture_delta_is_only_names_geometry_identity_and_serial_setup_depth(self):
        before=json.loads(S.read(S.PARENT/'graphs'/S.GRAPHS['capture0'][0]));after=copy.deepcopy(self.rows['capture0']['graph'])
        self.assertEqual(set(before),set(after))
        for node in before:
            self.assertEqual(before[node]['class_type'],after[node]['class_type'])
            a=after[node]['inputs'];b=before[node]['inputs']
            if node in ('364','428','426'):
                for key in ('output_size','speed_only','comparison_mode','qualification_id'):a.pop(key)
            allowed={'run_name'}
            if node in ('364','428'):allowed.add('clip_index')
            if node=='364':allowed.add('text')
            if node in ('338','339'):allowed.add('noise_seed')
            if node=='356':allowed.update(('width','height','length','batch_size'))
            if node=='366':allowed.add('frames_number')
            if node=='428':allowed.add('depth')
            self.assertEqual({k:v for k,v in a.items() if k not in allowed},{k:v for k,v in b.items() if k not in allowed})
        graph=self.rows['capture0']['graph']
        self.assertEqual(graph['428']['inputs']['mode'],'pipeline');self.assertEqual(graph['428']['inputs']['depth'],1)
        self.assertEqual(graph['426']['inputs']['mode'],'pipeline-save')
        self.assertEqual(graph['426']['inputs']['clip_index'],['428',2])
        self.assertEqual(graph['356']['inputs'],{'width':320,'height':192,'length':49,'batch_size':1})
        self.assertEqual(graph['414']['inputs']['images'],['426',0])

    def test_actual_run_behind_one_prompt_only_submits_sample_and_emits_fill(self):
        path=S.PARENT/'source/scripts/ltx_pipeline.py';raw=S.read(path)
        manifest=json.loads(S.read(S.PARENT/'manifest.json'))
        self.assertEqual(S.sha(raw),manifest['files']['source/scripts/ltx_pipeline.py'])
        tree=ast.parse(raw);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_behind')
        state={'jobs':{}};calls=[]
        def submit(stage,index,job,target=None):
            calls.append((stage,index,target));state['jobs'][index]=job;return True
        def forbidden(*args):raise AssertionError('First fill must not collect/recompute/decode')
        ns={'require':S.require,'MAX_PENDING':8,'submit':submit,'collect':forbidden,
            '_LOCK':threading.Lock(),'_state':lambda _:state,'pending':lambda _:list(state['jobs'])}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),ns)
        value,detail=ns['run_behind']('sample',S.CAPTURE_INDICES['capture0'],1,forbidden,target='ltx-sample-0')
        self.assertIsNone(value);self.assertEqual(detail['emitted_index'],-1)
        self.assertEqual(calls,[('sample',99909030,'ltx-sample-0')]);self.assertEqual(len(state['jobs']),1)
        # Even if a prior done tail remained, the second nonadjacent capture must
        # not collect it into the decoder. Runtime still explicitly retires it.
        value,detail=ns['run_behind']('sample',S.CAPTURE_INDICES['capture1'],1,forbidden,target='ltx-sample-1')
        self.assertIsNone(value);self.assertEqual(detail['emitted_index'],-1)
        self.assertEqual(calls[-1],('sample',99909041,'ltx-sample-1'))
        # PipelineDecode's existing negative-index branch produces placeholders,
        # before its decode_job definition / run_behind('decode') call.
        text=S.read(S.PARENT/'source/scripts/pipeline_decode_node.py').decode()
        self.assertLess(text.index('elif clip_index < 0:'),text.index('def decode_job('))

    def test_rehashed_schedule_tamper_is_not_accepted(self):
        bad=copy.deepcopy(self.envelope);bad['schedule']['rows'][3]['graph']['428']['inputs']['depth']=2
        bad['schedule_sha256']=S.sha(S.canonical(bad['schedule']))
        with self.assertRaisesRegex(ValueError,'pinned reconstruction'):S.validate_schedule(bad)

    def test_rehashed_missing_or_incomplete_final_barrier_refused(self):
        for mutation in (
            lambda p:p['boundary_dependencies'].pop('barrier:fast_verified'),
            lambda p:p['boundary_dependencies']['barrier:fast_verified'].pop(),
            lambda p:p.__setitem__('final_verification_action','verify-timed')):
            bad=copy.deepcopy(self.envelope);mutation(bad['schedule'])
            bad['schedule_sha256']=S.sha(S.canonical(bad['schedule']))
            with self.assertRaisesRegex(ValueError,'pinned reconstruction'):S.validate_schedule(bad)

    def test_changed_pinned_graph_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'graphs').mkdir();(p/'manifest.json').write_bytes(S.read(S.PARENT/'manifest.json'))
            for name,_ in S.GRAPHS.values():(p/'graphs'/name).write_bytes(S.read(S.PARENT/'graphs'/name))
            file=p/'graphs'/S.GRAPHS['capture0'][0];file.write_bytes(file.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'Pinned setup graph'):S.build_schedule(p)

    def test_rehashed_plan_unknown_geometry_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'plan.json';env=json.loads(S.read(S.PLAN));env['plan']['basis']['size']='512x320'
            env['plan_sha256']=S.sha(S.canonical(env['plan']));p.write_text(json.dumps(env))
            with self.assertRaisesRegex(ValueError,'Unreviewed plan'):S.build_schedule(plan_path=p)


if __name__=='__main__':unittest.main(verbosity=2)
