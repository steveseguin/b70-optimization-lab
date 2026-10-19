"""CPU-only replay of packet58amc checks; no compile, model read or queue mutation."""
import json,pathlib,subprocess,tempfile,resource,os,time,sys
P=pathlib.Path(__file__).resolve().parent;R=P.parents[3];Q=R/'experiments/own-xpu-runtime/ops/lane-queue';E=P/'evidence';records=[]
def bounded():resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
def run(name,cmd):
 with (E/f'p58an-{name}.log').open('w') as f:
  cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,cwd=R,preexec_fn=bounded)
 records.append(dict(check=name,returncode=cp.returncode));print(name,cp.returncode,flush=True)
if '--skip-tests' not in sys.argv:
 run('python-tests',['python3','-B',str(P/'checks.py')])
else:
 assert json.loads((E/'python-tests.json').read_text())['passed']
 records.append(dict(check='python-tests-already-completed',returncode=0))
for kind in (('v5',) if '--v5-only' in sys.argv else ('smoke','v5')):
 with tempfile.TemporaryDirectory(prefix='p58an-plan-') as d:
  pathlib.Path(d,'queue-A.txt').write_text((Q/f'proposed-p58am-{kind}-A.txt').read_text())
  job=json.loads(next(line for line in (Q/f'proposed-p58am-{kind}-A.txt').read_text().splitlines() if line.startswith('{')))
  argv=list(job['argv']);i=argv.index('--fault-review');del argv[i:i+2];argv.remove('--authorized-device-window');run('entry-plan-'+kind,argv+['--plan'])
  run('plan-'+kind,['python3','-B',str(Q/'lanequeue.py'),'plan','--lane','A','--directory',d])
 with (E/f'p58an-rehearse-{kind}.json').open('w') as out,(E/f'p58an-rehearse-{kind}.log').open('w') as err:
  cp=subprocess.run(['python3','-B',str(Q.parent/'rehearse_entry.py'),str(Q/f'proposed-p58am-{kind}-A.txt'),'--report','--json'],stdin=subprocess.DEVNULL,stdout=out,stderr=err,cwd=R,preexec_fn=bounded)
 records.append(dict(check='rehearse-'+kind,returncode=cp.returncode));print('rehearse-'+kind,cp.returncode,flush=True)
(E/'p58an-checks.json').write_text(json.dumps(dict(records=records,max_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,device_executed=False),indent=2)+'\n')
