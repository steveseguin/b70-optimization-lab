"""Replay actual packet100b IDs with frozen packet58 position-end cache policy."""
import json,struct,subprocess,sys,resource
from build_engine import P,ROOT,sha,limits
from compile_turn import turn
ORIGIN=P.parent/'packet100b-route-capture/evidence'
def main():
 limits();b=P/'build';b.mkdir(exist_ok=True)
 manifest=json.loads((ORIGIN/'route-inputs.json').read_text())
 assert manifest['passed'] and manifest['ready'] and len(manifest['rows'])==6144
 sources={str((ORIGIN/'route-inputs.json').relative_to(ROOT)):sha(ORIGIN/'route-inputs.json')}
 for name,h in manifest['sources'].items():assert sha(ROOT/name)==h,name
 rows=manifest['rows'];prompts=list(dict.fromkeys(r['prompt_id'] for r in rows));raw=bytearray()
 for prompt in prompts:
  for step in range(1,65):
   selected=sorted((r for r in rows if r['prompt_id']==prompt and r['fixture']==step),key=lambda r:r['layer'])
   assert [r['layer'] for r in selected]==list(range(48))
   for r in selected:
    path=ROOT/r['path'];data=path.read_bytes()[r['offset']:r['offset']+120]
    assert __import__('hashlib').sha256(data).hexdigest()==r['sha256']
    raw.extend(data);sources[r['path']]=sha(path)
 (P/'evidence/all-routes.bin').write_bytes(raw)
 cmd=['/usr/bin/g++','-std=c++20','-O2',str(P/'replay.cpp'),'-o',str(b/'replay')]
 with turn():subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL)
 subprocess.run([str(b/'replay'),str(P/'evidence/all-routes.bin'),str(P/'evidence/cases.bin')],check=True,stdin=subprocess.DEVNULL,stdout=(P/'evidence/replay.json').open('w'))
 sources[str((P.parent/'packet58j-onecard-port/cache_table.hpp').relative_to(ROOT))]=sha(P.parent/'packet58j-onecard-port/cache_table.hpp')
 row=dict(schema='packet125.routes.v1',passed=True,diagnostic_only=True,origin_sources=sources,all_routes_sha256=sha(P/'evidence/all-routes.bin'),cases_sha256=sha(P/'evidence/cases.bin'),semantics='Actual accepted target routes; SIMULATED empty 18GB global LRU, frozen packet58 Cache, publication after whole position, persists across two prompts; NOT observed one-card misses. All 64 steps replayed; checkpoints 1,16,32,64 measured, all48 layers.')
 (P/'evidence/route-inputs.json').write_text(json.dumps(row,indent=2)+'\n')
 print((P/'evidence/replay.json').read_text())
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2);main()
