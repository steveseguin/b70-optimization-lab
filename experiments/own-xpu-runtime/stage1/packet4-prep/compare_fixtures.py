#!/usr/bin/env python3
"""Authenticate raw fixtures, execute the frozen CPU references, retain differences."""
import argparse
import json
import math
import os
from pathlib import Path

import jsonschema
import numpy as np
import torch

from common import (DTYPES, decode_tree, evaluate, file_hash, flatten, json_bytes,
                    load_ref, load_tensor, contained, token_hash)
from extract_fixtures import schema


def difference(expected, actual):
    """Bit comparison includes signed zero and NaN payloads. ULP uses ordered bits.

    NaN/Inf unequal pairs have no finite absolute/ULP distance, reported null.
    Integer tensors use exact bytes plus absolute integer distance, no ULP.
    """
    if expected.shape != actual.shape or expected.dtype != actual.dtype:
        return {'bit_exact': False, 'reason': 'shape/dtype mismatch',
                'expected_shape': list(expected.shape), 'actual_shape': list(actual.shape),
                'expected_dtype': str(expected.dtype), 'actual_dtype': str(actual.dtype),
                'max_abs': None, 'max_ulp': None}
    a = expected.detach().contiguous().reshape(-1)
    b = actual.detach().contiguous().reshape(-1)
    size = a.element_size()
    ab = a.view(torch.uint8).numpy().reshape(-1, size)
    bb = b.view(torch.uint8).numpy().reshape(-1, size)
    unequal = np.any(ab != bb, axis=1)
    count = int(unequal.sum())
    out = {'bit_exact': count == 0, 'different_elements': count,
           'elements': a.numel(), 'max_abs': 0, 'max_ulp': 0,
           'first_different_flat_index': int(np.flatnonzero(unequal)[0]) if count else None}
    if count == 0:
        return out
    if not a.is_floating_point():
        # Python ints avoid overflow for I64 subtraction.
        out.update(max_abs=max(abs(int(x)-int(y)) for x, y in zip(a.tolist(), b.tolist())), max_ulp=None)
        return out
    af, bf = a.double().numpy(), b.double().numpy()
    finite = np.isfinite(af) & np.isfinite(bf)
    out['nonfinite_differences'] = int((unequal & ~finite).sum())
    out['max_abs'] = float(np.max(np.abs(af[finite]-bf[finite]))) if finite.any() else None
    if out['nonfinite_differences']:
        out['max_ulp'] = None
    else:
        # F8/F16/BF16/F32 IEEE-like sign ordering, monotonic through signed zero.
        uint = {1: np.uint8, 2: np.uint16, 4: np.uint32}[size]
        bits_a = ab.reshape(-1).view(uint).astype(np.int64)
        bits_b = bb.reshape(-1).view(uint).astype(np.int64)
        sign = 1 << (size * 8 - 1)
        mask = (1 << (size * 8)) - 1
        order = lambda v: np.where((v & sign) != 0, mask - v, v + sign)
        out['max_ulp'] = int(np.max(np.abs(order(bits_a) - order(bits_b))))
    return out


