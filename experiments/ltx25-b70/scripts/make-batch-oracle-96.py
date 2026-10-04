#!/usr/bin/env python3
"""Packet 96: store the batch-B reference set from the reference arm.

    make-batch-oracle-96.py <ref-throughput.json> --batch B --run <server run dir> \
        --manifest <packet manifest sha256> --out <data dir>

The reference arm (run-throughput-fixtures-96.py --order ref --no-oracle) samples the
ten fixtures on a batch-B server in one fixed arrangement, one job at a time. This
script refuses (exit 10, nothing stored) unless ALL of these hold:

1. Every fixture was emitted, every emitted clip came from a batch job of exactly B
   rows on this server (sampler receipts: sampler_batch == B, the job's row list has B
   entries), and its slot and neighbours are recorded.
2. Every request ran on one server identity (pid, start ticks, boot) with the given
   packet manifest, and succeeded.
3. Every emitted clip's own encode receipt shows the window encoder (mode
   pipeline-window, a window bucket < 1024, no capture during the encode).
4. Tensor files load and re-hash to their summaries.
5. A fixture emitted twice (the batch-4 arrangement repeats fixtures 0 and 1 in other
   slots with other neighbours) is byte-identical on all four tensors.

Then the first emitted clip of each fixture is copied as a NEW reference
'stability-01-b<B>-<fixture>' (output/validation and requests; existing files are
never touched) and data/stability-01-batch<B>-prereg.json is written, recording each
reference's arrangement (job, slot, neighbour fixtures).

Closeness report (recorded, not a gate): batch<B>-reference-vs-w93c.json, per fixture
against the w93c reference of the same fixture: images PSNR, waveform SNR and PSNR,
latent max/mean differences. Batched clips are "the same mathematics, different
rounding"; this shows how different the take is. No GPU: CPU tensors only.
"""
import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LANE / 'scripts'))
import ltx_sampler_batch as batching  # noqa: E402
NAMES = ('images', 'video_latent', 'audio_latent', 'waveform')
LABEL = ('batch-B sampler: the same arithmetic at a different batch size; changes output at rounding level '
         'versus batch 1 (GEMM rounding depends on the row count); adoption is the owner\'s decision')


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


def load_json(path):
    return json.loads(Path(path).read_text())


def emitted_rows(tp):
    """fixture -> [rows in emission order] (pipeline fills excluded)."""
    out = {}
    for r in tp['rows']:
        if r.get('emitted_index', -1) < 0 or r.get('emitted_fixture') is None or r.get('fill'):
            continue
        out.setdefault(r['emitted_fixture'], []).append(r)
    return out


def check_sequence(tp, batch, fixture_ids):
    """Review finding 3: the reference arm must emit exactly the 'ref' arrangement: clips
    0..K-1 in prompt order (K = len(ORDERS[B]['ref'])), each once, each the fixture the
    order assigns, so every intended repeat is present."""
    ref = batching.ORDERS[batch]['ref']
    emitted = [r for r in tp['rows'] if r.get('emitted_index', -1) >= 0]
    need([r['emitted_index'] for r in emitted] == list(range(len(ref))),
         'reference arm emitted clips %s, expected 0..%d in order' % ([r['emitted_index'] for r in emitted],
                                                                   len(ref) - 1))
    for r in emitted:
        need(not r.get('duplicate') and r.get('emitted_fixture') == fixture_ids[ref[r['emitted_index']]],
             '%s: clip %d is %r, the ref order says %r' % (r['prompt'], r['emitted_index'], r.get('emitted_fixture'),
                                                           fixture_ids[ref[r['emitted_index']]]))
        info = r.get('batch') or {}
        rows = info.get('rows') or []
        slot = info.get('slot')
        need(isinstance(slot, int) and 0 <= slot < len(rows) and rows[slot] == tp['index_base'] + r['emitted_index'],
             '%s: batch provenance does not name clip %d at its slot' % (r['prompt'], r['emitted_index']))
    return {fixture_ids[k]: ref.count(k) for k in set(ref)}


