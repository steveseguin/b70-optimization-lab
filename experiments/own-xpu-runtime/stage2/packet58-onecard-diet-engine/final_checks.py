#!/usr/bin/env python3
"""Packet58 diet-engine final checks. CPU only; never queues or launches.

  python3 -B final_checks.py          verify every receipt, the seal and the proposal (no write)
  python3 -B final_checks.py --ready  the same, then write READY-FOR-DEVICE.json LAST, then re-run the real pin
                                      guard on the full READY closure, count every pin directly (0 cross-packet
                                      mutable pins required) and plan the proposal in a private queue copy;
                                      any refusal withdraws READY (moved to evidence/READY-WITHDRAWN-<utc>.json).
"""
import datetime, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from build_engine import P, ROOT, sha, save, limits

OPS = P.parents[1] / 'ops'; LQ = OPS / 'lane-queue'
PROPOSAL = LQ / 'proposed-p58-dietengine-one-card-A.txt'
READY = P / 'READY-FOR-DEVICE.json'
JOB = 'packet58dietengine-one-card-v5-A'
CHECKS = ('build', 'kernel-identity', 'diet-fixture', 'cache-identity', 'preparation', 'loader', 'analyzer-real-parent', 'python-cpu-gates', 'drain-fix',
          'package-rows', 'entry-imports', 'queue-plans', 'shared-entry-report-final', 'pin-guard')
FRESH = (P / 'screen/evidence/card0-58de-v5-a',)
ENGINE_PARENT = '083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a'


def read(p):
    return json.loads(Path(p).read_text())


