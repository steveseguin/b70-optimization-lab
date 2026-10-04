#!/usr/bin/env python3
"""CPU-only tests for packet 93b's runner tools, on a synthetic results root in a
temporary directory (nothing under /mnt is written; no GPU, no server).

1. make-window-oracle-93.py: two distinct window passes are accepted, the new
   references are copied, and the finished-clip comparison holds every required
   number; the same pass supplied twice, a differing tensor, a tensor file that
   disagrees with its summary, a non-window execution, another server identity
   and another packet manifest are each refused with nothing stored.
2. missing-markers-93b.py: expects only jobs the server actually queued for
   prompts the client actually submitted.
3. summarize-campaign-93.py: the context-sentry gate passes on equal hashes for
   all ten fixtures and fails (non-zero) on a missing fixture, a null hash or a
   differing hash.
"""
import importlib.util
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
LANE = HERE.parent
import torch  # noqa: E402  (CPU only)
from safetensors.torch import save_file  # noqa: E402

FIXTURES = [f['id'] for f in json.loads((LANE / 'data/stability-01-prereg.json').read_text())['fixtures']]
MANIFEST = 'a' * 64
results = []


def case(name, fn):
    try:
        fn()
        results.append((name, True, ''))
    except Exception as error:  # noqa: BLE001
        import traceback
        results.append((name, False, repr(error) + ' ' + ' | '.join(traceback.format_exc().splitlines()[-3:])))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ORACLE = module(HERE / 'make-window-oracle-93.py', 'oracle93b')
MARKERS = module(HERE / 'missing-markers-93b.py', 'markers93b')
SUMMARY = module(HERE / 'summarize-campaign-93.py', 'summary93b')


def clip_tensors(fixture_i, delta=0.0):
    g = torch.Generator().manual_seed(fixture_i)
    return {'images': (torch.rand(2, 8, 8, 3, generator=g) + delta).clamp(0, 1),
            'video_latent': torch.randn(1, 4, 2, 2, 2, generator=g) + delta,
            'audio_latent': torch.randn(1, 4, 3, 2, generator=g) + delta,
            'waveform': torch.randn(1, 2, 64, generator=g) * 0.1 + delta}


def write_clip(root, name, tensors, summary_override=None):
    base = root / 'output/validation' / name
    base.mkdir(parents=True)
    save_file({k: v.contiguous() for k, v in tensors.items()}, str(base / 'tensors.safetensors'))
    meta = {'tensors': {k: {'sha256': ORACLE.tensor_sha(v)} for k, v in tensors.items()},
            'deterministic_enabled': True, 'deterministic_warn_only': False, 'sample_rate': 48000}
    if summary_override:
        meta['tensors'].update(summary_override)
    (base / 'summary.json').write_text(json.dumps(meta))


def write_pass(root, run, out, prefix, base, t0, fills=3, mode='pipeline-window', server=None,
               manifest=MANIFEST, tamper=None, window=64):
    server = server or {'pid': 1234, 'proc_start_ticks': '99', 'boot_id': 'boot-x'}
    rows = []
    count = 10 + fills
    for i in range(count):
        name = '%s-%02d' % (prefix, i)
        req = root / 'requests' / name
        req.mkdir(parents=True)
        pid = 'pid-%s' % name
        (req / 'identity.json').write_text(json.dumps({**server, 'source_packet_manifest_sha256': manifest}))
        (req / 'submission.json').write_text(json.dumps({'prompt_id': pid}))
        (req / 'history.json').write_text(json.dumps({'prompt': [0, pid, {}], 'status': {'status_str': 'success'}}))
        (req / 'result.json').write_text(json.dumps({'prompt_id': pid}))
        (req / 'prompt.json').write_text('{}')
        # encode receipt of the prompt that SUBMITTED clip i
        (run / ('pipeline-%s.json' % name)).write_text(json.dumps({
            'mode': mode, 'passed': True, 'clip_index': base + i,
            'detail': {'window_encode': {'window': window if mode == 'pipeline-window' else None,
                                         'full_path': mode != 'pipeline-window', 'clip_index': base + i,
                                         'captured_graphs': 0}}}))
        emitted = i - fills
        if emitted < 0:
            rows.append({'prompt': name, 'index': i, 'emitted_index': -1, 'emitted_fixture': None, 'fill': True,
                         't_done': t0 + i})
            continue
        fx = FIXTURES[emitted % 10]
        tensors = clip_tensors(FIXTURES.index(fx), 1e-3)
        override = None
        if tamper and tamper[0] == fx:
            if tamper[1] == 'bytes':
                tensors['waveform'] = tensors['waveform'].clone()
                tensors['waveform'].view(torch.int32)[0, 0, 0] ^= 1
            elif tamper[1] == 'summary':
                override = {'images': {'sha256': '0' * 64}}
        write_clip(root, name, tensors, override)
        rows.append({'prompt': name, 'index': i, 'emitted_index': emitted, 'emitted_fixture': fx, 'fill': False,
                     't_done': t0 + i, 'reference': 'x', 'exact': False})
    path = out / ('%s-throughput.json' % prefix)
    path.write_text(json.dumps({'prefix': prefix, 'index_base': base, 'count': count, 'rows': rows,
                                'intervals_between_distinct_clips_s': [1.0] * 9}))
    return path


