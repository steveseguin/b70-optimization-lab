#!/usr/bin/env python3
"""CPU supervisor; native launch ONLY after explicit, fresh window admission.

No runtime imports here. --plan and --audit are CPU-only. The subprocess is
the A367 host Python, never a container. One chat request, no request retry.
"""
from __future__ import annotations

import argparse
from collections import Counter
import datetime as dt
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
PREP = HERE.parent
REPO = HERE.parents[4]
LANE = REPO / 'experiments/qwen38-flash-next-fp8-b70'
PREREG = HERE / 'preregistration.json'
ORACLE = REPO / 'experiments/own-xpu-runtime/stage2/packet1/oracle-token-ids.json'
SUITE = REPO / 'repro/rapid-model-snapshots-b70/realistic-suite-v1.json'
FAULT_ROOTS = (Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913'),
               LANE / 'reopen-20261008', PREP)
FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|GPU HANG|'
                   r'GuC.*reset|coredump|timed.?out job|job[^\n]*timed\s*out|wedged|'
                   r'hard LOCKUP|soft lockup|Hardware Error', re.I)
DELETED = re.compile(r'coredump has been deleted', re.I)
PROMPT_ID = 'incident-retrospective'
CAP = 64
PORT = 19980


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    with temp.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def artifact(path):
    return {'path': str(Path(path).resolve()), 'sha256': sha(path)}


def timestamp(value):
    return dt.datetime.strptime(value, '%Y-%m-%d %H:%M:%S UTC').replace(
        tzinfo=dt.timezone.utc).timestamp()


def verify_health(h, boot, now):
    require(h.get('schema') == 'ltx.four-card-health.v1', 'health schema')
    require(h.get('passed') is True and h.get('boot_id') == boot, 'health failed/wrong boot')
    require(h.get('kernel') == Path('/proc/sys/kernel/osrelease').read_text().strip(), 'health kernel')
    require(0 <= now - timestamp(h['end_utc']) <= 600, 'health stale/future')
    require(timestamp(h['start_utc']) <= timestamp(h['end_utc']), 'health reversed timestamps')
    require(h.get('device_count') == 4 and len(h.get('cards', [])) == 4, 'four-card health required')
    require({c['device'] for c in h['cards']} == {f'xpu:{i}' for i in range(4)}
            and all(c.get('pass') is True for c in h['cards']), 'health rank coverage')
    require(h.get('journal_fault_lines_during_probe') == [], 'health journal fault')
    # Existing earlier faults cannot be silently admitted by a new health pass.
    require(h.get('fault_lines_earlier_this_boot') == 0, 'earlier boot faults: resolve halt first')


def processes():
    rows = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            pid = int(path.parent.name)
            if pid == os.getpid():
                continue
            argv = path.read_bytes().replace(b'\0', b' ').decode(errors='replace').strip()
            comm = (path.parent / 'comm').read_text().strip()
            rows.append((pid, comm, argv))
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise ValueError('cannot inspect process ownership') from exc
    return rows


def conflicts(rows):
    # Match actual processes, including multiprocessing setproctitle names.
    # The preparation wrapper path itself contains no model/server term.
    return [(pid, comm, argv) for pid, comm, argv in rows if
            re.search(r'(?i)(vllm|ltx[^ /]*|comfyui)', comm + ' ' + argv)]


def owned_session_gone(pid):
    """Do not delete IPC/cache backing while any session descendant survives."""
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if os.getsid(int(proc.name)) == pid:
                return False
        except ProcessLookupError:
            continue
        except PermissionError:
            return False
    return True


