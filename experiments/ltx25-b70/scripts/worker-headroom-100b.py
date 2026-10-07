#!/usr/bin/env python3
"""CPU-only 20/28 admission; hash-bound qualified99b freeze, never old-layout aliasing.

--control-basis JSON and --control-basis-sha256 bind actual freeze/identity/summary
receipts. Plan debits card1 by 3*.97+.25 GiB, gives card0 no credit, and requires
all cards >=2 GiB plus retained card2 replica probe room. Estimates are not
reservations or proof: actual100 live checks and the real freeze remain required.
Live uses the conservative private-pool worker cost for20/28, never a23/25
calibration. Calibration is recorded only for this named layout; not used here.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
LANE = Path('/home/steve/llm-optimizations/experiments/ltx25-b70')
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
LAYOUT = 'two-way20-28'
CARDS = ('xpu:0', 'xpu:1', 'xpu:2', 'xpu:3')
GIB = 2**30
DEBIT_GIB = 3 * .97 + .25
OLD_SHA = '8dee8c4748a026ce1f4d1125ca50b67431a1d44921d33121addf6a4aa7d37944'
CONTROL_MANIFEST = 'f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a'
W93C_PREREG = LANE / 'data/stability-01-window-prereg.json'
W93C_PREREG_SHA = '9c188d9b96805ec1cfc3e6c694f952550ebfd8166a9a11c23044cb14834abb17'


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def regular(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe receipt path')
    st = path.stat()
    require(stat.S_ISREG(st.st_mode) and st.st_size <= 16 * 1024**2, 'Nonregular/oversized receipt')
    raw = path.read_bytes()
    after = path.stat()
    require((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Receipt changed while reading')
    return raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bound(path, digest):
    require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'Expected SHA256 required')
    raw = regular(path)
    require(sha(raw) == digest, 'Receipt hash differs: ' + str(path))
    def pairs(rows):
        d = {}
        for k, v in rows:
            require(k not in d, 'Duplicate JSON key'); d[k] = v
        return d
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def free_values(receipt):
    d = receipt.get('free_bytes')
    require(isinstance(d, dict) and set(d) == set(CARDS) and
            all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 64 * GIB for v in d.values()),
            'Complete finite four-card free bytes required')
    return d


def validate_compat_identity(identity):
    """Bind the actual compatibility receipt to the immutable99b installer."""
    parent = bound(ROOT / 'prepared-encoder-upstream-99b/manifest.json', CONTROL_MANIFEST)
    require(identity.get('runtime99b_transition') == parent['rope99b'], 'Control99b compatibility transition differs')
    r = identity.get('rope_compatibility', {})
    files = parent['rope99b']['installer']['files']
    expected = {
        'schema': 'ltx.rope-arithmetic-compat.v1', 'status': 'installed-unqualified',
        'installer_sha256': files['install_rope_compat.py'],
        'source_path': '/home/steve/ltx25-upstream99-dependencies/site-packages/comfy_kitchen/backends/eager/rope.py',
        'original_source_sha256': files['source-evidence/rope-0.2.37.py'],
        'restored_source_sha256': files['source-evidence/rope-0.2.33.py'],
        'function': 'apply_rope_split_half1', 'backend': 'eager',
        'package_files_changed': False, 'gpu_parity_qualified': False,
    }
    require(all(r.get(k) == v and type(r.get(k)) is type(v) for k, v in expected.items()),
            'Control99b RoPE compatibility receipt missing/different')
    require(all(isinstance(r.get(k), str) and re.fullmatch('[0-9a-f]{64}', r[k])
                for k in ('before_code_sha256', 'after_code_sha256')) and
            r['before_code_sha256'] != r['after_code_sha256'], 'RoPE code identity absent/unchanged')


def validate_control_basis(path, expected_sha256):
    b = bound(path, expected_sha256)
    require(b.get('schema') == 'ltx.rebalance100.control-basis.v1', 'Control basis schema differs')
    manifest = b.get('packet_manifest_sha256')
    require(manifest == CONTROL_MANIFEST, 'Exact reviewed control99b manifest required')
    rows = {k: bound(b[k]['path'], b[k]['sha256']) for k in ('freeze', 'identity', 'summary')}
    f, identity, summary = (rows[k] for k in ('freeze', 'identity', 'summary'))
    require(identity.get('source_packet_manifest_sha256') == manifest and
            identity.get('source_packet_path') == str(ROOT / 'prepared-encoder-upstream-99b'), 'Control99b packet differs')
    require(identity.get('runtime99_transition', {}).get('control') == {
        'layout': 'two-way', 'blocks': [23, 25], 'workers': 2, 'batch': 1, 'shared_pool': 1,
        'decode_replica': 'xpu:2', 'size': '256x256', 'references': 'w93c'}, 'Control99b configuration differs')
    validate_compat_identity(identity)
    run = identity.get('encoder_run_dir', '')
    require(re.fullmatch(re.escape(str(ROOT)) + r'/encoder-server-upstream-99b-two-way-w2-b1-p1-dxpu2-s256x256(?:-r[2-5])?', run),
            'Unexpected control run')
    require(f.get('server_identity_sha256') == b['identity']['sha256'] and
            f.get('schema') == 'ltx.sampler-capture-freeze.v2' and f.get('outcome') == 'frozen' and
            f.get('frozen') is True and f.get('loads_frozen') is True and f.get('placement') == 'two-way' and
            f.get('output_size') == '256x256' and f.get('sampler_batch') == 1 and
            f.get('sampler_workers') == 2 and f.get('sampler_shared_pool') == 1 and
            f.get('floor_bytes') == 2 * GIB and f.get('residents_missing') == [] and
            f.get('decode_replica', {}).get('replica_devices') == ['xpu:2'], 'Control99b freeze incomplete/different')
    cov, chain = f.get('coverage', {}), f.get('chain_check', {})
    require(cov.get('incomplete_routes') == [] and cov.get('routes') == 48 and cov.get('workers') == 2 and
            cov.get('signatures_per_route_min') == 2 and chain.get('chains_checked') == 4 and
            chain.get('chains_passed') == 4 and chain.get('shared_pool') == 1, 'Incomplete control capture/chain')
    cr = chain.get('rows', [])
    require(len(cr) == 4, 'Control chain rows missing')
    for card, blocks in [('xpu:0', list(range(23))), ('xpu:1', list(range(23, 48)))]:
        matched = [r for r in cr if r.get('device') == card]
        require(len(matched) == 2 and all(r.get('blocks') == blocks and r.get('passed') is True and
                r.get('replay_equals_eager') == [True, True] and r.get('replay_equals_repeat') == [True, True]
                for r in matched), 'Control chain ownership or parity differs')
    require(summary.get('run') == run and summary.get('batch') == 1 and summary.get('missing_or_failed') == [] and
            summary.get('context_sentry_gate_passed') is True, 'Control summary incomplete/failed')
    prereg = bound(W93C_PREREG, W93C_PREREG_SHA)
    references = sorted(row['reference'] for row in prereg['fixtures'])
    require(len(references) == len(set(references)) == 10, 'Pinned w93c fixture inventory differs')
    arms = list(summary.get('arms', {}).values())
    for label, count, clips in [('placement-probe', 13, 10), ('timed', 120, 116)]:
        matches = [a for a in arms if a.get('label') == label]
        require(len(matches) == 1, 'Control qualification arm missing/ambiguous')
        a = matches[0]
        require(a.get('present') is True and a.get('batch') == 1 and a.get('all_exact') is True and
                a.get('prompts') == count and a.get('clips_emitted') == clips and
                a.get('clips_verified') == clips and a.get('exact') == clips and
                a.get('references_checked_against') == 'references:w93c' and
                a.get('comparison') == 'references:w93c' and a.get('speed_only') is False and
                a.get('output_size') == '256x256' and a.get('shape_problems') == [] and
                a.get('emission_sequence_ok') is True and a.get('references') == references,
                'Control qualification requires complete accepted-w93c exact arms')
    free = free_values(f)
    require(all(v >= 2 * GIB for v in free.values()), 'Control freeze below floor')
    prediction = {c: free[c] / GIB - (DEBIT_GIB if c == 'xpu:1' else 0) for c in CARDS}
    return {'basis_sha256': expected_sha256, 'control_manifest_sha256': manifest,
            'reference_preregistration': {'path': str(W93C_PREREG), 'sha256': W93C_PREREG_SHA},
            'receipts': {k: b[k] for k in rows}, 'freeze_free_gib': {c: free[c] / GIB for c in CARDS},
            'card1_charge_gib': DEBIT_GIB, 'card0_credit_gib': 0,
            'predicted_free_gib_all_workers': prediction,
            'admitted': all(v >= 2 for v in prediction.values()) and prediction['xpu:2'] >= 4.51,
            'limits': 'Conservative estimate, not a bound/reservation; actual100 live and freeze required'}


def legacy():
    p = LANE / 'scripts/worker-headroom-98.py'
    require(sha(regular(p)) == OLD_SHA, 'Historical CPU helper changed')
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location('rebalance100_headroom98', p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    m.LAYOUTS[LAYOUT] = dict(zip(CARDS, (20, 28, 0, 0)))
    return m


def validate_live(path, identity_path, manifest):
    raw = regular(identity_path); identity = json.loads(raw)
    require(identity.get('source_packet_manifest_sha256') == manifest and
            identity.get('source_packet_path') == str(ROOT / 'prepared-encoder-rebalance-100b') and
            re.fullmatch(re.escape(str(ROOT)) + r'/encoder-server-rebalance-100b-two-way20-28-w2-b1-p1-dxpu2-s256x256(?:-r[2-5])?', identity.get('encoder_run_dir', '')),
            'Actual100 server identity required')
    validate_compat_identity(identity)
    r = json.loads(regular(path))
    require(r.get('server_identity_sha256') == sha(raw) and r.get('output_size') == '256x256' and
            r.get('sampler_batch') == 1 and r.get('sampler_workers') == 2 and r.get('sampler_shared_pool') == 1,
            'Actual100 coverage identity differs')
    free_values(r)
    return r


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('plan', 'live', 'calibrate')); p.add_argument('values', nargs='+')
    p.add_argument('--manifest', required=True); p.add_argument('--size', default='256x256')
    p.add_argument('--replicas', default='xpu:2'); p.add_argument('--calibration-root')
    p.add_argument('--control-basis', type=Path); p.add_argument('--control-basis-sha256')
    p.add_argument('--server-identity', type=Path); p.add_argument('--out')
    a = p.parse_args(argv)
    require(re.fullmatch('[0-9a-f]{64}', a.manifest) and a.size == '256x256' and a.replicas == 'xpu:2', 'Narrow100 identity differs')
    v = a.values
    if a.command == 'plan':
        require(v == [LAYOUT, '2', '1', '1'], 'Only20/28 W2B1 shared pool admitted')
        require(a.control_basis is not None, 'Qualified99 basis required')
        d = validate_control_basis(a.control_basis, a.control_basis_sha256)
        print(json.dumps(dict(d, layout=LAYOUT, workers=2, batch=1, shared_pool=1,
                             output_size='256x256', room_for_first_worker=d['admitted'])))
        return 0 if d['admitted'] else 18
    require(a.server_identity is not None, 'Actual100 server identity required')
    m = legacy()
    if a.command == 'live':
        require(len(v) in (4, 5) and v[1:4] == [LAYOUT, '1', '1'], 'Unexpected live configuration')
        r = validate_live(v[0], a.server_identity, a.manifest)
        if len(v) == 5:
            prev = validate_live(v[4], a.server_identity, a.manifest)
            require(m._finite(prev.get('time')) and m._finite(r.get('time')) and prev['time'] < r['time'], 'Coverage time order differs')
        # No optimistic pooled measurement credit: private-pool charge20/28.
        ok, short = m.live(r['free_bytes'], LAYOUT, 1, pool=0, spec='xpu:2')
        print(json.dumps({'room_for_one_more_worker': ok, 'layout': LAYOUT, 'short': short,
                          'basis': '20/28 private-pool conservative worker charge; actual100 coverage',
                          'needed_gib': m.needed(LAYOUT, 1, pool=0, spec='xpu:2')}))
        return 0 if ok else 18
    require(len(v) == 5 and v[2:] == [LAYOUT, '1', '1'] and a.out, 'Unexpected calibration configuration')
    for name in v[:2]:
        validate_live(name, a.server_identity, a.manifest)
    return m.main(['headroom100', 'calibrate', *v, '--size', a.size, '--manifest', a.manifest, '--out', a.out])


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        print(json.dumps({'status': 'refused', 'error': str(error)}))
        sys.exit(18)
