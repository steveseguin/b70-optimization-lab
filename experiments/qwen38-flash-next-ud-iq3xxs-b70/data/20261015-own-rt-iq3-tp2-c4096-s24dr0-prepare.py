"""Read completed SPEED3 receipts; write only this data prefix. Never submit."""
import argparse,base64,copy,datetime,gzip,hashlib,json,os,statistics,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
D=Path(__file__).resolve().parent
PREFIX='20261015-own-rt-iq3-tp2-c4096-s24dr0-'
OLD='20261013-own-rt-iq3-tp2-c4096-'
P=ROOT/'experiments/own-xpu-runtime/stage2/packet45-merged3'
RUN=P/'build/speed3-c4096-dr0-s24-gpu'
LABEL='qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-mtp1-c4096-s24dr0-realistic-20261015'
REV='75d2c459d'
SEAL='8460585fe53879223066a5d54799c9f105c73002adfc09fc9a743ceaee7e3fa8'
sys.path.insert(0,str(ROOT/'scripts'))
from promotion_evidence import validate_packet45_device_evidence
from submit_localmaxxing_results import preflight_payload, OWNER_128_AUTHORIZATION, OWNER_128_RAW_GATE

def sha(data):return hashlib.sha256(data).hexdigest()
def rel(p):return str(p.relative_to(ROOT))
def read(p):return json.loads(p.read_bytes())
def dest(suffix):return D/(PREFIX+suffix)
def save(suffix,value):
 p=dest(suffix);assert not p.is_relative_to(P)
 p.write_text(json.dumps(value,indent=1)+'\n');return p

