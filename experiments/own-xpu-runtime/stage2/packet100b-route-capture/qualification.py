"""Packet100's unchanged 15%/both-order/per-route gate with p100b inputs."""
import importlib.util,json
from build_engine import P,ROOT,sha,save
from capture_inputs import require_ready,MANIFEST,ROUTES
from common import read,require,verify_map
BASE=P.parent/'packet100-down-locality'
MICRO=P/'evidence/micro-B'

def analyzer():
 spec=importlib.util.spec_from_file_location('p100_frozen_micro_gate',BASE/'micro_gate.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.analyze

def measured(packet=P):
 require(packet==P,'qualification packet mismatch')
 routes=require_ready()
 window=read(MICRO/'window.json');build=read(P/'evidence/microbench-build.json')
 require(all(window.get(k) is True for k in ('passed','device_executed','drained','lease_released'))
         and window.get('child_still_running') is False and not window.get('stop_reasons'),'clean micro window required')
 require(build.get('passed') is True and build.get('device_executed') is False,'CPU build required')
 verify_map(ROOT,build['sources']);verify_map(P,build['artifacts'])
 require(window['binary_sha256']==sha(P/'build/microbench')==build['binary_sha256'],'micro binary changed')
 require(window['build_receipt_sha256']==sha(P/'evidence/microbench-build.json') and window['samples_sha256']==sha(MICRO/'samples.jsonl'),'micro evidence changed')
 require(window['identity']['route_manifest_sha256']==sha(MANIFEST)
         and window['identity']['route_bytes_sha256']==routes['route_bytes_sha256'],'capture identity changed')
 require(window.get('device_isolation',{}).get('passed') is True,'micro device ownership unproved')
 rows=[json.loads(line) for line in (MICRO/'samples.jsonl').read_text().splitlines() if line.strip()]
 result=analyzer()(rows,routes['micro_route_vectors'])
 result.update(schema='packet100b.micro-qualification.v1',route_origin='p100b real accepted target routes',
  capture_manifest_sha256=sha(MANIFEST),capture_route_bytes_sha256=sha(ROUTES),
  bindings={str(f.relative_to(ROOT)):sha(f) for f in (MICRO/'window.json',MICRO/'samples.jsonl',
    P/'evidence/microbench-build.json',P/'packet-seal.json',P/'qualification.py',
    BASE/'micro_gate.py',BASE/'screen-jobs-seal.json',MANIFEST,ROUTES)})
 return result

def evaluate(packet=P):
 result=measured(packet);save(MICRO/'qualification.json',result);return result

def require_qualified(packet=P):
 require((MICRO/'qualification.json').is_file(),'p100b real-route micro qualification pending')
 result=measured(packet)
 require(read(MICRO/'qualification.json')==result,'micro qualification changed')
 require(result['qualified'],'no candidate meets unchanged >=15% gate')
 return tuple(result['qualified'])