def verify_admission(owner, health, boot, now, output, rows, fault_paths):
    require(not output.exists(), 'output exists: no retry/reuse')
    require(not any(p.exists() for p in fault_paths), 'FAULT.json present')
    require(owner.get('schema') == 'own-xpu-runtime.packet4.owner-window.v1'
            and owner.get('authorized') is True, 'owner-window authorization absent')
    require(owner.get('boot_id') == boot and owner.get('host') == socket.gethostname() == 'steve-b70s', 'owner host/boot')
    require(owner.get('preregistration_sha256') == sha(PREREG), 'owner preregistration pin')
    require(owner.get('health_sha256') == hashlib.sha256(
        Path(owner['health_path']).read_bytes()).hexdigest(), 'owner health pin')
    require(Path(owner['output']).resolve() == output.resolve(), 'owner output binding')
    require(owner.get('halt_resolved') is True, 'owner must resolve current halt explicitly')
    require(owner.get('pci_ids') == ['0000:23:00.0', '0000:27:00.0', '0000:43:00.0', '0000:47:00.0']
            and isinstance(owner.get('firmware'), str) and owner['firmware'].strip()
            and 'OBSERVED-' not in owner['firmware'], 'owner PCI/firmware facts missing')
    require(owner['issued_unix'] <= now < owner['expires_unix']
            and owner['expires_unix'] - owner['issued_unix'] <= 3600, 'owner window stale/future')
    require(305 <= now - owner['previous_teardown_completed_unix'], '305-second stop gap')
    verify_health(health, boot, now)
    require(not conflicts(rows), 'ltx/vLLM/ComfyUI process running')


def verify_repo(p= None):
    p = p or read(PREREG)
    for relative, expected in p['repo_pins'].items():
        require(sha(REPO / relative) == expected, 'seal mismatch: ' + relative)
    require(p['patch_seal_members'] == 75, '75-member seal required')
    for relative, expected in read(HERE / 'driver-seal.json')['files'].items():
        require(sha(HERE / relative) == expected, 'driver seal mismatch: ' + relative)
    return p


def verify_environment(paths, p):
    """Read bytes/metadata only. No torch/vLLM imports, weight loads or changes."""
    source, stage, model = (paths[k] for k in ('source', 'stage', 'model'))
    for relative, expected in p['source_pins'].items():
        require(sha(source / relative) == expected, 'source differs: ' + relative)
    actual = {str(f.relative_to(source)) for f in (source / 'vllm').rglob('*.py')}
    require(actual == set(p['source_pins']), 'source Python file set differs')
    manifest = LANE / 'data/runtime-stage-gdn-roundstate-v2-loadable.sha256'
    binaries = []
    for line in manifest.read_text().splitlines():
        expected, relative = line.split(maxsplit=1)
        target = stage / 'vllm_xpu_kernels' / relative.strip().lstrip('*')
        require(sha(target) == expected, 'A367 kernel stage differs: ' + str(target))
        binaries.append(artifact(target))
    require(len(binaries) == 18, '18 kernel members required')
    for target, expected in [
        (paths['oneccl'] / 'lib/libccl.so.1.0', '43d94d43506e30096dd099b9d53b54f932be964751e92ff0cbb8d3a37fad6700'),
        (paths['python'].parent.parent / 'lib/ccl/kernels/kernels.spv', '0d549c35a558f1b216cb7d1efeaa9f86d7596ffc47b383644e075290d314f0c9')]:
        require(sha(target) == expected, 'collective library differs')
    site = paths['python'].parent.parent / 'lib/python3.12/site-packages'
    versions = {d.metadata['Name'].lower(): d.version for d in importlib.metadata.distributions(path=[str(site)])}
    # Intel's wheel distribution is triton-xpu; its import package is triton.
    versions['triton'] = versions.get('triton-xpu', versions.get('triton'))
    for name, expected in p['versions'].items():
        require(versions.get(name) == expected, 'venv version differs: ' + name)
    contract = read(REPO / 'repro/qwen38-flash-next-fp8-tp4-mtp3-b70/model-contract.json')
    c = contract['contract']
    for name, key in [('config.json', 'config_sha256'), ('model.safetensors.index.json', 'index_sha256')]:
        require(sha(model / name) == c[key], 'model identity differs: ' + name)
    verification = contract['historical_full_verification']
    require(sha(verification['receipt_path_on_origin_host']) == verification['receipt_sha256'], 'full model verification receipt absent/changed')
    require(len(list(model.glob('model-*.safetensors'))) == 131, 'model shards missing')
    # Headers/metadata and local publisher LFS SHA256s are frozen by packet1.
    # Actual payload hashing is supplied as a separate fresh admission receipt.
    return {'passed': True, 'versions': {k: versions[k] for k in p['versions']},
            'source': str(source), 'source_commit': p['certified_source_commit'],
            'source_files_verified': len(p['source_pins']), 'kernel_files': binaries}


