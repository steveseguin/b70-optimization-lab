"""Read-only closed artifact audit. No runtime, process/service or device APIs."""
import hashlib,json,os,resource,stat
from pathlib import Path
P=Path(__file__).resolve().parent;LANE=P.parents[2];ROOT=LANE.parents[2]
C=Path('/home/steve/own-xpu-runtime-results/gsq-model-a.control')
E=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-model-a')
assert os.getpriority(os.PRIO_PROCESS,0)==19
assert os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32))
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))

def sha(p):
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd);assert stat.S_ISREG(before.st_mode)
        h=hashlib.sha256()
        while b:=os.read(fd,256*1024):h.update(b)
        after=os.fstat(fd);assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
        return h.hexdigest()
    finally:os.close(fd)
def read(p):return json.loads(Path(p).read_text())
def write(p,j):
    with Path(p).open('x') as f:json.dump(j,f,indent=2);f.write('\n')
plan=read(C/'plan.json');adm=read(C/'admission.json');terminal=read(C/'terminal.json');q=read(E/'qualification.json')
assert adm['plan']==plan and sha(C/'plan.json')==adm['plan_sha256']==terminal['plan_sha256']
assert hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()==adm['canonical_plan_sha256']
assert terminal['passed'] and q['passed'] and terminal['result']==q and q['same_rank_processes'] and q['requests']==2
assert terminal['first_error'] is terminal['original_error'] is None
assert terminal['children_exited'] and terminal['target_descriptors_empty'] and terminal['observed_target_contact']==[True,True]
assert terminal['service_changes']==terminal['retries']==terminal['hard_kills']==0 and terminal['speed_claim'] is False
assert q['rank_pids']==[x[0] for x in terminal['rank_identities']]
source_pins={**plan['source_sha256'],**{str(ROOT/p):h for p,h in plan['adapter']['source_sha256'].items()}}
for f,h in source_pins.items():assert sha(f)==h,f
build=read(plan['adapter']['build_receipt']);assert build['passed'] and build['mode']=='native'
assert sha(plan['adapter']['build_receipt'])==plan['adapter']['build_receipt_sha256']
assert sha(plan['adapter']['binary'])==plan['adapter']['binary_sha256']==build['binary_sha256']
for f,h in build['source_sha256'].items():assert sha(ROOT/f)==h,f
for f,h in build['object_sha256'].items():assert sha(f)==h,f
assert plan['adapter']['mini'] is False and plan['adapter']['context']==4096
assert plan['max_new']==32 and plan['requests']==2
for rank in (0,1):
    launch=read(C/f'ranks/rank{rank}-launch.json');argv=launch['argv'];env=launch['environment']
    assert launch['pid']==q['rank_pids'][rank] and env==plan['adapter']['environment'][rank]
    for flag,value in [('--cards','1'),('--card','0'),('--context','4096'),('--target-split','24'),('--draft-rank','0'),('--memory','resident')]:assert argv[argv.index(flag)+1]==value
    assert '--gsq-packed' in argv and '--selection' not in argv and '--dispatch' not in argv
    assert ('--draft-mtp' in argv)==(rank==0)
    assert env['FilterBdfPath']==('0000:23:00.0','0000:47:00.0')[rank] and env['HOME']=='/home/steve'

results=[read(E/f'{mode}-result.json') for mode in ('none','mtp')]
tokens=results[0]['tokens'];assert len(tokens)==32 and tokens==results[1]['tokens']
assert [r['tokens'] for r in q['rows']]==[tokens,tokens]
expected=list(enumerate(plan['prompt']+tokens[:-1]));assert len(expected)==55
for j in results:
    assert j['decode_tok_s'] is None and j['diagnostic'] is False
    assert [x['token_id'] for x in j['timing_rows']]==tokens
    rows=j['rank_trace'];r1=sorted((x for x in rows if x['rank']==1 and x['op']==1),key=lambda x:x['position'])
    assert [(x['position'],x['token']) for x in r1]==expected
    pending=None;accepted=[]
    for x in sorted((x for x in rows if x['rank']==0),key=lambda x:x['rank_received']):
        if x['op']==1:pending=x
        elif x['op']==3:pending=None
        elif x['op']==2:
            assert pending is not None;accepted.append((pending['position'],pending['token']));pending=None
    assert accepted==expected and pending is None
