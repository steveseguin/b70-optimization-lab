#!/usr/bin/env python3
"""Root-only closed replay plus one-pass final rank1 logits readback."""
import argparse,hashlib,importlib.util,json,math,os,resource,struct
from pathlib import Path
P=Path(__file__).resolve().parent;L=P.parents[2];R=L.parents[2]
C=Path('/home/steve/own-xpu-runtime-results/gsq-recurrent-f32-prefix-a.control')
E=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-recurrent-f32-prefix-a')
PLAN_SHA='393423753abf1816eb1a8ac9523af2b1ed7d73b577f91505b3249f407cd4927a'
REFERENCE_SHA='80895690ba537319cdb091b32cde971ff76d415bba667e32d337662919451b48'
FAILURE_SHA='d986a765de69b25773ed74f8076c6f4b0eb07c59781b0a5599c022ebdaac2ffe'
BINARY='5926a24746c62c6b0ecdc5c3e4895f310145e0f9d74a90a5d657035b9a8151f4'
BUILD='6cf68ff86eaa86fcec0ede752a2489121f6027e29463af474989d25ae955e01b'
RANGES={'logits.bin':496640,'position.bin':4,'token.bin':4,'next_token.bin':4}
def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
for f,h in json.loads((P/'audit-parent-pins.json').read_text()).items():need(sha(R/f)==h,'auditor parent drift '+f)
F=load(P.parent/'longer-a/audit_closed.py','prefix_closed_metadata');B=F.B
M=load(L/'recurrent-f32/logit-comparison/compare.py','prefix_logit_math')
S=load(P/'bundle_extract.py','prefix_one_pass_bundle')
read=F.read

def alignment(case,reference,result):
 need(len(reference['prompt_tokens'])==87 and len(reference['tokens'])==512,'fixed CPU case0')
 prefix=reference['prompt_tokens']+reference['tokens'][:70]
 need(case['prompt_tokens']==prefix and len(prefix)==157 and prefix[-1]==303,'audited shared157 prefix')
 need(result['tokens']==[220] and reference['tokens'][70]==264,'reproduced original divergence')
 need(B.confirmed_inputs(result,prefix)==157,'actual confirmed consumed prefix')
 return dict(input_tokens=157,generated_tokens=1,consumed_tokens=157,last_evaluated_position_zero_based=156,committed_position=157,last_consumed_token=prefix[-1],selected_token=220,reference_selected_token=264,original_generated_index_zero_based=70,conditional_prefix_ids=prefix)
def reference_row(response,reference):
 need(response['status']==200,'CPU response status');r=response['response'];probs=r['completion_probabilities']
 need(r['tokens']==reference['tokens'] and r['tokens_evaluated']==87,'CPU original prompt/token identity')
 need(len(probs)==512 and [x['id'] for x in probs]==r['tokens'],'unambiguous exact probability positions')
 need(r['generation_settings']['post_sampling_probs'] is False,'pre-sampling reference probabilities')
 row=probs[70];need(row['id']==264 and len(row['top_logprobs'])==32,'fixed reference prediction/top32')
 return row

def rounding_question(logits,reference):
 native,other=logits[220],logits[264];need(math.isfinite(native) and math.isfinite(other),'finite comparison pair')
 need(native>=other,'actual native selected versus competitor order')
 tied=native==other
 return dict(native_selected_token=220,reference_selected_token=264,native_selected_logit=native,native_reference_competitor_logit=other,native_bf16_logit_gap=native-other,native_pair_tied=tied,final_rounding_can_hide_reverse_strict_order=tied,conclusion='A BF16 tie can conceal either pre-round order; dual-store observation may localize tie-breaking.' if tied else 'Distinct finite BF16 values preserve pre-round ordering; final rounding alone cannot reverse this pair.',reference_top2_logprob_margin=reference['top_logprobs'][0]['logprob']-reference['top_logprobs'][1]['logprob'],scope='Monotonic round-to-nearest final store only; upstream BF16 activation and reference arithmetic differences remain unresolved; no quality threshold.')
def check_budget(b):
 need(b['stage']==3 and b['acknowledged']==['reset_00','last_dump','finish'] and b['remaining_payload_bytes']==0,'closed capture acknowledgements')
 need(b['metadata_reserve_bytes']==128<<20 and b['external_floor_bytes']==2<<30,'unchanged evidence reserves')
