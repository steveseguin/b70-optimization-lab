#!/usr/bin/env python3
"""Packet58-onecard-cache23-chain final checks (CPU only; never launches, queues or touches a PAUSE file).

Default (verification only):
  * the packet seal (seal.py --verify) and every CPU gate receipt (cpu_gates.check), the reseal receipt;
  * receipt facts: engine 083e3853 reused byte for byte (0 compiler runs), capacity argv max23/23049601024 in every model
    window (script mode + real parser), host floor 100,487,123,456 in the queue plan and the launcher, admission gate
    (screen winner +1.72 %, chain bar not met, record bar 35.926720 / cmvjejvoi03qcrf0138emu5a6), python 0 failures,
    submission rehearsal (notes <= 2,000, packet182c's real bundle refused), post-native/pre-device/closure rehearsals;
  * live pin guard: check_job on the orchestration's entry-proposal and a classification of every pin in the packet
    closure (0 cross-packet mutable required; the packet58-onecard-cache23 screen is referenced by provenance records);
  * private-copy `lanequeue.py plan --lane A` (informative: the chain is launched by launch_chain.sh, never queued);
  * lane state observed read-only; root free; fresh output and fault review.
--ready: all of the above; the READY row is pre-classified (no cross-packet mutable pin may enter the closure); then the
  packet's READY-FOR-DEVICE.json, the ops READY-FOR-DEVICE.json and ops/ready.json are written LAST; then the live pin
  guard runs again with READY in the closure, launch_chain.sh --dry-run is rehearsed in a sandbox (scratch lane dir,
  scratch coordination dir, scratch /proc, stub systemctl/systemd-run on PATH, scratch meminfo: one positive dry run and
  eleven refusals; the stubs prove systemd-run is never called and the lane/coordination dirs are never modified), one
  live --dry-run (real systemctl reads, real lane dir, real meminfo) is recorded as observed, and verify_ready.py runs.
  Any failure withdraws READY (moved under evidence/withdrawn-ready-<stamp>/).
Writes evidence/final-checks.json and, with --ready, evidence/final-pin-guard.json and evidence/launcher-rehearsal.json.
"""
import argparse, datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path('/home/steve/llm-optimizations')
X = ROOT / 'experiments/own-xpu-runtime'
O = X / 'ops/packet58c23chain-orchestration'
P = X / 'stage2/packet58-onecard-cache23-chain'
LQ = X / 'ops/lane-queue'
EV = P / 'evidence'
DEVICE = '083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a'
HOST_FLOOR = 100487123456
READY_FILES = (P / 'READY-FOR-DEVICE.json', O / 'READY-FOR-DEVICE.json', O / 'ready.json')
sys.path.insert(0, str(O))
import cpu_gates  # noqa: E402


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load(name):
    return json.loads((EV / name).read_text())


def rel(p):
    return str(Path(p).relative_to(ROOT))


def record(p):
    return dict(name=Path(p).name, parent_relpath=rel(p), parent_digest=sha(p))


