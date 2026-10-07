#!/usr/bin/env python3
"""One pinned R276 container pilot; no retries, settings changes or hard kills."""
import argparse
import datetime
import fcntl
import grp
import uuid
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

REPO = Path(__file__).resolve().parents[3]
PYTHON = '/home/steve/.venvs/vllm-xpu/bin/python'
IMAGE = 'sha256:521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad'
MODEL_ROOT = '/dev/shm/qwen38-27b-fp8-worker-20261007'
MODEL = MODEL_ROOT
MODEL_MANIFEST = Path(__file__).with_name('model-manifest.json')
MODEL_REVISION = '017b9c7af6b5689d5dd426a76e0bc077eb5ca20a'
FAULT = re.compile(r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump|Timedout job|wedged|Out of memory: Killed process', re.I)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    interrupted = []
    def request_stop(signum, frame):
        interrupted.append(signum)
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    signalled = set()
    def graceful_stop(child):
        if child.poll() is None and child.pid not in signalled:
            signalled.add(child.pid)
            try: child.send_signal(signal.SIGINT)
            except ProcessLookupError: pass
        child.wait()  # Hold all locks until exit; never escalate or retry.
    def save(name, value):
        with (out / name).open('w') as stream:
            json.dump(value, stream, indent=2); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
    def journal(since=None):
        cmd = ['journalctl', '-k', '-b', '--no-pager']
        if since: cmd += ['--since', since]
        return subprocess.check_output(cmd, text=True, timeout=20)
    def run_probe(command, environment, log_path, label):
        if interrupted: raise RuntimeError('Interrupted; refusing a new probe')
        with log_path.open('w') as log:
            child = subprocess.Popen(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 120
                while child.poll() is None:
                    if interrupted: raise RuntimeError('Interrupted during ' + label)
                    if time.monotonic() >= deadline: raise subprocess.TimeoutExpired(command, 120)
                    time.sleep(0.5)
                return child.returncode
            except subprocess.TimeoutExpired:
                save('FAULT.json', {'reason': label + ' timeout', 'pid': child.pid})
                raise
            finally:
                if child.poll() is None: graceful_stop(child)
    communication_path = Path(__file__).with_name('communication-admission.json')
    communication = json.loads(communication_path.read_text())
    admitted = communication.get('attempts', [{}])[-1].get('result', {})
    if (communication.get('status') != 'cpu-sibling-pidfd-passed'
            or communication.get('image') != IMAGE
            or communication.get('selected_user') != '0:0'
            or communication.get('gpu_exposed') is not False
            or communication.get('host_mounts') is not False
            or communication.get('network') != 'none'
            or communication.get('source_sha256') != hashlib.sha256(Path(__file__).with_name('probe_pidfd.py').read_bytes()).hexdigest()
            or admitted.get('uid') != 0 or admitted.get('gid') != 0
            or admitted.get('cap_eff') != '0000000000080000'
            or admitted.get('no_new_privs') != '1' or admitted.get('seccomp') != '2'
            or admitted.get('passed') is not True):
        raise RuntimeError('Reviewed CPU sibling-pidfd admission does not match this container policy')
    save('communication-admission.json', communication)
    preservation = json.loads(Path('/home/steve/worker-qwen27b-intake-20261007/model-preservation/summary.json').read_text())
    if (preservation.get('status') != 'verified-cold-copy-complete'
            or preservation.get('revision') != MODEL_REVISION
            or preservation.get('source') != MODEL_ROOT
            or preservation.get('post_clean_remount_full_readback') is not True
            or preservation.get('drive_cleanly_unmounted') is not True
            or Path('/mnt/usb-models').is_mount()):
        raise RuntimeError('Verified cold copy and clean external-drive unmount required')
    # Verify the complete immutable publisher manifest before any GPU probe.
    manifest = json.loads(MODEL_MANIFEST.read_text())
    if manifest['revision'] != MODEL_REVISION:
        raise RuntimeError('Unexpected model manifest revision')
    if Path(MODEL_ROOT).stat().st_mode & 0o005 != 0o005:
        raise RuntimeError('Model directory must be readable/searchable without DAC override')
    verified = []
    for kind in ('lfs_files', 'small_files'):
        for item in manifest[kind]:
            path = Path(MODEL_ROOT) / item['path']
            if path.stat().st_mode & 0o004 == 0:
                raise RuntimeError('Model file must be world-readable: ' + item['path'])
            if path.stat().st_size != item['bytes']:
                raise RuntimeError('Model file size mismatch: ' + item['path'])
            digest = hashlib.sha256() if kind == 'lfs_files' else hashlib.sha1()
            if kind == 'small_files':
                digest.update(('blob ' + str(item['bytes']) + '\0').encode())
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(4 * 1024**2), b''): digest.update(block)
            expected = item['sha256'] if kind == 'lfs_files' else item['git_blob']
            if digest.hexdigest() != expected:
                raise RuntimeError('Model file digest mismatch: ' + item['path'])
            verified.append({'path': item['path'], 'bytes': item['bytes'], 'digest': expected})
            if interrupted: raise RuntimeError('Interrupted during model verification')
    save('model-verification.json', {'repository': manifest['repository'], 'revision': MODEL_REVISION,
         'manifest_sha256': hashlib.sha256(MODEL_MANIFEST.read_bytes()).hexdigest(), 'files': verified})
    handles = []
    for name in ['/run/lock/muse-glimmer-gpu-exclusive.lock', '/tmp/b70-benchmark.lock'] + [f'/tmp/b70-gpu{i}.lock' for i in range(4)]:
        handle = open(name, 'a'); fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB); handles.append(handle)
    for key in ('ZE_AFFINITY_MASK', 'ONEAPI_DEVICE_SELECTOR', 'SYCL_DEVICE_FILTER'):
        if os.environ.get(key): raise RuntimeError('Unexpected inherited device filter: ' + key)
    nodes = sorted(Path('/dev/dri').glob('renderD*'))
    if len(nodes) != 4: raise RuntimeError('Expected four render nodes')
    owners = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, timeout=10)
    if owners.returncode != 1 or owners.stdout or owners.stderr: raise RuntimeError('Render nodes not idle')
    if subprocess.check_output(['docker', 'ps', '-q'], timeout=10).strip(): raise RuntimeError('Container already running')
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', 18125))
    mem = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
    if mem['MemAvailable'] < 64 * 1024**2: raise RuntimeError('Require 64GiB available RAM after the model is staged')
    for block in range(53, 58):
        if Path(f'/sys/devices/system/memory/memory{block}/state').read_text().strip() != 'offline':
            raise RuntimeError('Existing RAM exclusion is not in place')
    disk = os.statvfs(out)
    if disk.f_bavail * disk.f_frsize < 50 * 1024**3 + 256 * 1024**2: raise RuntimeError('Disk reserve not met')
    before = journal(); (out / 'journal-before.txt').write_text(before)
    # Historical October4 OOMs are preserved in the baseline. Any new OOM halts
    # this pilot; no device-fault recovery is automated by this launcher.
    historical_gpu_faults = [line for line in before.splitlines() if FAULT.search(line) and 'Out of memory: Killed process' not in line]
    if historical_gpu_faults: raise RuntimeError('Current boot contains device fault evidence; review before launch')
    since = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('VLLM_', 'B70_', 'CCL_', 'ZE_', 'SYCL_', 'ONEAPI_', 'TORCH_'))}
    env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='8', MKL_NUM_THREADS='8')
    probe_command = [PYTHON, '-B', str(REPO / 'experiments/ltx25-b70/scripts/check-four-card-health.py'), str(out / 'health.json')]
    probe_code = run_probe(probe_command, env, out / 'health.log', 'preflight')
    if probe_code or not json.loads((out / 'health.json').read_text()).get('passed'):
        raise RuntimeError('Health probe failed; no model launched')
    container_env = {
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
        'TOKENIZERS_PARALLELISM': 'false', 'OMP_NUM_THREADS': '8', 'MKL_NUM_THREADS': '8',
        'ZE_AFFINITY_MASK': '0,1', 'VLLM_PLUGINS': '',
        'PYTHONPATH': '/opt/venv/lib/python3.12/site-packages', 'PYTHONDONTWRITEBYTECODE': '1',
        'HOME': '/tmp', 'HF_HOME': '/tmp/huggingface', 'XDG_CACHE_HOME': '/tmp/cache',
        'VLLM_CACHE_ROOT': '/tmp/vllm-cache', 'TORCHINDUCTOR_CACHE_DIR': '/tmp/torchinductor',
        'VLLM_XPU_FP16_LINEAR_ROWCHUNK': '32', 'VLLM_XPU_ENABLE_XPU_GRAPH': '0',
        'VLLM_XPU_GDN_SPLIT_MIXED': '0', 'VLLM_XPU_GDN_SPEC_GROUP': '0',
        'VLLM_XPU_DRAFT_LM_HEAD_INT4': '0',
        'VLLM_XPU_QWEN_GEMMA_RMSNORM_PACKED_SERIAL_EXACT': '0',
        'VLLM_XPU_FP8_BLOCK_W8A16': '1', 'VLLM_XPU_GDN_NATIVE_FALLBACK': '1',
        'VLLM_BATCH_INVARIANT': '0',
    }
    # Match the historical TP2 OFI/TCP + pidfd transport. Both worker ranks
    # share this container's private IPC namespace. No host IPC/power changes.
    # CPU sibling-FD admission proved non-root loses this capability; UID0
    # with only SYS_PTRACE passed under the unchanged seccomp/no-new-privileges
    # policy. It does not qualify GPU collectives. Never switch transport on error.
    container_env.update({
        'CCL_ATL_TRANSPORT': 'ofi', 'FI_PROVIDER': 'tcp', 'FI_TCP_IFACE': 'lo',
        'CCL_ZE_IPC_EXCHANGE': 'pidfd', 'CCL_SEND': 'direct', 'CCL_RECV': 'direct',
        'CCL_TOPO_P2P_ACCESS': '1',
        'CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD': '4294967296',
        'CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD': '4294967296',
        'CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD': '4294967296',
        'PYTHONHASHSEED': '0', 'VLLM_USE_V2_MODEL_RUNNER': '0',
    })
    command = ['/opt/venv/bin/python', '-B', '-m', 'vllm.entrypoints.openai.api_server', '--model', MODEL,
               '--served-model-name', 'qwen38-27b-fp8-target-only-worker-pilot', '--host', '127.0.0.1', '--port', '18125',
               '--dtype', 'float16', '--quantization', 'fp8', '--kv-cache-dtype', 'auto', '--tensor-parallel-size', '2',
               '--pipeline-parallel-size', '1', '--max-model-len', '33024', '--block-size', '64', '--max-num-seqs', '1',
               '--max-num-batched-tokens', '512', '--gpu-memory-utilization', '0.80',
               '--language-model-only', '--no-enable-prefix-caching', '--enable-prompt-tokens-details', '--enforce-eager']
    owner = uuid.uuid4().hex
    container_name = 'qwen38-27b-target-only-pilot-' + owner
    owner_label = 'lab.local-coding-worker.pilot-owner'
    container_id = None
    create = ['docker', 'create', '--name', container_name, '--label', owner_label + '=' + owner,
              '--restart', 'no', '--read-only', '--tmpfs', '/tmp:rw,exec,nosuid,nodev,size=2g,mode=1777',
              '--network', 'host', '--memory', '48g', '--memory-swap', '48g',
              '--cap-drop', 'ALL', '--cap-add', 'SYS_PTRACE', '--security-opt', 'no-new-privileges', '--user', '0:0',
              '--device', '/dev/dri', '--workdir', '/tmp', '--ipc', 'private', '--shm-size', '8g', '--ulimit', 'core=0',
              '--mount', 'type=bind,src=/dev/dri/by-path,dst=/dev/dri/by-path,readonly',
              '--log-driver', 'local', '--log-opt', 'max-size=10m', '--log-opt', 'max-file=2',
              '--mount', 'type=bind,src=' + MODEL_ROOT + ',dst=' + MODEL_ROOT + ',readonly',
              '--entrypoint', command[0]]
    for group in ('render', 'video'):
        create += ['--group-add', str(grp.getgrnam(group).gr_gid)]
    for key, value in container_env.items(): create += ['--env', key + '=' + value]
    create += [IMAGE, *command[1:]]
    save('launch.json', {'create_command': create, 'server_command': command, 'container_env': container_env,
                        'image': IMAGE, 'model_revision': MODEL_REVISION, 'model_manifest': str(MODEL_MANIFEST), 'container_name': container_name, 'owner_label': owner_label, 'owner': owner,
                        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'since': since,
                        'supervisor_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        'server_start_planned': True,
                        'communication_admission_sha256': hashlib.sha256(communication_path.read_bytes()).hexdigest(),
                        'memory_plan': {'container_limit_gib': 48, 'combined_memory_swap_gib': 48,
                                        'tmp_cap_gib': 2, 'private_shm_cap_gib': 8,
                                        'tmp_and_shm_count_toward_container_limit': True,
                                        'model_staging_bytes': sum(item['bytes'] for item in verified),
                                        'minimum_host_available_after_model_staging_gib': 64}})
    stop_sent = False; started = time.monotonic(); reason = 'container exited'
    attach = None; create_child = None; final_state = None
    def inspect_owned():
        result = subprocess.run(['docker', 'inspect', '--type', 'container', container_name],
                                capture_output=True, text=True, timeout=20)
        if result.returncode:
            if 'No such object:' in result.stderr or 'No such container:' in result.stderr: return None
            raise RuntimeError('Cannot inspect owned container: ' + result.stderr)
        data = json.loads(result.stdout)[0]
        if (data['Image'] != IMAGE or data['Config']['Labels'].get(owner_label) != owner
                or (container_id is not None and data['Id'] != container_id)):
            raise RuntimeError('Container ownership/image mismatch; refusing signals')
        return data
    def graceful_container_stop(data):
        nonlocal stop_sent
        if data['State']['Running'] and not stop_sent:
            stop_sent = True  # At most one attempt, including ambiguous Docker errors.
            result = subprocess.run(['docker', 'kill', '--signal', 'SIGINT', data['Id']],
                                    capture_output=True, text=True, timeout=20)
            save('stop-signal.json', {'signal': 'SIGINT', 'container_id': data['Id'],
                                    'returncode': result.returncode, 'stderr': result.stderr})
    def retain_until_stopped():
        # Unknown daemon state never releases ownership. Only read-only inspection
        # repeats; no restart, second signal, hard kill, or automatic removal.
        while True:
            try:
                data = inspect_owned()
                if data is None or not data['State']['Running']:
                    if attach is None or attach.poll() is not None: return data
                    # A start/attach client may still submit its start request.
                    # Observe until it exits or the container actually starts.
                else:
                    graceful_container_stop(data)
            except Exception as exc:
                print('Holding GPU locks; container cleanup unresolved:', str(exc), flush=True)
            time.sleep(3)
    try:
        admission_journal = journal(since)
        (out / 'journal-admission.txt').write_text(admission_journal)
        if interrupted or FAULT.search(admission_journal):
            raise RuntimeError('Interrupted or new fault during admission; no container creation')
        # Keep the create CLI alive until it finishes, avoiding ambiguous daemon
        # completion after a timed-out/terminated client.
        with (out / 'create.log').open('w') as create_log:
            create_child = subprocess.Popen(create, stdout=create_log, stderr=subprocess.STDOUT,
                                            start_new_session=True)
            if create_child.wait() != 0: raise RuntimeError('Docker create failed')
        data = inspect_owned()
        if data is None: raise RuntimeError('Created container disappeared')
        container_id = data['Id']
        save('container.json', {'id': container_id, 'image': IMAGE, 'owner': owner})
        admission_journal = journal(since)
        (out / 'journal-before-start.txt').write_text(admission_journal)
        if interrupted or (out / 'STOP').exists() or FAULT.search(admission_journal):
            raise RuntimeError('Interrupted, stopped or new fault; refusing container start')
        with (out / 'server.log').open('w') as log:
            attach = subprocess.Popen(['docker', 'start', '--attach', container_id], stdout=log,
                                      stderr=subprocess.STDOUT, start_new_session=True)
            save('pid.json', {'docker_attach_pid': attach.pid, 'supervisor_pid': os.getpid(),
                              'container_id': container_id, 'server_start_attempts': 1})
            while True:
                data = inspect_owned()
                if data is None: raise RuntimeError('Owned container disappeared during serving')
                if attach.poll() is not None and not data['State']['Running']:
                    final_state = data['State']; break
                current = journal(since)
                if FAULT.search(current):
                    save('FAULT.json', {'reason': 'new kernel fault'})
                    (out / 'journal-fault.txt').write_text(current)
                if data['State'].get('OOMKilled'):
                    save('FAULT.json', {'reason': 'container OOM'})
                if (interrupted or (out / 'STOP').exists() or (out / 'FAULT.json').exists()
                        or time.monotonic() - started > 3600 or attach.poll() is not None):
                    reason = 'fault' if (out / 'FAULT.json').exists() else 'stop/deadline/attach exit'
                    graceful_container_stop(data)
                time.sleep(3)
    except BaseException as exc:
        save('FAULT.json', {'reason': 'supervisor error', 'error': str(exc)})
        raise
    finally:
        if create_child is not None: create_child.wait()
        data = retain_until_stopped()
        if attach is not None:
            attach.wait()  # CLI may not outlive ownership cleanup.
            # A start CLI that had not yet submitted could race the first
            # inspection. Recheck after CLI completion before releasing locks.
            data = retain_until_stopped()
        if data is not None: final_state = data['State']
        while True:
            try:
                owners = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, timeout=10)
                if owners.returncode == 1 and not owners.stdout and not owners.stderr: break
                print('Holding GPU locks; render nodes are still occupied or unreadable', flush=True)
            except Exception as exc:
                print('Holding GPU locks; render-idle inspection failed:', str(exc), flush=True)
            time.sleep(3)
        save('cleanup.json', {'container_id': container_id, 'container_state': final_state,
                              'render_nodes_idle': True, 'stop_signal_sent': stop_sent})
    if final_state is None: raise RuntimeError('No final owned-container state')
    if final_state.get('OOMKilled'):
        save('FAULT.json', {'reason': 'container OOM'})
    after = journal(since); (out / 'journal-after.txt').write_text(after)
    remaining = subprocess.run(['fuser', *map(str, nodes)], capture_output=True, timeout=10)
    idle = remaining.returncode == 1 and not remaining.stdout and not remaining.stderr
    postflight_passed = False
    if idle and not interrupted and not FAULT.search(after) and not (out / 'FAULT.json').exists():
        post_env = dict(env)
        code = run_probe([*probe_command[:-1], str(out / 'postflight-health.json')], post_env, out / 'postflight-health.log', 'postflight')
        postflight_passed = code == 0 and json.loads((out / 'postflight-health.json').read_text()).get('passed', False)
        after = journal(since); (out / 'journal-after.txt').write_text(after)
    save('shutdown.json', {'container_state': final_state, 'container_id': container_id, 'reason': reason, 'stop_signal_sent': stop_sent,
                          'new_kernel_fault': bool(FAULT.search(after)), 'render_nodes_idle': idle, 'four_card_postflight_passed': postflight_passed})
    return 0 if final_state['ExitCode'] == 0 and not final_state['Running'] and idle and not FAULT.search(after) and not (out / 'FAULT.json').exists() and postflight_passed else 1


if __name__ == '__main__': raise SystemExit(main())
