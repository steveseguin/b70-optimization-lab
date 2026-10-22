#!/usr/bin/env python3
"""Packet184 final checks; --ready writes READY-FOR-DEVICE.json last, then re-runs the pin guard.

Default (verification only):
  * the CPU seal verifies and every sealed gate receipt passed with unchanged sources;
  * key results: build (0 warnings, 78 parent objects relinked, parent reproduction), checkpoint CPU
    gate (4 lifecycle points, 2 appends + chains + empty delta, coverage == inventory on both ranks,
    draft-necessity control, >= 20 refusals, locks), production shape (fresh captures == parent on both
    ranks, coverage == inventory, resume and append restores with capture == fresh and a real half step),
    worker rehearsal (2 + 3 legs, 6 report negatives, real device request row);
  * package-rows / check-queue-rows receipts passed; the proposal equals its sealed mirror;
  * drain-fix scan: UNFIXED copies only in the vendored historical v4-lanes tree, and an import trace
    of the real entry (checkpoint_job.py --plan) loads only the packet's FIXED drain code.
--ready: READY-FOR-DEVICE.json (with a `checks` path->sha256 map so the pin guard walks every
  receipt), then the live pin guard (check_job on both rows) and a direct classification of every pin
  in the closure; any cross-packet mutable pin withdraws READY.
Writes v5/evidence/final-checks.json and, with --ready, v5/evidence/final-pin-guard.json.
"""
import argparse, datetime, hashlib, importlib.util, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V5 = HERE / 'v5'
EV = V5 / 'evidence'
LQ = HERE.parents[1] / 'ops/lane-queue'
NAME = 'proposed-p184-two-card-B.txt'
SEALED = ('build', 'native-delta', 'checkpoint-cpu', 'production-shape', 'worker-rehearsal', 'safety', 'exec-limits', 'admission')
READY_GATES = ('check-queue-rows', 'queue-plan', 'pin-guard')
EXTRA = ('package-rows',)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(name):
    return json.loads((EV / (name + '.json')).read_text())


def rel(p):
    return str(Path(p).relative_to(ROOT))


def drain_scan():
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/check_drain_fix.py'), str(HERE)], cwd=ROOT, stdin=subprocess.DEVNULL,
                       capture_output=True, text=True, timeout=300)
    rows = [l.split(None, 1) for l in r.stdout.splitlines() if l.startswith(('FIXED', 'UNFIXED'))]
    unfixed = [p for k, p in rows if k == 'UNFIXED']
    vendored = [p for p in unfixed if '/lineage-inputs/vendor/repo/experiments/own-xpu-runtime/stage2/screen/v4-lanes/' in p]
    assert unfixed == vendored, 'UNFIXED drain copy outside the vendored historical v4-lanes tree: ' + str(sorted(set(unfixed) - set(vendored)))
    code = ('import sys,runpy,json\nsys.path.insert(0,%r)\nsys.argv=["checkpoint_job.py","--kind","lifecycle","--lane","B","--output",%r,"--plan"]\n'
            'rc=None\ntry: runpy.run_path(%r,run_name="__main__")\nexcept SystemExit as e: rc=e.code\n'
            'mods=sorted({getattr(m,"__file__","") or "" for m in list(sys.modules.values())})\n'
            'sys.stderr.write("TRACE="+json.dumps(dict(rc=rc,mods=[m for m in mods if "drain" in m or "conditions" in m or "v4-lanes" in m]))+"\\n")\n') % (
        str(V5), str(EV / 'import-trace-plan-out'), str(V5 / 'checkpoint_job.py'))
    t = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
    trace = json.loads(next(l[6:] for l in t.stderr.splitlines() if l.startswith('TRACE=')))
    assert trace['rc'] in (0, None), trace
    loaded = trace['mods']
    assert loaded and all(m.startswith(str(V5)) for m in loaded) and not any('v4-lanes' in m for m in loaded), loaded
    return dict(scan_rc=r.returncode, fixed=[p for k, p in rows if k == 'FIXED'], unfixed_vendored_historical=vendored,
                entry_plan_import_trace=dict(rc=trace['rc'], drain_and_condition_modules=[rel(m) for m in loaded]))


