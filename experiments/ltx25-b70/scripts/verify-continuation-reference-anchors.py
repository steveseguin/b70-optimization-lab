#!/usr/bin/env python3
"""Read three protected captures using stdlib only; save hashes, never media.

This verifies raw anchor extraction against original full-image hashes. It does
not load Torch, invoke the provider tensor path or run continuation inference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from continuation_anchor_io import extract_anchor, validate_anchor_bytes, FRAME_BYTES
from continuation_anchor_node import read_predecessor

LANE = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/output')
REFERENCES = {
    'baseline-01': 'data/requests/baseline-01/capture-summary.json',
    'speed-oracle-marble': 'data/speed-initial/speed-oracle-marble/capture-summary.json',
    'speed-oracle-bird': 'data/speed-initial/speed-oracle-bird/capture-summary.json',
}


def verify(run_name, summary_relative):
    summary_raw = (LANE / summary_relative).read_bytes()
    summary = json.loads(summary_raw)
    assert summary['run_name'] == run_name
    expected = summary['tensors']['images']
    assert expected['dtype'] == 'torch.float32' and expected['shape'] == [25, 256, 256, 3]
    assert expected['finite'] is True
    capture = OUTPUT_ROOT / 'validation' / run_name / 'tensors.safetensors'
    payload, metadata = extract_anchor(capture)
    image_offset = metadata['source_byte_offset'] - 24 * FRAME_BYTES
    # Hash all images using bounded reads; independently retain only the final
    # frame from this linear pass. The original capture hash binds the range.
    digest = hashlib.sha256()
    last_frame = bytearray()
    position = 0
    with capture.open('rb', buffering=0) as stream:
        stream.seek(image_offset)
        while position < 25 * FRAME_BYTES:
            block = stream.read(min(65536, 25 * FRAME_BYTES - position))
            if not block:
                raise ValueError('truncated reference images')
            digest.update(block)
            if position + len(block) > 24 * FRAME_BYTES:
                last_frame.extend(block[max(0, 24 * FRAME_BYTES - position):])
            position += len(block)
    assert digest.hexdigest() == expected['sha256'], 'full images disagree with protected reference'
    assert payload == bytes(last_frame), 'anchor is not the independently streamed final frame'
    validate_anchor_bytes(payload, hashlib.sha256(last_frame).hexdigest())
    provider_payload, _ = read_predecessor(OUTPUT_ROOT, run_name, metadata['sha256'])
    assert provider_payload == payload
    return {'run_name': run_name, 'summary_path': summary_relative,
            'summary_sha256': hashlib.sha256(summary_raw).hexdigest(),
            'original_images_sha256_verified': digest.hexdigest(),
            'anchor': metadata, 'independent_final_frame_bytes_equal': True,
            'provider_read_bytes_equal': True, 'native_tensor_path_executed': False,
            'full_images_streamed_bytes': position, 'maximum_stream_read_bytes': 65536}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    # Reserve the result path before reading. Failure leaves a partial receipt
    # with explicit status; existing evidence cannot be overwritten.
    with args.receipt.open('x') as output:
        report = {'status': 'incomplete', 'references': [], 'gpu_requests': 0,
                  'source_sha256': {name: hashlib.sha256((LANE / 'scripts' / name).read_bytes()).hexdigest()
                                    for name in (Path(__file__).name, 'continuation_anchor_io.py',
                                                 'continuation_anchor_node.py')},
                  'limitations': ['Existing protected T2V captures, not a generated continuation chain',
                                  'No Torch tensor construction, GPU inference or timing qualification',
                                  'No files deleted and no new media saved']}
        try:
            for name, summary in REFERENCES.items():
                report['references'].append(verify(name, summary))
            assert 'torch' not in sys.modules
            report['status'] = 'passed-existing-reference-anchor-bytes-only'
        except BaseException as error:
            report['status'] = 'failed'
            report['error'] = repr(error)
            raise
        finally:
            report['torch_imported'] = 'torch' in sys.modules
            output.write(json.dumps(report, indent=2) + '\n')
    print(report['status'], len(report['references']))


if __name__ == '__main__':
    main()
