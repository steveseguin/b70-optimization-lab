#!/usr/bin/env python3
"""Bounded real-byte CPU fixtures; never import a serving runtime or query XPU."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import struct
import sys
import time

from admit import HERE, P1, REPO, guards, sha, utc


def digest(b):
    return hashlib.sha256(b).hexdigest()


def e4m3(byte):
    """Independent scalar IEEE E4M3FN decode, including subnormal/signed zero."""
    sign, exponent, fraction = (-1 if byte & 128 else 1), (byte >> 3) & 15, byte & 7
    if exponent == 15 and fraction == 7:
        return float('nan')
    return sign * (fraction * 2.0**-9 if exponent == 0 else (1 + fraction/8) * 2.0**(exponent-7))


def bf16(raw):
    return struct.unpack('<f', b'\0\0' + raw)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model', type=Path)
    ap.add_argument('--receipt', default='sample-receipt.json')
    args = ap.parse_args()
    settings = guards()
    import torch
    from reference.math import fp8_dequant
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    start = time.monotonic()
    admission = json.loads((HERE/'admission-receipt.json').read_text())
    assert admission['passed'] and args.model.resolve() == Path(admission['model'])
    census = json.loads((HERE/'tensor-census.json').read_text())
    assert sha(HERE/'tensor-census.json') == admission['census_sha256']
    tensors = {t['name']: t for t in census['tensors']}
    files = {r['path']: r for r in admission['files']}
    read_bytes = 0

    def read_range(t, offset, size):
        nonlocal read_bytes
        path = args.model / t['shard']
        st = path.stat()
        assert (st.st_size, st.st_mtime_ns) == (files[t['shard']]['bytes'], files[t['shard']]['mtime_ns'])
        assert 0 <= offset <= t['bytes'] - size
        with path.open('rb') as f:
            f.seek(t['file_offsets'][0] + offset)
            b = f.read(size)
        assert len(b) == size
        read_bytes += size
        return b

    def raw_tensor(t):
        return t.contiguous().view(torch.uint8).numpy().tobytes()

    def stats(t):
        v = t.float()
        return {'count': v.numel(), 'finite': int(torch.isfinite(v).sum()),
                'zeros': int((v == 0).sum()), 'min': v.min().item(), 'max': v.max().item(),
                'mean': v.double().mean().item(), 'rms': v.double().square().mean().sqrt().item(),
                'sha256': digest(raw_tensor(t)), 'dtype': str(t.dtype)}

    # Exhaust all byte encodings independently of torch's FP8 decoder.
    all_raw = bytes(range(256))
    decoded = torch.frombuffer(bytearray(all_raw), dtype=torch.float8_e4m3fn).float()
    for i in range(256):
        expected = e4m3(i)
        assert math.isnan(decoded[i].item()) if math.isnan(expected) else struct.pack('<f', decoded[i].item()) == struct.pack('<f', expected)
    assert e4m3(0x38) == 1 and e4m3(0x40) == 2 and e4m3(0x7e) == 448 and e4m3(1) == 2**-9
    # Boundary fixture: four different scales, both signs, subnormals, and max.
    fixture_raw = bytes([0x38, 0xb8, 0x40, 0xc0, 0x01, 0x7e])
    fixture_raw = (fixture_raw * ((256*256+5)//6))[:256*256]
    fixture_scales = struct.pack('<4H', 0x3f00, 0x4000, 0x3e80, 0x4080)  # .5,2,.25,4
    q = torch.frombuffer(bytearray(fixture_raw), dtype=torch.float8_e4m3fn).reshape(256,256)
    s = torch.frombuffer(bytearray(fixture_scales), dtype=torch.bfloat16).reshape(2,2)
    want = b''.join(struct.pack('<f', e4m3(b)*[.5,2,.25,4][(i//256//128)*2+(i%256//128)]) for i,b in enumerate(fixture_raw))
    got = fp8_dequant(q,s,torch.float32)
    assert raw_tensor(got) == want
    assert raw_tensor(fp8_dequant(q,s)) == b''.join(struct.pack('<e', v[0]) for v in struct.iter_unpack('<f', want))
    known = {'all_256_e4m3fn_encodings_passed': True, 'nan_codes': [127,255],
             'boundary_shape': [256,256], 'bf16_scale_u16_le': [0x3f00,0x4000,0x3e80,0x4080],
             'expected_f32_sha256': digest(want), 'expected_f16_sha256': digest(raw_tensor(fp8_dequant(q,s))),
             'passed': True}
    pairs = []
    for t in tensors.values():
        if t['dtype'] != 'F8_E4M3':
            continue
        s = tensors[t['format']['scale_tensor']]
        assert s['dtype'] == 'BF16' and s['shape'] == [(d+127)//128 for d in t['shape']]
        assert all(d%128 == 0 for d in t['shape'])
        pairs.append({'weight': t['name'], 'weight_shape': t['shape'], 'scale': s['name'], 'scale_shape': s['shape'],
                      'scale_bytes': s['bytes'], 'block_aligned': True})
    selected = [t for t in tensors.values() if t['dtype']=='F8_E4M3' and
                ('.layers.0.' in t['name'] or '.layers.3.' in t['name'] or t['component']=='native_mtp')]
    fp8_rows = []
    for t in selected:
        n,k = t['shape']
        scale = tensors[t['format']['scale_tensor']]
        # Top-left 2x2 blocks tests both 127->128 transitions. Last block tests extent.
        for row0,col0,width in [(0,0,256),(n-128,k-128,128)]:
            b = b''.join(read_range(t,(row0+r)*k+col0,width) for r in range(width))
            blocks = width//128
            sb = b''.join(read_range(scale,2*((row0//128+r)*scale['shape'][1]+col0//128),2*blocks) for r in range(blocks))
            q = torch.frombuffer(bytearray(b), dtype=torch.float8_e4m3fn).reshape(width,width)
            s = torch.frombuffer(bytearray(sb), dtype=torch.bfloat16).reshape(blocks,blocks)
            scales = [bf16(sb[i:i+2]) for i in range(0,len(sb),2)]
            assert all(math.isfinite(v) and v > 0 for v in scales)
            vals = [e4m3(v)*scales[(i//width//128)*blocks+(i%width//128)] for i,v in enumerate(b)]
            assert all(math.isfinite(v) for v in vals)
            expected32 = b''.join(struct.pack('<f',v) for v in vals)
            expected16 = b''.join(struct.pack('<e',v) for v in vals)
            out32, out16 = fp8_dequant(q,s,torch.float32), fp8_dequant(q,s)
            assert raw_tensor(out32) == expected32 and raw_tensor(out16) == expected16
            assert raw_tensor(fp8_dequant(q,s)) == expected16
            # Pack block-major [Nblock,Kblock,128,128], then restore row-major.
            packed = q.view(torch.uint8).reshape(blocks,128,blocks,128).permute(0,2,1,3).contiguous()
            restored = packed.permute(0,2,1,3).contiguous().reshape(width,width)
            assert raw_tensor(restored) == b
            if blocks == 2:
                assert raw_tensor(fp8_dequant(restored.view(torch.float8_e4m3fn),s)) == expected16
            examples = []
            for rr,cc in [(0,0),(127,127),(width-1,width-1)] + ([(127,128),(128,127),(128,128)] if width==256 else []):
                i = rr*width+cc
                j = (rr//128)*blocks+cc//128
                examples.append({'weight_index':[row0+rr,col0+cc], 'fp8_u8':b[i], 'fp8_value':e4m3(b[i]),
                                 'scale_index':[(row0+rr)//128,(col0+cc)//128],
                                 'scale_u16':int.from_bytes(sb[2*j:2*j+2],'little'), 'scale_value':scales[j],
                                 'product_f32':struct.unpack_from('<f',expected32,4*i)[0],
                                 'product_f16':struct.unpack_from('<e',expected16,2*i)[0]})
            fp8_rows.append({'tensor':t['name'], 'origin':[row0,col0], 'shape':[width,width],
                             'raw_sha256':digest(b), 'packed_block_major_sha256':digest(raw_tensor(packed)),
                             'scale_raw_hex':sb.hex(), 'scale_values':scales,
                             'unscaled':stats(q.float()), 'dequant_f32':stats(out32), 'dequant_f16':stats(out16),
                             'scalar_reference_exact':True,'packing_roundtrip_exact':True,'repeat_exact':True,
                             'division_differs': not torch.equal(out32, q.float()/s.float().repeat_interleave(128,0).repeat_interleave(128,1)),
                             'known_real_values':examples})
    bf_rows = []
    for t in tensors.values():
        if t['dtype'] != 'BF16' or t['format']['kind'] != 'unquantized':
            continue
        count = t['bytes']//2
        if t['component'] in ['embedding','target_head']:
            cols = t['shape'][1]
            ranges = [(r*cols,cols) for r in [0,127,128,t['shape'][0]-1]]
        elif count <= 768:
            ranges = [(0,count)]
        else:
            ranges = [(0,256),((count//2)-128,256),(count-256,256)]
        raw = b''.join(read_range(t,off*2,size*2) for off,size in ranges)
        b = torch.frombuffer(bytearray(raw),dtype=torch.bfloat16)
        widened = b.float()
        expected = b''.join(b'\0\0'+raw[i:i+2] for i in range(0,len(raw),2))
        assert raw_tensor(widened) == expected and raw_tensor(widened.to(torch.bfloat16)) == raw
        assert bool(torch.isfinite(widened).all())
        f16 = widened.to(torch.float16)
        bf_rows.append({'tensor':t['name'],'component':t['component'],'shape':t['shape'],
                        'ranges_flat_elements':ranges,'raw_bf16_sha256':digest(raw),
                        'f32':stats(widened),'f16_cpu_reference_cast':stats(f16),
                        'bf16_roundtrip_exact':True, 'f16_changed_elements':int((f16.float()!=widened).sum()),
                        'first_8_bf16_u16':[int.from_bytes(raw[i:i+2],'little') for i in range(0,min(16,len(raw)),2)]})
    # Deterministic content separated from timing for fresh-process comparison.
    content = {'known_value_fixture':known,'scale_pairs':pairs,'fp8_samples':fp8_rows,'bf16_samples':bf_rows}
    encoded = json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    sources = [Path(__file__), HERE/'admit.py', HERE.parent/'packet1b/reference/math.py',
               HERE.parent/'packet1b/source-evidence.json', P1/'tensor-contract.json',
               HERE/'admission-receipt.json', HERE/'tensor-census.json']
    receipt = {'schema':'own-xpu-runtime.packet2.cpu-samples.v1','utc':utc(),'argv':sys.argv,
               'settings':settings,'python':sys.version,'executable':sys.executable,'torch':torch.__version__,
               'torch_threads':torch.get_num_threads(),'interop_threads':torch.get_num_interop_threads(),
               'device':'cpu','model':str(args.model),'read_bytes':read_bytes,
               'sources':{str(p.relative_to(REPO)):sha(p) for p in sources},
               'content_sha256':digest(encoded),'content':content,'passed':True,
               'elapsed_seconds':time.monotonic()-start,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (HERE/args.receipt).write_text(json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:receipt[k] for k in ['passed','read_bytes','content_sha256','elapsed_seconds','max_rss_kib']}))
    print(f'{len(pairs)} scale pairs; {len(selected)} FP8 tensors / {len(fp8_rows)} windows; {len(bf_rows)} BF16 tensors')


if __name__ == '__main__':
    main()