def verify():
    sys.path.insert(0, str(V5))
    from cpu_seal import verify as seal_verify, check_sources
    seal = seal_verify()
    out = {}
    for name in SEALED + READY_GATES + EXTRA:
        row = load(name)
        assert row['passed'] is True and row['device_executed'] is False, name
        if row.get('sources'):
            check_sources(row['sources'])
        out[name] = sha(EV / (name + '.json'))
    b = load('build')
    assert b['warnings'] == 0 and b['relinked_parent_objects'] == 78 and b['parent_reproduction']['passed']
    c = load('checkpoint-cpu')
    assert len(c['lifecycle']) == 4 and len(c['append']) == 2 and len(c['coverage']) == 2 and len(c['refusals']) >= 20
    assert all(r['uploads'] == 0 for r in c['refusals']) and c['draft']['target_blobs_equal'] and c['draft']['draft_blobs_differing_after_resume']
    s = load('production-shape')
    assert all(s['fresh'][r]['equal_to_parent'] for r in ('0', '1')) and set(s['restore']) == {'resume', 'append'}
    assert all(s['restore'][k][r]['continue']['half_launches_issued'] > 0 for k in ('resume', 'append') for r in ('0', '1'))
    w = load('worker-rehearsal')
    assert w['smoke']['legs'] == 2 and w['lifecycle']['legs'] == 3 and len(w['negatives']) == 6
    q = load('check-queue-rows')
    live, mirror = LQ / NAME, HERE / 'proposals' / NAME
    assert sha(live) == sha(mirror) == load('package-rows')['proposal_sha256'] == load('queue-plan')['sha256']
    drain = drain_scan()
    pauses = sorted(p.name for p in LQ.glob('PAUSE-*'))
    queues = sorted(p.name for p in LQ.glob('queue-*.txt'))
    row = dict(passed=True, device_executed=False, queued=False, cpu_seal_sha256=sha(V5 / 'cpu-seal.json'), binary_sha256=seal['binary_sha256'],
               gnu_host_sha256=seal['gnu_host_sha256'], tool_sha256=seal['tool_sha256'], receipts=out, drain=drain,
               entry_rehearsal_passed=next(s_['passed'] for s_ in q['steps'] if s_['step'].startswith('ops/rehearse_entry')),
               save_bytes_production_shape=s['checkpoint']['save_bytes'],
               lane_state_observed=dict(pause_files=pauses, queue_files=queues, note='observed only; never written by preparation'),
               proposal=rel(live), proposal_sha256=sha(live))
    (EV / 'final-checks.json').write_text(json.dumps(row, indent=1) + '\n')
    return row


def pin_guard():
    spec = importlib.util.spec_from_file_location('p184_pin_guard_live', LQ / 'pin_guard.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rows = [json.loads(l) for l in (LQ / NAME).read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
    checks = [m.check_job(r) for r in rows]
    assert all(c['passed'] for c in checks)
    pins, manifests = m.collect_pins(HERE)
    oracle = {(p, h) for p, h, s in pins if s.name == 'oracle-binding.json'}
    classes, cross = {}, []
    for p, h, s in pins:
        if p.is_relative_to(HERE) and p.resolve().is_relative_to(HERE.resolve()):
            key = 'packet-private'
        else:
            reason = m.immutable_reason(p, h, HERE, oracle, m.STAGE)
            key = reason or 'CROSS-PACKET MUTABLE'
            if not reason:
                cross.append(str(p))
        classes[key] = classes.get(key, 0) + 1
    return dict(check_job=[dict(job=r['name'], passed=c['passed'], pins=c.get('pins')) for r, c in zip(rows, checks)],
                collected_pins=len(pins), manifests=len(manifests), ready_in_closure=any(Path(x).name == 'READY-FOR-DEVICE.json' for x in manifests),
                classes=classes, cross_packet_mutable_pins=len(cross), cross_examples=cross[:10])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ready', action='store_true')
    a = ap.parse_args()
    ready = HERE / 'READY-FOR-DEVICE.json'
    if a.ready and ready.exists():
        sys.exit('READY-FOR-DEVICE.json already exists; withdraw it first')
    row = verify()
    print('final checks PASS: seal', row['cpu_seal_sha256'][:16], 'binary', row['binary_sha256'][:16])
    if not a.ready:
        return
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    checks = {rel(EV / (n + '.json')): sha(EV / (n + '.json')) for n in SEALED + READY_GATES + EXTRA + ('final-checks',)}
    checks[rel(V5 / 'cpu-seal.json')] = sha(V5 / 'cpu-seal.json')
    marker = dict(schema='packet184.ready-for-device.v1', commit=commit, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  passed=True, ready_for_device=True, device_executed=False, queued=False, lane='B', arithmetic='iq3-p49-split32-v1',
                  label='experimental-two-card', contract='v1.2+p184', cpu_seal_sha256=sha(V5 / 'cpu-seal.json'),
                  cpu_gate_sha256={n: sha(EV / (n + '.json')) for n in READY_GATES + ('final-checks',)},
                  proposal_sha256s={rel(LQ / NAME): sha(LQ / NAME)}, checks=checks,
                  device_quality_pending=True, checkpoint_qualification_pending=True, binary_sha256=row['binary_sha256'],
                  operations=['save', 'same-generation-resume', 'append', 'restore-then-save', 'inspect', 'inspect-metadata', 'delete'],
                  admission='smoke first (2 fresh pairs: oracle-128 anchor, merged K+M == uninterrupted reference); lifecycle depends on the smoke',
                  last_packet_write=True)
    ready.write_text(json.dumps(marker, indent=2) + '\n')
    try:
        g = pin_guard()
        assert g['cross_packet_mutable_pins'] == 0 and g['ready_in_closure'], g
    except BaseException as e:
        withdrawn = EV / f'withdrawn-ready-{int(time.time())}.json'
        ready.rename(withdrawn)
        (EV / 'final-pin-guard.json').write_text(json.dumps(dict(passed=False, error=repr(e)[:4000], withdrawn=rel(withdrawn)), indent=1) + '\n')
        sys.exit('READY withdrawn: ' + repr(e)[:400])
    (EV / 'final-pin-guard.json').write_text(json.dumps(dict(passed=True, device_executed=False, ready_sha256=sha(ready), **g), indent=1) + '\n')
    print('READY written; live pin guard PASS on both rows; collected pins', g['collected_pins'], 'cross-packet mutable', g['cross_packet_mutable_pins'], g['classes'])


if __name__ == '__main__':
    main()
