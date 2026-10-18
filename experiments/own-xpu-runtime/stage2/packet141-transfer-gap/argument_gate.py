"""Intercept both actual rank execs; no process, device or shared-state writes."""
import argparse,importlib.util,json,os,resource,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
class Reached(BaseException):pass
class Forbidden(BaseException):pass

def sandbox(tmp):
 def audit(event,args):
  if event=='open' and isinstance(args[0],(str,bytes)):
   p=Path(os.fsdecode(args[0])).absolute()
   if str(p).startswith('/dev/dri/') or p.suffix=='.gguf':raise Forbidden('device/model read')
   if (args[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
    if p!=Path('/dev/null') and not p.resolve().is_relative_to(tmp):raise Forbidden('write outside scratch: '+str(p))
  if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):raise Forbidden('unexpected execution')
 sys.addaudithook(audit)

def probe():
 from exec_limits import snapshot,check
 before=snapshot();check()
 import capture_identity as I
 import capture_worker as C
 import run_capture as R
 from devices import masked_environment
 from types import SimpleNamespace
 q=ROOT/'experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py'
 spec=importlib.util.spec_from_file_location('p141_lanequeue',q);L=importlib.util.module_from_spec(spec);sys.modules[spec.name]=L;spec.loader.exec_module(L)
 proposal=q.parent/'proposed-p141-probe-B.txt';job=json.loads(proposal.read_text());L.validate(job,'B')
 env=L.closed_env('/opt/intel/oneapi/compiler/2026.0/lib')
 cmd=L.command(job,'/tmp/p141-review.json','/tmp/p141-receipt.json',env['LD_LIBRARY_PATH'])
 unit=next(x.split('=',1)[1] for x in cmd if x.startswith('--unit='))+'.service'
 R.unit_gate('0::/user.slice/user-1000.slice/user@1000.service/app.slice/'+unit+'\n')
 assert '--property=SendSIGKILL=no' in cmd and '--property=Restart=no' in cmd
 real_sha=I.sha
 def envelope_sha(path):return '0'*64 if Path(path)==P/'packet-seal.json' else real_sha(path)
 with patch.object(I,'verify'),patch.object(I,'sha',side_effect=envelope_sha):
  identity=I.sealed(SimpleNamespace(lineage=P,profile='tp2',placement='1',timing='token'))
 identity.update(lane='B')
 calls=[]
 with tempfile.TemporaryDirectory(prefix='p141-arguments-') as d:
  tmp=Path(d);sandbox(tmp)
  def launch(argv,**kw):
   check();assert snapshot()==before
   rank=int(argv[argv.index('--rank')+1]);assert rank==len(calls)
   assert argv[argv.index('--max-new')+1]=='48' and argv[argv.index('--retain-steps')+1]=='none'
   assert argv[argv.index('--card')+1]==str(rank)
   assert '--authorized-device-window' in argv
   actual=kw['env'];assert actual['FilterBdfPath']=='0000:4' and actual['ZE_AFFINITY_MASK']=='0,1'
   assert set(actual)<=set(masked_environment('B',env))|{'HOME'}
   calls.append(dict(rank=rank,argv=argv,limits=check(),environment=actual))
   if len(calls)==2:raise Reached()
   return SimpleNamespace(pid=os.getpid())
  class Monitor:
   def __init__(self,*a):pass
   def poll(self,**kw):pass
   def register(self,*a):pass
  with patch.dict(os.environ,masked_environment('B',env),clear=True),patch.object(I,'verify'),patch.object(I,'sha',side_effect=envelope_sha),patch.object(C,'DeviceMonitor',Monitor),patch('subprocess.Popen',side_effect=launch):
   try:C.run(identity,tmp/'run',4800)
   except Reached:pass
   else:raise AssertionError('both launches not reached')
 assert len(calls)==2 and snapshot()==before
 print(json.dumps(dict(passed=True,device_executed=False,unit=unit,rank_execs=calls,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))

def main():
 from build_engine import limits,save
 limits()
 cp=subprocess.run([sys.executable,'-B',__file__,'--probe'],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 (P/'evidence/arguments.log').write_text(cp.stdout+cp.stderr)
 assert cp.returncode==0,cp.stderr[-3000:]
 row=json.loads(cp.stdout);assert row['max_rss_kib']<4*1024**2
 save(P/'evidence/arguments.json',row);print('real worker native argv, closed environment, unit and getrlimit x2 PASS')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--probe',action='store_true');args=ap.parse_args()
 probe() if args.probe else main()
