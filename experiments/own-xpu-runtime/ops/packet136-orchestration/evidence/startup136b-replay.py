import sys,json,gzip,resource
from pathlib import Path
from unittest.mock import patch
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
p=Path('experiments/own-xpu-runtime/stage2/packet136-record-bundle').resolve();sys.path.insert(0,str(p))
import startup103 as s
from build_engine import sha,ROOT
row=json.loads((p/'startup103.json').read_text())
changed=[n for n,h in row['sources'].items() if sha(ROOT/n)!=h]
assert changed==[str((p/'confirm136.py').relative_to(ROOT))],changed
archive=ROOT/row['archive']['path'];assert sha(archive)==row['archive']['sha256']
raw=gzip.decompress(archive.read_bytes());old=json.loads(raw)
for file in (p/'startup103.json',archive):
 dest=p/'evidence'/('before-136b-'+sha(file)+'-'+file.name)
 if not dest.exists():dest.write_bytes(file.read_bytes())
files=[s.S/n for n in ('main.cpp','mtp.hpp','entry.cpp')]
for f in [*files,s.S/'fixture']:assert row['sources'][str(f.relative_to(ROOT))]==sha(f)
with patch.object(s,'build',return_value=(files,old['commands'])):s.main()