assert results[0]['stats']['guesses']==0
assert [results[1]['stats'][k] for k in ('guesses','hits','misses')]==[31,25,6]
assert len(results[1]['guess_rows'])==31 and sum(r['hit'] for r in results[1]['guess_rows'])==25
raw_request=list(map(int,(C/'ranks/native-request.txt').read_text().split()))
assert raw_request[:7]==[3,32,1,0,len(plan['prompt']),0,2] and raw_request[7:7+len(plan['prompt'])]==plan['prompt'] and raw_request[-2:]==[248044,248046]
assert read(C/'ranks/native-result.json')['tokens']==tokens

# Rehash every closed file in bounded chunks. No model tensor files are opened.
index=[];digests={}
for label,root in [('control',C),('evidence',E)]:
    for f in sorted(root.rglob('*')):
        assert not f.is_symlink(),str(f)
        if not f.is_file():continue
        digest=sha(f);digests[str(f)]=digest
        index.append(dict(root=label,path=str(f.relative_to(root)),bytes=f.stat().st_size,sha256=digest))
assert sum(r['bytes'] for r in index)<1024**3
states=[];rawstate=[]
for mode,base in [('none',E),('mtp',E/'mtp-request')]:
    state={};raw=0
    for rank in (0,1):
        directory=base/f'rank{rank}/state-2147483647'
        state[str(rank)]={str(f.relative_to(directory)):digests[str(f)] for f in sorted(directory.rglob('*')) if f.is_file()}
        manifest=read(directory/'state.json')
        for name,digest in manifest['buffers'].items():
            filename=('alternate-'+name.split(':',1)[1] if name.startswith('alternate:') else name)+'.bin'
            assert state[str(rank)][filename]==digest
        raw+=sum(f.stat().st_size for f in directory.glob('*.bin'))
    assert state==next(r['state'] for r in q['rows'] if r['mode']==mode)
    states.append(state);rawstate.append(raw)
assert states[0]==states[1] and rawstate==[221743168]*2
owners=[];memory=[]
ledger=read(LANE/'memory/engine-accounting.json')['scenarios']['split24-24_mtp-rank0']['ranks']
for rank in (0,1):
    r=read(E/f'rank{rank}/receipt.json');assert r['passed'] and r['rank']==rank and r['device_executed'] and r['error']=='' and r['selection_sha256']==''
    assert len(r['teardown'])==1;t=r['teardown'][0]
    assert t['safe_to_exit'] and t['status']=='complete' and t['in_flight']==t['live_bytes']==t['exit_code']==0
    owners.append({k:t[k] for k in ('backend','status','safe_to_exit','in_flight','live_bytes','exit_code')})
    c=read(E/f'rank{rank}/census.json');actual=sum(a['bytes'] for a in c['allocations'] if a['live'] and a['memory']=='device')
    assert actual==c['totals']['device']==ledger[rank]['device_logical_bytes']
    assert c['totals']['host-pinned']==ledger[rank]['pinned_host_bytes']
    memory.append(dict(rank=rank,device_bytes=actual,forecast_exact=True,pinned_host_bytes=c['totals']['host-pinned']))
    reset=read(E/f'mtp-request/rank{rank}/reset.json');assert reset['passed'] and reset['allocation_ids_preserved']