def build_environment(paths, output):
    """Allowlisted environment; ambient VLLM/CCL/NEO knobs cannot leak in."""
    compiler = '/opt/intel/oneapi/compiler/2025.3'
    venv = str(paths['python'].parent.parent)
    stage, source = str(paths['stage']), str(paths['source'])
    env = {k: os.environ[k] for k in ('HOME', 'USER', 'LOGNAME', 'LANG') if k in os.environ}
    env.update({
        'PATH': f'{compiler}/bin:/usr/bin:/bin', 'CMPLR_ROOT': compiler,
        'LIBRARY_PATH': f'{compiler}/lib:{compiler}/opt/compiler/lib',
        'OCL_ICD_FILENAMES': f'{compiler}/lib/libintelocl.so',
        'PYTHONPATH': f'{HERE}:{PREP}:{stage}:{source}',
        'LD_LIBRARY_PATH': f'{stage}/vllm_xpu_kernels:{venv}/lib:{venv}/lib/python3.12/site-packages/torch/lib:{compiler}/lib:{compiler}/opt/compiler/lib',
        'LD_PRELOAD': str(paths['oneccl'] / 'lib/libccl.so.1.0'),
        'HF_HOME': str(output / 'scratch/hf'), 'HUGGINGFACE_HUB_CACHE': str(output / 'scratch/hf'),
        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'VLLM_CACHE_ROOT': str(output / 'scratch/vllm'), 'TORCHINDUCTOR_CACHE_DIR': str(output / 'scratch/inductor'),
        'TRITON_CACHE_DIR': str(output / 'scratch/triton'), 'XDG_CACHE_HOME': str(output / 'scratch/xdg'),
        'TMPDIR': str(output / 'scratch/rpc'), 'VLLM_RPC_BASE_PATH': str(output / 'scratch/rpc'),
        'PYTHONNOUSERSITE': '1', 'PYTHONSAFEPATH': '1', 'PYTHONDONTWRITEBYTECODE': '1',
        'ZE_AFFINITY_MASK': '0,1,2,3', 'VLLM_TARGET_DEVICE': 'xpu', 'VLLM_USE_V1': '1',
        'VLLM_WORKER_MULTIPROC_METHOD': 'spawn', 'VLLM_NO_USAGE_STATS': '1',
        'PYTHONHASHSEED': '0', 'PYTORCH_ALLOC_CONF': 'expandable_segments:True',
        'OMP_NUM_THREADS': '2', 'VLLM_XPU_ENABLE_XPU_GRAPH': '0', 'VLLM_KV_CACHE_LAYOUT': 'BLHNC',
        'CCL_ATL_TRANSPORT': 'ofi', 'FI_PROVIDER': 'tcp', 'FI_TCP_IFACE': 'lo',
        'CCL_ZE_IPC_EXCHANGE': 'pidfd', 'CCL_SEND': 'direct', 'CCL_RECV': 'direct',
        'CCL_TOPO_P2P_ACCESS': '1', 'CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD': '4294967296',
        'CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD': '4294967296',
        'CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD': '4294967296',
        'CCL_KERNEL_PATH': f'{venv}/lib/ccl/kernels', 'CCL_SYCL_ALLREDUCE_LL_THRESHOLD': '4096',
        'CCL_SYCL_ALLREDUCE_LL': 'twoshots', 'VLLM_XPU_MKLDNN_DETERMINISTIC': '1',
        'VLLM_TUNED_CONFIG_FOLDER': str(LANE / 'configs/moe-m1-w13-n32'),
        'VLLM_XPU_HC_TRITON': '1', 'VLLM_XPU_QSA_FUSED_INDEXER': '1',
        'VLLM_XPU_GDN_SERIAL_SPEC_DECODE': '0', 'VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT': '1',
        'VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH': '1', 'VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER': '1',
        'VLLM_XPU_ROWWISE_ALLREDUCE_MAX_ROWS': '2', 'VLLM_XPU_ROWWISE_HC_NORM_MAX_ROWS': '2',
        'Q38_EXPERT_HOST_PLACEMENT': str(LANE / 'data/20260906-q38-expert-host-placement-3p5gib-per-rank.json'),
        'PACKET4_WINDOW': str(output), 'PACKET4_SOURCE': source,
    })
    return env


