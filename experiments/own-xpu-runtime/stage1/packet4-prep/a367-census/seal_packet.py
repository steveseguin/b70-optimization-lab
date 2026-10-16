#!/usr/bin/env python3
"""CPU-only maintainer seal writer; never records owner approval or launches work."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inherited = json.loads((HERE.parent / 'a367-replay/seal.json').read_text())['files']
    files = dict(inherited)
    members = [HERE.parent / 'a367-replay/seal.json']
    members += [p for p in HERE.iterdir() if p.is_file() and p.name not in {'seal.json', 'owner-approval.pending.json'}]
    members += [REPO / 'notes' / name for name in (
        '2026-10-16-flash-next-a367-record-replay.md',
        '2026-10-16-flash-next-a367-calibration-attempts.md',
        '2026-10-16-flash-next-m2-glue-fusion-design.md',
        '2026-10-16-flash-next-fp8-return-survey.md')]
    for p in members:
        files[str(p.relative_to(REPO))] = sha(p)
    # Do not silently refresh protected dependency pins.
    for relative, digest in files.items():
        if sha(REPO / relative) != digest:
            raise ValueError('dependency drift: ' + relative)
    seal = HERE / 'seal.json'
    seal.write_text(json.dumps({'schema': 'own-xpu-runtime.packet4.a367-census-seal.v1', 'files': dict(sorted(files.items()))}, indent=2) + '\n')
    import a367_census as c
    pending = {'schema': 'own-xpu-runtime.packet4.a367-census-owner-approval.pending.v1',
        'census_preregistration_sha256': sha(HERE / 'preregistration.json'), 'census_seal_sha256': sha(seal),
        'census_memory_exception': {'approved': False, 'approved_by': 'owner',
            'minimum_mem_available_kib': 114840824, 'owner_approval_text': c.census_approval_text()}}
    (HERE / 'owner-approval.pending.json').write_text(json.dumps(pending, indent=2) + '\n')
    print(json.dumps({'seal_sha256': sha(seal), 'preregistration_sha256': sha(HERE / 'preregistration.json'), 'files': len(files)}))


if __name__ == '__main__':
    main()
