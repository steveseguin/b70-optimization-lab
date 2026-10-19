import json,resource
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
S=Path(__file__).resolve().parent.parent
for name,root in [('two',S/'packet136-record-bundle/build/device-cards01-a/WS128/run'),('one',S/'packet58aj-onecard-resident/evidence/card0-58aj-a/WS128/run')]:
 files=[f for f in root.rglob('*') if f.is_file() and not f.is_symlink()]
 sizes={}
 for f in files:
  key=f.suffix;sizes[key]=sizes.get(key,0)+f.stat().st_size
 states=[json.loads(f.read_text()) for f in root.rglob('state-retention.json')]
 print(name,dict(bytes=sum(f.stat().st_size for f in files),by_suffix=sizes,largest=max((f.stat().st_size,str(f))for f in files),states=[{k:r[k]for k in ('original_bytes','retained_bytes')}for r in states[:2]],maximum_state=max([r['original_bytes']for r in states]or[0])))
