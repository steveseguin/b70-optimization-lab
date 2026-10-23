#!/usr/bin/env python3
"""Finish CPU qualification and seal the additive diet chain; no device/service/queue writes."""
import argparse,datetime,hashlib,importlib.util,json,os,re,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');X=ROOT/'experiments/own-xpu-runtime'
O=X/'ops/packet196-orchestration';P=X/'stage2/packet196-onecard-diet-chain';P0=X/'stage2/packet58-onecard-cache23-chain'
FLAGS={'--wait-policy':'spin','--foreground-io':'kernel','--expert-gateup':'diet'}
CAPACITY={'--cache-cap':'max23','--cache-bytes':'23049601024'}
GATES=('diet-admission.json','diet-engine-binding.json','diet-script-argv.json','diet-tests.json','diet-submission.json','diet-final-rehearsals.json','launch-limits.json','launcher-tests.json')
ENV=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(p,row):Path(p).write_text(json.dumps(row,indent=2,ensure_ascii=False)+'\n')
def run(name,argv,cwd=ROOT):
 assert shutil.disk_usage('/').free>=27_000_000_000
 cp=subprocess.run(list(map(str,argv)),cwd=cwd,env=ENV,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=1800)
 log=P/'evidence'/f'{name}.log';log.write_text(cp.stdout+cp.stderr)
 assert cp.returncode==0,f'{name}: rc={cp.returncode}: '+(cp.stdout+cp.stderr)[-1600:]
 return cp

def generator():
 s=importlib.util.spec_from_file_location('p196_generator',O/'onecard_chain_derive.py');g=importlib.util.module_from_spec(s);s.loader.exec_module(g);g.OPS=X/'ops';return g

def binding():
 b=read(P/'engine-binding.json');checked=[]
 assert b['compiled_here'] is False
 for k in ('engine','host_parser','k1_fixture'):
  r=b[k];assert sha(P/r['path'])==r['sha256']==sha(ROOT/r['source']['parent_relpath'])==r['source']['parent_digest'];checked.append(r['path'])
 source=P/b['source_snapshot']['directory']
 for r in b['source_snapshot']['source_files']:
  assert sha(source/r['relative_path'])==r['digest'],r['relative_path']
 assert read(source/'proofs/kernel-identity.json')['passed'] and read(source/'proofs/diet-fixture.json')['passed']
 save(P/'evidence/diet-engine-binding.json',dict(passed=True,device_executed=False,compiled_here=False,compiler_runs=0,binding_sha256=sha(P/'engine-binding.json'),binaries=checked,snapshot_files=len(b['source_snapshot']['source_files']),all_snapshot_bytes_match=True))

def seal():
 g=generator();r=read(P/'build-receipt.json');exclude={'build-receipt.json','submission-pins.json','ready.json','READY-FOR-DEVICE.json','DERIVATION-READY.json'}
 files=[f for f in P.glob('*') if f.is_file() and f.suffix in g.TEXT and f.name not in exclude]
 for d in g.COPY_DIRS:files.extend(f for f in (P/d).rglob('*') if f.is_file() and '__pycache__' not in f.parts)
 gates={n:sha(P/n) for n in r['gates']}
 for n in GATES:
  p=P/'evidence'/n
  if p.exists():
   v=read(p);assert v['passed'] and v['device_executed'] is False,n;gates['evidence/'+n]=sha(p)
 r.update(sources={str(f.relative_to(ROOT)):sha(f) for f in sorted(set(files))},gates=gates,native_recompiled=False,compiled_here=False,
  engine_rebound=True,reused_qualified_screen_binary=True,qualification='packet58-onecard-diet-engine screen:60/60 exact, both diet views clear +2% and37.33456224 tok/s, no kills. Chain remains unmeasured.',
  engine_binding_sha256=sha(P/'engine-binding.json'),chain_flags=FLAGS)
 save(P/'build-receipt.json',r)
 names=('packet58_submission.py','composition.py','submission_cli.py','shared_submission_cli.py','suite_metrics.py','submission-policy.json','record-threshold.snapshot')
 save(P/'submission-pins.json',dict(schema='packet196.submission-pins.v1',build_receipt_sha256=sha(P/'build-receipt.json'),sources={str((P/n).relative_to(ROOT)):sha(P/n) for n in names},artifacts=r['artifacts'],finalized_before_chain=True))
 run('final-seal',['python3','-B',P/'seal.py','--verify'])
 run('packet-ready',['python3','-B',P/'verify_ready.py','--output',P/'ready.json'])
 bad,manifests=g.pin_audit(P,ROOT,[P/n for n in gates],parent=P0);assert not bad,bad[:8]
 return dict(sources=len(r['sources']),gates=len(gates),manifests=len(manifests),cross_packet_mutable_pins=0)

