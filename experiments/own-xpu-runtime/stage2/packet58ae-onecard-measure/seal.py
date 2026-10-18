"""Seal CPU preparation, explicitly separate from device readiness."""
import json,resource,subprocess
from build_engine import P,ROOT,sha,save,limits
from cpu_seal import verify
GATES=['evidence/build-measure.json','evidence/reset-gate.json','evidence/cpu-tests.json','evidence/entry-report.json','evidence/final-cpu-checks.json']
def create():
    limits();native=json.loads((P/'evidence/build-measure.json').read_text());assert native['passed']
    gates={}
    for n in GATES:
        row=json.loads((P/n).read_text());assert row['passed'],n;gates[n]=sha(P/n)
    files=[*P.glob('*.py'),*P.glob('*.json'),P/'.gitignore']
    for folder in ('native','sources','host-admission','selections','proposals'):
        files.extend(f for f in (P/folder).rglob('*') if f.is_file() and '__pycache__' not in f.parts)
    files.extend([P/'lineage/vendor58z/lineage/58x-build-source.tar.gz',P/'lineage/vendor-copy-manifest.json'])
    sources=dict(native['sources'])
    for f in files:
        if f.name not in ('build-receipt.json','READY-FOR-DEVICE.json') or f.parent!=P:sources[str(f.relative_to(ROOT))]=sha(f)
    sources.update(json.loads((P/'oracle-binding.json').read_text())['files_sha256'])
    for name in ('single_device.cpp','owner.cpp','owner_retire.cpp','fullshape_submit_test.hpp','postload_allocation_test.hpp'):
        f=P/'lineage/supplemental'/name;sources[str(f.relative_to(ROOT))]=sha(f)
    # Objects consumed by the link are immutable ELF inputs. Their identity was
    # independently checked by reproducing the two frozen parent executables.
    for name,digest in sources.items():assert sha(ROOT/name)==digest,name
    size=sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file());assert size<=300_000_000
    row=dict(schema='own-runtime.packet58.build.v1',passed=True,device_executed=False,sources=sources,
        artifacts=native['artifacts'],gates=gates,retained_build_bytes=size,arithmetic='iq3-p49-split32-v1',
        gpu_count=1,decode_mode='plain',kv_dtype='BF16',cache_allocation_bytes=21552729600,
        runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),
        qualification='Compilation, miniature bytes and report gates only. Arm 2 split and launch integration incomplete; device execution refused.')
    save(P/'build-receipt.json',row);verify();return row
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));r=create();print('CPU seal written; not device readiness')
