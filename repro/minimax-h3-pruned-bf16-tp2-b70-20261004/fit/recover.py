#!/usr/bin/env python3
"""CPU AdaLN reconstruction experiment, NOT a certified checkpoint producer.

Only reads local safetensors. No torch, network, mmap, device access or launches.
Missing inputs produce a blocked receipt and exit 2; mismatches exit 1.
Output is hashes/metrics only: no derived weights are redistributed or installed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import struct
import sys

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
              'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_name] = '2'

HERE = Path(__file__).resolve().parent
PROTECTED = (Path('/mnt/usb-models/llm-models'), Path('/mnt/usb-models/hf-cache'))
np = None  # Imported only after missing-input preflight.


def safe_path(value, writing=False):
    p = Path(value).resolve()
    forbidden = PROTECTED + ((Path('/mnt/fast-ai'),) if writing else ())
    if any(p == q or q in p.parents for q in forbidden):
        raise ValueError(f'Forbidden path: {p}')
    if p == Path('/dev') or Path('/dev') in p.parents:
        raise ValueError('Device paths are forbidden')
    return p


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Tensors:
    """Read a single file or shards, one bounded row chunk at a time."""
    def __init__(self, path):
        path = safe_path(path)
        files = sorted(path.glob('*.safetensors')) if path.is_dir() else [path]
        self.entries, self.headers, self.hashers = {}, [], {}
        for path in files:
            path = safe_path(path)
            with path.open('rb') as f:
                prefix = f.read(8)
                n, = struct.unpack('<Q', prefix)
                if not 2 <= n <= 16 * 1024**2:
                    raise ValueError('Invalid or excessive header size')
                raw = f.read(n)
            h = json.loads(raw)
            self.headers.append(dict(path=str(path), bytes=path.stat().st_size,
                                     header_sha256=sha(raw), header_with_length_sha256=sha(prefix+raw)))
            for key, e in h.items():
                if key == '__metadata__':
                    continue
                if key in self.entries:
                    raise ValueError(f'Duplicate key: {key}')
                self.entries[key] = (path, 8+n, e)

    def read(self, key, start=0, stop=None):
        path, base, e = self.entries[key]
        dtype = {'F32': '<f4', 'F16': '<f2', 'BF16': '<u2'}[e['dtype']]
        shape = e['shape']
        stop = shape[0] if stop is None else stop
        stride = math.prod(shape[1:]) * np.dtype(dtype).itemsize
        if not 0 <= start <= stop <= shape[0]:
            raise ValueError('Invalid row range')
        size = (stop-start)*stride
        if size > 128 * 1024**2:
            raise ValueError('Read exceeds 128 MiB; reduce --chunk')
        with path.open('rb') as f:
            f.seek(base+e['data_offsets'][0]+start*stride)
            raw = f.read(size)
        if len(raw) != size:
            raise ValueError(f'Truncated tensor: {key}')
        a = np.frombuffer(raw, dtype=dtype).reshape([stop-start]+shape[1:])
        if e['dtype'] == 'BF16':
            a = (a.astype(np.uint32) << 16).view(np.float32)
        return a.astype(np.float32), raw

    def inventory(self, key):
        e = self.entries[key][2]
        digest = hashlib.sha256()
        for i in range(0, e['shape'][0], 1024):
            _, raw = self.read(key, i, min(i+1024, e['shape'][0]))
            digest.update(raw)
        return dict(key=key, shape=e['shape'], dtype=e['dtype'], sha256=digest.hexdigest())


def bf16(x):
    u = np.ascontiguousarray(x, dtype=np.float32).view(np.uint32)
    return ((u + 0x7fff + ((u >> 16) & 1)) & 0xffff0000).view(np.float32)


def curve(weights, precision, reverse=False):
    dtype = np.float64 if precision == 'f64' else np.float32
    t = np.arange(1025, dtype=dtype) / 1024
    if reverse:
        t = t[::-1].copy()
    phase = t[:, None] * np.exp(-np.log(10000.) * np.arange(128, dtype=dtype)/128)
    x = np.concatenate([np.cos(phase), np.sin(phase)], axis=1).astype(dtype)
    w1,b1,w2,b2 = [w.astype(dtype) for w in weights]
    # bf16-io models rounded operands/outputs, NOT BF16 accumulation.
    rnd = bf16 if precision == 'bf16-io' else lambda a: a
    def silu(a):
        return (a * (1/(1+np.exp(-a.astype(np.float64))))).astype(dtype)
    x = rnd(rnd(x) @ rnd(w1).T + rnd(b1))
    x = rnd(silu(x))
    x = rnd(x @ rnd(w2).T + rnd(b2))
    return rnd(silu(x))


def metric(candidate, reference, storage):
    """ULP means absolute error / spacing toward +inf at stored reference."""
    c = np.ascontiguousarray(candidate, dtype=storage)
    r = np.ascontiguousarray(reference, dtype=storage)
    delta = np.abs(c.astype(np.float64)-r.astype(np.float64))
    spacing = np.abs(np.nextafter(r, np.array(np.inf, dtype=storage)).astype(np.float64)-r)
    return dict(sha256=sha(c.tobytes()), reference_sha256=sha(r.tobytes()),
                shape=list(c.shape), dtype=str(c.dtype),
                bit_exact=c.tobytes() == r.tobytes(),
                equal_values=int(np.count_nonzero(c == r)), elements=c.size,
                max_abs=float(delta.max()), max_reference_ulp=float((delta/spacing).max()))


def run(args, receipt):
    global np
    import numpy as np
    import io
    from contextlib import redirect_stdout
    config = io.StringIO()
    with redirect_stdout(config):
        np.show_config()
    receipt['environment'].update(numpy=np.__version__, numpy_config=config.getvalue())
    full, fitted = Tensors(args.full_dir), Tensors(args.fitted)
    receipt['input_headers'] = dict(official=full.headers, fitted=fitted.headers)
    keys = ['time_embedder.linear_1.weight', 'time_embedder.linear_1.bias',
            'time_embedder.linear_2.weight', 'time_embedder.linear_2.bias']
    weights = [full.read(k)[0] for k in keys]
    expected = [(5376,256),(5376,),(2688,5376),(2688,)]
    if [w.shape for w in weights] != expected:
        raise ValueError('Not the declared official H3 time embedder')
    reference, _ = fitted.read('adaln_t_table')
    if reference.shape != (1025,8):
        raise ValueError('Wrong fitted table shape')
    receipt['inputs'] = [full.inventory(k) for k in keys]
    receipt['reference_tensors'] = [fitted.inventory('adaln_t_table')]
    blocks = list(range(50)) + ['final'] if args.blocks == 'all' else args.blocks.split(',')
    pairs = []
    for b in blocks:
        source = 'norm_out.linear' if b == 'final' else f'transformer_blocks.{b}.adaln_proj.linear'
        target = 'final_layer.adaln_proj.linear' if b == 'final' else f'blocks.{b}.adaln_proj.linear'
        for suffix in ('.weight', '.bias'):
            receipt['inputs'].append(full.inventory(source+suffix))
            receipt['reference_tensors'].append(fitted.inventory(target+suffix))
        pairs.append((source,target))
    receipt['variants'] = []
    for precision in args.precisions.split(','):
        S = curve(weights, precision, args.reverse_grid)
        mean = S.mean(axis=0)
        U, singular, Vt = np.linalg.svd(S-mean, full_matrices=False)
        table, V = U[:,:8]*singular[:8], Vt[:8].T
        # Resolve SVD signs from our own largest-magnitude coordinate, not target bytes.
        signs = np.sign(table[np.argmax(np.abs(table),axis=0),np.arange(8)])
        table, V = table*signs, V*signs
        if args.reverse_grid:
            table = table[::-1].copy()
            S = S[::-1].copy()
        for solver in args.solvers.split(','):
            stored = solver != 'svd'
            T = reference if stored else table
            if solver == 'normal':
                C = T @ np.linalg.inv((T.T @ T).astype(np.float64)).astype(np.float32)
                basis = None
            elif solver == 'lstsq':
                basis = np.linalg.lstsq(T.astype(np.float64), (S-mean).astype(np.float64), rcond=None)[0].T
            else:
                basis = V
            result = dict(precision=precision, solver=solver,
                          uses_stored_table=stored, uses_stored_bias=solver=='normal',
                          table=metric(table,reference,np.float32), projections=[])
            for source,target in pairs:
                bias = full.read(source+'.bias')[0]
                refw = fitted.read(target+'.weight')[0]
                refb = fitted.read(target+'.bias')[0]
                rows = len(bias)
                outw, outb = np.empty((rows,8),np.float16), np.empty(rows,np.float16)
                for i in range(0,rows,args.chunk):
                    j = min(rows,i+args.chunk)
                    W = full.read(source+'.weight',i,j)[0].astype(S.dtype)
                    outb[i:j] = W @ mean + bias[i:j]
                    if solver == 'normal':
                        outw[i:j] = (W @ S.T + bias[i:j,None] - refb[i:j,None]) @ C
                    else:
                        outw[i:j] = W @ basis
                result['projections'].append(dict(key=target,
                    weight=metric(outw,refw,np.float16), bias=metric(outb,refb,np.float16)))
            result['adaln_exact'] = (not stored and args.blocks == 'all' and
                result['table']['bit_exact'] and all(p[k]['bit_exact']
                    for p in result['projections'] for k in ('weight','bias')))
            receipt['variants'].append(result)
    receipt['adaln_bit_exact'] = any(v['adaln_exact'] for v in receipt['variants'])
    receipt['verdict'] = 'adaln-exact-only' if receipt['adaln_bit_exact'] else 'inexact'
    receipt['outputs'] = 'Per-tensor candidate hashes in variants; tensors not written'
    receipt['max_abs'] = 'Per-tensor, per-variant measurements below'
    receipt['max_reference_ulp'] = 'Per-tensor, per-variant measurements below'
    # This harness cannot certify unchanged tensors, serialization or full model parity.
    receipt['whole_denoiser_bit_exact'] = False


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--full-dir', required=True)
    ap.add_argument('--fitted', required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    ap.add_argument('--blocks', default='0,25,final', help='all for 50 blocks and final layer')
    ap.add_argument('--chunk', type=int, default=1024)
    ap.add_argument('--precisions', default='f32,f64,bf16-io')
    ap.add_argument('--solvers', default='svd,normal,lstsq')
    ap.add_argument('--reverse-grid', action='store_true', help='Probe reduction order on same grid')
    args = ap.parse_args()
    if not 1 <= args.chunk <= 8192:
        ap.error('chunk must be 1..8192')
    if not set(args.precisions.split(',')) <= {'f32','f64','bf16-io'}:
        ap.error('Unknown precision')
    if not set(args.solvers.split(',')) <= {'svd','normal','lstsq'}:
        ap.error('Unknown solver')
    if args.blocks != 'all' and any(x != 'final' and x not in map(str,range(50)) for x in args.blocks.split(',')):
        ap.error('Unknown block')
    output = safe_path(args.receipt, writing=True)
    if output.exists():
        ap.error('Receipt exists; use a new path')
    receipt = dict(schema='neural.download.h3-fit-attempt.v1', verdict='blocked',
                   attempted_at=datetime.now(timezone.utc).isoformat(),
                   whole_denoiser_bit_exact=False, adaln_bit_exact=None,
                   max_abs=None, max_reference_ulp=None, inputs=[], outputs=[],
                   script_sha256=sha(Path(__file__).read_bytes()), arguments=vars(args).copy(),
                   environment=dict(host=platform.node(), python=platform.python_version(),
                                    threads=2, nice=os.getpriority(os.PRIO_PROCESS,0)),
                   official_revision='42ed227ee7df40d41602854ae760620d6eb651fe',
                   official_file_hashes_verified=False)
    receipt['arguments']['receipt'] = str(args.receipt)
    try:
        paths = [safe_path(args.full_dir),safe_path(args.fitted)]
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            receipt['missing_inputs'] = missing
        else:
            # 2 GiB address-space ceiling, including BLAS workspace; never whole denoiser.
            resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
            run(args,receipt)
    except Exception as exc:
        receipt['verdict'] = 'error'
        receipt['error'] = f'{type(exc).__name__}: {exc}'
    receipt['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output.write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    print(receipt['verdict'])
    return 0 if receipt['verdict']=='adaln-exact-only' else 2 if receipt['verdict'] in ('blocked','error') else 1


if __name__ == '__main__':
    sys.exit(main())
