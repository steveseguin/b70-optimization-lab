"""Analysis gate: real-stream schema positives, missing-stream negatives, the s186 rule on REAL device data."""
import json,subprocess,sys,resource
from p186_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();tests=[]
 for name in ('test_analyze.py','test_timing_report.py','test_s186_decision.py'):
  cp=subprocess.run([sys.executable,'-B',str(P/name)],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600,cwd=P)
  log=P/'evidence'/('analysis-'+name+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text()
  tests.append(dict(name=name,passed=True,log_digest=sha(log)))
 own=LOCAL/'lineage-inputs'
 paths=[P/'analysis_gate.py',P/'analyze.py',P/'timing_report.py',P/'test_analyze.py',P/'test_timing_report.py',P/'s186_decision.py',P/'interval_model.py',P/'test_s186_decision.py',
        own/'packet153-own/v5/evidence/device-static-v5-B-p153b/bracket-summary.json',
        own/'packet183-own/v5/evidence/device-metadata-v5-B-p183/bracket-summary.json',
        *sorted(own.glob('packet185-own/v5/evidence/device-view*-B-p185/bracket-summary.json')),
        *(own/'timing-fixture').glob('*'),*(own/'timing-fixture-p153b').glob('*'),
        *(f for f in (own/'decision-fixtures').rglob('*') if f.is_file())]
 save(P/'evidence/analysis.json',dict(passed=True,device_executed=False,real_historical_schema_checked=True,missing_streams_and_scopes_refused=True,
  head_scope_absence_enforced_for_u_and_v3=True,boundary_scopes_mandatory_for_v3_and_refused_for_u=True,first_request_gate_in_every_row=True,
  elapsed_time_informational_only=True,
  s186_rule_on_real_packet185_views='NOT A WINNER with a V3 equal to a real bundle-8 view (U = real un-split views); scalings cover winner+chain, winner below 59.974, below +0.5 %, drift, inexact, proposals, missing smoke',
  s186_rule_on_real_packet183_bracket='NOT A WINNER (S1 metadata views as V3: about -6 %)',
  v3_interval_extension='reproduces the vendored packet85 accounting exactly without boundary commands; adds the boundary to the ready side with them (real packet183 streams)',
  tests=tests,sources={str(f.relative_to(ROOT)):sha(f) for f in paths}))
 print('analysis gate PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4_000_000_000,4_000_000_000));main()
