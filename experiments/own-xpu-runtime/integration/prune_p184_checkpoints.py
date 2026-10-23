#!/usr/bin/env python3
"""Prune only verified archived tensor copies; retain metadata and controls."""
import argparse
import json
import os
import shutil

import archive_p184_checkpoints as A

RECEIPT = A.EVIDENCE / 'checkpoint-local-prune-20261023.json'
MARKER = A.EVIDENCE / 'ARCHIVED-CHECKPOINTS-20261023.json'


def write(path, row, mode='x'):
    with path.open(mode) as file:
        json.dump(row, file, indent=2)
        file.write('\n')
        file.flush()
        os.fsync(file.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prune-verified-copies', action='store_true', required=True)
    parser.parse_args()
    A.require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and
              set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'helper placement required')
    A.require(not os.path.lexists(RECEIPT) and not os.path.lexists(MARKER), 'prior prune attempt exists; no retry')
    archive = A.read(A.RECEIPT)
    A.require(archive['passed'] and archive['original_files_unchanged'] and archive['deleted_files'] == 0,
              'successful copy and complete readback required')
    pin = A.pin(A.ARCHIVE)
    A.require(pin['sha256'] == archive['archive_sha256'] and pin['stamp'] == archive['archive_stamp'],
              'verified archive changed')
    originals = A.inventory()  # Rechecks every original native hash and closed-run/source guard.
    A.require(originals == archive['originals'] and not originals['tracked_tensor_candidates'],
              'originals/guards changed or tracked tensor deletion attempted')
    candidates = {name: row for name, row in originals['files'].items() if row['tensor_prune_candidate']}
    A.require(len(candidates) == 796 and sum(row['stamp']['bytes'] for row in candidates.values()) == A.TENSOR_BYTES,
              'fixed prune scope changed')
    result = dict(schema='p184-verified-tensor-prune-v1', passed=False, started_utc=A.utc(),
                  archive_receipt_sha256=A.pin(A.RECEIPT)['sha256'], archive_sha256=pin['sha256'],
                  script_sha256=A.pin(A.Path(__file__))['sha256'], removed_files=[], removed_bytes=0,
                  root_free_before_bytes=shutil.disk_usage(A.ROOT).free)
    write(RECEIPT, result)
    try:
        for name, expected in sorted(candidates.items()):
            path = A.ROOT / name
            A.require(A.pin(path) == {k: expected[k] for k in ('sha256', 'stamp')}, 'candidate changed before unlink')
            path.unlink()
            result['removed_files'].append(name)
            result['removed_bytes'] += expected['stamp']['bytes']
        for name, expected in originals['files'].items():
            if name not in candidates:
                A.require(A.pin(A.ROOT / name) == {k: expected[k] for k in ('sha256', 'stamp')},
                          'retained metadata/control bytes changed')
        result.update(passed=True, finished_utc=A.utc(), root_free_after_bytes=shutil.disk_usage(A.ROOT).free,
                      retained_binary_files=72, retained_metadata_files=8)
    except BaseException as error:
        result.update(error=str(error), finished_utc=A.utc())
        raise
    finally:
        temporary = RECEIPT.with_suffix('.json.tmp')
        write(temporary, result)
        os.replace(temporary, RECEIPT)
    write(MARKER, dict(complete_local_checkpoints=False, archive=str(A.ARCHIVE),
                      archive_sha256=pin['sha256'], archive_receipt=str(A.RECEIPT), prune_receipt=str(RECEIPT),
                      removed_tensor_files=796, retained='all eight metadata and72 small control/token files',
                      restoration='Verify whole archive and each member against archive receipt; reconstruct the four complete trees in a fresh destination before full native inspect/restore. Current local trees are incomplete.'))
    print(json.dumps({k: result[k] for k in ('passed', 'removed_bytes', 'root_free_before_bytes', 'root_free_after_bytes')}))


if __name__ == '__main__':
    main()
