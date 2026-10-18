"""CPU interception at both real rank exec sites. No native executable may run."""
import argparse,contextlib,hashlib,json,os,resource,runpy,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
O=P=Path(__file__).resolve().parent;ROOT=P.parents[3]
sys.path.insert(0,str(P))
class Reached(BaseException):pass
class Refused(BaseException):pass

def probe(role,negative=False):
 from exec_limits import snapshot,check,install
 baseline=snapshot();observations=[]
 with tempfile.TemporaryDirectory(prefix='p118-exec-') as tmp:
  tmp=Path(tmp)
  def audit(event,values):
   if event=='open' and isinstance(values[0],(str,bytes)):
    path=Path(os.fsdecode(values[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise Refused('device open forbidden')
    if (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise Refused('write outside CPU scratch: '+str(path))
   if event in ('os.system','os.exec','os.posix_spawn'):raise Refused('native execution forbidden')
  # Per-probe expendable process; this audit persists until exit.
  sys.addaudithook(audit)
  def stop(cmd,*args,**kwargs):
   argv=list(map(str,cmd))
   assert any('own-rt-iq3' in x for x in argv),'unexpected subprocess'
   assert argv[argv.index('--target-split')+1]==('0' if role=='production' else '25')
   assert argv[argv.index('--draft-rank')+1]=='1'
   check(baseline);observations.append(dict(argv=argv,limits=snapshot(),unchanged=True))
   if len(observations)==2:raise Reached()
   return SimpleNamespace(pid=99999999,poll=lambda:0,returncode=0)
  if negative:resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
  try:
   with contextlib.ExitStack() as stack:
    stack.enter_context(patch.object(subprocess,'Popen',side_effect=stop))
    import exec_limits
    def refusal_before_recovery(inherited):
     try:check(inherited)
     except AssertionError as error:raise Refused(str(error))
    stack.enter_context(patch.object(exec_limits,'check',side_effect=refusal_before_recovery))
    install()
    if True:
     from bootstrap import install as bootstrap,WRAPPER
     bootstrap()
     from screen_jobs import view
     from common import sealed
     from conditions import LANES
     import conditions,devices
     stack.enter_context(patch.object(conditions,'lane_gate'))
     stack.enter_context(patch.object(conditions,'Teardown',side_effect=lambda *a,**k:contextlib.nullcontext()))
     stack.enter_context(patch.object(devices.DeviceMonitor,'register'))
     stack.enter_context(patch.object(devices.DeviceMonitor,'poll'))
     # Only operational device admission is synthetic. Identity/oracle/argv real.
     stack.enter_context(patch.object(devices,'masked_environment',side_effect=lambda *a,**k:dict(os.environ)))
     lineage=view(role)
     identity=sealed(SimpleNamespace(lineage=lineage,seal=lineage/'screen-seal.json',binary=None,dispatch=None,profile='tp2',timing='token',placement='1' if role=='production' else '25-23'))
     identity.update(lane='B',conditions=LANES['B'])
     out=tmp/'run';out.mkdir()
     import worker
     namespace=runpy.run_path(str(P/'runtime_worker.py'));namespace['run'](identity,out,1800)
   raise AssertionError('did not reach both native boundaries')
  except Reached:
   assert not negative
   return dict(passed=True,device_executed=False,role=role,observations=observations,synthetic_admission=True)
  except (AssertionError,Refused) as e:
   if negative and ('RLIMIT_AS' in str(e) or 'resource limits changed' in str(e)):return dict(passed=True,negative_control=True,refusal=str(e),device_executed=False)
   raise

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--probe',choices=('production','25-23'));ap.add_argument('--negative',action='store_true');a=ap.parse_args()
 if a.probe:print(json.dumps(probe(a.probe,a.negative)));return
 rows=[]
 for role,negative in [('production',True),('production',False),('25-23',False)]:
  cp=subprocess.run([sys.executable,'-B',str(Path(__file__)), '--probe',role,*(['--negative'] if negative else [])],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
  (O/'evidence'/('exec-'+role+('-negative' if negative else '')+'.log')).write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,cp.stderr[-3000:]
  rows.append(json.loads(cp.stdout));print(role,'negative' if negative else 'positive','PASS',flush=True)
 sources={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [P/n for n in ('exec_limits.py','worker.py','runtime_worker.py','chain_pipeline.py','launch_limit_gate.py')]}
 (O/'evidence/launch-limits.json').write_text(json.dumps(dict(passed=True,device_executed=False,cases=rows,sources=sources),indent=2)+'\n')
if __name__=='__main__':main()
