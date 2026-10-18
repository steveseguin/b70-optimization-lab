"""Bounded CPU-only continuation. Never launches, queues or signals device work."""
import argparse,datetime,json,resource,subprocess,sys,time
from router_replay import P,ROOT,sha,save

def main(args):
 from build_engine import limits
 deadline=datetime.datetime.fromisoformat(args.until).timestamp()
 manifest=P/'evidence/capture-inputs.json';window=P/'evidence/capture-B/window.json'
 while not manifest.exists():
  limits()
  if time.time()>=deadline:
   print('Time box reached while capture pending; no measurements invented.',flush=True);return
  if window.exists():
   try:row=json.loads(window.read_text())
   except json.JSONDecodeError:row={}
   if row.get('stop_reasons') or row.get('lease_released') and not row.get('passed'):
    raise RuntimeError('Coordinator capture did not pass; CPU continuation will not retry any device job')
  time.sleep(min(5,max(0,deadline-time.time())))
 seal=P/'evidence/analysis-seal.json';receipt=json.loads(seal.read_text());assert receipt['passed']
 for name,digest in receipt['sources'].items():assert sha(ROOT/name)==digest,name
 for script in ('router_replay.py','simulate.py'):
  limits();remaining=deadline-time.time()
  if remaining<=0:raise TimeoutError('CPU analysis time box exhausted')
  print('Starting CPU-only',script,flush=True)
  subprocess.run([sys.executable,'-B',str(P/script)],stdin=subprocess.DEVNULL,check=True,timeout=remaining)
  limits()
 save(P/'evidence/continuation.json',dict(passed=True,device_started=False,
  analysis_seal_sha256=sha(seal),capture_manifest_sha256=sha(manifest),
  outputs={name:sha(P/'evidence'/name) for name in ('router-replay.json.gz','predictions.json.gz','cache-projections.json.gz','projection-status.json')},
  max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))

if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 ap=argparse.ArgumentParser();ap.add_argument('--until',required=True,help='UTC ISO deadline, e.g. 2026-10-18T18:28:48+00:00')
 main(ap.parse_args())
