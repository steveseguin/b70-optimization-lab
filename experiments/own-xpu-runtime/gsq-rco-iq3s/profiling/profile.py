#!/usr/bin/env python3
"""Fixed prompt00 class diagnostic; no CLI owner launch or native changes."""
import hashlib,importlib.util,json,math,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parent;R=P.parents[3]
PINS={'baseline/suite.py':'301347fe701eaaaa1e16e7a3891da2808a956147ae67b9b918dd451b7fe010d4','baseline/manifest.json':'c8ad4665ddad4cff54961181679d402525c19381af855434d046508840180e20','serving/adapter.py':'68538b214b7bda9c2fa5cd87534bad2243745b8a1af0dc82b43f01da48b06a01'}
BASE_CONTROL=Path('/home/steve/own-xpu-runtime-results/gsq-baseline-a.control')
BASE_EVIDENCE=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-baseline-a')
PER_REQUEST=231442500
def require(v,msg):
    if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify_sources():
    for name,digest in PINS.items():require(sha(L/name)==digest,'frozen profiling dependency changed: '+name)
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
verify_sources();S=load(L/'baseline/suite.py','gsq_profile_frozen_suite');A=S.A
TOKEN_COMMAND=A.command
def command(plan,rank,channel,stop_fd):
    argv=TOKEN_COMMAND(plan,rank,channel,stop_fd)
    require(argv.count('--timing')==1,'single timing argument required')
    i=argv.index('--timing')+1;require(argv[i]=='token','frozen token timing expected')
    argv[i]='class';return argv
# Only this private imported adapter module changes. Its build_plan and runtime
# both call the same command function; argv/environment digest binds the change.
A.command=command
def read_json(path,limit=64*1024**2):
    p=Path(path);require(p.is_file() and not p.is_symlink() and p.stat().st_size<=limit,'bounded regular evidence')
    return json.loads(p.read_text())
def baseline_proof(binary_sha):
    terminal=BASE_CONTROL/'terminal.json';admission=BASE_CONTROL/'admission.json'
    t=read_json(terminal,2*1024**2);a=read_json(admission,2*1024**2)
    require(t['passed'] is True and t['children_exited'] and t['target_descriptors_empty'] and t['first_error'] is None and t['original_error'] is None,'completed clean baseline required')
    require(t['plan_sha256']==a['plan_sha256'] and a['plan']['adapter']['binary_sha256']==binary_sha,'baseline plan/binary identity')
    require(t['result']['requests']==26 and t['result']['measured_requests']==24,'complete all12 baseline required')
    path=BASE_EVIDENCE/'resident-suite.json'
    require(t['result']['full_result_path']==str(path) and sha(path)==t['result']['full_result_sha256'],'baseline result hash')
    full=read_json(path);require(full['passed'] is True and len(full['prompts'])==12 and full['manifest_sha256']==sha(L/'baseline/manifest.json'),'baseline full result identity')
    pair=full['prompts'][0];m=S.manifest();require(pair['prompt_id']==m['prompts'][0]['prompt_id'] and pair['exact_tokens'] and pair['exact_final_target_state'],'fixed prompt00 proof')
    arms=[x for x in pair['arms'] if x['mode']=='none'];require(len(arms)==1,'one baseline target arm')
    arm=arms[0];require(arm['prompt_tokens']==m['prompts'][0]['tokens'] and arm['requested_max_new']==128 and arm['measured'] is True,'baseline request identity')
    require(set(arm['state_sha256'])=={'0','1'} and all(arm['state_sha256'].values()),'both complete target states')
    S.metric(arm['result'],128)
    for f,h in a['plan']['source_sha256'].items():require(sha(f)==h,'baseline admitted source changed')
    return arm,{str(f):sha(f) for f in (terminal,admission,path)}
