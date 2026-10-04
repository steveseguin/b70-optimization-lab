#!/usr/bin/env python3
"""One persistent encoder experiment server. No stop/restart/retry operations.

Packet 93 adds one option, --health-receipt <path> (owner rule of 2026-10-03,
AGENTS.md "One fault does not end the session"). Without it the launcher
behaves exactly as before: any fault line in the whole boot's kernel journal
refuses the start. With it, the launcher verifies the receipt written by
scripts/check-four-card-health.py (schema ltx.four-card-health.v1, passed,
four passing cards, the running boot, end_utc no older than 6 hours and not in
the future), copies it into the run directory, records the earlier fault lines
it admits (journal-admitted-faults.txt), and applies the no-fault-line check
only to the journal since the receipt's end_utc. Any fault line after the
receipt still refuses; the in-run journal watcher is unchanged.
"""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import socket
import subprocess
import sys
import threading
import time

# Set before importing packet-local modules, including in --check-only mode.
sys.dont_write_bytecode = True
import encoder_runtime_common as common

# Additive host-kernel incident detection; no recovery or restart behavior.
FAULT = re.compile(
    r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump|'
    r'\bBUG:[ \t]+soft lockup[ \t]+-[ \t]+CPU#\d+[ \t]+stuck for[ \t]+\d+(?:\.\d+)?s!|'
    r'\bINFO:[ \t]+rcu_(?:preempt|sched|bh|tasks(?:_rude|_trace)?)[ \t]+(?:self-)?detected[ \t]+(?:expedited[ \t]+)?stalls?[ \t]+on[ \t]+(?:CPUs?(?:/tasks)?|tasks)\b|'
    r'\brcu_(?:preempt|sched|bh|tasks(?:_rude|_trace)?)[ \t]+kthread starved for[ \t]+\d+[ \t]+jiffies\b|'
    r'\bINFO:[ \t]+task[ \t]+[^\r\n]+:\d+[ \t]+blocked for more than[ \t]+\d+(?:\.\d+)?[ \t]+seconds\.'
    , re.I)


HEALTH_SCHEMA = 'ltx.four-card-health.v1'
HEALTH_MAX_AGE = datetime.timedelta(hours=6)
HEALTH_CLOCK_SKEW = datetime.timedelta(minutes=2)


