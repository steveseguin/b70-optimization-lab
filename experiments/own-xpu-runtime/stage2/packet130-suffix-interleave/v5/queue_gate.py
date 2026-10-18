"""Packet124c pattern: real queue loop/plan, scratch writes, intercepted execute.

Two windows are registered: smoke-B (12 x 64) and bracket-B (five 12 x 128 views).
Legacy eleven-window bundle chains are not admitted by this view's seal.
Scheduler guards/review/status are synthetic; plan, argv, queue mutation and
failure/no-retry behavior are real. No service or native process can execute.
"""
import importlib.util,json,shutil,subprocess,tempfile
from pathlib import Path
from unittest.mock import patch
from build_engine import P,ROOT,sha,save,limits

def main():
 limits()
 spec=importlib.util.spec_from_file_location('p130_queue',P.parents[2]/'ops/lane-queue/lanequeue.py')
 q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
 proposals=[P.parents[2]/('ops/lane-queue/proposed-p130-'+kind+'-B.txt') for kind in ('smoke','bracket')]
 results=[]
 for proposal in proposals:
  for rc in (0,1):
   with tempfile.TemporaryDirectory(prefix='p130-queue-') as d:
    tmp=Path(d);shutil.copyfile(proposal,tmp/'queue-B.txt')
    jobs=q.read_queue(tmp,'B');assert len(jobs)==1
    executed=[];reviews=[]
    class Backend:
     def guards(self,lane):assert lane=='B';return 0
     def review(self,job,directory):
      reviews.append(job['name']);return str(tmp/'synthetic-review.json')
     def execute(self,cmd,log):
      # Capture the actual systemd job command without invoking it.
      executed.append(cmd);return rc
     def status(self,name,receipt):return dict(Result='success' if rc==0 else 'exit-code',ExecMainStatus=rc)
    clock=[100000.]
    def now():clock[0]+=100.;return clock[0]
    queue=q.Queue(tmp,'B',backend=Backend(),now=now,sleep=lambda _:None)
    original=queue.finish
    def finish(job,record):original(job,record);queue.stopped=True
    # plan_job itself executes only its audited CPU --plan. The real immutable
    # proposal is planned from scratch and all retained queue output is synthetic.
    with patch.object(q,'live_window_blocker',return_value=None),patch.object(q,'drain_spacing_deadline',return_value=0),patch.object(queue,'finish',side_effect=finish),patch.object(q,'report_failure_evidence',side_effect=ValueError('synthetic failed child')):
     result=queue.run()
    assert len(executed)==len(reviews)==1
    assert result==(0 if rc==0 else 1)
    done=json.loads((tmp/'done-B.txt').read_text());assert done['outcome']==('DONE' if rc==0 else 'FAILED')
    assert not q.read_queue(tmp,'B') and not queue.active.exists()
    results.append(dict(child_returncode=rc,queue_returncode=result,outcome=done['outcome'],executions=len(executed),command=executed[0]))
 save(P/'evidence/queue-gate.json',dict(passed=True,device_executed=False,service_executed=False,
  synthetic_operational_state=True,registered_windows=['smoke','bracket'],scratch_removed=True,cases=results,
  sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'queue_gate.py',P/'bracket_job.py',P/'tp2_worker.py',Path(q.__file__),*proposals)}))
 print('real proposed queue: plan, success, failed-child/no-retry PASS')
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