def make_root(tmp):
    root, run, out = tmp / 'R', tmp / 'R/encoder-server-x', tmp / 'out'
    for p in (root, run, out):
        p.mkdir(parents=True, exist_ok=True)
    cert_rows = []
    for i, fx in enumerate(FIXTURES):
        t = clip_tensors(i)
        src = tmp / 'cert' / fx / 'tensors.safetensors'
        src.parent.mkdir(parents=True)
        save_file(t, str(src))
        cert_rows.append({'fixture': fx, 'source': str(src), 'source_sha256': ORACLE.sha_file(src),
                          'expected': {k: ORACLE.tensor_sha(v) for k, v in t.items()}})
    cert = tmp / 'cert.json'
    cert.write_text(json.dumps({'fixtures': cert_rows}))
    return root, run, out, cert


def run_oracle(tmp, root, run, out, cert, p1, p2, manifest=MANIFEST):
    prereg = tmp / 'prereg.json'
    if prereg.exists():
        prereg.unlink()
    rep = out / 'window-oracle-vs-1024-oracle.json'
    if rep.exists():
        rep.unlink()
    rc = ORACLE.main([str(p1), str(p2), '--out', str(out), '--run', str(run), '--manifest', manifest,
                      '--root', str(root), '--prereg-out', str(prereg), '--certified', str(cert)])
    return rc, json.loads(rep.read_text()), prereg


def oracle_accept_case():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        root, run, out, cert = make_root(tmp)
        p1 = write_pass(root, run, out, 'or1', 1000, 100.0)
        p2 = write_pass(root, run, out, 'or2', 1200, 200.0)
        rc, rep, prereg = run_oracle(tmp, root, run, out, cert, p1, p2)
        assert rc == 0 and rep['accepted'] is True, rep.get('status')
        assert rep['window_buckets']['pass1'] == {fx: 64 for fx in FIXTURES}
        assert all((root / 'output/validation' / ('stability-01-w93b-' + fx) / 'tensors.safetensors').is_file()
                   for fx in FIXTURES)
        refs = json.loads(prereg.read_text())['fixtures']
        assert [r['reference'] for r in refs] == ['stability-01-w93b-' + fx for fx in FIXTURES]
        row = rep['finished_clip_comparison'][0]['comparison']
        for k in ('psnr_db', 'max_abs_255', 'mean_abs_255', 'fraction_pixels_over_1_255'):
            assert isinstance(row['images'][k], float), k
        for k in ('max_abs', 'mean_abs', 'snr_db'):
            assert isinstance(row['waveform'][k], float), k
        for lat in ('video_latent', 'audio_latent'):
            assert set(row[lat]) == {'max_abs', 'mean_abs'}
        assert abs(row['waveform']['max_abs'] - 1e-3) < 1e-5 and math.isfinite(row['images']['psnr_db'])
        assert len(rep['table']) == 11 and 'PSNR' in rep['table'][0]


case('oracle: two distinct window passes accepted; references copied; finished-clip numbers recorded',
     oracle_accept_case)


def oracle_refusal_case():
    cases = {
        'same pass twice': dict(same=True),
        'differing tensor': dict(p2=dict(tamper=('bird', 'bytes'))),
        'file vs summary': dict(p1=dict(tamper=('rain', 'summary'))),
        'non-window execution': dict(p2=dict(mode='pipeline')),
        'other server': dict(p2=dict(server={'pid': 999, 'proc_start_ticks': '1', 'boot_id': 'boot-x'})),
        'other manifest': dict(p2=dict(manifest='b' * 64)),
        'full-path bucket': dict(p1=dict(window=1024)),
    }
    expect = {'same pass twice': 'same prefix', 'differing tensor': 'bytes differ',
              'file vs summary': 'differs from its summary', 'non-window execution': 'not encoded in window mode',
              'other server': 'different server identity', 'other manifest': 'another packet',
              'full-path bucket': 'did not use a window bucket'}
    for label, spec in cases.items():
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            root, run, out, cert = make_root(tmp)
            p1 = write_pass(root, run, out, 'or1', 1000, 100.0, **spec.get('p1', {}))
            p2 = p1 if spec.get('same') else write_pass(root, run, out, 'or2', 1200, 200.0, **spec.get('p2', {}))
            rc, rep, prereg = run_oracle(tmp, root, run, out, cert, p1, p2)
            assert rc == 10 and rep['accepted'] is False, (label, rep.get('status'))
            assert expect[label] in rep['status'], (label, rep['status'])
            assert not prereg.exists() and not list((root / 'output/validation').glob('stability-01-w93b-*')), label


case('oracle: identical pass, differing tensor, bad file, non-window, other server/manifest refused',
     oracle_refusal_case)


