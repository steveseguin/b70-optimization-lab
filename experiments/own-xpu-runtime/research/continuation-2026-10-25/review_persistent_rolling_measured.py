import sys,json,hashlib,gzip,pathlib,datetime
ROOT=pathlib.Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime'); H=ROOT/'research/continuation-2026-10-25'
sys.path[:0]=[str(H),str(ROOT/'engine/tools'),str(ROOT/'engine/planning')]
import finalize_persistent_rolling_proof as F
from persistent_ring_policy import validate_policy
R=pathlib.Path('/dev/shm/sc117-ring-20261025/persistent-rolling-measured-a');P=H/'persistent-rolling-measured-proof'
def read(p):return json.loads(pathlib.Path(p).read_text())
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def ident(p):p=pathlib.Path(p);return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
plan=read(R/'plan.json');summary=read(P/'summary.json');terminal=read(R/'persistent-rolling-result.json');suite=read(P/'runtime-inputs.json');recursive=read(P/'recursive-reference.json')
assert F.validate_identity(plan,suite,terminal,recursive)=='measured'

qualified=H/'persistent-rolling-qualified-proof'
assert sha(qualified/'summary.json')==summary['qualified_reference']['sha256']
assert summary['qualified_reference_parity'] is True and all(x['qualified_reference_parity'] is True for x in summary['request_summaries'])
from persistent_rolling_suite_audit import validate_prerequisite_record,validate_prerequisite_closure
qsummary=read(qualified/'summary.json');qplan=validate_prerequisite_record(qsummary,qualified/'plan.json','qualification')
validate_prerequisite_record(summary,P/'plan.json','measured',qualified/'summary.json')
closure=validate_prerequisite_closure(plan,qplan)

assert sha(R/'plan.json')==summary['original_plan']['sha256']==read(R/'admission.json')['plan_sha256']
assert sha(R/'persistent-rolling-result.json')==summary['original_result']['sha256']
for key in ('finalizer','comparator'):assert sha(summary[key]['path'])==summary[key]['sha256']
pins=[]
for p,w in plan['pins'].items():
 assert sha(p)==w,p
 pins.append(dict(path=p,sha256=w))
build=read('/dev/shm/engine-build-ring-persistent-20261025/build-receipt.json')
native=[]
for p,w in build['sources'].items():
 p=str(ROOT/'engine/src'/p)
 assert sha(p)==w,(p,w)
 native.append(dict(path=p,sha256=w))
unit=read(R/'unit.json');assert unit['Restart']=='no' and unit['KillMode']=='process' and unit['SendSIGKILL']=='no'
launches=[read(R/f'stage{i}/launch.json') for i in range(4)]
assert len({x['pid'] for x in launches})==4
known={str(x['pid']):x['identity']['start_ticks'] for x in launches}
obs=F.lines(R/'observations.jsonl');base=read(H/'host-ring-persistent-measured-admission.json')
for o in obs:
 assert o['boot']==base['boot'] and o['kernel']['faults']==base['kernel']['faults'] and o['known_fault_baseline_matches'] is True
 assert not o['identity_races'] and not o['inventory']['errors']
 assert o['metadata_only'] and all(o[k]==0 for k in ('device_api_calls','device_opens','service_changes'))
 for pid,rec in o['holders'].items():assert known[pid]==rec['start_ticks']
