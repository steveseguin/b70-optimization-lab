#!/usr/bin/env python3
"""Replay the analysis with original receipt paths unavailable, without moving them."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
from unittest.mock import patch

P = Path(__file__).resolve().parent
REPO = P.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    pins = json.loads((P / 'analysis-inputs.json').read_text())
    originals = {REPO / name for name in pins}
    original_hashes = {path: digest(path) for path in originals if path.exists()}
    outputs = ('analysis-data.json', 'analysis-inputs.json', 'position-pairs.jsonl.gz')
    before = {name: digest(P / name) for name in outputs}
    exists = Path.exists
    with patch.object(Path, 'exists', lambda path: False if path in originals else exists(path)):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            runpy.run_path(str(P / 'analyze.py'), run_name='__main__')
    result = json.loads(stdout.getvalue())
    assert result['passed'] and result['joined_positions'] == 2386
    assert {name: digest(P / name) for name in outputs} == before
    assert {path: digest(path) for path in original_hashes} == original_hashes
    provenance = json.loads((P / 'tool-provenance.json').read_text())
    assert digest(P / provenance['copy']) == provenance['sha256']
    assert digest(REPO / provenance['source']) == provenance['sha256']
    validation = dict(passed=True, archive_only_replay=True,
        input_paths=len(pins), original_paths_hash_verified_unchanged=len(original_hashes),
        original_analyzer_copy_exact=True, output_sha256=before,
        same_outputs_after_archive_replay=True, joined_positions=2386,
        metric_positions_per_arm=1188, device_executed=False)
    (P / 'validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()
