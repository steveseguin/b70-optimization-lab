"""Bounded CPU native111 proof reconstruction; no writes or live runtime queries.

ProofVerifier(packet, manifest, manifest_sha, run, plan, identity_sha).produce(name)
returns a receipt for exclusive writing to continuation-proof-NAME.json; verify
(name,path,sha) reconstructs it, including every prior immutable prefix proof.
Both set verified=True only on success. plan is the frozen inner plan dictionary.

Artifact root is run.parent. Requests and output/validation below are relative
to that root; all other runtime receipts/proofs below are relative to run.
Inputs: requests/NAME/{prompt,submission,history,result,identity}.json/events.jsonl;
resolution-before/after-NAME.json; continuation-observation-NAME.json (common
identity fields plus state/native_snapshot); native-memory-before/after-NAME.json;
native-preparation.json; pipeline-NAME.json; output/validation/NAME/{summary.json,
tensors.safetensors}; capture-checkpoint-NAME.json (common+prewrite); conditioned
provider-receipt-NAME.json (common+binding/anchor_metadata/calls=1/predecessor_name/
predecessor_proof_sha256/current_graph_sha256), conditioning-receipt-NAME.json
(common+guard_receipts filtered to request/controller_receipts full array/failed
None/native_call_binding/runtime_policy). Native call binding has method and
sources{absolute_path:sha}; policy has actual mandatory_runtime_policy values.
Window uses existing text-window-probe-NAME.json and sealed110 setup validator.
No mutable latest-status/client-state artifact is a reconstruction dependency.
"""
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct

PLAN_SHA = '7944f8701244bd386c41bc5cdd6c4e9df1ea8fcf4d9dedf91e249f476105b2c5'
QID = '705fa3d73c603833591ac5ae13b5f2d4d79c329b860794ff4d061c71e8942266'
MODEL_SHA = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
SETUP_FILE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-duration-full-110/resolution/components/setup_gates.py')
SETUP_SHA = '000c806bd2fa771d3260f2d06a3fc9c229dcde7c59ac99ff0ece15a55407f43a'
SHAPES = {'images':[49,384,640,3], 'video_latent':[1,128,7,12,20],
          'audio_latent':[1,8,51,16], 'waveform':[1,2,96480]}
FRAME_INDEX = 48
BLOCK = 1024*1024
MAX_META = 8*BLOCK
MAX_CAPTURE = 146230536
CARDS = ('xpu:0','xpu:1','xpu:2','xpu:3')
PRE = dict(zip(CARDS, (8*2**30,8*2**30,2*2**30,9*2**30)))
POST = dict.fromkeys(CARDS, 2*2**30)
ROLES = dict(zip(('sampler_primary','sampler_secondary','upsampler','text_primary',
                 'text_secondary','video_vae','audio_vae'),
                ('xpu:0','xpu:1','xpu:0','xpu:2','xpu:3','xpu:3','xpu:3')))


def require(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}',value), 'Invalid digest')
    return value


def strict_json(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            require(k not in out,'Duplicate JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,
                      parse_constant=lambda _:require(False,'Nonfinite JSON'))


def safe_path(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts and
            not any(x.is_symlink() for x in (p,*p.parents)), 'Unsafe evidence path')
    return p


def file_identity(s):
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink]


def open_regular(path, cap):
    path=safe_path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=cap,
                'Nonregular, linked or oversized evidence')
        return os.fdopen(fd,'rb',buffering=0),info
    except BaseException:
        os.close(fd);raise


def unchanged(path, stream, before):
    require(file_identity(before)==file_identity(os.fstat(stream.fileno()))==
            file_identity(safe_path(path).lstat()),'Evidence changed while reading')


def read_regular(path):
    stream,before=open_regular(path,MAX_META)
    with stream:
        raw=stream.read(MAX_META+1)
        require(len(raw)==before.st_size,'Incomplete metadata')
        unchanged(path,stream,before)
    return raw


