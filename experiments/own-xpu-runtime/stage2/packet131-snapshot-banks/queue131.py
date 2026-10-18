"""Plan new proposals on scratch copies and exercise success/failure queue paths."""
import importlib.util,json,subprocess,sys,tempfile,shutil
from pathlib import Path
from unittest.mock import patch
from build131 import P,ROOT,sha,save,cpu_main,limits
def main():
 from run131 import output
 queue=P.parents[1]/'ops/lane-queue'
 spec=importlib.util.spec_from_file_location('p131_queue',queue/'lanequeue.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
 rows=[]
 for label,indices in [('smoke-B',[-1]),('grid-B',list(range(5)))]:
  jobs=[]
  for i in indices:
   jobs.append(dict(name='p131-B-'+('smoke12' if i==-1 else 'grid-'+str(i)),lane='B',argv=['/usr/bin/python3','-B',str((P/'run131.py').relative_to(ROOT)),'--index',str(i),'--output',str(output(i)),'--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},review=str((P.parent/'screen/v4-lanes/fault_review.py').relative_to(ROOT))))
  proposal=queue/('proposed-p131-'+label+'.txt');payload=''.join(json.dumps(job)+'\n' for job in jobs)
  with tempfile.TemporaryDirectory(prefix='p131-plan-',dir=P/'build/tmp') as d:
   tmp=Path(d);(tmp/'queue-B.txt').write_text(payload)
   cmd=[sys.executable,'-B',str(queue/'lanequeue.py'),'plan','--lane','B','--directory',str(tmp)]
   log=P/'evidence'/('queue-plan-'+label+'.log')
   with log.open('w') as stream:subprocess.run(cmd,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=240)
  proposal.write_text(payload);rows.append(dict(proposal=str(proposal.relative_to(ROOT)),sha256=sha(proposal),jobs=len(jobs),expected_seconds_per_job=360 if label.startswith('smoke') else 480,watchdog_seconds=1800 if label.startswith('smoke') else 3600))
 cases=[]
 for rc in (0,1):
  with tempfile.TemporaryDirectory(prefix='p131-queue-') as d:
   tmp=Path(d);shutil.copyfile(queue/'proposed-p131-smoke-B.txt',tmp/'queue-B.txt');executed=[]
   class Backend:
    def guards(self,lane):assert lane=='B';return 0
    def review(self,job,directory):return str(tmp/'synthetic-review.json')
    def execute(self,cmd,log):executed.append(cmd);return rc
    def status(self,name,receipt):return dict(Result='success' if rc==0 else 'exit-code',ExecMainStatus=rc)
   clock=[100000.]
   def now():clock[0]+=100.;return clock[0]
   runner=q.Queue(tmp,'B',backend=Backend(),now=now,sleep=lambda _:None);finish=runner.finish
   def done(job,record):finish(job,record);runner.stopped=True
   with patch.object(q,'live_window_blocker',return_value=None),patch.object(q,'drain_spacing_deadline',return_value=0),patch.object(runner,'finish',side_effect=done),patch.object(q,'report_failure_evidence',side_effect=ValueError('synthetic failed child')):
    result=runner.run()
   assert len(executed)==1 and result==rc
   assert not q.read_queue(tmp,'B') and not runner.active.exists()
   cases.append(dict(returncode=rc,executions=len(executed),command=executed[0],receipt=json.loads((tmp/'done-B.txt').read_text())))
 save(P/'evidence/queue131.json',dict(passed=True,device_executed=False,service_executed=False,live_queue_modified=False,synthetic_scheduler=True,proposals=rows,cases=cases,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'queue131.py',P/'run131.py',Path(q.__file__),*(ROOT/r['proposal'] for r in rows)]}))
 print('six plans and real queue success/failure PASS',flush=True)
if __name__=='__main__':cpu_main();main()