ownership=read(E/'ownership.json');assert ownership['returncodes']==[0,0] and ownership['retained_pids']==[] and ownership['signals_sent']==0 and not ownership['stop_requested']
prefix=read(E/'rank0/draft-prefix.json');assert prefix['rows']==prefix['full_rows']==248320 and prefix['extra_weight_bytes']==839321600
manifest={r.split()[0]:r.split()[7] for r in (LANE/'mtp/draft-manifest.tsv').read_text().splitlines() if r.strip()}
assert read(E/'rank0/draft-tensor-reads.json')==manifest
model=Path('/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a')
for row in (LANE/'loader/shard-auth.tsv').read_text().splitlines():
    name,*numbers=row.split();s=(model/name).stat();assert list(map(int,numbers))==[s.st_size,s.st_dev,s.st_ino,s.st_mtime_ns,s.st_ctime_ns]
before=adm['before'];after=terminal['after']
assert before['boot']==after['boot'] and before['kernel']['faults']==after['kernel']['faults'] and after['known_fault_baseline_matches']
assert before['drm']==after['drm'] and before['queue']==after['queue']
assert before['units']['qwen38-27b-vision']==after['units']['qwen38-27b-vision']
assert after['holders']['3487303']['start_ticks']==63453537
assert not after['identity_races'] and after['inventory']['errors']==[]
for h in after['inventory']['holders']:
    assert h['pid']==3487303 and after['drm'][h['node']]['bdf'] in ('0000:27:00.0','0000:43:00.0')
assert {h['node'] for h in before['inventory']['holders']}=={h['node'] for h in after['inventory']['holders']}
assert after['root_free_bytes']>=27000000000
coherence=LANE/'operating/first-model-text.json';text=read(coherence);assert text['tokens']==tokens and text['truncated_at_max_new']
(P/'first-model-text.json').write_bytes(coherence.read_bytes())
index_record={'schema':'ownrt.gsq.real-model-closed-index.v1','roots':{'control':str(C),'evidence':str(E)},'files':index,'raw_state_bytes_per_request':rawstate,'state_originals_retained':True,'no_model_payload_read':True}
with (P/'artifact-index.json').open('x') as f:json.dump(index_record,f,separators=(',',':'));f.write('\n')
review=dict(schema='ownrt.gsq.real-model-independent-review.v1',passed=True,scope='One 24-token prompt / 32-output-token correctness fixture; no speed or broad quality claim',tokens=tokens,prompt_tokens=plan['prompt'],same_pair=q['rank_pids'],confirmed_consumed_positions_per_rank=55,final_generated_token_not_consumed=tokens[-1],target_state_files_per_request=sum(len(x) for x in states[0].values()),target_state_exact=True,mtp_stats=results[1]['stats'],draft_tensor_hashes_checked=len(manifest),draft_full_head=True,owners=owners,ownership=ownership,memory=memory,physical_drain={'source':'retained passive before/after inventories and source-bound coordinator attestation; no fresh device/host query','target_bdfs':['0000:23:00.0','0000:47:00.0'],'after_target_holders':0,'vision_pid':3487303,'vision_start_ticks':63453537,'vision_bdfs':['0000:27:00.0','0000:43:00.0'],'kernel_fault_baseline_unchanged':True},binary_sha256=build['binary_sha256'],native_source_pins_checked=len(build['source_sha256']),native_objects_checked=len(build['object_sha256']),source_sha256=source_pins,artifact_index_sha256=sha(P/'artifact-index.json'),artifact_count=len(index),indexed_bytes=sum(x['bytes'] for x in index),coherence_text_sha256=sha(coherence),reviewer_script_sha256=sha(__file__),limitations=['One capped prompt, response ends mid-sentence at32 tokens','Target-only and MTP use this same quantization; no FP8/othermodel equivalence','All target plan/alternate bytes compared, not every standalone runtime scratch allocation','Target source/header/stat identity verified; no independent full GGUF payload rehash','Recorded physical drain and protected vision evidence audited, not a fresh process/service/kernel inspection','Native receipt arithmetic label and plan variant strings inherit old generic naming; actual identity is the new bound loader and full native build SHA','No timing comparison: first request includes first-use compilation/cache effects'])
write(P/'review.json',review)
print(json.dumps({'passed':True,'review_sha256':sha(P/'review.json'),'files':len(index),'bytes':review['indexed_bytes'],'state_files':review['target_state_files_per_request']}))
