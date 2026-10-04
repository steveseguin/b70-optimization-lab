#!/usr/bin/env python3
"""Packet 93 part B2: the windowed identity's own oracle, from two oracle passes.

    make-window-oracle-93.py <pass1-throughput.json> <pass2-throughput.json> --out <data dir>

1. For each of the ten fixtures, the first clip each pass emitted for it.
2. Pass 1 and pass 2 must be byte-identical on all four tensors per fixture
   (ltx_text_window.judge_oracle_passes); otherwise the windowed identity is
   REJECTED (exit 10) and nothing is stored.
3. Accepted: pass 1 is copied as a NEW reference set next to the existing one
   (output/validation/stability-01-w93-<fixture> and requests/stability-01-w93-<fixture>;
   the existing stability-01-r01-* and other references are never touched), and
   data/stability-01-window-prereg.json points at it.
4. window-oracle-vs-1024-oracle.json: per fixture and tensor, max and mean
   absolute difference against the certified 1024-encode clip (the pinned
   f90c-endure captures of data/decode-replica-probe-fixtures.json, whose
   sha256s equal the existing references), and PSNR of the decoded images.

The window CHANGES OUTPUT AT ROUNDING LEVEL; owner decision pending.
No GPU: CPU tensors only (the same kind of process as compare-clip.py).
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
NAMES = ('images', 'video_latent', 'audio_latent', 'waveform')
NEW_PREFIX = 'stability-01-w93-'
LABEL = 'changes output at rounding level; owner decision pending'
sys.path.insert(0, str(LANE / 'scripts'))


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def first_rows(throughput):
    rows = {}
    for r in json.loads(Path(throughput).read_text())['rows']:
        if r.get('fill') or r.get('emitted_fixture') is None:
            continue
        rows.setdefault(r['emitted_fixture'], r['prompt'])
    return rows


def tensor_shas(name):
    meta = json.loads((ROOT / 'output/validation' / name / 'summary.json').read_text())
    return {k: meta['tensors'][k]['sha256'] for k in NAMES}


def main():
    import ltx_text_window as window
    ap = argparse.ArgumentParser()
    ap.add_argument('pass1')
    ap.add_argument('pass2')
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--prereg-out', type=Path, default=LANE / 'data/stability-01-window-prereg.json')
    ap.add_argument('--fixtures', type=Path, default=LANE / 'data/stability-01-prereg.json')
    ap.add_argument('--certified', type=Path, default=LANE / 'data/decode-replica-probe-fixtures.json')
    a = ap.parse_args()
    assert not (ROOT / 'FAULT.json').exists(), 'device fault recorded'
    a.out.mkdir(parents=True, exist_ok=True)
    report_path = a.out / 'window-oracle-vs-1024-oracle.json'
    assert not report_path.exists(), 'refuse to overwrite ' + str(report_path)
    p1, p2 = first_rows(a.pass1), first_rows(a.pass2)
    sha1 = {f: tensor_shas(n) for f, n in p1.items()}
    sha2 = {f: tensor_shas(n) for f, n in p2.items()}
    accepted, bad = window.judge_oracle_passes(sha1, sha2)
    report = {'schema': 'ltx.window-oracle-93.v1', 'label': LABEL, 'accepted': accepted,
              'pass1': a.pass1, 'pass2': a.pass2, 'pass1_prompts': p1, 'pass2_prompts': p2,
              'pass_mismatches': bad}
    if not accepted:
        report['status'] = 'rejected: the two oracle passes differ; the windowed arm is skipped'
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'accepted': False, 'mismatches': bad}))
        return 10
    fixtures = json.loads(a.fixtures.read_text())['fixtures']
    assert len(fixtures) == 10 and set(f['id'] for f in fixtures) == set(p1)
    for f in fixtures:
        new = NEW_PREFIX + f['id']
        for sub, src in (('output/validation', ROOT / 'output/validation' / p1[f['id']]),
                         ('requests', ROOT / 'requests' / p1[f['id']])):
            dst = ROOT / sub / new
            assert not dst.exists(), 'refuse to overwrite ' + str(dst)
            shutil.copytree(src, dst, symlinks=False)
            for p in src.rglob('*'):
                if p.is_file():
                    assert sha_file(p) == sha_file(dst / p.relative_to(src)), 'copy differs: ' + str(p)
        assert tensor_shas(new) == sha1[f['id']]
    prereg = {'campaign': 'stability-01-window-93', 'label': LABEL,
              'source': 'packet 93 oracle pass 1 (%s), byte-identical to pass 2 (%s)' % (a.pass1, a.pass2),
              'fixtures': [{'id': f['id'], 'prompt': f['prompt'], 'seed': f['seed'],
                            'reference': NEW_PREFIX + f['id'], 'oracle_pass1_prompt': p1[f['id']]}
                           for f in fixtures]}
    assert not a.prereg_out.exists(), 'refuse to overwrite ' + str(a.prereg_out)
    a.prereg_out.write_text(json.dumps(prereg, indent=2) + '\n')

    import torch
    from safetensors.torch import load_file
    certified = {r['fixture']: r for r in json.loads(a.certified.read_text())['fixtures']}
    rows = []
    for f in fixtures:
        c = certified[f['id']]
        assert sha_file(c['source']) == c['source_sha256'], 'certified capture changed: ' + c['source']
        old = load_file(c['source'])
        new = load_file(str(ROOT / 'output/validation' / (NEW_PREFIX + f['id']) / 'tensors.safetensors'))
        row = {'fixture': f['id'], 'certified_capture': c['source'], 'tensors': {}}
        for k in NAMES:
            assert hashlib.sha256(old[k].view(torch.uint8).numpy().tobytes()).hexdigest() == c['expected'][k]
            x, y = new[k].double(), old[k].double()
            d = (x - y).abs()
            entry = {'bitwise_equal': bool(torch.equal(new[k].view(torch.uint8), old[k].view(torch.uint8))),
                     'max_abs_diff': float(d.max()), 'mean_abs_diff': float(d.mean()),
                     'max_abs_reference': float(y.abs().max())}
            if k == 'images':
                mse = float((d ** 2).mean())
                entry['psnr_db'] = float('inf') if mse == 0 else 10.0 * math.log10(1.0 / mse)
            row['tensors'][k] = entry
        rows.append(row)
    report.update({'status': 'accepted: new reference set stored', 'new_references': prereg['fixtures'],
                   'prereg': str(a.prereg_out), 'versus_1024_oracle': rows,
                   'psnr_definition': 'images in [0, 1]; 10*log10(1/MSE) against the certified 1024-encode clip'})
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'accepted': True, 'psnr_db': {r['fixture']: round(r['tensors']['images']['psnr_db'], 2)
                                                     for r in rows}}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
