"""CPU-only description of a bounded, experimental p198 serving owner.

No CLI, directory creation, listener, process launch or operational admission.
The outer coordinator must separately admit faults, memory, ownership and a
reviewed storage budget. This profile is deliberately never live-ready.
The conservative launch-origin idle clock includes model loading: a 215-second
load leaves only 25 seconds of the 240-second soft idle allowance. Slower loading
may exhaust intake before it opens. Ready receipt time is not a proven origin.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
P199 = HERE.parent / 'stage2/packet199-chat-parking'
READY = P199 / 'READY-FOR-DEVICE.json'
READY_SHA256 = '096e731f91f9831e88db693011d49c1d9d64b717e849c2f6a483bd53040b261b'
BINARY_SHA256 = 'c9b401089d95eeb152953a8c0d82d0678de2474934941bc6c97abd4b03287875'
PYTHON = Path('/home/steve/.venvs/vllm-xpu/bin/python')
IDENTITY = HERE / 'checkpoint-fixtures-p198/admitted-engine-identity.json'
BUDGET_RECEIPT = HERE / 'receipts/bounded-serving-storage-budget.json'
BUDGET_SHA256 = 'd877c8f1026cbee39b835d155d213f36f90f1b39cb180bf3c3277ded0f76466b'
DEVICE_AUDIT = P199 / 'evidence/independent-device-result.json'
DEVICE_AUDIT_SHA256 = '335e914aa0cf3db7ee02ec5bec36248382937e049fe80b3ad6bec133f45a3019'
LIMITS = dict(requests=16, context=4096, vocab=248320, max_new=512,
    idle_seconds=240, absolute_seconds=4800, native_idle_seconds=300, native_seconds=7200,
    parking_bytes=512 * 1024**2, save_bound_bytes=256 * 1024**2,
    planned_write_bytes=768 * 1024**2, disk_floor_bytes=27_000_000_000,
    host_required_available_bytes=98_990_252_032, coordinator_margin_bytes=1024**3)


class ProfileRefusal(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise ProfileRefusal(reason)


def sha(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def _baseline():
    require(Path(sys.executable) == PYTHON and Path(sys.prefix) == PYTHON.parent.parent,
            'fixed vllm-xpu interpreter required')
    require(not any(n == 'torch' or n.startswith('torch.') for n in sys.modules), 'no Torch in coordinator')
    require(sha(READY) == READY_SHA256, 'p199 baseline seal changed')
    ready = read(READY)
    require(ready['passed'] is True and ready['device_executed'] is False, 'baseline CPU seal invalid')
    for relative, digest in ready['files_sha256'].items():
        require(sha(ROOT / relative) == digest, 'baseline source drift: ' + relative)
    gate = P199 / 'evidence/device-cpu-gates.json'
    require(sha(gate) == ready['gates_sha256'] and read(gate)['passed'] is True, 'baseline gate mismatch')
    expected = set(ready['external_files_sha256'])
    inventory = {str(PYTHON.resolve()), str(PYTHON.parent.parent / 'pyvenv.cfg')}
    site = PYTHON.parent.parent / 'lib/python3.12/site-packages'
    for name in ('regex', 'jinja2', 'markupsafe'):
        folder = site / name
        require(folder.is_dir() and folder.resolve() == folder, 'dependency root changed')
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix in ('.py', '.so'):
                require(not path.is_symlink(), 'dependency symlink refused')
                inventory.add(str(path))
    require(inventory == expected, 'interpreter/dependency inventory changed')
    # Hashing installed files is insufficient if an ambient package was loaded.
    for name in ('regex', 'jinja2', 'jinja2.sandbox', 'markupsafe'):
        importlib.import_module(name)
    for name, module in tuple(sys.modules.items()):
        if name.split('.')[0] in ('regex', 'jinja2', 'markupsafe'):
            location = getattr(module, '__file__', None)
            require(location is not None and str(Path(location).resolve()) in expected,
                    'loaded codec dependency origin differs: ' + name)
    for path, digest in ready['external_files_sha256'].items():
        require(sha(path) == digest, 'external dependency drift: ' + path)
    identity = read(IDENTITY)
    argv = ready['native_argv']
    binary = Path(argv[2])
    require(argv[:2] == ['/usr/bin/ionice', '-c3'] and sha(binary) == BINARY_SHA256
            and identity['engine']['binary_sha256'] == BINARY_SHA256, 'admitted binary mismatch')
    require(argv.count('--model-dir') == 1, 'model directory flag ambiguous')
    model = Path(argv[argv.index('--model-dir') + 1])
    for row in identity['model']['shard_stat_rows']:
        state = (model / row['name']).stat()
        actual = dict(name=row['name'], size=state.st_size, dev=state.st_dev, ino=state.st_ino,
                      mtime=state.st_mtime_ns, ctime=state.st_ctime_ns)
        require(row == actual, 'admitted model shard stat identity changed')
    return ready, identity, binary


def _paths(output, checkpoint_root, *, fresh):
    paths = [Path(output), Path(checkpoint_root)]
    for path in paths:
        require(path.is_absolute() and '..' not in path.parts and path.is_relative_to(ROOT),
                'absolute repository-local path required')
        require(path.parent.is_dir() and path.parent.resolve() == path.parent,
                'existing real parent required')
        parent = path.parent.stat()
        require(parent.st_dev == ROOT.stat().st_dev and parent.st_uid == os.getuid()
                and not parent.st_mode & 0o022, 'trusted local parent required')
        if fresh:
            require(not os.path.lexists(path), 'fresh output/checkpoint path required; no retry')
        else:
            require(os.path.lexists(path), 'attached private directory missing')
            state = path.lstat()
            require(stat.S_ISDIR(state.st_mode) and state.st_uid == os.getuid()
                    and state.st_dev == parent.st_dev and stat.S_IMODE(state.st_mode) == 0o700,
                    'attached directories must be private0700 and local')
    a, b = paths
    require(a != b and not a.is_relative_to(b) and not b.is_relative_to(a),
            'output/checkpoint roots must be disjoint')
    return dict(output=str(a), owner_output=str(a / 'owner'), checkpoint_root=str(b))


def _argv(baseline, paths):
    argv = list(baseline)
    fixed = {'--context': '4096', '--max-new': '512', '--seconds': '7200',
             '--request-front-idle-seconds': '300', '--cache-bytes': '21552729600',
             '--cache-cap': 'max', '--timing': 'token', '--retain-steps': 'none'}
    for flag, value in fixed.items():
        require(argv.count(flag) == 1 and argv[argv.index(flag) + 1] == value,
                'baseline argument mismatch: ' + flag)
    changes = {'--output': paths['owner_output'], '--request-front-checkpoints': paths['checkpoint_root'],
               '--request-front-max-requests': '16'}
    for flag, value in changes.items():
        require(argv.count(flag) == 1, 'ambiguous argument: ' + flag)
        argv[argv.index(flag) + 1] = value
    require(sum(a != b for a, b in zip(argv, baseline)) == 3, 'exact three argv value deltas required')
    return argv


def _profile(output, checkpoint_root, *, fresh):
    ready, identity, binary = _baseline()
    paths = _paths(output, checkpoint_root, fresh=fresh)
    require(sha(DEVICE_AUDIT) == DEVICE_AUDIT_SHA256 and read(DEVICE_AUDIT)['passed'] is True,
            'actual p199 device provenance changed')
    require(sha(BUDGET_RECEIPT) == BUDGET_SHA256, 'independent storage audit changed')
    budget = read(BUDGET_RECEIPT)
    require(budget['schema'] == 'ownrt.bounded-serving-storage-budget.v1' and
            budget['passed'] is True and budget['live_admission_ready'] is False and
            budget['native_binary_sha256'] == BINARY_SHA256, 'storage audit scope mismatch')
    sources = dict(ready['files_sha256'])
    for relative, digest in budget['source_sha256'].items():
        require(sha(ROOT / relative) == digest and sources.get(relative, digest) == digest,
                'storage audit source drift: ' + relative)
        sources[relative] = digest
    for path in (READY, P199 / 'evidence/device-cpu-gates.json', Path(__file__),
                 HERE / 'test_bounded_serving_profile.py', HERE / 'session_lifecycle.py',
                 HERE / 'test_session_lifecycle.py', HERE / 'bounded_serving_session.py',
                 HERE / 'test_bounded_serving_session.py', HERE / 'test_checkpoint_engine.py',
                 HERE / 'bounded_evidence.py', HERE / 'test_bounded_evidence.py',
                 BUDGET_RECEIPT, DEVICE_AUDIT):
        sources[str(path.relative_to(ROOT))] = sha(path)
    return dict(schema='ownrt.bounded-serving-profile.v1',
        status='CPU experimental; live admission pending', live_admission_ready=False,
        device_executed=False, submission_eligible=False, precision='full BF16 KV',
        model='qwen38-flash-next-ud-iq3-xxs-experimental',
        protocol='ownrt.request-front.v2', checkpoint_contract='v1.2+p198',
        checkpoint_label='experimental-postreply-front', cache_bytes=21_552_729_600,
        paths=paths, limits=dict(LIMITS), binary=dict(path=str(binary), sha256=BINARY_SHA256),
        python=str(PYTHON), identity=identity, native_stop_token_ids=[248044, 248046],
        bind_host='127.0.0.1', native_argv=_argv(ready['native_argv'], paths),
        baseline_ready_sha256=READY_SHA256, device_audit_sha256=DEVICE_AUDIT_SHA256, source_sha256=sources,
        external_sha256=dict(ready['external_files_sha256']),
        storage_budget=dict(status='provisional forecast; independent budget and live admission required',
            receipt_path=str(BUDGET_RECEIPT), receipt_sha256=BUDGET_SHA256,
            audit_reviewed=True, receipt_admitted=False),
        timer_provenance='Coordinator records monotonic immediately before Popen for the absolute origin and explicitly supplies trusted conservative last_native_activity. Launch time is safe but includes loading in the 240-second idle budget; 215 seconds loading leaves 25 seconds. Ready-receive or wrapper-construction time must not silently reset it. A later origin needs separate source/timing proof.',
        required_outer_gates=['source closure', 'reviewed storage budget', 'fresh private directories',
            'whole-host reservation', 'drain permit', 'reviewed boot fault baseline', 'memory and disk forecast',
            'unlimited AS', 'one owner and card0 proof', 'continuous passive guards', 'one incident SIGTERM',
            'clean native exit and physical drain'])


def build_profile(output: Path, checkpoint_root: Path):
    """Read-only CPU plan; refuses used destinations. Does not reserve storage."""
    profile = _profile(output, checkpoint_root, fresh=True)
    require(shutil.disk_usage(ROOT).free - LIMITS['planned_write_bytes'] >= LIMITS['disk_floor_bytes'],
            'root forecast below27GB floor')
    return profile


def validate_profile(profile, *, check_fresh=True):
    """Recheck every pin. Attached mode checks existing0700 roots, not freshness.

    This never grants permission to launch or establishes operational readiness.
    A fresh forecast reserves the entire proposed write budget; attached mode
    checks the current floor because existing checkpoints already consume space.
    """
    require(type(profile) is dict and type(check_fresh) is bool, 'profile/mode invalid')
    paths = profile.get('paths', {})
    require(type(paths) is dict and set(paths) == {'output', 'owner_output', 'checkpoint_root'}, 'paths missing')
    expected = _profile(paths['output'], paths['checkpoint_root'], fresh=check_fresh)
    require(json.dumps(profile, sort_keys=True, allow_nan=False) ==
            json.dumps(expected, sort_keys=True, allow_nan=False),
            'profile identity, limits, argv or source pins changed')
    planned = LIMITS['planned_write_bytes'] if check_fresh else 0
    require(shutil.disk_usage(ROOT).free - planned >= LIMITS['disk_floor_bytes'], 'root storage floor refused')
