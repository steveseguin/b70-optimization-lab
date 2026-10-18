"""Replace only new packet object copies with verified links to frozen inputs."""
import os
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits
import json
def main():
 limits();rows=[]
 for item in json.loads((P/'evidence/object-identity.json').read_text())['objects']:
  source=ROOT/item['source'];dest=ROOT/item['local']
  assert dest.is_relative_to(P/'build') and not source.is_relative_to(P)
  assert source.resolve().is_relative_to(ROOT) and sha(source)==sha(dest)==item['sha256']
  if not dest.is_symlink():
   temporary=dest.with_suffix(dest.suffix+'.link');temporary.symlink_to(source);os.replace(temporary,dest)
  rows.append(dict(source=item['source'],local=item['local'],sha256=item['sha256']))
 save(P/'evidence/immutable-object-links.json',dict(passed=True,device_executed=False,
      reason='Frozen inherited inputs linked, not copied; no object bytes discarded or changed',objects=rows))
 print('Linked',len(rows),'immutable object inputs',flush=True)
if __name__=='__main__':main()