def compare(root, max_bytes=512 * 1024**2):
    root = Path(root)
    run = json.loads((root / 'extraction-result.json').read_text())
    if run['status'] != 'extracted-unverified' or run.get('single_prompt_oracle_equal') is not True or run.get('cached_tokens') != 0:
        raise ValueError('rejected/non-neutral extraction')
    oracle = json.loads((root / 'oracle.json').read_text())
    selected = next(r for r in oracle['rows'] if r['prompt_id'] == run['prompt_id'])
    if run['token_ids'] != selected['token_ids'] or token_hash(run['token_ids']) != selected['sha256'] or run['actual_token_sha256'] != selected['sha256']:
        raise ValueError('neutrality token arrays/hashes disagree')
    identity_path = contained(root, run['run_identity']['path'])
    if file_hash(identity_path) != run['run_identity']['sha256']:
        raise ValueError('run identity hash mismatch')
    identity = json.loads(identity_path.read_text())
    records, total = [], 0
    seen = set()
    checked = set()
    def verify_artifacts(value):
        if isinstance(value, dict):
            if set(value) == {'path', 'sha256'}:
                path = contained(root, value['path'])
                key = (str(path), value['sha256'])
                if key not in checked:
                    if file_hash(path) != value['sha256']:
                        raise ValueError('provenance/tensor artifact hash mismatch')
                    checked.add(key)
            else:
                for item in value.values():verify_artifacts(item)
        elif isinstance(value, list):
            for item in value:verify_artifacts(item)
    for entry in run['fixtures']:
        path = contained(root, entry['path'])
        if str(path) in seen or file_hash(path) != entry['sha256']:
            raise ValueError('duplicate/changed fixture envelope')
        seen.add(str(path))
        f = json.loads(path.read_text())
        jsonschema.validate(f, schema())
        verify_artifacts(f)
        d = f['diagnostic']
        if d['mock'] != run['mock'] or f['comparator'] != identity['comparator']:
            raise ValueError('mixed fixture identity')
        if file_hash(load_ref(d['model_key']).__file__) != d['reference_sha256']:
            raise ValueError('CPU reference changed; freeze a new receipt')
        groups = {}
        for group in ('inputs', 'outputs', 'state_before', 'state_after'):
            names = [v['name'] for v in f[group]]
            if len(names) != len(set(names)):
                raise ValueError('duplicate tensor names')
            groups[group] = {}
            for t in f[group]:
                total += t['nbytes']
                if total > max_bytes:
                    raise ValueError('comparison byte cap exceeded')
                groups[group][t['name']] = load_tensor(root, t, max_bytes)
        rec = {'fixture_id': f['fixture_id'], 'operator': f['operator'], 'rows': d['rows'],
               'rank': d['rank'], 'comparisons': {}, 'status': 'UNTESTED'}
        call = d['reference_call']
        if call is None:
            rec['reason'] = 'native boundary has no normalized CPU reference binding'
        else:
            try:
                args = decode_tree(call['args'], groups['inputs'], d['model_key'])
                kwargs = decode_tree(call['kwargs'], groups['inputs'], d['model_key'])
                # Raw mappings are private (copy-on-write), so replay cannot
                # alter the recorded files even if a future reference mutates.
                result = flatten(evaluate(d['model_key'], call['function'], args, kwargs))
                expected = d['expected']
                for name, dest in expected.items():
                    group, tensor_name = dest.split(':', 1)
                    if group not in ('outputs', 'state_after'):
                        raise ValueError('expected must bind output or state_after')
                    rec['comparisons'][name] = difference(result[name], groups[group][tensor_name])
                covered = set(expected.values())
                required = {f'{g}:{name}' for g in ('outputs', 'state_after') for name in groups[g]}
                rec['uncompared'] = sorted(required - covered)
                if not expected or rec['uncompared']:
                    rec['reason'] = 'some recorded outputs/states lack a CPU mapping'
                elif all(v['bit_exact'] for v in rec['comparisons'].values()):
                    rec['status'] = 'VERIFIED-EXACT'
                else:
                    rec['status'] = 'VERIFIED-DIFF'
                # Never hide an observed difference behind incomplete coverage.
                if any(not v['bit_exact'] for v in rec['comparisons'].values()):
                    rec['status'] = 'VERIFIED-DIFF'
            except (NotImplementedError, ValueError, KeyError, RuntimeError) as e:
                rec['reason'] = f'CPU mapping refused: {type(e).__name__}: {e}'
        records.append(rec)
    census = {}
    for u in (f'U{i}' for i in range(1, 8)):
        selected_records = [r for r in records if u in r['operator']['census_items']]
        statuses = {r['status'] for r in selected_records}
        status = ('VERIFIED-DIFF' if 'VERIFIED-DIFF' in statuses else
                  'VERIFIED-EXACT' if statuses == {'VERIFIED-EXACT'} else 'UNTESTED')
        census[u] = {'status': status, 'scope': 'recorded operator samples only',
                     'qualification': 'UNTESTED', 'fixtures': len(selected_records),
                     'observed_M': sorted({r['operator']['M'] for r in selected_records}),
                     'missing_M': sorted({1, 2, 6} - {r['operator']['M'] for r in selected_records}),
                     'differences': [r['fixture_id'] for r in selected_records if r['status'] == 'VERIFIED-DIFF']}
    return {'schema': 'own-xpu-runtime.packet4.cpu-comparison.v1', 'mock': run['mock'],
            'scope': 'single-prompt diagnostic; exact samples do not close a U-row',
            'promotion_eligible': False, 'census': census, 'operators': records,
            'all_recorded_exact': bool(records) and all(r['status'] == 'VERIFIED-EXACT' for r in records),
            'extraction_sha256': file_hash(root / 'extraction-result.json'), 'tensor_bytes_checked': total}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('fixtures', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--max-bytes', type=int, default=512 * 1024**2)
    a = p.parse_args()
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or os.environ.get('OMP_NUM_THREADS') != '2':
        p.error('requires nice 19 and OMP_NUM_THREADS=2')
    torch.set_num_threads(2)
    result = compare(a.fixtures, a.max_bytes)
    with a.output.open('xb') as f:
        f.write(json_bytes(result))
    print(json.dumps(result['census'], indent=2))
    raise SystemExit(0 if result['all_recorded_exact'] else 1)


if __name__ == '__main__':
    main()