def stream_hash(path,cap=MAX_CAPTURE):
    stream,before=open_regular(path,cap);h=hashlib.sha256()
    with stream:
        while True:
            b=stream.read(BLOCK)
            if not b:break
            h.update(b)
        unchanged(path,stream,before)
    return h.hexdigest()


def scan_capture(path,metadata,*,shapes=None,frame_index=None):
    """Private shape seam supports tiny synthetic parser tests; production is fixed."""
    shapes=SHAPES if shapes is None else shapes
    frame_index=FRAME_INDEX if frame_index is None else frame_index
    stream,before=open_regular(path,MAX_CAPTURE)
    with stream:
        prefix=stream.read(8);require(len(prefix)==8,'Truncated archive')
        count=struct.unpack('<Q',prefix)[0]
        require(0<count<=65536 and count%8==0 and count+8<=before.st_size,'Invalid header length')
        raw=stream.read(count);require(len(raw)==count,'Truncated header')
        header=strict_json(raw)
        require(type(header) is dict and set(header)==set(metadata)==set(shapes),'Four tensors required')
        ordered=[]
        for key,shape in shapes.items():
            row=header[key]
            require(type(row) is dict and set(row)=={'dtype','shape','data_offsets'} and
                    row['dtype']=='F32' and row['shape']==shape and
                    all(type(x) is int for x in row['shape']), 'Tensor shape/dtype differs')
            off=row['data_offsets'];require(type(off) is list and len(off)==2 and
                all(type(x) is int for x in off),'Invalid tensor offsets')
            require(off[1]-off[0]==math.prod(shape)*4,'Tensor byte length differs')
            ordered.append((off[0],off[1],key))
        whole=hashlib.sha256(prefix+raw);cursor=0;inventory={};anchor=hashlib.sha256()
        require(type(frame_index) is int and 0<=frame_index<shapes['images'][0],'Invalid anchor frame')
        frame_bytes=math.prod(shapes['images'][1:])*4
        for start,end,key in sorted(ordered):
            require(start==cursor and end<=before.st_size-8-count,'Tensor gap/overlap/range')
            h=hashlib.sha256();position=0
            while position<end-start:
                b=stream.read(min(BLOCK,end-start-position))
                require(b and len(b)%4==0,'Truncated F32 payload')
                require(all(word&0x7f800000!=0x7f800000 for (word,) in struct.iter_unpack('<I',b)),
                        'Nonfinite tensor bytes')
                whole.update(b);h.update(b)
                if key=='images':
                    lo=max(position,frame_index*frame_bytes);hi=min(position+len(b),(frame_index+1)*frame_bytes)
                    if lo<hi:anchor.update(b[lo-position:hi-position])
                position+=len(b)
            item=dict(dtype='torch.float32',shape=shapes[key],sha256=h.hexdigest(),finite=True)
            require(all(metadata[key].get(k)==v for k,v in item.items()),'Metadata differs from tensor bytes')
            inventory[key]=item;cursor=end
        require(cursor==before.st_size-8-count and not stream.read(1),'Unclaimed archive bytes')
        unchanged(path,stream,before)
    return dict(path=str(path),sha256=whole.hexdigest(),tensors=inventory),dict(
        capture_path=str(path),capture_sha256=whole.hexdigest(),anchor_sha256=anchor.hexdigest(),
        frame_index=frame_index,shape=[1,*shapes['images'][1:]],dtype='F32',byte_order='little',
        byte_length=frame_bytes,source_file_identity=file_identity(before),header_sha256=sha(raw),
        whole_capture_hash_verified=True,anchor_finite_verified=True,
        other_tensor_finiteness_verified=False,transformation='none')


class Evidence:
    def __init__(self): self.hashes={};self.captures=set()
    def raw(self,path):
        raw=read_regular(path);self.bind(path,sha(raw));return raw
    def bind(self,path,value):
        key=str(path);require(key not in self.hashes or self.hashes[key]==value,'Evidence changed')
        self.hashes[key]=value
    def json(self,path):return strict_json(self.raw(path))
    def recheck(self):
        for p,h in self.hashes.items():
            require((stream_hash(p) if p in self.captures else sha(read_regular(p)))==h,
                    'Evidence changed before proof')


