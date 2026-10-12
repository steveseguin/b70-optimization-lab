#!/usr/bin/env python3
"""Hash the final overlay against both sealed parents and their common base."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

def main():
 files={}
 for path in sorted(P.rglob('*')):
  rel=path.relative_to(P)
  if not path.is_file() or any(part in ('build','__pycache__','evidence') for part in rel.parts):continue
  if path.suffix not in ('.cpp','.hpp','.py') and path.name not in ('CMakeLists.txt',):continue
  files[str(rel)]={'sha256':sha(path),**{packet+'_sha256':sha(P.parent/(packet+'-'+lane)/rel) for packet,lane in [('packet32','pipeline'),('packet36','draft'),('packet37','merged2')]}}
 report=dict(base_commit='2e8ec7585c',packet36_commit='3048343bff',packet37_commit='3c03e29a4e',files=files)
 (P/'source-overlay.json').write_text(json.dumps(report,indent=2)+'\n')
 print(len(files),'source files inventoried against all three parents')
if __name__=='__main__':main()
