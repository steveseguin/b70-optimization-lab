"""Small synthetic controls, using actual pinned graphs and real request/capture schemas."""
import copy
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import sys
import unittest

HERE = Path(__file__).resolve().parent

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

C = load('candidate_tested', 'candidate_gate.py')
T = load('native_fixture_helpers', 'test_reference_gate.py')
C.R = T.G  # Share the deliberately tiny test tensor shapes, never bypass verification.


class CandidateControls(unittest.TestCase):
    def setUp(self):
        self.f = T.GateTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.run_gate(); self.ref = self.f.output; self.refsha = C.R.sha(self.ref.read_bytes())
        self.reference = C.R.verify_receipt(self.ref, self.refsha)
        self.root = self.f.root; self.server = self.f.server
        self.output = self.root / 'candidate.json'; self.timed = self.root / 'timed.json'
        self.client_contract = {'schema': 'ltx.resolution-request-client.v1',
            'root': str(self.root), 'server_run': str(self.server),
            'plan_sha256': C.R.PLAN_SHA,
            'runtime_manifest_sha256': self.reference['runtime_manifest_sha256'],
            'server_identity_sha256': self.reference['server_identity_sha256'],
            'source_bindings': {str(self.f.client_source): C.R.sha(self.f.client_source.read_bytes())}}
        self.f.write(self.server / 'resolution-client-contract.json', self.client_contract)
        self.fast = self.root / 'fast.json'
        self.make_phase('candidate-check')

    def auth(self, role, name, phase, candidate_sha=None):
        value = {'role': role, 'run_name': name,
                 'phase': 'optimized_preparation' if phase == 'candidate-check' else 'timing',
                 'qualification_id': C.R.QUALIFICATION_ID, 'plan_sha256': C.R.PLAN_SHA,
                 'comparison_mode': 'same-size-native-v1', 'runtime_manifest_sha256': self.reference['runtime_manifest_sha256'],
                 'server_identity_sha256': self.reference['server_identity_sha256'],
                 'reference_receipt_sha256': self.refsha, 'candidate_receipt_sha256': candidate_sha}
        return value

    def label(self, value, role, name, phase, candidate_sha=None):
        value.update(output_size='640x384', frame_count=49, speed_only=False, output_parity_claimed=False)
        value['session_observation' if role == 'auxiliary' else 'phase_authorization'] = self.auth(role, name, phase, candidate_sha)
        return value

    def make_phase(self, phase, candidate_sha=None):
        rows = [r for r in self.f.plan['requests'] if r['phase'] == phase]
        for i, row in enumerate(rows):
            name = row['name']; req = self.root / 'requests' / name; req.mkdir(parents=True)
            pid = 'test-' + name; start = {'candidate-check':30000,'timed-fast':60000}[phase] + i*1000
            end = start+500
            messages = [['execution_start', {'prompt_id': pid, 'timestamp': start}],
                        ['execution_cached', {'prompt_id': pid, 'timestamp': start, 'nodes': []}],
                        ['execution_success', {'prompt_id': pid, 'timestamp': end}]]
            status = {'status_str': 'success', 'completed': True, 'messages': messages}
            for file, value in [('prompt.json', row['graph']), ('submission.json', {'prompt_id':pid,'number':i,'node_errors':{}}),
                                ('history.json', {'prompt':[i,pid,row['graph']],'status':status}),
                                ('result.json', {'name':name,'prompt_id':pid,'status':status}), ('identity.json',self.f.identity)]:
                self.f.write(req/file,value)
            events = [{'type':'execution_start','seconds':0,'data':messages[0][1]}]
            events += [{'type':'executing','seconds':j/10,'data':{'prompt_id':pid,'node':n}} for j,n in enumerate(['364','428','426','414'])]
            events.append({'type':'execution_success','seconds':.5,'data':messages[-1][1]})
            (req/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            if phase == 'timed-fast':
                self.f.write(req / 'client-policy.json', {
                    'schema':'ltx.client-checkpoint-policy.v1','name':name,'phase':phase,
                    'policy':row['client_checkpoint_policy'], 'checkpoint_count':20,
                    'storage_save_count':5,
                    'skipped_storage_save_count':15,
                    'source_sha256':C.R.sha(self.f.client_source.read_bytes()),
                    'plan_sha256':C.R.PLAN_SHA,
                    'runtime_manifest_sha256':self.reference['runtime_manifest_sha256'],
                    'server_identity_sha256':self.reference['server_identity_sha256'],
                    'client_contract_sha256':C.R.sha((self.server/'resolution-client-contract.json').read_bytes())})
            common = {'passed':True,'run_name':name,'server_identity_sha256':self.reference['server_identity_sha256'],
                      'model_verification_sha256':'b'*64}
            textsha = C.R.sha(('pipeline-window\n' + row['graph']['364']['inputs']['text']).encode('utf-8'))
            text = dict(common,clip_index=row['clip_index'],mode='pipeline-window',depth=2,
                        detail={'text_sha256':textsha,'tag':textsha,'speculation_miss':False,
                                'window_encode':{'window':64,'clip_index':row['clip_index']}})
            si = -1 if i < 2 else row['clip_index']-2
            di = -1 if i < 4 else rows[0]['clip_index']+row['expected_emitted_index']
            sample = dict(common,schema='ltx.pipeline-sampler-request.v1',clip_index=row['clip_index'],mode='pipeline-lean',
                          depth=2,sampler_batch=1,sampler_workers=2,detail={'emitted_index':si})
            decode = dict(common,schema='ltx.pipeline-decode-request.v1',clip_index=si,mode='pipeline-replica',
                          depth=2,upstream_depth=0,detail={'emitted_index':di},save_failures=[])
            for stem, role, val in [('pipeline-','text',text),('pipeline-sampler-','sampler',sample),('pipeline-decode-','decode',decode)]:
                self.f.write(self.server/(stem+name+'.json'),self.label(val,role,name,phase,candidate_sha))
            if i < 4: continue
            original = self.root/'output/validation'/row['reference']; out = original.parent/name
            shutil.copytree(original,out)
            self.f.mutate(out/'summary.json',lambda v:v.update(run_name=name))
            prefix = rows[row['expected_emitted_index']+2]['name']+'/preview'
            saved = prefix+'_00001_.mp4'; preview=self.root/'output'/saved; preview.parent.mkdir(parents=True,exist_ok=True);preview.write_bytes(b'synthetic-preview')
            self.f.write(self.server/('pipeline-save-'+name+'.json'), {'schema':'ltx.pipeline-save-record.v2','run_name':name,
                         'status':'queued-to-writer','prefix':prefix,'saved_file':None})
            for j, stage in enumerate(('sample','decode','save')):
                done={'stage':stage,'index':di,'finished_unix':(start+100+j*100)/1000}
                done.update({'finite':True} if stage=='sample' else {'slot':('native','replica')[di%2]} if stage=='decode' else {'saved':saved})
                self.f.write(self.server/('pipeline-done-%s-%d.json'%(stage,di)),self.label(done,'auxiliary',None,phase,candidate_sha))

    def run_gate(self):
        return C.verify_outputs(self.root,T.PLAN,self.ref,self.refsha,'candidate-check',self.output)

    def refuse(self):
        with self.assertRaises((ValueError,KeyError,FileNotFoundError)):self.run_gate()
        self.assertFalse(self.output.exists())

    def row(self,index=10):return self.f.plan['requests'][index]

    def marker(self, stage, emitted=0):
        base = self.row(6)['clip_index']
        return self.server / ('pipeline-done-%s-%d.json' % (stage, base+emitted))

    def test_complete_candidate_reconstruction_and_timing(self):
        result=self.run_gate();self.assertEqual(result['four_tensor_exact_clips'],3)
        sha=C.R.sha(self.output.read_bytes());self.assertEqual(C.verify_candidate_receipt(self.output,sha),result)
        self.make_phase('timed-fast',sha)
        fast=self.run_fast(sha)
        self.assertEqual(fast['completion_intervals_seconds'],[1.]*2)
        self.assertEqual(fast['status'],'timed_fast_verified')
        self.assertNotIn('fast_receipt_sha256',fast)
        self.assertNotIn('control_receipt_sha256',fast)
        self.assertEqual([r['timing_scope'] for r in fast['executions'][4:]],['duration49-three-fixture-pilot']*3)
        self.assertTrue(all('trace_enabled' not in r for r in fast['executions']))
        self.assertEqual(fast['policy_totals']['skipped_storage_save_count'],7*15)
        fast_sha=C.R.sha(self.fast.read_bytes())
        self.assertEqual(C.verify_fast_receipt(self.fast,fast_sha),fast)
        self.assertNotIn('torch',sys.modules)

    def test_fill_capture_is_never_parity(self):
        for index in (6, 9):  # First and fourth fills are not scored tensor captures.
            folder=self.root/'output/validation'/self.row(index)['name']
            folder.mkdir();(folder/'tensors.safetensors').write_bytes(b'placeholder')
        result=self.run_gate();self.assertEqual([r['parity_status'] for r in result['executions'][:4]],['not-scored-fill']*4)

    def test_conditioning_tags_match_pinned_producer_for_candidate_and_timing(self):
        parent=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b')
        manifest=C.R.read_file(parent/'manifest.json')
        self.assertEqual(C.R.sha(manifest),C.R.PARENT_SHA)
        source=C.R.read_file(parent/'source/scripts/pipeline_node.py')
        self.assertEqual(C.R.sha(source),json.loads(manifest)['files']['source/scripts/pipeline_node.py'])
        functions=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in ('_text_sha256','_job_tag')]
        self.assertEqual(len(functions),2)
        ns={'hashlib':hashlib}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'pinned-producer-tag','exec'),ns)
        candidate_sha=self.prepare_fast()
        for row in [r for r in self.f.plan['requests'] if r['phase'] in ('candidate-check','timed-fast')]:
            inputs=row['graph']['364']['inputs'];expected=ns['_job_tag'](inputs['mode'],inputs['text'])
            p=self.server/('pipeline-'+row['name']+'.json')
            detail=json.loads(p.read_text())['detail']
            self.assertEqual(detail['text_sha256'],expected);self.assertEqual(detail['tag'],expected)
            self.assertNotEqual(expected,ns['_text_sha256'](inputs['text']))
        self.run_fast(candidate_sha)

    def test_raw_text_digest_refused_for_window_conditioning(self):
        row=self.row();wrong=C.R.sha(row['graph']['364']['inputs']['text'].encode('utf-8'))
        p=self.server/('pipeline-'+row['name']+'.json')
        self.f.mutate(p,lambda v:v['detail'].update(tag=wrong,text_sha256=wrong))
        with self.assertRaisesRegex(ValueError,'Conditioning provenance differs'):self.run_gate()
        self.assertFalse(self.output.exists())

    def test_wrong_emitted_index_and_missing_worker_marker(self):
        name=self.row()['name'];p=self.server/('pipeline-decode-'+name+'.json')
        self.f.mutate(p,lambda v:v['detail'].update(emitted_index=self.row(6)['clip_index']+1));self.refuse()

    def test_wrong_sampler_worker_or_depth_refused(self):
        p = self.server / ('pipeline-sampler-' + self.row()['name'] + '.json')
        original = json.loads(p.read_text())
        for field, value in [('sampler_workers', 1), ('depth', 1), ('sampler_batch', 2)]:
            changed = copy.deepcopy(original)
            changed[field] = value
            self.f.write(p, changed)
            with self.assertRaisesRegex(ValueError, 'Sampler emission differs'):
                self.run_gate()
            self.assertFalse(self.output.exists())
        self.f.write(p, original)

    def test_all_pipeline_roles_refuse_missing_or_old_frame_count(self):
        for role in ('pipeline', 'pipeline-sampler', 'pipeline-decode'):
            p = self.server / (role + '-' + self.row()['name'] + '.json')
            original = json.loads(p.read_text())
            for bad in (None, 25, 49.0, True):
                with self.subTest(role=role, frame_count=bad):
                    changed = copy.deepcopy(original)
                    if bad is None:
                        changed.pop('frame_count')
                    else:
                        changed['frame_count'] = bad
                    self.f.write(p, changed)
                    with self.assertRaisesRegex(ValueError, 'Pipeline request identity/failure'):
                        self.run_gate()
                    self.assertFalse(self.output.exists())
            self.f.write(p, original)

    def test_fourth_fill_and_two_prompt_sampler_delay_are_required(self):
        row = self.row(7)  # second candidate request must still be sampler fill
        p = self.server / ('pipeline-sampler-' + row['name'] + '.json')
        self.f.mutate(p, lambda v: v['detail'].update(emitted_index=row['clip_index']-1))
        with self.assertRaisesRegex(ValueError, 'Sampler emission differs'):
            self.run_gate()
        self.assertFalse(self.output.exists())

    def test_preview_must_use_two_prompt_producer_offset(self):
        row = self.row()
        p = self.server / ('pipeline-save-' + row['name'] + '.json')
        wrong = self.row(7)['name'] + '/preview'
        self.f.mutate(p, lambda v: v.update(prefix=wrong))
        with self.assertRaisesRegex(ValueError, 'Preview completion/prefix differs'):
            self.run_gate()
        self.assertFalse(self.output.exists())

    def test_missing_done_marker(self):
        self.marker('save').unlink();self.refuse()

    def test_wrong_deterministic_decode_slot_refused(self):
        self.f.mutate(self.marker('decode', 1),lambda v:v.update(slot='native'));self.refuse()

    def test_preview_failure_refused(self):
        self.f.mutate(self.marker('save'),lambda v:v.update(saved='save-failed:RuntimeError'));self.refuse()

    def test_coherent_tensor_change_still_rejected_by_native_bytes(self):
        folder=self.root/'output/validation'/self.row()['name'];p=folder/'tensors.safetensors'
        p.write_bytes(p.read_bytes()[:-8]+struct.pack('<ff',99.,1.))
        self.f.mutate(folder/'summary.json',lambda v:v['tensors']['waveform'].update(sha256=C.R.sha(struct.pack('<ff',99.,1.))))
        self.refuse()

    def test_last_candidate_fixture_tensor_difference_refused(self):
        row = [r for r in self.f.plan['requests'] if r['phase'] == 'candidate-check'][-1]
        self.assertEqual(row['expected_emitted_fixture'], 'bird')
        folder = self.root/'output/validation'/row['name']
        p = folder/'tensors.safetensors'
        p.write_bytes(p.read_bytes()[:-8] + struct.pack('<ff', 77., 1.))
        self.f.mutate(folder/'summary.json', lambda v: v['tensors']['waveform'].update(
            sha256=C.R.sha(struct.pack('<ff', 77., 1.))))
        with self.assertRaisesRegex(ValueError, 'Four-tensor native equality failed'):
            self.run_gate()
        self.assertFalse(self.output.exists())

    def prepare_fast(self):
        self.run_gate(); candidate_sha=C.R.sha(self.output.read_bytes())
        self.make_phase('timed-fast',candidate_sha)
        return candidate_sha

    def run_fast(self, candidate_sha):
        return C.verify_outputs(self.root,T.PLAN,self.ref,self.refsha,'timed-fast',self.fast,
                                self.output,candidate_sha)

    def test_fast_policy_readout_required(self):
        sha=self.prepare_fast()
        row=next(r for r in self.f.plan['requests'] if r['phase']=='timed-fast')
        (self.root/'requests'/row['name']/'client-policy.json').unlink()
        with self.assertRaises(FileNotFoundError):self.run_fast(sha)
        self.assertFalse(self.fast.exists())

    def test_policy_counts_identity_and_source_pin_are_checked(self):
        sha=self.prepare_fast()
        row=next(r for r in self.f.plan['requests'] if r['phase']=='timed-fast')
        path=self.root/'requests'/row['name']/'client-policy.json'
        original=json.loads(path.read_text())
        for changes in ({'checkpoint_count':21},{'checkpoint_count':True},
                        {'source_sha256':'f'*64},{'client_contract_sha256':'f'*64},
                        {'policy':'always'},{'phase':'timed'}):
            self.f.write(path,dict(original,**changes))
            with self.assertRaises(ValueError):self.run_fast(sha)
            self.assertFalse(self.fast.exists())
        self.f.write(path,original)
        self.f.client_source.write_text('# Changed source bytes')
        with self.assertRaisesRegex(ValueError,'source binding differs'):self.run_fast(sha)

    def test_control_phase_and_dangling_proof_dependencies_refused(self):
        sha=self.prepare_fast()
        with self.assertRaisesRegex(ValueError,'Unknown verification phase'):
            C.verify_outputs(self.root,T.PLAN,self.ref,self.refsha,'timed',self.timed,self.output,sha)
        for kwargs in ({'control_receipt_path':self.fast,'control_sha256':'a'*64},
                       {'fast_receipt_path':self.fast,'fast_sha256':'a'*64}):
            with self.assertRaises(TypeError):
                C.verify_outputs(self.root,T.PLAN,self.ref,self.refsha,'timed-fast',self.fast,self.output,sha,**kwargs)
        self.assertFalse(self.fast.exists());self.assertFalse(self.timed.exists())

    def test_forged_fast_receipt_and_changed_fast_policy_refused(self):
        sha=self.prepare_fast();self.run_fast(sha)
        original=self.fast.read_bytes()
        self.f.mutate(self.fast,lambda v:v.update(four_tensor_exact_clips=99))
        with self.assertRaisesRegex(ValueError,'actual evidence'):
            C.verify_fast_receipt(self.fast,C.R.sha(self.fast.read_bytes()))
        self.fast.write_bytes(original)
        row=next(r for r in self.f.plan['requests'] if r['phase']=='timed-fast')
        self.f.mutate(self.root/'requests'/row['name']/'client-policy.json',lambda v:v.update(source_sha256='f'*64))
        with self.assertRaisesRegex(ValueError,'readout identity'):
            C.verify_fast_receipt(self.fast,C.R.sha(original))

    def test_fast_zero_skips_is_valid_but_must_report_it_truthfully(self):
        sha=self.prepare_fast()
        for row in (r for r in self.f.plan['requests'] if r['phase']=='timed-fast'):
            self.f.mutate(self.root/'requests'/row['name']/'client-policy.json',
                          lambda v:v.update(storage_save_count=20,skipped_storage_save_count=0))
        result=self.run_fast(sha)
        self.assertEqual(result['policy_totals']['skipped_storage_save_count'],0)

    def test_first_fast_last_fixture_still_requires_exact_native_bytes(self):
        sha=self.prepare_fast()
        row=[r for r in self.f.plan['requests'] if r['phase']=='timed-fast'][-1]
        self.assertEqual(row['expected_emitted_fixture'],'bird')
        folder=self.root/'output/validation'/row['name'];p=folder/'tensors.safetensors'
        p.write_bytes(p.read_bytes()[:-8]+struct.pack('<ff',99.,1.))
        self.f.mutate(folder/'summary.json',lambda v:v['tensors']['waveform'].update(
            sha256=C.R.sha(struct.pack('<ff',99.,1.))))
        with self.assertRaisesRegex(ValueError,'Four-tensor native equality failed'):
            self.run_fast(sha)
        self.assertFalse(self.fast.exists())

    def test_fast_cannot_reuse_candidate_prompt_id(self):
        sha=self.prepare_fast()
        candidate=json.loads(self.output.read_text())
        row=next(r for r in self.f.plan['requests'] if r['phase']=='timed-fast')
        self.f.mutate(self.root/'requests'/row['name']/'submission.json',
                      lambda v:v.update(prompt_id=candidate['executions'][0]['prompt_id']))
        with self.assertRaisesRegex(ValueError,'Duplicate/failed submission'):
            self.run_fast(sha)
        self.assertFalse(self.fast.exists())

    def test_fast_must_begin_after_last_candidate_execution(self):
        sha=self.prepare_fast()
        row=next(r for r in self.f.plan['requests'] if r['phase']=='timed-fast')
        folder=self.root/'requests'/row['name']
        for n in ['history.json','result.json']:
            self.f.mutate(folder/n,lambda v:v['status']['messages'][0][1].update(timestamp=30000))
        with self.assertRaisesRegex(ValueError,'time ordering differs'):
            self.run_fast(sha)
        self.assertFalse(self.fast.exists())

    def test_unknown_graph_or_runtime_refused(self):
        p=self.root/'requests'/self.row()['name']/'identity.json';self.f.mutate(p,lambda v:v.update(pid=999));self.refuse()

    def test_graph_tamper_refused(self):
        p=self.root/'requests'/self.row()['name']/'prompt.json';self.f.mutate(p,lambda v:v['338']['inputs'].update(noise_seed=0));self.refuse()

    def test_wrong_phase_or_reference_receipt_refused(self):
        p=self.server/('pipeline-sampler-'+self.row()['name']+'.json')
        self.f.mutate(p,lambda v:v['phase_authorization'].update(reference_receipt_sha256='f'*64));self.refuse()

    def test_cached_execution_refused(self):
        folder=self.root/'requests'/self.row()['name']
        for file in ('history.json','result.json'):
            self.f.mutate(folder/file,lambda v:v['status']['messages'][1][1].update(nodes=['428']))
        self.refuse()

    def test_missing_numerical_event_refused(self):
        p=self.root/'requests'/self.row()['name']/'events.jsonl'
        p.write_text(''.join(line+'\n' for line in p.read_text().splitlines() if json.loads(line)['data'].get('node')!='428'));self.refuse()

    def test_exclusive_output_and_forged_rehashed_receipt(self):
        self.run_gate()
        with self.assertRaisesRegex(ValueError,'already exists'):self.run_gate()
        self.f.mutate(self.output,lambda v:v.update(four_tensor_exact_clips=99))
        with self.assertRaisesRegex(ValueError,'actual evidence'):C.verify_candidate_receipt(self.output,C.R.sha(self.output.read_bytes()))

    def test_changed_native_evidence_and_fault_refused(self):
        (self.root/'FAULT.json').write_text('{}');self.refuse()

    def test_actual_session_halt_refuses_existing_success_artifacts(self):
        (self.server/'resolution-halt.json').write_text('{"reason":"postcheck failure"}')
        self.refuse()

    def test_timing_without_verified_candidate_refused(self):
        with self.assertRaisesRegex(ValueError,'needs verified candidate'):
            C.verify_outputs(self.root,T.PLAN,self.ref,self.refsha,'timed-fast',self.fast)
        self.assertFalse(self.fast.exists())


if __name__=='__main__':unittest.main(verbosity=2)