def launcher_tests():
 cp=run('launcher-tests',['python3','-B','-m','unittest','discover','-s',O,'-p','test_launcher.py'])
 save(P/'evidence/launcher-tests.json',dict(passed=True,device_executed=False,tests=3,admission_cases=12,systemctl_mocked=True,privilege_used=False,log_sha256=sha(P/'evidence/launcher-tests.log')))

def prepare():
 launcher_tests();binding();run('diet-admission',['python3','-B',O/'admission_gate.py','--verify'])
 run('diet-script-argv',['python3','-B',O/'script_argv_check.py',P,'--flags',json.dumps(dict(FLAGS,**CAPACITY)),'--json',P/'evidence/diet-script-argv.json'])
 # Fixtures are data, not the old qualification: update the synthetic command identity only.
 seal()
 cp=run('diet-tests',['python3','-B','-m','unittest','discover','-s',P,'-p','test_*.py'],cwd=P)
 count=int(re.search(r'Ran (\d+) tests',cp.stdout+cp.stderr)[1]);save(P/'evidence/diet-tests.json',dict(passed=True,device_executed=False,tests=count,log_sha256=sha(P/'evidence/diet-tests.log'),scope='CPU/mocked chain and submission tests; no device execution'))
 cp=run('diet-submission',['python3','-B',P/'rehearse_submission.py'],cwd=P)
 row=read(P/'evidence/submission-rehearsal-cache23.json');assert row['passed'] and row['notes_characters']<=2000 and row['network_used'] is False
 row.update(schema='packet196.submission-rehearsal.v1',device_executed=False,validator_sha256=sha(P/'packet58_submission.py'));save(P/'evidence/diet-submission.json',row)
 # Closed environment/limits checks and exact manual command properties.
 sys.path.insert(0,str(P));sys.path.insert(0,str(X/'ops'))
 import launch_env,exec_limits,window
 binary_checks={n:launch_env.check_binary(P/n) for n in read(P/'build-receipt.json')['artifacts']}
 assert all(r['passed'] for r in binary_checks.values());exec_limits.check()
 derived=read(P/'derived-chain.json');cmd=derived['chain_command']
 for text in ('--unit=packet58-onecard-diet-a','--property=Restart=no','--property=SendSIGKILL=no','--property=TimeoutStopSec=infinity','--property=Nice=0','/usr/bin/taskset -c 0-3,16-19','/usr/bin/env -i PATH=/usr/bin:/bin',' OMP_NUM_THREADS=2','--view down-tile16'):
  assert text in cmd,text
 assert 'LD_LIBRARY_PATH='+launch_env.library_path()+' ' in cmd
 writes=sum(window.WRITES['K1' if n.startswith('K1') else n] for n in ('K1a','K1b','KD','W2m','WS','WS128x','WS128'));assert writes==397492208
 save(P/'evidence/launch-limits.json',dict(passed=True,device_executed=False,planned_write_bytes=writes,host_floor_bytes=100487123456,launcher_host_floor_bytes=101560865280,root_free_floor_bytes=25000000000+writes,binaries=binary_checks,chain_command_digest_sha256=hashlib.sha256(cmd.encode()).hexdigest(),native_executed='ldd only in entry sandbox'))
 seal();g=generator();pre=g.predevice_gate(P);post=g.postnative_gate(P,P0/'evidence/card0-cache23-a');missing,checked=g.closure_check(P,P0,ROOT);assert not missing,missing
 save(P/'evidence/diet-final-rehearsals.json',dict(passed=True,device_executed=False,predevice=pre,postnative=post,closure_checked=checked,closure_missing=missing))
 seal()
 # Temporary lanequeue plan only; it cannot publish a live queue row.
 with tempfile.TemporaryDirectory(prefix='p196-plan-',dir=P/'build') as tmp:
  temp=Path(tmp);(temp/'queue-A.txt').write_bytes((O/'entry-proposal.jsonl').read_bytes())
  run('diet-private-plan',['python3','-B',X/'ops/lane-queue/lanequeue.py','plan','--lane','A','--directory',temp])
 run('launcher-syntax',['bash','-n',O/'launch_chain.sh'])
 print(json.dumps(dict(passed=True,prepared=True,ready_written=False)))