def run():
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and os.sched_getaffinity(0)<=set(range(8,16))|set(range(24,32)),'helper placement');resource.setrlimit(resource.RLIMIT_AS,(4<<30,4<<30))
 plan=read(P/'plan.json');need(F.ARTIFACTS[str(P/'plan.json')]['sha256']==PLAN_SHA,'fixed retained plan')
 need(read(C/'plan.json')==plan and F.ARTIFACTS[str(C/'plan.json')]['sha256']==PLAN_SHA,'actual control plan')
 ad=read(C/'admission.json');term=read(C/'terminal.json')
 need(term['passed'] and term['first_error'] is None and term['original_error'] is None and term['children_exited'] and term['target_descriptors_empty'],'successful closed prerequisite')
 need(ad['plan']==plan and ad['plan_sha256']==term['plan_sha256']==PLAN_SHA,'actual admission')
 need(hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()==ad['canonical_plan_sha256'],'canonical plan')
 for k,v in plan['unit_properties'].items():need(ad['unit'][k]==v,'safe unit property')
 flags=F.passive(ad['before'],term['after'],term);need(all(flags.values()),'physical ownership/drain/vision/fault gates')
 for mapping in (plan['source_sha256'],plan['suite']['source_sha256'],plan['adapter']['source_sha256']):
  for f,h in mapping.items():need(sha(R/f)==h,'source identity '+f)
 need(plan['requests']==1 and plan['suite']['requests']==1 and plan['max_new']==plan['suite']['max_new']==1 and plan['startup_max_new']==128 and plan['suite']['modes']==['none'],'one target RPC1/startup128')
 need(plan['suite']['retained_state_dumps']==2 and plan['adapter']['storage']['raw_state_bytes']==640127112,'two-group extent')
 need(plan['suite']['initial_root_free_required_bytes']==27000000000+(256<<20) and plan['suite']['initial_external_required_bytes']==3056046216,'initial admission margins')
 native=read(plan['adapter']['build_receipt']);need(F.ARTIFACTS[plan['adapter']['build_receipt']]['sha256']==BUILD==plan['adapter']['build_receipt_sha256'] and native['passed'],'native build authority')
 need(native['binary_sha256']==plan['adapter']['binary_sha256']==BINARY and B.sha(plan['adapter']['binary'])==BINARY,'actual unchanged binary')
 fp=E/'f32-prefix-replay.json';full=read(fp)
 need(term['result']['full_result_path']==str(fp) and term['result']['full_result_sha256']==F.ARTIFACTS[str(fp)]['sha256'],'closed result binding')
 need(full['passed'] and full['requests']==1 and len(full['rows'])==1 and full['normal_FINISH_and_closed_payload_verified'] and full['native_divergence_reproduced'] and full['reference_equal'] is False and full['diagnostic_only'] and not full['quality_qualified'],'diagnostic disposition')
 need(full['rank_pids']==[x[0] for x in term['rank_identities']],'same closed owners');check_budget(full['capture_budget'])
 row=full['rows'][0];raw=read(E/'prompt-00-none/request-result.json');expected=dict(row);expected.pop('state_sha256');expected.pop('capture_snapshot');need(raw==expected,'raw response/enriched map join')
 need(row['name']=='prompt-00-none' and row['mode']=='none' and row['requested_max_new']==1 and row['native_reproduction'],'fixed request')
 refpath=L/'reference-cpu/runtime-longer-a/evidence/closed-readback-review.json';ref=read(refpath);need(F.ARTIFACTS[str(refpath)]['sha256']==REFERENCE_SHA and ref['passed'] and ref['owner_exited'] and ref['returncode']==0,'closed CPU authority')
 failpath=P.parent/'longer-a/evidence/closed-metadata-review.json';failure=read(failpath);need(F.ARTIFACTS[str(failpath)]['sha256']==FAILURE_SHA and failure['classification']=='numerical_mismatch_safely_closed' and not failure['run_qualification_passed'],'original failure preserved')
 case=plan['suite']['cases'][0];need(row['prompt_tokens']==case['prompt_tokens'] and row['prompt_id']==case['id'],'admitted exact request')
 align=alignment(case,ref['cases'][0],row['result']);need(align['conditional_prefix_ids']==failure['rows'][0]['localization']['shared_input_tokens'],'original failed shared-prefix join')
 need(row['reference_comparison']['equal'] is False and row['reference_comparison']['first_difference']==0 and row['reference_comparison']['reference_tokens']==[264],'reference disagreement retained')
 need(all(row['result']['stats'][k]==0 for k in ('guesses','hits','misses')),'target-only counters');B.timing(row['result'],1)
 need(list(map(int,row['native_request'].split()))==[0,1,1,0,157,0,2,*align['conditional_prefix_ids'],248044,248046],'actual serialized RPC1')
 answer=read(Path(ref['cases'][0]['response_path']));need(F.ARTIFACTS[ref['cases'][0]['response_path']]['sha256']==ref['cases'][0]['response_sha256'],'CPU probability response identity');prob=reference_row(answer,ref['cases'][0])
 owners=[]
 for rank in (0,1):
  reset=read(E/f'prompt-00-none/rank{rank}/reset.json');need(reset['passed'] and reset['allocation_ids_preserved'],'fresh RESET acknowledged')
  rec=read(E/f'rank{rank}/receipt.json');need(rec['passed'] and rec['rank']==rank and rec['device_executed'] and not rec['error'] and len(rec['teardown'])==1,'native owner receipt');o=rec['teardown'][0];need(o['safe_to_exit'] and o['in_flight']==o['live_bytes']==o['exit_code']==0,'safe closed owner');owners.append(o)
  launch=read(C/f'ranks/rank{rank}-launch.json');argv=launch['argv'];want=plan['adapter']['rank_argv'][rank];need(len(argv)==len(want),'argv extent')
  for a,b in zip(argv,want):need((a.isdigit() if b in ('<channel-fd>','<stop-fd>') else a==b),'actual argv')
  need(launch['environment']==plan['adapter']['environment'][rank] and launch['pid']==full['rank_pids'][rank],'actual environment/PID')
 ownership=read(E/'ownership.json');need(ownership['returncodes']==[0,0] and not ownership['retained_pids'] and ownership['signals_sent']==0 and not ownership['stop_requested'] and not ownership['diagnostic_errors'],'clean process close')
 # The only payload pass: one final rank1 file, every range and full seal hash.
 capture=S.read_selected(E/'prompt-00-none/rank1/state-2147483647',RANGES)
 need(capture['payload_bytes']==125598668,'fixed corrected rank1 capture bytes')
 need(capture['logical_map']==row['state_sha256']['1'] and capture['snapshots']==row['capture_snapshot']['1'],'closed map/stamps match acknowledged DUMP')
 selected=capture.pop('captured');stored={n:struct.unpack('<I',selected[n])[0] for n in ('position.bin','token.bin','next_token.bin')}
 need(stored=={'position.bin':157,'token.bin':align['last_consumed_token'],'next_token.bin':220},'actual committed prefix counters')
 logits=M.bf16(selected['logits.bin']);need(len(logits)==248320,'full head vocabulary');comparison=M.compare(logits,prob);need(comparison['native_argmax']==220,'saved logits explain selected native token')
 question=rounding_question(logits,prob)
 for p,x in F.ARTIFACTS.items():need(F.stamp(os.stat(p,follow_symlinks=False))==x['identity'],'metadata changed after readback')
 return dict(schema='gsq.recurrent-f32.shared-prefix-replay-logits.v1',evidence_review_passed=True,diagnostic_reproduction_passed=True,reference_equal=False,quality_qualified=False,full_state_qualification=False,plan_sha256=PLAN_SHA,native_binary_sha256=BINARY,reference_review_sha256=REFERENCE_SHA,prior_failure_review_sha256=FAILURE_SHA,alignment=align,stored_context=stored,comparison=comparison,final_rounding=question,rank1_capture=capture,whole_bundle_stream_passes=1,bundle_payload_bytes_read=125598668,extracted_bytes=sum(RANGES.values()),other_bundle_payload_bytes_read=0,owners=owners,ownership=ownership,passive_checks=flags,capture_budget=full['capture_budget'],artifacts=F.ARTIFACTS,metadata_bytes_read=F.TOTAL,limitations=['One exact157-token conditional prefix only; no quality or speed certification.','Other three bundles and draft payloads are not reread; this is not a full-state qualification.','CPU retained top32 probabilities only; native float64 logsoftmax is descriptive, not an identical FP32 softmax oracle.','Failed512 run remains numerically unequal; this replay establishes the selected-token reproduction and aligned final logits.'])
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--run',action='store_true',required=True);ap.parse_args();out=P/'evidence/closed-logit-review.json'
 with out.open('x') as f:
  try:r=run()
  except BaseException as e:r={'evidence_review_passed':False,'error':repr(e),'artifacts':F.ARTIFACTS};json.dump(r,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());raise
  r['auditor_sha256']=sha(__file__);r['extractor_sha256']=sha(P/'bundle_extract.py');json.dump(r,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 print(json.dumps({'evidence_review_passed':True,'review_sha256':sha(out),'native_pair_tied':r['final_rounding']['native_pair_tied']}))