def parse_utc(text):
    return datetime.datetime.strptime(text, '%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=datetime.timezone.utc)


def verify_health_receipt(receipt, boot_id, now):
    """Return the receipt's end time if it admits a same-boot start, else raise."""
    common.require(isinstance(receipt, dict) and receipt.get('schema') == HEALTH_SCHEMA,
                   'Health receipt schema is not ' + HEALTH_SCHEMA)
    common.require(receipt.get('passed') is True, 'Health receipt did not pass')
    cards = receipt.get('cards')
    common.require(receipt.get('device_count') == 4 and isinstance(cards, list) and len(cards) == 4 and
                   all(isinstance(c, dict) and c.get('pass') is True for c in cards),
                   'Health receipt does not show four passing cards')
    common.require(not receipt.get('journal_fault_lines_during_probe'),
                   'Health receipt saw fault lines during its own probe')
    common.require(receipt.get('boot_id') == boot_id, 'Health receipt is from another boot')
    try:
        end = parse_utc(receipt['end_utc'])
    except (KeyError, TypeError, ValueError):
        raise RuntimeError('Health receipt has no readable end_utc')
    common.require(end <= now + HEALTH_CLOCK_SKEW, 'Health receipt end_utc is in the future')
    common.require(now - end <= HEALTH_MAX_AGE, 'Health receipt is older than 6 hours')
    return end


def load_health_receipt(path):
    common.require(path is not None, 'No health receipt given')
    path = Path(path)
    common.require(path.is_absolute() and path.is_file() and not path.is_symlink(),
                   'Health receipt must be an absolute path to a regular file')
    data = path.read_bytes()
    return json.loads(data), data


def fault_lines(journal):
    return [line for line in journal.splitlines() if FAULT.search(line)]


def admit_journal(whole_boot, since_receipt):
    """Same-boot admission: refuse on any fault line after the receipt; return the
    earlier fault lines being admitted."""
    later = fault_lines(since_receipt)
    common.require(not later, 'Kernel device or host fault after the health receipt: ' + (later[:1] or [''])[0][:200])
    return fault_lines(whole_boot)


def write_json(path, value):
    with path.open('x') as handle:
        handle.write(json.dumps(value, indent=2) + '\n')


def server_args(packet, run):
    return [str(packet / 'source/main.py'), '--listen', '127.0.0.1', '--port', '8188',
            '--disable-auto-launch', '--cache-none', '--deterministic',
            '--disable-async-offload', '--disable-dynamic-vram', '--disable-comfy-compiler',
            '--disable-cuda-graphs', '--disable-pinned-memory', '--reserve-vram', '2',
            '--bf16-unet', '--bf16-text-enc', '--bf16-vae', '--use-pytorch-cross-attention',
            '--disable-xformers', '--disable-api-nodes', '--extra-model-paths-config',
            str(packet / 'model-paths.yaml'), '--output-directory', str(common.ROOT / 'output'),
            '--user-directory', str(run / 'user'), '--temp-directory', str(run / 'temp'),
            '--input-directory', str(run / 'input'),
            '--disable-all-custom-nodes', '--whitelist-custom-nodes', *common.NODES]


def prepare_start(packet, digest, run_name):
    common.require(re.fullmatch(r'encoder-server-[a-z0-9-]+', run_name), 'Invalid run name')
    run = common.ROOT / run_name
    common.require(not run.exists() and not run.is_symlink(), 'Run directory already exists')
    manifest = common.verify_packet(packet, digest)
    common.verify_runtime(manifest['runtime'])
    common.verify_model_receipt()
    common.require(common.sha(Path(__file__)) == manifest['startup_tools']['serve-encoder.py'],
                   'Launcher differs from packet')
    common.require(common.sha(Path(common.__file__)) == manifest['startup_tools']['encoder_runtime_common.py'],
                   'Identity checker differs from packet')
    common.require(shutil.disk_usage(common.ROOT).free >= 5 * 1024**3, 'Less than 5 GiB disk available')
    memory = {row.split(':')[0]: int(row.split()[1]) for row in Path('/proc/meminfo').read_text().splitlines()}
    common.require(memory['MemAvailable'] >= 16 * 1024**2, 'Less than 16 GiB RAM available')
    return manifest, run


def launch(packet, digest, run_name, check_only=False, health_receipt=None):
    manifest, run = prepare_start(packet, digest, run_name)
    health = None
    if health_receipt is not None:
        receipt, receipt_bytes = load_health_receipt(health_receipt)
        boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        receipt_end = verify_health_receipt(receipt, boot_id, datetime.datetime.now(datetime.timezone.utc))
        health = {'path': str(Path(health_receipt)), 'sha256': hashlib.sha256(receipt_bytes).hexdigest(),
                  'end_utc': receipt['end_utc'], 'boot_id': boot_id}
    if check_only:
        result = {'status': 'inactive-startup-check-passed', 'run_dir': str(run),
                  'packet_manifest_sha256': digest, 'server_args': server_args(packet, run),
                  'limits': 'No device discovery, locks, process changes or GPU work; exclusive preflight occurs only at launch'}
        if health is not None:
            result['health_receipt'] = dict(health, verified='schema, passed, four cards, boot id, age; '
                                            'the journal-since-receipt check runs only at launch')
        print(json.dumps(result, indent=2))
        return
    # Ownership gates precede Torch import/device discovery and output creation.
    locks = []
    for name in ['/run/lock/muse-glimmer-gpu-exclusive.lock', '/tmp/b70-benchmark.lock'] + [
            f'/tmp/b70-gpu{i}.lock' for i in range(4)]:
        handle = open(name, 'a')
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locks.append(handle)
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', 8188))
    common.require(not subprocess.check_output(['docker', 'ps', '-q'], text=True, timeout=10).strip(),
                   'A container is running; inspect ownership')
    nodes = list(Path('/dev/dri').glob('renderD*'))
    common.require(len(nodes) == 4, 'Expected four render devices')
    owners = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, text=True, timeout=10)
    common.require(owners.returncode == 1 and not owners.stdout.strip() and not owners.stderr.strip(),
                   'Render devices are owned or ownership check failed')
    before = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager'], text=True, timeout=10)
    admitted = None
    if health is None:
        common.require(not FAULT.search(before), 'Kernel device or host fault in current boot')
    else:
        # Re-verify at the moment of launch (age), then check only the journal
        # since the receipt's end. journalctl's --since is inclusive of that
        # second, so a line logged in the receipt's last second also refuses.
        receipt_end = verify_health_receipt(receipt, health['boot_id'], datetime.datetime.now(datetime.timezone.utc))
        since_receipt = subprocess.check_output(['journalctl', '-k', '-b', '--since', receipt['end_utc'],
                                                 '--no-pager'], text=True, timeout=10)
        admitted = admit_journal(before, since_receipt)
    common.verify_model_receipt()
    run.mkdir()
    (run / 'user').mkdir()
    (run / 'temp').mkdir()
    (run / 'input').mkdir()
    (run / 'journal-before.txt').write_text(before)
    if health is not None:
        (run / 'health-receipt.json').write_bytes(receipt_bytes)
        (run / 'journal-since-health-receipt.txt').write_text(since_receipt)
        (run / 'journal-admitted-faults.txt').write_text(
            '# Fault lines earlier in this boot, admitted by the health receipt %s (sha256 %s, end_utc %s)\n'
            % (health['path'], health['sha256'], health['end_utc']) + ''.join(line + '\n' for line in admitted))
        health['admitted_fault_lines'] = len(admitted)
    since = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

    def fault(reason, journal=None):
        if journal is not None:
            (run / 'journal-fault.txt').write_text(journal)
        target = common.ROOT / 'FAULT.json'
        try:
            write_json(target, {'reason': reason, 'time': time.time(), 'run': str(run)})
        except FileExistsError:
            pass
        if 'comfy.model_management' in sys.modules:
            sys.modules['comfy.model_management'].interrupt_current_processing(True)
        print('FAULT: halt new requests; preserve process for incident review', flush=True)

    def watch_journal():
        while True:
            try:
                journal = subprocess.check_output(['journalctl', '-k', '-b', '--since', since,
                                                   '--no-pager'], text=True, timeout=10)
            except (subprocess.SubprocessError, OSError) as error:
                fault('Journal observation failed: ' + str(error))
                return
            if FAULT.search(journal):
                fault('Kernel device or host fault', journal)
                return
            time.sleep(5)

    for key in ['ZE_AFFINITY_MASK', 'ONEAPI_DEVICE_SELECTOR', 'SYCL_DEVICE_FILTER']:
        common.require(not os.environ.get(key), 'Unexpected device filter: ' + key)
    os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false',
                      OMP_NUM_THREADS='16', MKL_NUM_THREADS='16', LTX_ENCODER_RUN_DIR=str(run))
    # Compiler-only successor: one worker and caches outside immutable source.
    compiler_environment = {'TORCHINDUCTOR_COMPILE_THREADS': '1',
                            'TORCHINDUCTOR_CACHE_DIR': str(run / 'inductor-cache'),
                            'TRITON_CACHE_DIR': str(run / 'triton-cache')}
    os.environ.update(compiler_environment)
    sys.dont_write_bytecode = True
    threading.Thread(target=watch_journal, daemon=True).start()
    import torch
    common.require(torch.__version__ == manifest['runtime']['torch'], 'Torch import version mismatch')
    torch.set_num_threads(16)
    torch.use_deterministic_algorithms(True, warn_only=False)
    devices = []
    try:
        common.require(torch.xpu.device_count() == 4, 'Expected four XPU devices')
        for i in range(4):
            common.verify_model_receipt()
            value = torch.ones((1024, 1024), device=f'xpu:{i}')
            common.require(float((value + 1).sum().cpu()) == 2097152.0, 'Startup copy/compute mismatch')
            torch.xpu.synchronize(i)
            devices.append({'ordinal': i, 'properties': str(torch.xpu.get_device_properties(i)),
                            'copy_compute': 'passed'})
            del value
        torch.xpu.set_device(0)
        journal = subprocess.check_output(['journalctl', '-k', '-b', '--since', since, '--no-pager'], text=True, timeout=10)
        (run / 'journal-after-preflight.txt').write_text(journal)
        if FAULT.search(journal):
            fault('Kernel device or host fault during preflight', journal)
        common.verify_model_receipt()
    except Exception as error:
        fault('Startup preflight failed: ' + repr(error))
        raise
    argv = server_args(packet, run)
    write_json(run / 'server-args.json', argv)
    identity = {'pid': os.getpid(), 'proc_start_ticks': common.process_ticks(os.getpid()),
                'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'start_utc': since, 'devices': devices, 'torch': torch.__version__,
                'runtime': manifest['runtime'], 'source_commit': common.PIN,
                'source_packet_path': str(packet), 'source_packet_manifest_sha256': digest,
                'encoder_run_dir': str(run), 'extension_sha256s': manifest['extension_sha256s'],
                'compiler_environment': compiler_environment,
                'launcher_sha256': common.sha(Path(__file__)),
                'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
                'server_args_sha256': common.sha(run / 'server-args.json')}
    if health is not None:
        identity['health_admission'] = health
    write_json(run / 'server-identity.json', identity)
    os.environ['LTX_ENCODER_IDENTITY_SHA256'] = common.sha(run / 'server-identity.json')
    os.chdir(packet / 'source')
    sys.path.insert(0, str(packet / 'source'))
    sys.path.insert(0, str(packet / 'source/scripts'))
    sys.argv = argv
    import comfy.options
    comfy.options.enable_args_parsing()
    # Comfy's import selects warn_only=True. Restore the original strict
    # baseline only after that import, before main can execute any graph.
    import comfy.model_management
    torch.use_deterministic_algorithms(True, warn_only=False)
    common.require(torch.are_deterministic_algorithms_enabled() and
                   not torch.is_deterministic_algorithms_warn_only_enabled(),
                   'Strict deterministic mode was not restored after Comfy import')
    write_json(run / 'determinism-after-import.json', {
        'enabled': torch.are_deterministic_algorithms_enabled(),
        'warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
        'stage': 'after_model_management_import_before_main',
        'server_identity_sha256': os.environ['LTX_ENCODER_IDENTITY_SHA256']})
    runpy.run_path(str(packet / 'source/main.py'), run_name='__main__')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--health-receipt', type=Path, default=None,
                        help='same-boot admission after a passed four-card health probe (packet 93)')
    args = parser.parse_args()
    launch(args.packet, args.manifest_sha256, args.run_name, args.check_only, args.health_receipt)
