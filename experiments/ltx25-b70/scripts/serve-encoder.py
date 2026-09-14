#!/usr/bin/env python3
"""One persistent encoder experiment server. No stop/restart/retry operations."""
import argparse
import datetime
import fcntl
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

FAULT = re.compile(r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump', re.I)


def write_json(path, value):
    with path.open('x') as handle:
        handle.write(json.dumps(value, indent=2) + '\n')


def server_args(packet, run):
    return [str(packet / 'source/main.py'), '--listen', '127.0.0.1', '--port', '8188',
            '--disable-auto-launch', '--cache-none', '--deterministic',
            '--disable-async-offload', '--disable-dynamic-vram', '--disable-comfy-compiler',
            '--disable-cuda-graphs', '--disable-pinned-memory', '--reserve-vram', '6',
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


def launch(packet, digest, run_name, check_only=False):
    manifest, run = prepare_start(packet, digest, run_name)
    if check_only:
        print(json.dumps({'status': 'inactive-startup-check-passed', 'run_dir': str(run),
                          'packet_manifest_sha256': digest, 'server_args': server_args(packet, run),
                          'limits': 'No device discovery, locks, process changes or GPU work; exclusive preflight occurs only at launch'}, indent=2))
        return
    # Ownership gates precede Torch import/device discovery and output creation.
    locks = []
    for name in ['/run/lock/muse-glimmer-gpu-exclusive.lock', '/tmp/b70-benchmark.lock'] + [
            f'/tmp/b70-gpu{i}.lock' for i in range(4)]:
        handle = open(name, 'a')
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locks.append(handle)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 8188))
    common.require(not subprocess.check_output(['docker', 'ps', '-q'], text=True, timeout=10).strip(),
                   'A container is running; inspect ownership')
    nodes = list(Path('/dev/dri').glob('renderD*'))
    common.require(len(nodes) == 4, 'Expected four render devices')
    owners = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, text=True, timeout=10)
    common.require(owners.returncode == 1 and not owners.stdout.strip() and not owners.stderr.strip(),
                   'Render devices are owned or ownership check failed')
    before = subprocess.check_output(['journalctl', '-k', '-b', '--no-pager'], text=True, timeout=10)
    common.require(not FAULT.search(before), 'Device fault in current boot')
    common.verify_model_receipt()
    run.mkdir()
    (run / 'user').mkdir()
    (run / 'temp').mkdir()
    (run / 'input').mkdir()
    (run / 'journal-before.txt').write_text(before)
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
                fault('Kernel device fault', journal)
                return
            time.sleep(5)

    for key in ['ZE_AFFINITY_MASK', 'ONEAPI_DEVICE_SELECTOR', 'SYCL_DEVICE_FILTER']:
        common.require(not os.environ.get(key), 'Unexpected device filter: ' + key)
    os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false',
                      OMP_NUM_THREADS='16', MKL_NUM_THREADS='16', LTX_ENCODER_RUN_DIR=str(run))
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
            fault('Device fault during preflight', journal)
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
                'launcher_sha256': common.sha(Path(__file__)),
                'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
                'server_args_sha256': common.sha(run / 'server-args.json')}
    write_json(run / 'server-identity.json', identity)
    os.environ['LTX_ENCODER_IDENTITY_SHA256'] = common.sha(run / 'server-identity.json')
    os.chdir(packet / 'source')
    sys.path.insert(0, str(packet / 'source'))
    sys.path.insert(0, str(packet / 'source/scripts'))
    sys.argv = argv
    import comfy.options
    comfy.options.enable_args_parsing()
    runpy.run_path(str(packet / 'source/main.py'), run_name='__main__')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    launch(args.packet, args.manifest_sha256, args.run_name, args.check_only)
