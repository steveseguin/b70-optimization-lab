"""Construct only the fixed eight-request native111 plan; no runtime or submission."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
PROTOTYPE = HERE.parent/'20261007-continuation111-reference'
PROTOTYPE_PINS = {
    'anchor.py':'a3aa2c357f47af7cc3e98b941f7473bcaf37ef376e2772dc9270c81159e96319',
    'graph.py':'90c5c438d7341846edbac5f9c9fd2b6c62e3ecfeb56d854717bd2fb5f1c26a68'}
SETUP_FILE_SHA = 'a16533121680eaaad8f952eb486d6a39a914290da7e6176ce537d78d940e714a'
PROVIDER = 'LTXContinuationAnchor111'
CONDITIONER = 'LTXContinuationCondition111'
FULL_FILE_BOUND = 146230536
ANCHOR_BYTES = 2949120
GIB = 2**30
MIB = 2**20


def require(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, expected):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe source path')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                before.st_size <= 8*MIB, 'Nonregular/linked/oversized source')
        stream = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with stream:
        raw = stream.read(8*MIB+1)
        identity = lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_nlink)
        require(len(raw) == before.st_size and identity(before) == identity(os.fstat(fd)) == identity(path.lstat()),
                'Source changed while reading')
    require(sha(raw) == expected, 'Pinned source changed: ' + str(path))
    return raw


def prototype():
    """Import only two exact CPU helpers without leaking their short module alias."""
    for name, pin in PROTOTYPE_PINS.items():
        read(PROTOTYPE/name, pin)
    def load(name, filename):
        spec=importlib.util.spec_from_file_location(name, PROTOTYPE/filename)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    old=sys.modules.get('anchor');had='anchor' in sys.modules
    try:
        helper=load('continuation111_plan_anchor','anchor.py');sys.modules['anchor']=helper
        return load('continuation111_plan_prototype','graph.py')
    finally:
        if had:sys.modules['anchor']=old
        else:sys.modules.pop('anchor',None)


def validate_edges(graph):
    visiting, done = set(), set()
    def visit(key):
        require(key not in visiting, 'Graph cycle')
        if key in done:return
        visiting.add(key)
        node=graph[key]
        require(set(node)=={'class_type','inputs'} and isinstance(node['inputs'],dict), 'Graph node fields differ')
        for value in node['inputs'].values():
            if isinstance(value,list):
                require(len(value)==2 and isinstance(value[0],str) and type(value[1]) is int and
                        value[1]>=0 and value[0] in graph, 'Dangling/malformed edge')
                visit(value[0])
        visiting.remove(key);done.add(key)
    for key in graph:visit(key)


def native_graph(base, pass_index, chunk_index, qualification_id):
    """Exact topology port; no runtime hash or fabricated predecessor receipt needed."""
    require(type(pass_index) is int and pass_index in (0,1) and
            type(chunk_index) is int and chunk_index in (0,1,2), 'Fixed pass/chunk only')
    graph=copy.deepcopy(base)
    name='continuation111-pass%d-chunk%d'%(pass_index,chunk_index)
    for node in graph.values():
        if 'run_name' in node['inputs']:node['inputs']['run_name']=name
    for key in ('338','339'):graph[key]['inputs']['noise_seed']=42+chunk_index
    graph['364']['inputs'].update(clip_index=99911000+pass_index*10+chunk_index,
                                qualification_id=qualification_id)
    if chunk_index:
        graph['continuation111_anchor']={'class_type':PROVIDER,'inputs':{'run_name':name}}
        for key,stage,edge in (('anchor_stage_a','A',['356',0]),('anchor_stage_b','B',['348',0])):
            graph[key]={'class_type':CONDITIONER,'inputs':{
                'vae':['420',2], 'image':['continuation111_anchor',0], 'latent':edge,
                'strength':1.0, 'bypass':False, 'run_name':name, 'stage':stage}}
        graph['377']['inputs']['video_latent']=['anchor_stage_a',0]
        graph['340']['inputs']['video_latent']=['anchor_stage_b',0]
    validate_edges(graph)
    return graph


def build_plan():
    p=prototype();base,sources=p.basis();original=p.design()
    # Derive QID before any graph embeds it. Actual plan SHA is computed last.
    numerical=copy.deepcopy(original['contract'])
    numerical.update(schema='ltx.continuation111.numerical-contract.v1',
        reference_mode='sequential native image-conditioned continuation plus full-chain replay',
        output_arithmetic='unchanged110 except disclosed native conditioning before both samplers',
        conditioning_native_api='LTXVImgToVideoInplace.execute(vae,image,latent,strength=1.0,bypass=False)',
        conditioning_stage_order=['A','B'], scene='boat', seed_order=[42,43,44],
        mandatory_runtime_policy={'torch_default_dtype':'torch.float32','intermediate_device':'cpu',
            'vae_model_dtype':'torch.bfloat16','vae_output_dtype':'torch.float32',
            'conditioning_latent_dtype':'torch.float32','conditioning_latent_device':'cpu',
            'stage_A_latent_shape':[1,128,7,6,10],'stage_B_latent_shape':[1,128,7,12,20],
            'before_each_conditioning_stage_floor_gib':[8,8,2,9],
            'after_each_conditioning_stage_floor_gib':2,
            'sampler_capture_routes':0,'decoder_replicas':0,'lean_sampler_installed':False,
            'vae_encoder_route':'unchanged native encode only; no tiled or alternate fallback',
            'text_encoder_route':'retain accepted graph-sharded window encoder',
            'policy':'Verify actual settings and tensors; never cast or change settings to satisfy this contract.'})
    qid=sha(canonical(numerical))
    setup_envelope=p.anchor.strict_json(read(p.PACKET/'resolution/setup-schedule.json', SETUP_FILE_SHA))
    source_setup=setup_envelope['schedule']['rows'][:2]
    require([r['kind'] for r in source_setup]==['window-probe','prepare-native'], 'Setup graph basis changed')
    rows=[]
    for old in source_setup:
        kind=old['kind'];name='continuation111-'+kind;graph=copy.deepcopy(old['graph'])
        for node in graph.values():
            if 'run_name' in node['inputs']:node['inputs']['run_name']=name
        validate_edges(graph)
        rows.append({'name':name,'kind':kind,'phase':'native-setup','authority_phase':'native_reference',
            'graph':graph,'graph_sha256':sha(canonical(graph)), 'capture_role':None,
            'requires_proofs':[] if not rows else ['proof:'+rows[-1]['name']],
            'proof_barrier':'proof:'+name, 'client_checkpoint_policy':'always'})
    for pass_index in range(2):
        for chunk_index in range(3):
            name='continuation111-pass%d-chunk%d'%(pass_index,chunk_index)
            predecessor=None if chunk_index==0 else 'continuation111-pass%d-chunk%d'%(pass_index,chunk_index-1)
            graph=native_graph(base,pass_index,chunk_index,qid)
            required=['proof:'+rows[-1]['name']]
            if pass_index:required.append('proof:continuation111-pass0-chunk%d'%chunk_index)
            if chunk_index and (pass_index or chunk_index==2):required.append('first-conditioned-verified')
            rows.append({'name':name,'kind':'native-chunk','phase':'native-reference' if pass_index==0 else 'native-repeat',
                'authority_phase':'native_reference','fixture':'boat','pass_index':pass_index,'chunk_index':chunk_index,
                'seed':42+chunk_index,'clip_index':99911000+pass_index*10+chunk_index,
                'graph':graph,'graph_sha256':sha(canonical(graph)), 'capture_role':'full',
                'predecessor_capture':predecessor,'predecessor_frame_index':48 if predecessor else None,
                'reference_capture':None if pass_index==0 else 'continuation111-pass0-chunk%d'%chunk_index,
                'requires_proofs':list(dict.fromkeys(required)), 'proof_barrier':'proof:'+name,
                'establishes':(['first-native-verified'] if (pass_index,chunk_index)==(0,0) else
                               ['first-conditioned-verified'] if (pass_index,chunk_index)==(0,1) else []),
                'conditioning_stages':['A','B'] if chunk_index else [],'client_checkpoint_policy':'always',
                'new_video_frames':49 if chunk_index==0 else 48, 'delivery_frame_start':int(chunk_index>0)})
    captures=[r for r in rows if r['capture_role']]
    contract={
        PROVIDER:{'required_inputs':{'run_name':'STRING'},'outputs':['IMAGE'],'registered':False,
            'source_binding':'Future sealed111 manifest must bind provider wrapper and reviewed anchor helper hashes.',
            'authority':'Resolve only active exact request and its accepted immediate same-pass predecessor proof; no caller path/hash.',
            'output':'Owned contiguous CPU F32 [1,384,640,3] from predecessor frame48; no conversion; reread whole-capture SHA each request.',
            'cache':'No cross-request cached provider output; one owned IMAGE shared by both consumers inside current request.'},
        CONDITIONER:{'required_inputs':{'vae':'VAE','image':'IMAGE','latent':'LATENT','strength':'FLOAT',
                     'bypass':'BOOLEAN','run_name':'STRING','stage':'STRING'},'outputs':['LATENT'],'registered':False,
            'stage_values':['A','B'], 'native_source_path':'source/comfy_extras/nodes_lt.py',
            'native_source_sha256':sources['source/comfy_extras/nodes_lt.py'],
            'native_class':'LTXVImgToVideoInplace','native_method':'execute',
            'source_binding':'Future sealed111 manifest must bind wrapper and ConditioningStageGuard helper hashes.',
            'authority':'Bind run_name to active request; require supplied image is the exact guard-owned anchor object; A then B once each.',
            'call':'Use guard.run_stage(stage, request_id=run_name, vae=vae, latent=latent, native_call=exact_native_execute); same original kwargs strength1/bypassFalse.',
            'safety':'Fresh conditioning admission and encode OOM-to-tiled refusal required before either native call; no fallback.'}}
    plan={'schema':'ltx.continuation111.native-plan.v1','status':'cpu-prepared-not-admitted',
        'qualification_id':qid,'numerical_contract':numerical,
        'basis':{'source_packet':str(p.PACKET),'source_manifest_sha256':p.MANIFEST_SHA,
            'source_plan_sha256':p.PLAN_SHA,'source_plan_file_sha256':p.PLAN_FILE_SHA,
            'native_graph_sha256':p.BASE_GRAPH_SHA,'setup_schedule_file_sha256':SETUP_FILE_SHA,
            'prototype_sources':PROTOTYPE_PINS,'prototype_numerical_design_sha256':original['prototype_plan_sha256'],
            'source_files':sources},
        'node_contracts':contract,'requests':rows,
        'execution_order':[r['name'] for r in rows],
        'after_each_request':'Complete durable proof_barrier before admitting next graph; no parallel submission, retries or extra fills.',
        'first_conditioned_admission':'After first-native proof; new encoding memory admission before pass0 chunk1 stages; accepted complete conditioned proof before subsequent conditioned requests.',
        'provider_binding':{'context_plan_sha256':'Use actual outer plan_sha256, never prototype_numerical_design_sha256 or qualification_id.',
            'context_runtime_sha256':'Use actual sealed111 runtime manifest, not source110 manifest or caller input.',
            'required_fields':['active_name','prompt_id','current_graph_sha256','predecessor_capture_sha256',
                'anchor_sha256','predecessor_graph_sha256','model_verification_sha256','prompt_sha256',
                'pass_index','predecessor_chunk_index','predecessor_seed','actual_plan_sha256','actual_runtime_sha256'],
            'dynamic_state':'Only verified per-chunk proof table changes; all eight graph hashes stay fixed.',
            'retention':'Keep both complete chains and all anchor/consumption/proof metadata until no readers remain and replay plus seam review complete.'},
        'capture_contract':{'count':6,'roles':{r['name']:'full' for r in captures},'full_file_bound_bytes':FULL_FILE_BOUND,
            'raw_capture_bound_bytes':6*FULL_FILE_BOUND,'shapes':copy.deepcopy(p.anchor.SHAPES),
            'prewrite':'Exact full F32 shape/dtype/finite/active-request checks before mkdir/save; no setup or placeholder capture roles.'},
        'budget':{'max_attempts':8,'max_captures':6,'retries':0,'setup_requests':2,'native_requests':6,
            'min_free_bytes':50*GIB,'runtime_write_allowance_bytes':4*GIB,'source_build_allowance_bytes':384*MIB,
            'minimum_free_before_build_bytes':54*GIB+384*MIB,'admitted':False,
            'write_allowance_status':'Conservative provisional ceiling; exact cache/other-output bound review and fresh measured storage admission still required.',
            'raw_capture_bound_bytes':6*FULL_FILE_BOUND,'anchor_payload_bytes_each':ANCHOR_BYTES,
            'predecessor_anchor_count':4,'anchor_payload_artifacts_required':False,
            'all_other_outputs_must_fit_remaining_bytes':4*GIB-6*FULL_FILE_BOUND},
        'proof_contract':{'setup':['source-bound accepted window verdict','native full-residency preparation and before-state'],
            'every_chunk':['exact registered graph and request/prompt/source identity','uncached required-node ordering',
                'four full tensor shapes/F32/finiteness/hash','prewrite full-role accounting',
                'fresh before/after native memory/owner/fault evidence','quiescence',
                'whole capture SHA and immediate same-pass predecessor linkage',
                'conditioned chunks require provider and A/B exact-call receipts'],
            'replay':'All four tensors equal corresponding pass0 chunk; pass1 derives anchors only from its own proven predecessor.',
            'final':'Six per-chunk proofs, four anchor/consumption links, two setup verdicts, source/plan/runtime identity, final quiescence and no fault.',
            'native_pre_floor_gib':[8,8,2,9],'post_request_floor_gib':2,'encode_workspace_admitted':False},
        'claims':{'deterministic_replay_qualified':False,'seam_motion_identity_accepted':False,
            'audio_alignment_resolved':False,'continuous_av':False,'adopted':False,'record':False,
            'endurance':False,'throughput_qualified':False,'unique_video_frames_per_chain':145,
            'raw_video_frames_per_chain':147,'replay_is_additional_unique_content':False,
            'delivery_slicing_implemented':False,
            'audio':'Retain separate untouched raw outputs; no trim/resample/crossfade/concatenation.',
            'timing':'Future submit-to-complete and anchor-ready-to-next-ready include conditioning/verification; no independent-W2 rate borrowed.'}}
    return {'plan':plan,'plan_sha256':sha(canonical(plan))}


def validate(envelope):
    require(type(envelope) is dict and set(envelope)=={'plan','plan_sha256'}, 'Plan envelope fields differ')
    require(envelope['plan_sha256']==sha(canonical(envelope['plan'])), 'Plan digest differs')
    require(envelope==build_plan(), 'Plan differs from exact reviewed source construction')
    return envelope


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();value=build_plan()
    if args.output:
        with args.output.open('x') as stream:
            json.dump(value,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
            stream.flush();os.fsync(stream.fileno())
        directory=os.open(args.output.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    else:
        print(json.dumps({'status':value['plan']['status'],'plan_sha256':value['plan_sha256'],
            'qualification_id':value['plan']['qualification_id'],'requests':len(value['plan']['requests']),
            'model_requests_submitted':0,'runtime_admitted':False},indent=2))


if __name__=='__main__':main()
