"""Seal CPU analysis preparation independently of the already prepared capture."""
import json,resource,subprocess,sys
from router_replay import P,ROOT,sha,save,library

def main():
 from build_engine import limits
 limits();library()
 cpu=json.loads((P/'evidence/replay-cpu.json').read_text())
 assert cpu['passed'] and not cpu['device_executed'] and not cpu['real_capture_tested']
 assert len(cpu['runs'])==4 and len({(r['logits_sha256'],r['routes_sha256']) for r in cpu['runs']})==1
 logs=[]
 for name in ('test_sim.py','test_replay_flow.py'):
  path=P/'evidence'/(name+'.log')
  with path.open('w') as log:
   subprocess.run([sys.executable,'-B',str(P/name)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=120,check=True)
  logs.append(path)
 sources=[P/n for n in ('analysis_gate.py','build_replay.py','cache_cpu.cpp','cache_sim.py','prepare_prefill.py','replay_gate.py','router_cpu.cpp','router_replay.py','simulate.py','test_sim.py','test_replay_flow.py','timing_inputs.py','ANALYSIS.md')]
 sources += [P/'evidence'/n for n in ('replay-build.json','replay-cpu.json','router-weights.json','prefill-binding.json','prefill-inputs.json.gz','timing-inputs.json')]
 sources+=logs
 save(P/'evidence/analysis-seal.json',dict(schema='packet138.cpu-analysis-preparation.v1',passed=True,device_executed=False,
  sources={str(f.relative_to(ROOT)):sha(f) for f in sources},tests=10,actual_capture='pending',
  synthetic_fixtures_are_not_measurements=True,peak_test_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
  replay_build_sha256=sha(P/'evidence/replay-build.json')))
 limits();print('CPU analysis preparation PASS: compiler repeats, ten tests, independent source seal')

if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
