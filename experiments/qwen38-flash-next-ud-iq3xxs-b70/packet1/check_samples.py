#!/usr/bin/env python3
"""Bounded real packed-weight fixtures, CPU reference only; never full tensors."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
from admit import HERE, ROOT, OWN, dump, sha, signature, priority, source_hashes
from loaders.dequant import dequantize, BY_NAME
import torch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model_dir', type=Path)
    ap.add_argument('--receipt', default='sample-receipt.json', choices=['sample-receipt.json','sample-repeat-receipt.json'])
    args = ap.parse_args()
    prio = priority()
    assert sys.byteorder == 'little'
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    admitted = json.loads((HERE / 'admission-receipt.json').read_text())
    assert admitted['passed'] and str(args.model_dir) == admitted['model_dir']
    files = {f['path']:f for f in admitted['files']}
    census = json.loads((HERE / 'tensor-census.json').read_text())
    groups = defaultdict(list)
    for t in census['tensors']:
        groups[(t['component'],t['type'])].append(t)
    selected = {}
    for group in groups.values():
        for i in sorted({0, len(group)//2, len(group)-1}):
            selected[group[i]['name']] = group[i]
    samples = []
    started = time.monotonic()
    for name,t in sorted(selected.items()):
        kind = t['type']
        block,size = BY_NAME[kind]  # fail closed for an unimplemented grid
        width = t['shape'][-1]
        assert width % block == 0
        rows = math.prod(t['shape']) // width
        row_bytes = width // block * size
        assert rows*row_bytes == t['bytes']
        path = args.model_dir / Path(t['shard']).name
        with path.open('rb') as stream:
            assert signature(os.fstat(stream.fileno())) == files[t['shard']]['before']
            for row in sorted({0,rows//2,rows-1}):
                # Full quantized rows. Scalar F32/BF16 rows get bounded edge windows.
                ranges = [(0,width)] if block>1 or width<=64 else [(0,64),(width-64,64)]
                for column,elements in ranges:
                    length = elements//block*size
                    offset = t['file_offsets'][0] + row*row_bytes + column//block*size
                    assert t['file_offsets'][0] <= offset and offset+length <= t['file_offsets'][1]
                    stream.seek(offset)
                    raw = stream.read(length)
                    assert len(raw) == length
                    out = dequantize(kind,raw,[1,elements])
                    again = dequantize(kind,raw,[1,elements])
                    encoded = out.numpy().astype('<f4',copy=False).tobytes()
                    assert encoded == again.numpy().astype('<f4',copy=False).tobytes(), name
                    assert out.device.type == 'cpu' and out.dtype == torch.float32
                    finite = bool(torch.isfinite(out).all())
                    assert finite, name
                    values = out.flatten().double()
                    samples.append(dict(name=name,component=t['component'],type=kind,shape=t['shape'],
                        shard=t['shard'],row_index=row,row_count=rows,row_width=width,
                        column_start=column,elements=elements,file_offset=offset,raw_bytes=length,
                        raw_sha256=sha(raw),decoded_fp32_le_sha256=sha(encoded),
                        same_process_bit_exact=True,finite_count=elements,zero_count=int((out==0).sum()),
                        negative_zero_count=int(((out==0)&torch.signbit(out)).sum()),
                        min=float(values.min()),max=float(values.max()),mean=float(values.mean()),
                        rms=float(torch.sqrt((values*values).mean())),first_eight_values=values[:8].tolist()))
            assert signature(os.fstat(stream.fileno())) == files[t['shard']]['before']
        print(f'{name} {kind}: PASS',flush=True)
    content = dict(selection='first/middle/last name per component/type; first/middle/last flat rows; full quantized rows; 64-element edge windows for scalar rows wider than 64',
                   output='IEEE FP32 little endian, stored row order, no GPU arithmetic claim',
                   absent_requested_types=[t for t in ['IQ3_XXS','Q3_K','F16'] if t not in census['types']],
                   sampled_tensor_count=len(selected),sample_count=len(samples),
                   model_bytes_read=sum(s['raw_bytes'] for s in samples),samples=samples)
    digest = sha(json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    receipt = dict(schema='qwen38-ud-iq3xxs.cpu-reference-fixtures.v1',passed=True,
        utc=datetime.now(timezone.utc).isoformat(),host=os.uname().nodename,execution=prio,
        python=sys.version,executable=sys.executable,torch=torch.__version__,
        source_hashes=source_hashes([Path(__file__),HERE/'admit.py',HERE/'tensor-census.json',HERE/'admission-receipt.json'] + sorted((OWN/'stage1/packet1b/loaders').glob('*.py')) + sorted((OWN/'stage1/packet1b/loaders').glob('*grid*.json'))),
        elapsed_seconds=time.monotonic()-started,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        content_sha256=digest,content=content)
    if args.receipt == 'sample-repeat-receipt.json':
        first = json.loads((HERE/'sample-receipt.json').read_text())
        receipt['fresh_process_bit_exact'] = digest == first['content_sha256'] and receipt['source_hashes']==first['source_hashes']
        assert receipt['fresh_process_bit_exact']
    dump(HERE/args.receipt,receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ['content','source_hashes']}),flush=True)


if __name__ == '__main__':
    main()
