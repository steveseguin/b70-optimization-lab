"""Real parent argument and queue paths, plus packet137's extended native starts.

The immutable parent's entry probes run in subprocesses with 4 GiB CPU caps.
They execute actual input and oracle checks and intercept native execution.
Their outputs are never treated as packet137 device or performance evidence.
"""
import importlib.util,json,os,resource,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[4]
OPS=P.parents[2]/'ops/packet124c-orchestration'
WINDOWS=('K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs','WS128x','WS128')
def probe(name):
 sys.path.insert(0,str(OPS))
 spec=importlib.util.spec_from_file_location('frozen124c_argument',OPS/'argument_gate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 if name=='k2-replay':return m.replay()
 if name=='queue':
  from inherited_queue_probe import probe as queue
  return queue()
 if name=='oracle':
  from queue_gate import oracle_probe
  return oracle_probe()
 return m.probe(name)
def main():
 from build_engine import limits,sha,save
 limits();rows=[]
 for name in (*WINDOWS,'k2-replay','queue','oracle'):
  cmd=[sys.executable,'-B',str(P/'all_window_gate.py'),'--probe',name]
  cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=300,env=dict(os.environ,OMP_NUM_THREADS='2'))
  log=P/'evidence'/('all-window-'+name+'.log');log.write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,name+': '+cp.stderr[-2500:]
  value=json.loads(next(line.removeprefix('RESULT=') for line in cp.stdout.splitlines() if line.startswith('RESULT=')))
  rows.append(dict(window=name,result=value,log_sha256=sha(log)))
  print(name,'real argument/queue path PASS',flush=True)
 queue=next(r['result'] for r in rows if r['window']=='queue')
 assert queue['passed'] and queue['queue_run_executed']
 assert len(queue['input_preflights'])==12 and len(queue['oracle_checks'])==6 and all(c['returncode']==0 for c in queue['oracle_checks'])
 assert len(next(r['result'] for r in rows if r['window']=='oracle')['calls'])==1
 extended=json.loads((P/'evidence/legacy-windows.json').read_text())
 assert extended['passed'] and extended['total_windows']==44
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'all_window_gate.py',P/'inherited_queue_probe.py',P/'evidence/legacy-windows.json',*OPS.glob('*.py'),*OPS.joinpath('inputs/k2-replay').glob('*'),*(P.parents[1]/'packet124c-record-bundle').glob('*.py')]}
 save(P/'evidence/all-windows.json',dict(passed=True,device_executed=False,windows=rows,extended_token_input_views=['original','draft_table','target_buffers','both'],real_queue_loop=True,oracle_via_original_binding=True,sources=sources))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 if '--probe' in sys.argv:print('RESULT='+json.dumps(probe(sys.argv[-1])))
 else:main()
