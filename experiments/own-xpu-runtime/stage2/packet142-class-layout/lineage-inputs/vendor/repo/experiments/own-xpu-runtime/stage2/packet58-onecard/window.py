#!/usr/bin/env python3
"""Coordinator-only packet58 single-card windows. Import and --help are CPU only."""
import argparse
import fcntl
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

import memory_plan as M

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
_spec = importlib.util.spec_from_file_location('packet58_supervision', HERE.parent / 'packet56-draft-prefix/p56_head_support.py')
SUPPORT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SUPPORT)
S = SUPPORT.SUPERVISION
require, sha, save = S.require, S.sha, S.save
PCI = {0: '0000:23:00.0', 2: '0000:43:00.0'}
# Expected durations are conservative planning bounds, not speed measurements.
CONFIG = {'K1': (120, 600), 'KD': (600, 1800), 'W2m': (600, 1800),
          'WS': (1200, 3600), 'WS128x': (1200, 3600), 'WS128': (1200, 3600)}
WRITES = {'K1': 128*1024**2, 'KD': 512*1024**2, 'W2m': 512*1024**2,
          'WS': 1024**3, 'WS128x': 256*1024**2, 'WS128': 256*1024**2}
PREVIOUS = {'KD': 'K1', 'W2m': 'KD', 'WS': 'W2m', 'WS128x': 'WS', 'WS128': 'WS128x'}


def closed_environment(source=None):
    env = dict(os.environ if source is None else source)
    require(set(env) <= {'PATH', 'LD_LIBRARY_PATH', 'LC_CTYPE', 'OMP_NUM_THREADS'}, 'closed environment required')
    require(env.get('PATH', '/usr/bin:/bin') == '/usr/bin:/bin', 'fixed PATH required')
    require(env.get('OMP_NUM_THREADS', '2') == '2', 'OMP_NUM_THREADS=2 required')
    return S.environment_gate({k:v for k,v in env.items() if k not in ('PATH', 'OMP_NUM_THREADS')})


def memory_fence(sysroot=Path('/sys/devices/system/memory')):
    states = {str(n): (sysroot / f'memory{n}' / 'state').read_text().strip() for n in range(53, 58)}
    require(all(states[str(n)] == 'offline' for n in (54, 56)), 'failing memory blocks 54/56 must remain offline')
    return states  # Other three blocks are best-effort margin under the service contract.


def selected_clients(card, proc=Path('/proc')):
    selected, other, hidden = [], [], 0
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        try:
            infos = list((pid / 'fdinfo').iterdir())
        except PermissionError:
            hidden += 1
            continue
        except FileNotFoundError:
            continue
        for info in infos:
            try:
                fields = dict(line.split(':', 1) for line in info.read_text().splitlines() if ':' in line)
            except PermissionError:
                hidden += 1
                continue
            except (FileNotFoundError, ProcessLookupError):
                continue
            if fields.get('drm-driver', '').strip() == 'xe':
                pci = fields.get('drm-pdev', '').strip()
                row = dict(pid=int(pid.name), fd=info.name, pci=pci)
                (selected if pci == PCI[card] or not pci else other).append(row)
    require(not selected, 'selected card owned or client identity missing: ' + str(selected))
    return dict(selected=selected, other=other, inaccessible_entries=hidden,
                hidden_clients_require_coordinator_ownership=True)


def safe_path(root, name):
    rel = Path(name)
    path = (root / rel).resolve()
    require(not rel.is_absolute() and '..' not in rel.parts and path.is_relative_to(root.resolve()), 'unsafe identity path')
    return path


def verify_files(root, files):
    require(isinstance(files, dict) and bool(files), 'empty file identity')
    for name, digest in files.items():
        require(sha(safe_path(root, name)) == digest, 'identity changed: ' + name)


def build_gate():
    path = HERE / 'build-receipt.json'
    row = json.loads(path.read_text())
    require(row.get('schema') == 'own-runtime.packet58.build.v1' and row.get('passed') is True
            and row.get('device_executed') is False, 'CPU build receipt incomplete')
    verify_files(REPO, row.get('sources'))
    verify_files(HERE, row.get('artifacts'))
    verify_files(HERE, row.get('gates'))
    require({'build/device/own-rt-iq3', 'build/device/p58-cache-fixtures'} <= set(row['artifacts']), 'both native binaries must be bound')
    for name in row['gates']:
        gate = json.loads(safe_path(HERE, name).read_text())
        require(gate.get('passed') is True and gate.get('device_executed') is False, 'CPU gate failed: ' + name)
    return row


