from pathlib import Path
import ast,base64,hashlib,importlib.util,json,os,re,stat,struct,sys,time
R=Path('/home/steve/llm-optimizations');P=R/'experiments/own-xpu-runtime/stage2/packet201-streaming-serving';E=P/'evidence';ST=E/'planned-a';O=ST/'output';N=O/'owner';CL=E/'client-a';OP=R/'experiments/own-xpu-runtime/ops/packet201-window';WIN=OP/'evidence/window-a'
def read(p):return json.loads(p.read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def digest(r):return hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
seal=P/'READY-FOR-DEVICE.json';manifest=read(seal);assert sha(seal)=='7d0eceb06516995ba6ab0876d9a439aef5ef920c879afe2da7a3ab0f16549383'
for name,h in manifest['source_sha256'].items():assert sha(R/name)==h,name
plan=read(OP/'actual-cpu-plan.json');profile=plan['profile'];assert digest(plan)==manifest['plan_sha256'];assert sha(Path(profile['binary']['path']))==profile['binary']['sha256']
C=load('_p201_actual_client_audit',P/'client_pilot.py');vectors,codec=C.plan();contract=load('_p201_actual_contract_audit',OP/'window.py')
w=read(O/'terminal/worker.json');pre=read(O/'terminal/pre-completion.json');restore=read(WIN/'restore-admission.json');client=read(CL/'client-result.json');adm=read(CL/'admission.json')
# Unit status is not retained raw. Replay pure structural validator with the status
# attested by the sealed controller's successful restore admission, and label scope.
contract.validate_terminal(w,plan_sha256=digest(plan),unit_status=dict(ActiveState='inactive',Result='success',ExecMainStatus='0'),passive_drained=True,precompletion=pre)
assert restore['terminal']['worker']==w and restore['terminal']['precompletion']==pre and restore['terminal']['client']==client
assert w['requests']==w['controls']==16 and w['model_loads']==w['native_process_count']==1 and w['incident_sigterm_count']==0
assert w['owner_returncode']==0 and w['stopped']==w['session']['lifecycle']['native_stopped']
assert w['stopped']==dict(event='stopped',reason='request-limit',safe_to_exit=True,completed_requests=16,completed_controls=16,discarded_pending=False,pending_request_id='')
assert adm['manifest_sha256']==sha(seal) and adm['vectors_sha256']==sha(P/'client-vectors.json') and adm['listener_events_sha256']==sha(O/'control/events.jsonl')
events=[json.loads(x) for x in (O/'control/events.jsonl').read_text().splitlines()];assert events==[dict(event='listener',address=adm['address'])] and adm['address']==w['address']
assert read(CL/'health.json')['status']==200 and read(CL/'models.json')['status']==200 and read(CL/'expected-refusal.json')['status']==400
assert read(CL/'health.json')['body']['status']=='ready';assert [x['id'] for x in read(CL/'models.json')['body']['data']]==[C.MODEL]
def strict_sse(response,request):
 raw=base64.b64decode(response['raw_sse_base64'],validate=True)
 assert 0<len(raw)<=128*1024 and hashlib.sha256(raw).hexdigest()==response['raw_sha256']
 assert raw.endswith(b'data: [DONE]\n\n') and b'\r' not in raw
 frames=raw.split(b'\n\n');assert frames.pop()==b''
 assert frames[-1]==b'data: [DONE]' and len(frames)<=request['body']['max_tokens']+4
 def pairs(values):
  out={}
  for k,v in values:assert k not in out;out[k]=v
  return out
 events=[];consumed=[];extent=0
 for frame in frames:
  assert frame.startswith(b'data: ') and b'\n' not in frame and len(frame)+1<=8192
  extent+=len(frame)+2;consumed.append(extent)
 for frame in frames[:-1]:
  event=json.loads(frame[6:].decode('utf-8',errors='strict'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(AssertionError(x)))
  assert type(event) is dict and set(event)<=set(('id','object','created','model','choices','usage'))
  assert event['id']==response['body']['id'] and event['model']==response['body']['model'] and event['created']==response['body']['created']
  assert event['object']=='chat.completion.chunk' and type(event['created']) is int and 0<=event['created']<2**63
  assert type(event['choices']) is list and len(event['choices'])==1
  choice=event['choices'][0];assert set(choice)=={'index','delta','finish_reason'} and type(choice['index']) is int and choice['index']==0
  events.append(event)
 assert events[0]['choices'][0]['delta']=={'role':'assistant','content':''} and events[0]['choices'][0]['finish_reason'] is None and 'usage' not in events[0]
 parts=[]
 for event in events[1:-1]:
  choice=event['choices'][0];delta=choice['delta']
  assert type(delta) is dict and set(delta)=={'content'} and type(delta['content']) is str and delta['content']
  delta['content'].encode('utf-8',errors='strict');assert choice['finish_reason'] is None and 'usage' not in event;parts.append(delta['content'])
 assert parts and ''.join(parts)==response['body']['choices'][0]['message']['content']
 final=events[-1];assert final['choices'][0]['delta']=={} and final['choices'][0]['finish_reason']==response['body']['choices'][0]['finish_reason']
 assert final['choices'][0]['finish_reason'] in ('stop','length') and final['usage']==response['body']['usage']
 assert set(final['usage'])=={'prompt_tokens','completion_tokens','total_tokens'} and all(type(n) is int and n>=0 for n in final['usage'].values())
 times=response['received_frames'];assert len(times)==len(frames) and type(response['elapsed_ns']) is int
 for n,(tick,offset) in enumerate(times):
  assert type(tick) is int and 0<=tick<=response['elapsed_ns'] and type(offset) is int and consumed[n]<=offset<=len(raw)
  if n:assert tick>=times[n-1][0] and offset>=times[n-1][1]
 assert times[-1][1]==len(raw) and response['done'] is True and response['sse_validated'] is True
 return dict(name=request['name'],raw_bytes=len(raw),raw_sha256=response['raw_sha256'],frames=len(frames),text_frames=len(parts),first_text_received_ns=times[1][0],finish_received_ns=times[-2][0],done_received_ns=times[-1][0],first_text_before_finish=times[1][0]<times[-2][0],scope='Client complete-frame receipt offsets only; no native token latency or disposition timestamp comparison')
rows=[];earlier={};ids=[];saves=[];sse=[]
for index,request in enumerate(vectors['rows'],1):
 h=read(CL/f'{index:02d}-http.json');saved=read(CL/f'{index:02d}-native.json');assert h['name']==request['name']
 rid=h['response']['body']['id'].removeprefix('chatcmpl-');assert re.fullmatch(r'h[0-9a-f]{32}-[0-9a-f]{16}',rid) and rid not in ids;ids.append(rid)
 nr=N/'requests'/rid/'result.json';ir=nr.parent/'input.tokens';native=read(nr);inputs=[int(x) for x in ir.read_text().splitlines()]
 checked=C.validate_turn(request,h['response'],native,codec,earlier,input_tokens=inputs)
 if request['body']['stream']:sse.append(strict_sse(h['response'],request))
 else:assert 'raw_sse_base64' not in h['response']
 baseline=request['p200_baseline'];assert inputs==baseline['input_tokens'] and native['tokens']==baseline['tokens'] and h['response']['body']['usage']==baseline['usage'] and h['response']['body']['choices'][0]['message']['content']==baseline['text']
 for k,v in checked.items():assert saved[k]==v,(index,k)
 assert saved['native_request_id']==rid and saved['native_result_sha256']==sha(nr) and saved['native_input_sha256']==sha(ir) and saved['native_input_tokens']==inputs
 assert native['arithmetic']=='iq3-p49-split32-v1' and native['gpu_count']==1 and native['decode_mode']=='plain'
 save=read(N/f'operations/parking-{index}/save.json');assert save['event']=='checkpoint-saved' and save['operation_id']==f'parking-{index}' and save['request_id']==rid
 assert save['request_disposed'] is True and save['request_quiesced'] is True and save['final_request'] is (index==16)
 assert save['path_scope']=='startup-checkpoint-root' and save['checkpoint_path']==save['checkpoint_id'] and save['receipt']==f'operations/parking-{index}/save.json'
 assert save['visible_tokens']==len(inputs)+len(native['tokens']) and save['processed_tokens']==save['visible_tokens']-1 and save['pending_token']==native['tokens'][-1]
 earlier[request['name']]=checked;saves.append(save)
 rows.append(dict(index=index,name=request['name'],request_id=rid,prompt_tokens=len(inputs),generated_tokens=len(native['tokens']),session_reuse=native['session_reuse'],cached_tokens=native['cached_tokens'],finish_reason=checked['finish_reason'],oracle_checked=checked['oracle_checked'],pair_checked=checked['pair_checked'],checkpoint_id=save['checkpoint_id'],checkpoint_manifest_sha256=save['manifest_sha256']))
assert set(q.name for q in (N/'requests').iterdir())==set(ids)
assert set(q.name for q in (N/'operations').iterdir())=={f'parking-{i}' for i in range(1,17)}
assert sum(x['generated_tokens'] for x in rows)==client['output_tokens']==1484<=1728
assert len(sse)==client['sse_requests']==client['sse_terminal_sequences']==7 and client['ordinary_requests']==9 and client['p200_exact_requests']==16
assert client['passed'] is True and client['controls_claimed'] is False and client['observed_delivery_timing_only'] is True
assert w['session']['schema']=='ownrt.streaming-serving-session.v1' and w['session']['streaming_source_sha256']==plan['streaming_sources'] and w['session']['streaming_closure_sha256']==digest(plan['streaming_sources'])
assert sum(x['oracle_checked'] for x in rows)==5 and sum(x['pair_checked'] is not None for x in rows)==1
assert rows[2]['session_reuse'] and rows[2]['cached_tokens']==saves[0]['processed_tokens']==342 and not rows[3]['session_reuse'] and not rows[4]['session_reuse']
receipt=read(N/'receipt.json');assert receipt['passed'] is True and receipt['safe_to_exit'] is True and receipt['device_executed'] is True and receipt['compute_started'] is True and receipt['error']==''
assert receipt['owner_cards']==1 and receipt['context']==4096 and receipt['cpu_affinity']==[0,1,2,3,16,17,18,19] and receipt['observed_nice']==0 and receipt['arithmetic']=='iq3-p49-split32-v1'
assert len(receipt['teardown'])==1
for t in receipt['teardown']:assert t['status']=='complete' and t['exit_code']==0 and t['safe_to_exit'] is True and t['in_flight']==t['live_bytes']==0 and t['error']==''
for x in receipt['lookup_residency']['tensors']:assert x['source_sha256']==x['resident_sha256']
d=w['diagnostics'];assert d['eof'] is True and d['incident'] is False and d['retained'] is False and d['definitely_discarded_bytes']==0
assert d['bytes_read']==d['successful_append_bytes']==(O/'stderr/native.stderr.log').stat().st_size
for q in (WIN/'terminal-passive-drain.json',WIN/'postflight-drain.json'):
 r=read(q);inv=r['privileged_passive_device_inventory'];assert inv['passed'] is True and inv['holders']==inv['errors']==[] and inv['device_opens']==0 and r['coordinator_guards_both_lanes'] is True
assert restore['passive_drain']==read(WIN/'postflight-drain.json')
for q in (O/'STOP',CL/'client-incident.json'):assert not q.exists(),q
assert (O/'terminal/retained.json').stat().st_size==0
# Parse retained journal using the pinned historical rule, with no journal command.
patterns={};fault_source=R/'experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/one-card/lineage/window_driver.py'
for node in ast.parse(fault_source.read_text()).body:
 if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call):
  for target in node.targets:
   if isinstance(target,ast.Name) and target.id in ('FAULT','DELETED'):patterns[target.id]=re.compile(ast.literal_eval(node.value.args[0]),re.I)
fault_review=read(E/'fault-review-device-a.json');journal=[json.loads(x) for x in (O/'control/kernel.jsonl').read_text().splitlines() if x.strip()]
faults=[x for x in journal if patterns['FAULT'].search(x.get('MESSAGE','')) and not patterns['DELETED'].search(x.get('MESSAGE',''))]
assert faults==fault_review['faults'] and len(faults)==fault_review['fault_count']
# Only the two currently retained states can be rehashed. Earlier states were
# deliberately evicted by policy; their save acks do not replace blob verification.
states=[];artifacts={};total_bytes=0
def bind(q):
 global total_bytes
 s=q.lstat();assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=64*1024**2,q
 key=str(q.relative_to(R));artifacts[key]=dict(bytes=s.st_size,sha256=sha(q));total_bytes+=s.st_size;return artifacts[key]['sha256']
for index,parent_state in ((15,'s1'),(16,'s2')):
 save=saves[index-1];folder=ST/'checkpoints'/save['checkpoint_id'];m=read(folder/'manifest.json');assert sha(folder/'manifest.json')==save['manifest_sha256']
 for key in ('model','engine','geometry','dtypes','tokenizer_identity'):assert m[key]==profile['identity'][key],key
 assert m['contract']=='v1.2+p198' and m['label']=='experimental-postreply-front' and m['checkpoint_id']==save['checkpoint_id']
 expected_names={b['name']+'.bin' for b in m['blobs']}|{'manifest.json','fields.tsv','tokens.bin'};assert set(q.name for q in folder.iterdir())==expected_names
 for b in m['blobs']:
  q=folder/(b['name']+'.bin');assert q.stat().st_size==b['bytes'] and bind(q)==b['sha256'],q
 for name in ('manifest.json','fields.tsv','tokens.bin'):bind(folder/name)
 raw=(folder/'tokens.bin').read_bytes();tokens=list(struct.unpack('<'+'i'*(len(raw)//4),raw));expected=vectors['rows'][index-1]['prompt_tokens']+earlier[vectors['rows'][index-1]['name']]['tokens']
 assert tokens==expected[:-1] and sha(folder/'tokens.bin')==m['token_state']['tokens_sha256'] and m['token_state']['next_token']==expected[-1]
 assert struct.unpack('<i',(folder/'next_token.bin').read_bytes())[0]==expected[-1]
 parent=(P.parent/'packet198-postreply-checkpoint/evidence/device-p198-lifecycle-A-a/checkpoints/s1/manifest.json' if index==15 else P.parent/'packet199-chat-parking/evidence/device-p199-chat-A-a/checkpoint-captures/b-park/manifest.json');pm=read(parent);bind(parent)
 assert m['blobs']==pm['blobs'] and m['token_state']==pm['token_state']
 states.append(dict(checkpoint_id=save['checkpoint_id'],blobs=len(m['blobs']),bytes=sum(q.stat().st_size for q in folder.iterdir()),manifest_sha256=save['manifest_sha256'],parent_manifest=str(parent.relative_to(R)),parent_blob_and_token_state_maps_exact=True))
assert set(q.name for q in (ST/'checkpoints').iterdir() if q.is_dir())=={x['checkpoint_id'] for x in states}
assert w['session']['parking']['bytes']==w['session']['parking']['budget']==536870912 and not w['session']['parking']['pending_delete'] and not w['session']['parking']['retained_bytes']
for directory in (N,O/'control',O/'stderr',O/'terminal',CL):
 for q in sorted(directory.rglob('*')):
  if q.is_file():bind(q)
for q in [seal,P/'client_pilot.py',P/'client-vectors.json',OP/'actual-cpu-plan.json',WIN/'preflight.json',WIN/'worker-launch.json',WIN/'client-launch.json',WIN/'terminal-passive-drain.json',WIN/'postflight-drain.json',WIN/'restore-admission.json',E/'fault-review-device-a.json']:bind(q)
assert len(artifacts)<2048 and total_bytes<512*1024**2
result=dict(sse_receipt_observations=sse,strict_sse_responses=7,ordinary_responses=9,all16_p200_baseline_prompt_tokens_text_usage_exact=True,schema='packet201.independent-device-result.v1',passed=True,audit_native_executed=False,audit_http_requests_executed=False,audit_service_or_kernel_operations=False,observed_prior_device_run=True,requests=16,controls=16,save_controls=16,release_controls=0,model_loads=1,native_processes=1,generated_tokens=1484,maximum_output_tokens=1728,full_recorded_oracles_exact=5,resumed_fresh_token_pairs_exact=1,all_consumed_prompts_exact=True,all_http_decode_finish_usage_exact=True,expected_sampling_refusal=400,native_request_inventory_exact=True,initial_activity='launch-conservative',native_stop=w['stopped'],owner_returncode=0,diagnostics=d,known_prior_faults=len(faults),new_faults_in_retained_capture=0,manifest_sha256=sha(seal),canonical_plan_sha256=digest(plan),baseline_binary=profile['binary'],precision=profile['identity']['dtypes'],context=4096,cache_bytes=profile['cache_bytes'],retained_checkpoints=states,rows=rows,artifact_count=len(artifacts),artifact_bytes=total_bytes,artifacts=artifacts,
 qualifications=['Fixed16-turn mixed local HTTP/SSE lifecycle, all16 prior p200 baselines, five earlier oracles and one resumed/fresh token pair passed.', 'Available final A/B checkpoint blobs independently rehashed and match their manifests plus retained p198 S1 (A) and p199 b-park (B) manifest state maps.', 'Independent retained passive-drain records contain no owners/errors; sealed controller admitted restoration after successful worker/client units and terminal checks.'],
 limitations=['No raw prior systemd status dictionaries retained: unit success0 is attested by sealed controller/restore-admission qualification, not independently replayed raw status; current units are collected.', 'Earlier checkpoints were normally deleted by parking policy. Append/fresh comparison independently proves exact output tokens, not rehashed state equality for deleted checkpoints.', 'Native raw stdout event stream is not retained; stopped/control protocol evidence is present in worker terminal and16 native save receipts.', 'Seven SSE payload byte streams and strict frame/terminal sequences directly replayed; nine ordinary captures retain parsed body plus original raw-response SHA, not raw HTTP bytes. Timing describes client complete-frame receipt only, not native generation latency or measured speed.', 'No cold-speed, throughput, semantic-quality-generalization, submission or broad OpenAI-compatibility claim. Native real_model_qualified remainsfalse; checkpoint experimental labels remainunchanged.', 'Restoration30 was underway during audit; its endpoint results are outside this receipt.', 'Forecast remains monitored reserve, not hard filesystem/cache quota; final parking status uses conservative256MiB reservation per retained checkpoint.'])
result['audit_script_sha256']=sha(Path(__file__))
path=E/'independent-device-result.json'
with path.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(dict(passed=True,receipt_sha256=sha(path),artifacts=len(artifacts),artifact_bytes=total_bytes,states=states,rows=[{k:x[k] for k in ('name','generated_tokens','session_reuse','finish_reason')} for x in rows])))
