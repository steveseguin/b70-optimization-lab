#!/usr/bin/env python3
"""Run standalone CPU mock regressions omitted by unittest discovery, once each."""
import gzip,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from storage import admit
P=Path(__file__).resolve().parent
CASES=[
 ('test_receipt_metadata.py','receipt-metadata-gates.json',[]),
 ('test_failure_storage.py','review-resume-storage-gates.json',['--output','review-resume-storage-gates.json']),
 ('test_window_storage.py','review-resume-window-storage-gates.json',['--output','review-resume-window-storage-gates.json']),
 ('test_draft_window_cleanup.py','draft-window-cleanup-gates.json',[]),
 ('test_state_retention.py','reset-retention-gate-results.json',[]),
 ('test_suite_export_retention.py','suite-export-retention-gates.json',[]),
 ('test_storage_race.py','storage-race-gates.json',[]),
 ('test_suite_warmup.py','suite-warmup-gates.json',[]),
 ('test_cleanup_paths.py','cleanup-path-gates.json',[]),
 ('test_suite_compiler.py','suite-compiler-gates.json',[]),
 ('test_seal_bootstrap.py','seal-bootstrap-gates.json',[]),
 ('test_retain_window.py','window-retention-gates.json',[]),
]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 rows=[];root=P/'evidence/python-standalone';root.mkdir(parents=True,exist_ok=True)
 for script,receipt,args in CASES:
  admit(2_000_000);before=(P/receipt).stat().st_mtime_ns if (P/receipt).exists() else None
  command=['nice','-n','19','ionice','-c','3',sys.executable,'-B',str(P/script),*args]
  started=time.monotonic();error=None
  try:
   child=subprocess.run(command,cwd=P,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,check=False)
   output=child.stdout;code=child.returncode
  except subprocess.TimeoutExpired as exc:
   output=exc.stdout or b'';code=None;error='standalone CPU mock watchdog expired'
  log=root/(Path(script).stem+'.log.gz')
  with gzip.open(log,'wb') as stream:stream.write(output)
  fresh=(P/receipt).is_file() and (P/receipt).stat().st_mtime_ns!=before
  result=json.loads((P/receipt).read_text()) if fresh else {}
  passed=code==0 and fresh and result.get('passed') is True
  rows.append(dict(script=script,command=command,passed=passed,returncode=code,error=error,seconds=time.monotonic()-started,receipt=receipt,receipt_sha256=sha(P/receipt) if fresh else None,log=str(log.relative_to(P)),log_sha256=sha(log)))
  print(json.dumps(dict(script=script,passed=passed,returncode=code)),flush=True)
  if not passed:break
 row=dict(passed=len(rows)==len(CASES) and all(r['passed'] for r in rows),device_executed=False,native_ranks_executed=False,tests=len(rows),expected_tests=len(CASES),rows=rows,source_sha256={n:sha(P/n) for n in [Path(__file__).name,*[c[0] for c in CASES]]})
 admit(2_000_000);(P/'python-standalone-gates.json').write_text(json.dumps(row,indent=2)+'\n')
 return 0 if row['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
