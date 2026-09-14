#!/usr/bin/env python3
"""Validate bounded byte delivery using existing protected references, no GPU."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from continuation_delivery import verify_capture, iter_delivery_frames

LANE = Path(__file__).resolve().parents[1]


def reference_config():
    path = LANE / 'scripts/verify-continuation-reference-anchors.py'
    spec = importlib.util.spec_from_file_location('anchor_reference_config', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def direct_range_sha(capture, offset, length):
    digest = hashlib.sha256()
    with capture.open('rb', buffering=0) as stream:
        stream.seek(offset)
        while length:
            data = stream.read(min(length, 65536))
            if not data:
                raise ValueError('truncated reference range')
            digest.update(data)
            length -= len(data)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    config = reference_config()
    with args.receipt.open('x') as output:
        result = {'status': 'incomplete', 'references': [],
                  'source_sha256': {name: hashlib.sha256((LANE / 'scripts' / name).read_bytes()).hexdigest()
                                    for name in (Path(__file__).name, 'continuation_delivery.py',
                                                 'continuation_anchor_io.py',
                                                 'verify-continuation-reference-anchors.py')},
                  'gpu_requests': 0, 'playback_executed': False, 'new_media_saved': False,
                  'limits': ['Existing original independent clips, not a new continuation chain',
                             'Byte delivery to a hash sink, not displayed video or measured throughput',
                             'No audio timeline changes, precision conversion or file deletion']}
        try:
            for run, summary_relative in config.REFERENCES.items():
                capture = config.OUTPUT_ROOT / 'validation' / run / 'tensors.safetensors'
                verified = verify_capture(capture, capture.parent / 'summary.json')
                expected_raw = (LANE / summary_relative).read_bytes()
                expected = json.loads(expected_raw)
                for name, item in verified['tensors'].items():
                    assert item['sha256'] == expected['tensors'][name]['sha256'], name
                modes = []
                for chunk_index in (0, 1):
                    delivered = hashlib.sha256()
                    frame_count = 0
                    byte_count = 0
                    for payload in iter_delivery_frames(capture, verified, chunk_index):
                        delivered.update(payload)
                        frame_count += 1
                        byte_count += len(payload)
                    first = 0 if chunk_index == 0 else 1
                    assert frame_count == 25 - first and byte_count == (25 - first) * 786432
                    direct = direct_range_sha(capture, verified['tensors']['images']['byte_offset']
                                              + first * 786432, byte_count)
                    assert delivered.hexdigest() == direct
                    modes.append({'chunk_index': chunk_index, 'first_frame': first,
                                  'frames': frame_count, 'bytes': byte_count,
                                  'delivered_sha256': delivered.hexdigest(),
                                  'independent_range_sha256': direct,
                                  'iterator_exhausted': True})
                result['references'].append({'run_name': run,
                    'tracked_summary_sha256': hashlib.sha256(expected_raw).hexdigest(),
                    'four_tensor_hashes_match_tracked_original': True,
                    'verification': verified, 'delivery_modes': modes})
            assert 'torch' not in sys.modules
            result['status'] = 'passed-existing-reference-byte-delivery-only'
        except BaseException as error:
            result['status'] = 'failed'
            result['error'] = repr(error)
            raise
        finally:
            result['torch_imported'] = 'torch' in sys.modules
            output.write(json.dumps(result, indent=2) + '\n')
    print(result['status'], len(result['references']))


if __name__ == '__main__':
    main()