def prerequisite(path, name, identity):
    require(path is not None, 'missing prerequisite ' + name)
    path = Path(path).resolve()
    row = json.loads(path.read_text())
    require(row.get('schema') == 'own-runtime.packet58.window.v1' and row.get('passed') is True
            and row.get('device_executed') is True and row.get('child_still_running') is False
            and row.get('window') == name and row.get('stop_reasons') == []
            and row.get('qualifying') is (name != 'K1'), 'invalid prerequisite ' + name)
    for key in ('boot_id', 'build_receipt_sha256', 'artifacts_sha256', 'environment', 'card', 'context', 'gpu_count'):
        require(row.get(key) == identity.get(key), 'prerequisite differs: ' + key)
    require(type(row.get('pid')) is int and row['pid'] > 0
            and type(row.get('process_start_ticks')) is int and row['process_start_ticks'] > 0, 'fresh owner identity missing')
    closure = {'summary.json', 'kernel-before.jsonl', 'kernel-window.jsonl'}
    if name == 'K1':
        closure |= {'run/k1.json', 'run/k1-cases.jsonl'}
    else:
        closure |= {str(p.relative_to(path.parent)) for p in (path.parent/'run').rglob('*') if p.is_file()}
        require({'run/receipt.json', 'run/summary.json', 'run/run/receipt.json'} <= closure, 'model prerequisite receipt closure missing')
    require(set(row.get('native_files', {})) == closure, 'prerequisite native closure incomplete')
    verify_files(path.parent, row.get('native_files'))
    for leaf in ('kernel-before.jsonl', 'kernel-window.jsonl'):
        require(not S.FAULT.search((path.parent/leaf).read_text()), 'prerequisite kernel fault')
    return row


def cpu_k1_digest():
    row = json.loads((HERE/'k1-cpu.json').read_text())
    require(row.get('passed') is True and row.get('device_executed') is False,
            'CPU production fixture receipt missing')
    return row.get('exact_output_sha256')


def k1_summary(native, cpu_digest=None):
    require(native.get('passed') is True and native.get('zero_copy_bytes_equal') is True
            and native.get('mixed_bytes_equal') is True and native.get('streamed_bytes_equal') is True, 'K1 byte equality failed')
    require(native.get('safe_to_exit') is True and native.get('device_executed') is True
            and native.get('zero_copy_supported') is True, 'K1 device support or teardown unproved')
    digest = native.get('exact_output_sha256')
    require(isinstance(digest, str) and len(digest) == 64
            and all(c in '0123456789abcdef' for c in digest), 'K1 exact output hash missing')
    require(digest == (cpu_k1_digest() if cpu_digest is None else cpu_digest), 'K1 differs from CPU production kernel bytes')
    require(native.get('cold_rotation') is True and type(native.get('working_set_bytes')) is int
            and native['working_set_bytes'] >= 128*1024**2, 'K1 must rotate cold host backing')
    size = native.get('bytes_per_iteration')
    require(isinstance(size, int) and size > 0, 'K1 useful bytes missing')
    times = {k: native.get(k) for k in ('host_ms', 'vram_ms', 'streamed_ms')}
    require(all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in times.values()), 'K1 invalid timing')
    bandwidth = size / (times['host_ms'] * 1e6)
    return dict(**native, zero_copy_useful_GB_s=bandwidth,
                selected_miss_path='zero-copy' if bandwidth >= 12.5 else 'streamed',
                selection_threshold_GB_s=12.5, threshold_basis='half packet55 measured 25 GB/s copy floor',
                microbenchmark_only=True, model_speed_claim=False)


def selected_miss_path(paths, identity):
    require(paths is not None and len(paths) == 2 and Path(paths[0]).resolve() != Path(paths[1]).resolve(), 'two distinct fresh K1 windows required')
    rows = [prerequisite(path, 'K1', identity) for path in paths]
    require(len({(r['pid'], r['process_start_ticks']) for r in rows}) == 2, 'K1 owners not fresh')
    summaries = [k1_summary(json.loads((Path(path).parent / 'run/k1.json').read_text())) for path in paths]
    require(summaries[0]['exact_output_sha256'] == summaries[1]['exact_output_sha256'], 'K1 fresh-process output bytes differ')
    return 'zero-copy' if all(r['selected_miss_path'] == 'zero-copy' for r in summaries) else 'streamed'