class ProofVerifier:
    def __init__(self,packet,manifest,manifest_sha,run,plan,identity_sha):
        self.packet=safe_path(packet);self.run=safe_path(run);self.root=self.run.parent
        self.manifest=copy.deepcopy(manifest);self.manifest_sha=digest(manifest_sha)
        self.plan=copy.deepcopy(plan);self.identity_sha=digest(identity_sha)
        require(sha(canonical(plan))==PLAN_SHA and plan['qualification_id']==QID and
                len(plan['requests'])==8,'Unreviewed111 plan')
        self.rows={r['name']:r for r in plan['requests']}
        require(len(self.rows)==8,'Duplicate plan requests')

    def common(self,value,row,pid):
        require(all(value.get(k)==v for k,v in dict(plan_sha256=PLAN_SHA,
            runtime_manifest_sha256=self.manifest_sha,server_identity_sha256=self.identity_sha,
            name=row['name'],prompt_id=pid).items()),'Receipt identity differs')

    def fault_check(self):
        for p in (self.run/'FAULT.json',self.run.parent/'FAULT.json',self.run/'resolution-halt.json',
                  self.run/'continuation-halt.json'):
            require(not p.exists(),'Fault or halt present')

    def source(self,e,path,expected=None):
        path=safe_path(path)
        require(path.is_relative_to(self.packet),'Source outside sealed packet')
        rel=str(path.relative_to(self.packet));pin=self.manifest['files'].get(rel)
        require(pin is not None and (expected is None or pin==expected),'Unbound source')
        raw=e.raw(path);require(sha(raw)==pin,'Source closure differs');return raw

    def state(self,value,pid=None):
        for k in ('sampler_routes','lean_state','decode_replicas','preview_pending','preview_failures'):
            require(type(value.get(k)) is int and value[k]==0,'Optimized/pending state present')
        require(value.get('fault') is False and value.get('captures_frozen') is False and
                value.get('loads_frozen') is False,'Fault/frozen state differs')
        require(type(value.get('queue_pending')) is int and value['queue_pending']==0 and
                value.get('queue_pending_ids')==[],'Pending requests')
        expected=[] if pid is None else [pid]
        require(type(value.get('queue_running')) is int and value['queue_running']==len(expected) and
                value['queue_running_ids']==expected,'Queue identity differs')
        pipe=value['pipeline'];require(type(pipe['running']) is int and pipe['running']==0,'Pipeline running')
        for stage in pipe['stages'].values():
            require(stage['queued_indices']==[] and stage['jobs']==[],'Pipeline jobs remain')
        paths=value['registered_module_paths']
        require(paths=={'graph':str(self.packet/'source/custom_nodes/ltx_graph_capture_lab/__init__.py'),
                        'decode':str(self.packet/'source/custom_nodes/ltx_pipeline_decode_lab/__init__.py')},
                'Observed registered node source changed')

    def snapshot(self,snap,minimum,baseline=None):
        require(snap.get('plan_sha256')==PLAN_SHA and snap.get('runtime_sha256')==self.manifest_sha and
                snap.get('phase')=='native-reference' and snap.get('fault') is False and
                snap.get('text_graphs_captured') is True and snap.get('window_qualified') is True,
                'Native snapshot identity/readiness differs')
        require(all(type(snap.get(k)) is int and snap[k]==0 for k in ('sampler_routes','decoder_replicas')),
                'Optimized native state')
        free=snap['physical_free_bytes'];require(set(free)==set(CARDS) and
            all(type(free[k]) is int and free[k]>=minimum[k] for k in CARDS),'Native memory floor')
        require(type(snap.get('timestamp_ns')) is int and snap['timestamp_ns']>0,'Native clock missing')
        residence=snap['residence'];require(set(residence)==set(ROLES),'Native owners incomplete')
        for role,device in ROLES.items():
            r=residence[role];require(r['device']==device and r['dtype']=='torch.bfloat16' and
                r['fully_resident'] is True and type(r['object_id']) is int and r['object_id']>0,
                'Native owner/dtype/residence changed');digest(r['ownership_sha256'])
        require(len({x['object_id'] for x in residence.values()})==len(ROLES),'Aliased native owners')
        if baseline is not None:require(residence==baseline['residence'],'Native owner fingerprint changed')
        require(set(snap['peaks'])==set(CARDS),'Missing allocator observations')
        for row in snap['peaks'].values():
            require(set(row)=={'allocated','reserved','peak'} and all(type(v) is int and v>=0 for v in row.values())
                    and row['reserved']>=row['allocated'] and row['peak']>=row['allocated'],'Invalid peak counters')

    def memory(self,value,name,event,minimum,baseline):
        require(value.get('request_id')==name and value.get('event')==event and
                value.get('admitted') is True and value.get('required_physical_free_bytes')==minimum and
                value.get('allowances_are_not_peak_bounds') is True,'Native admission receipt differs')
        self.snapshot(value['snapshot'],minimum,baseline)

    def execution(self,e,row,identity,previous_end):
        p=self.root/'requests'/row['name'];graph=e.json(p/'prompt.json')
        require(graph==row['graph'] and sha(canonical(graph))==row['graph_sha256'],'Submitted graph changed')
        sub=e.json(p/'submission.json');hist=e.json(p/'history.json');result=e.json(p/'result.json');pid=sub['prompt_id']
        require(type(pid) is str and pid and not sub.get('node_errors'),'Failed submission')
        require(hist['prompt'][1]==result['prompt_id']==pid and hist['prompt'][2]==graph and
                hist['prompt'][0]==sub['number'] and result['name']==row['name'],'History identity differs')
        status=hist['status'];require(result['status']==status and status['status_str']=='success' and
                status['completed'] is True,'Incomplete execution')
        msgs=status['messages'];require(all(m[1].get('prompt_id')==pid for m in msgs),'History prompt differs')
        require(not any(m[0] in ('execution_error','execution_interrupted') or
                        m[0]=='execution_cached' and m[1].get('nodes') for m in msgs),'Failed/cached history')
        starts=[m[1]['timestamp'] for m in msgs if m[0]=='execution_start'];ends=[m[1]['timestamp'] for m in msgs if m[0]=='execution_success']
        require(len(starts)==len(ends)==1 and all(type(x) is int for x in starts+ends) and
                previous_end<=starts[0]<ends[0],'Execution order/clock differs')
        events=[strict_json(x) for x in e.raw(p/'events.jsonl').splitlines()]
        require(events and all(x['data'].get('prompt_id')==pid for x in events),'Event prompt differs')
        require(all(type(x.get('seconds')) in (int,float) and math.isfinite(x['seconds']) and x['seconds']>=0 for x in events)
                and all(a['seconds']<=b['seconds'] for a,b in zip(events,events[1:])),'Event clock invalid')
        require(events[-1]['type']=='execution_success' and not any(x['type'] in ('execution_error','execution_interrupted')
                or x['type']=='execution_cached' and x['data'].get('nodes') for x in events),'Failed/cached events')
        for kind,expected in [('execution_start',starts),('execution_success',ends)]:
            require([x['data'].get('timestamp') for x in events if x['type']==kind]==expected,'Event/history clock mismatch')
        nodes=[x['data'].get('node') for x in events if x['type']=='executing']
        required={'470'} if row['kind']=='window-probe' else {'490'} if row['kind']=='prepare-native' else {'364','344','348','368','374','358','414'}
        if row.get('chunk_index'):required|={'continuation111_anchor','anchor_stage_a','anchor_stage_b'}
        require(required<=set(nodes) and all(nodes.count(n)==1 for n in required),'Missing/duplicate genuine node event')
        if row['kind']=='native-chunk':
            chains=[['364','344','348','368','374','414'],['368','358','414']]
            if row['chunk_index']:chains += [['continuation111_anchor','anchor_stage_a','344'],['348','anchor_stage_b','368']]
            require(all(all(nodes.index(a)<nodes.index(b) for a,b in zip(chain,chain[1:])) for chain in chains),'Node execution order differs')
        require(e.json(p/'identity.json')==identity,'Request source/process identity changed')
        for side in ('before','after'):
            value=e.json(self.run/('resolution-'+side+'-'+row['name']+'.json'));self.common(value,row,pid)
            require(value['phase']=='native_reference' and value['qualification_id']==QID,'Authority phase differs')
            self.state(value['state'],pid)
        obs=e.json(self.run/('continuation-observation-'+row['name']+'.json'));self.common(obs,row,pid);self.state(obs['state'])
        return pid,starts[0],ends[0],obs

    def conditioning(self,e,row,pid,predecessor,baseline):
        name=row['name'];provider=e.json(self.run/('provider-receipt-'+name+'.json'));self.common(provider,row,pid)
        require(provider['calls']==1 and type(provider['calls']) is int and
                provider['binding']==predecessor['anchor_binding'] and
                provider['predecessor_name']==row['predecessor_capture'] and
                provider['predecessor_proof_sha256']==e.hashes[str(self.run/('continuation-proof-'+row['predecessor_capture']+'.json'))] and
                provider['current_graph_sha256']==row['graph_sha256'],'Provider predecessor/context differs')
        anchor=provider['anchor_metadata'];require(anchor['shape']==[1,384,640,3] and
            anchor['dtype']=='torch.float32' and anchor['device']=='cpu' and anchor['contiguous'] is True,
            'Provider IMAGE metadata differs')
        for k in ('object_id','storage_id'):require(type(anchor[k]) is int and anchor[k]>0,'Provider ownership missing')
        value=e.json(self.run/('conditioning-receipt-'+name+'.json'));self.common(value,row,pid)
        require(value['failed'] is None,'Conditioning failed')
        binding=value['native_call_binding'];require(binding['method']=='LTXVImgToVideoInplace.execute','Wrong native conditioning method')
        require(type(binding['sources']) is dict and binding['sources'],'Missing native method source closure')
        suffixes=set()
        for path,pin in binding['sources'].items():
            raw=self.source(e,path,digest(pin));suffixes.add(Path(path).name)
            if path.endswith('/comfy/sd.py'):
                tree=ast.parse(raw);vae=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='VAE')
                for method in ('encode','decode'):
                    fn=next(n for n in vae.body if isinstance(n,ast.FunctionDef) and n.name==method)
                    require(sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='reject_oom'
                                for n in ast.walk(fn))==1,'Missing encode/decode OOM refusal')
        require({'nodes_lt.py','sd.py','native_safety.py'}<=suffixes and any('conditioning_guard' in x for x in suffixes),
                'Native call safety sources incomplete')
        policy=self.plan['numerical_contract']['mandatory_runtime_policy']
        for k in ('torch_default_dtype','intermediate_device','vae_model_dtype','vae_output_dtype',
                  'conditioning_latent_dtype','conditioning_latent_device','stage_A_latent_shape',
                  'stage_B_latent_shape','sampler_capture_routes','decoder_replicas','lean_sampler_installed',
                  'before_each_conditioning_stage_floor_gib','after_each_conditioning_stage_floor_gib'):
            require(type(value['runtime_policy'].get(k)) is type(policy[k]) and value['runtime_policy'][k]==policy[k],
                    'Actual native runtime policy differs')
        receipts=value['guard_receipts'];require([r['event'] for r in receipts]==['begin','stage','stage','finish'] and
            all(r['request_id']==name for r in receipts),'Incomplete/failed conditioning sequence')
        require(receipts[0]['anchor_sha256']==provider['binding']['anchor_sha256'] and
                receipts[0]['plan_sha256']==PLAN_SHA and receipts[0]['runtime_sha256']==self.manifest_sha,
                'Guard anchor/source binding differs')
        thread=receipts[0]['thread_ident'];require(type(thread) is int and thread>0,'Guard thread missing')
        controller=value['controller_receipts'];encoder_ids=set();last_clock=0
        require(type(controller) is list and len(controller)<=64,'Controller evidence exceeds bounded native111 scope')
        for stage,gr in zip(('A','B'),receipts[1:3]):
            require(gr['stage']==stage and gr['completed'] is True and 'exception' not in gr and
                    gr['anchor_sha256']==provider['binding']['anchor_sha256'],'Unfinished conditioning stage')
            shape=policy['stage_'+stage+'_latent_shape']
            expected=gr['source_derived_encode_expectation'];height,width=shape[-2]*32,shape[-1]*32
            require(expected==dict(conditioning_node_sha256='09ddb30d42244d64ae72e9c64261d1a6b4c512afe0570372222c43dbebd64243',
                vae_source_before_encode_safety_delta_sha256='d1c63b66a6d0cf467ecb084d7ec5fb73d20b0fac43181668124a8ded06aa7604',
                expected_input_shape=[1,3,1,height,width],workspace_estimate_bytes=80*7*height*width*2,
                estimate_formula='80 * max(T,7) * H * W * BF16_bytes',internal_pixels_observed=False,
                measured_peak=False,loader_checks_required_unchanged=True),'Encode source expectation differs')
            for k,expected in [('input',shape),('output',shape),('noise_mask',[1,1,7,1,1])]:
                m=gr[k];require(m['shape']==expected and all(type(x) is int for x in m['shape']) and m['dtype']=='torch.float32' and
                    m['device']=='cpu' and m['contiguous'] is True and
                    all(type(m[x]) is int and m[x]>0 for x in ('object_id','storage_id')),'Guard tensor metadata differs')
            require(len({gr[x]['storage_id'] for x in ('input','output','noise_mask')}|{anchor['storage_id']})==4,'Guard storage aliases')
            for k in ('cache_before','cache_after_before_snapshot','cache_after','cache_after_after_snapshot'):
                cache=gr[k];require(cache['source_sha256']=='42010d800e6e49bdc69ae24587910b55b2418e26a1140bec7159a873276c45c2'
                    and type(cache['thread_ident']) is int and cache['thread_ident']==thread and type(cache['encoder_id']) is int and cache['encoder_id']>0
                    and all(type(cache[x]) is int and cache[x]==0 for x in ('entry_count','foreign_entry_count')),'Encoder cache identity/residue differs')
                encoder_ids.add(cache['encoder_id'])
            self.memory(gr['before'],name,'conditioning-'+stage+'-before',PRE,baseline)
            self.memory(gr['after'],name,'conditioning-'+stage+'-after',POST,baseline)
            require(last_clock<gr['before']['snapshot']['timestamp_ns']<gr['after']['snapshot']['timestamp_ns'],
                    'Conditioning memory snapshots reordered')
            last_clock=gr['after']['snapshot']['timestamp_ns']
            lo,hi=gr['controller_receipt_start'],gr['controller_receipt_end']
            require(type(lo) is int and type(hi) is int and 0<=lo<hi<=len(controller) and
                    controller[lo:hi]==[gr['before'],gr['after']],'Controller range differs')
        require(len(encoder_ids)==1,'Encoder cache owner changed across stages')
        return provider

    def _one(self,e,row,identity,prior,previous_end):
        pid,start,end,obs=self.execution(e,row,identity,previous_end)
        out=dict(schema='ltx.continuation111.proof.v1',verified=True,name=row['name'],prompt_id=pid,
                 plan_sha256=PLAN_SHA,runtime_manifest_sha256=self.manifest_sha,
                 server_identity_sha256=self.identity_sha,graph_sha256=row['graph_sha256'],start_ms=start,success_ms=end)
        if row['kind']=='window-probe':
            require(obs['native_snapshot'] is None,'Window unexpectedly has native snapshot')
            source=self.packet/'source/scripts/setup_gates.py'
            raw=self.source(e,source,SETUP_SHA);namespace={}
            exec(compile(raw,str(source),'exec'),namespace)
            out['setup']=namespace['validate_window'](e.json(self.run/('text-window-probe-'+row['name']+'.json')),row['name'],self.identity_sha)
        else:
            preparation=e.json(self.run/'native-preparation.json');baseline=preparation['snapshot']
            self.snapshot(baseline,PRE);self.snapshot(obs['native_snapshot'],POST,baseline)
            admission=preparation['receipts'][0];require(admission['event']=='preload-admission','Preload admission absent')
            for card in CARDS:
                require(all(type(admission[k][card]) is int and admission[k][card]>=0 for k in ('free','required','missing_tensor_bytes'))
                        and admission['free'][card]>=admission['required'][card]>=math.ceil(1.1*admission['missing_tensor_bytes'][card])+PRE[card],
                        'Preload equation/free margin differs')
            if row['kind']=='prepare-native':out['setup']={'kind':'native-full-residency','snapshot':baseline}
            else:
                name=row['name']
                before=e.json(self.run/('native-memory-before-'+name+'.json'));after=e.json(self.run/('native-memory-after-'+name+'.json'))
                self.memory(before,name,'before',PRE,baseline);self.memory(after,name,'after',POST,baseline)
                require(before['snapshot']['timestamp_ns']<after['snapshot']['timestamp_ns']<=obs['native_snapshot']['timestamp_ns'],'Native snapshot order differs')
                pipe=e.json(self.run/('pipeline-'+name+'.json'));detail=pipe['detail'];text=sha(('pipeline-window\n'+row['graph']['364']['inputs']['text']).encode())
                require(pipe['passed'] is True and pipe['run_name']==name and pipe['clip_index']==row['clip_index'] and
                        pipe['depth']==2 and pipe['mode']=='pipeline-window' and pipe['server_identity_sha256']==self.identity_sha and
                        pipe['model_verification_sha256']==MODEL_SHA and pipe['output_size']=='640x384' and
                        type(pipe['frame_count']) is int and pipe['frame_count']==49 and pipe['speed_only'] is False,'Native encoder receipt differs')
                require(detail['text_sha256']==detail['tag']==text and detail['started_ahead']==detail['pending_after']==[] and
                        detail['speculation_miss'] is False and detail['window_encode']['window']==64 and
                        detail['window_encode']['clip_index']==row['clip_index'],'Encoder reused/ahead/geometry differs')
                out['conditioning_sha256']=digest(detail['conditioning_fingerprint'])
                capture=self.root/'output/validation'/name;meta=e.json(capture/'summary.json')
                require(meta['run_name']==name and meta['sample_rate']==48000 and meta['deterministic_enabled'] is True and
                        meta['deterministic_warn_only'] is False,'Capture determinism/identity differs')
                inventory,anchor=scan_capture(capture/'tensors.safetensors',meta['tensors'])
                e.bind(inventory['path'],inventory['sha256']);e.captures.add(inventory['path']);out['capture']=inventory
                if row['chunk_index']<2:
                    context=dict(runtime_manifest_sha256=self.manifest_sha,model_verification_sha256=MODEL_SHA,plan_sha256=PLAN_SHA,
                                 prompt_sha256=sha(row['graph']['364']['inputs']['text'].encode()),pass_index=row['pass_index'],
                                 chunk_index=row['chunk_index'],seed=row['seed'],graph_sha256=row['graph_sha256'],capture_name=name)
                    out['anchor_binding']=dict(schema='ltx.continuation111.anchor.v1',context=context,**anchor)
                checkpoint=e.json(self.run/('capture-checkpoint-'+name+'.json'));self.common(checkpoint,row,pid)
                pre=checkpoint['prewrite'];prefix=[r for r in self.plan['requests'][:list(self.rows).index(name)+1] if r['capture_role']]
                require(pre['failed'] is None and pre['plan_sha256']==PLAN_SHA and pre['capture_cap']==6 and
                        pre['captures_reserved']==len(prefix) and pre['raw_budget_bytes']==6*MAX_CAPTURE and
                        pre['reserved_bytes']==len(prefix)*MAX_CAPTURE and len(pre['captures'])==len(prefix),'Capture prefix/cap differs')
                require(all(type(pre[k]) is int for k in ('capture_cap','captures_reserved','raw_budget_bytes','reserved_bytes')),
                        'Capture counts must be strict integers')
                for expected,actual in zip(prefix,pre['captures']):
                    expected_pid=pid if expected['name']==name else prior[expected['name']]['prompt_id']
                    require(actual['name']==expected['name'] and actual['prompt_id']==expected_pid and
                            actual['graph_sha256']==expected['graph_sha256'] and actual['role']=='full' and
                            actual['actual_shape_kind']=='full' and actual['charged_bytes']==actual['file_bound']==MAX_CAPTURE,
                            'Capture authority row differs')
                if row['chunk_index']:
                    out['provider']=self.conditioning(e,row,pid,prior[row['predecessor_capture']],baseline)
                else:
                    require(not (self.run/('provider-receipt-'+name+'.json')).exists() and
                            not (self.run/('conditioning-receipt-'+name+'.json')).exists(),'Unconditioned chunk has anchor execution')
                if row['pass_index']:
                    ref=prior[row['reference_capture']]
                    require(ref['capture']['tensors']==inventory['tensors'] and ref['conditioning_sha256']==out['conditioning_sha256'],
                            'Full native replay differs')
                    out['replay_reference']=row['reference_capture']
        out['evidence_sha256']=dict(e.hashes)
        return out

    def produce(self,name):
        require(name in self.rows,'Unknown request');self.fault_check();e=Evidence()
        require(sha(e.raw(self.packet/'manifest.json'))==self.manifest_sha and
                e.json(self.packet/'manifest.json')==self.manifest,'Manifest identity differs')
        envelope=e.json(self.packet/'resolution/candidate-plan.json')
        require(envelope=={'plan':self.plan,'plan_sha256':PLAN_SHA},'Packet plan differs')
        for rel,pin in self.manifest['files'].items():
            if rel.endswith('.py'):self.source(e,self.packet/rel,pin)
        identity=e.json(self.run/'server-identity.json');require(e.hashes[str(self.run/'server-identity.json')]==self.identity_sha and
            identity['source_packet_manifest_sha256']==self.manifest_sha and identity['model_verification_sha256']==MODEL_SHA,'Server source/model differs')
        require(all(identity.get(k) is not None for k in ('pid','proc_start_ticks','boot_id','source_commit','runtime','rope_compatibility')),'Incomplete server identity')
        require(all(type(identity[k]) is int and identity[k]>0 for k in ('pid','proc_start_ticks')),
                'Invalid server process identity')
        prior={};seen=set();end=0
        for row in self.plan['requests']:
            result=self._one(e,row,identity,prior,end)
            require(result['prompt_id'] not in seen,'Duplicate prompt ID');seen.add(result['prompt_id']);end=result['success_ms']
            if row['name']==name:break
            path=self.run/('continuation-proof-'+row['name']+'.json');stored=e.json(path)
            require(stored==result,'Prior proof differs from reconstructed prefix')
            prior[row['name']]=result
        e.recheck();self.fault_check()
        return result

    def verify(self,name,path,expected_sha256):
        require(safe_path(path)==self.run/('continuation-proof-'+name+'.json'),'Proof path differs')
        raw=read_regular(path);require(sha(raw)==digest(expected_sha256),'Proof SHA differs')
        stored=strict_json(raw);actual=self.produce(name)
        require(stored==actual and read_regular(path)==raw,'Proof failed fresh reconstruction')
        return actual
