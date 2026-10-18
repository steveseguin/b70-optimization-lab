"""Seal this packet only. No parent orchestration or selection file is pinned."""
import json,subprocess,sys
from build_engine import P,ROOT,B,sha,save,limits

def main():
 limits()
 sys.path.insert(0,str(P.parent/'screen/v4-lanes'))
 from cpu_seal import verify as verify_wrapper
 wrapper=verify_wrapper()
 build=json.loads((P/'build-receipt.json').read_text())
 sources=dict(build['sources']);artifacts=dict(build['artifacts'])
 for leaf in ('capture-cpu.json','full-shape.json','microbench-build.json'):
  row=json.loads((P/'evidence'/leaf).read_text())
  assert row['passed'] and not row['device_executed']
  sources.update(row['sources']);artifacts.update(row.get('artifacts',{}))
  sources[str((P/'evidence'/leaf).relative_to(ROOT))]=sha(P/'evidence'/leaf)
 for name,digest in sources.items():assert sha(ROOT/name)==digest,name
 for name,digest in artifacts.items():assert sha(P/name)==digest,name
 with (P/'evidence/python-tests.log').open('w') as log:
  subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(P),'-p','test_packet100b.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 save(P/'evidence/python-tests.json',dict(passed=True,device_executed=False,tests=23,log_sha256=sha(P/'evidence/python-tests.log')))
 local=[*P.glob('*.py'),*P.glob('*.hpp'),*P.glob('*.cpp'),P/'selection.json',P/'memory-plan.json',P/'dispatch-speed6.json',P/'suite.snapshot.json',P/'shared-wrapper-pin.json',P/'build-receipt.json',P/'micro-origin.snapshot.json',P/'parent-commands.snapshot.json',P/'evidence/python-tests.json',P/'evidence/python-tests.log']
 sources.update({str(f.relative_to(ROOT)):sha(f) for f in local})
 # Compiled parent headers/objects are immutable implementation inputs. Parent
 # decisions, selection files, build receipts and ops/evidence JSON are not.
 for name in sources:
  if not name.startswith(str(P.relative_to(ROOT))+'/'):
   assert not ('/ops/' in name or '/evidence/' in name or name.endswith('.json')),name
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file())
 assert size<=300_000_000,size
 save(P/'packet-seal.json',dict(schema='packet100b.cpu-preparation.v1',passed=True,device_executed=False,
  diagnostic_only=True,sources=sources,artifacts=artifacts,build_bytes=size,
  wrapper_seal_sha256=sha(P.parent/'screen/v4-lanes/wrapper-seal.json'),
  device_exactness='pending: both 64-token outputs must match existing oracle',
  performance='pending: original packet100 15% per-route/both-order gate'))
 print('packet100b CPU seal PASS; build bytes',size)
if __name__=='__main__':main()
