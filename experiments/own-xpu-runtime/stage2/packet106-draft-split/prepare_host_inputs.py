"""Pin existing immutable CPU fixtures locally; no build, model or device run."""
import json,os
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
def main():
 limits();parent=P.parent/'packet97-record-bundle'
 oracle=P/'oracle'
 if not oracle.exists():oracle.symlink_to('../packet49-integrate/oracle',target_is_directory=True)
 for name in ('oracle-binding.json','runtime-revision.json','kernel-registry.json','k2-class-registry.json','extension-slots.json'):
  src=parent/name
  if src.is_file() and not (P/name).exists():(P/name).write_bytes(src.read_bytes())
 save(P/'chain-registration.json',dict(output='device-cards01-p106-unqualified'))
 rows=[]
 for src in sorted((parent/'build/gnu-host').iterdir()):
  if not src.is_symlink() or not src.is_file():continue
  dest=B/'gnu-host'/src.name
  if not dest.exists():os.link(src.resolve(),dest)
  assert sha(src)==sha(dest)
  rows.append(dict(source=str(src.resolve()),local=str(dest.relative_to(ROOT)),sha256=sha(dest)))
 save(P/'evidence/host-fixture-inputs.json',dict(passed=True,device_executed=False,fixtures=rows))
 print('Pinned CPU fixtures',len(rows))
if __name__=='__main__':main()
