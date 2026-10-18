"""CPU-only frozen binary reuse; no compiler, model payload or device execution."""
import json, shutil
from pathlib import Path
from build_engine import P, ROOT, B, sha, save, limits
OLD = P.with_name('packet118-record-bundle')
SNAP = P/'parent-snapshot'
def native_sources():
    copied=json.loads((P/'copy-lineage.json').read_text())['copied_files'];sources={}
    for name,digest in copied.items():
        f=P/name
        if f.suffix in ('.cpp','.hpp','.inc','.bf16','.tsv') and isinstance(digest,str):
            assert sha(f)==digest, 'native bytes changed: '+name
            sources[str(f.relative_to(ROOT))]=digest
    for f in (SNAP/'build-device-receipt.json',SNAP/'engine-commands.json',P/'copy-lineage.json'):
        sources[str(f.relative_to(ROOT))]=sha(f)
    return sources
def main():
    limits();assert shutil.disk_usage('/').free>=25_000_000_000
    original=json.loads((SNAP/'build-device-receipt.json').read_text());sources=native_sources();artifacts={}
    for name,digest in original['artifacts'].items():
        assert sha(P/name)==digest,name
        artifacts[name]=digest
    for name,digest in original['sources'].items():
        src=ROOT/name
        # Generated mirror includes absolute paths. Its old bytes are described
        # by the snapshot; fresh CPU fixtures bind the regenerated local mirror.
        if '/build/checked/' in name:continue
        if src.suffix not in ('.cpp','.hpp','.inc','.o','.bf16','.tsv'):continue
        local=Path(str(src).replace(str(OLD),str(P)))
        assert sha(local)==digest,str(local)
        sources[str(local.relative_to(ROOT))]=digest
    (P/'engine-commands.json').write_text((SNAP/'engine-commands.json').read_text().replace(str(OLD),str(P)))
    from kernel_gate import mirror
    mirror()
    for f in (P/'reuse_build.py',P/'build_engine.py',P/'engine-commands.json'):
        sources[str(f.relative_to(ROOT))]=sha(f)
    size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink());assert size<=250_000_000,size
    save(P/'build-device-receipt.json',dict(schema='packet124.binary-reuse.v1',passed=True,device_executed=False,
        sources=sources,artifacts=artifacts,build_logical_bytes=size,source_snapshot_sha256=sha(SNAP/'build-device-receipt.json'),
        scope='GNU host and SYCL device binaries copied byte-identically from packet118; no native rebuild'))
    print('byte-identical native binaries; build bytes',size,flush=True)
if __name__=='__main__':main()
