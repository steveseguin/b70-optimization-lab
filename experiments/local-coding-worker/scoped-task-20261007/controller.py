#!/usr/bin/env python3
"""One scoped task; bounded client, fault-halt, no retry or server restart."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,time,urllib.request
ROOT=Path('/home/steve/llm-optimizations')
LANE=ROOT/'experiments/local-coding-worker/scoped-task-20261007'
OUT=Path('/home/steve/worker-scoped-task-20261007')
SERVER=OUT/'server'
PY='/home/steve/.venvs/neural-worker/bin/python'

def save(name,value):
 with (OUT/name).open('x') as f:json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def source():
 return {k:subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip() for k,args in [('head',['rev-parse','HEAD']),('status',['status','--porcelain'])]}
def healthy():
 if any((SERVER/x).exists() for x in ('STOP','FAULT.json','shutdown.json')):raise RuntimeError('Server stopping, stopped or faulted')
def supervisor():
 pid=json.loads((SERVER/'pid.json').read_text())['supervisor_pid']
 raw=Path(f'/proc/{pid}/stat').read_text();fields=raw.rsplit(')',1)[1].split()
 ticks=int(fields[19]);uptime=float(Path('/proc/uptime').read_text().split()[0]);age=uptime-ticks/os.sysconf('SC_CLK_TCK')
 cmd=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
 assert str(LANE/'serve_r276_once.py').encode() in cmd and str(SERVER).encode() in cmd,'Unexpected supervisor identity'
 assert fields[0] not in ('Z','X'),'Supervisor not alive'
 return {'pid':pid,'start_ticks':ticks,'age_s':age}
def main():
 profile=json.loads((LANE/'worker-profile.json').read_text());plan=json.loads((LANE/'runtime-plan.json').read_text())
 before=source();assert before['status']=='','Source must be clean'
 for name,want in plan['prepared_gate_artifacts'].items():assert hashlib.sha256((LANE/name).read_bytes()).hexdigest()==want,name+' gate changed'
 for name,want in plan['worker']['code_bindings'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==want,name+' changed'
 for name,want in [('task.json',plan['task']['task_sha256']),('worker-profile.json',plan['worker']['profile_sha256'])]:assert hashlib.sha256((LANE/name).read_bytes()).hexdigest()==want,name+' changed'
 assert sorted(x.name for x in (OUT/'acceptance').iterdir())==['worker_action_latency.py']
 assert hashlib.sha256((OUT/'acceptance/worker_action_latency.py').read_bytes()).hexdigest()==plan['task']['acceptance_sha256']
 assert json.loads((OUT/'boundaries/result.json').read_text())['status']=='passed'
 assert json.loads((OUT/'transport-canary/result.json').read_text())['status']=='passed'
 healthy();owner=supervisor();assert owner['age_s']<240,'Too little supervisor lifetime remains; no request'
 mem={l.split(':')[0]:int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')}
 assert mem['MemAvailable']>=24*1024**3,'Host available memory below24GiB'
 cmd=[PY,'-B',str(LANE/'run_guarded_worker.py'),'--repo',str(ROOT),'--task',str(LANE/'task.json'),'--acceptance-dir',str(OUT/'acceptance'),'--config',str(LANE/'worker-profile.json'),'--out',str(OUT/'attempt')]
 save('client-launch.json',{'command':cmd,'runtime_source':before,'supervisor':owner,'mem_available_bytes':mem['MemAvailable'],'controller_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'started_epoch':time.time(),'request_attempts_per_task':1,'wall_stop_trigger_s':900,'server_shutdown_after_task':True})
 reason=None;p=None;sent=False;begin=time.monotonic()
 def stop(signum,frame):
  nonlocal reason
  reason='controller interrupted'
 def interrupt():
  nonlocal sent
  if p is not None and p.poll() is None and not sent:
   sent=True
   try:p.send_signal(signal.SIGINT)
   except ProcessLookupError:pass
 signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
 with (OUT/'client.log').open('x') as log:
  try:
   if reason:raise RuntimeError(reason)
   healthy();p=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   while p.poll() is None:
    try:
     healthy();now=supervisor()
     if (now['pid'],now['start_ticks'])!=(owner['pid'],owner['start_ticks']):raise RuntimeError('Supervisor changed')
    except (RuntimeError,OSError,ValueError,AssertionError):reason='server stop/fault/ownership change detected'
    if time.monotonic()-begin>900:reason='client wall bound'
    if reason:interrupt()
    time.sleep(1)
  finally:
   interrupt()
   if p is not None:p.wait()
 after=source()
 save('client-exit.json',{'exit_code':p.returncode,'elapsed_s':time.monotonic()-begin,'interrupt_sent':sent,'stop_reason':reason,'no_retry':True,'source_after':after,'source_unchanged':before==after})
 return p.returncode if before==after else 1
if __name__=='__main__':
 try:raise SystemExit(main())
 finally:
  if SERVER.is_dir() and not (SERVER/'STOP').exists():
   with (SERVER/'STOP').open('x') as f:f.write('Single scoped coding task finished or admission failed; graceful stop, no retry.\n')
