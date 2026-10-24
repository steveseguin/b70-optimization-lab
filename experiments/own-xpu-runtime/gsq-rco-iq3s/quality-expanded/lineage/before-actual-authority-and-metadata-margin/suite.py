"""Expanded fixed corpus using the qualified private adapter and ACK accounting.
No CLI, tokenizer execution at import, or operational admission in this module.
"""
from pathlib import Path
import hashlib,importlib.util,json,time
P=Path(__file__).resolve().parent;L=P.parent;R=L.parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
for f,h in json.loads((P/'parent-pins.json').read_text()).items():require(sha(f)==h,'frozen expanded parent '+f)
Q=load(L/'dense-packed-block/engine/operating/launch-b/once.py','expanded_private_storage_b')
S=Q.S;A=S.A;C=S.C;CAP=S.CAP;MANIFEST=S.MANIFEST;manifest=S.manifest;metric=S.metric;summary=S.summary
T=load(L/'coverage/tokenizer.py','expanded_pinned_decode_only')
BINARY='5aef74d5f803b33758711db352ee5e1a393a364e6c33aa9f8a4cdb4478f5fe6a'
BUILD='3fe225c3c7076fbf680b3d7e0d1a051e533a34b5ed059da0048b8743323aed95'
ACTUAL=L/'dense-packed-block/engine/operating/launch-b/evidence/device-b/review.json'
ADAPTER_BUILD=A.build_plan;COMMAND=A.command;SUITE_BUILD=Q.SUITE_BUILD
storage_guard=S.storage_guard

def actual_authority():
 # Root supplies this only after independent actual full-suite readback PASS.
 binding=json.loads((P/'actual-authority.json').read_text())
 require(binding['review_path']==str(ACTUAL) and sha(ACTUAL)==binding['review_sha256'],'actual current review binding')
 r=json.loads(ACTUAL.read_text())
 require(r['passed'] and r['all12_exact'] and r['measured_arms']==24 and r['bundles']==54 and r['physical_drain'] and r['kernel_fault_baseline_unchanged'] and r['native_binary_sha256']==BINARY,'current full Engine actual qualification')
 require(r['capture_budget']['finished'] and r['capture_budget']['remaining_payload_bytes']==0,'qualified acknowledged closure')
 return binding

def review_sources():
 review=P/'evidence/independent-review.json';r=json.loads(review.read_text());require(r['passed'] and r['source_sha256'],'expanded source review')
 for f,h in r['source_sha256'].items():require(sha(Path(f) if Path(f).is_absolute() else R/f)==h,'reviewed expanded source drift')
 files=[P/'suite.py',P/'once.py',P/'parent-pins.json',P/'PLAN.md',P/'rubrics.json',P/'actual-authority.json',review,ACTUAL]
 return {str(f):sha(f) for f in files}

def read_rubrics():
 m=manifest();require(all(len(x['tokens'])+512<=4096 for x in m['prompts']),'expanded context capacity');r=json.loads((P/'rubrics.json').read_text());source=R/r['source_suite'];require(sha(source)==r['source_sha256'],'original rubric source')
 require([x['id'] for x in r['cases']]==[x['prompt_id'] for x in m['prompts']],'all12 fixed rubric IDs/order')
 return r

def command(plan,rank,channel,stop_fd):
 # Inherited builder calls command before added distinction fields exist.
 require(plan['max_new']==512 and plan.get('startup_max_new',128)==128,'fixed startup128/request512 split')
 return COMMAND(dict(plan,max_new=128),rank,channel,stop_fd)
def adapter_build(output,*,mini=False,max_new=128,seconds=7200,evidence_output=None):
 require(not mini and max_new in (128,512),'fixed real expanded adapter')
 p=ADAPTER_BUILD(output,mini=False,max_new=512,seconds=seconds,evidence_output=evidence_output)
 p.update(startup_max_new=128,measured_request_max_new=512,warmup_request_max_new=8)
 p['source_sha256'].update(review_sources());return p
A.command=command;A.build_plan=adapter_build

def suite_build(output,evidence_output):
 actual_authority();read_rubrics();p=SUITE_BUILD(output,evidence_output)
 require(p['adapter']['binary_sha256']==BINARY and p['adapter']['build_receipt_sha256']==BUILD and p['adapter']['max_new']==512,'same current binary/request ceiling')
 p.update(schema='gsq.expanded-quality.plan.v1',max_output_tokens=24*512+2*8,startup_max_new=128,measured_request_max_new=512,no_speed_claim=True,scope='All12 original prompts expanded to512; original128 prefix and full target/MTP equality; manual complete-answer readback required')
 p['source_sha256'].update(review_sources());return p
