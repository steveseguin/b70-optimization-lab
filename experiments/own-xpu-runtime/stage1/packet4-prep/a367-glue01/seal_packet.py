#!/usr/bin/env python3
"""CPU-only seal writer; does not authorize or launch a window."""
import json
from pathlib import Path
import battery_client as b
import test_battery as fixtures
import a367_glue01 as c
w = c.w
HERE = Path(__file__).resolve().parent

def main():
    origin = HERE.parent / 'a367-census/seal.json'
    files = dict(w.read(origin)['files'])
    # First verify all inherited bytes, never silently update protected dependencies.
    for path, digest in files.items():
        w.require(w.sha(w.REPO / path) == digest, 'inherited dependency drift: ' + path)
    members = [origin]
    members += [p for p in HERE.iterdir() if p.is_file() and p.name not in {'seal.json','owner-approval.pending.json'}]
    members += [w.REPO / name for name in b.DEPENDENCIES]
    members += [fixtures.DATA / (fixtures.PREFIX + name + '.json') for name in fixtures.TEST_DEPENDENCIES]
    members += [w.REPO / name for name in (
        'patches/flash-next-m2-glue-fusion-01-row-copy.patch',
        'notes/2026-10-16-flash-next-moe-m2-lever-study.md',
        'notes/2026-10-16-flash-next-m2-glue-fusion-design.md',
        'scripts/check-storage-headroom.py', 'experiments/ltx25-b70/scripts/check-four-card-health.py')]
    resolution = w.read(HERE / 'resolved-fault.json')
    members += [w.REPO / resolution[key] for key in ('kernel_window_path','probe_receipt_path')]
    for path in members:
        relative = str(path.relative_to(w.REPO))
        digest = w.sha(path)
        w.require(relative not in files or files[relative] == digest, 'inherited pin collision')
        files[relative] = digest
    b.verify_dependencies()
    seal = {'schema':'own-xpu-runtime.packet4.a367-glue01-seal.v1',
            'origin_commit':'7a5176c5dd9ab4bad6597653d07cf8a95078edca', 'files':dict(sorted(files.items()))}
    w.write(c.SEAL, seal)
    pending = {'schema':'a367-glue01-owner-approval.pending.v1',
        'glue_preregistration_sha256':w.sha(c.REG),'glue_seal_sha256':w.sha(c.SEAL),
        'recording_authority':'coordinator records under owner standing instruction in the glue01 CPU-build brief',
        'glue_memory_exception':{'approved':False,'approved_by':'owner','minimum_mem_available_kib':114840824,
                                 'owner_approval_text':c.glue_approval_text()}}
    w.write(HERE/'owner-approval.pending.json', pending)
    print(json.dumps({'seal_sha256':w.sha(c.SEAL),'preregistration_sha256':w.sha(c.REG),'files':len(files)}))

if __name__ == '__main__':
    main()
