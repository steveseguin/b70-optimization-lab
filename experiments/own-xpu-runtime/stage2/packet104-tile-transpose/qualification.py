"""Hash-bound packet104 micro results; target routes do not qualify draft routes."""
import json
from build_engine import P,ROOT,sha,save
from route_inputs import require_ready,MANIFEST,ROUTES
from micro_gate import analyze,require
MICRO=P/'evidence/micro-B'
def measured(packet=P):
 require(packet==P,'packet mismatch');routes=require_ready()
 window=json.loads((MICRO/'window.json').read_text());build=json.loads((P/'evidence/microbench-build.json').read_text())
 require(all(window.get(k) is True for k in ('passed','device_executed','drained','lease_released')) and window.get('child_still_running') is False and not window.get('stop_reasons'),'clean micro window required')
 require(build.get('passed') is True and build.get('device_executed') is False,'CPU build required')
 for n,h in build['sources'].items():require(sha(ROOT/n)==h,'source changed: '+n)
 for n,h in build['artifacts'].items():require(sha(P/n)==h,'artifact changed: '+n)
 require(window['binary_sha256']==sha(P/'build/microbench')==build['binary_sha256'],'binary changed')
 require(window['build_receipt_sha256']==sha(P/'evidence/microbench-build.json') and window['samples_sha256']==sha(MICRO/'samples.jsonl'),'receipt changed')
 require(window['identity']['route_manifest_sha256']==sha(MANIFEST) and window['identity']['route_bytes_sha256']==routes['route_bytes_sha256'],'route binding changed')
 require(window.get('device_isolation',{}).get('passed') is True,'device isolation unproved')
 result=analyze([json.loads(s) for s in (MICRO/'samples.jsonl').read_text().splitlines() if s.strip()],384)
 result['bindings']={str(f.relative_to(ROOT)):sha(f) for f in (MICRO/'window.json',MICRO/'samples.jsonl',P/'evidence/microbench-build.json',P/'micro_gate.py',P/'qualification.py',MANIFEST,ROUTES)}
 return result
def evaluate(packet=P):
 result=measured(packet);save(MICRO/'qualification.json',result);return result
def require_qualified(packet=P):
 result=measured(packet)
 require(json.loads((MICRO/'qualification.json').read_text())==result,'qualification changed')
 require(result['qualified'],'no candidate passes 15% gate with matching routes')
 return tuple(result['qualified'])
