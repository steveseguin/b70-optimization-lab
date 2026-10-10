#!/usr/bin/env python3
"""CPU-only streamed authentication and complete real GGUF header reconciliation."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OWN = ROOT / 'experiments/own-xpu-runtime'
sys.path.insert(0, str(OWN / 'stage1/packet1b'))
from loaders.headers import gguf_header, gguf_shards, TYPES


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')


def signature(stat):
    return dict(device=stat.st_dev, inode=stat.st_ino, bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns, ctime_ns=stat.st_ctime_ns)


def priority():
    io = subprocess.check_output(['ionice', '-p', str(os.getpid())], text=True).strip()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19, 'run at nice 19'
    assert io == 'idle', 'run at ionice -c 3'
    assert os.environ.get('OMP_NUM_THREADS') == '2'
    return dict(nice=19, ionice=io, OMP_NUM_THREADS='2')


def source_hashes(paths):
    return {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in paths}


def differences(actual, expected):
    found = []
    aa = {t['name']: t for t in actual}
    ee = {t['name']: t for t in expected}
    for name in sorted(aa.keys() | ee.keys()):
        if name not in aa or name not in ee:
            found.append(dict(name=name, field='coverage', actual=name in aa, expected=name in ee))
            continue
        for field in ('type', 'type_id', 'dimensions', 'shape', 'data_offset', 'file_offsets', 'bytes', 'shard'):
            if aa[name][field] != ee[name][field]:
                found.append(dict(name=name, field=field, actual=aa[name][field], expected=ee[name][field]))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model_dir', type=Path)
    args = ap.parse_args()
    prio = priority()
    manifest_path = OWN / 'data/unsloth-flash-next-stage2-files.json'
    prior_path = OWN / 'stage2/packet1c/ud-census.json'
    fetch_path = OWN / 'stage2/packet1c/fetch-receipt.json'
    manifest = json.loads(manifest_path.read_text())
    prior = json.loads(prior_path.read_text())['variants']['UD-IQ3_XXS']
    fetch = {f['path']: f for f in json.loads(fetch_path.read_text())['files']}
    expected = {t['name']: t for t in prior['tensors']}
    files = [f for f in manifest['files'] if f['path'].startswith('UD-IQ3_XXS/')]
    assert len(files) == 3
    inventory = sorted(p.name for p in args.model_dir.glob('*.gguf'))
    assert inventory == sorted(Path(f['path']).name for f in files)
    receipt = dict(schema='qwen38-ud-iq3xxs.weight-admission.v1',
                   started_utc=datetime.now(timezone.utc).isoformat(),
                   host=os.uname().nodename, model_dir=str(args.model_dir),
                   repository=manifest['repo'], revision=manifest['revision'],
                   execution=prio, chunk_bytes=4*1024*1024, files=[], passed=False,
                   sources=source_hashes([Path(__file__), manifest_path, prior_path, fetch_path,
                                         OWN / 'stage1/packet1b/loaders/headers.py']))
    parsed, tensors, meta = [], [], []
    for f in files:
        path = args.model_dir / Path(f['path']).name
        start = time.monotonic()
        with path.open('rb') as stream:
            before = signature(os.fstat(stream.fileno()))
            h = hashlib.sha256()
            count = 0
            progress = 0
            while chunk := stream.read(receipt['chunk_bytes']):
                h.update(chunk)
                count += len(chunk)
                if count // (8*1024**3) > progress:
                    progress = count // (8*1024**3)
                    print(f'{path.name}: hashed {count} bytes', flush=True)
            after = signature(os.fstat(stream.fileno()))
            row = dict(path=f['path'], expected_bytes=f['bytes'], bytes=count,
                       expected_sha256=f['sha256'], sha256=h.hexdigest(),
                       before=before, after=after, elapsed_seconds=time.monotonic()-start)
            row['passed'] = (count == f['bytes'] and h.hexdigest() == f['sha256'] and before == after)
            receipt['files'].append(row)
            dump(HERE / 'admission-receipt.json', receipt)
            assert row['passed'], row
            stream.seek(0)
            p = gguf_header(stream, count)
            stream.seek(0)
            header_hash = sha(stream.read(p['header_bytes_read']))
            assert signature(os.fstat(stream.fileno())) == before
        assert signature(path.stat()) == before
        row['header_sha256'] = header_hash
        row['header_matches_range_capture'] = header_hash == fetch[f['path']]['header_sha256']
        row['header_bytes'] = p['header_bytes_read']
        row['data_start'] = p['data_start']
        assert row['header_matches_range_capture']
        parsed.append(p)
        fields = {}
        for key, value in p['metadata'].items():
            if isinstance(value, list) and len(value) > 64:
                encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
                fields[key] = dict(array_count=len(value), canonical_utf8_json_sha256=sha(encoded),
                                   first_values=value[:3], last_values=value[-3:])
            else:
                fields[key] = value
        meta.append(dict(shard=f['path'], metadata=fields, metadata_types=p['metadata_types'],
                         header_sha256=header_hash, data_start=p['data_start']))
        end = p['data_start']
        padding = p['data_start'] - p['header_bytes_read']
        for name, t in sorted(p['tensors'].items(), key=lambda x:x[1]['data_offset']):
            assert t['file_offsets'][0] == (end+31)//32*32
            padding += t['file_offsets'][0]-end
            end = t['file_offsets'][1]
            tensors.append(dict(name=name, shard=f['path'], **t))
        assert 0 <= count-end < 32
        row['padding_bytes'] = padding + count-end
        row['tensor_count'] = len(p['tensors'])
        row['tensor_bytes'] = sum(t['bytes'] for t in p['tensors'].values())
        print(f'{path.name}: SHA256/size PASS; {row["tensor_count"]} tensors', flush=True)
    gguf_shards(parsed)
    delta = differences(tensors, prior['tensors'])
    dump(HERE / 'reconciliation.json', dict(passed=not delta, differences=delta,
         tensor_count=len(tensors), fields=['coverage','type','type_id','dimensions','shape','data_offset','file_offsets','bytes','shard'],
         all_header_bytes_match_range_captures=all(f['header_matches_range_capture'] for f in receipt['files'])))
    assert not delta, 'tensor differences retained in reconciliation.json'
    # Component labels are attached only after exact descriptor reconciliation.
    components = defaultdict(lambda:dict(bytes=0,tensors=0))
    widths = defaultdict(set)
    counts = Counter()
    for t in tensors:
        for key in ('component','layer','hc_projection_replicated','official_correspondence'):
            t[key] = expected[t['name']][key]
        components[t['component']]['bytes'] += t['bytes']
        components[t['component']]['tensors'] += 1
        counts[t['type']] += 1
        widths[t['type']].add(t['shape'][-1])
    types = {kind:dict(tensors=counts[kind],bytes=sum(t['bytes'] for t in tensors if t['type']==kind),
                      elements_per_block=block,bytes_per_block=size,row_widths=sorted(widths[kind]),
                      all_rows_block_aligned=all(w%block==0 for w in widths[kind]))
             for _, (kind,block,size) in TYPES.items() if counts[kind]}
    dump(HERE / 'metadata.json', dict(array_hash_encoding='UTF-8 JSON, ensure_ascii=false, compact separators',shards=meta))
    dump(HERE / 'tensor-census.json', dict(schema='qwen38-ud-iq3xxs.real-census.v1',
         tensor_count=len(tensors), tensor_bytes=sum(t['bytes'] for t in tensors),
         components=dict(components), types=types,tensors=sorted(tensors,key=lambda t:t['name'])))
    assert inventory == sorted(p.name for p in args.model_dir.glob('*.gguf'))
    for f in receipt['files']:
        assert signature((args.model_dir/Path(f['path']).name).stat()) == f['before']
    receipt.update(passed=True, completed_utc=datetime.now(timezone.utc).isoformat(),
                   total_bytes=sum(f['bytes'] for f in receipt['files']),
                   max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   directory_inventory_stable=True)
    dump(HERE / 'admission-receipt.json', receipt)
    print(json.dumps(dict(passed=True,types=types,total_bytes=receipt['total_bytes'])),flush=True)


if __name__ == '__main__':
    main()
