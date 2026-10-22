"""First-request actual-schema positives and missing-stream negatives."""
import json,subprocess,sys,resource
from p184_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();tests=[]
 for name in ('test_analyze.py','test_timing_report.py'):
  cp=subprocess.run([sys.executable,'-B',str(P/name)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
  log=P/'evidence'/('analysis-'+name+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text()
  tests.append(dict(name=name,passed=True,log_digest=sha(log)))
 paths=[P/'analysis_gate.py',P/'analyze.py',P/'timing_report.py',P/'test_analyze.py',P/'test_timing_report.py',*(LOCAL/'lineage-inputs/timing-fixture').glob('*'),*(LOCAL/'lineage-inputs/timing-fixture-p153b').glob('*')]
 save(P/'evidence/analysis.json',dict(passed=True,device_executed=False,real_historical_schema_checked=True,missing_streams_and_scopes_refused=True,first_request_gate_in_smoke=True,elapsed_time_informational_only=True,real_packet153_cold_prefill_regression=True,tests=tests,sources={str(f.relative_to(ROOT)):sha(f) for f in paths}))
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000));main()
