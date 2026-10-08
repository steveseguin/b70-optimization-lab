"""Tiny synthetic archives and receipt corruption tests; no model/Torch reads."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import proof as P

TINY={'images':[2,1,1,3],'video_latent':[1,1,1,1,1],
      'audio_latent':[1,1,1,1],'waveform':[1,1,2]}
PLAN_PATH=Path(__file__).resolve().parents[1]/'20261007-continuation111-plan/candidate-plan.json'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(json.dumps(value,sort_keys=True,indent=2).encode()+b'\n')


def archive(path,shapes=TINY,change=None):
    header={};meta={};parts=[];offset=0
    for i,(key,shape) in enumerate(shapes.items()):
        size=__import__('math').prod(shape)
        part=b''.join(struct.pack('<f',float(i+1)) for _ in range(size))
        if change and change[0]==key:part=change[1]+part[4:]
        header[key]=dict(dtype='F32',shape=shape,data_offsets=[offset,offset+len(part)])
        meta[key]=dict(dtype='torch.float32',shape=shape,sha256=P.sha(part),finite=True)
        parts.append(part);offset+=len(part)
    raw=P.canonical(header);raw+=b' '*((-len(raw))%8)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(struct.pack('<Q',len(raw))+raw+b''.join(parts))
    return meta


class Fixture:
    def __init__(self,path):
        self.root=path;self.packet=path/'packet';self.run=path/'run'
        self.packet.mkdir();self.run.mkdir()
        self.plan=json.loads(PLAN_PATH.read_text())['plan']
        write(self.packet/'resolution/candidate-plan.json',dict(plan=self.plan,plan_sha256=P.PLAN_SHA))
        sources={'source/comfy/sd.py':'class VAE:\n def encode(self): self.guard.reject_oom(self,None)\n def decode(self): self.guard.reject_oom(self,None)\n',
                 'source/comfy_extras/nodes_lt.py':'# synthetic node source\n',
                 'source/scripts/native_safety.py':'# synthetic source\n',
                 'source/scripts/conditioning_guard.py':'# synthetic guard source\n'}
        sources['source/scripts/setup_gates.py']=P.SETUP_FILE.read_text()
        for label in ('ltx_graph_capture_lab','ltx_pipeline_decode_lab'):
            sources['source/custom_nodes/'+label+'/__init__.py']='# synthetic registered source\n'
        self.manifest={'files':{}}
        for rel,raw in sources.items():
            p=self.packet/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(raw)
            self.manifest['files'][rel]=P.sha(raw.encode())
        write(self.packet/'manifest.json',self.manifest)
        self.runtime=P.sha((self.packet/'manifest.json').read_bytes())
        self.identity=dict(source_packet_manifest_sha256=self.runtime,model_verification_sha256=P.MODEL_SHA,
                           pid=123,proc_start_ticks=456,boot_id='synthetic-boot',source_commit='synthetic',
                           runtime={'synthetic':True},rope_compatibility={'synthetic':True})
        write(self.run/'server-identity.json',self.identity);self.idsha=P.sha((self.run/'server-identity.json').read_bytes())
        self.verifier=P.ProofVerifier(self.packet,self.manifest,self.runtime,self.run,self.plan,self.idsha)
        self.prepared=self.snapshot(1,P.PRE)
        admission=dict(event='preload-admission',free={c:40*2**30 for c in P.CARDS},
                       missing_tensor_bytes={c:0 for c in P.CARDS},required=P.PRE)
        write(self.run/'native-preparation.json',dict(snapshot=self.prepared,receipts=[admission,dict(event='prepared',snapshot=self.prepared)]))
        self.controller=[];self.captures=[];self.proofs={}

    def state(self,pid=None):
        return dict(sampler_routes=0,lean_state=0,decode_replicas=0,preview_pending=0,preview_failures=0,
                    fault=False,captures_frozen=False,loads_frozen=False,queue_pending=0,queue_pending_ids=[],
                    queue_running=int(pid is not None),queue_running_ids=[] if pid is None else [pid],
                    pipeline={'running':0,'stages':{'encode':{'queued_indices':[],'jobs':[]}}},
                    registered_module_paths={'graph':str(self.packet/'source/custom_nodes/ltx_graph_capture_lab/__init__.py'),
                    'decode':str(self.packet/'source/custom_nodes/ltx_pipeline_decode_lab/__init__.py')})

    def snapshot(self,time,free):
        return dict(plan_sha256=P.PLAN_SHA,runtime_sha256=self.runtime,phase='native-reference',fault=False,
                    text_graphs_captured=True,window_qualified=True,sampler_routes=0,decoder_replicas=0,
                    physical_free_bytes=dict(free),timestamp_ns=time,
                    residence={r:dict(object_id=i+1,device=c,dtype='torch.bfloat16',fully_resident=True,
                                      ownership_sha256=str(i+1)*64) for i,(r,c) in enumerate(P.ROLES.items())},
                    peaks={c:dict(allocated=1,reserved=2,peak=1) for c in P.CARDS})

    def common(self,row,pid):
        return dict(plan_sha256=P.PLAN_SHA,runtime_manifest_sha256=self.runtime,
                    server_identity_sha256=self.idsha,name=row['name'],prompt_id=pid)

    def memory(self,name,event,free,time):
        return dict(request_id=name,event=event,required_physical_free_bytes=free,
                    snapshot=self.snapshot(time,free),admitted=True,allowances_are_not_peak_bounds=True)

    def create(self,index):
        row=self.plan['requests'][index];name=row['name'];pid='pid-'+str(index);start=1000+index*100;end=start+50
        common=self.common(row,pid);path=self.root/'requests'/name
        messages=[['execution_start',dict(prompt_id=pid,timestamp=start)],['execution_success',dict(prompt_id=pid,timestamp=end)]]
        status=dict(status_str='success',completed=True,messages=messages)
        for filename,obj in [('prompt.json',row['graph']),('submission.json',dict(prompt_id=pid,number=index,node_errors={})),
                             ('history.json',dict(prompt=[index,pid,row['graph']],status=status)),
                             ('result.json',dict(name=name,prompt_id=pid,status=status)),('identity.json',self.identity)]:write(path/filename,obj)
        nodes=['470'] if index==0 else ['490'] if index==1 else ['364','344','348','368','374','358','414']
        if row.get('chunk_index'):nodes=['364','continuation111_anchor','anchor_stage_a','344','348','anchor_stage_b','368','374','358','414']
        events=[dict(type='execution_start',seconds=0,data=messages[0][1])]
        events += [dict(type='executing',seconds=(i+1)*.01,data=dict(prompt_id=pid,node=n)) for i,n in enumerate(nodes)]
        events += [dict(type='execution_success',seconds=1,data=messages[1][1])]
        (path/'events.jsonl').write_bytes(b'\n'.join(P.canonical(x) for x in events)+b'\n')
        for side in ('before','after'):write(self.run/f'resolution-{side}-{name}.json',dict(**common,phase='native_reference',qualification_id=P.QID,state=self.state(pid)))
        write(self.run/f'continuation-observation-{name}.json',dict(**common,state=self.state(),native_snapshot=None if index==0 else self.snapshot(end*10+3,P.POST)))
        if index==0:
            prompts=['fixture-boat','fixture-marble','fixture-bird']+['other'+str(i) for i in range(37)]
            rows=[dict(prompt=p,window=64,finite=True,full_identical_across_workers=True,window_sha256=['a'*64]*4,
                       full_sha256=['b'*64]*2,mean_rel=0,max_abs_in_bf16_steps=0,differing_fraction=0) for p in prompts]
            report=dict(run_name=name,server_identity_sha256=self.idsha,model_verification_sha256=P.MODEL_SHA,
                        output_size='640x384',frame_count=49,schema='ltx.text-window-probe.v1',passed=True,
                        outcome='window-qualified',pending_encode_at_start=[],worker_errors=[],reasons=[],
                        workers=['ltx-encode-0','ltx-encode-1'],admitted=[64],prompt_count=40,rows=rows,
                        capture={k:dict(captured=48,error=None) for k in ['w0/64','w1/64']})
            write(self.run/f'text-window-probe-{name}.json',report)
        if index<2:return
        for event,minimum,clock in [('before',P.PRE,start*10),('after',P.POST,end*10+1)]:
            value=self.memory(name,event,minimum,clock);self.controller.append(value)
            write(self.run/f'native-memory-{event}-{name}.json',value)
        text=P.sha(('pipeline-window\n'+row['graph']['364']['inputs']['text']).encode())
        write(self.run/f'pipeline-{name}.json',dict(passed=True,run_name=name,clip_index=row['clip_index'],depth=2,
            mode='pipeline-window',server_identity_sha256=self.idsha,model_verification_sha256=P.MODEL_SHA,
            output_size='640x384',frame_count=49,speed_only=False,
            detail=dict(text_sha256=text,tag=text,started_ahead=[],pending_after=[],speculation_miss=False,
                        window_encode=dict(window=64,clip_index=row['clip_index']),conditioning_fingerprint='a'*64)))
        output=self.root/'output/validation'/name
        meta=archive(output/'tensors.safetensors')
        write(output/'summary.json',dict(run_name=name,sample_rate=48000,deterministic_enabled=True,deterministic_warn_only=False,tensors=meta))
        self.captures.append(dict(name=name,prompt_id=pid,graph_sha256=row['graph_sha256'],role='full',actual_shape_kind='full',charged_bytes=P.MAX_CAPTURE,file_bound=P.MAX_CAPTURE))
        write(self.run/f'capture-checkpoint-{name}.json',dict(**common,prewrite=dict(failed=None,plan_sha256=P.PLAN_SHA,
            capture_cap=6,captures_reserved=len(self.captures),raw_budget_bytes=6*P.MAX_CAPTURE,
            reserved_bytes=len(self.captures)*P.MAX_CAPTURE,captures=copy.deepcopy(self.captures))))
        if row['chunk_index']:
            pred=row['predecessor_capture'];binding=self.proofs[pred]['anchor_binding'];anchor_meta=dict(object_id=100,storage_id=100,shape=[1,384,640,3],dtype='torch.float32',device='cpu',contiguous=True)
            write(self.run/f'provider-receipt-{name}.json',dict(**common,binding=binding,anchor_metadata=anchor_meta,
                calls=1,predecessor_name=pred,predecessor_proof_sha256=P.sha((self.run/f'continuation-proof-{pred}.json').read_bytes()),current_graph_sha256=row['graph_sha256']))
            receipts=[dict(event='begin',request_id=name,anchor_sha256=binding['anchor_sha256'],plan_sha256=P.PLAN_SHA,runtime_sha256=self.runtime,thread_ident=200)]
            for ordinal,stage in enumerate(('A','B')):
                shape=self.plan['numerical_contract']['mandatory_runtime_policy']['stage_'+stage+'_latent_shape']
                metadata=lambda ident,shape:dict(object_id=ident,storage_id=ident,shape=shape,dtype='torch.float32',device='cpu',contiguous=True)
                cache=dict(source_sha256='42010d800e6e49bdc69ae24587910b55b2418e26a1140bec7159a873276c45c2',thread_ident=200,encoder_id=300,entry_count=0,foreign_entry_count=0)
                before=self.memory(name,'conditioning-'+stage+'-before',P.PRE,start*10+1+ordinal*100)
                after=self.memory(name,'conditioning-'+stage+'-after',P.POST,start*10+90+ordinal*100)
                lo=len(self.controller);self.controller.extend([before,after])
                receipts.append(dict(event='stage',request_id=name,stage=stage,completed=True,anchor_sha256=binding['anchor_sha256'],
                    input=metadata(101,shape),output=metadata(102,shape),noise_mask=metadata(103,[1,1,7,1,1]),
                    cache_before=cache,cache_after_before_snapshot=cache,cache_after=cache,cache_after_after_snapshot=cache,
                    before=before,after=after,controller_receipt_start=lo,controller_receipt_end=lo+2))
                height,width=shape[-2]*32,shape[-1]*32
                receipts[-1]['source_derived_encode_expectation']=dict(
                    conditioning_node_sha256='09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243',
                    vae_source_before_encode_safety_delta_sha256='d1c63b66a6d0cf467ecb084d7ec5fb73d20b0fac43181668124a8ded06aa7604',
                    expected_input_shape=[1,3,1,height,width],workspace_estimate_bytes=80*7*height*width*2,
                    estimate_formula='80 * max(T,7) * H * W * BF16_bytes',internal_pixels_observed=False,
                    measured_peak=False,loader_checks_required_unchanged=True)
            receipts.append(dict(event='finish',request_id=name))
            write(self.run/f'conditioning-receipt-{name}.json',dict(**common,guard_receipts=receipts,
                controller_receipts=self.controller,failed=None,native_call_binding=dict(method='LTXVImgToVideoInplace.execute',
                sources={str(self.packet/k):v for k,v in self.manifest['files'].items()}),
                runtime_policy=self.plan['numerical_contract']['mandatory_runtime_policy']))

    def build_prefix(self,count=8):
        for i in range(count):
            self.create(i);name=self.plan['requests'][i]['name'];receipt=self.verifier.produce(name)
            self.proofs[name]=receipt;write(self.run/f'continuation-proof-{name}.json',receipt)


class ParserTests(unittest.TestCase):
    def test_tiny_complete_inventory_and_exact_anchor_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';meta=archive(p);cap,anchor=P.scan_capture(p,meta,shapes=TINY,frame_index=1)
            self.assertEqual(cap['sha256'],P.sha(p.read_bytes()))
            self.assertEqual(anchor['anchor_sha256'],P.sha(struct.pack('<fff',1,1,1)))
            self.assertEqual(set(cap['tensors']),set(TINY))

    def test_nonfinite_last_tensor_and_coherent_bad_metadata_refused(self):
        for bad in (struct.pack('<I',0x7f800000),struct.pack('<I',0x7fc00001)):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'x';meta=archive(p,change=('waveform',bad))
                with self.assertRaisesRegex(ValueError,'Nonfinite'):P.scan_capture(p,meta,shapes=TINY,frame_index=1)

    def test_metadata_hash_shape_and_dtype_drift(self):
        for key,value in [('sha256','0'*64),('shape',[9]),('dtype','torch.bfloat16')]:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'x';meta=archive(p);meta['waveform'][key]=value
                with self.assertRaises(ValueError):P.scan_capture(p,meta,shapes=TINY,frame_index=1)

    def test_duplicate_json_and_trailing_payload(self):
        with self.assertRaises(ValueError):P.strict_json(b'{"a":1,"a":2}')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';meta=archive(p)
            with p.open('ab') as f:f.write(b'xxxx')
            with self.assertRaises(ValueError):P.scan_capture(p,meta,shapes=TINY,frame_index=1)

    def test_symlink_and_hardlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';meta=archive(p);link=Path(d)/'link';link.symlink_to(p)
            with self.assertRaises(ValueError):P.scan_capture(link,meta,shapes=TINY,frame_index=1)
            link.unlink();__import__('os').link(p,link)
            with self.assertRaises(ValueError):P.scan_capture(p,meta,shapes=TINY,frame_index=1)

    def test_overlap_wrong_header_dtype_and_truncation(self):
        for defect in ('overlap','dtype','truncate'):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d)/'x';meta=archive(p);raw=p.read_bytes();size=struct.unpack('<Q',raw[:8])[0]
                if defect=='truncate':p.write_bytes(raw[:-1])
                else:
                    header=P.strict_json(raw[8:8+size])
                    if defect=='overlap':header['waveform']['data_offsets'][0]-=4
                    else:header['waveform']['dtype']='BF16'
                    changed=P.canonical(header);changed+=b' '*((-len(changed))%8)
                    p.write_bytes(struct.pack('<Q',len(changed))+changed+raw[8+size:])
                with self.assertRaises(ValueError):P.scan_capture(p,meta,shapes=TINY,frame_index=1)


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.shape=patch.object(P,'SHAPES',TINY);self.frame=patch.object(P,'FRAME_INDEX',1)
        self.shape.start();self.frame.start();self.addCleanup(self.shape.stop);self.addCleanup(self.frame.stop)
        self.f=Fixture(Path(self.temp.name))

    def mutate(self,path,fn):
        base=self.f.root if str(path).startswith(('requests/','output/')) else self.f.run
        p=base/path;v=json.loads(p.read_text());fn(v);write(p,v)

    def test_full_eight_prefix_reconstructs_replay_and_actual_context(self):
        self.f.build_prefix();name=self.f.plan['requests'][-1]['name'];p=self.f.run/f'continuation-proof-{name}.json'
        receipt=self.f.verifier.verify(name,p,P.sha(p.read_bytes()))
        self.assertIs(receipt['verified'],True);self.assertEqual(receipt['replay_reference'],'continuation111-pass0-chunk2')
        anchor=self.f.proofs['continuation111-pass1-chunk1']['anchor_binding']
        self.assertEqual(anchor['context']['plan_sha256'],P.PLAN_SHA)
        self.assertEqual(anchor['context']['runtime_manifest_sha256'],self.f.runtime)
        self.assertEqual(anchor['context']['pass_index'],1)
        self.assertNotIn('torch',sys.modules)

    def test_request_and_capture_root_is_parent_of_server_run(self):
        self.f.build_prefix(3);name=self.f.plan['requests'][2]['name']
        receipt=self.f.proofs[name]
        self.assertEqual(receipt['capture']['path'],str(self.f.root/'output/validation'/name/'tensors.safetensors'))
        actual=self.f.root/'requests'/name
        wrong=self.f.run/'requests'/name
        wrong.parent.mkdir();actual.rename(wrong)
        with self.assertRaises(FileNotFoundError):self.f.verifier.produce(name)
        wrong.rename(actual)
        actual_capture=self.f.root/'output/validation'/name
        wrong_capture=self.f.run/'output/validation'/name
        wrong_capture.parent.mkdir(parents=True);actual_capture.rename(wrong_capture)
        with self.assertRaises(FileNotFoundError):self.f.verifier.produce(name)

    def test_wrong_digest_and_changed_source_refused(self):
        self.f.build_prefix(1);name=self.f.plan['requests'][0]['name'];p=self.f.run/f'continuation-proof-{name}.json'
        with self.assertRaisesRegex(ValueError,'SHA'):self.f.verifier.verify(name,p,'0'*64)
        (self.f.packet/'source/comfy/sd.py').write_text('# changed')
        with self.assertRaisesRegex(ValueError,'Source closure'):self.f.verifier.produce(name)

    def test_prior_stored_boolean_cannot_substitute_fresh_reconstruction(self):
        self.f.build_prefix(3);name=self.f.plan['requests'][2]['name']
        self.mutate(f'continuation-observation-{name}.json',lambda d:d['state'].update(fault=True))
        with self.assertRaises(ValueError):self.f.verifier.produce(name)

    def test_cached_history_even_with_success_refused(self):
        self.f.create(0);name=self.f.plan['requests'][0]['name']
        self.mutate(f'requests/{name}/history.json',lambda d:d['status']['messages'].insert(1,['execution_cached',dict(prompt_id='pid-0',nodes=['470'])]))
        with self.assertRaises(ValueError):self.f.verifier.produce(name)

    def test_missing_genuine_last_capture_event(self):
        self.f.build_prefix(2);self.f.create(2);name=self.f.plan['requests'][2]['name'];p=self.f.root/f'requests/{name}/events.jsonl'
        events=[P.strict_json(x) for x in p.read_bytes().splitlines()]
        p.write_bytes(b'\n'.join(P.canonical(x) for x in events if x['data'].get('node')!='414'))
        with self.assertRaisesRegex(ValueError,'node event'):self.f.verifier.produce(name)

    def test_post_memory_and_owner_drift(self):
        self.f.build_prefix(2);self.f.create(2);name=self.f.plan['requests'][2]['name']
        self.mutate(f'native-memory-after-{name}.json',lambda d:d['snapshot']['physical_free_bytes'].update({'xpu:3':1}))
        with self.assertRaisesRegex(ValueError,'memory floor'):self.f.verifier.produce(name)

    def test_capture_prefix_extra_or_wrong_prompt_refused(self):
        self.f.build_prefix(2);self.f.create(2);name=self.f.plan['requests'][2]['name']
        self.mutate(f'capture-checkpoint-{name}.json',lambda d:d['prewrite']['captures'][0].update(prompt_id='wrong'))
        with self.assertRaisesRegex(ValueError,'Capture authority'):self.f.verifier.produce(name)

    def test_wrong_same_pass_predecessor_and_stage_cache_refused(self):
        self.f.build_prefix(3);self.f.create(3);name=self.f.plan['requests'][3]['name']
        path=f'provider-receipt-{name}.json';original=(self.f.run/path).read_bytes()
        self.mutate(path,lambda d:d['binding']['context'].update(pass_index=1))
        with self.assertRaisesRegex(ValueError,'Provider predecessor'):self.f.verifier.produce(name)
        (self.f.run/path).write_bytes(original)
        self.mutate(f'conditioning-receipt-{name}.json',lambda d:d['guard_receipts'][1]['cache_after_after_snapshot'].update(entry_count=1))
        with self.assertRaisesRegex(ValueError,'cache'):self.f.verifier.produce(name)

    def test_replay_last_chunk_fourth_tensor_coherent_change_refused(self):
        self.f.build_prefix(7);self.f.create(7);name=self.f.plan['requests'][7]['name'];p=self.f.root/'output/validation'/name
        meta=archive(p/'tensors.safetensors',change=('waveform',struct.pack('<f',99)))
        self.mutate(f'output/validation/{name}/summary.json',lambda d:d.update(tensors=meta))
        with self.assertRaisesRegex(ValueError,'replay differs'):self.f.verifier.produce(name)

    def test_global_fault_file_halts_reconstruction(self):
        self.f.build_prefix(1);(self.f.run/'FAULT.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Fault'):self.f.verifier.produce(self.f.plan['requests'][0]['name'])

    def test_exact_plan_file_required_not_only_constructor_argument(self):
        self.f.create(0)
        p=self.f.packet/'resolution/candidate-plan.json';value=json.loads(p.read_text())
        value['plan']['budget']['max_attempts']=9;write(p,value)
        with self.assertRaisesRegex(ValueError,'Packet plan'):self.f.verifier.produce(self.f.plan['requests'][0]['name'])

    def test_observed_registered_source_and_idle_queue(self):
        for defect in ('owner','pending','bool'):
            with self.subTest(defect=defect):
                self.f.create(0);name=self.f.plan['requests'][0]['name']
                def mutate(d):
                    if defect=='owner':d['state']['registered_module_paths']['graph']='/tmp/other.py'
                    elif defect=='pending':d['state']['pipeline']['stages']['encode']['jobs']=[{'done':True}]
                    else:d['state']['queue_pending']=False
                self.mutate(f'continuation-observation-{name}.json',mutate)
                with self.assertRaises(ValueError):self.f.verifier.produce(name)

    def test_conditioning_corruption_order_range_policy_and_cache_owner(self):
        self.f.build_prefix(3);self.f.create(3);name=self.f.plan['requests'][3]['name'];path=self.f.run/f'conditioning-receipt-{name}.json'
        original=path.read_bytes()
        for defect in ('order','range','policy','encoder','complete','alias'):
            path.write_bytes(original)
            def mutate(d):
                first,last=d['guard_receipts'][1:3]
                if defect=='order':last['stage']='A'
                if defect=='range':first['controller_receipt_end']-=1
                if defect=='policy':d['runtime_policy']['after_each_conditioning_stage_floor_gib']=1
                if defect=='encoder':last['cache_after_after_snapshot']['encoder_id']+=1
                if defect=='complete':first['completed']=False
                if defect=='alias':first['output']['storage_id']=first['input']['storage_id']
            self.mutate(path.relative_to(self.f.run),mutate)
            with self.subTest(defect=defect),self.assertRaises(ValueError):self.f.verifier.produce(name)

    def test_native_owner_fingerprint_drift(self):
        self.f.build_prefix(2);self.f.create(2);name=self.f.plan['requests'][2]['name']
        self.mutate(f'native-memory-after-{name}.json',lambda d:d['snapshot']['residence']['video_vae'].update(ownership_sha256='e'*64))
        with self.assertRaisesRegex(ValueError,'fingerprint'):self.f.verifier.produce(name)

    def test_capture_changed_at_final_recheck(self):
        self.f.build_prefix(2);self.f.create(2);name=self.f.plan['requests'][2]['name']
        with patch.object(P,'stream_hash',return_value='0'*64),self.assertRaisesRegex(ValueError,'before proof'):
            self.f.verifier.produce(name)

    def test_duplicate_prompt_coherently_rebound_artifacts_refused(self):
        self.f.build_prefix(2);self.f.create(2);name=self.f.plan['requests'][2]['name']
        files=list((self.f.root/'requests'/name).glob('*'))
        files += [self.f.run/f'{prefix}-{name}.json' for prefix in ['resolution-before','resolution-after',
                  'continuation-observation','capture-checkpoint']]
        for path in files:path.write_bytes(path.read_bytes().replace(b'pid-2',b'pid-1'))
        with self.assertRaisesRegex(ValueError,'Duplicate prompt'):self.f.verifier.produce(name)


if __name__=='__main__':unittest.main()
