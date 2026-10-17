"""Packet53 coordinator helpers and pure CPU admission checks.

Importing this file never runs a journal query, child, health check or device.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SPEC = importlib.util.spec_from_file_location(
    'packet53_inherited_supervision', HERE.parent / 'packet34-replay-bench/window.py')
SUPERVISION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPERVISION)
# Extend the private imported supervisor's signatures without editing packet34.
# Keep specific driver messages; generic words such as "hang" are not faults.
SUPERVISION.FAULT = re.compile(
    r'Fault response|CAT error|(?:GPU |engine )reset|timed[- ]out job|job.*timed out|'
    r'devcoredump|(?:device |GPU |xe.*)coredump', re.I)
_inherited_process_tree_anon = SUPERVISION.process_tree_anon


def _exited_status(proc, pid):
    """True when /proc shows the pid as a zombie/dead task (its mm fields are gone)."""
    try:
        status = (proc / str(pid) / 'status').read_text()
    except (FileNotFoundError, ProcessLookupError):
        return True
    state = [line.split()[1] for line in status.splitlines() if line.startswith('State:')]
    if bool(state) and state[0] in ('Z', 'X'):
        return True
    # 2026-10-17 p52-a-e1: exit_mm() drops RssAnon before the task becomes a
    # zombie, so a still-R/D task can lack it. Accept only the kernel's own
    # PF_EXITING flag (0x4, /proc/PID/stat field 9); live tasks still fail.
    try:
        fields = (proc / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return not (proc / str(pid)).exists()
    except (IndexError, OSError):
        return False
    return len(fields) > 6 and fields[6].isdigit() and bool(int(fields[6]) & 0x4)


def process_tree_anon(pid, proc=Path('/proc')):
    """2026-10-17 p48-a-e1: RssAnon is absent while the native child is a zombie at exit.
    A zombie owns no anonymous memory, so report the tree without it instead of failing."""
    try:
        return _inherited_process_tree_anon(pid, proc)
    except Exception as error:
        if 'missing/malformed RssAnon' in str(error) and _exited_status(proc, int(str(error).rsplit(' ', 1)[-1])):
            return _inherited_process_tree_anon_skip_exited(pid, proc)
        raise


def _inherited_process_tree_anon_skip_exited(pid, proc):
    pending, seen, rows = [pid], set(), []
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        if _exited_status(proc, current):
            continue
        base = proc / str(current)
        try:
            status = base.joinpath('status').read_text()
            values = [line.split() for line in status.splitlines() if line.startswith('RssAnon:')]
            require(len(values) == 1 and len(values[0]) == 3 and values[0][2] == 'kB',
                    'missing/malformed RssAnon for pid ' + str(current))
            rows.append({'pid': current, 'rss_anon_bytes': int(values[0][1]) * 1024})
            for task in base.joinpath('task').iterdir():
                try:
                    pending.extend(int(child) for child in task.joinpath('children').read_text().split())
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass
    return {'anonymous_bytes': sum(row['rss_anon_bytes'] for row in rows),
            'root_seen': any(row['pid'] == pid for row in rows),
            'processes': sorted(rows, key=lambda row: row['pid'])}


SUPERVISION.process_tree_anon = process_tree_anon
require = SUPERVISION.require
sha = SUPERVISION.sha
save = SUPERVISION.save


def inside(root, name):
    relative = Path(name)
    path = (root / relative).resolve()
    external = Path('/home/steve/own-xpu-runtime-results/packet53-expert-order')
    # This packet's explicitly registered build/evidence symlinks are the only
    # external storage accepted by its seal and source verifier.
    external_ok = False
    for leaf in ('build', 'evidence'):
        registered = HERE / leaf
        if registered.is_symlink() and registered.resolve() == external / leaf:
            lexical = root / relative
            if lexical.is_relative_to(registered):
                external_ok = path.is_relative_to(external / leaf)
    require(not relative.is_absolute() and '..' not in relative.parts
            and (path.is_relative_to(root.resolve()) or external_ok), 'unsafe sealed path: ' + str(name))
    return path


def verify_files(files, root):
    require(isinstance(files, dict) and bool(files), 'empty identity closure')
    for name, digest in files.items():
        require(isinstance(digest, str) and len(digest) == 64, 'invalid identity digest')
        require(sha(inside(root, name)) == digest, 'sealed input changed: ' + name)


def sealed_gate(path=None, *, root=HERE, repo=REPO):
    path = root / 'seal.json' if path is None else Path(path)
    seal = json.loads(path.read_text())
    require(seal.get('schema') == 'own-runtime.packet53.seal.v1'
            and seal.get('passed') is True and seal.get('device_executed') is False,
            'missing or incomplete CPU preparation seal')
    verify_files(seal.get('sources'), repo)
    verify_files(seal.get('artifacts'), root)
    required_gates = {'python-gates.json','cpu-gates.json','build-receipt.json'}
    require(set(seal.get('gates', {})) == required_gates, 'complete named CPU gates required')
    verify_files(seal.get('gates'), root)
    for name in seal['gates']:
        row = json.loads(inside(root, name).read_text())
        require(row.get('passed') is True and row.get('device_executed') is False,
                'failed or non-CPU gate: ' + name)
    require('build/device/expert-order-bench' in seal['artifacts'], 'device binary not bound')
    return seal


def environment(source=None):
    return SUPERVISION.environment_gate(source)


def host_memory():
    fields = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemAvailable', 'MemFree', 'SwapFree', 'SwapTotal'):
            fields[key] = int(value.split()[0]) * 1024
    require(fields.get('MemAvailable', 0) >= 16 * 1024**3,
            'single-layer fixture window requires 16 GiB available host memory')
    return fields


def storage(path, planned_write_bytes=64 * 1024**2):
    parent = Path(path)
    while not parent.exists():
        parent = parent.parent
    free = shutil.disk_usage(parent).free
    require(free - planned_write_bytes >= 8_000_000_000,
            'window would breach unchanged 8 GB free-storage floor')
    return dict(free_bytes=free, planned_write_bytes=planned_write_bytes,
                min_free_bytes=8_000_000_000)


def identity(seal_path, environment, boot):
    return dict(seal_sha256=sha(seal_path),
                binary_sha256=sha(HERE / 'build/device/expert-order-bench'),
                card=0, boot_id=boot, environment=environment)


def prerequisite(paths, current, *, expected_mode='exact'):
    require(len(paths) == 2 and len({str(Path(p).resolve()) for p in paths}) == 2,
            'two distinct fresh-process exactness windows required')
    rows = []
    for path in paths:
        path = Path(path).resolve()
        row = json.loads(path.read_text())
        require(row.get('schema') == 'own-runtime.packet53.window.v1' and
                row.get('passed') is True and row.get('mode') == expected_mode and
                row.get('device_executed') is True and row.get('child_still_running') is False,
                'incomplete exactness companion')
        for key in ('seal_sha256', 'binary_sha256', 'card', 'boot_id', 'environment', 'coordinator_fault_review'):
            require(row.get(key) == current.get(key), 'companion identity changed: ' + key)
        require(isinstance(row.get('pid'), int) and row['pid'] > 0
                and bool(row.get('process_start_ticks')), 'companion owner identity missing')
        verify_files(row.get('native_files'), path.parent)
        require(set(row['native_files']) == {'run/receipt.json','run/comparisons.jsonl','run/iterations.jsonl','run/manifest.json'}, 'complete native companion closure required')
        from summarize import exact
        native = exact(path.parent / 'run')
        require(native['exact_output_identity'] == row.get('exact_output_identity'), 'companion native output identity changed')
        rows.append(row)
    require(len({(row['pid'], row['process_start_ticks']) for row in rows}) == 2,
            'exactness owners were not fresh processes')
    require(rows[0].get('exact_output_identity') and
            rows[0]['exact_output_identity'] == rows[1].get('exact_output_identity'),
            'fresh-process complete output/state identity differs')
    return [dict(path=str(Path(p).resolve()), sha256=sha(p)) for p in paths]


def process_start(pid):
    # stat comm can contain spaces and parentheses; fields after its final ')'
    # begin at field 3, making starttime (field 22) index 19.
    data = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return int(data[19])


def gpu_clients(proc=Path('/proc')):
    """Passive fdinfo check, never opens a DRM device or invokes xpu-smi.

    Refuse visible render/compute clients even if idle: the coordinator releases
    other work before this one-card microbenchmark. Permission-hidden clients
    remain a coordinator ownership responsibility, explicitly recorded.
    """
    clients, inaccessible = [], 0
    for pid in proc.iterdir():
        if not pid.name.isdigit():
            continue
        try:
            files = list((pid / 'fdinfo').iterdir())
        except PermissionError:
            inaccessible += 1
            continue
        except FileNotFoundError:
            continue
        for info in files:
            try:
                text = info.read_text()
            except PermissionError:
                inaccessible += 1
                continue
            except (FileNotFoundError, ProcessLookupError):
                continue
            fields = dict(line.split(':', 1) for line in text.splitlines() if ':' in line)
            if fields.get('drm-driver', '').strip() == 'xe':
                clients.append(dict(pid=int(pid.name), fd=info.name,
                                    pci=fields.get('drm-pdev', '').strip()))
    require(not clients, 'foreign Xe clients present; coordinator must release ownership: ' + str(clients))
    return dict(visible_xe_clients=clients, inaccessible_entries=inaccessible,
                method='passive /proc fdinfo only; no device discovery')