def build_plan(output,evidence_output):
    verify_sources();m=S.manifest()
    base=A.build_plan(output,mini=False,max_new=128,seconds=3600,evidence_output=evidence_output)
    first=S.first_native_proof(base['binary_sha256']);arm,prior=baseline_proof(base['binary_sha256'])
    review=L/'baseline/evidence/independent-suite-review.json';r=read_json(review)
    require(r['passed'] is True,'independent frozen suite review required')
    for f,h in r['source_sha256'].items():require(sha(R/f)==h,'reviewed suite source changed')
    files=[Path(__file__),P/'test_profile.py',P/'README.md',first,review,*[L/f for f in PINS]]
    return dict(schema='ownrt.gsq.class-profile.v1',adapter=base,prompt_id=m['prompts'][0]['prompt_id'],prompt_tokens=m['prompts'][0]['tokens'],warmup=m['warmup'][0],baseline_evidence_sha256=prior,source_sha256={str(f):sha(f) for f in files},requests=2,measured_requests=1,max_new=128,storage=dict(per_request_state_bytes=PER_REQUEST,retained_state_dumps=3,evidence_forecast_bytes=3*PER_REQUEST+64*1024**2,root_cache_forecast_bytes=128*1024**2,root_floor_bytes=27000000000,external_floor_bytes=2*1024**3,hard_bound=False),timing='class',only_native_argv_delta='--timing token -> class',rank1_queue_profiling_property_changed=True,whole_request_classes=True,no_speed_claim=True,native_admitted=False)
def validate_plan(plan):
    require(plan==build_plan(plan['adapter']['output'],plan['adapter']['evidence_output']),'profiling source/plan/prerequisite changed')
    A.validate_plan(plan['adapter'])
def storage_guard(plan,completed=0,started=False):
    require(type(completed)is int and 0<=completed<=2,'bounded request count')
    c=Path(plan['adapter']['output']);e=Path(plan['adapter']['evidence_output']);b=plan['storage']
    cp=c if started else c.parent;ep=e if started else e.parent
    require(cp.stat().st_dev!=ep.stat().st_dev,'external state filesystem required')
    require(shutil.disk_usage(cp).free>=b['root_floor_bytes']+b['root_cache_forecast_bytes'],'root floor/cache forecast')
    require(shutil.disk_usage(ep).free>=b['external_floor_bytes']+(3-completed)*PER_REQUEST+64*1024**2,'external state forecast')
def classes(path):
    r=read_json(path,2*1024**2);require(r['profiling'] is True and r['classes'],'nonempty class report')
    require(any(x['launches']>0 and x['device_ms']>0 for x in r['classes']),'actual profiled events required')
    for x in r['classes']:require(math.isfinite(x['device_ms']) and x['device_ms']>=0 and type(x['launches'])is int and x['launches']>=0 and type(x['groups'])is int and x['groups']>=0,'valid class totals')
    return dict(path=str(path),sha256=sha(path),report=r)
def qualification(plan,*,admit,check,launch_hook):
    validate_plan(plan);storage_guard(plan);admit(plan);reference,_=baseline_proof(plan['adapter']['binary_sha256'])
    t=A.Transport.__new__(A.Transport)
    try:
        t.__init__(plan['adapter'],admit=lambda p:require(p==plan['adapter'],'adapter identity'),check=check,launch_hook=launch_hook)
        warm=plan['warmup'];A.reset(t,t.out/'warmup-none');storage_guard(plan,0,True)
        result=A.BASE.NativeController(t,A.BASE.Draft('none'),True,False).run(warm['tokens'],8,())
        require(len(result['tokens'])==8,'complete excluded warmup');A.save(t.request_output/'warmup.json',dict(excluded=True,result=result));t.check_alive()
        storage_guard(plan,1,True);A.reset(t,t.out/'profile-none')
        result=A.BASE.NativeController(t,A.BASE.Draft('none'),True,False).run(plan['prompt_tokens'],128,(248044,248046))
        result.update(evidence_label='class profiling diagnostic only',decode_tok_s=None)
        state=A.state_hashes(t)
        require(result['tokens']==reference['result']['tokens'],'profiling changed confirmed tokens')
        require(state==reference['state_sha256'],'profiling changed final target state')
        t.check_alive();t.close(True)
        reports={str(r):classes(t.out/f'profile-none/rank{r}/class-times.json') for r in (0,1)}
        full=dict(passed=True,requests=2,measured_requests=1,prompt_id=plan['prompt_id'],result=result,state_sha256=state,exact_baseline_tokens=True,exact_baseline_target_state=True,classes=reports,baseline_evidence_sha256=plan['baseline_evidence_sha256'],no_speed_claim=True)
        path=t.out/'profile-result.json';A.save(path,full)
        return dict(passed=True,requests=2,measured_requests=1,rank_pids=[p.pid for p in t.children],full_result_path=str(path),full_result_sha256=sha(path),exact_baseline_tokens=True,exact_baseline_target_state=True,no_speed_claim=True)
    except BaseException as error:
        secondary=A.cleanup_failure(t,error)
        if hasattr(t,'out') and t.out.exists():
            try:A.save(t.out/'profile-incident.json',dict(passed=False,error=repr(error),secondary=secondary))
            except BaseException:pass
        raise
