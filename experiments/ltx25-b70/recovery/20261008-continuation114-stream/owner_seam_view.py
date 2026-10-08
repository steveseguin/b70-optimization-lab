#!/usr/bin/env python3
"""Side-by-side seam clips for the owner look: two stream runs (e.g. 114 frame vs 114 latent, or 113 vs 114).

For each seam between stream chunk n and n+1 of both runs, cut the last SECONDS of chunk n and the first
SECONDS of chunk n+1 (dropping n+1's leading overlap frame, as the client does), join them, and stack
run A (left) and run B (right) into one MP4 with a 2-pixel gap. Also writes the full joined streams side by
side (`stream-side-by-side.mp4`) and a JSON index with each seam's border-to-centre chroma ratio.

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
STREAM = re.compile(r'receipt-(stream11[234]-s[0-9]{8})\.json')


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
        diag = (json.loads(decode.read_text()) if decode.exists() else receipt).get('anchor_diagnostics') or {}
        chunks.append({'name': name, 'mp4': str(mp4), 'skip': receipt['delivery']['drop_leading_frames'],
                       'frames': receipt['frames'], 'anchor': receipt.get('anchor', 'frame'),
                       'reset': receipt.get('reset', False), 'border_ratio': diag.get('border_to_centre_chroma_ratio')})
    return chunks


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
    (a.out / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    for p in work.iterdir():
        p.unlink()
    work.rmdir()
    print(json.dumps({'seams': len(index['seams']), 'out': str(a.out)}))


if __name__ == '__main__':
    main()