def check_arrangement(run, tp, rows_by_fixture, batch):
    arrangement = {}
    for fixture, rows in sorted(rows_by_fixture.items()):
        for r in rows:
            info = r.get('batch') or {}
            need(info.get('batch') == batch and isinstance(info.get('slot'), int) and
                 isinstance(info.get('rows'), list) and len(info['rows']) == batch,
                 '%s (%s) did not come from a batch-%d job: %r' % (r['prompt'], fixture, batch, info))
            smp = load_json(run / ('pipeline-sampler-' + r['prompt'] + '.json'))
            need(smp.get('sampler_batch') == batch and smp.get('passed') is True,
                 'sampler receipt of %s is not a passed batch-%d receipt' % (r['prompt'], batch))
        first = rows[0]['batch']
        arrangement[fixture] = {'job': first['job'], 'slot': first['slot'],
                                'neighbour_fixtures': first['neighbour_fixtures'],
                                'fill_slots': first['fill_slots'],
                                'occurrences': [{'prompt': r['prompt'], 'slot': r['batch']['slot'],
                                                 'neighbour_fixtures': r['batch']['neighbour_fixtures']}
                                                for r in rows]}
    return arrangement


def verify_server(root, names, manifest):
    server = None
    seen = set()
    for name in names:
        req = root / 'requests' / name
        ident = load_json(req / 'identity.json')
        hist = load_json(req / 'history.json')
        sub = load_json(req / 'submission.json')
        need(hist.get('status', {}).get('status_str') == 'success', 'execution of %s did not succeed' % name)
        need(hist.get('prompt', [None, None])[1] == sub.get('prompt_id'), 'history/submission mismatch for ' + name)
        need(ident.get('source_packet_manifest_sha256') == manifest, '%s ran another packet' % name)
        key = (ident.get('pid'), ident.get('proc_start_ticks'), ident.get('boot_id'))
        server = server or key
        need(key == server, '%s ran on a different server identity' % name)
        need(sub.get('prompt_id') not in seen, 'duplicate prompt id for ' + name)
        seen.add(sub.get('prompt_id'))
    return {'pid': server[0], 'proc_start_ticks': server[1], 'boot_id': server[2], 'manifest': manifest}


def verify_window(run, tp, rows_by_fixture):
    buckets = {}
    for fixture, rows in sorted(rows_by_fixture.items()):
        for r in rows:
            submitter = '%s-%02d' % (tp['prefix'], r['emitted_index'])
            rec = load_json(run / ('pipeline-' + submitter + '.json'))
            info = (rec.get('detail') or {}).get('window_encode') or {}
            need(rec.get('mode') == 'pipeline-window' and rec.get('passed') is True,
                 'clip %s was not encoded in window mode' % submitter)
            need(rec.get('clip_index') == tp['index_base'] + r['emitted_index'] and
                 info.get('clip_index') == rec.get('clip_index'), 'window receipt of %s does not belong to it' % submitter)
            need(isinstance(info.get('window'), int) and info['window'] < 1024 and info.get('full_path') is False,
                 '%s did not use a window bucket' % submitter)
            need(info.get('captured_graphs') == 0, '%s captured graphs during its encode' % submitter)
            buckets.setdefault(fixture, info['window'])
    return buckets


def load_tensors(root, name):
    from safetensors.torch import load_file
    base = root / 'output/validation' / name
    meta = load_json(base / 'summary.json')
    tensors = load_file(str(base / 'tensors.safetensors'))
    need(set(tensors) == set(NAMES) == set(meta['tensors']), 'unexpected tensor set in ' + name)
    for k in NAMES:
        need(tensor_sha(tensors[k]) == meta['tensors'][k]['sha256'], '%s/%s differs from its summary' % (name, k))
    return tensors


