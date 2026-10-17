#!/usr/bin/env python3
"""Retain the exact small-fixture bytes compressed, or restore without overwrites."""
import argparse,gzip,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
def digest(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--restore',action='store_true');a=ap.parse_args()
 manifest=P/'fixture/retention.json'
 if a.restore:
  for r in json.loads(manifest.read_text())['files']:
   archive=P/r['archive'];raw=gzip.decompress(archive.read_bytes());assert digest(raw)==r['sha256']
   dest=P/r['path']
   if dest.exists():assert dest.read_bytes()==raw
   else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
 else:
  files=[]
  for p in sorted((P/'fixture').rglob('*.bin')):
   raw=p.read_bytes();compressed=gzip.compress(raw,compresslevel=6,mtime=0);archive=p.with_suffix('.bin.gz');archive.write_bytes(compressed)
   assert gzip.decompress(compressed)==raw
   files.append(dict(path=str(p.relative_to(P)),archive=str(archive.relative_to(P)),bytes=len(raw),sha256=digest(raw),archive_sha256=digest(compressed)))
  manifest.write_text(json.dumps(dict(schema='packet66.fixture-retention.v1',files=files),indent=2)+'\n')
 print('fixture bytes verified')
if __name__=='__main__':main()