def guard_module():
    spec = importlib.util.spec_from_file_location('p58c23_pin_guard_live', LQ / 'pin_guard.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def proposal():
    return json.loads((O / 'entry-proposal.jsonl').read_text().strip())


def pin_guard():
    m = guard_module()
    job = proposal()
    check = m.check_job(job)
    assert check['passed'] and check['packet'] == str(P), check
    pins, manifests = m.collect_pins(P)
    oracle = {(p, h) for p, h, s in pins if s.name == 'oracle-binding.json'}
    classes, cross = {}, []
    for p, h, s in pins:
        if p.is_relative_to(P) and p.resolve().is_relative_to(P.resolve()):
            key = 'packet-private'
        else:
            key = m.immutable_reason(p, h, P, oracle, m.STAGE) or 'CROSS-PACKET MUTABLE'
            if key == 'CROSS-PACKET MUTABLE':
                cross.append(f'{p} (sealed by {s})')
        classes[key] = classes.get(key, 0) + 1
    return dict(check_job=dict(job=job['name'], passed=check['passed'], pins=check.get('pins'), manifests=check.get('manifests')),
                collected_pins=len(pins), manifests=len(manifests),
                ready_in_closure=sorted(rel(x) for x in manifests if Path(x).name in ('READY-FOR-DEVICE.json', 'ready.json')),
                classes=classes, cross_packet_mutable_pins=len(cross), cross_examples=cross[:10])


def preclassify(row):
    m = guard_module()
    bad = []
    for name, digest in m.extract_pins(row):
        target = m.pin_path(name, P / 'READY-FOR-DEVICE.json', P, ROOT)
        if not (target.is_relative_to(P) and target.resolve().is_relative_to(P.resolve())) and not m.immutable_reason(target, digest, P, set(), m.STAGE):
            bad.append(str(target))
        elif target.is_relative_to(P) and (not target.is_file() or sha(target) != digest):
            bad.append(str(target) + ' (packet-local bytes differ)')
    assert not bad, 'READY row would add bad pins: ' + str(bad[:5])


def private_plan():
    with tempfile.TemporaryDirectory(prefix='p58c23-plan-', dir=P / 'build') as tmp:
        shutil.copyfile(O / 'entry-proposal.jsonl', Path(tmp) / 'queue-A.txt')
        cp = subprocess.run([sys.executable, '-B', str(LQ / 'lanequeue.py'), 'plan', '--lane', 'A', '--directory', tmp], cwd=ROOT,
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900, env=dict(os.environ, OMP_NUM_THREADS='2'))
    rows = [json.loads(l) for l in cp.stdout.splitlines() if l.startswith('{')]
    assert cp.returncode == 0 and len(rows) == 1 and rows[0].get('plan') == 'passed' and rows[0]['host_required_available_bytes'] == HOST_FLOOR, cp.stdout[-1500:] + cp.stderr[-1500:]
    return dict(returncode=cp.returncode, rows=rows, live_queue_modified=False, lanequeue_sha256=sha(LQ / 'lanequeue.py'),
                applicability='informative only: the chain is launched by launch_chain.sh (systemd unit packet58-onecard-cache23-a), never appended to queue-A')


def verify():
    cp = subprocess.run([sys.executable, '-B', str(P / 'seal.py'), '--verify'], cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600)
    assert cp.returncode == 0, 'seal: ' + (cp.stdout + cp.stderr)[-800:]
    ok, gates = cpu_gates.check()
    assert ok, gates
    reseal = json.loads((O / 'reseal.json').read_text())
    assert reseal['passed'] and reseal['build_receipt_sha256'] == sha(P / 'build-receipt.json'), 'reseal receipt stale: run reseal.py'
    receipt = json.loads((P / 'build-receipt.json').read_text())
    assert receipt['artifacts']['build/device/own-rt-iq3'] == DEVICE == sha(P / 'build/device/own-rt-iq3') and receipt['cache_cap'] == 'max23' and receipt['cache_allocation_bytes'] == 23049601024
    binding = json.loads((P / 'engine-binding.json').read_text())
    assert binding['compiled_here'] is False and binding['compiler_runs'] == 0 and binding['engine']['sha256'] == DEVICE
    argv = load('script-argv-check.json')
    assert argv['passed'] and all(w['flags_present'] and not w['native_child_executed'] for w in argv['windows']) and len(argv['windows']) == 5
    flags = load('chain-flags.json')
    assert flags['passed'] and flags['binary_sha256'] == DEVICE and flags['capacity_argv'] == {'--cache-cap': 'max23', '--cache-bytes': '23049601024'}
    adm = load('admission-gate.json')
    r = adm['recomputed']
    assert r['screen_winner'] and not r['chain_rule'] and r['minimum_gain_vs_best_warm_control'] >= 0.005 and r['control_drift_fraction'] <= 0.03 and r['exact_requests'] == 60 \
        and r['fills_reduced_8pct'] and r['drm_under_guard'] and adm['admission']['record_bar']['tok_s'] == 35.92672010504166 and adm['admission']['chain_bar_met'] is False
    queue = load('queue-gate.json'); launch = load('launch-limits.json')
    assert queue['plan']['host_required_available_bytes'] == HOST_FLOOR and launch['host_floor_bytes'] == HOST_FLOOR and launch['planned_write_bytes'] == 397492208
    py = load('python-cpu-gates-cache23.json')
    assert py['mine']['summary'].startswith('OK') and py['mine']['returncode'] == 0
    sub = load('submission-rehearsal-cache23.json')
    assert sub['notes_characters'] <= 2000 and sub['packet182c_real_bundle']['refused'] and sub['payload_written'] is False and sub['network_used'] is False
    post = load('postnative-cache23.json'); pre = load('predevice-cache23.json'); clo = load('closure-cache23.json')
    assert post['passed'] and post['records'][-1]['full_cache_bytes'] == 23049601024 and pre['passed'] and len(pre['windows']) == 7 and clo['passed']
    derived = json.loads((P / 'derived-chain.json').read_text())
    digest = hashlib.sha256(derived['chain_command'].encode()).hexdigest()
    assert not (ROOT / derived['chain_output']).exists() and not (EV / 'fault-review-cache23-a.json').exists(), 'output or fault review not fresh'
    assert proposal()['plan']['host_required_available_bytes'] == HOST_FLOOR
    guard = pin_guard()
    assert guard['cross_packet_mutable_pins'] == 0, guard
    plan = private_plan()
    assert not any(LQ.glob('queue-*.txt')) or all('packet58-onecard-cache23-chain' not in q.read_text() for q in LQ.glob('queue-*.txt')), 'the chain must never be in a live queue'
    row = dict(schema='packet58cache23chain.final-checks.v1', passed=True, device_executed=False, queued=False, submitted=False, launched=False,
               binary_sha256=DEVICE, reused_byte_for_byte=True, compiler_runs=0, chain_command_digest_sha256=digest, unit=derived['unit'], chain_output=derived['chain_output'],
               capacity=dict(cache_cap='max23', cache_bytes=23049601024, arena_old=21552729600), host_required_available_bytes=HOST_FLOOR, launcher_floor_bytes=HOST_FLOOR + 1073741824,
               bracket=dict(rates=adm['recomputed']['rates'], minimum_gain=r['minimum_gain_vs_best_warm_control'], drift=r['control_drift_fraction'], fills=[adm['views'][l]['fills_per_token'] for l in ('A0', 'B0', 'A1', 'B1', 'A2')],
                            drm_peak_loaded_bytes=r['drm_peak_loaded_bytes'], files_read=adm['files_read']),
               bars=dict(record_tok_s=35.92672010504166, reference_submission='cmvjejvoi03qcrf0138emu5a6', chain_bar_tok_s=36.6452544, chain_bar_met=False,
                         admitted_by='coordinator ruling 2026-10-23 (idle lanes)'),
               gates={v['receipt']: v['sha256'] for v in gates.values()}, notes_chars=sub['notes_characters'], python=dict(ran=py['mine']['ran'], summary=py['mine']['summary']),
               pin_guard_before_ready=guard, private_plan=plan, reseal=dict(build_receipt_sha256=reseal['build_receipt_sha256'], sources=reseal['sources'], gates=len(reseal['gates'])),
               lane_state_observed=dict(pause_files=sorted(p.name for p in LQ.glob('PAUSE-*')), queue_files=sorted(p.name for p in LQ.glob('queue-*.txt')), note='observed only; never written by preparation'),
               root_free_bytes=shutil.disk_usage('/').free, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    (EV / 'final-checks.json').write_text(json.dumps(row, indent=1) + '\n')
    return row


STUB_SYSTEMCTL = r'''#!/bin/bash
# packet58c23chain launcher-rehearsal stub: answers only the read queries launch_chain.sh makes.
echo "$*" >> "$STUB_LOG"
case " $* " in
  *" is-active "*) u="${@: -1}"; for kv in ${STUB_STATES:-}; do [ "${kv%%=*}" = "$u" ] && { echo "${kv#*=}"; exit 0; }; done; echo inactive; exit 3;;
  *" list-units "*) case " $* " in *"codex-*"*) for x in ${STUB_CODEX:-}; do echo "$x loaded active running stub"; done;; *) for x in ${STUB_LIST:-}; do echo "$x loaded active running stub"; done;; esac; exit 0;;
  *" show "*) echo "${STUB_FREEZER:-frozen}"; exit 0;;
esac
echo "UNEXPECTED systemctl $*" >> "$STUB_LOG.unexpected"; exit 1
'''
STUB_RUN = '#!/bin/bash\necho "systemd-run $*" >> "$STUB_LOG.systemd-run"; exit 1\n'


def lane_state(d):
    return sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in Path(d).iterdir())


def launcher_rehearsal():
    script = O / 'launch_chain.sh'
    cases = [
        ('positive-dry-run', dict(), ['PAUSE-B'], 'high', ['--dry-run'], 0, 'dry run: every check passed; would run: systemd-run --user --unit=packet58-onecard-cache23-a'),
        ('endpoint-active', dict(STUB_STATES='qwen38-27b-fp8=active'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'owner endpoint qwen38-27b-fp8 is active'),
        ('pause-a-present', dict(), ['PAUSE-A', 'PAUSE-B'], 'high', ['--dry-run'], 4, 'PAUSE-A is present'),
        ('pause-b-absent', dict(), [], 'high', ['--dry-run'], 4, 'PAUSE-B is absent'),
        ('lane-unit-busy', dict(STUB_LIST='lanequeue-A9.service'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'active lane/window/chain units: lanequeue-A9.service'),
        ('codex-not-frozen', dict(STUB_CODEX='codex-exec-7.service', STUB_FREEZER='running'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'codex unit codex-exec-7.service is active and not frozen'),
        ('host-memory-low', dict(), ['PAUSE-B'], 'low', ['--dry-run'], 4, 'MemAvailable'),
        ('override-without-dry-run', dict(), ['PAUSE-B'], 'high', [], 64, 'rehearsal overrides require --dry-run'),
        ('previous-unit-failed', dict(STUB_STATES='packet58-onecard-cache23-a=failed'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'unit packet58-onecard-cache23-a is failed'),
        ('lane-marker-present', dict(), ['PAUSE-B', 'inflight-A.json'], 'high', ['--dry-run'], 4, 'inflight-A.json exists'),
        ('coordination-marker-present', dict(MARK='active-lane-A.json'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'active-lane-A.json exists'),
        ('render-node-user', dict(DRI='1'), ['PAUSE-B'], 'high', ['--dry-run'], 4, 'render-node users present'),
    ]
    rows = []
    with tempfile.TemporaryDirectory(prefix='p58c23-launcher-', dir=P / 'build') as tmp:
        tmp = Path(tmp)
        stub = tmp / 'bin'
        stub.mkdir()
        (stub / 'systemctl').write_text(STUB_SYSTEMCTL)
        (stub / 'systemd-run').write_text(STUB_RUN)
        for f in stub.iterdir():
            f.chmod(0o755)
        (tmp / 'meminfo-high').write_text('MemTotal:       263000000 kB\nMemAvailable:   200000000 kB\n')
        (tmp / 'meminfo-low').write_text('MemTotal:       263000000 kB\nMemAvailable:     1000000 kB\n')
        empty_proc = tmp / 'proc-empty'; empty_proc.mkdir()
        dri_proc = tmp / 'proc-dri'; (dri_proc / '4242' / 'fd').mkdir(parents=True); os.symlink('/dev/dri/renderD129', dri_proc / '4242' / 'fd' / '9')
        for name, extra, files, mem, args, want, text in cases:
            extra = dict(extra)
            lane = tmp / ('lane-' + name); lane.mkdir()
            for f in files:
                (lane / f).write_text('rehearsal\n')
            coord = tmp / ('coord-' + name); coord.mkdir()
            mark = extra.pop('MARK', None)
            if mark:
                (coord / mark).write_text('rehearsal\n')
            proc = dri_proc if extra.pop('DRI', None) else empty_proc
            before = lane_state(lane) + lane_state(coord)
            log = tmp / ('stub-' + name + '.log')
            fn = tmp / ('fn-' + name)
            env = dict(PATH=f'{stub}:/usr/bin:/bin', HOME=os.environ.get('HOME', '/home/steve'), OMP_NUM_THREADS='2', FN=str(fn), STUB_LOG=str(log),
                       P58C23_LANE_DIR=str(lane), P58C23_MEMINFO=str(tmp / ('meminfo-' + mem)), P58C23_COORD_DIR=str(coord), P58C23_PROC=str(proc),
                       XDG_RUNTIME_DIR=os.environ.get('XDG_RUNTIME_DIR', ''), **extra)
            started = time.monotonic()
            cp = subprocess.run(['/usr/bin/bash', str(script), *args], cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
            out = cp.stdout + cp.stderr
            launched = Path(str(log) + '.systemd-run').exists()
            unexpected = Path(str(log) + '.unexpected').exists()
            unchanged = lane_state(lane) + lane_state(coord) == before
            leftovers = sorted(p.name for p in EV.glob('.dry-run-fault-review-*'))
            ok = cp.returncode == want and text in out and not launched and not unexpected and unchanged and not leftovers and not (EV / 'fault-review-cache23-a.json').exists()
            rows.append(dict(case=name, returncode=cp.returncode, expected=want, matched=text in out, systemd_run_called=launched, unexpected_systemctl=unexpected,
                             lane_and_coordination_dirs_unchanged=unchanged, temporary_fault_review_removed=not leftovers, seconds=round(time.monotonic() - started, 1),
                             output_tail=out.strip().splitlines()[-1][:400] if out.strip() else '', passed=ok))
            assert ok, rows[-1]
        live_fn = tmp / 'fn-live'
        cp = subprocess.run(['/usr/bin/bash', str(script), '--dry-run'], cwd=ROOT, env=dict(os.environ, FN=str(live_fn), OMP_NUM_THREADS='2'),
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
        live = dict(returncode=cp.returncode, output_tail=(cp.stdout + cp.stderr).strip().splitlines()[-1][:400] if (cp.stdout + cp.stderr).strip() else '',
                    note='real systemctl reads, real lane dir, real meminfo, real /proc; --dry-run never launches; rc 4 is the expected refusal while the owner endpoints run')
        assert cp.returncode in (0, 4), live
    return dict(passed=True, device_executed=False, launched=False, launcher=rel(script), launcher_digest=sha(script), cases=rows, live_dry_run=live)


def ready_row(final):
    base = json.loads((O / 'derivation-READY-FOR-DEVICE.json').read_text())
    sel = json.loads((P / 'runtime-selection.json').read_text())
    derived = json.loads((P / 'derived-chain.json').read_text())
    pfiles = ['build-receipt.json', 'submission-pins.json', 'ready.json', 'WINDOW.md', 'runtime-selection.json', 'submission-policy.json', 'record-threshold.snapshot',
              'derived-chain.json', 'seal.py', 'verify_ready.py', 'fault_review.py', 'queue_runner.py', 'window.py', 'suite_driver.py', 'views.py', 'composition.py',
              'memory_plan.py', 'admission.json', 'packet58_submission.py', 'engine-binding.json', 'restore-inputs.json', 'README.md', 'DO-NOT-REPEAT.md', 'RETENTION.md',
              'CPU-PREPARATION-CLOSEOUT.md', 'MEMORY.md', 'evidence/chain-flags.json', 'evidence/cache23-chain-delta.json', 'evidence/admission-gate.json', 'evidence/final-checks.json']
    pfiles += ['evidence/' + leaf for leaf in cpu_gates.RECEIPTS.values() if 'evidence/' + leaf not in pfiles]
    ofiles = ['derive_cache23_chain.py', 'apply_cache23_chain_delta.py', 'cpu_gates.py', 'reseal.py', 'admission_gate.py', 'script_argv_check.py', 'launch_chain.sh',
              'final_checks.py', 'verify_ready.py', 'prepare_submission.py', 'submission.py', 'entry-proposal.jsonl', 'queue-plan.log', 'help.json', 'predevice-rehearsal.json',
              'postnative-rehearsal.json', 'onecard_chain_derive.py', 'derivation.json', 'capacity-patch.json', 'derivation-READY-FOR-DEVICE.json', 'reseal.json', 'README.md']
    row = dict(base)
    row.update(schema='packet58-onecard-cache23-chain.ready-for-device.v2', prepared_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               generator='ops/onecard_chain_derive.py (derive_cache23_chain.py) + apply_cache23_chain_delta.py + reseal.py + final_checks.py',
               reason='packet182c-chain re-derived from packet58aj-orchestration with the packet58-onecard-cache23 engine, the max23 capacity argv/selection, the cache23 '
                      'device plan (host 100,487,123,456) and the adapted submission validator; chain admitted below the +2 % bar by coordinator ruling (idle lanes).',
               chain_binary_sha256=DEVICE, parent_chain_binary_sha256=base['parent_chain_binary_sha256'], record_line_binary_sha256='1b41fb4da10a3c8c644f44f6288b9b1af0f46300847a06a254420796af921145',
               configuration=sel, capacity=derived['capacity'], host_required_available_bytes=HOST_FLOOR, launcher_host_floor_bytes=HOST_FLOOR + 1073741824,
               bars=final['bars'], admission_gate=dict(path='evidence/admission-gate.json', sha256=sha(EV / 'admission-gate.json'), files_read=final['bracket']['files_read']),
               bracket_rates_tok_s=final['bracket']['rates'], minimum_gain=final['bracket']['minimum_gain'], control_drift_fraction=final['bracket']['drift'],
               fills_per_token=final['bracket']['fills'], drm_peak_loaded_bytes=final['bracket']['drm_peak_loaded_bytes'],
               launcher='ops/packet58c23chain-orchestration/launch_chain.sh (--dry-run first; coordinator by hand; never auto-launched)',
               submission=dict(prepare='ops/packet58c23chain-orchestration/prepare_submission.py --chain <output> --output <packet>/submission/prepared-a',
                               submit='ops/packet58c23chain-orchestration/submission.py --payloads <prepared-a>/payload-queue.json [--dry-run | --server-dry-run]',
                               update_record='prepare_submission.py --update-record <prepared-a>/result.json --submission-id <ID>', notes_cap=2000, scope_tokens=128),
               gates=final['gates'],   # {'evidence/<receipt>': sha256}: packet-local pins (the pin guard reads a `gates` map as pins)
               files_sha256={rel(P / n): sha(P / n) for n in pfiles}, orchestration_provenance=[record(O / n) for n in ofiles if (O / n).is_file()],
               pin_audit=dict(final['pin_guard_before_ready'], lanequeue_plan='passed (temporary queue dir)'),
               final_checks_sha256=sha(EV / 'final-checks.json'), commit=subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
               chain_quality_pending=True, chain_performance_pending=True, record_eligible_after_chain_only=True, no_retry=True, queued=False, device_executed=False,
               services_started=False, model_payload_reads=False, live_queue_changed=False, submission_performed=False, final_content_write=True, last_packet_write=True)
    return row


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
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'run under nice -n 19 taskset -c 8-15,24-31'
    assert shutil.disk_usage('/').free >= 26_000_000_000, 'root below the 26 GB preparation floor'
    if a.ready and any(f.exists() for f in READY_FILES):
        sys.exit('a READY file already exists; withdraw it first')
    row = verify()
    print('final checks PASS: engine', DEVICE[:16], '(reused), pin guard', row['pin_guard_before_ready']['collected_pins'], 'pins /', row['pin_guard_before_ready']['cross_packet_mutable_pins'],
          'cross-packet mutable; private plan rc', row['private_plan']['returncode'])
    if not a.ready:
        return
    ready = ready_row(row)
    preclassify(ready)
    for f in READY_FILES:
        f.write_text(json.dumps(ready, indent=2) + '\n')
    try:
        guard = pin_guard()
        assert guard['cross_packet_mutable_pins'] == 0 and len(guard['ready_in_closure']) >= 2, guard
        launcher = launcher_rehearsal()
        cp = subprocess.run([sys.executable, '-B', str(O / 'verify_ready.py')], cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=900)
        assert cp.returncode == 0, 'verify_ready after READY: ' + (cp.stdout + cp.stderr)[-800:]
    except BaseException as error:
        withdraw(repr(error))
    (EV / 'launcher-rehearsal.json').write_text(json.dumps(launcher, indent=1) + '\n')
    (EV / 'final-pin-guard.json').write_text(json.dumps(dict(passed=True, device_executed=False, ready_sha256=sha(P / 'READY-FOR-DEVICE.json'), **guard), indent=1) + '\n')
    print('READY written; live pin guard PASS:', guard['collected_pins'], 'pins, cross-packet mutable', guard['cross_packet_mutable_pins'], guard['classes'])
    print('launcher rehearsal PASS:', ', '.join(f"{r['case']}={r['returncode']}" for r in launcher['cases']), '| live dry run rc', launcher['live_dry_run']['returncode'],
          launcher['live_dry_run']['output_tail'][:200])


if __name__ == '__main__':
    main()