def confirmation_evidence(headline, headline_requests, input_hashes):
 configs=[
  ('run1-headline',RUN/'WS128',True),
  ('run2-confirmation',RUN/'WS128-r2',False),
  ('run3-confirmation',RUN/'WS128-r3',False),
  ('p44-interleaved-control',ROOT/'experiments/own-xpu-runtime/stage2/packet44-context/build/c4096ctl15a/WS128-r2',False),
  ('p44-earlier-control',ROOT/'experiments/own-xpu-runtime/stage2/packet44-context/build/c4096ctl15a/WS128',False),
  ('draft-rank1-confirmation',P/'build/speed3-c4096-dr1-gpu/WS128',False)]
 records=[]
 for label,directory,submitted in configs:
  raw=(directory/'window.json').read_bytes();w=json.loads(raw);s=w['summary']
  assert w['passed'] and w['device_executed'] and not w.get('cpu_rehearsal',False)
  assert w['boot_id']==headline['boot_id'] and s['complete'] and len(s['rows'])==12
  assert w.get('qualifying',True) and not w.get('diagnostic_unsealed',False)
  is_p45=directory.is_relative_to(P)
  if is_p45:
   assert w['qualifying'] and w['build_receipt_sha256']==SEAL and w['artifacts_sha256']==headline['artifacts_sha256']
   if w['draft_rank']==0:assert w['dispatch_sha256']==headline['dispatch_sha256']
  out=dest(label+'-confirmation-window.json');out.write_bytes(raw)
  input_hashes[rel(directory/'window.json')]=sha(raw)
  rates=[];classes={};timestamps=[];members=[]
  for row in s['rows']:
   f=directory/'run'/row['receipt'];b=f.read_bytes();r=json.loads(b)
   assert w['receipts'][str(f.relative_to(directory))]==sha(b)
   assert r['passed'] and len(r['tokens'])==128
   assert r['tokens']==headline_requests[row['prompt_id']]['tokens']
   stamps=row['token_timestamps'] if is_p45 else row['generated_token_completion_timestamps']
   assert len(stamps)==128
   rate=99/(stamps[99]-stamps[0]);rates.append(rate);timestamps.extend(stamps)
   declared=row['tok_s_1_100_intervals_after_ttft'] if is_p45 else row['submission_tok_s']
   assert abs(rate-declared)<1e-8
   if is_p45:
    assert row['cached_tokens']==0 and row['requested_max_new']==128 and row['repeat']==1
    classes.setdefault(row['prompt_class'],[]).append(rate)
   members.append(dict(path=rel(f),sha256=sha(b),raw_base64=base64.b64encode(b).decode()))
  archive=dest(label+'-confirmation-requests.json.gz')
  archive.write_bytes(gzip.compress(json.dumps(members,separators=(',',':')).encode(),mtime=0))
  records.append(dict(run=label,submitted_headline=submitted,source_path=rel(directory),window_path=rel(out),window_sha256=sha(raw),request_archive=dict(path=rel(archive),sha256=sha(archive.read_bytes())),passed=w['passed'],qualifying=w.get('qualifying'),qualification_note='Explicit qualifying receipt' if is_p45 else 'Legacy p44 schema: no qualifying field; passing device control, described as qualifying by owner',boot_id=w['boot_id'],build_receipt_sha256=w['build_receipt_sha256'],cards=[w['card'],w['card']+1],draft_rank=w.get('draft_rank',0),target_split=w.get('target_split'),all_prompt_median=statistics.median(rates),class_balanced=statistics.median(statistics.median(v) for v in classes.values()) if classes else None,first_token_monotonic=min(timestamps),last_token_monotonic=max(timestamps),tokens_equal_headline=True,requests=12,output_tokens_per_request=128))
 return dict(schema='lab.speed3-confirmation.v1',headline='run1-headline',selection_policy='Pre-registered run 1 only; no pooling, selection of higher repeats, or substitution',runs=records,chronological_order=sorted([dict(run=r['run'],first_token_monotonic=r['first_token_monotonic'],last_token_monotonic=r['last_token_monotonic']) for r in records],key=lambda r:r['first_token_monotonic']),controls_class_balanced_note='Not reported in the legacy p44 summary; all-prompt conventional 99-interval medians shown')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--owner-128-exception',action='store_true');a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32))
 assert os.statvfs('/').f_bavail*os.statvfs('/').f_frsize>=8_000_000_000
 manifest_path=ROOT/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012-cap128/suite-manifest.json'
 manifest=read(manifest_path);entries={r['prompt_id']:r for r in manifest['prompts']}
 assert sha((P/'build-receipt.json').read_bytes())==SEAL
 windows={n:read(RUN/n/'window.json') for n in ('W2m','WS','WSs','WS128x','WS128')}
 performance=windows['WS128'];artifacts=performance['artifacts_sha256']
 evidence=[];input_hashes={};summaries={};requests={};archives={};fixture_counts={};seen_pids=set()
 for name,w in windows.items():
  assert w['passed'] and w['qualifying'] and w['device_executed'] and not w['diagnostic_unsealed'] and not w['cpu_rehearsal']
  assert (w['card'],w['context'],w['draft_rank'],w['target_split'])==(0,4096,0,24)
  assert w['build_receipt_sha256']==SEAL and w['artifacts_sha256']==artifacts
  assert w['boot_id']==performance['boot_id'] and w['dispatch_sha256']==performance['dispatch_sha256']
  pids=set(w['launched_pids']);assert len(pids)==2 and not pids&seen_pids and not w['retained_owner_pids'];seen_pids|=pids
  source=RUN/name/'window.json';raw=source.read_bytes();out=dest(name+'-window.json');out.write_bytes(raw)
  input_hashes[rel(source)]=sha(raw);evidence.append(dict(path=rel(out),sha256=sha(raw),source_path=rel(source),window=name))
  for filename in ('kernel-window.txt','kernel-preflight.txt'):
   f=RUN/name/filename;data=f.read_bytes();input_hashes[rel(f)]=sha(data)
   dest(name+'-'+filename).write_bytes(data)
   if filename=='kernel-window.txt':assert not any(k in data.lower() for k in (b'fault response',b'cat error',b'engine reset',b'timed-out job',b'timed out job',b'devcoredump'))
  if name=='W2m':assert w['token_matches']==64 and w['layer_matches']==384;continue
  summary=read(RUN/name/'run/summary.json');summaries[name]=summary
  assert summary==w['summary'] and summary['passed'] and summary['complete'] and not summary['partial_suite']
  assert len(summary['rows'])==12 and set(r['prompt_id'] for r in summary['rows'])==set(entries)
  requests[name]={};members=[];fixture_counts[name]=0
  for row in summary['rows']:
   f=RUN/name/'run'/row['receipt'];raw=f.read_bytes();receipt=json.loads(raw);pid=row['prompt_id']
   assert w['receipts'][str(f.relative_to(RUN/name))]==sha(raw)
   assert receipt['passed'] and receipt['device_executed'] and receipt['repeat']==1
   assert receipt['binary_sha256']==artifacts['device/own-rt-iq3'] and receipt['target_split']==24
   assert receipt['cached_tokens']==receipt['usage']['prompt_tokens_details']['cached_tokens']==0
   assert receipt['output_tokens']==len(receipt['tokens'])==128 and receipt['requested_max_new']==128
   assert receipt['oracle_check']['passed'] and receipt['oracle_check']['every_emitted_token'] and receipt['oracle_check']['tokens']==128
   oracle=ROOT/entries[pid]['oracle_directory']/'tokens.jsonl'
   oracle_raw=oracle.read_bytes();input_hashes[rel(oracle)]=sha(oracle_raw)
   assert receipt['tokens']==[json.loads(line)['token_id'] for line in oracle_raw.splitlines()]
   input_path=ROOT/entries[pid]['input_bundle']/'input.json';inp=read(input_path);input_hashes[rel(input_path)]=sha(input_path.read_bytes())
   assert len(inp['tokens'])==receipt['prompt_tokens']
   assert sha(json.dumps(inp['tokens'],separators=(',',':')).encode())==receipt['prompt_token_sha256']
   assert sha(json.dumps(receipt['tokens'],separators=(',',':')).encode())==receipt['output_token_sha256']
   assert row['output_token_sha256']==receipt['output_token_sha256']
   if name=='WS128':
    stamps=receipt['token_timestamps'];assert len(stamps)==128 and all(y>x for x,y in zip(stamps,stamps[1:]))
    assert abs(99/(stamps[99]-stamps[0])-receipt['submission_tok_s'])<1e-9
    assert abs(row['wall_tok_s']-receipt['wall_tok_s'])<1e-9 and abs(row['ttft_ms']-receipt['ttft_ms'])<1e-9
    assert receipt['retain_steps']=='none' and receipt['metric_window_eligible']
   fixture_counts[name]+=receipt['oracle_check']['fixture_files']
   requests[name][pid]=receipt;input_hashes[rel(f)]=sha(raw)
   members.append(dict(path=rel(f),sha256=sha(raw),raw_base64=base64.b64encode(raw).decode()))
  warm=RUN/name/'run/warmup/receipt.json';warm_raw=warm.read_bytes();wr=json.loads(warm_raw)
  assert wr['excluded_from_timing'] and wr['warmup_selection']['distinct_from_every_suite_prompt'] and wr['warmup_selection']['complete_reset_before_measured_requests']
  members.append(dict(path=rel(warm),sha256=sha(warm_raw),raw_base64=base64.b64encode(warm_raw).decode()))
  archive=dest(name+'-request-receipts.json.gz');archive.write_bytes(gzip.compress(json.dumps(members,separators=(',',':')).encode(),mtime=0))
  archives[name]=dict(path=rel(archive),sha256=sha(archive.read_bytes()),members=len(members),format='gzip JSON array; raw_base64 decodes original receipt bytes; SHA256 per member')
 for pid in entries:
  assert all(requests[n][pid]['tokens']==requests['WS128'][pid]['tokens'] for n in requests)
 assert fixture_counts==dict(WS=4608,WSs=4608,WS128x=9216,WS128=0)
 validate_packet45_device_evidence(dict(artifacts_sha256=artifacts),evidence,dest('promotion-attestation.json'))
 dispatch=(RUN/'K2/run0/dispatch-measured.json').read_bytes();assert sha(dispatch)==performance['dispatch_sha256'];dest('dispatch-measured.json').write_bytes(dispatch)
 chain=[]
 for name in ('K0','K1a','K1b','K2','W0p','KD'):
  f=RUN/name/'window.json';raw=f.read_bytes();w=json.loads(raw)
  assert w['passed'] and w['qualifying'] and w['device_executed'] and not w['diagnostic_unsealed']
  assert w['build_receipt_sha256']==SEAL and w['artifacts_sha256']==artifacts and w['target_split']==24 and w['draft_rank']==0
  chain.append(dict(window=name,path=rel(f),sha256=sha(raw),passed=True,device_executed=True,qualifying=True))
 s=summaries['WS128'];rows=s['rows'];class_rates={}
 for r in rows:class_rates.setdefault(r['prompt_class'],[]).append(r['tok_s_1_100_intervals_after_ttft'])
 classes={k:statistics.median(v) for k,v in class_rates.items()};headline=statistics.median(classes.values())
 assert headline==s['class_balanced_tok_s_1_100_intervals_after_ttft']['median']==38.15715689731613
 base=copy.deepcopy(read(D/(OLD+'localmaxxing-payload-queue.json'))[0]);base['label']=LABEL
 payload=base['payload'];flags=payload['engineFlags']
 identity=dict(model_revision=payload['modelRevision'],runtime_revision=REV,optimization_identity='packet45-merged3-SPEED3-tp2-c4096-target24-24-draft-rank0-write-set-snapshot-K2-selected-kernels-native-controller-single-pass-draft-profiling',suite_sha256=manifest['suite_sha256'])
 command=['ionice -c 3 env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2',"LD_LIBRARY_PATH='"+performance['environment']['native']['LD_LIBRARY_PATH']+"'",'python3 -B '+rel(P/'window.py'),'--authorized-device-window --card 0 --context 4096 --draft-rank 0 --target-split 24 --window WS128','--output '+rel(RUN/'WS128')]
 for n in ('K0','K1a','K1b','K2','W0p','KD'):command+=['--'+n.lower()+' '+rel(RUN/n/'window.json')]
 command+=['--dispatch '+rel(RUN/'K2/run0/dispatch-measured.json'),'--suite-manifest '+rel(manifest_path),'--controller native --repeat 1 --retain-steps none --exactness-window '+rel(RUN/'WS128x/window.json')]
 command=' '.join(command)
 notes='Same Unsloth UD-IQ3_XXS model and quantization as record cmv6pugme0020oa01fjrho6nx, on new runtime revision 75d2c459d (SPEED3). Two rank processes on two B70 cards, 24/24 target layers, official one-token MTP draft on rank 0, native controller and K2-selected kernels. Every accepted token is target-verified. Checked write-set rollback preserves full state; draft events are profiled once. Twelve fixed realistic prompts, one cold response each, 128-token cap, zero cached tokens and complete request resets; no prompt/KV/response reuse. All 1536 output tokens match immutable arithmetic-v2-detmath oracles and sequential WSs. Separate WS128x checks 9216 retained layer fixtures at steps 1-8 and 97-104. Speed window retains no fixtures. Primary rate is the median of six prompt-class medians over 99 intervals between tokens 1 and 100. This is the historical 128-token submission scope, not a 512-token natural-completion gate. Context capacity 4096 only for this split/draft placement.'
 payload.update(engineVersion=f'own-xpu-runtime packet45-merged3 SPEED3 {REV}; device binary sha256 '+artifacts['device/own-rt-iq3'],promptTokens=s['promptTokens'],outputTokens=s['outputTokens'],tokSOut=headline,tokSTotal=s['wall_rate_statistics']['median'],ttftMs=s['ttft_statistics']['median'],notes=notes)
 flags.update(benchmarkJson=rel(dest('realistic-suite-v1-result.json')),commandSnippet=command,githubResultPacket='https://github.com/steveseguin/b70-optimization-lab/blob/main/'+rel(dest('result-packet.md')),promotionIdentity=identity,promotionAttestation=rel(dest('promotion-attestation.json')),outputSha256=[r['output_token_sha256'] for r in rows],promptSha256=[r['prompt_token_sha256'] for r in rows],outputTokens=[r['output_tokens'] for r in rows],realisticPromptTokenCounts=[r['prompt_tokens'] for r in rows],realisticOutputTokenCounts=[r['output_tokens'] for r in rows],realisticSuiteGatePassed=False,localmaxxingSubmissionAllowedUnderCurrentPolicy=a.owner_128_exception,kvCacheDtype='bf16',apiKvCacheDtype='auto',hashEncoding='SHA256 of compact JSON integer token arrays, as recorded in WS128 request receipts',targetSplit=[24,24],draftRank=0,deviceCards=[0,1],bootId=performance['boot_id'],buildReceiptSha256=SEAL,dispatchSha256=performance['dispatch_sha256'],environment={'OMP_NUM_THREADS':'2'},requestedMaxNew=128,strict512TokenFinalGatePassed=False)
 flags['rawRealisticFinalGate']=s['realistic_final_gate']
 assert flags['rawRealisticFinalGate']==OWNER_128_RAW_GATE
 if a.owner_128_exception:
  flags['realisticSuiteScopeException']=copy.deepcopy(OWNER_128_AUTHORIZATION)
  payload['notes']+=' Owner authorization 2026-10-15: "'+OWNER_128_AUTHORIZATION['authorization_text']+'" Strict 512-cap gate remains false: '+OWNER_128_RAW_GATE['reason']+'. Requested cap: 128. Run 1 is the registered headline; higher repeats are confirmation only.'
 confirmation=confirmation_evidence(performance,requests['WS128'],input_hashes)
 confirmation_path=save('confirmation-evidence.json',confirmation)
 result=copy.deepcopy(read(D/(OLD+'realistic-suite-v1-result.json')))
 result.update(label=LABEL,generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),engine='own-xpu-runtime (stage2/packet45-merged3 SPEED3 75d2c459d, native controller, two rank processes, target24/24, draft rank0)',artifacts_sha256=artifacts,promotionIdentity=identity,receipts=rel(dest('result-packet.md')))
 result['exactness'].update(retained_layer_fixtures_exact='9216/9216 in separate WS128x; none retained by WS128 speed window',authority='passing W2m, WS, WSs, WS128x device windows against immutable arithmetic-v2-detmath per-prompt oracles; byte equality, no tolerance',speculation='official one-token MTP draft head on rank 0; accepted tokens target-verified; identical tokens to fresh sequential WSs')
 result['primary_metric'].update(value_tok_s=headline,class_medians=classes)
 result['secondary'].update(decode_63_interval_median_tok_s=s['decode_median_tok_s'],wall_median_tok_s=payload['tokSTotal'],ttft_median_ms=payload['ttftMs'],prompt_tokens_median=payload['promptTokens'],output_tokens_median=payload['outputTokens'],submission100_all_prompt_statistics=s['submission100_statistics'],acceptance_statistics=s['acceptance_statistics'],ttft_statistics=s['ttft_statistics'],wall_rate_statistics=s['wall_rate_statistics'])
 result['rows']=[dict(prompt_id=r['prompt_id'],prompt_class=r['prompt_class'],prompt_tokens=r['prompt_tokens'],output_tokens=r['output_tokens'],ttft_ms=r['ttft_ms'],decode_tok_s=r['decode_tok_s'],submission_tok_s=r['tok_s_1_100_intervals_after_ttft'],wall_tok_s=r['wall_tok_s'],prompt_sha256=r['prompt_token_sha256'],output_sha256=r['output_token_sha256'],acceptance=r['acceptance'],ended_early=r['ended_early'],cached_tokens=r['cached_tokens'],finish_reason=r['finish_reason'],requested_max_new=128,full_natural_completion_tok_s=r['full_natural_completion_tok_s'],full_cap_limited_tok_s=r['full_cap_limited_tok_s'],submission100=r['submission100']) for r in rows]
 scope=dict(scope='Historical 2026-10-13 128-token-cap submission; not the strict 512-token final gate',owner_exception_authorized=a.owner_128_exception,raw_realistic_final_gate=s['realistic_final_gate'],strict_512_gate_passed=False,prepared_only=True,real_submission_performed=False)
 scope['owner_authorization']=copy.deepcopy(OWNER_128_AUTHORIZATION) if a.owner_128_exception else None
 scope['reference_submission']='cmv6pugme0020oa01fjrho6nx'
 scope['requested_max_new']=128
 result['confirmation_evidence']=dict(path=rel(confirmation_path),sha256=sha(confirmation_path.read_bytes()),headline_selection='Run 1 pre-registered; repeats and controls are never pooled or substituted')
 result.update(submission_scope=scope,hash_encoding=flags['hashEncoding'],quality_evidence=evidence,source_request_archives=archives)
 result_path=save('realistic-suite-v1-result.json',result)
 att=copy.deepcopy(read(D/(OLD+'promotion-attestation.json')));att.update(label=LABEL,date='2026-10-15',identity=identity,performance_evidence=dict(path=rel(result_path),sha256=sha(result_path.read_bytes())),quality_evidence=evidence,evidence=[e['path'] for e in evidence]+[rel(result_path)],submission_scope=scope)
 att['gates']['bit_exact_vs_cpu_oracles']='12/12 requests, 1536/1536 tokens in WS128; 9216/9216 retained layer fixtures in separate WS128x, byte equality'
 att['gates']['fresh_process_repeated_token_equality']='All 12 token sequences identical across independent WS, WSs, WS128x and WS128 rank-process launches; speed repeats are not pooled'
 att['confirmation_evidence']=result['confirmation_evidence']
 att['gates']['strict_512_token_final_gate_passed']=False
 att['gates']['kernel_log_scope']='No new signatures in each window journal tail; preflight includes historical October 11 faults, so not a clean-boot claim'
 att['seal6_amendment']=dict(rule='packet45.fix6.device-oracle-authority.2026-10-15',build_receipt_sha256=SEAL,required_device_windows=['W2m','WS','WSs','WS128x'],all_present_passing_same_artifacts=True)
 att_path=save('promotion-attestation.json',att);flags['promotionAttestationSha256']=sha(att_path.read_bytes())
 save('localmaxxing-payload-queue.json',[base])
 save('verification.json',dict(passed=True,device_executed=False,protected_tree_read_only=True,input_sha256=input_hashes,device_window_fixture_counts=fixture_counts,performance_source=rel(RUN/'WS128/run/summary.json'),performance_source_sha256=sha((RUN/'WS128/run/summary.json').read_bytes()),source_archives=archives,chain_prerequisites=chain,distinct_window_device_pids=sorted(seen_pids),preflight_problems=preflight_payload(base),submission_scope=scope))
 print(json.dumps(dict(headline=headline,decode=s['decode_median_tok_s'],submission100=s['submission100_statistics']['median'],ttftMs=payload['ttftMs'],tokSTotal=payload['tokSTotal'],preflight=preflight_payload(base))))

if __name__=='__main__':main()