def build_command(paths):
    return [str(paths['python']), '-B', str(HERE / 'server_entry.py'), 'serve', str(paths['model']),
            '--host', '127.0.0.1', '--port', str(PORT), '--served-model-name', 'qwen38-flash-next-fp8-tp4',
            '--tokenizer', str(paths['model']), '--dtype', 'bfloat16', '--tensor-parallel-size', '4',
            '--pipeline-parallel-size', '1', '--data-parallel-size', '1', '--distributed-executor-backend', 'mp',
            '--enable-expert-parallel', '--all2all-backend', 'allgather_reducescatter', '--language-model-only',
            '--moe-backend', 'triton', '--enforce-eager', '--compilation-config', '{"mode":0,"cudagraph_mode":"NONE"}',
            '--max-model-len', '4352', '--max-num-seqs', '1', '--max-num-batched-tokens', '64',
            '--no-enable-prefix-caching', '--offload-backend', 'uva', '--cpu-offload-gb', '12.25',
            '--cpu-offload-params', 'ple_embedding.ngram_embedding.weight', 'embed_tokens.weight',
            '--gpu-memory-utilization', '0.92', '--kv-cache-memory-bytes', '376569856', '--kv-cache-dtype', 'auto',
            '--block-size', '64', '--generation-config', 'vllm', '--load-format', 'safetensors',
            '--no-async-scheduling', '--enable-prompt-tokens-details', '--disable-uvicorn-access-log',
            '--speculative-config', '{"method":"mtp","num_speculative_tokens":1}',
            '--worker-cls', 'packet4_worker.ExtractionWorker']


def oracle_assert(ids, cached_tokens, finish_reason, root, oracle=None):
    oracle = oracle or read(ORACLE)
    expected = next(r['token_ids'] for r in oracle['rows'] if r['prompt_id'] == PROMPT_ID)[:CAP]
    passed = (type(ids) is list and all(type(t) is int and t >= 0 for t in ids)
              and ids == expected and type(cached_tokens) is int and cached_tokens == 0
              and finish_reason == 'length')
    verdict = {'status': 'PREFIX64-EXACT-UNQUALIFIED' if passed else 'VOID',
               'passed': passed, 'token_ids': ids, 'expected_token_ids': expected,
               'cached_tokens': cached_tokens, 'finish_reason': finish_reason,
               'full_oracle_equal': False, 'realistic_final_gate': {'passed': False},
               'scope': 'exact 64-token prefix of the frozen 512-token answer'}
    write(root / 'oracle-verdict.json', verdict)
    if not passed:
        void(root, 'token IDs/cache/length differ from preregistered oracle prefix')
        raise AssertionError('oracle mismatch: fixtures VOID')
    return verdict


def void(root, reason):
    write(root / 'VOID.json', {'status': 'VOID', 'reason': reason})
    for rank in range(4):
        d = root / f'rank-{rank}'
        if d.is_dir():
            write(d / 'VOID.json', {'status': 'VOID', 'reason': reason})


def journal():
    result = subprocess.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'short-iso-precise'],
                            capture_output=True, text=True, check=True, timeout=3)
    require(result.stdout.strip() and not result.stderr.strip(), 'complete kernel journal unavailable')
    return result.stdout


def fault_lines(log):
    return [s for s in log.splitlines() if FAULT.search(s) and not DELETED.search(s)]


