#!/usr/bin/env python3
"""Packet187 final checks (CPU only). --ready writes the READY markers last, then re-runs the live pin guard
and the guarded launcher's rehearsal against them; any failure withdraws READY.

Default (verification only):
  * verify_cpu: chain seal (every seal pin is packet-internal; every ops file equals its sealed packet copy),
    CPU receipts current, proposal unchanged;
  * receipt facts: packet194 exp-diet engines reused byte for byte (device b8482321..., 0 compiler runs), W0p transport
    canary through the chain code plus the old shared-size negative, production-shape startup of both ranks
    (lane-A placement, diet at every exp-halfcache gate/up site), 11-window real entry, packet194 s194 screen recomputed
    from raw rows (screen winner +1.96 %; chain admitted by the coordinator's idle-lane ruling), submission rehearsal
    (2,000-char notes cap, diet/k3x/V3/static disclosure), compile-hold receipt, input closure;
  * live pin guard on the proposal descriptor (check_job) and a classification of every pin in the closure;
  * private-copy `lanequeue.py plan --lane A` on a scratch copy of the descriptor (informative: the chain is
    launched by launch_chain.sh, not appended to a lane queue);
  * lane state observed read-only (names of PAUSE-* and queue-*.txt files; nothing is written there).
--ready: all of the above; the READY row is pre-classified in memory (no cross-packet pin may enter the closure);
  then ops ready.json, ops READY-FOR-DEVICE.json and the packet's READY-FOR-DEVICE.json are written, then the live
  pin guard runs again (READY in the closure) and launch_chain.sh --dry-run is rehearsed in a sandbox (scratch lane
  dir, scratch coordination dir, stub systemctl/systemd-run on PATH, scratch meminfo): one positive dry run and nine
  refusals; the stubs prove that systemd-run is never called and the lane/coordination dirs are never modified. One live --dry-run (real systemctl
  is-active / list-units reads, real lane dir, real meminfo) is recorded as observed. Any failure withdraws READY.
Writes evidence/final-checks.json and, with --ready, evidence/final-pin-guard.json and evidence/launcher-rehearsal.json.
"""
import argparse, datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path
O = Path(__file__).resolve().parent
ROOT = O.parents[3]
P = ROOT / 'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet'
LQ = ROOT / 'experiments/own-xpu-runtime/ops/lane-queue'
EV = O / 'evidence'
DEVICE = 'b8482321769039274daf42b70f783517177cbc8c1d0b2d81b8ebab25f1442bdc'
READY_FILES = (O / 'ready.json', O / 'READY-FOR-DEVICE.json', P / 'READY-FOR-DEVICE.json')
sys.path.insert(0, str(O))


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load(name):
    return json.loads((EV / name).read_text())


def rel(p):
    return str(Path(p).relative_to(ROOT))


