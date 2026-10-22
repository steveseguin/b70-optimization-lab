"""Offline rehearsal of final submission helper on copied REAL packet136 evidence.

Historical replay preserves every measured byte and its original scope/threshold.
It is never emitted as packet190 data. The current-record guard must refuse it.
"""
import copy,gzip,hashlib,importlib.util,json,os,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];STAGE=ROOT/'experiments/own-xpu-runtime/stage2';P=STAGE/'packet190-record-bundle-k3x'
def main():
 assert shutil.disk_usage('/').free>=27_000_000_000
 sys.path.insert(0,str(ROOT/'scripts'))
 spec=importlib.util.spec_from_file_location('p190_final_submission',O/'submission_evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert m.ROOT==ROOT,'repository-root regression'
 archive=STAGE/'packet136-record-bundle/submission/prepared-a/evidence.json.gz'
 copied=O/'evidence/packet136-chain-evidence.json.gz'
 if not copied.exists():shutil.copy2(archive,copied)
 assert m.sha(copied.read_bytes())==m.sha(archive.read_bytes())
 evidence=m.Evidence(json.loads(gzip.decompress(copied.read_bytes()))['members'])
 # Historical identity only: use this final helper with the matching immutable
 # bundle8 selection functions and historical constants retained in its evidence.
 old='packet136-record-bundle';m.P56_PACKET=old;m.DEFAULT_PACKET=old;m.DYNAMIC_PACKETS=(m.D_PACKET,old);m.LINEAGE[old]=None
 sys.path.insert(0,str(STAGE/old));sys.modules.pop('bundle_selection',None)
 result=m.derive(evidence,old)
 rate=result['primary_metric']['value_tok_s']
 assert abs(rate-58.798109)<.000001 and result['realistic_final_gate']['passed'] is False
 # Same guard used by final write_prepared, checked before eligible output.
 try:m.require_new_record(rate)
 except ValueError:floor_refused=True
 else:raise AssertionError('current-record replay must be refused')
 # A changed output cannot pass after merely rehashing the evidence member.
 broken=m.Evidence(copy.deepcopy(evidence.members));key='WS128/run/summary.json'
 keys=[k for k in broken.members if k.startswith('WS128/') and k.endswith('summary.json')]
 assert keys
 key=keys[0];raw=broken.read(key);requests=raw.get('requests',raw.get('rows',[]))
 assert requests
 requests[0]['passed']=False
 b=m.encoded(raw);broken.members[key].update(raw_base64=m.base64.b64encode(b).decode(),sha256=m.sha(b))
 try:m.derive(broken,old)
 except (ValueError,AssertionError):exact_refused=True
 else:raise AssertionError('modified output admitted')
 # Packet190 k3x identity on the same real bytes (never written to a payload queue, never posted): notes cap
 # and disclosure, shared API string limits, k3x/V3/static engine flags and every identity field present.
 bundle=json.loads((P/'bundle-selection.json').read_text())
 notes=m.submission_notes(bundle);assert len(notes)<=2000
 for term in ('k3x','snapshot_host=static','layers 24-26','VERIFIED token','rank 1 starts at QSA layer 27','248,320','60.659520','strict512 false','Packet189','cmvjvabyv040jrf01dricuz8s','kernel_io=kernel','rank0_prepare=async','boundary_export=copy'):assert term in notes,term
 sim=copy.deepcopy(result);sim['bundle_selection']=bundle;sim['packet']='packet190-record-bundle-k3x'
 item=m.payload_for(sim,dict(path='rehearsal/result.json',sha256='0'*64),dict(path='rehearsal/promotion-attestation.json',sha256='0'*64),'rehearsal/result-packet.md')
 payload=item['payload'];flags=payload['engineFlags']
 spec=importlib.util.spec_from_file_location('p190_shared_submit',ROOT/'scripts/submit_localmaxxing_results.py');shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
 for field,limit in shared.API_STRING_LIMITS.items():assert field in payload and 0<len(str(payload[field]))<=limit,field
 assert payload['notes']==notes and flags['snapshotHost']=='static' and flags['v3Boundary']['rank1FirstLayer']==27 and flags['v3Boundary']['rank0Layers']=='0-26' and flags['k3xTrims']['boundaryExport']=='copy' and flags['deviceCards']==[0,1]
 assert flags['tensorParallel']==2 and flags['requestedMaxNew']==128 and flags['strict512TokenFinalGatePassed'] is False and flags['realisticSuiteGatePassed'] is False
 assert payload['hardware']['gpuCount']==2 and payload['outputTokens']==128 and payload['contextLength']==4096
 v3_identity=dict(notes_chars=len(notes),notes_cap=2000,string_limits_checked=sorted(shared.API_STRING_LIMITS),engine_flag_keys=sorted(flags),
  disclosure=['packet189 k3x (layers 24-26 on rank 0 for verified tokens, boundary rank0-k3)','kernel_io=kernel, rank0_prepare=async, boundary_export=copy','V3 head placement (full head on rank 1)','packet153 static snapshot','packet189 screen + packet188 fresh V3 reference'],
  simulated_on='packet136 real result bytes relabeled in memory only; the real payload comes from prepare_submission.py --chain on the finished packet190 chain')
 # Record-threshold update path (`prepare_submission.py --update-record RESULT --submission-id ID`) on scratch
 # copies under build/ (never the real ledger): (1) the real ledger copy refuses packet136's non-improving result
 # and stays byte-identical; (2) a scratch ledger truncated before packet136's row accepts the same real result and
 # appends exactly one validated row. The real scripts/packet49_record_threshold.json is checked unchanged.
 real_ledger=ROOT/'scripts/packet49_record_threshold.json';real_before=real_ledger.read_bytes()
 result_rel=Path('experiments/own-xpu-runtime/stage2/packet136-record-bundle/submission/prepared-a/result.json')
 historical=json.loads((ROOT/result_rel).read_text())
 updates={}
 with tempfile.TemporaryDirectory(prefix='p190-ledger-',dir=P/'build') as repo:
  repo=Path(repo).resolve()
  for rel in (result_rel,Path(historical['evidence_bundle']['path'])):
   (repo/rel).parent.mkdir(parents=True,exist_ok=True);os.link(ROOT/rel,repo/rel)
  ledger=repo/'scripts/packet49_record_threshold.json';ledger.parent.mkdir(parents=True,exist_ok=True)
  ledger.write_bytes(real_before)
  try:m.update_record(repo/result_rel,'rehearsal-not-a-submission',repo=repo)
  except ValueError as error:updates['current_ledger']=dict(refused=True,reason=str(error)[:200],unchanged=ledger.read_bytes()==real_before)
  else:raise AssertionError('non-improving record update admitted')
  policy=json.loads(real_before);keep=[r for r in policy['records'] if r['threshold_tok_s']<rate];policy['records']=keep
  ledger.write_bytes(m.encoded(policy));before=len(keep)
  row=m.update_record(repo/result_rel,'rehearsal-not-a-submission',repo=repo)
  after=json.loads(ledger.read_bytes());m.validate_threshold(after)
  assert len(after['records'])==before+1 and after['records'][-1]==row and row['threshold_tok_s']==rate and row['result']['path']==str(result_rel)
  updates['scratch_ledger']=dict(appended=True,rows_before=before,rows_after=len(after['records']),row=row)
 assert real_ledger.read_bytes()==real_before,'real record ledger changed'
 updates['real_ledger_unchanged']=True
 # Local `submission.py --dry-run` path (the coordinator's first command after prepare_submission): run through
 # packet190's wrapper on packet136's real prepared payload. No key exists in this environment (LMX_API_KEY unset,
 # HOME = an empty scratch dir), the shared CLI returns before any key read or network use in --dry-run, and the
 # packet190 validator must BLOCK the foreign payload (its runtime/seal pair is not packet190's pinned pair).
 foreign=STAGE/'packet136-record-bundle/submission/prepared-a/payload-queue.json'
 with tempfile.TemporaryDirectory(prefix='p190-nohome-',dir=P/'build') as home:
  env={k:v for k,v in os.environ.items() if k!='LMX_API_KEY'};env.update(HOME=home,OMP_NUM_THREADS='2')
  cp=subprocess.run([sys.executable,'-B',str(O/'submission.py'),'--payloads',str(foreign),'--dry-run'],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
 assert cp.returncode==2 and 'runtime/seal pair not owner-authorized' in cp.stderr and 'HTTP' not in cp.stdout,(cp.returncode,cp.stderr[-800:])
 local_dry_run=dict(command='submission.py --payloads <packet136 prepared payload-queue.json> --dry-run',returncode=cp.returncode,blocked=True,
  reason=[l.strip() for l in cp.stderr.splitlines() if l.strip().startswith('-')][:3],key_available=False,network=False,
  meaning='packet190 wrapper loads the packet190 validator; a payload not bound to packet190\'s pinned runtime/seal pair is refused before any key read',
  server_dry_run='not run: it needs the LocalMaxxing key (coordinator-only, after prepare_submission.py --chain on the finished chain)')
 row=dict(passed=True,device_executed=False,submitted=False,rehearsal_only=True,k3x_payload_identity=v3_identity,local_dry_run_negative=local_dry_run,record_update=updates,final_helper=str((O/'submission_evidence.py').relative_to(ROOT)),final_helper_sha256=m.sha((O/'submission_evidence.py').read_bytes()),copied_evidence=str(copied.relative_to(ROOT)),copied_evidence_sha256=m.sha(copied.read_bytes()),historical_packet=old,historical_rate=rate,strict512=False,current_record_floor=60.65951991975228,current_record='cmvjvabyv040jrf01dricuz8s',current_floor_refusal=floor_refused,tampered_output_refused=exact_refused,scope='Real packet136 bytes replayed unchanged under their historical identity. They are not packet190 measurements; production floor refuses them. The V3 notes/payload identity is checked on an in-memory relabel only.')
 (O/'evidence/submission-rehearsal.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row,indent=2))
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
