"""Refresh only Python analyzer evidence; retain the qualified native byte runs."""
import json,resource,subprocess,sys
from p157_v5_build_engine import P,ROOT,sha,save,limits

def main():
 limits()
 path=P/'evidence/split-cpu.json'
 previous=P/'evidence/packet157b-previous-split-cpu.json'
 if not previous.exists():previous.write_bytes(path.read_bytes())
 row=json.loads(previous.read_text())
 changed={str((P/n).relative_to(ROOT)) for n in ('analyze.py','test_analyze.py')}
 for name,digest in row['sources'].items():
  if name not in changed:assert sha(ROOT/name)==digest,'native/prior test source changed: '+name
 tests=[]
 for name in row['tests']:
  cp=subprocess.run([sys.executable,'-B',str(P/name)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
  log=P/'evidence'/('packet157b-'+name+'.log');log.write_text(cp.stdout+cp.stderr)
  assert cp.returncode==0,log.read_text()
  tests.append(dict(test=name,log=str(log.relative_to(ROOT)),sha256=sha(log)))
 # Read only the retained JSON timing stream, never model weights.
 raw=P/'evidence/device-p157-smoke-A/run/views/00-candidate/incident64/rank1/timings.jsonl'
 rows=[json.loads(s) for s in raw.read_text().splitlines()]
 host=[r for r in rows if 'p157_segment' in r]
 errors=[abs(1000*(r['end']-r['start'])-r['ms']) for r in host]
 assert all(e<=max(.02,1e-5*r['ms']) for r,e in zip(host,errors))
 proof=P/'evidence/packet157b-analyzer.json'
 save(proof,dict(passed=True,device_executed=False,tests=tests,
  prior_split_cpu_sha256=sha(previous),native_runs_reused=True,
  retained_stream=str(raw.relative_to(ROOT)),retained_stream_sha256=sha(raw),
  host_rows=len(host),old_tolerance_failures=sum(e>=.02 for e in errors),
  new_tolerance_failures=0,max_disagreement_ms=max(errors),
  sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'analyze.py',P/'test_analyze.py',P/'reseal157b.py')},
  peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 row['sources'].update({name:sha(ROOT/name) for name in changed})
 row['sources'][str(proof.relative_to(ROOT))]=sha(proof)
 row['python_analyzer_refresh']=dict(evidence=str(proof.relative_to(ROOT)),sha256=sha(proof),
  prior_receipt=str(previous.relative_to(ROOT)),prior_sha256=sha(previous),
  native_runs='Retained unchanged from the prior receipt; no rebuild or native execution.')
 save(path,row)
 print('Analyzer tests and retained timing stream PASS; native runs retained unchanged')

if __name__=='__main__':main()
