#!/usr/bin/env python3
"""Four CPU-only full-snapshot Docker controls; no model requests or server launches.

Commit this runner and its task packet before use: the existing snapshot helper
requires a clean, unchanged repository. OUT must be a new internal-disk directory
outside the repository. Large scratch snapshots use the existing /dev/shm mount.
Nothing changes mounts, swap, cache, GPU or power settings. No retry is performed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TASKS = ('lab-catalog-pending-headlines', 'lab-context-number-boundaries')
IMAGE = 'node@sha256:8a34c4ab3ea2c5cd194f07e317b2a8f09461d3c8b05c4e34c8ccd56d56024c4d'
GIB = 1024 ** 3


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, data):
    """Exclusive durable receipt; a repeated run cannot overwrite old evidence."""
    if not isinstance(data, bytes):
        data = (json.dumps(data, indent=2, sort_keys=True) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    fsync_dir(path.parent)


def admission(out_parent):
    memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    available = int(memory['MemAvailable'].split()[0]) * 1024
    scratch = Path('/dev/shm')
    # Verify the intended existing mount, not a directory on another filesystem.
    mounts = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    matches = [row for row in mounts if row[4] == '/dev/shm']
    if len(matches) != 1 or matches[0][matches[0].index('-') + 1] != 'tmpfs':
        raise RuntimeError('/dev/shm must already be its own tmpfs mount')
    if out_parent.stat().st_dev != Path('/').stat().st_dev:
        raise RuntimeError('OUT must be on the internal root filesystem')
    shm_free = shutil.disk_usage(scratch).free
    root_free = shutil.disk_usage(out_parent).free
    result = {'at': stamp(), 'mem_available_bytes': available, 'shm_free_bytes': shm_free,
              'root_free_bytes': root_free, 'requirements': {
                  'mem_available_bytes': 24 * GIB, 'shm_free_bytes': 10 * GIB,
                  'root_free_bytes': 50 * GIB + 128 * 1024 ** 2}}
    if available < 24 * GIB or shm_free < 10 * GIB or root_free < 50 * GIB + 128 * 1024 ** 2:
        raise RuntimeError('resource admission refused: ' + json.dumps(result))
    return result


def load_sandbox():
    spec = importlib.util.spec_from_file_location('controls_worker_sandbox', ROOT / 'worker/sandbox.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_control(module, task, validation, role, acceptance, out, accepted_identity):
    name = task['id'] + '-' + role
    checkpoint = admission(out)
    destination = out / name
    destination.mkdir()
    fsync_dir(out)
    save(destination / 'admission.json', checkpoint)
    temporary = tempfile.TemporaryDirectory(prefix='worker-full-control-', dir='/dev/shm')
    # Preserve scratch automatically on an incomplete stop or failed durable copy.
    # Cleanup is explicit only after the receipt transaction below succeeds.
    temporary._finalizer.detach()
    scratch = Path(temporary.name) / 'run'
    sandbox = None
    execution = None
    error = None
    commit = validation['baseline_commit' if role == 'baseline' else 'fixed_commit']
    receipt = {'schema': 'lab.worker-full-container-control.v1', 'started_at': stamp(),
               'task_id': task['id'], 'control': role, 'source_commit': commit,
               'image': IMAGE, 'scratch': str(scratch), 'source_scope': 'complete pinned git archive',
               'model_requests': 0, 'retried': False, 'snapshot_deleted': False,
               'acceptance_identity': accepted_identity,
               'sandbox_helper_sha256': sha((ROOT / 'worker/sandbox.py').read_bytes())}
    try:
        module.prepare_snapshot(ROOT, commit, scratch)
        save(destination / 'pre-container-admission.json', admission(out))
        if module._regular_tree(acceptance) != accepted_identity:
            raise RuntimeError('acceptance files changed before container start')
        sandbox = module.DockerSandbox(scratch, IMAGE, acceptance_dir=acceptance)
        sandbox.start()
        execution = sandbox.execute({'command': task['validation_command']})
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    finally:
        if sandbox is not None and not sandbox.stopped:
            try:
                if sandbox.stop_attempted:
                    raise RuntimeError('owned CPU stop already attempted; refusing retry')
                sandbox.stop()
            except Exception as exc:
                error = (error + '; ' if error else '') + f'CPU stop: {type(exc).__name__}: {exc}'
        try:
            if module._regular_tree(acceptance) != accepted_identity:
                raise RuntimeError('acceptance files changed during the control')
        except Exception as exc:
            error = (error + '; ' if error else '') + str(exc)
        stopped = bool(sandbox and sandbox.stopped)
        expected = bool(execution and (
            execution['returncode'] == 0 if role == 'fixed' else
            execution['returncode'] != 0 and task['expected_baseline_error'] in execution['output']))
        receipt.update(finished_at=stamp(), error=error, expected_outcome=expected,
                       passed=not error and stopped and expected, cpu_container_stopped=stopped,
                       container=sandbox.serialize() if sandbox else None)
        # Persist partial evidence too. Any failed write leaves scratch intact.
        copied = {}
        for filename in ('snapshot.json', 'sandbox.json'):
            source = scratch / filename
            if source.exists():
                data = source.read_bytes()
                save(destination / filename, data)
                copied[filename] = {'sha256': sha(data), 'bytes': len(data)}
        save(destination / 'acceptance.json', execution or {'not_executed': True})
        save(destination / 'task.json', task)
        receipt['preserved_files'] = copied
        save(destination / 'receipt.json', receipt)
        fsync_dir(destination)
        fsync_dir(out)
        fsync_dir(out.parent)
    if receipt['passed']:
        temporary.cleanup()
        save(destination / 'cleanup.json', {'at': stamp(), 'scratch_removed': not Path(temporary.name).exists(),
                                           'path': temporary.name, 'after_durable_receipts': True})
    print(json.dumps({'control': name, 'passed': receipt['passed'], 'receipt': str(destination / 'receipt.json'),
                      'scratch_retained': Path(temporary.name).exists()}), flush=True)
    return receipt['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.absolute()
    if any(path.is_symlink() for path in (out, *out.parents)):
        raise ValueError('OUT must not use symlink ancestors')
    if out.resolve().is_relative_to(ROOT) or out.exists() or not out.parent.is_dir():
        raise ValueError('OUT must be a new directory outside the repo with an existing parent')
    admission(out.parent)
    module = load_sandbox()
    acceptance = HERE / 'tasks-a/acceptance'
    accepted_identity = module._regular_tree(acceptance)
    if not accepted_identity:
        raise ValueError('acceptance directory is empty')
    planned = []
    for ident in TASKS:
        task_path = HERE / 'tasks-a' / (ident + '.json')
        task = json.loads(task_path.read_text())
        validation = json.loads((HERE / 'tasks-a/validation' / (ident + '.json')).read_text())
        if (sha(task_path.read_bytes()) != validation['task_sha256']
                or task['source_commit'] != validation['baseline_commit']
                or accepted_identity[validation['acceptance_file']]['sha256'] != validation['acceptance_sha256']):
            raise ValueError('task or acceptance identity differs from frozen validation')
        planned.append((task, validation))
    out.mkdir()
    fsync_dir(out.parent)
    save(out / 'plan.json', {'schema': 'lab.worker-full-container-controls-plan.v1', 'at': stamp(),
                            'runner_sha256': sha(Path(__file__).read_bytes()), 'image': IMAGE,
                            'tasks': [{'id': task['id'], 'baseline_commit': validation['baseline_commit'],
                                       'fixed_commit': validation['fixed_commit']} for task, validation in planned],
                            'acceptance_identity': accepted_identity, 'model_requests': 0})
    for task, validation in planned:
        for role in ('baseline', 'fixed'):
            if not run_control(module, task, validation, role, acceptance, out, accepted_identity):
                return 1
    save(out / 'summary.json', {'at': stamp(), 'controls_passed': 4, 'model_requests': 0,
                               'scope': 'CPU Docker acceptance on complete historical snapshots only'})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
