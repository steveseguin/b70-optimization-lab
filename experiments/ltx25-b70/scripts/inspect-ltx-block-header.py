#!/usr/bin/env python3
"""Read only checkpoint header metadata to bound the native block experiment."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import struct

MODEL = Path('/mnt/fast-ai/llm-models/LTX-2.5-baseline/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors')
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
VERIFICATION = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
PREFIX = re.compile(r'model\.diffusion_model\.transformer_blocks\.(\d+)\.(.+)\Z')


def inspect():
    verification = (ROOT / 'model-verification.json').read_bytes()
    if hashlib.sha256(verification).hexdigest() != VERIFICATION or json.loads(verification)['status'] != 'passed':
        raise RuntimeError('Model verification identity changed')
    before = MODEL.stat()
    with MODEL.open('rb') as stream:
        length = struct.unpack('<Q', stream.read(8))[0]
        if not 0 < length <= 64 * 1024**2:
            raise RuntimeError('Unexpected checkpoint header length')
        header_bytes = stream.read(length)
    header = json.loads(header_bytes)
    blocks = {i: {} for i in range(48)}
    for name, value in header.items():
        match = PREFIX.fullmatch(name)
        if not match:
            continue
        index, key = int(match[1]), match[2]
        if index not in blocks or value['dtype'] not in {'BF16', 'F32'}:
            raise RuntimeError('Unexpected native block index/dtype')
        start, end = value['data_offsets']
        elements = math.prod(value['shape'])
        size = {'BF16': 2, 'F32': 4}[value['dtype']] * elements
        if not 0 <= start < end <= before.st_size - 8 - length or end - start != size:
            raise RuntimeError('Invalid block tensor size/offset')
        blocks[index][key] = {'shape': value['shape'], 'dtype': value['dtype'], 'elements': elements, 'bytes': size}
    after = MODEL.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise RuntimeError('Checkpoint file changed during metadata read')
    if not all(blocks.values()):
        raise RuntimeError('Missing native block metadata')
    rows = [{'index': i, 'tensors': len(values), 'elements': sum(v['elements'] for v in values.values()),
             'stored_dtype_counts': dict(Counter(v['dtype'] for v in values.values())),
             'state_bytes': sum(v['bytes'] for v in values.values()), 'same_shapes_as_block_zero': values == blocks[0]}
            for i, values in blocks.items()]
    return {'schema': 'ltx.native-block-header.v1', 'scope': 'Header metadata only; no tensor allocation or model execution',
            'model_path': str(MODEL), 'model_verification_sha256': VERIFICATION,
            'file_stat': {'inode': before.st_ino, 'bytes': before.st_size, 'mtime_ns': before.st_mtime_ns},
            'header_bytes': length, 'header_sha256': hashlib.sha256(header_bytes).hexdigest(),
            'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'block_count': len(blocks), 'blocks': rows, 'block_zero_tensors': blocks[0],
            'limitations': ['This does not rehash checkpoint tensor data.',
                           'Stored checkpoint dtypes do not establish runtime loaded dtypes.',
                           'Weight bytes do not bound compiler peak memory or predict latency.',
                           'Native XPU lowering and full-clip equivalence remain untested.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = inspect()
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'block_count': report['block_count'], 'block_zero': report['blocks'][0],
                      'header_bytes_read': report['header_bytes']}, indent=2))
