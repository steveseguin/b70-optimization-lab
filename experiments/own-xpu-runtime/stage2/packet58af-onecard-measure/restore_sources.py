"""Restore ignored source snapshots from the vendored packet58z archive only."""
import hashlib,json,os,resource,shutil,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
OLD=P.parent/'packet58x-cache-capacity'

def digest(data):return hashlib.sha256(data).hexdigest()
def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    assert shutil.disk_usage('/').free>=25_000_000_000
    manifest=json.loads((P/'copy-manifest.json').read_text());archive=P/manifest['archive']
    assert digest(archive.read_bytes())==manifest['archive_sha256']
    with tarfile.open(archive) as tar:
        for member in tar:
            assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
            raw=tar.extractfile(member).read();out=P/'lineage/snapshot'/member.name
            out.parent.mkdir(parents=True,exist_ok=True)
            if out.exists():assert out.read_bytes()==raw
            else:out.write_bytes(raw)
    snap=P/'lineage/snapshot'/OLD.relative_to(ROOT)
    frozen=P/'lineage/frozen-inputs'
    # These two private checked headers are deterministic instrumented outputs.
    # Reset them from retained pristine templates before archive verification.
    checked=frozen/'repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
    for name in ('p49d_expert.hpp','p100_down.hpp'):
        template=P/'native/templates'/name
        if template.exists() and (checked/name).exists():(checked/name).write_bytes(template.read_bytes())
    for source in (snap/'frozen-inputs').rglob('*'):
        if not source.is_file():continue
        out=frozen/source.relative_to(snap/'frozen-inputs');raw=source.read_bytes()
        if source.suffix in ('.py','.cpp','.hpp','.h','.make') or source.name=='link.txt':raw=raw.replace(str(OLD).encode(),str(P).encode())
        out.parent.mkdir(parents=True,exist_ok=True)
        if out.exists():assert out.read_bytes()==raw
        else:out.write_bytes(raw)
    for name in ('58xb-source-snapshot.json','58xb-source-snapshot.tar.gz'):
        target=P/'lineage'/name;raw=(snap/'lineage'/name).read_bytes()
        if target.exists():assert target.read_bytes()==raw
        else:target.write_bytes(raw)
    link=P/'frozen-inputs'
    if not link.exists():link.symlink_to('lineage/frozen-inputs',target_is_directory=True)
    import frozen_inputs
    frozen_inputs.restore()
    print('source snapshots restored; no model/full-shape reads, compilation or device execution')
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