def markers_case():
    with tempfile.TemporaryDirectory() as t:
        root, run = Path(t) / 'R', Path(t) / 'R/run'
        run.mkdir(parents=True)
        for i in range(5):                                  # 5 requested, 3 actually submitted
            req = root / 'requests' / ('arm-%02d' % i)
            req.mkdir(parents=True)
            if i < 3:
                (req / 'submission.json').write_text('{}')
        for i in range(3):
            name = 'arm-%02d' % i
            (run / ('pipeline-sampler-%s.json' % name)).write_text(json.dumps(
                {'clip_index': 500 + i, 'detail': {'emitted_index': -1 if i < 2 else 500}}))
            dec = {'clip_index': 500 if i == 2 else -1, 'upstream_depth': 0,
                   'detail': ({'saved_file': 'queued:x'} if i == 2 else {'emitted_index': -1, 'upstream_fill': True})}
            (run / ('pipeline-decode-%s.json' % name)).write_text(json.dumps(dec))
        missing = lambda: [l for l in MARKERS.expected(root, run, ['arm'])
                           if not (run / ('pipeline-done-%s.json' % l)).is_file()]
        assert sorted(missing()) == ['decode-500', 'sample-500', 'sample-501', 'sample-502'], missing()
        for m in ('sample-500', 'sample-501', 'sample-502', 'decode-500'):
            (run / ('pipeline-done-%s.json' % m)).write_text('{}')
        assert missing() == ['save-500'], missing()
        (run / 'pipeline-done-save-500.json').write_text('{}')
        assert missing() == []
        # a prompt that failed before its sampler queued anything expects nothing
        (run / 'pipeline-sampler-arm-01.json').write_text(json.dumps({'clip_index': 501, 'passed': False}))
        (run / 'pipeline-done-sample-501.json').unlink()
        assert missing() == []


case('markers: only jobs actually submitted and queued are awaited', markers_case)


def sentry_gate_case():
    def arm(hashes):
        return {'present': True, 'context_sentries': hashes}
    good = {fx: [['a-' + fx, 'b-' + fx]] for fx in FIXTURES}
    assert SUMMARY.compare_sentries(arm(good), arm(json.loads(json.dumps(good))), FIXTURES)['passed'] is True
    miss = {k: v for k, v in good.items() if k != 'rain'}
    r = SUMMARY.compare_sentries(arm(good), arm(miss), FIXTURES)
    assert r['passed'] is False and any('rain' in p for p in r['problems'])
    null = dict(good); null['bird'] = [['a-bird', None]]
    assert SUMMARY.compare_sentries(arm(null), arm(null), FIXTURES)['passed'] is False
    diff = dict(good); diff['boat'] = [['a-boat', 'other']]
    assert SUMMARY.compare_sentries(arm(good), arm(diff), FIXTURES)['passed'] is False
    two = dict(good); two['paper'] = [['a-paper', 'b-paper'], ['x', 'y']]
    assert SUMMARY.compare_sentries(arm(two), arm(two), FIXTURES)['passed'] is False
    # end to end: main() returns non-zero when the gate fails
    with tempfile.TemporaryDirectory() as t:
        out, run = Path(t) / 'out', Path(t) / 'run'
        out.mkdir(); run.mkdir()
        for prefix, base, sab in (('ctl', 100, ('A', 'B')), ('lean', 300, ('A', 'X'))):
            rows = []
            for i in range(12):
                name = '%s-%02d' % (prefix, i)
                rows.append({'prompt': name, 'index': i, 't_done': base + i, 'fill': i < 2,
                             'reference': None if i < 2 else 'r', 'exact': True})
                if i >= 2:
                    (run / ('pipeline-sampler-%s.json' % name)).write_text(json.dumps({'detail': {
                        'emitted_index': base + i - 2, 'stage_seconds': 1.0,
                        'emitted_context_sentry': {'stage_a_context_sha256': sab[0] + str(i % 10),
                                                   'stage_b_context_sha256': sab[1] + str(i % 10)}}}))
            (out / ('%s-throughput.json' % prefix)).write_text(json.dumps({
                'rows': rows, 'index_base': base, 'all_exact': True, 'intervals_between_distinct_clips_s': [1.0] * 9}))
        argv = sys.argv
        sys.argv = ['x', '--run', str(run), '--out', str(out), '--arm', 'ctl:control', '--arm', 'lean:lean',
                    '--pair', 'ctl:lean']
        try:
            rc = SUMMARY.main()
        finally:
            sys.argv = argv
        s = json.loads((out / 'summary.json').read_text())
        assert rc != 0 and s['context_sentry_gate_passed'] is False, (rc, s['context_sentry_pairs'])


case('summary: context-sentry gate (ten fixtures, non-null, equal) fails the campaign otherwise', sentry_gate_case)

for name, ok, err in results:
    print(f'{"ok " if ok else "BAD"} {name}{"" if ok else "  " + err}')
print('ALL CASES AS EXPECTED:', all(ok for _, ok, _ in results))
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
