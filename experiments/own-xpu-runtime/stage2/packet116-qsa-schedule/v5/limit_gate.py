"""CPU audit: device entry imports cannot impose resource limits or launch."""
import hashlib,json,os,resource,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4]
def main():
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 before=resource.getrlimit(resource.RLIMIT_AS)
 def audit(event,args):
  if event in ('resource.setrlimit','subprocess.Popen','os.system','os.exec','os.posix_spawn'):
   raise RuntimeError('forbidden during device-entry import: '+event)
 sys.addaudithook(audit)
 import bracket_job,cpu_seal,screen,tp2_worker,bracket,compare
 assert resource.getrlimit(resource.RLIMIT_AS)==before
 sources={}
 for module in list(sys.modules.values()):
  name=getattr(module,'__file__',None)
  if name and Path(name).is_file() and Path(name).resolve().is_relative_to(ROOT):
   f=Path(name).resolve();sources[str(f.relative_to(ROOT))]=hashlib.sha256(f.read_bytes()).hexdigest()
 row=dict(passed=True,device_executed=False,imports=['bracket_job','cpu_seal','screen','tp2_worker','bracket','compare'],resource_limits_unchanged=True,limit_or_launch_calls=0,sources=sources,scope='CPU main sets its own 8 GiB bound before installing the audit; all subsequent device-import resource changes and subprocess launches refuse.')
 (P/'evidence/import-limits.json').write_text(json.dumps(row,indent=2)+'\n')
 print('device-entry import closure: no limits, no launches')
if __name__=='__main__':main()
