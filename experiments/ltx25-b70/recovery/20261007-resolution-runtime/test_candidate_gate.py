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
        self.make_phase('candidate-check')

    def auth(self, role, name, phase, candidate_sha=None):
        value = {'role': role, 'run_name': name,
                 'phase': 'optimized_preparation' if phase == 'candidate-check' else 'timing',
                 'qualification_id': C.R.QUALIFICATION_ID, 'plan_sha256': C.R.PLAN_SHA,
                 'comparison_mode': 'same-size-native-v1', 'runtime_manifest_sha256': 'a'*64,
                 'server_identity_sha256': self.reference['server_identity_sha256'],
                 'reference_receipt_sha256': self.refsha, 'candidate_receipt_sha256': candidate_sha}
        return value

    def label(self, value, role, name, phase, candidate_sha=None):
        value.update(output_size='640x384', speed_only=False, output_parity_claimed=False)
        value['session_observation' if role == 'auxiliary' else 'phase_authorization'] = self.auth(role, name, phase, candidate_sha)
        return value

    def make_phase(self, phase, candidate_sha=None):
        rows = [r for r in self.f.plan['requests'] if r['phase'] == phase]
        for i, row in enumerate(rows):
            name = row['name']; req = self.root / 'requests' / name; req.mkdir(parents=True)
            pid = 'test-' + name; start = (10000 if phase == 'candidate-check' else 30000) + i*1000; end = start+500
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
            common = {'passed':True,'run_name':name,'server_identity_sha256':self.reference['server_identity_sha256'],
                      'model_verification_sha256':'b'*64}
            textsha = C.R.sha(('pipeline-window\n' + row['graph']['364']['inputs']['text']).encode('utf-8'))
            text = dict(common,clip_index=row['clip_index'],mode='pipeline-window',depth=2,
                        detail={'text_sha256':textsha,'tag':textsha,'speculation_miss':False,
                                'window_encode':{'window':64,'clip_index':row['clip_index']}})
            si = -1 if i == 0 else row['clip_index']-1
            di = -1 if i < 3 else rows[0]['clip_index']+row['expected_emitted_index']
            sample = dict(common,schema='ltx.pipeline-sampler-request.v1',clip_index=row['clip_index'],mode='pipeline-lean',
                          depth=1,sampler_batch=1,sampler_workers=1,detail={'emitted_index':si})
            decode = dict(common,schema='ltx.pipeline-decode-request.v1',clip_index=si,mode='pipeline-replica',
                          depth=2,upstream_depth=0,detail={'emitted_index':di},save_failures=[])
            for stem, role, val in [('pipeline-','text',text),('pipeline-sampler-','sampler',sample),('pipeline-decode-','decode',decode)]:
                self.f.write(self.server/(stem+name+'.json'),self.label(val,role,name,phase,candidate_sha))
            if i < 3: continue
            original = self.root/'output/validation'/row['reference']; out = original.parent/name
            shutil.copytree(original,out)
            self.f.mutate(out/'summary.json',lambda v:v.update(run_name=name))
            prefix = rows[row['expected_emitted_index']+1]['name']+'/preview'
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

    def row(self,index=9):return self.f.plan['requests'][index]

    def test_complete_candidate_reconstruction_and_timing(self):
        result=self.run_gate();self.assertEqual(result['four_tensor_exact_clips'],3)
        sha=C.R.sha(self.output.read_bytes());self.assertEqual(C.verify_candidate_receipt(self.output,sha),result)
        self.make_phase('timed',sha)
        timing=C.verify_outputs(self.root,T.PLAN,self.ref,self.refsha,'timed',self.timed,self.output,sha)
        self.assertEqual(timing['four_tensor_exact_clips'],10);self.assertEqual(timing['distinct_fixtures'],3)
        self.assertEqual(timing['completion_intervals_seconds'],[1.]*9)
        self.assertNotIn('torch',sys.modules)

    def test_fill_capture_is_never_parity(self):
        folder=self.root/'output/validation'/self.row(6)['name'];folder.mkdir();(folder/'tensors.safetensors').write_bytes(b'placeholder')
        result=self.run_gate();self.assertEqual([r['parity_status'] for r in result['executions'][:3]],['not-scored-fill']*3)

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
        self.run_gate();candidate_sha=C.R.sha(self.output.read_bytes())
        self.make_phase('timed',candidate_sha)
        for row in self.f.plan['requests'][6:]:
            inputs=row['graph']['364']['inputs'];expected=ns['_job_tag'](inputs['mode'],inputs['text'])
            p=self.server/('pipeline-'+row['name']+'.json')
            detail=json.loads(p.read_text())['detail']
            self.assertEqual(detail['text_sha256'],expected);self.assertEqual(detail['tag'],expected)
            self.assertNotEqual(expected,ns['_text_sha256'](inputs['text']))
        C.verify_outputs(self.root,T.PLAN,self.ref,self.refsha,'timed',self.timed,self.output,candidate_sha)

    def test_raw_text_digest_refused_for_window_conditioning(self):
        row=self.row();wrong=C.R.sha(row['graph']['364']['inputs']['text'].encode('utf-8'))
        p=self.server/('pipeline-'+row['name']+'.json')
        self.f.mutate(p,lambda v:v['detail'].update(tag=wrong,text_sha256=wrong))
        with self.assertRaisesRegex(ValueError,'Conditioning provenance differs'):self.run_gate()
        self.assertFalse(self.output.exists())

    def test_wrong_emitted_index_and_missing_worker_marker(self):
        name=self.row()['name'];p=self.server/('pipeline-decode-'+name+'.json')
        self.f.mutate(p,lambda v:v['detail'].update(emitted_index=99901101));self.refuse()

    def test_missing_done_marker(self):
        (self.server/'pipeline-done-save-99901100.json').unlink();self.refuse()

    def test_wrong_deterministic_decode_slot_refused(self):
        self.f.mutate(self.server/'pipeline-done-decode-99901101.json',lambda v:v.update(slot='native'));self.refuse()

    def test_preview_failure_refused(self):
        self.f.mutate(self.server/'pipeline-done-save-99901100.json',lambda v:v.update(saved='save-failed:RuntimeError'));self.refuse()

    def test_coherent_tensor_change_still_rejected_by_native_bytes(self):
        folder=self.root/'output/validation'/self.row()['name'];p=folder/'tensors.safetensors'
        p.write_bytes(p.read_bytes()[:-8]+struct.pack('<ff',99.,1.))
        self.f.mutate(folder/'summary.json',lambda v:v['tensors']['waveform'].update(sha256=C.R.sha(struct.pack('<ff',99.,1.))))
        self.refuse()

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
            C.verify_outputs(self.root,T.PLAN,self.ref,self.refsha,'timed',self.timed)
        self.assertFalse(self.timed.exists())


if __name__=='__main__':unittest.main(verbosity=2)
