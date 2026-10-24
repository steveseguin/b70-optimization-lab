#!/usr/bin/env python3
"""Fixed all-12 resident comparison. CLI plans only; root owns operational admission."""
import argparse,hashlib,importlib.util,json,math,shutil,statistics,time
from pathlib import Path
P=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/baseline');L=P.parent;R=P.parents[3]
OPERATING=Path(__file__).resolve().parent.parent
MANIFEST=P/'manifest.json';CAP=26;PER_REQUEST=221743168+9699332
CORPUS=R/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json'

def require(v,msg):
    if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load_adapter():
    p=OPERATING/'generated/adapter.py';s=importlib.util.spec_from_file_location('gsq_resident_adapter',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
A=load_adapter()
s=importlib.util.spec_from_file_location('gsq_iq3_block_checks',OPERATING/'checks.py');C=importlib.util.module_from_spec(s);s.loader.exec_module(C)
def manifest():
    m=json.loads(MANIFEST.read_text());require(len(m['prompts'])==12 and m['total_requests']==CAP and m['measured_requests']==24,'fixed full corpus/count')
    require(m['max_new']==128 and m['context']==4096,'fixed output/context cap')
    original=json.loads(CORPUS.read_text())['prompts']
    require([p['prompt_id'] for p in m['prompts']]==[p['prompt_id'] for p in original],'original complete corpus order')
    ids=set();spans=set()
    for i,row in enumerate(m['prompts']):
        require(row['prompt_id'] not in ids,'duplicate prompt');ids.add(row['prompt_id'])
        t=row['tokens'];require(t==list(map(int,(R/original[i]['input_bundle']/'tokens.txt').read_text().split())),'original prompt token bytes')
        require(type(t)is list and len(t)==row['prompt_tokens'] and all(type(x)is int and 0<=x<248320 for x in t) and len(t)+128<=4096,'prompt tokens')
        require(row['order']==(['none','mtp'] if i%2==0 else ['mtp','none']),'balanced fixed order')
        spans.update(tuple(t[j:j+5]) for j in range(max(0,len(t)-4)))
    require(len(m['warmup'])==2 and [w['mode'] for w in m['warmup']]==['none','mtp'],'both warmup modes')
    warm=set()
    for w in m['warmup']:
        t=tuple(w['tokens']);require(len(t)==5 and all(type(v)is int and 1<=v<=15 for v in t) and t not in spans and t not in warm,'warmup disjointness')
        require(w['max_new']==8 and not w['measured'] and not w['eos_enabled'],'excluded warmup bounds');warm.add(t)
    require(m['tokenizer_authority']['all_tokenizer_metadata_equal'] and len(m['tokenizer_authority']['canonical_json_sha256'])==10,'tokenizer authority')
    for path,h in {**m['source_pins'],**m['tokenizer_authority']['source_sha256']}.items():require(sha(R/path)==h,'frozen corpus source changed')
    return m

def first_native_proof(binary_sha):
    return C.prerequisites(binary_sha)

def build_plan(output,evidence_output):
    m=manifest();base=A.build_plan(output,mini=False,max_new=128,seconds=7200,evidence_output=evidence_output)
    prior=first_native_proof(base['binary_sha256'])
    files=[prior,Path(__file__).resolve(),MANIFEST,L/'serving/adapter.py',L/'serving/evidence/host-pair.json',L/'metadata/compatibility-delta.json',OPERATING.parent/'evidence/native-build.json',OPERATING/'checks.py',OPERATING/'candidate-ledger.json',OPERATING/'preparation.json']
    return dict(schema='ownrt.gsq.resident-baseline-plan.v1',adapter=base,baseline_review_sha256=C.REVIEW_SHA,baseline_result_sha256=C.REFERENCE_SHA,manifest_sha256=sha(MANIFEST),source_sha256={str(f):sha(f) for f in files},total_requests=CAP,measured_requests=24,warmup_requests=2,max_output_tokens=24*128+2*8,lifetime_seconds=7200,storage=dict(per_request_state_bytes=PER_REQUEST,retained_state_dumps=CAP+1,evidence_forecast_bytes=(CAP+1)*PER_REQUEST+128*1024**2,root_cache_forecast_bytes=128*1024**2,root_floor_bytes=27000000000,external_floor_bytes=2*1024**3,hard_bound=False),authority='this outer26-request suite owns count/storage policy; inherited adapter2-request comparison helper is not called',native_admitted=False,scope=m['scope'])
def validate_plan(plan):
    require(plan==build_plan(plan['adapter']['output'],plan['adapter']['evidence_output']),'suite plan/source/parent changed')
    A.validate_plan(plan['adapter']);return manifest()
def storage_guard(plan,completed=0,started=False):
    require(type(completed)is int and 0<=completed<=CAP,'request budget')
    c=Path(plan['adapter']['output']);e=Path(plan['adapter']['evidence_output']);b=plan['storage']
    cp=c if started else c.parent;ep=e if started else e.parent
    require(cp.stat().st_dev!=ep.stat().st_dev,'suite state evidence must use separate external filesystem')
    require(shutil.disk_usage(cp).free>=b['root_floor_bytes']+b['root_cache_forecast_bytes'],'root cache forecast/floor')
    remaining=(CAP-completed+1)*b['per_request_state_bytes']+128*1024**2
    require(shutil.disk_usage(ep).free>=b['external_floor_bytes']+remaining,'remaining external state forecast/floor')

def metric(result,requested):
    tokens=result['tokens'];rows=result['timing_rows'];require(0<len(tokens)<=requested and len(rows)==len(tokens),'complete output/timing rows')
    stamps=[]
    for i,(t,row) in enumerate(zip(tokens,rows)):
        require(row['generated_index']==i+1 and row['token_id']==t,'timing/token identity')
        stamp=row['completed_monotonic'];require(type(stamp) in (int,float) and math.isfinite(stamp),'finite completion time');stamps.append(stamp)
    require(all(b>a for a,b in zip(stamps,stamps[1:])),'strictly increasing completion times')
    if len(tokens)<requested:require(tokens[-1] in (248044,248046),'unexplained early termination')
    wall=result['decode_wall_ms'];n=len(tokens)-1
    require(type(wall) in (int,float) and math.isfinite(wall) and wall>=0 and result['decode_intervals']==n,'decode interval identity')
    require(abs(wall-((stamps[-1]-stamps[0])*1000 if n else 0))<=max(.001,wall*1e-9),'decode timestamps disagree')
    require(math.isfinite(result['prompt_wall_ms']) and result['prompt_wall_ms']>=0,'finite prompt wall time')
    return dict(output_tokens=len(tokens),output_cap=requested,termination='eos' if tokens[-1] in (248044,248046) else 'cap',decode_intervals=n,decode_wall_ms=wall,decode_tok_s=n*1000/wall if n and wall>0 else None,prompt_wall_ms=result['prompt_wall_ms'],scope='resident request after excluded warmup; N-1 intervals after first token, EOS included if emitted; not cold-start/end-to-end throughput')

def summary(pairs):
    groups={}
    for first in ('all','none','mtp'):
        selected=[p for p in pairs if first=='all' or p['order'][0]==first]
        arms={}
        for mode in ('none','mtp'):
            rows=[next(a for a in p['arms'] if a['mode']==mode) for p in selected]
            n=sum(a['metric']['decode_intervals'] for a in rows);ms=sum(a['metric']['decode_wall_ms'] for a in rows)
            rates=[a['metric']['decode_tok_s'] for a in rows if a['metric']['decode_tok_s'] is not None]
            arms[mode]=dict(prompts=len(rows),zero_interval_prompts=len(rows)-len(rates),total_output_tokens=sum(a['metric']['output_tokens'] for a in rows),decode_intervals=n,decode_wall_ms=ms,interval_weighted_tok_s=n*1000/ms if n and ms else None,median_prompt_tok_s=statistics.median(rates) if rates else None,prompt_wall_ms_sum=sum(a['metric']['prompt_wall_ms'] for a in rows),guesses=sum(a['result']['stats']['guesses'] for a in rows),hits=sum(a['result']['stats']['hits'] for a in rows),misses=sum(a['result']['stats']['misses'] for a in rows))
        groups[first]=dict(first_arm=first,arms=arms)
    return dict(order_groups=groups,all_cases_retained=True,short_eos_cases_retained=True,warmups_excluded=True,claim_scope='candidate correctness and descriptive timing only; separate-process baseline comparison is not a speed promotion')

def run_attached(t,plan,m=None):
    """Strictly serialized fixed schedule; caller owns admission and normal close."""
    C.bind_references(plan)
    m=m or manifest();require(not getattr(t,'resident_suite_started',False),'suite may run only once');t.resident_suite_started=True
    count=0;measured=[];warm=[];capture_stamps={};start=time.monotonic()
    def request(name,mode,prompt,cap,measuring):
        nonlocal count
        require(sha(MANIFEST)==plan['manifest_sha256'],'manifest changed during suite')
        require(count<CAP and time.monotonic()-start<plan['lifetime_seconds'],'suite count/lifetime exceeded')
        t.check_alive();storage_guard(plan,count,True)
        # Every warmup and measurement begins from a full original RESET. There
        # is no retained prompt prefix/KV and no benchmark-prompt warmup.
        destination=t.out/name;A.reset(t,destination);count+=1
        C.verify_capture_stamps(t.out,capture_stamps)
        result=A.BASE.NativeController(t,A.BASE.Draft(mode),True,False).run(prompt,cap,(248044,248046) if measuring else ())
        result.update(evidence_label='GSQ IQ3_XXS block candidate; every measured arm checked against frozen baseline',decode_tok_s=None)
        row=dict(request=count,name=name,mode=mode,prompt_tokens=prompt,requested_max_new=cap,measured=measuring,result=result)
        if measuring:
            row['metric']=metric(result,cap);row['state_sha256']=A.state_hashes(t);capture_stamps[name]=C.capture_stamp(destination)
        else:require(len(result['tokens'])==cap,'incomplete excluded warmup')
        A.save(destination/'suite-request.json',row)
        if measuring:
            C.check_arm(row)
            A.save(destination/'baseline-exact.json',dict(passed=True,reference_sha256=C.REFERENCE_SHA,scope='exact corresponding independently audited baseline token/state arm'))
        t.check_alive();return row
    for w in m['warmup']:warm.append(request('warmup-'+w['mode'],w['mode'],w['tokens'],w['max_new'],False))
    for i,prompt in enumerate(m['prompts']):
        pair=[]
        for mode in prompt['order']:pair.append(request(f'prompt-{i:02d}-{mode}',mode,prompt['tokens'],128,True))
        require(pair[0]['result']['tokens']==pair[1]['result']['tokens'],'target/MTP tokens differ: '+prompt['prompt_id'])
        require(pair[0]['state_sha256']==pair[1]['state_sha256'],'target/MTP final state differs: '+prompt['prompt_id'])
        row=dict(prompt_id=prompt['prompt_id'],order=prompt['order'],exact_tokens=True,exact_final_target_state=True,arms=pair)
        measured.append(row);A.save(t.out/f'pair-{i:02d}.json',row)
    require(count==CAP and len(measured)==12,'incomplete suite')
    final=measured[-1]['arms'][-1]
    require(A.state_hashes(t)==final['state_sha256'],'final explicit DUMP differs')
    C.verify_capture_stamps(t.out,capture_stamps)
    return dict(passed=True,capture_stamps=capture_stamps,final_explicit_DUMP_verified=True,rank_pids=[p.pid for p in t.children],requests=count,measured_requests=24,warmup=warm,prompts=measured,summary=summary(measured),manifest_sha256=sha(MANIFEST),output_cap=128,resident_scope=True,cold_start_speed_claim=False,old_model_record_comparison=False,completed_elapsed_seconds=time.monotonic()-start)

def qualification(plan,*,admit,check,launch_hook):
    m=validate_plan(plan);storage_guard(plan);admit(plan)
    t=A.Transport.__new__(A.Transport)
    try:
        t.__init__(plan['adapter'],admit=lambda p:A.require(p==plan['adapter'],'adapter binding'),check=check,launch_hook=launch_hook)
        result=run_attached(t,plan,m);t.close(True);C.verify_capture_stamps(t.out,result['capture_stamps']);result['closed_capture_stamps_verified']=True;path=t.out/'resident-suite.json';A.save(path,result)
        # Full request traces stay on the external evidence filesystem. The
        # coordinator receives a bounded terminal join, not another multi-MB copy.
        return dict(passed=True,requests=CAP,measured_requests=24,rank_pids=result['rank_pids'],manifest_sha256=result['manifest_sha256'],summary=result['summary'],full_result_path=str(path),full_result_sha256=sha(path),old_model_record_comparison=False)
    except BaseException as error:
        # Same original-error and retained-resource behavior as frozen adapter.
        secondary=A.cleanup_failure(t,error)
        if hasattr(t,'out') and t.out.exists():
            try:A.save(t.out/'resident-suite-incident.json',dict(passed=False,error=repr(error),secondary=secondary))
            except BaseException:pass
        raise

def main():
    a=argparse.ArgumentParser();a.add_argument('--plan',action='store_true',required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--evidence-output',type=Path,required=True);x=a.parse_args();print(json.dumps(build_plan(x.output,x.evidence_output),indent=2))
if __name__=='__main__':main()
