#!/usr/bin/env python3
"""CPU AdaLN reconstruction experiment, NOT a certified checkpoint producer.

Only reads local safetensors. No torch, network, mmap, device access or launches.
Missing inputs produce a blocked receipt and exit 2; mismatches exit 1.
Compare mode emits metrics only; --assemble searches independent fits and keeps
only a whole-file SHA-256 match. No network, installation or redistribution.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import itertools
import tempfile
import shutil
import re
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


def curve(weights, precision, reverse=False, grid='divide', time_range=(0., 1.)):
    dtype = np.float64 if precision == 'f64' else np.float32
    t = (np.arange(1025, dtype=dtype) / 1024 if grid == 'divide'
         else np.linspace(0, 1, 1025, dtype=dtype))
    t = time_range[0] + t * (time_range[1] - time_range[0])
    if reverse:
        t = t[::-1].copy()
    phase = t[:, None] * np.exp(-np.log(10000.) * np.arange(128, dtype=dtype)/128)
    x = np.concatenate([np.cos(phase), np.sin(phase)], axis=1).astype(dtype)
    w1,b1,w2,b2 = [w.astype(dtype) for w in weights]
    # bf16-io models rounded operands/outputs, NOT BF16 accumulation.
    rnd = bf16 if precision in ('bf16-io', 'bf16-acc') else lambda a: a
    def silu(a):
        return (a * (1/(1+np.exp(-a.astype(np.float64))))).astype(dtype)
    x = rnd(matmul(rnd(x), rnd(w1).T, precision) + rnd(b1))
    x = rnd(silu(x))
    x = rnd(matmul(x, rnd(w2).T, precision) + rnd(b2))
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



HISTORICAL_SHA = 'a32572fb90b5508b201ec7c2eddcc184b13ddfd3c6f6d2cf06a0b46535d541b4'
LAYOUT_SHA = 'c426b8dddb8745c52e0e5f511eaf6cba2d8903a3818c3cee448516d968a7b710'
HISTORICAL_BYTES = 40225724176


def matmul(a, b, precision):
    """Explicit BF16 accumulator hypothesis; no claim of a hardware BLAS match.

    BF16 operands; each scalar product is exact in F32, add to the previous
    BF16 accumulator in F32 and round to BF16 after every K term, in K order.
    This is deliberately distinct from BF16 I/O with an F32 accumulator.
    """
    if precision != 'bf16-acc':
        return a @ b
    a, b = bf16(a), bf16(b)
    out = np.zeros((a.shape[0], b.shape[1]), np.float32)
    for k in range(a.shape[1]):
        out = bf16(out + a[:, k:k+1] * b[k:k+1, :])
    return out


def file_sha(path):
    h = hashlib.sha256()
    with safe_path(path).open('rb') as f:
        while raw := f.read(4 * 1024**2):
            h.update(raw)
    return h.hexdigest()


def layout(raw):
    """Retain original JSON bytes, padding, tensor order and offsets verbatim."""
    if len(raw) < 10 or struct.unpack('<Q', raw[:8])[0] != len(raw)-8:
        raise ValueError('Invalid layout prefix')
    h = json.loads(raw[8:])
    entries = {k: v for k, v in h.items() if k != '__metadata__'}
    end = 0
    for key, e in sorted(entries.items(), key=lambda item: item[1]['data_offsets'][0]):
        start, stop = e['data_offsets']
        n = math.prod(e['shape']) * {'BF16': 2, 'F16': 2, 'F32': 4}[e['dtype']]
        if start != end or stop-start != n or any(d <= 0 for d in e['shape']):
            raise ValueError(f'Invalid layout offsets/shape: {key}')
        end = stop
    return entries, len(raw)+end


def copy_plan(header, full):
    """Inverse of the lab's run_h3_t2v.build_remap; raw bytes, no casting.

    Each output maps to ordered (official key, first row, end row) slices.
    Q,K,V concatenate in that order; SwiGLU halves exchange symmetrically.
    """
    names = {
        'video_patch_proj': 'proj_in', 'audio_patch_proj': 'audio_proj_in',
        'condition_proj': 'context_embedder', 'final_layer.norm': 'norm_out.norm',
        'final_layer.video_out': 'proj_out', 'final_layer.audio_out': 'audio_proj_out',
    }
    plan = {}
    for target, entry in header.items():
        if target in ('adaln_t_table','rope.inv_freq') or '.adaln_proj.linear.' in target:
            continue
        source = target
        for old, new in names.items():
            if source.startswith(old + '.'):
                source = new + source[len(old):]
                break
        source = re.sub(r'^blocks\.(\d+)\.', r'transformer_blocks.\1.', source)
        source = source.replace('token_refiner.blocks.', 'token_refiner.refiner_blocks.')
        if '.attn.qkv_proj.' in source:
            sources = [source.replace('.qkv_proj.', f'.to_{x}.') for x in ('q','k','v')]
        else:
            source = source.replace('.attn.out_proj.', '.attn.to_out.0.')
            source = source.replace('.attn.q_norm.', '.attn.norm_q.')
            source = source.replace('.attn.k_norm.', '.attn.norm_k.')
            source = source.replace('.mlp.fc1.', '.ff.net.0.proj.')
            source = source.replace('.mlp.fc2.', '.ff.net.2.')
            sources = [source]
        slices = []
        total_rows = 0
        for key in sources:
            e = full.entries[key][2]
            if e['dtype'] != entry['dtype'] or e['shape'][1:] != entry['shape'][1:]:
                raise ValueError(f'Copy dtype/shape mismatch: {target} <- {key}')
            rows = e['shape'][0]
            if '.mlp.fc1.' in target:
                if rows % 2:
                    raise ValueError('Odd SwiGLU rows')
                slices.extend([(key,rows//2,rows),(key,0,rows//2)])
            else:
                slices.append((key,0,rows))
            total_rows += rows
        if total_rows != entry['shape'][0]:
            raise ValueError(f'Copy row mismatch: {target}')
        plan[target] = slices
    return plan


def assemble_base(path, raw_header, full, plan, chunk=1024):
    """Create one disk-backed candidate; fit slots remain holes until patched."""
    header, size = layout(raw_header)
    with safe_path(path, writing=True).open('xb') as out:
        out.write(raw_header)
        out.truncate(size)
        for target, slices in plan.items():
            e = header[target]
            out.seek(len(raw_header)+e['data_offsets'][0])
            count = 0
            for key, first, last in slices:
                for i in range(first, last, chunk):
                    _, raw = full.read(key,i,min(last,i+chunk))
                    out.write(raw)
                    count += len(raw)
            if count != e['data_offsets'][1]-e['data_offsets'][0]:
                raise ValueError(f'Wrong copied size: {target}')
    return header


def write_fits(path, raw_header, tensors):
    header, _ = layout(raw_header)
    required = {k for k in header if k in ('adaln_t_table','rope.inv_freq') or '.adaln_proj.linear.' in k}
    seen = set()
    with path.open('r+b') as out:
        for key, array in tensors:
            if key not in required or key in seen:
                raise ValueError(f'Unexpected/duplicate fitted tensor: {key}')
            e = header[key]
            a = np.ascontiguousarray(array, dtype={'F16':'<f2','F32':'<f4'}[e['dtype']])
            if list(a.shape) != e['shape'] or not np.isfinite(a).all():
                raise ValueError(f'Wrong shape or nonfinite fitted tensor: {key}')
            out.seek(len(raw_header)+e['data_offsets'][0])
            out.write(a.tobytes())
            seen.add(key)
    if seen != required:
        raise ValueError(f'Missing fitted tensors: {sorted(required-seen)}')


def variant_specs(precisions=('f32','bf16-io','bf16-acc')):
    # Only documented time range and table size; grid implementations happen to
    # be equal on this binary-fraction grid. Retain both identities in receipts.
    for precision, grid, reverse, solver, signs in itertools.product(
            precisions, ('divide','linspace'), (False,True),
            ('svd','normal-left','normal-right'), ('native','largest')):
        yield dict(precision=precision, grid=grid, reverse=reverse, solver=solver,
                   signs=signs, time_range=[0.,1.], table_size=1025, rank=8,
                   rope='numpy-f32-power', svd='numpy-lapack', mean='numpy-f32')


def fit_tensors(full, header, spec, chunk):
    keys = [f'time_embedder.linear_{i}.{s}' for i in (1,2) for s in ('weight','bias')]
    S = curve([full.read(k)[0] for k in keys], spec['precision'], spec['reverse'],
              spec['grid'], spec['time_range'])
    mean = S.mean(axis=0)
    U, values, Vt = np.linalg.svd(S-mean, full_matrices=False)
    rank = spec['rank']
    T, V = U[:,:rank]*values[:rank], Vt[:rank].T
    if spec['signs'] == 'largest':
        signs = np.where(T[np.argmax(np.abs(T),axis=0),np.arange(rank)] < 0,-1.,1.).astype(T.dtype)
        T, V = T*signs, V*signs
    if spec['reverse']:
        T, S = T[::-1].copy(), S[::-1].copy()
    yield 'adaln_t_table', T
    if 'rope.inv_freq' in header:
        # Nonpersistent in diffusers; the official checkpoint has no copy.
        # Same formula as the lane loader, NumPy F32 implementation hypothesis.
        freq_dim = header['rope.inv_freq']['shape'][0]
        freq = np.arange(0,2*freq_dim,2,dtype=np.float32)/(2*freq_dim)
        yield 'rope.inv_freq', np.float32(1.) / np.power(np.float32(10000.),freq)
    precision = spec['precision']
    # Solver-order hypotheses use a newly generated table and newly folded bias,
    # never the stored fitted table/bias as an oracle input.
    if spec['solver'] != 'svd':
        gram_inverse = np.linalg.inv((T.T @ T).astype(np.float64)).astype(np.float32)
        C = T @ gram_inverse
    for target in sorted(k[:-7] for k in header if k.endswith('.adaln_proj.linear.weight')):
        source = ('norm_out.linear' if target.startswith('final_layer.') else
                  target.replace('blocks.', 'transformer_blocks.', 1))
        bias = full.read(source+'.bias')[0]
        outw = np.empty((len(bias),rank),np.float16)
        outb = np.empty(len(bias),np.float16)
        for i in range(0,len(bias),chunk):
            j = min(len(bias),i+chunk)
            W = full.read(source+'.weight',i,j)[0]
            b = matmul(W,mean[:,None],precision)[:,0]+bias[i:j]
            outb[i:j] = b
            if spec['solver'] == 'svd':
                w = matmul(W,V,precision)
            else:
                M = matmul(W,S.T,precision)+bias[i:j,None]-outb[i:j,None].astype(np.float32)
                w = (matmul(M,C,precision) if spec['solver'] == 'normal-left' else
                     matmul(matmul(M,T,precision),gram_inverse,precision))
            outw[i:j] = w
        yield target+'.weight', outw
        yield target+'.bias', outb


def search_assembled(full, raw_header, output, specs, fitter, record, expected=HISTORICAL_SHA, chunk=1024):
    """All variants get full-file hashes. Never retain an unmatched candidate."""
    output = safe_path(output, writing=True)
    if output.exists():
        raise ValueError('Output exists; refusing overwrite')
    header, _ = layout(raw_header)
    plan = copy_plan(header, full)
    results = []
    with tempfile.TemporaryDirectory(prefix='h3-assemble-', dir=output.parent) as tmp:
        candidate = Path(tmp)/'candidate.safetensors'
        assemble_base(candidate,raw_header,full,plan,chunk)
        for spec in specs:
            item = dict(variant=spec, sha256=None, matched=False)
            try:
                write_fits(candidate,raw_header,fitter(full,header,spec,chunk))
                item.update(sha256=file_sha(candidate), size_bytes=candidate.stat().st_size)
                item['matched'] = item['sha256'] == expected
                if item['matched'] and not output.exists():
                    with candidate.open('rb') as src, output.open('xb') as dst:
                        shutil.copyfileobj(src,dst,4*1024**2)
                    if file_sha(output) != expected:
                        output.unlink()
                        raise ValueError('Retained output reread hash mismatch')
            except (ValueError, np.linalg.LinAlgError, FloatingPointError) as exc:
                item['error'] = f'{type(exc).__name__}: {exc}'
                item['matched'] = False
            results.append(item)
            record(results)
    return results


def run_assembly(args, receipt, output_receipt):
    global np
    import numpy as np
    if not args.output:
        raise ValueError('--assemble requires --output')
    raw = (HERE/'historical-layout.header').read_bytes()
    if sha(raw) != LAYOUT_SHA or layout(raw)[1] != HISTORICAL_BYTES:
        raise ValueError('Historical header identity mismatch')
    # Verify complete source bytes before trusting a shard name or tensor header.
    metadata = json.loads((HERE/'recovery-metadata.json').read_text())
    root = safe_path(args.full_dir)
    receipt['source_verification'] = []
    for entry in metadata['repositories'][0]['files']:
        name = entry['rfilename']
        if not (name.startswith('transformer/') and name.endswith('.safetensors')):
            continue
        path = safe_path(root/Path(name).name)
        digest = file_sha(path)
        if path.stat().st_size != entry['size'] or digest != entry['lfs']['sha256']:
            raise ValueError(f'Official input mismatch: {path.name}')
        receipt['source_verification'].append(dict(file=path.name,sha256=digest))
    receipt['official_file_hashes_verified'] = True
    full = Tensors(root)
    index = json.loads((HERE/'official-diffusion_pytorch_model.safetensors.index.json').read_text())
    if set(full.entries) != set(index['weight_map']):
        raise ValueError('Official tensor inventory mismatch')
    import io
    from contextlib import redirect_stdout
    config = io.StringIO()
    with redirect_stdout(config):
        np.show_config()
    receipt.update(environment={**receipt['environment'], 'numpy':np.__version__,
                                'numpy_config':config.getvalue()},
                   expected_sha256=HISTORICAL_SHA, layout_sha256=LAYOUT_SHA,
                   whole_denoiser_bit_exact=False, variants=[], verdict='searching')
    def record(results):
        receipt['variants'] = results
        output_receipt.write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    results = search_assembled(full,raw,args.output,variant_specs(args.search_precisions.split(',')),
                               fit_tensors,record,chunk=args.chunk)
    receipt['whole_denoiser_bit_exact'] = any(r['matched'] for r in results)
    receipt['search_complete'] = all(r['sha256'] is not None for r in results)
    receipt['variant_count'] = len(results)
    receipt['verdict'] = 'whole-denoiser-exact' if receipt['whole_denoiser_bit_exact'] else ('no-matching-variant' if receipt['search_complete'] else 'search-incomplete')
    receipt['outputs'] = [str(args.output)] if receipt['whole_denoiser_bit_exact'] else []

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--full-dir', required=True)
    ap.add_argument('--fitted', help='Required in comparison mode only')
    ap.add_argument('--assemble', action='store_true', help='Independent fit search and full-file hash gate')
    ap.add_argument('--output', type=Path, help='Retain only a historical full-file hash match')
    ap.add_argument('--search-precisions', default='f32,bf16-io,bf16-acc')
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
    if not args.assemble and not args.fitted:
        ap.error('--fitted is required unless --assemble is selected')
    if not set(args.search_precisions.split(',')) <= {'f32','bf16-io','bf16-acc','f64'}:
        ap.error('Unknown search precision')
    output = safe_path(args.receipt, writing=True)
    if args.output and safe_path(args.output, writing=True) == output:
        ap.error('Output and receipt must differ')
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
    receipt['arguments'] = {k: str(v) if isinstance(v,Path) else v for k,v in vars(args).items()}
    try:
        paths = [safe_path(args.full_dir)] + ([safe_path(args.fitted)] if not args.assemble else [])
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            receipt['missing_inputs'] = missing
        else:
            # 2 GiB address-space ceiling, including BLAS workspace; never whole denoiser.
            resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
            run_assembly(args,receipt,output) if args.assemble else run(args,receipt)
    except Exception as exc:
        receipt['verdict'] = 'error'
        receipt['error'] = f'{type(exc).__name__}: {exc}'
    receipt['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output.write_text(json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    print(receipt['verdict'])
    return 0 if receipt['verdict'] in ('adaln-exact-only','whole-denoiser-exact') else 2 if receipt['verdict'] in ('blocked','error') else 1


if __name__ == '__main__':
    sys.exit(main())