def guard_module():
    spec = importlib.util.spec_from_file_location('p195_pin_guard_live', LQ / 'pin_guard.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def proposal_rows():
    return [json.loads(l) for l in (O / 'proposal.jsonl').read_text().splitlines() if l.strip()]


def pin_guard():
    m = guard_module()
    rows = proposal_rows()
    checks = [m.check_job(r) for r in rows]
    assert all(c['passed'] for c in checks) and all(c['packet'] == str(P) for c in checks), checks
    pins, manifests = m.collect_pins(P)
    oracle = {(p, h) for p, h, s in pins if s.name == 'oracle-binding.json'}
    classes, cross = {}, []
    for p, h, s in pins:
        if p.is_relative_to(P) and p.resolve().is_relative_to(P.resolve()):
            key = 'packet-private'
        else:
            key = m.immutable_reason(p, h, P, oracle, m.STAGE) or 'CROSS-PACKET MUTABLE'
            if key == 'CROSS-PACKET MUTABLE':
                cross.append(str(p))
        classes[key] = classes.get(key, 0) + 1
    return dict(check_job=[dict(job=r['name'], passed=c['passed'], pins=c.get('pins'), manifests=c.get('manifests')) for r, c in zip(rows, checks)],
                collected_pins=len(pins), manifests=len(manifests),
                ready_in_closure=sorted(rel(x) for x in manifests if Path(x).name in ('READY-FOR-DEVICE.json', 'ready.json')),
                classes=classes, cross_packet_mutable_pins=len(cross), cross_examples=cross[:10])


def preclassify(row):
    """Pins the READY row would add to the guarded closure, classified before any READY file exists."""
    m = guard_module()
    bad = []
    for name, digest in m.extract_pins(row):
        target = m.pin_path(name, P / 'READY-FOR-DEVICE.json', P, ROOT)
        if not (target.is_relative_to(P) and target.resolve().is_relative_to(P.resolve())) and not m.immutable_reason(target, digest, P, set(), m.STAGE):
            bad.append(str(target))
    assert not bad, 'READY row would add cross-packet mutable pins: ' + str(bad[:5])


def private_plan():
    with tempfile.TemporaryDirectory(prefix='p195-plan-', dir=P / 'build') as tmp:
        shutil.copyfile(O / 'proposal.jsonl', Path(tmp) / 'queue-A.txt')
        cp = subprocess.run([sys.executable, '-B', str(LQ / 'lanequeue.py'), 'plan', '--lane', 'A', '--directory', tmp], cwd=ROOT,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900, env=dict(os.environ, OMP_NUM_THREADS='2'))
    rows = [json.loads(l) for l in cp.stdout.splitlines() if l.startswith('{')]
    assert cp.returncode == 0 and rows and all(r.get('plan') != 'FAILED' for r in rows), cp.stdout[-2000:] + cp.stderr[-2000:]
    return dict(returncode=cp.returncode, rows=rows, live_queue_modified=False, lanequeue=rel(LQ / 'lanequeue.py'), lanequeue_sha256=sha(LQ / 'lanequeue.py'),
                applicability='informative only: the chain is launched by launch_chain.sh (systemd unit packet195-chain-a), never appended to queue-A')


def verify():
    from verify_cpu import verify as cpu
    gates = cpu()
    native = json.loads((O / 'inputs/packet194-native.json').read_text())
    assert native['reused_byte_for_byte'] is True and native['relinked'] is False and native['compiler_runs'] == 0
    assert native['binaries']['build/device/own-rt-iq3']['sha256'] == DEVICE == sha(P / 'build/device/own-rt-iq3')
    assert sha(O / 'inputs/packet194-native.json') == sha(P / 'lineage-inputs/packet194-native.json')
    transport = load('transport-gate.json')
    assert transport['rows']['w0p_canary_diet']['handovers'] == 1000 and transport['rows']['negative_old_shared_size']['refused']
    assert transport['chain_shared_bytes'] == 4 * 65536 + 4096 + 64 and transport['rows']['decode']['identical']
    shape = load('real-shape.json')
    census = {r['rank']: r['device_census_bytes'] for r in shape['runs']}
    assert census == {0: 31374119922, 1: 31581735626} and all(r['capture_equals_packet194_diet_first'] and r['expert_gateup'] == 'diet' and r['expert_diet_sites'] > 0 for r in shape['runs'])
    entry = load('entry195.json')
    assert [w['window'] for w in entry['windows']] == ['K0', 'K1a', 'K1b', 'K2', 'W0p', 'KD', 'W2m', 'WS', 'WSs', 'WS128x', 'WS128']
    bracket = load('bracket-gate.json')
    assert bracket['screen_winner'] and bracket['idle_lane_exception']['authorized'] and bracket['min_gain_vs_every_k3x_view_percent'] >= 0.5 and bracket['k3x_drift_percent'] <= 0.5 and not bracket['s194_kill_rules']['fired']
    assert bracket['chain_rule_met'] is False and bracket['chain_rule_shortfall_points'] < 0.1 and bracket['record'] == 62.345281904743764
    rehearsal = load('submission-rehearsal.json')
    ident = rehearsal['k3x_payload_identity']
    assert rehearsal['submitted'] is False and ident['notes_chars'] <= ident['notes_cap'] == 2000 and rehearsal['current_floor_refusal']
    assert load('compile-poll.json')['passed'] and load('input-check.json')['passed']
    layout = json.loads((P / 'lineage/packet195-guard-layout.json').read_text())
    guard = pin_guard()
    assert guard['cross_packet_mutable_pins'] == 0, guard
    plan = private_plan()
    pauses = sorted(p.name for p in LQ.glob('PAUSE-*'))
    queues = sorted(p.name for p in LQ.glob('queue-*.txt'))
    row = dict(schema='packet195.final-checks.v1', passed=True, device_executed=False, queued=False, submitted=False,
               binary_sha256=DEVICE, reused_byte_for_byte=True, relinked=False, compiler_runs=0,
               cpu=gates, census_bytes_per_rank=[census[0], census[1]], w0p_handovers=1000, entry_windows=len(entry['windows']),
               bracket=dict(slower_diet_rate=bracket['slower_diet_rate'], faster_k3x_rate=bracket['faster_k3x_rate'], gain_vs_every_k3x_percent=bracket['min_gain_vs_every_k3x_view_percent'],
                            k3x_drift_percent=bracket['k3x_drift_percent'], record_bar=bracket['record_bar'], chain_rule_met=bracket['chain_rule_met'], idle_lane_exception=bracket['idle_lane_exception']['authorized'],
                            gateup_saving_us_per_layer=bracket['gateup_saving_min_both_ranks_us_per_layer'], evidence_files=len(bracket['evidence'])),
               notes_chars=ident['notes_chars'], pin_guard_before_ready=guard, private_plan=plan,
               guard_layout_receipt=rel(P / 'lineage/packet195-guard-layout.json'), guard_layout_moves=sorted(layout['directories']),
               lane_state_observed=dict(pause_files=pauses, queue_files=queues, note='observed only; never written by preparation'),
               root_free_bytes=shutil.disk_usage('/').free)
    (EV / 'final-checks.json').write_text(json.dumps(row, indent=1) + '\n')
    return row


STUB_SYSTEMCTL = r'''#!/bin/bash
# packet195 launcher-rehearsal stub: answers only the two read queries launch_chain.sh makes.
echo "$*" >> "$STUB_LOG"
case " $* " in
  *" is-active "*) u="${@: -1}"; for kv in ${STUB_STATES:-}; do [ "${kv%%=*}" = "$u" ] && { echo "${kv#*=}"; exit 0; }; done; echo inactive; exit 3;;
  *" list-units "*) for x in ${STUB_LIST:-}; do echo "$x loaded active running stub"; done; exit 0;;
esac
echo "UNEXPECTED systemctl $*" >> "$STUB_LOG.unexpected"; exit 1
'''
STUB_RUN = '#!/bin/bash\necho "systemd-run $*" >> "$STUB_LOG.systemd-run"; exit 1\n'


def lane_state(d):
    return sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in Path(d).iterdir())


