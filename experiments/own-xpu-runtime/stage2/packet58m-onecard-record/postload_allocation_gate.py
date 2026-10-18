#!/usr/bin/env python3
"""Execute the actual engine post-load setup using only its CPU mock backend."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

P = Path(__file__).resolve().parent
ROOT = P.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    binary = P / 'build/gnu-host/own-rt-iq3'
    sources = dict(json.loads((P / 'parent-build-gnu-host-receipt.json').read_text())['sources_sha256'])
    for path in (Path(__file__), P / 'selection.json', P / 'dispatch-speed6.json',
                 P.parent / 'suite-inputs-20261012/incident-retrospective/plan.tsv'):
        sources[str(path.relative_to(ROOT))] = sha(path)
    assert all(sha(ROOT / name) == digest for name, digest in sources.items())
    binary_hash = sha(binary)
    with tempfile.TemporaryDirectory(prefix='postload-', dir=P / 'build') as temporary:
        output = Path(temporary) / 'run'
        command = [str(binary), '--postload-allocation-test', str(output)]
        run = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                             text=True, timeout=60, env={'PATH': '/usr/bin:/bin', 'OMP_NUM_THREADS': '2'})
        (P / 'evidence/postload-allocation-cpu.log').write_text(run.stdout + run.stderr)
        if run.returncode:
            raise RuntimeError(run.stdout + run.stderr)
        row = json.loads((output / 'result.json').read_text())
        assert row['passed'] and not row['device_executed'] and not row['model_reads']
        assert row['postload_allocations'] == 3 and row['negative_cases'] == 2
        row.update(schema='packet58d.postload-allocation-cpu.v1', binary_sha256=binary_hash,
                   sources=sources, configuration=dict(card=0, context=4096, kv='BF16',
                   decode='plain', miss_path='zero-copy', cache_bytes=18_000_000_000),
                   method='Real Engine::initialize_cache and Arena::allocate; metadata-only loaded-bank fixture; bounded mock backing')
        for leaf in ('census.json', 'teardown.json'):
            path = P / 'evidence' / ('postload-' + leaf)
            path.write_bytes((output / leaf).read_bytes())
            row['sources'][str(path.relative_to(ROOT))] = sha(path)
    assert sha(binary) == binary_hash
    assert all(sha(ROOT / name) == digest for name, digest in sources.items())
    (P / 'evidence/postload-allocation-cpu.json').write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps({k: row[k] for k in ('passed', 'device_executed', 'postload_allocations', 'negative_cases', 'backing_bytes')}))


if __name__ == '__main__':
    main()
