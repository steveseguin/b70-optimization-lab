#!/usr/bin/env python3
"""Offline, bounded, read-only official checkpoint admission. Original lab code."""
import argparse
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
P1 = HERE.parent / 'packet1'
sys.path.insert(0, str(HERE.parent / 'packet1b'))
from loaders.headers import safetensors_header, validate_contract


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def guards():
    io = subprocess.check_output(['ionice', '-p', str(os.getpid())], text=True).strip()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2' or io != 'idle':
        raise RuntimeError('requires nice 19, ionice -c 3, OMP_NUM_THREADS=2')
    return {'nice': 19, 'ionice': io, 'OMP_NUM_THREADS': '2'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model', type=Path)
    args = ap.parse_args()
    settings = guards()
    started = utc()
    model = args.model.resolve(strict=True)
    contract = json.loads((P1 / 'tensor-contract.json').read_text())
    hf_path = P1 / 'metadata/hf-model-info.json'
    hf = json.loads(hf_path.read_text())
    manifest_path = REPO / 'repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/model-direct.json'
    manifest = json.loads(manifest_path.read_text())
    assert hf['sha'] == manifest['revision'] == contract['revision']
    expected = {x['rfilename']: x for x in hf['siblings']}
    for item in manifest['lfs_files']:
        h = expected[item['path']]
        assert (h['size'], h['lfs']['sha256']) == (item['bytes'], item['sha256'])
    for item in manifest['small_files']:
        h = expected[item['path']]
        assert (h['size'], h['blobId']) == (item['bytes'], item['git_blob'])
    files = sorted(p for p in model.rglob('*') if p.is_file())
    assert all(p.resolve().is_relative_to(model) for p in files)
    before = {str(p.relative_to(model)): (p.stat().st_size, p.stat().st_mtime_ns) for p in files}
    rows, differences = [], []
    for p in files:
        rel = str(p.relative_to(model))
        start = time.monotonic()
        n, mtime = before[rel]
        s256 = hashlib.sha256()
        blob = hashlib.sha1(f'blob {n}\0'.encode())
        count = 0
        # Two live chunks at most; no mmap, full-file buffer or cache controls.
        with p.open('rb') as stream:
            while chunk := stream.read(4 * 1024 * 1024):
                count += len(chunk)
                s256.update(chunk)
                blob.update(chunk)
        entry = expected.get(rel)
        stable = (p.stat().st_size, p.stat().st_mtime_ns) == (n, mtime)
        ok = stable and count == n
        if entry:
            ok = ok and count == entry['size']
            ok = ok and (s256.hexdigest() == entry['lfs']['sha256'] if 'lfs' in entry else blob.hexdigest() == entry['blobId'])
        row = {'path': rel, 'bytes': count, 'sha256': s256.hexdigest(),
               'git_blob_sha1': blob.hexdigest(), 'seconds': time.monotonic()-start,
               'mtime_ns': mtime, 'unchanged_during_read': stable,
               'kind': ('lfs' if 'lfs' in entry else 'publisher_small') if entry else 'local_cache_metadata',
               'expected': entry, 'passed': ok}
        rows.append(row)
        if not ok:
            differences.append({'file': rel, 'problem': 'hash/size/stability mismatch'})
        if entry:
            print(f'{rel}: {count} bytes {row["seconds"]:.3f}s {"PASS" if ok else "FAIL"}', flush=True)
    missing = sorted(set(expected)-set(before))
    differences.extend({'file': p, 'problem': 'missing'} for p in missing)
    parsed_rows, shards, seen = [], [], set()
    for shard in contract['shards']:
        name = shard['file']
        path = model / name
        with path.open('rb') as stream:
            parsed = safetensors_header(stream, path.stat().st_size)
        try:
            validate_contract(parsed, name, contract)
            verdict = 'PASS'
        except ValueError as error:
            verdict = str(error)
            differences.append({'shard': name, 'problem': verdict})
        shards.append({'shard': name, 'tensor_count': len(parsed['tensors']),
                       'header_and_prefix_bytes': parsed['header_and_prefix_bytes'],
                       'file_bytes': parsed['file_bytes'], 'contract_verdict': verdict})
        for tensor_name, t in sorted(parsed['tensors'].items()):
            if tensor_name in seen:
                differences.append({'tensor': tensor_name, 'problem': 'duplicate'})
            seen.add(tensor_name)
            parsed_rows.append(dict(t, name=tensor_name, shard=name))
    actual = {t['name']: t for t in parsed_rows}
    bound = {t['name']: t for t in contract['tensors']}
    for n in sorted(set(actual) | set(bound)):
        if n not in actual or n not in bound:
            differences.append({'tensor': n, 'problem': 'missing/unexpected'})
        else:
            for field in ['shard','dtype','shape','data_offsets','file_offsets','bytes']:
                if actual[n][field] != bound[n][field]:
                    differences.append({'tensor': n, 'field': field, 'actual': actual[n][field], 'expected': bound[n][field]})
    # Copy classifications only after the independently parsed records match.
    if not differences:
        for t in parsed_rows:
            for key in ['component','residency_class','format','exclusion_matches']:
                t[key] = bound[t['name']][key]
    totals = {}
    for key in ['dtype', 'component', 'residency_class']:
        acc = collections.Counter()
        for t in parsed_rows:
            acc[t.get(key, 'unclassified')] += t['bytes']
        totals[key] = dict(acc)
    write('tensor-census.json', {'tensors': parsed_rows, 'shards': shards, 'totals_bytes': totals,
                               'differences': differences, 'passed': not differences})
    end_files = sorted(p for p in model.rglob('*') if p.is_file())
    after = {str(p.relative_to(model)): (p.stat().st_size, p.stat().st_mtime_ns) for p in end_files}
    if after != before:
        differences.append({'problem': 'directory size/mtime inventory changed'})
    sources = [Path(__file__), P1/'tensor-contract.json', P1/'identity.json', hf_path,
               manifest_path, HERE.parent/'packet1b/loaders/headers.py']
    receipt = {'schema': 'own-xpu-runtime.packet2.admission.v1', 'started_utc': started,
               'finished_utc': utc(), 'hostname': os.uname().nodename, 'model': str(model),
               'repository': manifest['repository'], 'revision': manifest['revision'],
               'argv': sys.argv, 'settings': settings, 'read_chunk_bytes': 4*1024*1024,
               'sources': {str(p.relative_to(REPO)): sha(p) for p in sources},
               'files': rows, 'file_count': len(rows), 'bytes': sum(r['bytes'] for r in rows),
               'kind_counts': dict(collections.Counter(r['kind'] for r in rows)),
               'missing': missing, 'differences': differences, 'passed': not differences,
               'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               'census_sha256': sha(HERE/'tensor-census.json')}
    write('admission-receipt.json', receipt)
    print(json.dumps({k: receipt[k] for k in ['file_count','bytes','kind_counts','passed','max_rss_kib']}))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
