#!/usr/bin/env python3
"""Read-only A367 payload audit; standard library, no runtime/device imports.

Uses the frozen tree verifier's contract and inventory/index validation, adds
SHA256 for ordinary Git files, checks packet1's independent publisher manifest,
and emits the fresh-receipt fields consumed by the calibration supervisor.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import time

REPO = Path(__file__).resolve().parents[1]
MODEL = Path('/mnt/usb-models/llm-models/Qwen3.8-Flash-Next-FP8')
HF = REPO / 'experiments/own-xpu-runtime/stage2/packet1/metadata/hf-model-info.json'
HF_SHA = 'bc69301a1f528f69711ecebbd2d0187fef34d6df37e77b441cf7d0d24c74cb09'
VERIFIER = REPO / 'scripts/verify-qwen38-flash-next-fp8-tree.py'
VERIFIER_SHA = 'a1c797b6922fa58e762aea7ac61b0cf191c21252ebeec7689b2c2788921afdaa'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_hashes(path):
    before = path.stat()
    sha = hashlib.sha256()
    blob = hashlib.sha1(f'blob {before.st_size}\0'.encode())
    count = 0
    with path.open('rb', buffering=0) as stream:
        while chunk := stream.read(16 * 1024 * 1024):
            sha.update(chunk)
            # LFS files need no Git blob digest; avoid doubling bulk hash work.
            if not path.name.endswith('.safetensors'):
                blob.update(chunk)
            count += len(chunk)
    after = path.stat()
    stable = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
              before.st_ctime_ns) == (after.st_dev, after.st_ino, after.st_size,
                                     after.st_mtime_ns, after.st_ctime_ns)
    return sha.hexdigest(), blob.hexdigest(), count, stable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    output = args.receipt.resolve()
    if not output.is_relative_to(REPO) or output.exists():
        parser.error('use a new receipt path inside the lab repository')
    initial_free = shutil.disk_usage('/').free

    def disk_guard():
        free = shutil.disk_usage('/').free
        if free < 14_000_000_000 or initial_free - free > 6_000_000_000:
            raise RuntimeError('root disk floor/growth guard')

    disk_guard()
    started = time.time()
    result = dict(schema='flash-next.a367.launch-payload.v1', passed=False,
                  all_files_sha256_verified=False, model_root=str(MODEL),
                  host=socket.gethostname(), started_unix=started,
                  verifier_sha256=digest(VERIFIER), producer_sha256=digest(Path(__file__)),
                  files=[], mismatches=[])
    try:
        assert digest(VERIFIER) == VERIFIER_SHA, 'shared verifier changed; review required'
        spec = importlib.util.spec_from_file_location('a367_tree_verifier', VERIFIER)
        v = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = v
        spec.loader.exec_module(v)
        result.update(revision=v.PINNED.revision, contract=asdict(v.PINNED))
        assert MODEL.resolve() == MODEL, 'launch path unexpectedly redirected'
        tree, expected = v.load_tree_metadata(MODEL, v.PINNED)
        assert digest(HF) == HF_SHA, 'packet1 publisher manifest changed'
        hf = json.loads(HF.read_text())
        assert hf['sha'] == v.PINNED.revision
        independent = {f['rfilename']: dict(size=f['size'], blob_id=f['blobId'],
                         lfs_sha256=f.get('lfs', {}).get('sha256')) for f in hf['siblings']}
        assert expected == independent, 'record tree and packet1 manifest disagree'
        result['manifest'] = dict(path=str(tree), sha256=digest(tree),
                                  packet1_path=str(HF.relative_to(REPO)), packet1_sha256=HF_SHA)
        actual = v.actual_root_files(MODEL)
        result['missing'] = sorted(set(expected) - actual)
        result['extra'] = sorted(actual - set(expected))
        initial_stats = {n: (MODEL / n).stat() for n in actual}
        for number, name in enumerate(sorted(actual), 1):
            disk_guard()
            sha, blob, size, stable = file_hashes(MODEL / name)
            declared = expected.get(name)
            kind = 'lfs_sha256' if declared and declared['lfs_sha256'] else 'git_blob_sha1'
            observed = sha if kind == 'lfs_sha256' else blob
            wanted = (declared['lfs_sha256'] or declared['blob_id']) if declared else None
            ok = bool(declared and size == declared['size'] and stable and observed == wanted)
            row = dict(path=name, size=size, sha256=sha, digest_kind=kind,
                       digest=observed, expected_digest=wanted, stable=stable, passed=ok)
            result['files'].append(row)
            if not ok:
                result['mismatches'].append(name)
            print(f'{number}/{len(actual)} {name}: {"MATCH" if ok else "DIFFERS"}', flush=True)
        # Detect changes to an earlier file during the complete pass, too.
        for name, before in initial_stats.items():
            after = (MODEL / name).stat()
            assert (before.st_size, before.st_mtime_ns, before.st_ctime_ns, before.st_ino) == (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns, after.st_ino), name + ' changed during audit'
        assert v.actual_root_files(MODEL) == actual, 'inventory changed during audit'
        index, shards = v.validate_index(MODEL, expected, v.PINNED)
        total = sum(f['size'] for f in result['files'])
        result['observed'] = dict(root_file_count=len(actual), root_total_bytes=total,
                                  indexed_shard_count=len(shards), indexed_tensor_count=len(index['weight_map']))
        result['passed'] = not (result['missing'] or result['extra'] or result['mismatches']) and total == v.PINNED.root_total_bytes
        result['all_files_sha256_verified'] = result['passed']
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
    result.update(verified_unix=time.time(), completed_utc=datetime.now(timezone.utc).isoformat(),
                  elapsed_seconds=time.time() - started, root_free_bytes=shutil.disk_usage('/').free,
                  scope='144 publisher root artifacts; .cache bookkeeping excluded as in frozen verifier; no model writes')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({k: result[k] for k in ('passed', 'mismatches', 'elapsed_seconds')}), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