def compare_repeats(root, rows_by_fixture):
    import torch
    shas, repeats = {}, {}
    for fixture, rows in sorted(rows_by_fixture.items()):
        first = load_tensors(root, rows[0]['prompt'])
        for other in rows[1:]:
            t = load_tensors(root, other['prompt'])
            for k in NAMES:
                need(t[k].dtype == first[k].dtype and tuple(t[k].shape) == tuple(first[k].shape) and
                     torch.equal(t[k].contiguous().view(torch.uint8), first[k].contiguous().view(torch.uint8)),
                     '%s/%s differs between its two arrangements (%s slot %s vs %s slot %s)'
                     % (fixture, k, rows[0]['prompt'], rows[0]['batch']['slot'], other['prompt'], other['batch']['slot']))
            repeats.setdefault(fixture, []).append(other['prompt'])
        shas[fixture] = {k: tensor_sha(first[k]) for k in NAMES}
    return shas, repeats


def closeness(new, old):
    import torch
    out = {}
    d = (new['images'].double() - old['images'].double()).abs()
    mse = float((d ** 2).mean())
    out['images'] = {'psnr_db': float('inf') if mse == 0 else 10.0 * math.log10(1.0 / mse),
                     'max_abs_255': float(d.max()) * 255.0, 'mean_abs_255': float(d.mean()) * 255.0,
                     'fraction_pixels_over_1_255': float((d > 1.0 / 255.0).any(dim=-1).double().mean()),
                     'bitwise_equal': bool(torch.equal(new['images'].contiguous().view(torch.uint8),
                                                       old['images'].contiguous().view(torch.uint8)))}
    ref = old['waveform'].double()
    dw = new['waveform'].double() - ref
    noise = float((dw ** 2).sum())
    wmse = float((dw ** 2).mean())
    out['waveform'] = {'snr_db': float('inf') if noise == 0 else 10.0 * math.log10(float((ref ** 2).sum()) / noise),
                       'psnr_db': float('inf') if wmse == 0 else 10.0 * math.log10(1.0 / wmse),
                       'max_abs': float(dw.abs().max()), 'mean_abs': float(dw.abs().mean())}
    for k in ('video_latent', 'audio_latent'):
        dl = (new[k].double() - old[k].double()).abs()
        out[k] = {'max_abs': float(dl.max()), 'mean_abs': float(dl.mean())}
    return out


