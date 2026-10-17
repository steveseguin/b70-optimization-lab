#!/usr/bin/env python3
"""Reseal packet70 wrapper sources; preserve every screen artifact and selection."""
import json
import os
from pathlib import Path
from storage import B, digest
from chain_seal import check_map
from build_engine import save
from bundle_selection import EXPERTS
from stopped_archive import require_fresh_chain
P = Path(__file__).resolve().parent
ROOT = P.parents[3]


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32))
    require_fresh_chain(B)
    from prepare_selections import main as verify_views
    verify_views()
    wrappers = ('p49_dispatch.py', 'prepare_selections.py', 'seal_and_plan.py',
                'fast_reseal.py', 'stopped_archive.py', 'archived-chains.json',
                'test_selection_postprocessing.py', 'test_stopped_archive.py',
                'evidence/k2fix-archive.json', 'evidence/k2fix-regression-after.log')
    # Verify every view before writing any new seals; retain each original.
    pending = []
    for expert in EXPERTS:
        view = P/'selections'/('1-draft-hc-batch-'+expert)
        path = view/'screen-seal.json'
        row = json.loads(path.read_text())
        archive = P/'evidence'/('k2fix-screen-seal-'+expert+'-'+digest(path)+'.json')
        if not archive.exists():
            archive.write_bytes(path.read_bytes())
        row['sources'].update({str((P/name).relative_to(ROOT)):digest(P/name) for name in wrappers})
        for key in ('artifacts', 'gates', 'fixture_files'):
            check_map(view, row[key])
        pending.append((path, row))
    for path, row in pending:
        save(path, row)
    print('PASS: five wrapper seals regenerated; screen artifacts unchanged; no device execution')


if __name__ == '__main__':
    main()
