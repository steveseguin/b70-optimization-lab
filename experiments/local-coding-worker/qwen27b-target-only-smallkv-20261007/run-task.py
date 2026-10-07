import argparse,hashlib,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
repo=Path('/home/steve/llm-optimizations')
pilot=Path('/home/steve/worker-qwen27b-smallkv-20261007')
packet=repo/'experiments/local-coding-worker/evaluation-20261007'
profile=repo/'experiments/local-coding-worker/qwen27b-target-only-smallkv-20261007/worker-profile.json'
parser=argparse.ArgumentParser();parser.add_argument('task');args=parser.parse_args()
assert args.task in ['lab-catalog-pending-headlines','lab-context-number-boundaries']
state=pilot/'server'
assert not (state/'FAULT.json').exists() and not (state/'shutdown.json').exists()
assert shutil.disk_usage('/dev/shm').free >=10*1024**3
memory={r.split(':')[0]:int(r.split()[1]) for r in Path('/proc/meminfo').read_text().splitlines()}
assert memory['MemAvailable']>=24*1024**2
assert shutil.disk_usage(pilot).free>=50*1024**3+256*1024**2
raw=Path('/dev/shm')/('worker-qwen27b-target-only-smallkv-20261007-'+args.task);raw.mkdir(exist_ok=False)
receipt=pilot/args.task;receipt.mkdir(exist_ok=False)
accept=raw/'harness-acceptance';accept.mkdir()
files={}
for source in sorted((packet/'tasks-a/acceptance').glob('*')):
 if not source.is_file():continue
 data=source.read_bytes();(accept/source.name).write_bytes(data)
 files[source.name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
(accept/'manifest.json').write_text(json.dumps({'files':files,'scope':'frozen evaluation20261007 setA'},indent=2)+'\n')
config=json.loads(profile.read_text())
campaign={'schema':'neural.download.worker-overnight-campaign.v1','review_identity_required':True,'profiles':{'qwen27b-target-only-r276-smallkv':{'config':config}},'attempts':[{'directory':'attempt','profile':'qwen27b-target-only-r276-smallkv','task_id':args.task,'kind':'task','role':'heldout'}]}
(raw/'campaign.json').write_text(json.dumps(campaign,indent=2)+'\n')
cmd=['/home/steve/.venvs/neural-worker/bin/python','-u',str(repo/'worker/run.py'),'--repo',str(repo),'--task',str(packet/'tasks-a'/(args.task+'.json')),'--acceptance-dir',str(accept),'--config',str(profile),'--out',str(raw/'attempt')]
(receipt/'launch.json').write_text(json.dumps({'command':cmd,'raw_root':str(raw),'source_commit':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),'source_snapshot_scope':'complete','scratch_medium':'existing tmpfs','configuration_changes':False},indent=2)+'\n')
child=None;stopping=False;requested_stop=False
def stop(signum=None,frame=None):
 global stopping,requested_stop
 requested_stop=True
 if child is not None and child.poll() is None and not stopping:
  stopping=True;child.send_signal(signal.SIGINT)
signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
def mirror():
 excluded={'baseline','workspace','cache','mini-config','__pycache__'}
 for directory,dirs,names in os.walk(raw):
  dirs[:]=[d for d in dirs if d not in excluded]
  for name in names:
   if name=='source.tar':continue
   source=Path(directory)/name
   if not source.is_file() or source.is_symlink():continue
   target=receipt/'live-copy'/source.relative_to(raw);target.parent.mkdir(parents=True,exist_ok=True)
   try:shutil.copy2(source,target)
   except FileNotFoundError:pass
with (receipt/'worker.log').open('w') as log:
 if requested_stop:raise RuntimeError('Stop requested before worker launch')
 child=subprocess.Popen(cmd,cwd=repo,stdout=log,stderr=subprocess.STDOUT)
 if requested_stop:stop()
 try:
  while child.poll() is None:
   if (state/'FAULT.json').exists() or (state/'shutdown.json').exists():stop()
   mirror();time.sleep(5)
 finally:
  if child.poll() is None:stop();child.wait()
  mirror()
(receipt/'exit.json').write_text(json.dumps({'returncode':child.returncode,'raw_root':str(raw),'scratch_retained_for_freeze':True,'live_copies_are_not_verified_archive':True},indent=2)+'\n')
print((raw/'attempt/result.json').read_text() if (raw/'attempt/result.json').exists() else 'No result; inspect worker.log',flush=True)
raise SystemExit(child.returncode)
