#!/usr/bin/env python3
"""Small original-byte snapshot of prior decisions, separate from current inputs."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import shutil
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage(ROOT).free >= 25_000_000_000
    archive_path = HERE / 'prior-inputs.tar.gz'
    paths = [HERE.parent/'packet85-critical-path/MODEL.md',
             HERE.parent/'packet85-critical-path/model.json',
             HERE.parent/'packet124-record-bundle/p105_common.hpp']
    paths += [HERE.parent/'screen/v4-lanes/evidence'/(
        'p106b-13e3630d590c-B-grid-'+suffix)/'summary.json' for suffix in (
            '0-production', '1-head-split', '2-head-split+draft-split', '3-production')]
    if args.check:
        with tarfile.open(archive_path, 'r:gz') as archive:
            data = {str(p.relative_to(ROOT)): archive.extractfile(str(p.relative_to(ROOT))).read() for p in paths}
    else:
        assert not archive_path.exists(), 'original-byte snapshot is immutable'
        data = {str(p.relative_to(ROOT)): p.read_bytes() for p in paths}
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for name, raw in sorted(data.items()):
                assert (ROOT/name).read_bytes() == raw
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(raw), 0o644
                archive.addfile(info, io.BytesIO(raw))
        packed = gzip.compress(stream.getvalue(), mtime=0)
        with tarfile.open(fileobj=io.BytesIO(packed), mode='r:gz') as archive:
            for name, raw in data.items():
                assert archive.extractfile(name).read() == raw
        archive_path.write_bytes(packed)
    rates = []
    for p in paths[3:]:
        d = json.loads(data[str(p.relative_to(ROOT))])
        rates.append({'source': str(p.relative_to(ROOT)), 'passed': d['passed'],
                      'class_balanced_tok_s': d['class_balanced_tok_s_1_100_intervals_after_ttft']['median']})
    controls = max(rates[0]['class_balanced_tok_s'], rates[3]['class_balanced_tok_s'])
    result = {'schema': 'own-runtime.packet126.prior-evidence.v1', 'device_executed': False,
              'files': {n: {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)} for n, b in sorted(data.items())},
              'p106b': {'runs': rates,
                        'combined_vs_stronger_control_percent': 100*(rates[2]['class_balanced_tok_s']/controls-1),
                        'combined_vs_head_only_percent': 100*(rates[2]['class_balanced_tok_s']/rates[1]['class_balanced_tok_s']-1)},
              'distinctions': {
                  'p79': 'Draft stays on rank1; no reverse-hidden transport or rank0 draft cost.',
                  'p106': 'No draft row split or remote draft suffix; fixed 80128 prefix unchanged.',
                  'depth2': 'No recursive draft hidden feedback or M2 target tile; one next-draft transaction only.',
                  'p36': 'Explicitly revisits the guessed-embedding state hazard only in a future transaction-gated implementation.',
                  'p123': 'The same split-head timing gap prevents a supported gain; B-A is not a measured wait.'}}
    encoded = (json.dumps(result, indent=2, sort_keys=True)+'\n').encode()
    if args.check:
        assert (HERE/'prior-results.json').read_bytes() == encoded
    else:
        (HERE/'prior-results.json').write_bytes(encoded)
    print(json.dumps({'passed': True, 'p106b': result['p106b'], 'archive_bytes': archive_path.stat().st_size}, indent=2))


if __name__ == '__main__':
    main()