Q.SUITE_BUILD=suite_build

def check_prefix(row):
 require(row['name'] in C.REFERENCES,'original arm name');ref=C.REFERENCES[row['name']]
 require(row['mode']==ref['mode'] and row['prompt_tokens']==ref['prompt_tokens'] and row['requested_max_new']==512,'expanded original request identity')
 original=ref['result']['tokens'];got=row['result']['tokens']
 require(0<len(original)<=128 and got[:len(original)]==original,'original baseline token prefix')
 if len(original)<128 or original[-1] in (248044,248046):require(got==original,'baseline natural EOS must remain terminal')
 # Deliberately no final512-vs-final128 target state comparison.

def retain_decoded(destination,row,rubrics):
 index=int(row['name'].split('-')[1]);rubric=rubrics['cases'][index]
 text=T.decode(row['result']['tokens'])
 A.save(destination/'decoded-output.json',dict(tokens=row['result']['tokens'],text=text,skip_special_tokens=False,tokenizer_sha256=T.TOKENIZER_SHA,requested_max_new=512,termination=row['metric']['termination'],rubric=rubric,automated_quality_passed=None,manual_full_output_review_required=True,scope='Unrepaired full output; cap truncation is not complete-task success'))
def quality_summary(pairs):
 result=summary(pairs);result['claim_scope']='512-cap expanded correctness and manual task readback; no public/cross-run speed claim';return result

def run_attached(t,plan,m=None):
    """Strictly serialized fixed schedule; caller owns admission and normal close."""
    C.bind_references(plan);rubrics=read_rubrics()
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
        result.update(evidence_label='Expanded512-cap same-target coverage; original128-token prefix only',decode_tok_s=None)
        row=dict(request=count,name=name,mode=mode,prompt_tokens=prompt,requested_max_new=cap,measured=measuring,result=result)
        if measuring:
            row['metric']=metric(result,cap);row['state_sha256']=A.state_hashes(t);capture_stamps[name]=C.capture_stamp(destination)
        else:require(len(result['tokens'])==cap,'incomplete excluded warmup')
        A.save(destination/'suite-request.json',row)
        if measuring:
            check_prefix(row)
            A.save(destination/'baseline-prefix-exact.json',dict(passed=True,reference_sha256=C.REFERENCE_SHA,scope='exact original128-cap token prefix only; final512 state compared within target/MTP pair'))
            retain_decoded(destination,row,rubrics)
        t.check_alive();return row
    for w in m['warmup']:warm.append(request('warmup-'+w['mode'],w['mode'],w['tokens'],w['max_new'],False))
    for i,prompt in enumerate(m['prompts']):
        pair=[]
        for mode in prompt['order']:pair.append(request(f'prompt-{i:02d}-{mode}',mode,prompt['tokens'],512,True))
        require(pair[0]['result']['tokens']==pair[1]['result']['tokens'],'target/MTP tokens differ: '+prompt['prompt_id'])
        require(pair[0]['state_sha256']==pair[1]['state_sha256'],'target/MTP final state differs: '+prompt['prompt_id'])
        row=dict(prompt_id=prompt['prompt_id'],order=prompt['order'],exact_tokens=True,exact_final_target_state=True,arms=pair)
        measured.append(row);A.save(t.out/f'pair-{i:02d}.json',row)
    require(count==CAP and len(measured)==12,'incomplete suite')
    final=measured[-1]['arms'][-1]
    require(A.state_hashes(t)==final['state_sha256'],'final explicit DUMP differs')
    C.verify_capture_stamps(t.out,capture_stamps)
    return dict(passed=True,capture_stamps=capture_stamps,final_explicit_DUMP_verified=True,rank_pids=[p.pid for p in t.children],requests=count,measured_requests=24,warmup=warm,prompts=measured,summary=quality_summary(measured),manifest_sha256=sha(MANIFEST),output_cap=512,startup_output_cap=128,quality_qualified=False,manual_full_output_review_required=True,no_speed_claim=True,resident_scope=True,cold_start_speed_claim=False,old_model_record_comparison=False,completed_elapsed_seconds=time.monotonic()-start)

Q.RUN=run_attached