def table(rows):
    lines = ['%-10s %5s %9s %9s %10s %10s %10s %10s' % ('fixture', 'slot', 'img PSNR', 'max/255', 'wav SNR',
                                                         'wav PSNR', 'vlat max', 'alat max')]
    for r in rows:
        c = r['comparison']
        lines.append('%-10s %5s %9.2f %9.2f %10.2f %10.2f %10.2e %10.2e' % (
            r['fixture'], r['slot'], c['images']['psnr_db'], c['images']['max_abs_255'], c['waveform']['snr_db'],
            c['waveform']['psnr_db'], c['video_latent']['max_abs'], c['audio_latent']['max_abs']))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('reference_arm')
    ap.add_argument('--batch', type=int, required=True, choices=(2, 4))
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--root', type=Path, default=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913'))
    ap.add_argument('--fixtures', type=Path, default=LANE / 'data/stability-01-window-prereg.json',
                    help='prompts/seeds and the w93c references (closeness report only)')
    ap.add_argument('--prereg-out', type=Path, default=None)
    a = ap.parse_args(argv)
    root, batch = a.root, a.batch
    prefix = 'stability-01-b%d-' % batch
    prereg_out = a.prereg_out or (LANE / ('data/stability-01-batch%d-prereg.json' % batch))
    assert not (root / 'FAULT.json').exists(), 'device fault recorded'
    a.out.mkdir(parents=True, exist_ok=True)
    report_path = a.out / ('batch%d-reference-vs-w93c.json' % batch)
    assert not report_path.exists(), 'refuse to overwrite ' + str(report_path)
    report = {'schema': 'ltx.batch-oracle-96.v1', 'label': LABEL, 'batch': batch, 'accepted': False,
              'reference_arm': a.reference_arm}
    fixtures = load_json(a.fixtures)['fixtures']
    try:
        tp = load_json(a.reference_arm)
        need(tp.get('batch') == batch and tp.get('order') == 'ref', 'not a batch-%d reference-arm pass' % batch)
        counts = check_sequence(tp, batch, [f['id'] for f in fixtures])
        rows_by_fixture = emitted_rows(tp)
        need({f: len(v) for f, v in rows_by_fixture.items()} == counts,
             'occurrences per fixture %s, the ref order needs %s' % (
                 {f: len(v) for f, v in rows_by_fixture.items()}, counts))
        need(set(rows_by_fixture) == {f['id'] for f in fixtures},
             'the reference arm must emit all ten fixtures: %s' % sorted(rows_by_fixture))
        report['arrangement'] = check_arrangement(a.run, tp, rows_by_fixture, batch)
        report['server'] = verify_server(root, [r['prompt'] for r in tp['rows']], a.manifest)
        report['window_buckets'] = verify_window(a.run, tp, rows_by_fixture)
        shas, repeats = compare_repeats(root, rows_by_fixture)
        report['repeats_byte_identical'] = repeats
        for f in fixtures:
            for sub in ('output/validation', 'requests'):
                need(not (root / sub / (prefix + f['id'])).exists(), 'reference %s%s already exists' % (prefix, f['id']))
        need(not prereg_out.exists(), 'prereg %s already exists' % prereg_out)
    except Refused as error:
        report['status'] = 'rejected: %s; nothing stored' % error
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'accepted': False, 'reason': str(error)}))
        return 10
    for f in fixtures:
        src_name = rows_by_fixture[f['id']][0]['prompt']
        for sub in ('output/validation', 'requests'):
            src, dst = root / sub / src_name, root / sub / (prefix + f['id'])
            shutil.copytree(src, dst, symlinks=False)
            for p in src.rglob('*'):
                if p.is_file():
                    assert sha_file(p) == sha_file(dst / p.relative_to(src)), 'copy differs: ' + str(p)
    prereg = {'campaign': 'stability-01-batch%d-96' % batch, 'label': LABEL, 'batch': batch,
              'source': 'packet 96 reference arm %s (one job at a time, order ref)' % a.reference_arm,
              'server': report['server'],
              'fixtures': [{'id': f['id'], 'prompt': f['prompt'], 'seed': f['seed'], 'reference': prefix + f['id'],
                            'reference_prompt': rows_by_fixture[f['id']][0]['prompt'],
                            'window': report['window_buckets'][f['id']],
                            'arrangement': report['arrangement'][f['id']],
                            'tensor_sha256': shas[f['id']]} for f in fixtures]}
    prereg_out.write_text(json.dumps(prereg, indent=2) + '\n')

    rows = []
    for f in fixtures:
        new = load_tensors(root, prefix + f['id'])
        old_name = f.get('reference')
        cmp = None
        if old_name and (root / 'output/validation' / old_name / 'tensors.safetensors').is_file():
            cmp = closeness(new, load_tensors(root, old_name))
        rows.append({'fixture': f['id'], 'slot': report['arrangement'][f['id']]['slot'],
                     'against': old_name, 'comparison': cmp})
    report.update({'accepted': True, 'status': 'accepted: batch-%d reference set stored' % batch,
                   'prereg': str(prereg_out), 'new_references': [prefix + f['id'] for f in fixtures],
                   'closeness_vs_w93c': rows,
                   'table': table([r for r in rows if r['comparison'] is not None]),
                   'definitions': {'images psnr_db': 'images in [0, 1]: 10*log10(1/MSE)',
                                   'waveform snr_db': '10*log10(sum ref^2 / sum (new-ref)^2)',
                                   'waveform psnr_db': 'peak 1.0: 10*log10(1/MSE)',
                                   'against': 'the w93c (batch-1, window encoder) reference of the same fixture'},
                   'gate': 'none: recorded for the owner (a different take, not a failure)'})
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('\n'.join(report['table']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