def verify():
    cp = subprocess.run([sys.executable, '-B', str(P / 'seal.py'), '--verify'], cwd=P, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert cp.returncode == 0, 'seal: ' + cp.stderr[-800:]
    checks = {}
    for leaf in CHECKS:
        f = P / 'evidence' / f'{leaf}.json'; r = read(f)
        assert r['passed'] is True and r['device_executed'] is False, leaf
        checks[str(f.relative_to(P))] = sha(f)
    for leaf in ('argument-gate.json', 'startup-cpu.json'):
        f = P / 'screen/evidence' / leaf; assert read(f)['passed'] is True; checks[str(f.relative_to(P))] = sha(f)
    pkg = read(P / 'evidence/package-rows.json')
    assert pkg['seal']['sha256'] == sha(P / 'screen/build-receipt.json') and pkg['proposal']['sha256'] == sha(PROPOSAL)
    assert PROPOSAL.read_bytes() == (P / 'screen/proposals' / PROPOSAL.name).read_bytes()
    plan = read(P / 'evidence/queue-plans.json'); assert plan['records'][0]['proposal_sha256'] == sha(PROPOSAL)
    assert read(P / 'evidence/shared-entry-report-final.json')['proposal_sha256'] == sha(PROPOSAL)
    build = read(P / 'evidence/build.json'); seal = read(P / 'screen/build-receipt.json')
    engine = sha(P / 'build/device/own-rt-iq3')
    assert build['artifacts']['build/device/own-rt-iq3'] == seal['engine_sha256'] == engine != ENGINE_PARENT and build['warnings'] == 0
    prep = read(P / 'evidence/preparation.json')
    assert prep['target_binary_sha256'] == engine and prep['p176_kernel_tail_stores'] == 60 and prep['peak_device_bytes'] <= 29828911360
    mp = read(P / 'memory-plan.json'); adm = read(P / 'admission.json')['admission']
    assert adm['device_categories'] == mp['device_categories'] and adm['device_owned_bound_bytes'] == 29828911360 and adm['driver_allowance_bytes'] == 671088640
    assert adm['host_required_available_bytes'] == 100487123456 and mp['peaks_after_growth']['drm_projection_bytes'] < 30_500_000_000
    for path in FRESH:
        assert not path.exists(), 'must be fresh: ' + str(path)
    assert not any(LQ.glob('queue-*.txt')) or all(JOB not in q.read_text() for q in LQ.glob('queue-*.txt')), 'proposal must never be in a live queue'
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop: 27 GB root floor'
    return checks


def census():
    sys.path.insert(0, str(LQ)); import pin_guard
    job = next(json.loads(s) for s in PROPOSAL.read_text().splitlines() if s.startswith('{'))
    guard = pin_guard.check_job(job, pin_guard.ROOT, pin_guard.STAGE)
    pins, manifests = pin_guard.collect_pins(P, ROOT)
    oracle = {(p, h) for p, h, s in pins if s.name == 'oracle-binding.json'}
    reasons, mutable = {}, []
    for target, digest, source in pins:
        if target.is_relative_to(P) and target.resolve().is_relative_to(P.resolve()):
            reason = 'packet-local'
        else:
            reason = pin_guard.immutable_reason(target, digest, P, oracle, pin_guard.STAGE)
            if not reason:
                mutable.append(f'{target} (sealed by {source})')
                reason = 'MUTABLE'
        reasons[reason] = reasons.get(reason, 0) + 1
    return dict(pin_guard=guard, pins=len(pins), manifests=len(manifests), by_reason=reasons,
                cross_packet_mutable_pins=len(mutable), mutable=mutable[:20], ready_in_closure=any(m.name == READY.name for m in manifests))


def live_plan():
    with tempfile.TemporaryDirectory(prefix='p58de-final-plan-') as tmp:
        (Path(tmp) / 'queue-A.txt').write_text(next(s for s in PROPOSAL.read_text().splitlines() if s.startswith('{')) + '\n')
        cp = subprocess.run([sys.executable, '-B', str(LQ / 'lanequeue.py'), 'plan', '--lane', 'A', '--directory', tmp], cwd=ROOT,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
    rows = [json.loads(s) for s in cp.stdout.splitlines() if s.startswith('{')]
    return dict(returncode=cp.returncode, rows=rows, stderr_tail=cp.stderr[-600:])


def ready(checks):
    assert not READY.exists(), 'READY already exists'
    mp = read(P / 'memory-plan.json')
    row = dict(schema='own-runtime.packet58dietengine.ready.v1', ready_for_device=True, passed=True, device_executed=False,
               packet=P.name, job=JOB, proposal=str(PROPOSAL.relative_to(ROOT)), proposal_sha256=sha(PROPOSAL),
               lane='A', scope='whole-host', gpu_count=1, card=0, model_loads=1, windows=['K1a', 'K1b', 'WSCREEN'],
               separate_smoke_required=False, opening_contract='No separate smoke: bracket opens with K1a/K1b and exact A0 control.',
               arm_order=['max23', 'max23+diet', 'max23', 'max23+diet', 'max23'], labels=['A0', 'B0', 'A1', 'B1', 'A2'],
               arms=dict(A='cache23 record selection, cache_cap max23, expert_gateup production',
                         B='same selection and max23 capacity, expert_gateup diet'),
               engine_sha256=sha(P / 'build/device/own-rt-iq3'), engine_rebuilt=True, parent_engine_sha256=ENGINE_PARENT,
               engine_identity='cache23 engine + native-dietengine-delta.patch; all 47 parent device images unchanged plus one pinned diet image; 47 of 48 gate/up sites switch (layer 2 keeps its other layout kernel)',
               warmup='A0 exact, excluded only from speed and drift', prompts_per_view=12, max_new=128, required_exact_requests=60,
               oracle='iq3-p49-split32-v1', kv_dtype='BF16', resident_lookups_all_views=True, foreground_io_all_views='kernel',
               winner_minimum_gain_over_every_warm_control=.005, maximum_control_drift_fraction=.03,
               chain_rule=dict(minimum_gain_over_every_control_view=.02, chain_bar_tok_s=37.33456224, record_tok_s=36.602512, tool='screen/compare_bracket.s58de_decision'),
               kill_rules=['any view not 12/12 exact', 'DRM total-vram0 > 30,500,000,000 B (native after-load + supervisor guard, unchanged)',
                           'fills/token or fill MB/token differ across arms', 'layer-body saving < 5 us per layer', 'warm max23 < 36.0 tok/s or drift > 3 % -> host disturbed; no automatic rerun'],
               memory=dict(cache_allocation_bytes=23049601024, usable=dict(max=21552729600, max23=23049601024), device_owned_bound_bytes=29828911360, driver_allowance_bytes=671088640,
                           device_reserve_bytes=1500000000, drm_guard_bytes=30500000000, drm_projection_bytes=mp['peaks_after_growth']['drm_projection_bytes'],
                           drm_guard_margin_bytes=mp['peaks_after_growth']['drm_guard_margin_bytes'], host_required_available_bytes=100487123456, plan='memory-plan.json'),
               expected=dict(v5_seconds=[700, 1200], watchdog_seconds=3600, gain='+2.1 to +2.8 % projected from the micro; full-engine gain unmeasured'),
               device_disk_floor_bytes=25_000_000_000, cpu_disk_stop_bytes=27_000_000_000,
               build_receipt_sha256=sha(P / 'screen/build-receipt.json'), checks=checks,
               argument_gate=dict(path='screen/evidence/argument-gate.json', sha256=sha(P / 'screen/evidence/argument-gate.json'),
                                  memavailable_substituted_for='WSCREEN (owner endpoints running during CPU preparation)'),
               device_exactness='pending', device_speed='pending', fresh_process_repeat=False, strict512=False, submission_eligible=False,
               coordinator_requirements='Whole-host lane A; PAUSE-B kept; endpoints stopped by the window procedure (MemAvailable >= 100,487,123,456 + 1 GiB at START); '
                                        'no retry; graceful drain; commit summary.json/window.json right after the window; chain only at >= +2 % (a later composite bundle, not this packet)',
               parent=dict(name='packet58-onecard-cache23', parent_relpath='experiments/own-xpu-runtime/stage2/packet58-onecard-cache23',
                           parent_commit=read(P / 'lineage/packet58de-copy.json')['parent']['parent_commit'],
                           record_line='packet58-onecard-cache23-chain (36.602512 tok/s, cmvkcqznb002lng01fsrhjn7t)'),
               prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               preparation_head_commit=subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True, stdin=subprocess.DEVNULL).strip())
    save(READY, row)
    return row


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    limits()
    if '--ready' not in sys.argv:
        assert not READY.exists() or '--allow-ready' in sys.argv, 'READY exists; use --allow-ready to re-verify'
        checks = verify()
        print(json.dumps(dict(passed=True, checks=len(checks), ready=READY.exists())))
        return 0
    checks = verify()
    ready(checks)
    try:
        c = census()
        assert c['cross_packet_mutable_pins'] == 0 and c['ready_in_closure'], c
        lp = live_plan()
        assert lp['returncode'] == 0 and len(lp['rows']) == 1 and lp['rows'][0]['plan'] == 'passed', lp
        save(P / 'evidence/final-ready-checks.json', dict(passed=True, device_executed=False, written_after_ready=True,
                                                          ready_sha256=sha(READY), pin_census=c, private_lanequeue_plan=lp))
    except (AssertionError, ValueError, OSError) as e:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        os.replace(READY, P / f'evidence/READY-WITHDRAWN-{stamp}.json')
        print('READY withdrawn: ' + str(e)[:2000], file=sys.stderr)
        return 1
    print(json.dumps(dict(ready=True, pins=c['pins'], manifests=c['manifests'], by_reason=c['by_reason'],
                          cross_packet_mutable_pins=c['cross_packet_mutable_pins'], plan=lp['rows'][0]['plan'])))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