def verify():
 for leaf in GATES:
  row=read(P/'evidence'/leaf);assert row['passed'] and row['device_executed'] is False,leaf
 binding_row=read(P/'evidence/diet-engine-binding.json');assert binding_row['binding_sha256']==sha(P/'engine-binding.json')
 r=read(P/'build-receipt.json');assert r['native_recompiled'] is False and r['compiled_here'] is False
 for root,key in ((ROOT,'sources'),(P,'artifacts'),(P,'gates')):
  for n,h in r[key].items():assert sha(root/n)==h,n
 derived=read(P/'derived-chain.json');sel=read(P/'runtime-selection.json')
 assert sel['chain_flags']==derived['flags']==FLAGS and sel['cache_cap']=='max23' and sel['cache_bytes']==sel['cache_allocation_bytes']==23049601024
 assert not (ROOT/derived['chain_output']).exists() and not (P/'evidence/fault-review-diet-a.json').exists()
 assert read(ROOT/'scripts/packet58_onecard_record_threshold.json')['records'][-1]['threshold_tok_s']==36.60251162011413
 assert read(P/'evidence/diet-admission.json')['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 assert (O/'entry-proposal.jsonl').read_text().count('100487123456')==1
 run('final-seal-verify',['python3','-B',P/'seal.py','--verify'])
 run('final-packet-ready',['python3','-B',P/'verify_ready.py','--output',P/'ready.json'])
 g=generator();bad,ms=g.pin_audit(P,ROOT,[P/n for n in r['gates']],parent=P0);assert not bad,bad[:8]
 return dict(passed=True,device_executed=False,compiled_here=False,compiler_runs=0,engine_rebound=True,chain_command_digest_sha256=hashlib.sha256(derived['chain_command'].encode()).hexdigest(),
   gates={n:sha(P/n) for n in r['gates']},pin_audit=dict(passed=True,manifests=len(ms),cross_packet_mutable_pins=0),
   host_required_available_bytes=100487123456,planned_write_bytes=397492208,root_free_bytes=shutil.disk_usage('/').free)

def ready():
 assert not (P/'READY-FOR-DEVICE.json').exists() and not (O/'READY-FOR-DEVICE.json').exists()
 result=verify();save(P/'evidence/final-checks.json',result)
 row=read(O/'DERIVATION-READY.json');derived=read(P/'derived-chain.json');r=read(P/'build-receipt.json')
 # Replace stale generated source maps with the final closure. Ops sources are also pinned.
 row.update(schema='packet196.ready.v1',generator='packet196-orchestration private additive adapter + finalize.py',
   reason='Exact expert instruction diet; qualified screen clears registered chain bar. Candidate chain not yet measured.',
   final_checks_sha256=sha(P/'evidence/final-checks.json'),last_packet_write=True,final_content_write=True,
   compiled_here=False,native_recompiled=False,reused_qualified_screen_binary=True,engine_rebound=True,
   host_required_available_bytes=100487123456,launcher_host_floor_bytes=101560865280,planned_write_bytes=397492208,
   files_sha256={str((P/n).relative_to(ROOT)):sha(P/n) for n in ('build-receipt.json','submission-pins.json','ready.json','derived-chain.json','engine-binding.json','runtime-selection.json','evidence/final-checks.json')},
   gates={str((P/n).relative_to(ROOT)):h for n,h in result['gates'].items()},pin_audit=result['pin_audit'],launcher='ops/packet196-orchestration/launch_chain.sh',
   orchestration_provenance=[dict(name=f.name,parent_relpath=str(f.relative_to(ROOT)),parent_digest=sha(f)) for f in sorted(O.iterdir()) if f.is_file() and f.name not in ('READY-FOR-DEVICE.json',)],
   prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),chain_quality_pending=True,chain_performance_pending=True,no_retry=True)
 # Explicit ops pin map: generated helpers are required launch inputs, not just prose provenance.
 row['orchestration_source_pins']=[dict(relative_path=str(f.relative_to(ROOT)),digest=sha(f)) for f in sorted(O.iterdir()) if f.is_file() and f.suffix in ('.py','.sh')]
 for item in row['orchestration_source_pins']:assert sha(ROOT/item['relative_path'])==item['digest']
 for f in (P/'READY-FOR-DEVICE.json',O/'READY-FOR-DEVICE.json'):save(f,row)
 g=generator();bad,ms=g.pin_audit(P,ROOT,[P/n for n in r['gates']],parent=P0)
 if bad:
  for f in (P/'READY-FOR-DEVICE.json',O/'READY-FOR-DEVICE.json'):f.rename(f.with_name('WITHDRAWN-READY.json'))
  raise AssertionError(bad[:8])
 print(json.dumps(dict(passed=True,ready=True,source_pins=len(r['sources']),gates=len(r['gates']))))

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert shutil.disk_usage('/').free>=27_000_000_000
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--ready',action='store_true');a=ap.parse_args()
 if a.prepare:prepare()
 elif a.ready:ready()
 else:print(json.dumps(verify()))
if __name__=='__main__':main()
