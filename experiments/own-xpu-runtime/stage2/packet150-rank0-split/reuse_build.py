"""Reuse packet131b native identity and exact state proof; never its speed verdict."""
import json,shutil
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
OLD=P.with_name('packet131b-snapshot-banks');SNAP=P/'parent-snapshot'
def verify_native():
 from source_gate136 import verify_sources
 row=json.loads((OLD/'evidence/ready131.json').read_text())
 assert row['passed'] and row['device_executed'] is False
 verify_sources(row['sources'])
 for mode in ('gnu-host','device'):
  assert sha(B/mode/'own-rt-iq3')==sha(OLD/'build'/mode/'own-rt-iq3')
 for f in OLD.glob('*'):
  if f.suffix in ('.cpp','.hpp','.inc','.bf16','.tsv') and f.is_file():
   # Dedicated state/census fixtures are retained by the parent, not runtime inputs.
   if (P/f.name).exists():assert sha(P/f.name)==sha(f),'native source differs: '+f.name
 from bundle_selection import views,selection
 for value,label in zip(views().values(),('control','candidate')):
  assert selection(value)==json.loads((OLD/'selections'/label/'selection.json').read_text()),'identical-selection rule: '+label
 return row
def native_sources():
 row=verify_native();sources=dict(row['sources'])
 for f in P.glob('*'):
  if f.suffix in ('.cpp','.hpp','.inc','.bf16','.tsv') and f.is_file():sources[str(f.relative_to(ROOT))]=sha(f)
 sources[str((OLD/'evidence/ready131.json').relative_to(ROOT))]=sha(OLD/'evidence/ready131.json')
 return sources
def main():
 limits();artifacts={}
 for mode in ('gnu-host','device'):
  dest=B/mode/'own-rt-iq3';dest.parent.mkdir(exist_ok=True);shutil.copy2(OLD/'build'/mode/'own-rt-iq3',dest)
  artifacts[str(dest.relative_to(P))]=sha(dest)
 verify_native()
 commands=json.loads((OLD/'engine-commands.json').read_text())
 # Startup helpers consume the flags before -o, then append their own source.
 for row in commands:
  if row['name'].endswith('-entry-main'):
   argv=row['command'];i=argv.index('-c');del argv[i:i+2]
 save(P/'engine-commands.json',commands)
 from kernel_gate import mirror
 mirror();sources=native_sources()
 for f in (P/'reuse_build.py',P/'source_gate136.py',P/'build_engine.py',P/'engine-commands.json'):
  sources[str(f.relative_to(ROOT))]=sha(f)
 save(P/'build-device-receipt.json',dict(schema='packet136.binary-reuse.v1',passed=True,device_executed=False,sources=sources,artifacts=artifacts,scope='Byte-identical packet131b native binaries and exact bank-state CPU proof. Device quality/speed pending.'))
 print('packet131b GNU/device identity and both selections verified')
if __name__=='__main__':main()
