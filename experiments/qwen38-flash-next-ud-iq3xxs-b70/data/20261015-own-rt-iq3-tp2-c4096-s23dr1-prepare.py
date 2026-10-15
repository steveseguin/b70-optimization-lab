"""Read completed SPEED6 receipts; write only this data prefix. Never submit."""
import argparse,base64,copy,datetime,gzip,hashlib,json,os,statistics,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
D=Path(__file__).resolve().parent
PREFIX='20261015-own-rt-iq3-tp2-c4096-s23dr1-'
OLD='20261015-own-rt-iq3-tp2-c4096-s24dr0-'
P=ROOT/'experiments/own-xpu-runtime/stage2/packet45-merged3'
RUN=P/'build/speed6-c4096-dr1-s23-cards01-gpu'
LABEL='qwen38-flash-next-unsloth-iq3xxs-ownrt-tp2-mtp1-c4096-s23dr1-realistic-20261015'
REV='34c62b433'
SEAL='9b6fa7f397151c380a25f79dc3cf08abca1c70853300d7159febbf9456b35fbf'
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
 p44=ROOT/'experiments/own-xpu-runtime/stage2/packet44-context/build/c4096ctl15a'
 configs=[('run1-headline',RUN/'WS128'),('run2-confirmation',RUN/'WS128-r2'),
  ('cards23-replicate',P/'build/speed6-c4096-dr1-s23-cards23-gpu/WS128'),
  ('p44-interleaved-control',p44/'WS128-r3'),('p44-earlier-control',p44/'WS128'),
  ('p44-earlier-repeat',p44/'WS128-r2')]
 records=[];seen_pids=set()
 for name,directory in configs:
  source=directory/'window.json';raw=source.read_bytes();w=json.loads(raw)
  summary_path=directory/'run/summary.json';summary_raw=summary_path.read_bytes();summary=json.loads(summary_raw)
  is_p45=directory.is_relative_to(P);failed_control=name=='p44-interleaved-control'
  assert w['device_executed'] and w['boot_id']==headline['boot_id'] and summary['complete'] and len(summary['rows'])==(8 if failed_control else 12)
  if failed_control:
   assert w['passed'] is False and summary['passed'] is False
   assert 'storage admission refused' in w['error'] and 'build below 6 GB' in w['error']
  else:assert w['passed'] and summary['passed']
  if is_p45:
   assert w['qualifying'] and not w['diagnostic_unsealed'] and not w['cpu_rehearsal']
   assert w['build_receipt_sha256']==SEAL and w['artifacts_sha256']==headline['artifacts_sha256']
   assert (w['target_split'],w['draft_rank'],w['context'])==(23,1,4096)
   assert w['card']==(2 if name=='cards23-replicate' else 0)
   if w['card']==0:assert w['dispatch_sha256']==headline['dispatch_sha256']
   pids=set(w['launched_pids']);assert len(pids)==2 and not pids&seen_pids;seen_pids|=pids
  out=dest(name+'-confirmation-window.json');out.write_bytes(raw)
  summary_out=dest(name+'-confirmation-summary.json');summary_out.write_bytes(summary_raw)
  input_hashes[rel(source)]=sha(raw);input_hashes[rel(summary_path)]=sha(summary_raw)
  rates=[];classes={};timestamps=[];members=[]
  for row in summary['rows']:
   f=directory/'run'/row['receipt'];data=f.read_bytes();request=json.loads(data)
   if not failed_control:assert w['receipts'][str(f.relative_to(directory))]==sha(data)
   assert row['passed'] and request['passed'] and request['device_executed']
   assert len(request['tokens'])==128 and request['tokens']==headline_requests[row['prompt_id']]['tokens']
   assert request['oracle_check']['passed'] and request['oracle_check']['tokens']==128
   stamps=row['token_timestamps'] if is_p45 else row['generated_token_completion_timestamps']
   assert len(stamps)==128 and all(b>a for a,b in zip(stamps,stamps[1:]))
   rate=99/(stamps[99]-stamps[0]);assert abs(rate-(row['tok_s_1_100_intervals_after_ttft'] if is_p45 else row['submission_tok_s']))<1e-8
   rates.append(rate);timestamps.extend(stamps)
   if is_p45:
    assert row['cached_tokens']==0 and row['requested_max_new']==128 and row['repeat']==1
    classes.setdefault(row['prompt_class'],[]).append(rate)
   input_hashes[rel(f)]=sha(data);members.append(dict(path=rel(f),sha256=sha(data),raw_base64=base64.b64encode(data).decode()))
  archive=dest(name+'-confirmation-requests.json.gz');archive.write_bytes(gzip.compress(json.dumps(members,separators=(',',':')).encode(),mtime=0))
  all_prompt=statistics.median(rates)
  assert abs(all_prompt-(summary['submission100_statistics']['median'] if is_p45 else summary['submission_median_tok_s']))<1e-8
  records.append(dict(run=name,submitted_headline=name=='run1-headline',source_path=rel(directory),window_path=rel(out),window_sha256=sha(raw),summary_path=rel(summary_out),summary_sha256=sha(summary_raw),request_archive=dict(path=rel(archive),sha256=sha(archive.read_bytes())),window_passed=w['passed'],summary_passed=summary['passed'],qualifying=w.get('qualifying'),qualification_note=('Passing qualifying SPEED6 device receipt' if is_p45 else 'Failed final write admission; completed per-request measurements only, not a passing window' if failed_control else 'Passing historical packet44 device window; legacy schema lacks qualifying field'),window_error=w.get('error'),boot_id=w['boot_id'],build_receipt_sha256=w['build_receipt_sha256'],cards=[w['card'],w['card']+1],draft_rank=w.get('draft_rank',0),target_split=w.get('target_split'),all_prompt_median=all_prompt,class_balanced=statistics.median(statistics.median(v) for v in classes.values()) if classes else None,first_token_monotonic=min(timestamps),last_token_monotonic=max(timestamps),tokens_equal_headline=True,requests=len(summary['rows']),expected_prompts=12,output_tokens_per_request=128,original_request_hashes_bound_by_window=not failed_control))
 assert not (RUN/'WS128-r3').exists(),'planned third repeat unexpectedly exists; review confirmation scope'
 return dict(schema='lab.speed6-confirmation.v1',status='PARTIAL_RUN3_NOT_EXECUTED',headline='run1-headline',selection_policy='Run 1 pre-registered; no replacement or pooling',runs=records,run3=dict(executed=False,reason='Coordinator runner halted after packet44 control final-write storage admission failure'),aba_complete=False,chronological_order=sorted([dict(run=r['run'],first_token_monotonic=r['first_token_monotonic'],last_token_monotonic=r['last_token_monotonic']) for r in records],key=lambda r:r['first_token_monotonic']),control_caveat='Packet44 WS128-r3 has passed=false after completed device execution because its old 6 GB build-cap admission refused the final write. Only 8 of 12 request receipts are retained and passing, despite complete=true in the legacy summary. The 37.211 median is over those 8 rows, not a full suite. This is partial measurement evidence, not a qualifying-window pass or completed A-B-A.')

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
 for command_path in ('chains/1013-p51a-WS128.sh','chains/1010-p51a-chain.sh','runner/coordinator_windows_speed5_omp2.sh'):
  path=ROOT/'data/own-xpu-runtime-packet45-device-rounds-20261014'/command_path
  input_hashes[rel(path)]=sha(path.read_bytes())
 for name,w in windows.items():
  assert w['passed'] and w['qualifying'] and w['device_executed'] and not w['diagnostic_unsealed'] and not w['cpu_rehearsal']
  assert (w['card'],w['context'],w['draft_rank'],w['target_split'])==(0,4096,1,23)
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
   assert receipt['binary_sha256']==artifacts['device/own-rt-iq3'] and receipt['target_split']==23
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
  assert w['build_receipt_sha256']==SEAL and w['artifacts_sha256']==artifacts and w['target_split']==23 and w['draft_rank']==1
  chain.append(dict(window=name,path=rel(f),sha256=sha(raw),passed=True,device_executed=True,qualifying=True))
 s=summaries['WS128'];rows=s['rows'];class_rates={}
 for r in rows:class_rates.setdefault(r['prompt_class'],[]).append(r['tok_s_1_100_intervals_after_ttft'])
 classes={k:statistics.median(v) for k,v in class_rates.items()};headline=statistics.median(classes.values())
 assert headline==s['class_balanced_tok_s_1_100_intervals_after_ttft']['median']==39.42200890284251
 base=copy.deepcopy(read(D/(OLD+'localmaxxing-payload-queue.json'))[0]);base['label']=LABEL
 payload=base['payload'];flags=payload['engineFlags']
 identity=dict(model_revision=payload['modelRevision'],runtime_revision=REV,optimization_identity='packet45-merged3-SPEED6-tp2-c4096-target23-25-draft-rank1-right-sized-scratch-prelaunch-arena-admission-write-set-snapshot-K2-selected-kernels-native-controller-single-pass-draft-profiling',suite_sha256=manifest['suite_sha256'])
 command='OMP_NUM_THREADS=2 python3 -B experiments/own-xpu-runtime/stage2/packet45-merged3/window.py --authorized-device-window --card 0 --context 4096 --draft-rank 1 --target-split 23 --window WS128 --output <build>/speed6-c4096-dr1-s23-cards01-gpu/WS128 --k0 <K0/window.json> --k1a <..> --k1b <..> --k2 <..> --w0p <..> --kd <..> --dispatch <K2/run0/dispatch-measured.json> --suite-manifest <suite-inputs-20261012-cap128/suite-manifest.json> --controller native --repeat 1 --retain-steps none --exactness-window <WS128x/window.json>'
 assert len(command)<=600
 notes='Same Unsloth UD-IQ3_XXS model and quantization as record cmv9j70v100v1le01q9jxyx2r, on new runtime revision 34c62b433 (SPEED6). Two rank processes on two B70 cards, 23/25 target layers, official one-token MTP draft on rank 1, native controller and K2-selected kernels. Every accepted token is target-verified. Right-sized scratch and pre-launch arena admission make the split fit. Checked write-set rollback preserves full state; draft events are profiled once. Twelve fixed realistic prompts, one cold response each, 128-token cap, zero cached tokens and complete request resets; no prompt/KV/response reuse. All 1536 output tokens match immutable arithmetic-v2-detmath oracles and sequential WSs. Separate WS128x checks 9216 retained layer fixtures at steps 1-8 and 97-104. Speed window retains no fixtures. Primary rate is the median of six prompt-class medians over 99 intervals between tokens 1 and 100. This is the historical 128-token submission scope, not a 512-token natural-completion gate. Context capacity 4096 only for this split/draft placement.'
 payload.update(engineVersion=f'own-xpu-runtime packet45-merged3 SPEED6 {REV}; device binary sha256 '+artifacts['device/own-rt-iq3'],promptTokens=s['promptTokens'],outputTokens=s['outputTokens'],tokSOut=headline,tokSTotal=s['wall_rate_statistics']['median'],ttftMs=s['ttft_statistics']['median'],notes=notes)
 flags.update(benchmarkJson=rel(dest('realistic-suite-v1-result.json')),commandSnippet=command,githubResultPacket='https://github.com/steveseguin/b70-optimization-lab/blob/main/'+rel(dest('result-packet.md')),promotionIdentity=identity,promotionAttestation=rel(dest('promotion-attestation.json')),outputSha256=[r['output_token_sha256'] for r in rows],promptSha256=[r['prompt_token_sha256'] for r in rows],outputTokens=[r['output_tokens'] for r in rows],realisticPromptTokenCounts=[r['prompt_tokens'] for r in rows],realisticOutputTokenCounts=[r['output_tokens'] for r in rows],realisticSuiteGatePassed=False,localmaxxingSubmissionAllowedUnderCurrentPolicy=a.owner_128_exception,kvCacheDtype='bf16',apiKvCacheDtype='auto',hashEncoding='SHA256 of compact JSON integer token arrays, as recorded in WS128 request receipts',targetSplit=[23,25],draftRank=1,deviceCards=[0,1],bootId=performance['boot_id'],buildReceiptSha256=SEAL,dispatchSha256=performance['dispatch_sha256'],environment={'OMP_NUM_THREADS':'2'},requestedMaxNew=128,strict512TokenFinalGatePassed=False)
 flags['commandSnippetFullInEvidence']='data/own-xpu-runtime-packet45-device-rounds-20261014/chains/1013-p51a-WS128.sh (headline WS128); chain: data/own-xpu-runtime-packet45-device-rounds-20261014/chains/1010-p51a-chain.sh + data/own-xpu-runtime-packet45-device-rounds-20261014/runner/coordinator_windows_speed5_omp2.sh'
 flags['rawRealisticFinalGate']=s['realistic_final_gate']
 assert flags['rawRealisticFinalGate']==OWNER_128_RAW_GATE
 if a.owner_128_exception:
  flags['realisticSuiteScopeException']=copy.deepcopy(OWNER_128_AUTHORIZATION)
  payload['notes']+=' Owner authorization 2026-10-15: "'+OWNER_128_AUTHORIZATION['authorization_text']+'" Strict 512-cap gate remains false: '+OWNER_128_RAW_GATE['reason']+'. Requested cap: 128. Run 1 is the registered headline; higher repeats are confirmation only.'
 confirmation=confirmation_evidence(performance,requests['WS128'],input_hashes)
 confirmation_path=save('confirmation-evidence.json',confirmation)
 result=copy.deepcopy(read(D/(OLD+'realistic-suite-v1-result.json')))
 result.update(label=LABEL,generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),engine='own-xpu-runtime (stage2/packet45-merged3 SPEED6 34c62b433, native controller, two rank processes, target23/25, draft rank1)',artifacts_sha256=artifacts,promotionIdentity=identity,receipts=rel(dest('result-packet.md')))
 result['exactness'].update(retained_layer_fixtures_exact='9216/9216 in separate WS128x; none retained by WS128 speed window',authority='passing W2m, WS, WSs, WS128x device windows against immutable arithmetic-v2-detmath per-prompt oracles; byte equality, no tolerance',speculation='official one-token MTP draft head on rank 1; accepted tokens target-verified; identical tokens to fresh sequential WSs')
 result['primary_metric'].update(value_tok_s=headline,class_medians=classes)
 result['secondary'].update(decode_63_interval_median_tok_s=s['decode_median_tok_s'],wall_median_tok_s=payload['tokSTotal'],ttft_median_ms=payload['ttftMs'],prompt_tokens_median=payload['promptTokens'],output_tokens_median=payload['outputTokens'],submission100_all_prompt_statistics=s['submission100_statistics'],acceptance_statistics=s['acceptance_statistics'],ttft_statistics=s['ttft_statistics'],wall_rate_statistics=s['wall_rate_statistics'])
 result['rows']=[dict(prompt_id=r['prompt_id'],prompt_class=r['prompt_class'],prompt_tokens=r['prompt_tokens'],output_tokens=r['output_tokens'],ttft_ms=r['ttft_ms'],decode_tok_s=r['decode_tok_s'],submission_tok_s=r['tok_s_1_100_intervals_after_ttft'],wall_tok_s=r['wall_tok_s'],prompt_sha256=r['prompt_token_sha256'],output_sha256=r['output_token_sha256'],acceptance=r['acceptance'],ended_early=r['ended_early'],cached_tokens=r['cached_tokens'],finish_reason=r['finish_reason'],requested_max_new=128,full_natural_completion_tok_s=r['full_natural_completion_tok_s'],full_cap_limited_tok_s=r['full_cap_limited_tok_s'],submission100=r['submission100']) for r in rows]
 scope=dict(scope='Historical 2026-10-13 128-token-cap submission; not the strict 512-token final gate',owner_exception_authorized=a.owner_128_exception,raw_realistic_final_gate=s['realistic_final_gate'],strict_512_gate_passed=False,prepared_only=True,real_submission_performed=False)
 scope['owner_authorization']=copy.deepcopy(OWNER_128_AUTHORIZATION) if a.owner_128_exception else None
 scope['reference_submission']='cmv6pugme0020oa01fjrho6nx'
 scope['requested_max_new']=128
 scope['authorization_extension']='Coordinator authorization under owner decision, 2026-10-15: the exception scope is the fixed suite, metric and 128-token cap, not one run. The helper admits only the pinned SPEED3 and SPEED6 run-1 identities. This task permits server dry-run only; no real submission.'
 result['confirmation_evidence']=dict(path=rel(confirmation_path),sha256=sha(confirmation_path.read_bytes()),headline_selection='Run 1 pre-registered; repeats and controls are never pooled or substituted',status='PARTIAL_RUN3_NOT_EXECUTED')
 result.update(submission_scope=scope,hash_encoding=flags['hashEncoding'],quality_evidence=evidence,source_request_archives=archives)
 result_path=save('realistic-suite-v1-result.json',result)
 att=copy.deepcopy(read(D/(OLD+'promotion-attestation.json')));att.update(label=LABEL,date='2026-10-15',identity=identity,performance_evidence=dict(path=rel(result_path),sha256=sha(result_path.read_bytes())),quality_evidence=evidence,evidence=[e['path'] for e in evidence]+[rel(result_path)],submission_scope=scope)
 att['gates']['bit_exact_vs_cpu_oracles']='12/12 requests, 1536/1536 tokens in WS128; 9216/9216 retained layer fixtures in separate WS128x, byte equality'
 att['gates']['fresh_process_repeated_token_equality']='All 12 token sequences identical across independent WS, WSs, WS128x and WS128 rank-process launches; speed repeats are not pooled'
 flags['confirmationEvidence']=result['confirmation_evidence']
 att['confirmation_evidence']=result['confirmation_evidence']
 att['gates']['strict_512_token_final_gate_passed']=False
 att['gates']['kernel_log_scope']='No new signatures in each window journal tail; preflight includes historical October 11 faults, so not a clean-boot claim'
 att['seal6_amendment']=dict(rule='packet45.fix6.device-oracle-authority.2026-10-15',build_receipt_sha256=SEAL,required_device_windows=['W2m','WS','WSs','WS128x'],all_present_passing_same_artifacts=True)
 att_path=save('promotion-attestation.json',att);flags['promotionAttestationSha256']=sha(att_path.read_bytes())
 assert len(payload['notes'])<=2000
 save('localmaxxing-payload-queue.json',[base])
 save('verification.json',dict(passed=True,device_executed=False,protected_tree_read_only=True,input_sha256=input_hashes,device_window_fixture_counts=fixture_counts,performance_source=rel(RUN/'WS128/run/summary.json'),performance_source_sha256=sha((RUN/'WS128/run/summary.json').read_bytes()),source_archives=archives,chain_prerequisites=chain,distinct_window_device_pids=sorted(seen_pids),preflight_problems=preflight_payload(base),submission_scope=scope))
 print(json.dumps(dict(headline=headline,decode=s['decode_median_tok_s'],submission100=s['submission100_statistics']['median'],ttftMs=payload['ttftMs'],tokSTotal=payload['tokSTotal'],preflight=preflight_payload(base))))

if __name__=='__main__':main()