class Watch:
    """Host polling like probe/watch_kernel.py; fresh receipts, no GPU probe."""
    def __init__(self, root, baseline, boot):
        self.root, self.boot = root, boot
        self.baseline = Counter(fault_lines(baseline))
        self.stop = threading.Event()
        self.failed = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def poll(self):
        require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.boot, 'boot changed')
        log = journal()
        (self.root / 'kernel-latest.log').write_text(log)
        new = list((Counter(fault_lines(log)) - self.baseline).elements())
        if new:
            write(self.root / 'FAULT.json', {'boot_id': self.boot, 'lines': new, 'unix': time.time()})
        require(not new, 'new kernel fault; preserve coredump; no retry')
        require(not any((p / 'FAULT.json').exists() for p in FAULT_ROOTS), 'external FAULT.json')
        write(self.root / 'watcher.json', {'passed': True, 'updated_unix': time.time(), 'boot_id': self.boot})

    def run(self):
        while not self.stop.is_set():
            try:
                self.poll()
            except BaseException as exc:
                self.failed = str(exc)
                write(self.root / 'STOP.json', {'reason': self.failed})
                return
            self.stop.wait(.5)


def make_identity(root, args, paths, env, command, audit, owner, health):
    comparator = {'image_digest': None, 'runtime_commit': read(PREREG)['certified_source_commit'],
                  'build_manifest': artifact(PREREG), 'overlay_manifest': artifact(PREP / 'comparator-identity-audit.json'),
                  # Hash receipts, not copies of the large binaries, travel with each writer.
                  'kernel_binaries': [artifact(root / 'environment.json')],
                  'compiler': 'oneAPI 2025.3', 'libraries': audit['versions'],
                  'environment': env, 'launch_flags': command,
                  'dispatch': 'A367 TP4 EP4 MTP1 eager diagnostic layer0 observer',
                  'device_topology': 'four B70; ZE_AFFINITY_MASK=0,1,2,3'}
    write(root / 'certified-environment.json', {'passed': True, 'comparator': comparator,
          'scope': 'A367 source/binary identity only; eager/hook neutrality UNTESTED', 'audit': audit})
    prompt = next(r['prompt'] for r in read(SUITE)['prompts'] if r['id'] == PROMPT_ID)
    request = {'model': 'qwen38-flash-next-fp8-tp4', 'messages': [{'role': 'user', 'content': prompt}],
               'temperature': 0, 'top_p': 1.0, 'seed': 20260609, 'max_tokens': CAP,
               'chat_template_kwargs': {'enable_thinking': False}, 'return_token_ids': True, 'stream': False}
    write(root / 'request.json', request)
    identity = {'mock': False, 'model': 'flash-next', 'comparator': comparator,
                'authorization': artifact(args.owner_window), 'health': artifact(args.health_receipt),
                'payload': artifact(args.payload_receipt), 'suite': artifact(SUITE), 'prompt': artifact(root / 'request.json'),
                'binding_manifest': artifact(PREREG), 'certified_environment_receipt': artifact(root / 'certified-environment.json'),
                'host': owner['host'], 'boot_id': owner['boot_id'], 'kernel': health['kernel'],
                'firmware': owner['firmware'], 'pci_ids': owner['pci_ids'], 'kv_dtype': 'BF16', 'state_dtype': 'BF16',
                'sampler': {'temperature': 0, 'seed': 20260609, 'top_p': 1.0}, 'mtp': 1,
                'environment': env, 'flags': command, 'execution': read(PREREG)['execution'],
                'deltas': read(PREREG)['deltas'], 'preregistration': artifact(PREREG)}
    write(root / 'identity.json', identity)
    return request


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--audit', action='store_true')
    mode.add_argument('--execute', action='store_true')
    p.add_argument('--owner-window', type=Path)
    p.add_argument('--health-receipt', type=Path)
    p.add_argument('--payload-receipt', type=Path)
    p.add_argument('--output', type=Path, required=True)
    for name, default in read(PREREG)['defaults'].items():
        p.add_argument('--' + name, type=Path, default=Path(default))
    a = p.parse_args(argv)
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.environ.get('OMP_NUM_THREADS') == '2', 'nice19 OMP2 required')
    paths = {k: getattr(a, k).absolute() for k in read(PREREG)['defaults']}
    root = a.output.absolute()
    command, env = build_command(paths), build_environment(paths, root)
    if a.plan:
        print(json.dumps({'command': command, 'environment': env, 'deltas': read(PREREG)['deltas'],
                          'native_executed': False}, indent=2))
        return 0
    prereg = verify_repo()
    if a.audit:
        print(json.dumps(verify_environment(paths, prereg), indent=2))
        return 0
    require(all((a.owner_window, a.health_receipt, a.payload_receipt)), 'owner, health and payload receipts required')
    # Lock file remains as a rendezvous, never unlinked while another owner may wait.
    with (PREP / 'extraction-window.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        owner, health = read(a.owner_window), read(a.health_receipt)
        owner_hash = sha(a.owner_window)
        require(Path(owner['health_path']).resolve() == a.health_receipt.resolve(), 'different health file')
        verify_admission(owner, health, boot, time.time(), root, processes(),
                         [p / 'FAULT.json' for p in (*FAULT_ROOTS, root)])
        audit = verify_environment(paths, prereg)
        payload = read(a.payload_receipt)
        require(payload.get('passed') is True and payload.get('model_root') == str(paths['model'])
                and payload.get('revision') == 'bcd9f01ddc9cff2316eb84281bebcd5b058bddce'
                and payload.get('all_files_sha256_verified') is True
                and 0 <= time.time() - payload['verified_unix'] <= 3600
                and sha(a.payload_receipt) == owner['payload_sha256'], 'fresh full payload verification required')
        require(shutil.disk_usage(root.parent).free >= prereg['minimum_disk_free_bytes'], 'disk reserve')
        mem = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        require(int(mem['MemAvailable'].split()[0]) * 1024 >= prereg['minimum_mem_available_bytes'], 'A367 memory floor not met; no host changes allowed')
        with socket.socket() as port:
            port.bind(('127.0.0.1', PORT))  # no HTTP contact with somebody else's server
        baseline = journal()
        require(not fault_lines(baseline), 'fault-bearing boot refused')
        # Recheck freshness, owners and latches after the potentially slow source audit.
        verify_admission(owner, health, boot, time.time(), root, processes(),
                         [p / 'FAULT.json' for p in (*FAULT_ROOTS, root)])
        root.mkdir()
        (root / 'scratch/rpc').mkdir(parents=True)
        write(root / 'environment.json', audit)
        (root / 'kernel-before.log').write_text(baseline)
        request = make_identity(root, a, paths, env, command, audit, owner, health)
        watch = Watch(root, baseline, boot)
        watch.poll()
        watch.thread.start()
        child = None
        stopped = False
        all_owners_gone = False
        error = None
        interrupted = threading.Event()
        old_signals = {s: signal.signal(s, lambda *_: interrupted.set()) for s in (signal.SIGINT, signal.SIGTERM)}
        deadline = time.monotonic() + prereg['load_and_request_seconds']
        def check():
            require(not interrupted.is_set(), 'coordinator interruption')
            require(not watch.failed, 'watcher failed: ' + str(watch.failed))
            require(not (root / 'STOP.json').exists(), 'worker/watch STOP')
            require(a.owner_window.exists() and sha(a.owner_window) == owner_hash
                    and time.time() < owner['expires_unix'], 'owner window changed/revoked/expired')
            require(time.monotonic() < deadline, 'load/request budget exceeded')
            require(child.poll() is None, 'server exited before request completed')
        try:
            with (root / 'server.log').open('xb') as log:
                child = subprocess.Popen(command, env=env, cwd=root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                write(root / 'launch.json', {'pid': child.pid, 'unix': time.time(), 'command': command, 'environment': env})
                # Readiness polling is not a generation request and never cycles the server.
                while True:
                    check()
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=1) as response:
                            if response.status == 200:
                                break
                    except (urllib.error.URLError, TimeoutError):
                        pass
                    time.sleep(.5)
                require(all((root / f'rank-{i}/registered.json').exists() for i in range(4)), 'missing worker registration')
                result = {}
                def request_once():
                    try:
                        req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions',
                              data=json.dumps(request).encode(), headers={'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req, timeout=300) as response:
                            result['response'] = json.load(response)
                    except BaseException as exc:
                        result['error'] = repr(exc)
                client = threading.Thread(target=request_once, daemon=True)
                client.start()
                while client.is_alive():
                    check()
                    client.join(.5)
                require('response' in result, 'single request failed: ' + str(result.get('error')))
                check()
                body = result['response']
                write(root / 'response.json', body)
                require(len(body['choices']) == 1, 'multiple choices')
                choice = body['choices'][0]
                require(body['usage']['completion_tokens'] == CAP, 'completion usage differs from64')
                oracle_assert(choice.get('token_ids'), body['usage']['prompt_tokens_details']['cached_tokens'],
                              choice['finish_reason'], root)
        except BaseException as exc:
            error = f'{type(exc).__name__}: {exc}'
            void(root, error)
        finally:
            if child is not None:
                if child.poll() is None:
                    child.send_signal(signal.SIGINT)  # one PID, once; never a group kill
                    write(root / 'stop-request.json', {'pid': child.pid, 'signal': 'SIGINT', 'unix': time.time()})
                soft_deadline = time.monotonic() + prereg['teardown_soft_seconds']
                while child.poll() is None:
                    if time.monotonic() > soft_deadline and not (root / 'teardown-incomplete.json').exists():
                        write(root / 'teardown-incomplete.json', {'status': 'MANUAL-RECOVERY', 'pid': child.pid,
                              'reason': '300s exceeded; still waiting, no escalation, no next launch'})
                        void(root, 'teardown exceeded 300s')
                    time.sleep(.5)
                stopped = True
                write(root / 'parent-exit.json', {'pid': child.pid, 'returncode': child.returncode,
                                                'unix': time.time(), 'complete_teardown': False})
            watch.stop.set()
            watch.thread.join(5)
            try:
                all_owners_gone = stopped and owned_session_gone(child.pid) and not conflicts(processes())
                require(all_owners_gone, 'native worker remains or ownership uncertain after server exit')
                require(not watch.thread.is_alive() and not watch.failed, 'watcher did not finish cleanly')
                watch.poll()  # fresh journal AFTER server exit, not a cached readiness receipt
                require(stopped, 'server was not started/stopped')
                require(child.returncode == 0, 'server exit code is not clean zero')
                for rank in range(4):
                    receipt = read(root / f'rank-{rank}/teardown.json')
                    require(receipt.get('passed') is True and receipt.get('rank') == rank, 'rank teardown failed')
                write(root / 'stop.json', {'pid': child.pid, 'completed_unix': time.time(),
                      'next_launch_not_before_unix': time.time() + 305, 'all_owners_gone': True})
                require(not (root / 'VOID.json').exists(), 'VOID fixtures')
                require(not (root / 'STOP.json').exists(), 'stop/cleanup budget failure')
                total = sum(f.stat().st_size for i in range(4) for f in (root / f'rank-{i}').rglob('*') if f.is_file())
                require(total <= prereg['shared_fixture_bytes'], 'shared fixture cap')
                write(root / 'receipt.json', {'passed': True, 'status': 'DIAGNOSTIC-PREFIX64-ONLY',
                      'fixture_bytes': total, 'realistic_final_gate': {'passed': False}, 'native_full_qualification': False})
            except BaseException as exc:
                error = error or str(exc)
                void(root, str(exc))
                write(root / 'receipt.json', {'passed': False, 'status': 'VOID', 'error': error})
            if all_owners_gone:
                shutil.rmtree(root / 'scratch')  # only this newly created run's scratch, after exit
            else:
                write(root / 'scratch-retained.json', {'reason': 'live or uncertain owner; manual recovery, no cleanup'})
            for s, handler in old_signals.items():
                signal.signal(s, handler)
        return 1 if error else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'REFUSED: {exc}', file=sys.stderr)
        sys.exit(2)
