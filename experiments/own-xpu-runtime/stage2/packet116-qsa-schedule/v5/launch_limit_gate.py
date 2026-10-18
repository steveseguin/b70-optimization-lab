"""Intercept both actual Transport rank execs; refuse inherited finite AS."""
import argparse,contextlib,json,os,resource,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
P=Path(__file__).resolve().parent;ROOT=P.parents[4]
class Reached(BaseException):pass
class Refused(BaseException):pass
def probe(negative=False):
 from exec_limits import snapshot,check,install
 baseline=snapshot();observations=[]
 with tempfile.TemporaryDirectory(prefix='p116-exec-') as temp:
  tmp=Path(temp)
  def audit(event,values):
   if event=='open' and isinstance(values[0],(str,bytes)):
    path=Path(os.fsdecode(values[0])).absolute()
    if str(path).startswith('/dev/dri/'):raise Refused('device open forbidden')
    if (values[2] or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) and path!=Path('/dev/null') and not path.resolve().is_relative_to(tmp):raise Refused('write outside CPU scratch: '+str(path))
   if event in ('os.system','os.exec','os.posix_spawn'):raise Refused('native execution forbidden')
  sys.addaudithook(audit)
  def stop(cmd,*args,**kwargs):
   argv=list(map(str,cmd));assert any('own-rt-iq3' in x for x in argv)
   check(baseline);observations.append(dict(argv=argv,limits=snapshot(),unchanged=True))
   if len(observations)==2:raise Reached()
   return SimpleNamespace(pid=99999999,poll=lambda:0,returncode=0)
  if negative:resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
  try:
   with patch.object(subprocess,'Popen',side_effect=stop):
    install()
    # Import the real worker so its guard and imported protocol match device use.
    import tp2_worker
    from common import P56
    sys.path.insert(0,str(P56));import pipeline
    pipeline.P=tmp/'adapter';pipeline.P.mkdir()
    args=pipeline.parser().parse_args(['--output',str(tmp/'ranks'),'--device','--binary',str(P/'build/device/own-rt-iq3'),'--dispatch',str(P/'lineage/dispatch-speed6.json'),'--controller','native','--draft','mtp','--draft-rank','1','--target-split','0','--context','4096','--tokens','128','--retain-steps','none','--timing','token','--native-nice','0','--card','0','--seconds','3600'])
    args.selection_sha256=__import__('hashlib').sha256((P/'lineage/selection.json').read_bytes()).hexdigest()
    args.input=P.parents[1]/'packet111-record-bundle/build/input'
    (tmp/'ranks').mkdir()
    pipeline.Transport(args,tmp/'ranks',dict(PATH='/usr/bin:/bin',OMP_NUM_THREADS='2'))
   raise AssertionError('did not reach both native execs')
  except Reached:
   assert not negative
   return dict(passed=True,device_executed=False,observations=observations,real_transport=True)
  except AssertionError as e:
   if negative and ('RLIMIT_AS' in str(e) or 'resource limits changed' in str(e)):
    return dict(passed=True,device_executed=False,negative_control=True,refusal=str(e))
   raise
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--probe',action='store_true');ap.add_argument('--negative',action='store_true');a=ap.parse_args()
 if a.probe:print(json.dumps(probe(a.negative)));return
 rows=[]
 for negative in (False,True):
  cp=subprocess.run([sys.executable,'-B',str(Path(__file__)),'--probe',*(['--negative'] if negative else [])],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=90)
  (P/'evidence'/('exec-negative.log' if negative else 'exec-positive.log')).write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,cp.stderr[-3000:]
  rows.append(json.loads(cp.stdout))
 from build_engine import sha,save
 files=[P/'exec_limits.py',P/'launch_limit_gate.py',P/'screen.py',P/'tp2_worker.py',P.parents[1]/'packet56-draft-prefix/pipeline.py']
 save(P/'evidence/launch-limits.json',dict(passed=True,device_executed=False,cases=rows,sources={str(f.relative_to(ROOT)):sha(f) for f in files}))
 print('both native rank boundaries unchanged; inherited finite cap rejected')
if __name__=='__main__':main()
