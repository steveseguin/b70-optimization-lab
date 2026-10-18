"""Reuse packet130's exact qualified binaries and source closure; never parent device results."""
import json,shutil,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
OLD=P.with_name('packet130-suffix-interleave');V=OLD/'v5';SNAP=P/'parent-snapshot'
def verify_native():
 row=json.loads((V/'lineage/screen-seal.json').read_text())
 assert row['passed'] and row['device_executed'] is False
 for n,h in row['sources'].items():assert sha(ROOT/n)==h,'p130 CPU/native source changed: '+n
 for mode in ('gnu-host','device'):
  assert sha(B/mode/'own-rt-iq3')==sha(V/'build'/mode/'own-rt-iq3')
 for f in OLD.glob('*'):
  if f.suffix in ('.cpp','.hpp','.inc') and f.is_file():assert sha(P/f.name)==sha(f),'native source differs: '+f.name
 from bundle_selection import views,selection
 for value,leaf in zip(views().values(),('selection.json','candidate.json')):
  assert selection(value)==json.loads((V/'lineage'/leaf).read_text()),'identical-selection rule: '+leaf
 return row

def native_sources():
 row=verify_native();sources=dict(row['sources'])
 for f in P.glob('*'):
  if f.suffix in ('.cpp','.hpp','.inc','.bf16','.tsv') and f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 sources[str((V/'lineage/screen-seal.json').relative_to(ROOT))]=sha(V/'lineage/screen-seal.json')
 return sources

def main():
 limits();artifacts={}
 for mode in ('gnu-host','device'):
  dest=B/mode/'own-rt-iq3';dest.parent.mkdir(exist_ok=True);shutil.copy2(V/'build'/mode/'own-rt-iq3',dest)
  artifacts[str(dest.relative_to(P))]=sha(dest)
 verify_native()
 # Keep the exact compiler/link identities for local CPU startup fixtures.
 (P/'engine-commands.json').write_bytes((V/'engine-commands.json').read_bytes())
 from kernel_gate import mirror
 mirror()
 sources=native_sources()
 for f in (P/'reuse_build.py',P/'build_engine.py',P/'engine-commands.json'):
  sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'build-device-receipt.json',dict(schema='packet133.binary-reuse.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,scope='Byte-identical packet130 v5 native binary, unchanged arithmetic; new chain qualification is independent'))
 print('packet130 v5 GNU and device binaries reused by exact hash')
if __name__=='__main__':main()
