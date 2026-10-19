"""Restore pinned local objects, then rebuild the private entry. Never starts devices."""
import argparse,json,resource,shutil,subprocess
from pathlib import Path
from build_engine import P,ROOT,turn,limits,sha
ap=argparse.ArgumentParser();ap.add_argument('packet',choices=['one-card','two-card']);ap.add_argument('--compile',action='store_true');a=ap.parse_args();p=P/a.packet
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);limits()
r=json.loads((p/'lineage/build-inputs.json').read_text())
for local,row in r['objects'].items():
 f=p/local
 if not f.exists():
  source=ROOT/row['source'];assert sha(source)==row['sha256'],'original kernel object changed'
  f.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,f)
 assert sha(f)==row['sha256'],'private kernel object changed'
for row in json.loads((p/'runtime-constants.json').read_text()):
 f=p/row['local']
 if not f.exists():
  source=ROOT/row['source'];assert sha(source)==row['sha256'];f.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,f)
 assert sha(f)==row['sha256'],'rotary/manifest bytes changed'
if a.compile:
 for label in ['compile','link']:
  with turn():
   limits();subprocess.run(r[label],stdin=subprocess.DEVNULL,check=True)
expected=json.loads((p/'identity.json').read_text())['binary_sha256'];assert sha(p/'build/device/own-rt-iq3')==expected,'rebuild differs; do not refresh READY or adopt silently'
print(a.packet,'restored object/constants and binary identity PASS; device not executed')