def native_command(args, output, miss_path):
    if args.window == 'K1':
        return [str(HERE/'build/device/p58-cache-fixtures'), '--card', '0', '--output', str(output/'run'),
                '--iterations', '20', '--authorized-device-window']
    return ['/usr/bin/python3', '-B', str(HERE/'suite_driver.py'), '--window', args.window,
            '--card', str(args.card), '--output', str(output/'run'), '--miss-mode', 'zerocopy' if miss_path == 'zero-copy' else 'streamed',
            '--authorized-device-window']


def user_unit_gate(cgroup):
    paths = [line.split(':', 2)[-1] for line in cgroup.splitlines()]
    require(any('/user@' in p and p.rsplit('/', 1)[-1].startswith('packet58-') and p.endswith('.service') for p in paths),
            'coordinator-owned packet58-* systemd user service required')


def live_memory_sensor(pid, baseline_gpuactive=0, *, full_model=True, budget=None):
    sample = SUPPORT.process_tree_anon(pid)
    # exit_mm drops anonymous fields before waitpid observes the dead task.
    if not sample['root_seen'] and SUPPORT._exited_status(Path('/proc'), pid):
        sample['root_seen'] = True
        sample['root_pf_exiting_or_gone'] = True
    snapshot = M.meminfo()
    sample['host'] = snapshot
    require(snapshot['MemAvailable'] >= M.HOST_RESERVE, 'host available memory below 8 GiB stop floor')
    shadow = max(0, snapshot.get('GPUActive', 0) - baseline_gpuactive)
    require(shadow <= (budget if budget is not None else M.plan())['device_owned_bound_bytes'] if full_model else shadow <= 4*M.GIB,
            'GPUActive shadow exceeds admitted bound')
    sample['gpuactive_growth_bytes'] = shadow
    return sample


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window', choices=tuple(CONFIG), required=True)
    parser.add_argument('--card', type=int, choices=(0, 2), default=0)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--k1', type=Path, action='append')
    parser.add_argument('--faults-reviewed-through', required=True)
    parser.add_argument('--authorized-device-window', action='store_true')
    args = parser.parse_args(argv)
    require(args.authorized_device_window, 'coordinator device-window authorization required')
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice 19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(4,16)) | set(range(20,32)), 'restricted affinity required')
    cgroup = Path('/proc/self/cgroup').read_text()
    user_unit_gate(cgroup)
    env = closed_environment()
    env['ONEAPI_DEVICE_SELECTOR'] = 'level_zero:' + str(args.card)
    build = build_gate()
    output = args.output.resolve()
    require(output.is_relative_to((HERE/'evidence').resolve()) and not output.exists(), 'new packet58 evidence output required')
    budget = M.plan()
    memory = M.admit(M.meminfo(), budget) if args.window != 'K1' else dict(snapshot=M.meminfo())
    if args.window == 'K1':
        require(memory['snapshot']['MemAvailable'] >= 12*M.GIB, 'K1 needs 12 GiB available')
    storage = SUPPORT.storage(output, WRITES[args.window])
    build_bytes = sum(p.stat().st_size for p in (HERE/'build').rglob('*') if p.is_file())
    require(build_bytes <= 1_500_000_000, 'packet58 build exceeds 1.5 GB')
    review, through = S.fault_review(args.faults_reviewed_through, time.time_ns()//1000)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    latch_path = HERE / ('fault-'+boot+'.json')
    require(not latch_path.exists(), 'retained fault/uncertain-owner latch; coordinator recovery required')
    record = dict(schema='own-runtime.packet58.window.v1', window=args.window, passed=False, qualifying=False,
                  device_executed=False, child_still_running=False, card=args.card, pci_bdf=PCI[args.card],
                  native_visible_card=0, context=4096, gpu_count=1, decode_mode='plain',
                  boot_id=boot, build_receipt_sha256=sha(HERE/'build-receipt.json'),
                  artifacts_sha256=build['artifacts'], environment=env, coordinator_fault_review=review,
                  started_utc_ns=time.time_ns(), expected_seconds=CONFIG[args.window][0],
                  watchdog_seconds=CONFIG[args.window][1], memory_admission=memory,
                  storage_admission=storage, systemd_cgroup=cgroup)
    if args.window in PREVIOUS:
        previous = prerequisite(args.previous, PREVIOUS[args.window], record)
        record['previous'] = dict(path=str(args.previous.resolve()), sha256=sha(args.previous))
    miss_path = None if args.window == 'K1' else selected_miss_path(args.k1, record)
    if args.window not in ('K1', 'KD'):
        require(previous.get('miss_path') == miss_path, 'miss path differs from previous full-model gate')
    record['miss_path'] = miss_path
    if args.k1:
        record['k1_refs'] = [dict(path=str(p.resolve()), sha256=sha(p),
            native_k1_sha256=sha(p.parent/'run/k1.json')) for p in args.k1]
    output.mkdir(parents=True)
    reasons, child, handlers = [], None, {}
    record['stop_reasons'] = reasons
    def persist():
        save(output/'window.json', record)
    def latch(reason):
        if child is not None or S.FAULT.search(reason):
            save(latch_path, dict(boot_id=boot, reason=reason, output=str(output), pid=None if child is None else child.pid))
    persist()
    try:
        with (HERE/'window.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            record['memory_fence'] = memory_fence()
            record['clients'] = selected_clients(args.card)
            initial, cursor = S.journal()
            (output/'kernel-boot-before-review.jsonl').write_text(initial)
            initial, cursor = S.journal(cursor, since_us=through)
            (output/'kernel-before.jsonl').write_text(initial)
            require(not S.FAULT.search(initial), 'unreviewed GPU fault')
            binary = HERE/'build/device'/('p58-cache-fixtures' if args.window == 'K1' else 'own-rt-iq3')
            record['ldd'] = S.ldd_preflight(binary, env)
            # Recheck after locks, prerequisite hashing and journal preflight.
            memory = M.admit(M.meminfo(), budget) if args.window != 'K1' else dict(snapshot=M.meminfo())
            if args.window == 'K1':
                require(memory['snapshot']['MemAvailable'] >= 12*M.GIB, 'K1 needs 12 GiB available')
            record['memory_admission'] = memory
            record['memory_fence'] = memory_fence()
            record['storage_admission'] = SUPPORT.storage(output, WRITES[args.window])
            command = native_command(args, output, miss_path)
            record['command'] = command
            handlers = {sig: signal.signal(sig, lambda signum, frame: reasons.append('coordinator stop '+str(signum))) for sig in (signal.SIGTERM, signal.SIGINT)}
            # Private inherited supervisor constants: full pinned experts are expected,
            # unlike the predecessor's small-fixture 8-GiB anonymous ceiling.
            S.ANONYMOUS_LIMIT_BYTES = budget['census']['pinned_expert_bytes'] + 4*M.GIB if args.window != 'K1' else 4*M.GIB
            S.ANONYMOUS_STOP_BYTES = S.ANONYMOUS_LIMIT_BYTES - 256*1024**2
            with (output/'native.log').open('w') as log, (output/'kernel-window.jsonl').open('w') as kernel:
                child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
                record.update(pid=child.pid, process_start_ticks=SUPPORT.process_start(child.pid), device_executed=True)
                persist()
                sensor = lambda pid: live_memory_sensor(pid, memory['snapshot'].get('GPUActive',0), full_model=args.window!='K1', budget=budget)
                record.update(S.supervise(child, CONFIG[args.window][1], cursor, kernel, reasons, latch, persist,
                    observe_memory=record.update, memory_sensor=sensor))
            if record['child_still_running']:
                record['child_retained'] = True
                persist()
                return 75
            require(not reasons and child.returncode == 0, 'native window failed or interrupted')
            if args.window == 'K1':
                summary = k1_summary(json.loads((output/'run/k1.json').read_text()))
                record['native_files'] = {name:sha(output/name) for name in ('run/k1.json', 'run/k1-cases.jsonl')}
            else:
                receipt = json.loads((output/'run/receipt.json').read_text())
                require(receipt.get('passed') is True and receipt.get('safe_to_exit') is True
                        and receipt.get('window') == args.window, 'native driver receipt incomplete')
                summary = json.loads((output/'run/summary.json').read_text())
                record['native_files'] = {str(p.relative_to(output)):sha(p) for p in (output/'run').rglob('*') if p.is_file()}
            save(output/'summary.json', summary)
            record['native_files']['summary.json'] = sha(output/'summary.json')
            for leaf in ('kernel-before.jsonl', 'kernel-window.jsonl'):
                record['native_files'][leaf] = sha(output/leaf)
            record.update(passed=True, qualifying=args.window!='K1', finished_utc_ns=time.time_ns())
            persist()
            return 0
    except Exception as error:
        reasons.append(str(error))
        if child is not None and child.poll() is None:
            record.update(child_still_running=True, child_retained=True)
            latch('supervision failed; live child retained for coordinator')
        persist()
        return 75 if record.get('child_still_running') else 1
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)

if __name__ == '__main__':
    raise SystemExit(main())