def launcher_rehearsal():
    script = O / 'launch_chain.sh'
    cases = [
        ('positive-dry-run', dict(), ['PAUSE-B'], 'high', ['--dry-run'], 0, 'dry run: every check passed; would run: systemd-run --user --unit=packet195-chain-a'),
        ('endpoint-active', dict(STUB_STATES='qwen38-27b-vision=active'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'owner endpoint qwen38-27b-vision is active'),
        ('pause-a-present', dict(), ['PAUSE-A', 'PAUSE-B'], 'high', ['--dry-run'], 4, 'PAUSE-A is present'),
        ('pause-b-absent', dict(), [], 'high', ['--dry-run'], 4, 'PAUSE-B is absent'),
        ('lane-unit-busy', dict(STUB_LIST='lanequeue-A9.service'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'active lane/window/chain units: lanequeue-A9.service'),
        ('host-memory-low', dict(), ['PAUSE-B'], 'low', ['--dry-run'], 4, 'MemAvailable'),
        ('override-without-dry-run', dict(), ['PAUSE-B'], 'high', [], 64, 'rehearsal overrides require --dry-run'),
        ('previous-unit-failed', dict(STUB_STATES='packet195-chain-a=failed'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'unit packet195-chain-a is failed'),
        ('lane-marker-present', dict(), ['PAUSE-B', 'inflight-B.json'], 'high', ['--dry-run'], 4, 'inflight-B.json exists'),
        ('coordination-marker-present', dict(MARK='active-lane-B.json'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'active-lane-B.json exists'),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix='p195-launcher-', dir=P / 'build') as tmp:
        tmp = Path(tmp)
        stub = tmp / 'bin'
        stub.mkdir()
        (stub / 'systemctl').write_text(STUB_SYSTEMCTL)
        (stub / 'systemd-run').write_text(STUB_RUN)
        for f in stub.iterdir():
            f.chmod(0o755)
        (tmp / 'meminfo-high').write_text('MemTotal:       263000000 kB\nMemAvailable:   200000000 kB\n')
        (tmp / 'meminfo-low').write_text('MemTotal:       263000000 kB\nMemAvailable:     1000000 kB\n')
        for name, extra, files, mem, args, want, text in cases:
            lane = tmp / ('lane-' + name)
            lane.mkdir()
            for f in files:
                (lane / f).write_text('rehearsal\n')
            coord = tmp / ('coord-' + name)
            coord.mkdir()
            mark = extra.pop('MARK', None)
            if mark:
                (coord / mark).write_text('rehearsal\n')
            before = lane_state(lane) + lane_state(coord)
            log = tmp / ('stub-' + name + '.log')
            fn = tmp / ('fn-' + name)
            env = dict(PATH=f'{stub}:/usr/bin:/bin', HOME=os.environ.get('HOME', '/home/steve'), OMP_NUM_THREADS='2', FN=str(fn), STUB_LOG=str(log),
                       P195_LANE_DIR=str(lane), P195_MEMINFO=str(tmp / ('meminfo-' + mem)), P195_COORD_DIR=str(coord), XDG_RUNTIME_DIR=os.environ.get('XDG_RUNTIME_DIR', ''), **extra)
            started = time.monotonic()
            cp = subprocess.run(['/usr/bin/bash', str(script), *args], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
            out = cp.stdout + cp.stderr
            launched = Path(str(log) + '.systemd-run').exists()
            unexpected = Path(str(log) + '.unexpected').exists()
            unchanged = lane_state(lane) + lane_state(coord) == before
            ok = cp.returncode == want and text in out and not launched and not unexpected and unchanged
            rows.append(dict(case=name, returncode=cp.returncode, expected=want, matched=text in out, systemd_run_called=launched,
                             unexpected_systemctl=unexpected, lane_and_coordination_dirs_unchanged=unchanged, seconds=round(time.monotonic() - started, 1),
                             output_tail=out.strip().splitlines()[-1][:400] if out.strip() else '', passed=ok))
            assert ok, rows[-1]
        live_fn = tmp / 'fn-live'
        cp = subprocess.run(['/usr/bin/bash', str(script), '--dry-run'], cwd=ROOT, env=dict(os.environ, FN=str(live_fn), OMP_NUM_THREADS='2'),
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
        live = dict(returncode=cp.returncode, output_tail=(cp.stdout + cp.stderr).strip().splitlines()[-1][:400] if (cp.stdout + cp.stderr).strip() else '',
                    note='real systemctl is-active/list-units reads, real lane dir, real meminfo; --dry-run never launches')
        assert cp.returncode in (0, 4), live
    return dict(passed=True, device_executed=False, launched=False, launcher=rel(script), launcher_sha256=sha(script), cases=rows, live_dry_run=live)


def withdraw(reason):
    stamp = time.strftime('%Y%m%dT%H%M%S')
    folder = EV / ('withdrawn-ready-' + stamp)
    folder.mkdir()
    for f in READY_FILES:
        if f.exists():
            f.rename(folder / (f.parent.name + '--' + f.name))
    (EV / 'final-pin-guard.json').write_text(json.dumps(dict(passed=False, error=reason[:4000], withdrawn=rel(folder)), indent=1) + '\n')
    sys.exit('READY withdrawn: ' + reason[:600])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ready', action='store_true')
    a = ap.parse_args()
    assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU stop floor'
    if a.ready and any(f.exists() for f in READY_FILES):
        sys.exit('a READY file already exists; withdraw it first')
    row = verify()
    print('final checks PASS: binary', DEVICE[:16], '(reused), pin guard', row['pin_guard_before_ready']['collected_pins'], 'pins / 0 cross-packet mutable;',
          'private plan rc', row['private_plan']['returncode'])
    if not a.ready:
        return
    from verify_ready import evaluate
    ready = evaluate()
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    ready.update(commit=commit, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), final_checks_sha256=sha(EV / 'final-checks.json'),
                 device_quality_pending=True, device_performance_pending=True, record_eligible_after_chain_only=True, last_packet_write=True)
    preclassify(ready)
    for f in READY_FILES:
        f.write_text(json.dumps(ready, indent=2) + '\n')
    try:
        guard = pin_guard()
        assert guard['cross_packet_mutable_pins'] == 0 and len(guard['ready_in_closure']) == 3, guard
        launcher = launcher_rehearsal()
        from verify_ready import verify as verify_live
        verify_live()
    except BaseException as error:
        withdraw(repr(error))
    (EV / 'launcher-rehearsal.json').write_text(json.dumps(launcher, indent=1) + '\n')
    (EV / 'final-pin-guard.json').write_text(json.dumps(dict(passed=True, device_executed=False, ready_sha256=sha(P / 'READY-FOR-DEVICE.json'), **guard), indent=1) + '\n')
    print('READY written; live pin guard PASS:', guard['collected_pins'], 'pins, cross-packet mutable', guard['cross_packet_mutable_pins'], guard['classes'])
    print('launcher rehearsal PASS:', ', '.join(f"{r['case']}={r['returncode']}" for r in launcher['cases']), '| live dry run rc', launcher['live_dry_run']['returncode'],
          launcher['live_dry_run']['output_tail'][:200])


if __name__ == '__main__':
    main()
