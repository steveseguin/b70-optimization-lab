"""Restore local historical fixture payloads and original aliases, never model bytes."""
import hashlib,json,os,resource,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
def digest(data):return hashlib.sha256(data).hexdigest()
def main():
 from v5.p142_v5_build_engine import limits
 limits();manifest=json.loads((P/'lineage-inputs/legacy-fixtures.json').read_text());archive=P/manifest['archive']
 assert digest(archive.read_bytes())==manifest['sha256']
 with tarfile.open(archive,'r:gz') as t:
  assert set(t.getnames())==set(manifest['members'])
  for name,sha in manifest['members'].items():
   target=P/name;assert target.resolve().is_relative_to(P)
   data=t.extractfile(name).read();assert digest(data)==sha
   if target.exists():assert digest(target.read_bytes())==sha
   else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 links=json.loads((P/'lineage-inputs/current-aliases.json').read_text())
 for name,target in links.items():
  path=P/name
  if path.is_symlink():assert str(path.readlink())==target
  else:
   assert not path.exists();path.parent.mkdir(parents=True,exist_ok=True);path.symlink_to(target)
 limits();print('Restored historical local fixtures and aliases; no native execution')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
