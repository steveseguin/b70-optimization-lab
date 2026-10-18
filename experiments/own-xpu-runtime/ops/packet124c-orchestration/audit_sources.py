"""Read-only native-identity, memory and storage audit; no parent mutation."""
import json,shutil,sys
from source_decision import O,P,ROOT,sha,save
sys.path.insert(0,str(P))
def main():
 from reuse_build import native_sources
 sources=native_sources()
 old=json.loads((P/'parent-snapshot/build-device-receipt.json').read_text())
 binaries={name:sha(P/name) for name in old['artifacts']}
 assert binaries==old['artifacts'],'runtime binary changed'
 assert sha(P/'selection.json')==sha(O/'inputs/bundle7-selection.json')
 assert sha(P/'memory-plan.json')==sha(O/'inputs/bundle7-memory-plan.json')
 size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file() and not f.is_symlink())
 free=shutil.disk_usage('/').free;assert size<=250_000_000 and free>=25_000_000_000
 row=dict(passed=True,device_executed=False,native_sources=sources,binaries=binaries,native_changes=[],
     vram_unchanged=True,selection_unchanged=True,build_bytes=size,root_free_bytes=free,
     shape_evidence_sha256=sha(P/'evidence/full-shape.json'))
 save(O/'source-audit.json',row);print(json.dumps({k:v for k,v in row.items() if k!='native_sources'}))
if __name__=='__main__':main()
