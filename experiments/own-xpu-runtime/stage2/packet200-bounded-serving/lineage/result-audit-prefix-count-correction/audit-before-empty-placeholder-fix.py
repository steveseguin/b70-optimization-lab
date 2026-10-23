from pathlib import Path
import ast,hashlib,importlib.util,json,os,re,stat,struct,sys,time
R=Path('/home/steve/llm-optimizations');P=R/'experiments/own-xpu-runtime/stage2/packet200-bounded-serving';E=P/'evidence';ST=E/'planned-a';O=ST/'output';N=O/'owner';CL=E/'client-a';OP=R/'experiments/own-xpu-runtime/ops/packet200-window';WIN=OP/'evidence/window-a'
def read(p):return json.loads(p.read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def digest(r):return hashlib.sha256(json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
seal=P/'READY-FOR-DEVICE.json';manifest=read(seal);assert sha(seal)=='3f9a18abe109800e8c8023769bd4d5c3d34c9e6e93e36fcb9916951c2f873d6a'
for name,h in manifest['source_sha256'].items():assert sha(R/name)==h,name
plan=read(OP/'actual-cpu-plan.json');profile=plan['profile'];assert digest(plan)==manifest['plan_sha256'];assert sha(Path(profile['binary']['path']))==profile['binary']['sha256']
C=load('_p200_actual_client_audit',P/'client_pilot.py');vectors,codec=C.plan();contract=load('_p200_actual_contract_audit',OP/'window.py')
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
rows=[];earlier={};ids=[];saves=[]
for index,request in enumerate(vectors['rows'],1):
 h=read(CL/f'{index:02d}-http.json');saved=read(CL/f'{index:02d}-native.json');assert h['name']==request['name']
 rid=h['response']['body']['id'].removeprefix('chatcmpl-');assert re.fullmatch(r'h[0-9a-f]{32}-[0-9a-f]{16}',rid) and rid not in ids;ids.append(rid)
 nr=N/'requests'/rid/'result.json';ir=nr.parent/'input.tokens';native=read(nr);inputs=[int(x) for x in ir.read_text().splitlines()]
 checked=C.validate_turn(request,h['response'],native,codec,earlier,input_tokens=inputs)
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
assert sum(x['oracle_checked'] for x in rows)==5 and sum(x['pair_checked'] is not None for x in rows)==1
assert rows[2]['session_reuse'] and rows[2]['cached_tokens']==saves[0]['processed_tokens']==342 and not rows[3]['session_reuse'] and not rows[4]['session_reuse']
receipt=read(N/'receipt.json');assert receipt['passed'] is True and receipt['safe_to_exit'] is True and receipt['device_executed'] is True and receipt['compute_started'] is True and receipt['error']==''
assert receipt['owner_cards']==1 and receipt['context']==4096 and receipt['cpu_affinity']==[0,1,2,3,16,17,18,19] and receipt['observed_nice']==0 and receipt['arithmetic']=='iq3-p49-split32-v1'
assert len(receipt['teardown'])==1
for t in receipt['teardown']:assert t['status']=='complete' and t['exit_code']==0 and t['safe_to_exit'] is True and t['in_flight']==t['live_bytes']==0 and t['error']==''
for x in receipt['lookup_residency']['tensors']:assert x['source_sha256']==x['resident_sha256']
d=w['diagnostics'];assert d['eof'] is True and d['incident'] is False and d['retained'] is False and d['definitely_discarded_bytes']==0
assert d['bytes_read']==d['successful_append_bytes']==(O/'stderr/native.stderr.log').stat().st_size==170
for q in (WIN/'terminal-passive-drain.json',WIN/'postflight-drain.json'):
 r=read(q);inv=r['privileged_passive_device_inventory'];assert inv['passed'] is True and inv['holders']==inv['errors']==[] and inv['device_opens']==0 and r['coordinator_guards_both_lanes'] is True
assert restore['passive_drain']==read(WIN/'postflight-drain.json')
for q in (O/'STOP',CL/'client-incident.json',O/'terminal/retained.json'):assert not q.exists(),q
# Parse retained journal using the pinned historical rule, with no journal command.
patterns={};fault_source=R/'experiments/own-xpu-runtime/stage2/packet181-session-swap-v3/one-card/lineage/window_driver.py'
for node in ast.parse(fault_source.read_text()).body:
 if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call):
  for target in node.targets:
   if isinstance(target,ast.Name) and target.id in ('FAULT','DELETED'):patterns[target.id]=re.compile(ast.literal_eval(node.value.args[0]),re.I)
fault_review=read(E/'fault-review-device-a.json');journal=[json.loads(x) for x in (O/'control/kernel.jsonl').read_text().splitlines() if x.strip()]
faults=[x for x in journal if patterns['FAULT'].search(x.get('MESSAGE','')) and not patterns['DELETED'].search(x.get('MESSAGE',''))]
assert faults==fault_review['faults'] and len(faults)==2
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
 parent=P.parent/f'packet198-postreply-checkpoint/evidence/device-p198-lifecycle-A-a/checkpoints/{parent_state}/manifest.json';pm=read(parent);bind(parent)
 assert m['blobs']==pm['blobs'] and m['token_state']==pm['token_state']
 states.append(dict(checkpoint_id=save['checkpoint_id'],blobs=len(m['blobs']),bytes=sum(q.stat().st_size for q in folder.iterdir()),manifest_sha256=save['manifest_sha256'],parent_manifest=str(parent.relative_to(R)),parent_blob_and_token_state_maps_exact=True))
assert set(q.name for q in (ST/'checkpoints').iterdir() if q.is_dir())=={x['checkpoint_id'] for x in states}
assert w['session']['parking']['bytes']==w['session']['parking']['budget']==536870912 and not w['session']['parking']['pending_delete'] and not w['session']['parking']['retained_bytes']
for directory in (N,O/'control',O/'stderr',O/'terminal',CL):
 for q in sorted(directory.rglob('*')):
  if q.is_file():bind(q)
for q in [seal,P/'client_pilot.py',P/'client-vectors.json',OP/'actual-cpu-plan.json',WIN/'preflight.json',WIN/'worker-launch.json',WIN/'client-launch.json',WIN/'terminal-passive-drain.json',WIN/'postflight-drain.json',WIN/'restore-admission.json',E/'device-unit-observations.json',E/'fault-review-device-a.json']:bind(q)
assert len(artifacts)<2048 and total_bytes<512*1024**2
result=dict(schema='packet200.independent-device-result.v1',passed=True,audit_native_executed=False,audit_http_requests_executed=False,audit_service_or_kernel_operations=False,observed_prior_device_run=True,requests=16,controls=16,save_controls=16,release_controls=0,model_loads=1,native_processes=1,generated_tokens=1484,maximum_output_tokens=1728,full_recorded_oracles_exact=5,resumed_fresh_token_pairs_exact=1,all_consumed_prompts_exact=True,all_http_decode_finish_usage_exact=True,expected_sampling_refusal=400,native_request_inventory_exact=True,initial_activity='launch-conservative',native_stop=w['stopped'],owner_returncode=0,diagnostics=d,known_prior_faults=2,new_faults_in_retained_capture=0,manifest_sha256=sha(seal),canonical_plan_sha256=digest(plan),baseline_binary=profile['binary'],precision=profile['identity']['dtypes'],context=4096,cache_bytes=profile['cache_bytes'],retained_checkpoints=states,rows=rows,artifact_count=len(artifacts),artifact_bytes=total_bytes,artifacts=artifacts,
 qualifications=['Fixed16-turn bounded local HTTP lifecycle and exact token/reference checks passed.', 'Available final A/B checkpoint blobs independently rehashed and match their manifests plus retained p198 S1/S2 manifest state maps.', 'Independent retained passive-drain records contain no owners/errors; sealed controller admitted restoration after successful worker/client units and terminal checks.'],
 limitations=['No raw prior systemd status dictionaries retained: unit success0 is attested by sealed controller/restore-admission qualification, not independently replayed raw status; current units are collected.', 'Earlier checkpoints were normally deleted by parking policy. Append/fresh comparison independently proves exact output tokens, not rehashed state equality for deleted checkpoints.', 'Native raw stdout event stream is not retained; stopped/control protocol evidence is present in worker terminal and16 native save receipts.', 'HTTP captures retain parsed body and original raw-response SHA but not original HTTP byte stream; replay verified parsed content/usage against actual native tokens.', 'No cold-speed, throughput, semantic-quality-generalization, submission or broad OpenAI-compatibility claim. Native real_model_qualified remainsfalse; checkpoint experimental labels remainunchanged.', 'Restoration29 was underway during audit; its endpoint results are outside this receipt.', 'Forecast remains monitored reserve, not hard filesystem/cache quota; final parking status uses conservative256MiB reservation per retained checkpoint.'])
path=E/'independent-device-result.json'
with path.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(dict(passed=True,receipt_sha256=sha(path),artifacts=len(artifacts),artifact_bytes=total_bytes,states=states,rows=[{k:x[k] for k in ('name','generated_tokens','session_reuse','finish_reason')} for x in rows])))
