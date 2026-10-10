#!/usr/bin/env python3
"""Side-by-side seam clips and the sharpness profile for the owner look: two stream runs (e.g. 116 mixed vs
116 guide, 114 latent vs 116 mixed, or 113 vs 116).

For each seam between stream chunk n and n+1 of both runs, cut the last SECONDS of chunk n and the first
SECONDS of chunk n+1 (dropping n+1's leading overlap frame, as the client does), join them, and stack
run A (left) and run B (right) into one MP4 with a 2-pixel gap. Also writes the full joined streams side by
side (`stream-side-by-side.mp4`) and a JSON index with each seam's border-to-centre chroma ratio.

Packet 116: also the per-chunk SHARPNESS PROFILE (variance of the 4-neighbour Laplacian of Rec.709 luma at
decoded frames 0, 1, 2, 5, 10, 24, the middle and the last, relative to the middle frame). A 116 decode
record carries it, computed by the server on the F32 frames; for 113/114 runs it is computed here from the
MP4 (8-bit, lossy: comparable within a source, labelled `source: mp4`). Written to `sharpness.json`, a
table (`sharpness.txt`, also printed) and a chart (`sharpness-profile.svg`: median relative sharpness per
frame index over the anchored chunks, left vs right). The 114 latent-anchor dip (frames 0-5 at 0.60-0.83
of mid-chunk) is the thing to look for.

CPU only: reads committed receipts and preview records of finished runs (113: receipts; 114: receipts plus
decode records), checks every MP4 against its record (bytes, SHA-256), and calls ffmpeg. It never talks to
a server. Video only (the chunk audio has no alignment rule yet).

    python3 -B owner_seam_view.py --left RUN_DIR_A --right RUN_DIR_B --out NEW_DIR [--seams 10] [--seconds 1.0]
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
STREAM = re.compile(r'receipt-(stream11[2345]-s[0-9]{8})\.json')
SHARP_FRAMES = (0, 1, 2, 5, 10, 24)


def sharp_frames(frames):
    return sorted({i for i in SHARP_FRAMES if i < frames} | {frames // 2, frames - 1})


def mp4_sharpness(mp4, frames):
    """Laplacian variance of the chosen frames, from the MP4 (8-bit RGB via ffmpeg)."""
    idx = sharp_frames(frames)
    raw = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(mp4), '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'], check=True, capture_output=True).stdout
    size = 256 * 256 * 3
    out = {}
    for i in idx:
        frame = raw[i * size:(i + 1) * size]
        if len(frame) < size:
            continue
        try:
            import numpy as np
            f = np.frombuffer(frame, dtype=np.uint8).reshape(256, 256, 3).astype(np.float64) / 255.0
            y = 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]
            lap = y[:-2, 1:-1] + y[2:, 1:-1] + y[1:-1, :-2] + y[1:-1, 2:] - 4.0 * y[1:-1, 1:-1]
            out[i] = float(lap.var())
        except ImportError:
            y = [(0.2126 * frame[k] + 0.7152 * frame[k + 1] + 0.0722 * frame[k + 2]) / 255.0 for k in range(0, size, 3)]
            vals = [y[r * 256 + c - 256] + y[r * 256 + c + 256] + y[r * 256 + c - 1] + y[r * 256 + c + 1] -
                    4.0 * y[r * 256 + c] for r in range(1, 255) for c in range(1, 255)]
            mean = sum(vals) / len(vals)
            out[i] = sum(v * v for v in vals) / len(vals) - mean * mean
    mid = out.get(frames // 2)
    return {'source': 'mp4', 'frames': idx, 'laplacian_variance': {str(k): v for k, v in out.items()},
            'reference_frame': frames // 2,
            'relative_to_reference': {str(k): (None if not mid else round(v / mid, 6)) for k, v in out.items()}}


def load_run(run, seams):
    run = Path(run)
    names = sorted(m.group(1) for p in (run / 'receipts').iterdir() if (m := STREAM.fullmatch(p.name)))
    chunks = []
    for name in names[:seams + 1]:
        receipt = json.loads((run / 'receipts' / ('receipt-' + name + '.json')).read_text())
        record = json.loads((run / 'receipts' / ('preview-' + name + '.json')).read_text())
        mp4 = Path(record['path'])
        raw = mp4.read_bytes()
        if len(raw) != record['bytes'] or hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise SystemExit('MP4 differs from its preview record: %s' % mp4)
        decode = run / 'receipts' / ('decode-' + name + '.json')
        drec = json.loads(decode.read_text()) if decode.exists() else None
        diag = (drec or receipt).get('anchor_diagnostics') or {}
        sharp = (drec or {}).get('sharpness')
        sharp = dict(sharp, source='decode record (F32)') if sharp else mp4_sharpness(mp4, receipt['frames'])
        chunks.append({'name': name, 'mp4': str(mp4), 'skip': receipt['delivery']['drop_leading_frames'],
                       'frames': receipt['frames'], 'anchor': receipt.get('anchor', 'frame'),
                       'reset': receipt.get('reset', False), 'border_ratio': diag.get('border_to_centre_chroma_ratio'),
                       'anchored': bool(receipt.get('anchored', receipt['chunk_index'] > 0)), 'sharpness': sharp})
    return chunks


def median(values):
    v = sorted(x for x in values if x is not None)
    return None if not v else (v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2)


def sharpness_summary(runs):
    """Median relative sharpness per frame index over the ANCHORED chunks of each run (the seam behaviour)."""
    out = {}
    for side, chunks in runs.items():
        anchored = [ch for ch in chunks if ch['anchored'] and not ch['reset']]
        idx = sorted({int(k) for ch in anchored for k in ch['sharpness']['relative_to_reference']})
        out[side] = {'anchor': chunks[0]['anchor'] if chunks else None, 'chunks': len(anchored),
                     'source': anchored[0]['sharpness']['source'] if anchored else None,
                     'median_relative': {str(i): median([ch['sharpness']['relative_to_reference'].get(str(i))
                                                          for ch in anchored]) for i in idx}}
    return out


def sharpness_table(summary):
    idx = sorted({int(k) for s in summary.values() for k in s['median_relative']})
    lines = ['frame  ' + '  '.join('%8s' % side for side in summary)]
    for i in idx:
        lines.append('%5d  ' % i + '  '.join('%8s' % ('-' if s['median_relative'].get(str(i)) is None else
                                                      '%.3f' % s['median_relative'][str(i)]) for s in summary.values()))
    lines.append('(median over anchored chunks, relative to the middle frame; sources: %s)'
                 % ', '.join('%s=%s %s' % (k, s['anchor'], s['source']) for k, s in summary.items()))
    return '\n'.join(lines) + '\n'


def sharpness_svg(summary):
    w, h, pad = 640, 320, 48
    idx = sorted({int(k) for s in summary.values() for k in s['median_relative']})
    if not idx:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="320"/>'
    xmax, ymax = max(idx) or 1, 1.3
    sx = lambda i: pad + (w - 2 * pad) * i / xmax
    sy = lambda v: h - pad - (h - 2 * pad) * min(v, ymax) / ymax
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" font-family="sans-serif" '
             'font-size="11"><rect width="100%%" height="100%%" fill="white"/>' % (w, h)]
    for v in (0.5, 1.0):
        parts.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#ccc"/><text x="4" y="%.1f">%.1f</text>'
                     % (pad, w - pad, sy(v), sy(v), sy(v) + 4, v))
    for i in idx:
        parts.append('<text x="%.1f" y="%d" text-anchor="middle">%d</text>' % (sx(i), h - pad + 16, i))
    for (side, s), color in zip(summary.items(), ('#1f77b4', '#d62728')):
        pts = [(sx(int(k)), sy(v)) for k, v in sorted(s['median_relative'].items(), key=lambda kv: int(kv[0]))
               if v is not None]
        parts.append('<polyline fill="none" stroke="%s" stroke-width="2" points="%s"/>'
                     % (color, ' '.join('%.1f,%.1f' % p for p in pts)))
        parts.append('<text x="%d" y="%d" fill="%s">%s: %s (%d chunks)</text>'
                     % (pad, 16 if side == 'left' else 30, color, side, s['anchor'], s['chunks']))
    parts.append('<text x="%d" y="%d" text-anchor="middle">decoded frame index (relative Laplacian variance, '
                 'median of anchored chunks)</text></svg>' % (w // 2, h - 8))
    return ''.join(parts)


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args], check=True)


def piece(chunk, out, head, seconds, fps=24):
    """head=False: last `seconds` of the chunk; head=True: first `seconds` after its dropped frames."""
    n = int(round(seconds * fps))
    if head:
        start, end = chunk['skip'], chunk['skip'] + n
    else:
        start, end = max(chunk['skip'], chunk['frames'] - n), chunk['frames']
    ffmpeg('-i', chunk['mp4'], '-vf', 'select=between(n\\,%d\\,%d),setpts=N/%d/TB' % (start, end - 1, fps),
           '-an', '-r', str(fps), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '12', str(out))


def join(parts, out):
    listing = Path(str(out) + '.txt')
    listing.write_text(''.join("file '%s'\n" % p for p in parts))
    ffmpeg('-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'copy', str(out))
    listing.unlink()


def stack(left, right, out):
    ffmpeg('-i', str(left), '-i', str(right), '-filter_complex',
           '[0:v]pad=iw+2:ih:0:0:black[l];[l][1:v]hstack=inputs=2', '-an', '-c:v', 'libx264',
           '-pix_fmt', 'yuv420p', '-crf', '12', str(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--left', required=True)
    ap.add_argument('--right', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--seams', type=int, default=10)
    ap.add_argument('--seconds', type=float, default=1.0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    work = a.out / 'work'
    work.mkdir()
    runs = {'left': load_run(a.left, a.seams), 'right': load_run(a.right, a.seams)}
    count = min(len(runs['left']), len(runs['right'])) - 1
    index = {'left': str(a.left), 'right': str(a.right), 'seconds': a.seconds, 'seams': []}
    for k in range(count):
        sides = {}
        for side, chunks in runs.items():
            tail, head = work / ('%s-%02d-tail.mp4' % (side, k)), work / ('%s-%02d-head.mp4' % (side, k))
            piece(chunks[k], tail, False, a.seconds)
            piece(chunks[k + 1], head, True, a.seconds)
            sides[side] = work / ('%s-%02d-seam.mp4' % (side, k))
            join([tail, head], sides[side])
        clip = a.out / ('seam-%02d.mp4' % k)
        stack(sides['left'], sides['right'], clip)
        index['seams'].append({'clip': clip.name,
                               **{side: {'from': runs[side][k]['name'], 'to': runs[side][k + 1]['name'],
                                         'anchor': runs[side][k + 1]['anchor'], 'reset': runs[side][k + 1]['reset'],
                                         'border_ratio_before': runs[side][k]['border_ratio'],
                                         'border_ratio_after': runs[side][k + 1]['border_ratio']}
                                  for side in runs}})
    whole = {}
    for side, chunks in runs.items():
        parts = []
        for k, chunk in enumerate(chunks[:count + 1]):
            part = work / ('%s-%02d-all.mp4' % (side, k))
            piece(dict(chunk), part, True, (chunk['frames'] - chunk['skip']) / 24.0)
            parts.append(part)
        whole[side] = work / ('%s-stream.mp4' % side)
        join(parts, whole[side])
    stack(whole['left'], whole['right'], a.out / 'stream-side-by-side.mp4')
    summary = sharpness_summary(runs)
    index['sharpness'] = summary
    (a.out / 'sharpness.json').write_text(json.dumps({side: [{'name': ch['name'], 'anchored': ch['anchored'],
                                                              'reset': ch['reset'], 'sharpness': ch['sharpness']}
                                                             for ch in chunks] for side, chunks in runs.items()},
                                                     indent=1) + '\n')
    table = sharpness_table(summary)
    (a.out / 'sharpness.txt').write_text(table)
    (a.out / 'sharpness-profile.svg').write_text(sharpness_svg(summary))
    print(table, end='')
    (a.out / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    for p in work.iterdir():
        p.unlink()
    work.rmdir()
    print(json.dumps({'seams': len(index['seams']), 'out': str(a.out)}))


if __name__ == '__main__':
    main()
