"""Pin existing immutable CPU fixtures locally; no build, model or device run."""
import json,os,subprocess
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
 manifest=parent/'input-fixtures.json'
 frozen=subprocess.check_output(['git','show','386faa9ee:'+str(manifest.relative_to(ROOT))],cwd=ROOT)
 assert frozen==manifest.read_bytes(), 'fixture manifest changed from packet97e'
 (P/'input-fixtures.json').write_bytes(frozen)
 source=parent/'build/fusion-fixtures';dest=B/'fusion-fixtures'
 if not dest.exists():dest.symlink_to(source.resolve(),target_is_directory=True)
 assert dest.resolve()==source.resolve()
 sources={str((P/'input-fixtures.json').relative_to(ROOT)):sha(P/'input-fixtures.json')}
 for name,item in json.loads(frozen)['files'].items():
  f=dest/name;assert f.stat().st_size==item['bytes'] and sha(f)==item['sha256'],name
  sources[str(f.relative_to(ROOT))]=item['sha256']
 save(P/'evidence/host-fixture-inputs.json',dict(passed=True,device_executed=False,fixtures=rows,sources=sources,fixture_manifest_commit='386faa9ee',payload_copied=False))
 print('Pinned CPU fixtures',len(rows))
if __name__=='__main__':main()
