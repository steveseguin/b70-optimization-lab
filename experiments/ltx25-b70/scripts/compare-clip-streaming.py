#!/usr/bin/env python3
"""Inactive F32 exact-output comparator with bounded tensor reads, no Torch.

The frozen compare-clip.py and its callers remain unchanged. Graph changes
still require separate review. Offline evidence mode can never emit 'passed'.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct

from continuation_delivery import _open_regular, _read_exact, _unchanged, _json
from finite_f32_bits import first_nonfinite_f32
from f32_difference import finite_units, rounded_abs_difference

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
KEYS = {'images', 'video_latent', 'audio_latent', 'waveform'}
READ_BYTES = 65536
MAX_JSON_BYTES = 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def raw_sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    with _open_regular(path) as (stream, identity):
        require(0 < identity['size'] <= MAX_JSON_BYTES, 'JSON metadata exceeds bounded size')
        raw = _read_exact(stream, identity['size'])
        _unchanged(stream, identity)
    result = _json(raw)
    require(isinstance(result, dict), 'JSON metadata must be an object')
    return result, raw_sha(raw)


def header(stream, identity):
    size = struct.unpack('<Q', _read_exact(stream, 8))[0]
    require(2 <= size <= MAX_JSON_BYTES and size + 8 <= identity['size'], 'invalid bounded header size')
    raw = _read_exact(stream, size)
    require(raw.startswith(b'{'), 'safetensors header must begin with an object')
    value = _json(raw)
    require(isinstance(value, dict) and set(value) - {'__metadata__'} == KEYS,
            'capture must contain exactly the four expected tensors')
    if '__metadata__' in value:
        require(isinstance(value['__metadata__'], dict)
                and all(isinstance(x, str) for x in value['__metadata__'].values()),
                'safetensors metadata must map strings to strings')
    tensors = {}
    for name in sorted(KEYS):
        desc = value[name]
        require(isinstance(desc, dict) and set(desc) == {'dtype', 'shape', 'data_offsets'},
                f'{name}: invalid descriptor')
        require(desc['dtype'] == 'F32', f'{name}: this candidate supports captured F32 tensors only')
        shape, offsets = desc['shape'], desc['data_offsets']
        require(isinstance(shape, list) and len(shape) <= 16
                and all(type(x) is int and 0 <= x < 2**63 for x in shape), f'{name}: invalid shape')
        require(isinstance(offsets, list) and len(offsets) == 2
                and all(type(x) is int for x in offsets), f'{name}: invalid offsets')
        start, end = offsets
        require(0 <= start < end <= identity['size'] - size - 8, f'{name}: invalid/nonempty range')
        require(end - start == math.prod(shape) * 4, f'{name}: shape/range mismatch')
        tensors[name] = {'dtype': 'F32', 'shape': shape, 'offset': size + 8 + start, 'length': end - start}
    position = size + 8
    for desc in sorted(tensors.values(), key=lambda x: x['offset']):
        require(desc['offset'] == position, 'overlapping or unindexed tensor data')
        position += desc['length']
    require(position == identity['size'], 'unindexed trailing data')
    return tensors, raw_sha(raw)


def verify_archive(path, metadata):
    require(metadata['deterministic_enabled'] is True and metadata['deterministic_warn_only'] is False,
            'strict deterministic capture settings required')
    require(set(metadata['tensors']) == KEYS, 'summary requires four tensors')
    with _open_regular(path) as (stream, identity):
        descriptors, header_sha = header(stream, identity)
        for name, desc in descriptors.items():
            expected = metadata['tensors'][name]
            require(expected['dtype'] == 'torch.float32' and expected['shape'] == desc['shape'],
                    f'{name}: summary layout differs from archive')
            require(all(type(x) is int for x in expected['shape']), 'noninteger summary dimensions')
            require(expected['finite'] is True, f'{name}: summary reports nonfinite samples')
            stream.seek(desc['offset'])
            remaining = desc['length']
            digest = hashlib.sha256()
            while remaining:
                block = _read_exact(stream, min(READ_BYTES, remaining))
                require(first_nonfinite_f32(block) is None, f'{name}: nonfinite samples')
                digest.update(block)
                remaining -= len(block)
            require(digest.hexdigest() == expected['sha256'], f'{name}: summary hash mismatch')
            desc['sha256'] = digest.hexdigest()
            _unchanged(stream, identity)
    return {'path': str(path), 'file_identity': identity, 'header_sha256': header_sha, 'tensors': descriptors}


def execution(root, name):
    require(isinstance(name, str) and re.fullmatch(r'[a-z0-9_-]+', name), 'simple lowercase run name required')
    folder = root / 'output/validation' / name
    metadata, metadata_sha = read_json(folder / 'summary.json')
    archive = verify_archive(folder / 'tensors.safetensors', metadata)
    request = root / 'requests' / name
    records, hashes = {}, {'capture_summary.json': metadata_sha}
    for filename in ('history', 'submission', 'result', 'prompt', 'identity'):
        records[filename], hashes[filename + '.json'] = read_json(request / (filename + '.json'))
    history, submission, result, prompt = (records[key] for key in ('history', 'submission', 'result', 'prompt'))
    require(history['prompt'][1] == submission['prompt_id'] == result['prompt_id'], 'execution IDs disagree')
    require(history['prompt'][2] == prompt, 'saved graph differs from history')
    require(history['status']['status_str'] == 'success', 'execution did not succeed')
    require(not any(message[1].get('nodes') for message in history['status']['messages']
                    if message[0] == 'execution_cached'), 'cached execution nodes are forbidden')
    identity = {'name': name, 'prompt_id': submission['prompt_id'],
                'prompt_sha256': hashes['prompt.json'], 'server_identity': records['identity'],
                'sample_rate': metadata['sample_rate'], 'client_seconds': result['seconds'],
                'evidence_sha256': hashes}
    return identity, archive


def compare_archives(reference, candidate):
    comparisons = {}
    with _open_regular(reference['path']) as (a, aid), _open_regular(candidate['path']) as (b, bid):
        for stream, identity, receipt in ((a, aid, reference), (b, bid, candidate)):
            require(identity == receipt['file_identity'], 'archive changed after verification')
            descriptors, header_sha = header(stream, identity)
            require(header_sha == receipt['header_sha256'], 'archive header changed')
            require(descriptors == {name: {key: value for key, value in item.items() if key != 'sha256'}
                                    for name, item in receipt['tensors'].items()}, 'verified ranges changed')
        for name in sorted(KEYS):
            left, right = reference['tensors'][name], candidate['tensors'][name]
            layout = left['dtype'] == right['dtype'] and left['shape'] == right['shape']
            row = {'bitwise_equal': False, 'same_layout': layout}
            comparisons[name] = row
            if not layout:
                continue
            a.seek(left['offset'])
            b.seek(right['offset'])
            remaining, sample_offset = left['length'], 0
            unequal_bits = unequal_values = maximum_delta = 0
            first_unequal = None
            adigest, bdigest = hashlib.sha256(), hashlib.sha256()
            while remaining:
                size = min(READ_BYTES, remaining)
                ablock, bblock = _read_exact(a, size), _read_exact(b, size)
                adigest.update(ablock)
                bdigest.update(bblock)
                if ablock != bblock:
                    for index, ((aword,), (bword,)) in enumerate(zip(struct.iter_unpack('<I', ablock),
                                                                   struct.iter_unpack('<I', bblock))):
                        if aword == bword:
                            continue
                        unequal_bits += 1
                        if first_unequal is None:
                            first_unequal = sample_offset + index
                        if (aword & 0x7fffffff) == 0 and (bword & 0x7fffffff) == 0:
                            continue  # Signed zero is byte-unequal but numerically equal.
                        unequal_values += 1
                        delta = abs(finite_units(aword) - finite_units(bword))
                        maximum_delta = max(maximum_delta, delta)
                remaining -= size
                sample_offset += size // 4
            require(adigest.hexdigest() == left['sha256'] and bdigest.hexdigest() == right['sha256'],
                    'archive content changed during comparison')
            row.update({'bitwise_equal': unequal_bits == 0, 'unequal_values': unequal_values,
                        'unequal_f32_bit_patterns': unequal_bits, 'first_unequal_sample': first_unequal,
                        **rounded_abs_difference(maximum_delta)})
        _unchanged(a, aid)
        _unchanged(b, bid)
    return comparisons


def compare_runs(root, reference, candidate, *, offline_evidence=False):
    root = Path(root)
    require(offline_evidence or not (root / 'FAULT.json').exists(), 'fault recorded; gate is halted')
    executions, archives = [], []
    for name in (reference, candidate):
        identity, archive = execution(root, name)
        executions.append(identity)
        archives.append(archive)
    require(executions[0]['prompt_id'] != executions[1]['prompt_id'], 'distinct executions required')
    require(executions[0]['sample_rate'] == executions[1]['sample_rate'], 'sample rates differ')
    require(executions[0]['server_identity']['model_verification_sha256'] ==
            executions[1]['server_identity']['model_verification_sha256'], 'model verification identities differ')
    comparisons = compare_archives(*archives)
    equal = all(row['bitwise_equal'] for row in comparisons.values())
    fault_present = (root / 'FAULT.json').exists()
    require(offline_evidence or not fault_present, 'fault recorded during comparison; gate is halted')
    return {'status': ('passed-offline-evidence' if equal else 'failed-offline-evidence') if offline_evidence
                      else ('passed' if equal else 'failed'),
            'scope': 'exact output comparison; graph changes are intentional and must be reviewed separately',
            'schema': 'ltx25.streaming-exact-comparison.v1', 'executions': executions, 'comparisons': comparisons,
            'offline_evidence_only': offline_evidence, 'eligible_for_live_gate': not offline_evidence and equal,
            'fault_present': fault_present,
            'diagnostics_definition': 'finite IEEE754 F32 values; exact integer difference rounded once to F32 nearest-even; signed zeros numerically equal',
            'diagnostics_native_torch_mode_qualified': False,
            'tensor_read_bound_bytes': READ_BYTES, 'max_json_file_bytes': MAX_JSON_BYTES,
            'restrictions': ['F32, nonempty tensors, rank at most16',
                             'JSON duplicate keys and NaN/Infinity constants rejected, including diagnostic metadata',
                             'summary layout and finite flags checked as well as actual bytes',
                             'strict settings must be JSON booleans', 'opened file/header/range changes rejected']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference')
    parser.add_argument('candidate')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offline-evidence', action='store_true',
                        help='read historical files only; report cannot satisfy a live gate')
    args = parser.parse_args()
    require(not args.output.exists(), 'output report already exists')
    report = compare_runs(ROOT, args.reference, args.candidate, offline_evidence=args.offline_evidence)
    # Preserve legacy Infinity diagnostics on F32 overflow; exact hex bits also
    # identify that result unambiguously. No nonfinite input may pass validation.
    with args.output.open('x') as output:
        output.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'comparisons': report['comparisons']}, indent=2))
    raise SystemExit(0 if all(row['bitwise_equal'] for row in report['comparisons'].values()) else 1)


if __name__ == '__main__':
    main()
