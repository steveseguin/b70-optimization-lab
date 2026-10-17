#!/usr/bin/env python3
"""Coordinator-only diagnostic screen. --plan is CPU-only and never opens a device."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from common import (D, HERE, M, ROOT, S, SUPPORT, W, compare_tokens, label,
                    read, require, save, sealed, sha, summary)

WRITES = {'tp2': 1_100_000_000, 'onecard': 256 * 1024**2}
WATCHDOG = {'tp2': 3600, 'onecard': 7200}


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', choices=('tp2', 'onecard'), required=True)
    ap.add_argument('--lineage', type=Path, required=True)
    for name in ('binary', 'dispatch', 'seal'):
        ap.add_argument('--' + name, type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--faults-reviewed-through', required=True)
    ap.add_argument('--miss-path', choices=('zero-copy', 'streamed'), default='streamed')
    ap.add_argument('--incident-prefix', action='store_true',
                    help='onecard: check first 64 tokens of first 128-token request (sealed ABI limit)')
    ap.add_argument('--authorized-device-window', action='store_true')
    ap.add_argument('--plan', action='store_true')
    return ap


def command(args, identity, manifest):
    out = args.output
    if args.profile == 'tp2':
        return ['/usr/bin/python3', '-B', str(HERE / 'tp2_worker.py'),
                '--identity', str(out / 'identity.json'), '--output', str(out / 'run'),
                '--seconds', str(WATCHDOG[args.profile])]
    bundle = ROOT / manifest['prompts'][0]['input_bundle']
    model = Path(read(bundle / 'input.json')['model_dir']).resolve()
    require(model == Path('/mnt/usb-models/llm-models/unsloth-Qwen3.8-Flash-Next-GGUF-766911a6/UD-IQ3_XXS'),
            'unadmitted model path')
    return ['/usr/bin/ionice', '-c3', identity['binary'], '--authorized-device-window',
            '--card', '0', '--cards', '1', '--context', '4096', '--max-new', '128',
            '--stage', 'decode', '--memory', 'resident', '--miss-path', args.miss_path,
            '--native-nice', '19', '--timing', 'token', '--retain-steps', 'none',
            '--suite-inputs', str(out / 'suite-inputs.tsv'), '--input', str(bundle / 'tokens.txt'),
            '--plan', str(bundle / 'plan.tsv'), '--identity', str(bundle / 'identity.tsv'),
            '--model-dir', str(model), '--selection', str(args.lineage / 'selection.json'),
            '--selection-sha256', identity['selection_sha256'], '--dispatch', identity['dispatch'],
            '--output', str(out / 'run'), '--seconds', str(WATCHDOG[args.profile])]


def memory_admit(profile):
    snapshot = M.meminfo()
    if profile == 'onecard':
        return M.admit(snapshot)
    require(snapshot['MemAvailable'] >= 97 * M.GIB, 'tp2 screen requires 97 GiB available before load')
    return dict(snapshot=snapshot, required_bytes=97 * M.GIB)


def memory_sensor(pid, profile, memory):
    if profile == 'onecard':
        return W.live_memory_sensor(pid, memory['snapshot'].get('GPUActive', 0), budget=memory['plan'])
    sample = SUPPORT.process_tree_anon(pid)
    if not sample['root_seen'] and SUPPORT._exited_status(Path('/proc'), pid):
        sample.update(root_seen=True, root_pf_exiting_or_gone=True)
    host = M.meminfo()
    require(host['MemAvailable'] >= M.HOST_RESERVE, 'host available memory below 8 GiB stop floor')
    sample['host'] = host
    return sample


def prefix_check(output, manifest):
    """Read only complete flushed timing lines; check before native teardown when observable."""
    entry = manifest['prompts'][0]
    path = output / 'run' / entry['prompt_id'] / 'timings.jsonl'
    if not path.exists():
        return None
    raw = path.read_text()
    lines = raw[:raw.rfind('\n') + 1].splitlines()
    rows = [json.loads(line) for line in lines if line]
    tokens = [r['token_id'] for r in rows if r.get('generated_index', 0) > 0][:64]
    if len(tokens) < 64:
        return None
    expected = D.CHECK.token_record(D.ORACLE / 'results' / entry['prompt_id'])
    compare_tokens(tokens, expected, 64, 'incident64')
    return dict(passed=True, tokens_compared=64, mode='first-suite-request-prefix',
                checked_while_owner_live=True, source=str(path.relative_to(output)))


def onecard_summary(output, manifest):
    native = read(output / 'run/receipt.json')
    require(native.get('passed') is True and native.get('safe_to_exit') is True
            and native.get('device_executed') is True and native.get('owner_cards') == 1,
            'native owner failed')
    teardown = native.get('teardown')
    require(isinstance(teardown, list) and len(teardown) == 1, 'one native teardown required')
    owner = teardown[0]
    require(owner.get('safe_to_exit') is True and owner.get('idle_marker_complete') is True
            and all(type(owner.get(k)) is int and owner[k] == 0 for k in ('exit_code', 'live_bytes', 'in_flight')),
            'native owner failed to drain')
    rows = [D.compare_request(output / 'run' / e['prompt_id'], D.ORACLE / 'results' / e['prompt_id'],
                              e, 128, 'none') for e in manifest['prompts']]
    incident = read(output / 'incident64.json')
    return summary(rows, incident, 'onecard')


def unit_gate(text):
    require(any('/user@' in line and line.rsplit('/', 1)[-1].startswith('screen-')
                and line.endswith('.service') for line in text.splitlines()),
            'coordinator-owned screen-* systemd user service required')


def main(argv=None):
    args = parser().parse_args(argv)
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'CPU affinity')
    args.lineage, args.output = args.lineage.resolve(), args.output.resolve()
    require(args.profile != 'onecard' or args.incident_prefix,
            'sealed onecard supports only 12 equal-cap requests; explicit --incident-prefix required')
    require(args.profile != 'tp2' or not args.incident_prefix, 'tp2 uses separate incident64 request')
    require(args.output.is_relative_to(HERE / 'evidence') and not args.output.exists(), 'new screen evidence output required')
    review, through = S.fault_review(args.faults_reviewed_through, time.time_ns() // 1000)
    identity = sealed(args)
    manifest = D.oracle_inputs()
    require(manifest['prompts'][0]['prompt_id'] == 'incident-retrospective', 'incident must be first')
    cmd = command(args, identity, manifest)
    if args.plan:
        print(json.dumps(dict(evidence_label='screen', device_executed=False, identity=identity,
                              command=cmd, model_lifetimes=1, watchdog_seconds=WATCHDOG[args.profile],
                              planned_write_bytes=WRITES[args.profile]), indent=2))
        return 0
    require(args.authorized_device_window, 'coordinator authorization required')
    cgroup = Path('/proc/self/cgroup').read_text()
    unit_gate(cgroup)
    env = W.closed_environment()
    if args.profile == 'onecard':
        env['ONEAPI_DEVICE_SELECTOR'] = 'level_zero:0'
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    latch_path = HERE / ('fault-' + boot + '.json')
    require(not latch_path.exists(), 'screen fault/uncertain-owner latch; coordinator recovery required')
    # Never clear or change a parent's latch, including a latch from another arm.
    for path in (args.lineage / 'build/FAULT.json', args.lineage / ('fault-' + boot + '.json')):
        if path.exists():
            require(read(path).get('boot_id') != boot, 'lineage fault latch requires coordinator recovery')
    SUPPORT.storage(args.output, WRITES[args.profile])
    memory_admit(args.profile)
    args.output.mkdir(parents=True)
    save(args.output / 'identity.json', identity)
    save(args.output / 'suite-manifest.snapshot.json', manifest)
    (args.output / 'suite-inputs.tsv').write_text(''.join(
        f"{e['prompt_id']} {(ROOT/e['input_bundle']/'tokens.txt').resolve()}\n" for e in manifest['prompts']))
    record = label(dict(schema='own-runtime.screen.window.v1', window='screen', passed=False,
        device_executed=False, child_still_running=False, profile=args.profile, boot_id=boot,
        identity=identity, environment=env, coordinator_fault_review=review, systemd_cgroup=cgroup,
        started_utc_ns=time.time_ns(), model_lifetimes=1, internal_cooldown_seconds=0,
        watchdog_seconds=WATCHDOG[args.profile], stop_reasons=[],
        wrapper_sources={str(p.relative_to(ROOT)):sha(p) for p in HERE.glob('*.py')},
        oracle_completion_sha256=sha(D.ORACLE / 'results/completion.json')))
    child, handlers = None, {}
    reasons = record['stop_reasons']
    def persist():
        save(args.output / 'window.json', record)
    def latch(reason):
        save(latch_path, dict(boot_id=boot, output=str(args.output), reason=reason,
                              pid=None if child is None else child.pid))
    persist()
    try:
        with (HERE / 'window.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record['memory_fence'] = W.memory_fence()
            record['clients'] = SUPPORT.gpu_clients() if args.profile == 'tp2' else W.selected_clients(0)
            initial, cursor = S.journal()
            (args.output / 'kernel-boot-before-review.jsonl').write_text(initial)
            initial, cursor = S.journal(cursor, since_us=through)
            (args.output / 'kernel-before.jsonl').write_text(initial)
            require(not S.FAULT.search(initial), 'unreviewed GPU fault')
            record['ldd'] = S.ldd_preflight(Path(identity['binary']), env)
            record['memory_admission'] = memory = memory_admit(args.profile)
            record['memory_fence'] = W.memory_fence()
            record['storage_admission'] = SUPPORT.storage(args.output, WRITES[args.profile])
            record['command'] = cmd
            handlers = {s: signal.signal(s, lambda n, f: reasons.append('coordinator stop ' + str(n)))
                        for s in (signal.SIGTERM, signal.SIGINT)}
            S.ANONYMOUS_LIMIT_BYTES = (memory['plan']['census']['pinned_expert_bytes'] + 4*M.GIB
                                      if args.profile == 'onecard' else 8*M.GIB)
            S.ANONYMOUS_STOP_BYTES = S.ANONYMOUS_LIMIT_BYTES - 256*1024**2
            def sensor(pid):
                if args.profile == 'onecard' and not (args.output / 'incident64.json').exists():
                    incident = prefix_check(args.output, manifest)
                    if incident:
                        save(args.output / 'incident64.json', incident)
                return memory_sensor(pid, args.profile, memory)
            require(not reasons, 'stop requested before launch')
            persist()
            with (args.output / 'native.log').open('w') as log, (args.output / 'kernel-window.jsonl').open('w') as kernel:
                child = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
                record.update(pid=child.pid, process_start_ticks=SUPPORT.process_start(child.pid), device_executed=True)
                persist()
                record.update(S.supervise(child, WATCHDOG[args.profile], cursor, kernel, reasons, latch, persist,
                                          memory_sensor=sensor, observe_memory=record.update,
                                          drain_seconds=90, read_journal=S.journal))
            if record['child_still_running']:
                record['child_retained'] = True
                persist()
                return 75
            require(not reasons and child.returncode == 0, 'screen failed or interrupted')
            result = onecard_summary(args.output, manifest) if args.profile == 'onecard' else read(args.output / 'run/summary.json')
            require(result.get('passed') is True, 'screen exactness/teardown failed')
            save(args.output / 'summary.json', label(result))
            record.update(passed=True, finished_utc_ns=time.time_ns(),
                          elapsed_seconds=(time.time_ns()-record['started_utc_ns'])/1e9,
                          files={str(p.relative_to(args.output)):sha(p) for p in args.output.rglob('*')
                                 if p.is_file() and p.name != 'window.json'})
            persist()
            return 0
    except Exception as error:
        reasons.append(str(error))
        if child is not None and child.poll() is None:
            child.send_signal(signal.SIGTERM)
            record.update(child_still_running=True, child_retained=True)
            latch('supervision failed; SIGTERM requested; owner retained')
        elif child is not None or S.FAULT.search(str(error)):
            latch(str(error))
        persist()
        return 75 if record.get('child_still_running') else 1
    finally:
        for s, handler in handlers.items():
            signal.signal(s, handler)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit('REFUSED: ' + str(error))
