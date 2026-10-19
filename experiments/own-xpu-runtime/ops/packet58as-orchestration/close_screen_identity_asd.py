"""packet58asd: keep the active screen closure pin-clean after the one rebuild.

Snapshots the p58asc closure, then points the two changed native sources at
their byte-identical lineage/packet58asd-before copies and the rebuilt device
executable at the retained bracket copy (screen/build -> ../build). The three
recompiled entry-main.o intermediates have no retained copy: they leave the
digest map and are listed with their bracket digests. The original screen seal
(lineage/packet58asc-before/screen-build-receipt.json) is untouched.
"""
import hashlib,json,resource,shutil
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
O=Path(__file__).resolve().parent;R=O.parents[3];P=R/'experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait';H2=P/'lineage/packet58asd-before'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
active=P/'screen/build-receipt.json';snapshot=H2/'screen-build-receipt.json'
assert not snapshot.exists();shutil.copy2(active,snapshot)
row=json.loads(active.read_text());sources={};superseded=[]
for n,h in row['sources'].items():
 f=R/n;rel=str(f.relative_to(P)) if f.is_relative_to(P) else None
 if rel in ('native/generated/main.cpp','native/bracket_table.hpp'):
  f=H2/rel;assert sha(f)==h,rel
 elif rel in tuple(f'build/{m}/entry-main.o' for m in ('device','gnu-host','intel-host')):
  superseded.append(dict(object=rel,bracket_sha256=h));continue
 sources[str(f.relative_to(R))]=h
assert len(superseded)==3
artifacts={}
for n,h in row['artifacts'].items():
 if n=='build/device/own-rt-iq3':n='build/bracket/device/own-rt-iq3'
 assert sha(P/'screen'/n)==h,n;artifacts[n]=h
row.update(sources=sources,artifacts=artifacts,superseded_bracket_objects=superseded,
 closure_before_packet58asd=dict(name='p58asc active screen closure',parent_relpath=str(snapshot.relative_to(R)),parent_digest=sha(snapshot)))
active.write_text(json.dumps(row,indent=2)+'\n')
print('Active screen closure points at retained bracket bytes; original screen seal untouched')
