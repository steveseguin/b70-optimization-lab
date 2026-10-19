"""Materialize the exact 58ah chain-b source closure; never run a device."""
import hashlib, json, os, shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
AH = P.parent / 'packet58ah-onecard-record'
AG = P.parent / 'packet58ag-onecard-ports'

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')

def destination(path):
    path = Path(path)
    return P / 'vendor' / path.relative_to(ROOT)

def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    assert shutil.disk_usage('/').free >= 27_000_000_000
    receipt = AH / 'lineage/58ag-build-receipt.json'
    pins = json.loads(receipt.read_text())['sources']
    rows = []
    for name, expected in pins.items():
        src = ROOT / name
        assert sha(src) == expected, name
        dst = destination(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == '.o':
            # Private bytes, never a symlink to mutable sibling objects.
            shutil.copy2(src, dst)
        else:
            data = src.read_bytes()
            try:
                data = data.decode().replace(str(ROOT) + '/', str(P / 'vendor') + '/').encode()
            except UnicodeDecodeError:
                pass
            dst.write_bytes(data)
        rows.append(dict(source=name, resolved_source=str(src.resolve().relative_to(ROOT)),
                         before=expected, destination=str(dst.relative_to(P)), after=sha(dst), bytes=dst.stat().st_size))
    save(P/'lineage/source-closure.json', dict(parent='packet58ah chain b',
         receipt_sha256=sha(receipt), files=rows, total_bytes=sum(r['bytes'] for r in rows)))
    for name in ('runtime-selection.json','selection.json','oracle-binding.json','admission.json'):
        shutil.copy2(AH/name, P/name)
    for name in ('58ag-build-receipt.json',):
        shutil.copy2(AH/'lineage'/name, P/'lineage'/name)
    for name in ('PLAN.md','DECISION.md','DO-NOT-REPEAT.md'):
        shutil.copy2(P.parent/'packet58al-demand-transfer-prep'/name, P/'lineage'/name)
    save(P/'lineage/parent-build-commands.json', json.loads((AG/'evidence/build.json').read_text())['commands'])
    save(P/'lineage/coordinator-override.json', dict(review=38, cpu_build_authorized=True,
         variant='bcs-demand-retained32x2', ready_for_device=False,
         release_condition='packet58ai census bound >= 1.000 ms/token',
         decision_sha256=sha(P.parent/'packet58al-demand-transfer-prep/DECISION.md')))
    print('Verified private source closure:', len(rows), sum(r['bytes'] for r in rows), 'bytes')

if __name__ == '__main__':
    main()
