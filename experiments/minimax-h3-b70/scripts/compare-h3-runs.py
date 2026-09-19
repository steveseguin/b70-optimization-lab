#!/usr/bin/env python3
"""Compare two MiniMax-H3 runs: the four receipt hashes, and then frame by frame.

`smoke_h3.sh repeat` already compares the four whole-tensor hashes in `receipt.json`
(`video_tensor_sha256`, `audio_tensor_sha256`, `video_latents_sha256`, `audio_latents_sha256`). That is the right gate
for a REPEAT, where the only acceptable answer is "bytewise-equal". It is the wrong instrument for an A/B between two
different denoisers, where the hashes are *expected* to differ and the question is how much and where.

So this adds the layer the smoke script lacks: it loads each run's `tensors.safetensors` (written by `--save-tensors`,
keys `video`, `audio`, `latents`, `audio_latents`) and reports, per video frame, the max and mean absolute difference,
the fraction of elements that differ at all, and a per-frame sha256 of each side. Audio and both latent tensors get
the same whole-tensor treatment.

Everything is done in float64 on the CPU, and no XPU is touched: this is safe to run at any time, including during a
GPU-fault halt.

    compare-h3-runs.py <run-a-dir> <run-b-dir> [--json OUT] [--max-frames N] [--quiet]

Exit code 0 if every video frame is bitwise identical, 1 otherwise -- so it can be used as a gate as well as a
measurement. A nonzero exit on a pruned-vs-int8 A/B is the expected outcome, not a failure; read the numbers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

HASH_KEYS = ('video_tensor_sha256', 'audio_tensor_sha256', 'video_latents_sha256', 'audio_latents_sha256')


def sha256_tensor(t):
    import torch
    return hashlib.sha256(t.detach().to('cpu').contiguous().flatten().view(torch.uint8).numpy().tobytes()).hexdigest()


def whole(name, a, b):
    import torch
    row = {'key': name, 'shape_a': list(a.shape), 'shape_b': list(b.shape),
           'dtype_a': str(a.dtype), 'dtype_b': str(b.dtype)}
    if a.shape != b.shape:
        row['verdict'] = 'SHAPE MISMATCH'
        return row
    da, db = a.to(torch.float64), b.to(torch.float64)
    diff = (da - db).abs()
    row.update(identical=bool(torch.equal(a, b)), max_abs_diff=float(diff.max()),
               mean_abs_diff=float(diff.mean()),
               differing_fraction=float((da != db).to(torch.float64).mean()))
    row['verdict'] = 'identical' if row['identical'] else 'differs'
    return row


def per_frame(va, vb, max_frames):
    """video tensors are [1, 3, T, H, W]; walk the T axis."""
    import torch
    if va.shape != vb.shape:
        return [], 'SHAPE MISMATCH'
    frames = va.shape[2] if va.dim() == 5 else va.shape[0]
    limit = frames if max_frames is None else min(frames, max_frames)
    rows = []
    for t in range(limit):
        fa = va[0, :, t] if va.dim() == 5 else va[t]
        fb = vb[0, :, t] if vb.dim() == 5 else vb[t]
        da, db = fa.to(torch.float64), fb.to(torch.float64)
        diff = (da - db).abs()
        rows.append({
            'frame': t,
            'identical': bool(torch.equal(fa, fb)),
            'max_abs_diff': float(diff.max()),
            'mean_abs_diff': float(diff.mean()),
            'differing_fraction': float((da != db).to(torch.float64).mean()),
            'sha256_a': sha256_tensor(fa),
            'sha256_b': sha256_tensor(fb),
        })
    return rows, ('all frames identical' if all(r['identical'] for r in rows)
                  else f"{sum(1 for r in rows if not r['identical'])}/{len(rows)} frames differ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run_a', type=Path, help='a run directory (the one holding receipt.json and tensors.safetensors)')
    ap.add_argument('run_b', type=Path)
    ap.add_argument('--json', type=Path, default=None, help='also write the full report here')
    ap.add_argument('--max-frames', type=int, default=None, help='stop after N frames (default: all)')
    ap.add_argument('--quiet', action='store_true', help='print the summary only, not every frame')
    args = ap.parse_args()

    import torch  # noqa: F401  (imported here so --help works without torch)
    from safetensors.torch import load_file

    report = {'run_a': str(args.run_a), 'run_b': str(args.run_b)}

    ra, rb = args.run_a / 'receipt.json', args.run_b / 'receipt.json'
    for path in (ra, rb):
        if not path.exists():
            sys.exit(f'missing {path}')
    a, b = json.loads(ra.read_text()), json.loads(rb.read_text())
    report['settings'] = {
        'a': {k: a['settings'].get(k) for k in ('denoiser', 'lora', 'seed', 'steps', 'height', 'width', 'frames',
                                                'prompt', 'denoiser_rotation', 'te_rotation')},
        'b': {k: b['settings'].get(k) for k in ('denoiser', 'lora', 'seed', 'steps', 'height', 'width', 'frames',
                                                'prompt', 'denoiser_rotation', 'te_rotation')},
    }
    report['settings']['differ'] = sorted(k for k in report['settings']['a']
                                          if report['settings']['a'][k] != report['settings']['b'][k])
    report['receipt_hashes'] = {k: {'a': a['hashes'].get(k), 'b': b['hashes'].get(k),
                                    'match': a['hashes'].get(k) == b['hashes'].get(k)} for k in HASH_KEYS}
    report['timings'] = {'a': a.get('timings_seconds'), 'b': b.get('timings_seconds')}
    # A `--decode-only` run carries the hashes of the run whose latents it decoded, so a two-card
    # or autocast decode can be checked against the ORIGINAL single-card clip even when the run it
    # is being compared with here is a different one.
    report['decode'] = {}
    for name, run in (('a', a), ('b', b)):
        placement = run.get('decode_placement') or {}
        row = {'vae_decode': placement.get('vae_decode'), 'vae_autocast': placement.get('vae_autocast'),
               'card': placement.get('card'), 'decode_video_seconds': (run.get('timings_seconds') or {}).get('decode.video')}
        only = run.get('decode_only')
        if only and only.get('source_hashes'):
            row['decode_only_source'] = only.get('source_run_name') or only.get('source_dir')
            row['vs_source'] = {k: {'match': run['hashes'].get(k) == only['source_hashes'].get(k),
                                    'source': only['source_hashes'].get(k)} for k in HASH_KEYS}
        report['decode'][name] = row

    print(f"run A  {args.run_a}   denoiser={report['settings']['a']['denoiser']}  seed={report['settings']['a']['seed']}"
          f"  steps={report['settings']['a']['steps']}")
    print(f"run B  {args.run_b}   denoiser={report['settings']['b']['denoiser']}  seed={report['settings']['b']['seed']}"
          f"  steps={report['settings']['b']['steps']}")
    if report['settings']['differ']:
        print(f"settings that differ: {', '.join(report['settings']['differ'])}")
    print()
    for key, row in report['receipt_hashes'].items():
        print(f"  {'MATCH   ' if row['match'] else 'DIFFERS '} {key}  {str(row['a'])[:16]}... / {str(row['b'])[:16]}...")
    print()
    for name in ('a', 'b'):
        row = report['decode'][name]
        secs = row['decode_video_seconds']
        print(f"run {name.upper()} decode: --vae-decode {row['vae_decode']} --vae-autocast {row['vae_autocast']}"
              f"  decode.video {secs if secs is None else f'{secs:.1f} s'}")
        if 'vs_source' in row:
            for key, cell in row['vs_source'].items():
                print(f"    {'MATCH   ' if cell['match'] else 'DIFFERS '} {key} vs {row['decode_only_source']}"
                      f"  {str(cell['source'])[:16]}...")
    print()

    ta, tb = args.run_a / 'tensors.safetensors', args.run_b / 'tensors.safetensors'
    if not (ta.exists() and tb.exists()):
        report['tensors'] = 'absent (both runs need --save-tensors); receipt hashes above are the whole comparison'
        print(report['tensors'])
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(report, indent=2) + '\n')
        return 0 if all(r['match'] for r in report['receipt_hashes'].values()) else 1

    A, B = load_file(str(ta)), load_file(str(tb))
    report['whole'] = [whole(k, A[k], B[k]) for k in ('video', 'audio', 'latents', 'audio_latents') if k in A and k in B]
    for row in report['whole']:
        print(f"  {row['key']:<14} {row['verdict']:<16} max|d|={row.get('max_abs_diff', float('nan')):.6g}  "
              f"mean|d|={row.get('mean_abs_diff', float('nan')):.6g}  "
              f"differing={row.get('differing_fraction', float('nan')):.4%}")
    print()

    rows, verdict = per_frame(A['video'], B['video'], args.max_frames)
    report['per_frame'] = rows
    report['per_frame_verdict'] = verdict
    if not args.quiet:
        print(f"{'frame':>6}  {'same':>5}  {'max|d|':>12}  {'mean|d|':>12}  {'differing':>10}  sha256 A / B")
        for r in rows:
            print(f"{r['frame']:>6}  {str(r['identical']):>5}  {r['max_abs_diff']:>12.6g}  {r['mean_abs_diff']:>12.6g}  "
                  f"{r['differing_fraction']:>9.4%}  {r['sha256_a'][:12]} / {r['sha256_b'][:12]}")
        print()
    worst = max(rows, key=lambda r: r['max_abs_diff']) if rows else None
    if worst:
        report['worst_frame'] = worst['frame']
        print(f"worst frame: {worst['frame']} (max|d| {worst['max_abs_diff']:.6g})")
    print(f"PER-FRAME VERDICT: {verdict}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + '\n')
        print(f"wrote {args.json}")
    return 0 if rows and all(r['identical'] for r in rows) else 1


if __name__ == '__main__':
    sys.exit(main())
