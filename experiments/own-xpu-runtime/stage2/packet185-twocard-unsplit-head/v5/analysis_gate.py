"""Analysis gate: real-stream schema positives, missing-stream negatives, s185 rule on REAL device data."""
import json,subprocess,sys,resource
from p185_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();tests=[];reference=None
 for name in ('test_analyze.py','test_timing_report.py','test_s185_decision.py'):
  cp=subprocess.run([sys.executable,'-B',str(P/name)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600,cwd=P)
  log=P/'evidence'/('analysis-'+name+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text()
  for line in cp.stdout.splitlines():
   if line.startswith('P106B_REFERENCE='):reference=json.loads(line[len('P106B_REFERENCE='):])
  tests.append(dict(name=name,passed=True,log_digest=sha(log)))
 fixtures=LOCAL/'lineage-inputs/decision-fixtures'
 paths=[P/'analysis_gate.py',P/'analyze.py',P/'timing_report.py',P/'test_analyze.py',P/'test_timing_report.py',P/'s185_decision.py',P/'interval_model.py',P/'test_s185_decision.py',
        LOCAL/'lineage-inputs/packet153-own/v5/evidence/device-static-v5-B-p153b/bracket-summary.json',
        LOCAL/'lineage-inputs/packet183-own/v5/evidence/device-metadata-v5-B-p183/bracket-summary.json',
        *(LOCAL/'lineage-inputs/timing-fixture').glob('*'),*(LOCAL/'lineage-inputs/timing-fixture-p153b').glob('*'),
        *(f for f in fixtures.rglob('*') if f.is_file())]
 save(P/'evidence/analysis.json',dict(passed=True,device_executed=False,real_historical_schema_checked=True,missing_streams_and_scopes_refused=True,
  unsplit_head_scope_absence_enforced=True,first_request_gate_in_every_view_row=True,elapsed_time_informational_only=True,
  s185_rule_on_real_packet183_bracket='CLOSED on the S1 rows (u ~ +0.97 ms), GO/CLOSE/INCOMPLETE branches by perturbing the real numbers',
  s185_rule_on_real_packet153_summary='refused: no interval statistics in a one-load bracket summary (INCOMPLETE, never GO)',
  packet106b_fresh_load_reference=reference,tests=tests,sources={str(f.relative_to(ROOT)):sha(f) for f in paths}))
 print('analysis gate PASS',reference)
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4_000_000_000,4_000_000_000));main()