requests=[];prev_request=plan['request_sha256'];prev_seq=[0]*4;prev_pos=0;inventories=None;metadata_sources={};raw_sources={}
records=read(R/'suite-result.json')['requests']
for i,(row,record,rs) in enumerate(zip(suite['prompts'],records,summary['request_summaries'])):
 rd=R/f"request-{i:02d}-{row['id']}";pd=P/rd.name;assert record==read(rd/'result.json')
 reset=F.audit_reset(plan,row,record,F.lines(rd/'reset-commands.jsonl'),previous_request=prev_request,previous_sequences=prev_seq,previous_target_position=prev_pos,prior_inventories=inventories,read_raw=lambda p:F.survival_bytes(p)[0])
 assert reset==rs['reset_audit']
 outputs=record['output_ids'];assert outputs==recursive['target_output_ids'];assert len(outputs)==32
 batches=F.lines(rd/'provider-batches.jsonl');native0=pathlib.Path(record['reset_receipts'][0]['native_output']);meta=read(native0/'pipeline-stage.json')
 replay=F.audit_controller(F.lines(rd/'commands.jsonl'),F.lines(rd/'final-records.jsonl'),batches,row['prompt_tokens'],outputs,reset['request_sha256'],4,meta['stream_bytes'],plan['vocab'],plan['context'],epoch=reset['epoch'],initial_sequences=record['initial_sequences'],check_policy='measured',max_new=32)
 assert [s['last_sequence'] for s in replay['states']]==record['final_sequences']
 counts=[]
 for j in range(4):
  n=pathlib.Path(record['reset_receipts'][j]['native_output']);att=read(n/f'state-{2000000000+i}.ring-state.json')
  validate_policy(att,policy='measured',first=j==0)
  rows=F.lines(n/'ring.jsonl');assert all(a['tentative']==b['tentative'] for a,b in zip(rows,replay['sent'][j]))
  audit=F.audit_native(rows,replay['sent'][j],replay['created'],row['prompt_tokens']+outputs[:-1],att,j==3)
  assert dict(stage=j,**audit)==rs['native_command_audits'][j]
  counts.append({k:att[k] for k in ('stage_id','rows','commits','abort_count','discarded_rows','target_snapshot_restores','target_host_restore_checks','byteverified_restore_count')})
  if j==0:
   provider=F.audit_provider(batches,F.lines(n/'ring-draft-batches.jsonl'),recursive,replay,len(row['prompt_tokens']),att,reset['request_sha256'],epoch=reset['epoch'],policy='measured');assert json.loads(json.dumps(provider))==rs['provider_audit']
   assert (n/'ring-provider-survival.jsonl').read_bytes()==b'' and rs['survival_audit'] is None
   assert att['provider_survival_records']==att['provider_survival_advanced_records']==att['provider_byteverified_restore_count']==0
   assert att['provider_all_restores_byte_verified'] is False
   assert att['provider_snapshot_captures']==att['provider_snapshot_restores']==att['provider_host_restore_checks']==32
   assert att['provider_canonical_commands_checked']==att['provider_commands']==117
 for kind,total in [('target',2065),('draft',73),('qualified-target',2065),('qualified-draft',73)]:
  cp=pd/f'{kind}-comparison.json.gz';comp=json.loads(gzip.decompress(cp.read_bytes()));assert comp['passed'] and comp['errors']==[] and len(comp['compared_source_keys'])==total
  for source in comp['candidate']['sources']:
   p=pathlib.Path(source['path']);assert p.stat().st_size==source['bytes']
   if p.name=='state.bundle':raw_sources[str(p)]=source
   else:
    assert sha(p)==source['sha256'],p
    metadata_sources[str(p)]=source
    if p.name=='state-seal.txt':
     seal=p.read_text().splitlines();assert seal[0]=='GSQ_STATE_SEAL_V1' and len(seal)==5
     bundle=p.with_name('state.bundle');assert bundle.stat().st_size==int(seal[1])
     assert sha(p.with_name('state-index.tsv'))==seal[3] and sha(p.with_name('state.json'))==seal[4]
     raw_sources[str(bundle)]=dict(path=str(bundle),bytes=int(seal[1]),sha256=seal[2])
 assert replay['actual_proposal_rows']==rs['actual_proposal_rows']
 requests.append(dict(index=i,epoch=reset['epoch'],outputs=32,input_rows=118,target_buffers_exact=2065,draft_allocations_exact=73,actual_proposal_rows=replay['actual_proposal_rows'],pending_borrows=rs['pending_borrows'],survival_checks=0,advanced_survival_checks=0,miss_depths=rs['observed_miss_depths'],mandatory_counters=counts,reset_post_sequences=reset['post_sequences']))
 prev_request=reset['request_sha256'];prev_seq=reset['post_sequences'];prev_pos=118;inventories=reset['inventories']
for source in summary['raw_bundles']:
 v=raw_sources[source['path']];assert all(v[k]==source[k] for k in ('bytes','sha256'))
assert len(raw_sources)==10
archive=read(H/'persistent-rolling-measured-full-archive.json');assert archive['passed'] and archive['qualified_bundles']==10
review=dict(schema='ownrt.persistent-rolling-independent-review.v1',passed=True,reviewed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),run=str(R),proof=str(P),sources=[ident(p) for p in [R/'plan.json',R/'persistent-rolling-result.json',R/'observations.jsonl',P/'summary.json',H/'persistent-rolling-measured-full-archive.json']],check_policy='measured',qualified_policy_execution_closure=closure,qualified_reference=ident(qualified/'summary.json'),native_binary_sha256=build['binary_sha256'],runtime_pins_verified=len(pins),native_source_pins_verified=len(native),small_state_source_hashes_verified=len(metadata_sources),raw_bundles_bound_to_comparison=10,raw_state_reread=False,requests=requests,terminal=dict(returncodes=terminal['returncodes'],live_pids=terminal['live_pids']),passive=dict(samples=len(obs),first_utc=obs[0]['utc'],last_utc=obs[-1]['utc'],same_boot=True,new_fault_entries=0,historical_fault_entries=len(base['kernel']['faults']),all_holders_match_launched_pid_and_start_ticks=True,last_sample_holders=obs[-1]['holders'],post_exit_sample_present=False),limits=['Two repeated 87-token prompts with 32 outputs each; not a twelve-prompt performance result.','State equality relies on authenticated frozen comparator receipts and sealed source identities; this review did not reread 889 MB of raw allocation payloads.','Both requests exercised target two-row suffix rollback, but actual provider pending-depth2 borrowing was zero; provider depth1 borrowing was observed.','Cold reset bytes were not individually read back; native cold metadata, actual reset chain and exact per-request terminal states were checked.','Measured policy disables per-operation target/provider byte checks and provider-abort survival readbacks; zeros/false/empty evidence explicitly checked. Exact terminal target/draft parity holds against both accepted baseline and qualified policy. No speed, early-EOS, cancellation or portable-deployment claim.','Final passive sample predates last worker exit; clean exit is independently reported by terminal process return codes.','Archive helper receipt checked; independent archive decompression/durable restore belongs to parent archive gate.'])
out=H/'persistent-rolling-measured-independent-review.json';out.write_text(json.dumps(review,indent=2)+'\n');print(json.dumps(dict(path=str(out),sha256=sha(out),requests=requests,runtime_pins=len(pins),native_pins=len(native)),indent=2))
