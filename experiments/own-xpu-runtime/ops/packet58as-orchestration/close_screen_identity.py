"""Retain original screen seal and expose its historical source paths to pin admission."""
import hashlib,json,resource,shutil
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
O=Path(__file__).resolve().parent;R=O.parents[3];P=R/'experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait';H=P/'lineage/packet58asc-before'
old=P/'screen/build-receipt.json';snapshot=H/'screen-build-receipt.json'
assert not snapshot.exists();shutil.copy2(old,snapshot)
row=json.loads(old.read_text());sources={}
for n,h in row['sources'].items():
 f=R/n
 if f.parent==P and (H/f.name).is_file():f=H/f.name
 sources[str(f.relative_to(R))]=h
row['sources']=sources;row['historical_screen_seal']=dict(name='original screen seal',parent_relpath=str(snapshot.relative_to(R)),parent_digest=hashlib.sha256(snapshot.read_bytes()).hexdigest())
old.write_text(json.dumps(row,indent=2)+'\n')
f=P/'screen_gate.py';s=f.read_text().replace("P/'screen/build-receipt.json'","P/'lineage/packet58asc-before/screen-build-receipt.json'");f.write_text(s)
f=P/'verify_ready.py';s=f.read_text().replace("screen_sources=screen['sources']", "screen_evidence=[dict(name=Path(n).name,parent_relpath=n,parent_digest=h) for n,h in screen['sources'].items()]").replace('58aj smoke/v5 pending or invalid','58as v5 pending or invalid');f.write_text(s)
print('Original screen seal retained byte-for-byte; active closure names historical sources explicitly')
