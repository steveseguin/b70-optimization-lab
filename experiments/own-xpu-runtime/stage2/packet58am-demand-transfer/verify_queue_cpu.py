"""Bounded real environment import/argv/preparation checks; no GPU or compilation."""
import json,os,pathlib,resource,subprocess,sys,tempfile,hashlib
P=pathlib.Path(__file__).resolve().parent;R=P.parents[3];S=P/'screen';E=P/'evidence'
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
CHILD=r'''
import sys,json,pathlib,os
S=pathlib.Path(sys.argv[1]);kind=sys.argv[2]
def audit(event,args):
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=os.fsdecode(args[0]);assert not p.endswith(('.gguf','.safetensors')) and not p.startswith(('/dev/dri/','/dev/accel/','/mnt/usb-models/','/mnt/raid-models/')),'forbidden CPU import open'
sys.addaudithook(audit);sys.path.insert(0,str(S))
import queue_runner as Q,window as W,suite_driver as D,device_memory,fault_review,release_gate
from launch_identity import unit_name
from types import SimpleNamespace
v=json.loads((S.parent/'proposals'/f'{kind}.json').read_text())
W.closed_environment();unit=unit_name(dict(name=v['job_name'],lane='A',argv=[]))
W.user_unit_gate('0::/user.slice/user@1000.service/app.slice/'+unit)
cmds=Q.commands(pathlib.Path(v['output']),0,'CPU-IMPORT-ONLY',os.environ['LD_LIBRARY_PATH'],'smoke' if kind=='smoke' else 'demand')
for stage,cmd in cmds.items():
 assert cmd[cmd.index('--output')+1]==v['output']+'/'+stage
 assert cmd[cmd.index('--card')+1]=='0'
a=SimpleNamespace(window='WSCREEN',view='smoke' if kind=='smoke' else 'demand',card=0,cache_maintenance='overlap',output=pathlib.Path(v['output'])/'WSCREEN/run',miss_mode='zerocopy')
route=W.native_command(a,pathlib.Path(v['output'])/'WSCREEN','zero-copy');assert route[2]==str(S/'suite_driver.py')
cmd=D.native_command(a,None,None);assert cmd[2:]==v['native_argv']
assert '--lookups' in cmd and cmd[cmd.index('--lookups')+1]=='resident'
assert int(cmd[cmd.index('--wait-seconds')+1])>=300
W.require(device_memory.observe([])['passed'],'empty synthetic sensor')
print(json.dumps(dict(passed=True,kind=kind,unit=unit,windows=list(cmds),native_argv_exact=True,device_executed=False,model_or_device_opened=False)))
'''
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 records=[];imports=[]
 for kind in ('smoke','v5'):
  row=json.loads((P/'proposals'/f'{kind}.json').read_text());env={'PATH':'/usr/bin:/bin',**row['environment']}
  cp=subprocess.run(['/usr/bin/python3','-B','-c',CHILD,str(S),kind],cwd=R,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
  (E/f'p58an-import-{kind}.log').write_text(cp.stdout+cp.stderr)
  imports.append(dict(kind=kind,passed=cp.returncode==0,returncode=cp.returncode,log_sha256=sha(E/f'p58an-import-{kind}.log')))
  # The actual device-define binary, actual proposed args and native mask;
  # only output and explicit CPU backend probe differ. No model file opens.
  with tempfile.TemporaryDirectory(prefix='p58an-prepare-') as tmp:
   root=pathlib.Path(tmp);env.update(HOME=str(root/'home'),NEOReadDebugKeys='1',FilterBdfPath='0000:23:00.0',ZE_ENABLE_PCI_ID_DEVICE_ORDER='1',ZE_AFFINITY_MASK='0',ONEAPI_DEVICE_SELECTOR='level_zero:0');(root/'home').mkdir()
   cmd=list(row['native_argv']);cmd[cmd.index('--output')+1]=str(root/'output');cmd+=['--cpu-preparation-probe']
   trace=E/f'p58an-prepare-{kind}.strace'
   cp=subprocess.run(['/usr/bin/strace','-f','-e','trace=openat,ioctl','-o',str(trace),*cmd],cwd=R,env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True)
   (E/f'p58an-prepare-{kind}.log').write_text(cp.stdout+cp.stderr)
   opened=any(x in trace.read_text() for x in ('/dev/dri','/dev/accel','.gguf','/mnt/usb-models','/mnt/raid-models'))
   records.append(dict(kind=kind,passed=cp.returncode==0 and not opened,returncode=cp.returncode,proposal_sha256=sha(P/'proposals'/f'{kind}.json'),binary_sha256=sha(pathlib.Path(cmd[0])),real_argv=row['native_argv'],probe_argv=cmd,model_or_device_opened=opened,trace_sha256=sha(trace),error=(cp.stdout+cp.stderr)[-2000:]))
   assert not opened,'CPU probe touched model/device path'
 rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024;assert rss<=2*1024**3
 save(E/'p58an-imports.json',dict(passed=all(r['passed'] for r in imports),records=imports,device_executed=False,max_rss_bytes=rss))
 save(E/'p58an-preparation.json',dict(passed=all(r['passed'] for r in records),records=records,device_executed=False,max_rss_bytes=rss))
 print(json.dumps(dict(imports=imports,preparation=[dict(kind=r['kind'],passed=r['passed'],error=r['error']) for r in records],max_rss_bytes=rss),indent=2))
if __name__=='__main__':main()
