#!/usr/bin/env python3
"""Bounded in-process CPU comparison; no model/server/host-control operations.

Checks one existing frame and the same protected four-tensor capture via the
old scalar rule and new exact bit rule. Host-fault timings are provisional and
cannot establish model throughput or a promoted generation speedup.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import statistics
import struct
import sys
import time
from unittest.mock import patch

import continuation_anchor_io as anchor
import continuation_delivery as delivery

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = LANE / 'data/finite-f32-candidate-01'
REFERENCES = {
    'baseline-01': 'data/requests/baseline-01/capture-summary.json',
    'speed-oracle-marble': 'data/speed-initial/speed-oracle-marble/capture-summary.json',
    'speed-oracle-bird': 'data/speed-initial/speed-oracle-bird/capture-summary.json',
}


def old_scalar():
    manifest = json.loads((PARENT / 'parent.json').read_text())
    raw = (PARENT / 'continuation_delivery.py').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest['source_sha256']['continuation_delivery.py']
    functions = [node for node in ast.parse(raw).body
                 if isinstance(node, ast.FunctionDef) and node.name == '_finite']
    assert len(functions) == 1
    env = {'struct': struct}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(PARENT / 'continuation_delivery.py'), 'exec'), env)
    return env['_finite']


def timed(callback):
    wall = time.perf_counter_ns()
    cpu = time.process_time_ns()
    result = callback()
    return result, {'wall_seconds': (time.perf_counter_ns() - wall) / 1e9,
                    'process_cpu_seconds': (time.process_time_ns() - cpu) / 1e9}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    scalar = old_scalar()
    candidate = delivery._finite
    functions = {'scalar': scalar, 'bit_intersections': candidate}
    order = ('scalar', 'bit_intersections', 'bit_intersections', 'scalar')
    with args.receipt.open('x') as output:
        fault = ROOT / 'FAULT.json'
        report = {'status': 'incomplete', 'host_fault_present': fault.exists(),
                  'host_fault_sha256': hashlib.sha256(fault.read_bytes()).hexdigest() if fault.exists() else None,
                  'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                  'python': sys.version, 'comparison_order': list(order),
                  'frame_rows': [], 'capture_rows': [],
                  'source_sha256': {name: hashlib.sha256((LANE / 'scripts' / name).read_bytes()).hexdigest()
                                    for name in (Path(__file__).name, 'finite_f32_bits.py',
                                                 'continuation_anchor_io.py', 'continuation_delivery.py')},
                  'gpu_requests': 0, 'torch_imported': False, 'new_video_generated': False,
                  'limits': ['Provisional CPU observations on a faulted host; no performance promotion',
                             'Only finite checking and capture verification measured; no model generation',
                             'Standard-library process only; no subprocess, retry, affinity or host-setting changes']}
        try:
            frame, frame_metadata = anchor.extract_anchor(ROOT / 'output/validation/baseline-01/tensors.safetensors')
            report['frame_sha256'] = frame_metadata['sha256']
            report['frame_bytes'] = len(frame)
            # Fixed ABBA order, three groups. No result cache or alternate input.
            for group in range(3):
                for arm in order:
                    result, timing = timed(lambda: functions[arm](frame, 'images'))
                    assert result is None
                    report['frame_rows'].append({'group': group, 'arm': arm, **timing})
            for run_name, summary_path in REFERENCES.items():
                path = ROOT / 'output/validation' / run_name / 'tensors.safetensors'
                expected_raw = (LANE / summary_path).read_bytes()
                expected = json.loads(expected_raw)
                control = None
                for arm in order:
                    # This substitution exists only inside this standalone CPU
                    # measurement process, never in a running model application.
                    with patch.object(delivery, '_finite', functions[arm]):
                        verified, timing = timed(lambda: delivery.verify_capture(path, path.parent / 'summary.json'))
                    for name, tensor in verified['tensors'].items():
                        assert tensor['sha256'] == expected['tensors'][name]['sha256']
                    if control is None:
                        control = verified
                    assert verified == control, 'candidate verification receipt differs from scalar'
                    report['capture_rows'].append({'run_name': run_name, 'arm': arm, **timing,
                        'verification_receipt_sha256': hashlib.sha256(json.dumps(verified,sort_keys=True).encode()).hexdigest(),
                        'tracked_summary_sha256': hashlib.sha256(expected_raw).hexdigest(),
                        'all_four_original_tensor_hashes_match': True, 'receipt_equals_scalar': True})
            report['medians'] = {}
            for label in ('frame', 'capture'):
                rows = report[label + '_rows']
                report['medians'][label] = {arm: {
                    key: statistics.median(row[key] for row in rows if row['arm'] == arm)
                    for key in ('wall_seconds', 'process_cpu_seconds')} for arm in order[:2]}
            assert 'torch' not in sys.modules
            report['status'] = 'passed-exact-cpu-candidate-provisional-timings'
        except BaseException as error:
            report['status'] = 'failed'
            report['error'] = repr(error)
            raise
        finally:
            report['torch_imported'] = 'torch' in sys.modules
            output.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['medians'], indent=2))


if __name__ == '__main__':
    main()
