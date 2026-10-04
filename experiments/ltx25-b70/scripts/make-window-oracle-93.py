#!/usr/bin/env python3
"""Packets 93/93b part B2: the windowed identity's own oracle, from two oracle passes.

    make-window-oracle-93.py <pass1-throughput.json> <pass2-throughput.json> \
        --out <data dir> --run <server run dir> --manifest <packet manifest sha256>

Refuses (exit 10, nothing stored) unless ALL of these hold:
1. For each of the ten fixtures, each pass emitted a clip (first emitted row).
2. The two passes are distinct successful executions: different prefixes and
   request names, disjoint index ranges, different execution timestamps, every
   history a success, and the same server identity (pid, start ticks, boot) and
   the same packet manifest (the one given) for every request.
3. Every emitted clip's own encode receipt says the window was used: mode
   'pipeline-window', its window bucket (< 1024, recorded), its clip index, no
   capture during the encode.
4. Both passes' tensor files are loaded and re-hashed (each must equal its
   summary), and all four tensors are compared pass 1 vs pass 2 for layout and
   bytes.
Only then is pass 1 copied as a NEW reference set (output/validation and
requests 'stability-01-w93c-<fixture>'; existing references never touched)
and data/stability-01-window-prereg.json written.

window-oracle-vs-1024-oracle.json (the owner's first condition, recorded, no
threshold applied here): per fixture, against the certified 1024-encode clip
(pinned captures, data/decode-replica-probe-fixtures.json):
  images: PSNR dB, max and mean abs difference on the 0-255 scale, fraction of
          pixels (any channel) differing by more than 1/255;
  waveform: max and mean abs difference, SNR dB;
  latents: max and mean abs difference.

Window label: changes output at rounding level; owner approved 2026-10-04 on two
conditions (negligible finished-clip difference; new references, byte-identical
thereafter). No GPU: CPU tensors only.
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
NAMES = ('images', 'video_latent', 'audio_latent', 'waveform')
NEW_PREFIX = 'stability-01-w93c-'
LABEL = ('changes output at rounding level; owner approved 2026-10-04 on two conditions '
         '(negligible finished-clip difference; new references, byte-identical thereafter)')


class Refused(Exception):
    pass


def need(ok, message):
    if not ok:
        raise Refused(message)


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def tensor_sha(t):
    import torch
    return hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest()


def load_pass(path):
    tp = json.loads(Path(path).read_text())
    rows = {}
    for r in tp['rows']:
        if r.get('fill') or r.get('emitted_fixture') is None or r.get('emitted_index', -1) < 0:
            continue
        rows.setdefault(r['emitted_fixture'], r)
    return {'path': str(path), 'prefix': tp['prefix'], 'index_base': tp['index_base'], 'count': tp['count'],
            'names': [r['prompt'] for r in tp['rows']], 't_done': [r['t_done'] for r in tp['rows']],
            'rows': rows}


def identity_of(root, name):
    req = root / 'requests' / name
    ident = json.loads((req / 'identity.json').read_text())
    hist = json.loads((req / 'history.json').read_text())
    sub = json.loads((req / 'submission.json').read_text())
    need(hist.get('status', {}).get('status_str') == 'success', 'execution of %s did not succeed' % name)
    need(hist.get('prompt', [None, None])[1] == sub.get('prompt_id'), 'history/submission mismatch for ' + name)
    return {'pid': ident.get('pid'), 'proc_start_ticks': ident.get('proc_start_ticks'),
            'boot_id': ident.get('boot_id'), 'manifest': ident.get('source_packet_manifest_sha256'),
            'prompt_id': sub.get('prompt_id')}


def verify_executions(root, p1, p2, manifest):
    need(p1['prefix'] != p2['prefix'], 'both passes have the same prefix: one pass supplied twice?')
    need(not set(p1['names']) & set(p2['names']), 'the passes share request names')
    r1 = set(range(p1['index_base'], p1['index_base'] + p1['count']))
    r2 = set(range(p2['index_base'], p2['index_base'] + p2['count']))
    need(not r1 & r2, 'the passes share clip indices')
    need(not set(p1['t_done']) & set(p2['t_done']), 'the passes share execution timestamps')
    need(max(p1['t_done']) < min(p2['t_done']) or max(p2['t_done']) < min(p1['t_done']),
         'the passes overlap in time')
    server = None
    prompt_ids = set()
    for p in (p1, p2):
        for name in p['names']:
            ident = identity_of(root, name)
            key = (ident['pid'], ident['proc_start_ticks'], ident['boot_id'], ident['manifest'])
            need(ident['manifest'] == manifest, 'request %s ran another packet (%s)' % (name, ident['manifest']))
            server = server or key
            need(key == server, 'request %s ran on a different server identity' % name)
            need(ident['prompt_id'] not in prompt_ids, 'duplicate prompt id ' + str(ident['prompt_id']))
            prompt_ids.add(ident['prompt_id'])
    return {'pid': server[0], 'proc_start_ticks': server[1], 'boot_id': server[2], 'manifest': server[3]}


def verify_window_used(run, p):
    buckets = {}
    for fixture, row in sorted(p['rows'].items()):
        emitted = row['emitted_index']
        submitter = '%s-%02d' % (p['prefix'], emitted)
        rec_path = run / ('pipeline-' + submitter + '.json')
        need(rec_path.is_file(), 'no encode receipt for clip %d (%s)' % (emitted, submitter))
        rec = json.loads(rec_path.read_text())
        info = (rec.get('detail') or {}).get('window_encode') or {}
        need(rec.get('mode') == 'pipeline-window' and rec.get('passed') is True,
             'clip %s/%d was not encoded in window mode' % (p['prefix'], emitted))
        need(rec.get('clip_index') == p['index_base'] + emitted and info.get('clip_index') == rec.get('clip_index'),
             'window receipt of %s does not belong to its clip' % submitter)
        need(isinstance(info.get('window'), int) and info['window'] < 1024 and info.get('full_path') is False,
             'clip %s/%d did not use a window bucket (%r)' % (p['prefix'], emitted, info.get('window')))
        need(info.get('captured_graphs') == 0, 'clip %s/%d captured graphs during its encode' % (p['prefix'], emitted))
        buckets[fixture] = info['window']
    return buckets


def load_tensors(root, name):
    from safetensors.torch import load_file
    base = root / 'output/validation' / name
    meta = json.loads((base / 'summary.json').read_text())
    tensors = load_file(str(base / 'tensors.safetensors'))
    need(set(tensors) == set(NAMES) == set(meta['tensors']), 'unexpected tensor set in ' + name)
    for k in NAMES:
        need(tensor_sha(tensors[k]) == meta['tensors'][k]['sha256'], '%s/%s differs from its summary' % (name, k))
    return tensors


def compare_passes(root, p1, p2):
    import torch
    need(set(p1['rows']) == set(p2['rows']) and len(p1['rows']) == 10,
         'each pass must emit all ten fixtures: %s / %s' % (sorted(p1['rows']), sorted(p2['rows'])))
    shas = {}
    for fixture in sorted(p1['rows']):
        a = load_tensors(root, p1['rows'][fixture]['prompt'])
        b = load_tensors(root, p2['rows'][fixture]['prompt'])
        for k in NAMES:
            need(a[k].dtype == b[k].dtype and tuple(a[k].shape) == tuple(b[k].shape),
                 '%s/%s layout differs between passes' % (fixture, k))
            need(torch.equal(a[k].contiguous().view(torch.uint8), b[k].contiguous().view(torch.uint8)),
                 '%s/%s bytes differ between passes' % (fixture, k))
        shas[fixture] = {k: tensor_sha(a[k]) for k in NAMES}
    return shas


def finished_clip_comparison(new, old):
    import torch
    out = {}
    d = (new['images'].double() - old['images'].double()).abs()
    mse = float((d ** 2).mean())
    out['images'] = {'psnr_db': float('inf') if mse == 0 else 10.0 * math.log10(1.0 / mse),
                     'max_abs_255': float(d.max()) * 255.0, 'mean_abs_255': float(d.mean()) * 255.0,
                     'fraction_pixels_over_1_255': float((d > 1.0 / 255.0).any(dim=-1).double().mean()),
                     'bitwise_equal': bool(torch.equal(new['images'].view(torch.uint8), old['images'].view(torch.uint8)))}
    ref = old['waveform'].double()
    dw = (new['waveform'].double() - ref)
    noise = float((dw ** 2).sum())
    out['waveform'] = {'max_abs': float(dw.abs().max()), 'mean_abs': float(dw.abs().mean()),
                       'snr_db': float('inf') if noise == 0 else 10.0 * math.log10(float((ref ** 2).sum()) / noise)}
    for k in ('video_latent', 'audio_latent'):
        dl = (new[k].double() - old[k].double()).abs()
        out[k] = {'max_abs': float(dl.max()), 'mean_abs': float(dl.mean())}
    return out


def table(rows):
    lines = ['%-10s %8s %8s %8s %9s %9s %10s %10s %10s' % (
        'fixture', 'PSNR dB', 'max/255', 'mean/255', '>1/255', 'wav SNR', 'wav max', 'vlat max', 'alat max')]
    for r in rows:
        c = r['comparison']
        lines.append('%-10s %8.2f %8.2f %8.4f %9.5f %9.2f %10.2e %10.2e %10.2e' % (
            r['fixture'], c['images']['psnr_db'], c['images']['max_abs_255'], c['images']['mean_abs_255'],
            c['images']['fraction_pixels_over_1_255'], c['waveform']['snr_db'], c['waveform']['max_abs'],
            c['video_latent']['max_abs'], c['audio_latent']['max_abs']))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('pass1')
    ap.add_argument('pass2')
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--root', type=Path, default=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913'))
    ap.add_argument('--prereg-out', type=Path, default=LANE / 'data/stability-01-window-prereg.json')
    ap.add_argument('--fixtures', type=Path, default=LANE / 'data/stability-01-prereg.json')
    ap.add_argument('--certified', type=Path, default=LANE / 'data/decode-replica-probe-fixtures.json')
    a = ap.parse_args(argv)
    root = a.root
    assert not (root / 'FAULT.json').exists(), 'device fault recorded'
    a.out.mkdir(parents=True, exist_ok=True)
    report_path = a.out / 'window-oracle-vs-1024-oracle.json'
    assert not report_path.exists(), 'refuse to overwrite ' + str(report_path)
    report = {'schema': 'ltx.window-oracle-93c.v1', 'label': LABEL, 'accepted': False,
              'pass1': a.pass1, 'pass2': a.pass2}
    try:
        p1, p2 = load_pass(a.pass1), load_pass(a.pass2)
        report['pass1_prompts'] = {f: r['prompt'] for f, r in p1['rows'].items()}
        report['pass2_prompts'] = {f: r['prompt'] for f, r in p2['rows'].items()}
        report['server'] = verify_executions(root, p1, p2, a.manifest)
        report['window_buckets'] = {'pass1': verify_window_used(a.run, p1), 'pass2': verify_window_used(a.run, p2)}
        sha1 = compare_passes(root, p1, p2)
    except Refused as error:
        report['status'] = 'rejected: %s; nothing stored, the windowed arm is skipped' % error
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'accepted': False, 'reason': str(error)}))
        return 10
    fixtures = json.loads(a.fixtures.read_text())['fixtures']
    assert len(fixtures) == 10 and set(f['id'] for f in fixtures) == set(p1['rows'])
    for f in fixtures:
        new = NEW_PREFIX + f['id']
        src_name = p1['rows'][f['id']]['prompt']
        for sub in ('output/validation', 'requests'):
            src, dst = root / sub / src_name, root / sub / new
            assert not dst.exists(), 'refuse to overwrite ' + str(dst)
            shutil.copytree(src, dst, symlinks=False)
            for p in src.rglob('*'):
                if p.is_file():
                    assert sha_file(p) == sha_file(dst / p.relative_to(src)), 'copy differs: ' + str(p)
    prereg = {'campaign': 'stability-01-window-93c', 'label': LABEL,
              'source': 'packet 93c oracle pass 1 (%s), byte-identical to pass 2 (%s)' % (a.pass1, a.pass2),
              'fixtures': [{'id': f['id'], 'prompt': f['prompt'], 'seed': f['seed'],
                            'reference': NEW_PREFIX + f['id'], 'oracle_pass1_prompt': p1['rows'][f['id']]['prompt'],
                            'window': report['window_buckets']['pass1'][f['id']]} for f in fixtures]}
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
        for k in NAMES:
            assert tensor_sha(old[k]) == c['expected'][k], 'certified tensor changed: %s/%s' % (f['id'], k)
        new = load_tensors(root, NEW_PREFIX + f['id'])
        rows.append({'fixture': f['id'], 'window': report['window_buckets']['pass1'][f['id']],
                     'certified_capture': c['source'], 'comparison': finished_clip_comparison(new, old)})
    report.update({'accepted': True, 'status': 'accepted: new reference set stored',
                   'new_references': prereg['fixtures'], 'prereg': str(a.prereg_out), 'pass_sha256': sha1,
                   'finished_clip_comparison': rows, 'table': table(rows),
                   'definitions': {'psnr_db': 'images in [0, 1]: 10*log10(1/MSE)',
                                   'max_abs_255/mean_abs_255': 'image differences times 255',
                                   'fraction_pixels_over_1_255': 'share of pixels with any channel off by > 1/255',
                                   'snr_db': 'waveform: 10*log10(sum ref^2 / sum (new-ref)^2)',
                                   'reference': 'certified 1024-encode clip of the same fixture'},
                   'owner_condition': 'negligible finished-clip difference: recorded here, judged by the owner'})
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('\n'.join(report['table']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
