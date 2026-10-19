#!/usr/bin/env python3
"""CPU-only native entry rehearsal: python3 -B rehearse_entry.py PROPOSAL.

Reads JSONL proposals, reconstructs lanequeue.command (never executes it),
and tests each declared native ELF with ldd and its help/argument parser.
Both modes scan device/report source and replay safe storage helpers in isolated
children, and run declared CPU preparation probes with the real rank argv.
Both also check Python gate identities throughout the packet, excluding lineage
trees: stale job/unit literals and rejecting lane assertions FAIL; ambiguous
uses WARN without importing or executing packet gates.
--report additionally imports the real entry and
executes its unchanged post-device report source on temporary synthetic receipts.
Packet58 queue runners use one-card WSCREEN or record-window report adapters.
No --plan, model read, queue mutation, service or device entry.

Default binary inventory comes from the packet's build-receipt.json artifacts
or artifacts_sha256. New proposals may declare plan.entry_rehearsal.binaries:
[{"path": "repo/relative/native", "sha256": "...", "args": ["--version"],
  "returncode": 0, "contains": "version"}]. Omit args for --help (including
an explicit unknown-option parser refusal). An empty inventory always fails.
Script coordinators require a packet-specific rehearsal; they fail here rather
than guessing their inner environment. This is only the loader/entry gate;
the packet's real arm/state-machine CPU rehearsal remains separately required.

plan.entry_rehearsal.prepare_probe declares a native command (argv list),
rank_argv (the real device argv; arguments after argv[0] must match), binary
sha256, contains (a first-decode preparation completion marker), optional small
repository metadata paths and their hashes in sources, and output_env (default
ENTRY_PREPARE_OUTPUT). The probe must redirect its writes to that temporary
directory and replace weights/device execution with a CPU transport backend.
It must be built with the device preparation defines. Missing probes WARN;
declared probes that cannot run safely FAIL. timing_evidence lists small saved
JSON receipts with load_seconds/load_ms or ttft_seconds/ttft_ms measurements.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

import entry_sandbox
import launch_env

OPS = Path(__file__).resolve().parent
ROOT = OPS.parents[2]

PACKAGING_CHECKS = ('storage_floor', 'wall_deadlines', 'preparation_path', 'gate_identity')
STORAGE_FLOOR = 25_000_000_000
COLD_TTFT = 60.0


def check_result(findings=(), **extra):
    return dict(status='FAIL' if findings else 'PASS', passed=not findings,
                findings=list(findings), **extra)


JOB_IDENTITY = re.compile(r'packet\d+[a-z]*-[a-z0-9-]+-[AB]')
UNIT_IDENTITY = re.compile(r'(?:screen-[A-Za-z0-9_.-]+|packet58-onecard-[A-Za-z0-9_.-]+)')


def gate_sources(packet):
    """Read Python source only, including gates omitted by packet_sources.

    Never follow symlinks or enter frozen lineage trees. No packet imports,
    binaries, receipts or model data are needed for this check.
    """
    if packet is None:
        return {}
    sources = {}
    for directory, dirs, files in os.walk(packet, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith('lineage')
                         and not (Path(directory) / d).is_symlink())
        for name in sorted(files):
            path = Path(directory) / name
            if path.suffix == '.py' and not path.is_symlink():
                sources[path] = ast.parse(path.read_text())
    return sources


def lane_value(node, lane):
    """Three-valued evaluation: unknown conditions never become a refusal."""
    if (isinstance(node, ast.Name) and node.id == 'lane' or
            isinstance(node, ast.Attribute) and node.attr == 'lane' or
            isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
            and node.slice.value == 'lane' or
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'get' and node.args
            and isinstance(node.args[0], ast.Constant) and node.args[0].value == 'lane'):
        return lane
    if isinstance(node, ast.Constant) and node.value in ('A', 'B'):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = [lane_value(n, lane) for n in node.elts]
        return values if all(v is not None for v in values) else None
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        a, b = lane_value(node.left, lane), lane_value(node.comparators[0], lane)
        if a is None or b is None:
            return None
        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return a == b
        if isinstance(op, ast.NotEq):
            return a != b
        if isinstance(op, (ast.In, ast.NotIn)) and isinstance(b, list):
            return (a in b) if isinstance(op, ast.In) else (a not in b)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = lane_value(node.operand, lane)
        return not value if isinstance(value, bool) else None
    if isinstance(node, ast.BoolOp):
        values = [lane_value(n, lane) for n in node.values]
        decisive = False if isinstance(node.op, ast.And) else True
        if any(v is decisive for v in values):
            return decisive
        if all(v is (not decisive) for v in values):
            return not decisive
    return None


def gate_identity(job, sources):
    """Find stale identities without executing gates or guessing dynamic values.

    Complete job/unit literals are checked exactly (optional .service suffix).
    Paths, command strings, fragments and CPU fixtures are not gate identities;
    ambiguous uses WARN. Lane dispatch alone is not a lane refusal. A definite
    rejecting assert or if/raise fails; conditional/custom require calls WARN.
    Diagnostics contain locations/reasons, never arbitrary source strings.
    """
    findings, warnings = [], []
    name, lane = job.get('name'), job.get('lane')
    unit = 'screen-' + name if isinstance(name, str) else None
    for path, tree in sources.items():
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        fixture = (path.name.startswith('test_') or path.name.endswith('_test.py')
                   or any(isinstance(n, ast.ImportFrom) and n.module == 'unittest.mock'
                          for n in ast.walk(tree)))
        for node in ast.walk(tree):
            ancestors, parent = [], parents.get(node)
            while parent is not None:
                ancestors.append(parent)
                parent = parents.get(parent)
            row = dict(file=str(path), line=getattr(node, 'lineno', 1))
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                bare = value.removesuffix('.service')
                kind = ('job' if JOB_IDENTITY.fullmatch(value) else
                        'unit' if UNIT_IDENTITY.fullmatch(value) else None)
                # Obvious filenames and existing source subdirectories are paths.
                if kind == 'unit' and (Path(value).suffix not in ('', '.service')
                                      or (path.parent / value).is_dir()):
                    continue
                partial = any(isinstance(p, (ast.JoinedStr, ast.BinOp)) for p in ancestors)
                comparison = any(isinstance(p, ast.Compare) for p in ancestors)
                data_literal = (any(isinstance(p, (ast.Call, ast.Dict, ast.List, ast.Tuple))
                                    for p in ancestors) and not comparison)
                if kind and not partial and not fixture and not data_literal:
                    expected = name if kind == 'job' else unit
                    if expected is None:
                        warnings.append(dict(row, reason='proposal identity unavailable'))
                    elif (value if kind == 'job' else bare) != expected:
                        findings.append(dict(row, reason='foreign ' + kind + ' literal'))
                elif kind or JOB_IDENTITY.search(value) or re.search(r'(?:screen-|packet58-onecard-)', value):
                    warnings.append(dict(row, reason='unclassified identity literal'))
            if not isinstance(node, ast.Compare):
                continue
            if not any((isinstance(n, ast.Name) and n.id == 'lane') or
                       (isinstance(n, ast.Attribute) and n.attr == 'lane') or
                       (isinstance(n, ast.Constant) and n.value == 'lane') for n in ast.walk(node)):
                continue
            if not any(isinstance(n, ast.Constant) and n.value in ('A', 'B') for n in ast.walk(node)):
                continue
            assertion = next((p for p in ancestors if isinstance(p, ast.Assert)), None)
            guard = next((p for p in ancestors if isinstance(p, ast.If)), None)
            # A loop may bind lane to another job, and an enclosing branch may
            # make a restriction conditional on state we cannot know here.
            conditional = fixture or any(isinstance(p, (ast.For, ast.While, ast.comprehension)) for p in ancestors)
            rejected = False
            if lane in ('A', 'B') and not conditional:
                if assertion is not None and guard is None:
                    rejected = lane_value(assertion.test, lane) is False
                elif guard is not None and sum(isinstance(p, ast.If) for p in ancestors) == 1:
                    rejected = (lane_value(guard.test, lane) is True
                                and bool(guard.body) and isinstance(guard.body[0], ast.Raise))
                    rejected |= (lane_value(guard.test, lane) is False
                                 and bool(guard.orelse) and isinstance(guard.orelse[0], ast.Raise))
            if rejected:
                findings.append(dict(row, reason='proposal lane rejected'))
            elif (assertion is None or conditional or guard is not None or
                  lane_value(assertion.test, lane) is None and lane_value(node, lane) is not True):
                warnings.append(dict(row, reason='conditional or unclassified lane check'))
    result = check_result(findings, warnings=warnings, files_scanned=len(sources))
    if warnings and not findings:
        result['status'] = 'WARN'
    result['message'] = f'{len(findings)} identity refusals; {len(warnings)} unclassified uses'
    return result


def source_path(node, values):
    """Resolve only literal pathlib expressions; never evaluate packet code."""
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return Path(node.value)
    if isinstance(node, ast.Attribute) and node.attr == 'parent':
        base = source_path(node.value, values)
        return base.parent if base is not None else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        a, b = source_path(node.left, values), source_path(node.right, values)
        return a / b if a is not None and b is not None else None
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in ('Path', 'str') and len(node.args) == 1:
            return source_path(node.args[0], values)
        if isinstance(node.func, ast.Attribute):
            base = source_path(node.func.value, values)
            if base is not None:
                if node.func.attr == 'resolve' and not node.args:
                    return base.resolve()
                if node.func.attr == 'with_name' and len(node.args) == 1:
                    name = source_path(node.args[0], values)
                    if name is not None and len(name.parts) == 1:
                        return base.with_name(str(name))
    return None


def packet_sources(job):
    """Follow local imports and literal worker/report filenames, without imports.

    Frozen lineage, build tools and CPU tests are not device/report modules.
    Unresolved dynamic imports are not claimed as scanned. No evidence/model
    tree walk: only source files in the entry directory and packet root.
    """
    argv = job.get('argv', [])
    if not argv or not Path(argv[0]).name.startswith('python'):
        return None, {}
    entry = report_entry(job)
    packet = next((p for p in entry.parents if p.name.startswith('packet')), entry.parent)
    pending, sources = [entry], {}
    while pending:
        path = pending.pop().resolve()
        if path in sources or not path.is_file() or not path.is_relative_to(packet):
            continue
        if any(p.startswith('lineage') for p in path.relative_to(packet).parts):
            continue
        if re.search(r'(^test_|build|qualify|reseal|prepare_sources)', path.stem):
            continue
        tree = ast.parse(path.read_text())
        sources[path] = tree
        paths = dict(__file__=path, HERE=path.parent, P=path.parent, LOCAL=packet)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                value = source_path(node.value, paths)
                if value is not None:
                    paths.update({target.id: value for target in node.targets if isinstance(target, ast.Name)})
        for node in ast.walk(tree):
            names = []
            if isinstance(node, (ast.Call, ast.BinOp)):
                target = source_path(node, paths)
                if target is not None and target.suffix == '.py' and target.is_absolute():
                    if not re.search(r'(^test_|_gate\.py$)', target.name):
                        pending.append(target)
            if isinstance(node, ast.Import):
                names = [n.name.replace('.', '/') + '.py' for n in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.replace('.', '/') + '.py']
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith('.py'):
                # Literal worker launches and spec_from_file_location imports.
                if '/' not in node.value and not re.search(r'(^test_|_gate\.py$)', node.value):
                    names = [node.value]
            for name in names:
                candidates = [path.parent / name, packet / name]
                # Dynamic vendor paths must not resolve to an unrelated root copy.
                if isinstance(node, ast.Constant):
                    candidates = candidates[:1]
                pending.extend(p for p in candidates[:1] if p.is_file())
                if not candidates[0].is_file() and isinstance(node, (ast.Import, ast.ImportFrom)):
                    pending.extend(p for p in candidates[1:] if p.is_file())
    return packet, sources


def number(node, constants):
    """Evaluate numeric literals/constant arithmetic, never packet code."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = number(node.operand, constants)
        if value is not None:
            return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        a, b = number(node.left, constants), number(node.right, constants)
        if a is None or b is None:
            return None
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Pow) and abs(b) < 32:
            return a ** b
        if isinstance(node.op, ast.Div) and b:
            return a / b
    return None


def constants_in(tree):
    values = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = number(node.value, values)
            if value is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = value
    return values


def storage_scan(sources):
    findings, admissions, functions = [], [], []
    for path, tree in sources.items():
        constants = constants_in(tree)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and re.search(r'storage|disk.*admi', node.name):
                functions.append(dict(path=str(path), function=node.name))
            if not isinstance(node, ast.Compare):
                continue
            text = ast.unparse(node)
            if not re.search(r'free|disk_usage|storage', text, re.I):
                continue
            operands = [node.left, *node.comparators]
            scale = 1024**3 if re.search(r'free_gib\b', text, re.I) else 10**9 if re.search(r'free_gb\b', text, re.I) else 1
            floors = [number(n, constants) for n in operands]
            floors = [n * scale for n in floors if n is not None and n * scale >= 1_000_000]
            if not floors:
                continue
            row = dict(file=str(path), line=node.lineno, floor_bytes=floors[0])
            parent = parents.get(node)
            while parent is not None:
                if isinstance(parent, (ast.Call, ast.Assert)):
                    messages = [n.value for n in ast.walk(parent)
                                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                    for message in messages:
                        match = re.search(r'(\d+(?:\.\d+)?)\s*(GiB|GB)\b', message)
                        if match:
                            stated = float(match[1]) * (1024**3 if match[2] == 'GiB' else 10**9)
                            if stated != floors[0]:
                                row['message_value_mismatch'] = True
                if isinstance(parent, ast.stmt):
                    break
                parent = parents.get(parent)
            # Replay the unchanged admission expression with only its free and
            # write inputs substituted. Full importable functions run separately.
            class Inputs(ast.NodeTransformer):
                def visit_Attribute(self, n):
                    if n.attr == 'free':
                        return ast.copy_location(ast.Constant(25_500_000_000 + 240_000_000), n)
                    return self.generic_visit(n)
                def visit_Name(self, n):
                    if re.search(r'free', n.id, re.I):
                        return ast.copy_location(ast.Constant((25_500_000_000 + 240_000_000) / scale), n)
                    if re.search(r'write|planned', n.id, re.I):
                        return ast.copy_location(ast.Constant(240_000_000 / scale), n)
                    if n.id in constants:
                        return ast.copy_location(ast.Constant(constants[n.id]), n)
                    return n
            expression = Inputs().visit(ast.parse(text, mode='eval'))
            if all(isinstance(n, (ast.Expression, ast.Compare, ast.Constant, ast.BinOp,
                    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Load,
                    ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq)) for n in ast.walk(expression)):
                row['passes_25_5gb_plus_writes'] = bool(eval(compile(expression, '<storage-admission>', 'eval'), {'__builtins__': {}}))
            admissions.append(row)
            # Coordinator 2026-10-19: only floors STRICTER than the shared 25 GB device floor can refuse a
            # healthy launch (packet154's 30 GB). Looser inherited floors (packet56 head support's 8 GB) sit
            # beside the packet's own 25 GB admission and are harmless, so they are not findings.
            if any(f > STORAGE_FLOOR for f in floors) or row.get('message_value_mismatch') or row.get('passes_25_5gb_plus_writes') is False:
                findings.append(row)
    return check_result(findings, admissions=admissions, functions=functions)


def measured_phases(job):
    """Only explicit small saved timing receipts, never planning estimates."""
    phases = {'first_request': COLD_TTFT}
    declaration = job.get('plan', {}).get('entry_rehearsal', {})
    paths = list(declaration.get('timing_evidence', []))
    argv = job.get('argv', [])
    for flag in ('--output', '--output-root'):
        if flag in argv:
            output = resolve(argv[argv.index(flag) + 1])
            paths.extend(str(output / n) for n in ('run/ranks/rank0/receipt.json',
                'run/ranks/rank1/receipt.json', 'run/ranks/native-result.json',
                'run/native-result.json', 'run/bracket-inputs.json', 'summary.json'))
    def visit(value, context=''):
        if isinstance(value, dict):
            context += ' ' + str(value.get('phase', ''))
            for key, child in value.items():
                qualified = context + '_' + key
                phase = ('load' if re.search(r'\b(?:model_)?load_(?:(?:wall|time|duration)_)?(?:seconds|s|ms)$', key)
                         else 'first_request' if re.fullmatch(r'(?:cold_)?ttft_(?:seconds|s|ms)', key)
                         else 'load' if re.search(r'\bload\s*_(?:duration_)?(?:seconds|s|ms)$', qualified) else None)
                if phase and type(child) in (int, float) and 0 < child < 1e9:
                    phases[phase] = max(phases.get(phase, 0), child / (1000 if key.endswith('_ms') else 1))
                visit(child, key)
        elif isinstance(value, list):
            for child in value:
                visit(child, context)
    for name in paths:
        path = resolve(name).resolve()
        if path.is_relative_to(ROOT) and path.suffix == '.json' and path.is_file() and path.stat().st_size <= 1024**2:
            visit(json.loads(path.read_text()))
    return phases


def deadline_scan(sources, phases):
    findings, limits = [], []
    for path, tree in sources.items():
        constants = constants_in(tree)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            bound = None
            is_limit = False
            text = ast.unparse(node)
            if isinstance(node, ast.Compare) and re.search(r'seconds|elapsed|deadline|monotonic|time\(|ttft|duration', text, re.I):
                # Only upper bounds, not minimum cooldowns/positive durations.
                for a, op, b in zip([node.left, *node.comparators], node.ops, node.comparators):
                    if isinstance(op, (ast.Lt, ast.LtE)):
                        bound = number(b, constants)
                        is_limit = bool(re.search(r'seconds|elapsed|deadline|monotonic|time\(|ttft|duration', ast.unparse(a), re.I))
                    elif isinstance(op, (ast.Gt, ast.GtE)):
                        bound = number(a, constants)
                        is_limit = bool(re.search(r'seconds|elapsed|deadline|monotonic|time\(|ttft|duration', ast.unparse(b), re.I))
            elif isinstance(node, ast.keyword) and node.arg == 'timeout':
                bound = number(node.value, constants)
                is_limit = True
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                parent = parents.get(node)
                target = ' '.join(ast.unparse(n) for n in parent.targets) if isinstance(parent, ast.Assign) else ''
                if re.search(r'monotonic\(|time\(|perf_counter\(', text) or 'deadline' in target:
                    bound = number(node.right, constants)
                    is_limit = True
            if not is_limit:
                continue
            enclosing = node
            while enclosing in parents and not isinstance(enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)):
                enclosing = parents[enclosing]
            function = getattr(enclosing, 'name', '')
            # Match the timed phase, not every subprocess to model TTFT. In
            # particular systemctl, coordination and teardown are not inference.
            local = text + ' ' + function
            parent = parents.get(node)
            if isinstance(node, ast.keyword) and parent is not None:
                local += ' ' + ast.unparse(parent)
            proof = 'proof' in local.lower() or ('proof' in function and re.search(r'time|second|deadline', text))
            phase = 'load' if re.search(r'load|startup', local, re.I) else 'first_request'
            matched = proof or bool(re.search(r'request|ttft|prefill|decode|infer|generate|first_minute', local, re.I))
            if phase == 'load':
                matched = True
            # A generic elapsed guard inside a request/proof function also counts.
            row = dict(file=str(path), line=node.lineno, seconds=bound, phase=phase,
                       measured_seconds=phases.get(phase), data_proof=proof)
            if not matched:
                continue
            limits.append(row)
            if proof or (bound is not None and phase in phases and bound < 2 * phases[phase]):
                findings.append(row)
    return check_result(findings, limits=limits, measured_seconds=phases)


def storage_function_child():
    """Import a storage helper under the report I/O guard, then call it unchanged."""
    import inspect
    import runpy
    import shutil
    from collections import namedtuple
    from unittest.mock import patch
    path, function, directory = sys.argv[2:]
    scratch = Path(directory).resolve()
    row = dict(file=path, function=function, status='WARN', message='storage helper not safely importable')
    violations = report_guard(scratch, Path(path).parent)
    try:
        sys.path.insert(0, str(Path(path).parent))
        namespace = runpy.run_path(path, run_name='_storage_rehearsal')
        helper = namespace[function]
        arguments = {}
        for name, parameter in inspect.signature(helper).parameters.items():
            if name in ('path', 'output', 'root'):
                arguments[name] = scratch
            elif re.search(r'write|planned', name):
                arguments[name] = 240_000_000
            elif parameter.default is inspect.Parameter.empty:
                raise ValueError('unsupported storage signature')
        row.update(status='FAIL', message='storage helper refused 25.5 GB plus planned writes')
        usage = namedtuple('usage', 'total used free')(100_000_000_000, 0, 25_740_000_000)
        with patch.object(shutil, 'disk_usage', return_value=usage):
            result = helper(**arguments)
        if result is False or (isinstance(result, dict) and result.get('passed') is False) or violations:
            raise ValueError('storage refused or attempted forbidden I/O')
        row.update(status='PASS', message='storage helper accepts 25.5 GB plus planned writes')
    except Exception:
        pass  # Never return packet exception text.
    (scratch / 'storage-result.json').write_text(json.dumps(row))
    return 0


def replay_storage(functions, env):
    import subprocess
    import tempfile
    rows = []
    for spec in functions:
        with tempfile.TemporaryDirectory(prefix='entry-storage-') as directory:
            with tempfile.TemporaryFile() as output:
                try:
                    cp = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
                        '--storage-probe', spec['path'], spec['function'], directory],
                        env=env, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                        timeout=15, preexec_fn=report_limits)
                    row = json.loads((Path(directory) / 'storage-result.json').read_text())
                    if cp.returncode:
                        row['status'] = 'FAIL'
                except (OSError, ValueError, subprocess.SubprocessError):
                    row = dict(status='FAIL', message='bounded storage helper failed', **spec)
                rows.append(row)
    return rows


def prepare_restrict(binary, metadata, scratch):
    """Landlock: libraries + exact metadata reads, temporary writes, no devices.

    This is the entry sandbox policy with narrowly enumerated probe inputs and
    scratch added. Never grant a packet directory, model directory or /dev.
    """
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 3:
        raise RuntimeError('preparation probe requires Landlock ABI 3')
    handled = (1 << 15) - 1
    ruleset = ctypes.c_uint64(handled)
    fd = libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    if fd < 0:
        raise RuntimeError('preparation sandbox unavailable')
    class Rule(ctypes.Structure):
        _pack_ = 1
        _fields_ = [('access', ctypes.c_uint64), ('parent', ctypes.c_int32)]
    paths = [Path('/usr'), Path('/opt/intel/oneapi'), Path('/etc/ld.so.cache'),
             Path('/etc/ld.so.conf'), Path('/proc/self/maps'), Path('/dev/null'), binary,
             *metadata, scratch]
    paths.extend(binary.parent.glob('*.so*'))
    try:
        for path in paths:
            if not path.exists():
                continue
            path = path.resolve()
            access = (1 | 4 | 8) if path.is_dir() else (1 | 4)
            if path == scratch:
                access = handled & ~(16 | 64 | 128 | 2048 | 4096)  # No device/socket/FIFO creation.
            elif path == Path('/dev/null'):
                access = 2 | 4
            parent = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = Rule(access, parent)
                if libc.syscall(445, fd, 1, ctypes.byref(rule), 0):
                    raise RuntimeError('cannot grant preparation input')
            finally:
                os.close(parent)
        if libc.prctl(38, 1, 0, 0, 0) or libc.syscall(446, fd, 0):
            raise RuntimeError('cannot restrict preparation probe')
    finally:
        os.close(fd)


def declared_preparation(job, packet):
    declaration = job.get('plan', {}).get('entry_rehearsal', {})
    if 'prepare_probe' in declaration:
        return declaration['prepare_probe']
    if packet is None:
        return None
    for receipt in (report_entry(job).parent / 'build-receipt.json', packet / 'build-receipt.json',
                    report_entry(job).parent / 'evidence/build.json'):
        if not receipt.is_file() or receipt.stat().st_size > 1024**2:
            continue
        build = json.loads(receipt.read_text())
        if 'prepare_probe' in build:
            return build['prepare_probe']
        if isinstance(build.get('entry_rehearsal'), dict) and 'prepare_probe' in build['entry_rehearsal']:
            return build['entry_rehearsal']['prepare_probe']
        if build.get('host_build') and build.get('device_defines'):
            raise ValueError('device-define host build must declare its safe real-argv preparation command')
    # Existing packet151 declaration: saved real argv and compiler commands,
    # with a transport-only host backend under the device compilation defines.
    path = report_entry(job).parent / 'evidence/preparation.json'
    if not path.is_file():
        return None
    saved = json.loads(path.read_text())
    if not all(saved.get(k) is True for k in ('device_defines', 'real_shapes', 'transport_only')):
        return None
    commands = saved['commands']
    binary = next((Path(c[c.index('-o') + 1]) for c in commands
                   if '-o' in c and c[c.index('-o') + 1].endswith('/fixed/fixture')), None)
    if binary is None:
        raise ValueError('declared preparation build has no runnable fixture')
    # This legacy adapter is deliberately exact; a new packet declares its
    # command and hashes explicitly instead of executing a build/gate script.
    fixture = report_entry(job).parent / 'native/preparation_fixture.cpp'
    if 'P151_AUDIT_OUTPUT' not in fixture.read_text():
        raise ValueError('unsupported legacy preparation output routing')
    argv = saved['real_rank_argv']
    launch = next(resolve(n) for n in saved['sources'] if n.endswith('/rank0-launch.json'))
    if json.loads(launch.read_text())['argv'] != argv:
        raise ValueError('preparation argv differs from saved real rank launch')
    metadata = [argv[argv.index(flag) + 1] for flag in ('--plan', '--selection', '--dispatch')]
    return dict(command=[str(binary), *argv[1:]], rank_argv=argv,
                sha256=digest(binary), contains='PASS CPU device-branch preparation',
                output_env='P151_AUDIT_OUTPUT', metadata=metadata,
                sources=saved['sources'], legacy_receipt=str(path),
                # This tracked source lookup table is sin/cos, not checkpoint
                # weights. The frozen device object names its packet136 path.
                rotary_source=str(packet.parent / 'packet136-record-bundle/rope.bf16'))


def preparation_probe(job, packet, env, runner=entry_sandbox.run):
    import tempfile
    from unittest.mock import patch
    spec = declared_preparation(job, packet)
    if spec is None:
        return dict(status='WARN', passed=False, message='no preparation-path probe declared', executed=False)
    command, rank = spec['command'], spec['rank_argv']
    if (not isinstance(command, list) or not isinstance(rank, list) or len(command) < 3 or
            command[1:] != rank[1:] or '--rank' not in rank or
            not all(isinstance(a, str) and '\x00' not in a for a in command)):
        raise ValueError('preparation command must preserve real rank argv')
    binary = resolve(command[0]).resolve(strict=True)
    if binary.suffix or not os.access(binary, os.X_OK):
        raise ValueError('preparation command must be a native executable')
    with binary.open('rb') as stream:
        elf = stream.read(4) == b'\x7fELF'
    if not elf or digest(binary) != spec['sha256']:
        raise ValueError('preparation binary identity differs')
    for name, expected in spec.get('sources', {}).items():
        source = resolve(name).resolve()
        if (not source.is_relative_to(ROOT) or source.suffix not in ('.py', '.cpp', '.hpp', '.h', '.c', '.cc', '.json', '.tsv') or
                source.stat().st_size > 2*1024**2 or digest(source) != expected):
            raise ValueError('preparation sources changed')
    metadata = []
    if spec.get('legacy_receipt'):
        rotary = resolve(spec['rotary_source']).resolve(strict=True)
        if (rotary != ROOT / 'experiments/own-xpu-runtime/stage2/packet136-record-bundle/rope.bf16' or
                rotary.stat().st_size != 4194304 or
                digest(rotary) != '92a8f39204b5b8b1969ee2e5d3caac2310ced502bfeb9f51380b537d451ef390'):
            raise ValueError('frozen rotary source identity differs')
        metadata.append(rotary)
    for name in spec.get('metadata', []):
        path = resolve(name).resolve(strict=True)
        if not path.is_relative_to(ROOT) or path.suffix not in ('.json', '.tsv') or path.stat().st_size > 1024**2:
            raise ValueError('preparation input must be small repository metadata')
        metadata.append(path)
    expected = spec['contains']
    if not isinstance(expected, str) or not expected:
        raise ValueError('preparation completion marker required')
    with tempfile.TemporaryDirectory(prefix='entry-preparation-') as directory:
        scratch = Path(directory).resolve()
        key = spec.get('output_env', 'ENTRY_PREPARE_OUTPUT')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or key in ('HOME', 'PATH', 'LD_LIBRARY_PATH'):
            raise ValueError('invalid preparation output environment key')
        # Reuse bounded CPU process management; substitute only Landlock's
        # exact access grants in the forked child, never run unsandboxed.
        with patch.object(entry_sandbox, 'restrict', side_effect=lambda b: prepare_restrict(Path(b), metadata, scratch)):
            cp = runner(launch_env.env_command([f'{key}={scratch}', str(binary), *command[1:]], env),
                        binary=binary, cwd=ROOT, timeout=45)
    passed = cp.returncode == 0 and expected in cp.stdout
    return dict(status='PASS' if passed else 'FAIL', passed=passed, executed=True,
                returncode=cp.returncode, real_rank_argv=True, first_decode_required=True,
                argv_sha256=hashlib.sha256(json.dumps(rank).encode()).hexdigest(),
                binary_sha256=spec['sha256'], legacy_receipt=spec.get('legacy_receipt'),
                preparation_bypassed='native operation bypassed preparation' in cp.stderr,
                message='preparation-path probe completed' if passed else 'preparation-path probe failed')


def packaging_checks(job, env, runner=entry_sandbox.run):
    rows = {}
    if not isinstance(job.get('plan', {}).get('entry_rehearsal', {}), dict):
        return {key: dict(status='FAIL', passed=False, message='invalid entry rehearsal declaration') for key in PACKAGING_CHECKS}
    try:
        packet, sources = packet_sources(job)
    except (OSError, ValueError, SyntaxError, IndexError):
        return {key: dict(status='FAIL', passed=False, message='packet source discovery failed') for key in PACKAGING_CHECKS}
    for key in PACKAGING_CHECKS:
        try:
            if key == 'storage_floor':
                row = storage_scan(sources)
                row['replays'] = replay_storage(row.pop('functions'), env)
                if any(r['status'] == 'FAIL' for r in row['replays']):
                    row.update(status='FAIL', passed=False)
            elif key == 'wall_deadlines':
                row = deadline_scan(sources, measured_phases(job))
            elif key == 'gate_identity':
                row = gate_identity(job, gate_sources(packet))
            else:
                row = preparation_probe(job, packet, env, runner)
            rows[key] = row
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, StopIteration, SyntaxError):
            rows[key] = dict(status='FAIL', passed=False, message='packaging check could not complete safely')
    return rows


def lanequeue():
    directory = OPS / 'lane-queue'
    sys.path.insert(0, str(directory))
    try:
        spec = importlib.util.spec_from_file_location('_entry_lanequeue', directory / 'lanequeue.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


def resolve(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def inventory(job):
    declaration = job.get('plan', {}).get('entry_rehearsal', {})
    if not isinstance(declaration, dict):
        raise ValueError('invalid entry rehearsal declaration')
    explicit = declaration.get('binaries')
    if explicit is not None:
        if not isinstance(explicit, list) or not explicit:
            raise ValueError('empty or invalid native inventory')
        return explicit
    argv = job['argv']
    script = resolve(argv[2] if Path(argv[0]).name.startswith('python') else argv[0])
    packet = next((p for p in (script.parent, *script.parents)
                   if (p / 'build-receipt.json').is_file()), None)
    if packet is None:
        raise ValueError('declare plan.entry_rehearsal.binaries; no build receipt found')
    receipt = json.loads((packet / 'build-receipt.json').read_text())
    if not isinstance(receipt, dict):
        raise ValueError('invalid build receipt')
    artifacts = receipt.get('artifacts', receipt.get('artifacts_sha256', {}))
    if not isinstance(artifacts, dict):
        raise ValueError('invalid build artifact inventory')
    binaries = []
    for name, digest in artifacts.items():
        path = Path(name)
        if not path.is_absolute():
            path = ROOT / path if name.startswith('experiments/') else packet / path
        # No broad tree scans or model/payload reads. Native executables have
        # no extension in the packet build receipts; .o/.a/.bin are not entrypoints.
        if path.suffix or not ('build' in path.parts and any(
                part in path.parts for part in ('device', 'gnu-host', 'host'))):
            continue
        binaries.append(dict(path=str(path), sha256=digest))
    if not binaries:
        raise ValueError('no native binaries in build receipt; declare an explicit inventory')
    return binaries


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unit_environment(job, queue, ldp):
    queue.validate(job, job.get('lane'))
    if 'script' in job:
        raise ValueError('script coordinator needs a packet-specific inner-environment rehearsal')
    command = queue.command(job, '/tmp/entry-review.json', '/tmp/entry-receipt.json', ldp)
    unit = '--unit=screen-' + job['name']
    if unit not in command:
        raise ValueError('lanequeue unit identity changed')
    index = command.index('/usr/bin/env')
    if command[index + 1] != '-i':
        raise ValueError('lanequeue environment is not closed')
    env = {}
    for arg in command[index + 2:]:
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', arg):
            break
        key, value = arg.split('=', 1)
        env[key] = value
    if env != queue.closed_env(ldp):
        raise ValueError('lanequeue environment construction changed')
    return env


def rehearse(job, queue, ldp, runner=entry_sandbox.run, *, report=False):
    name = job.get('name', '?')
    row = dict(job=name, unit='screen-' + name, passed=False, binaries=[],
               service_started=False, arm_sequence_tested=False)
    row.update({key: dict(status='FAIL', passed=False, message='entry validation did not complete')
                for key in PACKAGING_CHECKS})
    try:
        env = unit_environment(job, queue, ldp)
        row['shared_environment_matches'] = env == launch_env.environment()
        native_env = dict(env)
        # Some frozen wrappers replace LD_LIBRARY_PATH from this option. Test
        # that narrower environment as well; do not silently repair the packet.
        argv = job['argv']
        for i, arg in enumerate(argv):
            if arg == '--library-path':
                native_env['LD_LIBRARY_PATH'] = argv[i + 1]
            elif arg.startswith('--library-path='):
                native_env['LD_LIBRARY_PATH'] = arg.split('=', 1)[1]
        row['packet_library_override'] = native_env != env
        row.update(packaging_checks(job, native_env, runner=runner))
        if report:
            row['report'] = rehearse_report(job, env)
        for spec in inventory(job):
            result = dict(passed=False)
            row['binaries'].append(result)
            try:
                result['phase'] = 'identity'
                path = resolve(spec['path']).resolve(strict=True)
                result['binary'] = str(path)
                if path.suffix or not os.access(path, os.X_OK):
                    raise ValueError('inventory entry is not a native executable')
                with path.open('rb') as stream:
                    if stream.read(4) != b'\x7fELF':
                        raise ValueError('inventory entry is not ELF')
                expected = spec.get('sha256')
                if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected):
                    raise ValueError('native inventory requires a SHA256')
                if digest(path) != expected:
                    raise ValueError('native binary differs from recorded build')
                result['phase'] = 'ldd'
                result['unit_ldd'] = launch_env.check_binary(path, env, runner)
                result['native_ldd'] = (launch_env.check_binary(path, native_env, runner)
                                        if native_env != env else result['unit_ldd'])
                if not result['unit_ldd']['passed'] or not result['native_ldd']['passed']:
                    continue
                args = spec.get('args', ['--help'])
                if (not isinstance(args, list) or not args or
                        not all(isinstance(a, str) and '\x00' not in a for a in args)):
                    raise ValueError('invalid native entry probe arguments')
                result['phase'] = 'entry'
                cp = runner(launch_env.env_command([str(path), *args], native_env),
                            binary=path, cwd=ROOT)
                output = cp.stdout + cp.stderr
                if 'args' in spec:
                    match = spec.get('contains')
                    if not isinstance(match, str) or not match:
                        raise ValueError('explicit probe requires expected output text')
                    passed = cp.returncode == spec.get('returncode', 0) and match in output
                else:
                    # A named unknown --help option is itself the binary's own
                    # argument-parse path. A generic rc=1 is never a pass.
                    passed = ((cp.returncode == 0 and bool(re.search(r'usage|options|help', output, re.I)))
                              or (cp.returncode in (1, 2) and bool(re.search(
                                  r'(?:unknown|unrecognized|unexpected|invalid) (?:argument|option)[^\n]*--help',
                                  output, re.I))))
                result.update(passed=passed, entry_returncode=cp.returncode,
                              entry_kind='explicit' if 'args' in spec else 'help-or-parser',
                              entry_timed_out=cp.returncode == 124)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                result['error'] = 'native inventory, loader, or bounded entry check failed'
        row['passed'] = (bool(row['binaries']) and all(b['passed'] for b in row['binaries'])
                         and all(row[k]['status'] != 'FAIL' for k in PACKAGING_CHECKS)
                         and (not report or row['report']['passed']))
    except (OSError, ValueError, KeyError, IndexError, TypeError, RuntimeError):
        # Do not echo arbitrary exceptions, argv, environments or binary output:
        # proposal values can include coordinator secrets.
        row['error'] = 'invalid proposal/inventory, stale binary, or unavailable CPU sandbox'
    return row


# Report rehearsal deliberately has no packet imports in the parent process.
# Every kind starts a fresh interpreter with the job's script directory first.
def report_entry(job):
    argv = job.get('argv', [])
    if len(argv) < 3 or not Path(argv[0]).name.startswith('python') or argv[1] != '-B':
        raise ValueError('report rehearsal needs a Python -B entry')
    path = resolve(argv[2]).resolve(strict=True)
    if path.suffix != '.py':
        raise ValueError('report entry must be Python source')
    return path


def duplicate_modules(packet, paths):
    """Static filesystem check, including unimported modules on active paths."""
    def modules(directory):
        result = {p.stem: p for p in directory.glob('*.py') if p.name != '__init__.py'}
        result.update({p.parent.name: p for p in directory.glob('*/__init__.py')})
        return result
    top = modules(packet)
    rows = []
    for directory in sorted({Path(p).resolve() for p in paths if p}):
        if directory == packet or not directory.is_relative_to(packet):
            continue
        for name, path in sorted(modules(directory).items()):
            if name in top:
                rows.append(dict(module=name, top=str(top[name]), shadow=str(path)))
    return rows


def report_limits():
    import resource
    os.setpriority(os.PRIO_PROCESS, 0, 19)
    os.sched_setaffinity(0, entry_sandbox.CPU)
    resource.setrlimit(resource.RLIMIT_AS, (entry_sandbox.MEMORY, entry_sandbox.MEMORY))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024**2, 1024**2))


def report_guard(scratch, source_root, metadata=()):
    """Deny execution, devices, model/data reads and writes outside scratch.

    Installed Python libraries, repository Python source and the small
    import-time kernel registry/launch environment are the only non-synthetic
    inputs. Audit failures are sticky even if packet code catches
    the exception. This is a trusted-source CPU harness, not a hostile-code VM.
    """
    violations = []
    def audit(event, args):
        denied = event in ('subprocess.Popen', 'os.system', 'os.posix_spawn',
                           'os.exec', 'os.fork', 'os.forkpty', 'os.kill', 'os.killpg',
                           'socket.connect', 'socket.bind', 'ctypes.dlopen')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            write = args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            allowed = path.is_relative_to(scratch)
            if not write:
                allowed |= path in metadata
                allowed |= path.is_relative_to(Path(sys.base_prefix)) and '/site-packages/' not in str(path)
                allowed |= (path.is_relative_to(source_root) or path.is_relative_to(ROOT)) and (path.suffix == '.py' or path.name in ('kernel-registry.json', 'launch-environment.json'))
            # Importlib may try bytecode before source even under -B.
            if not allowed and not write and path.suffix == '.pyc':
                raise PermissionError('bytecode excluded from source rehearsal')
            denied |= not allowed
        if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.rename',
                     'os.link', 'os.symlink', 'os.truncate'):
            count = 2 if event in ('os.rename', 'os.link', 'os.symlink') else 1
            denied |= any(not isinstance(p, (str, bytes, os.PathLike)) or
                          not Path(os.fsdecode(p)).resolve().is_relative_to(scratch)
                          for p in args[:count])
        if denied:
            violations.append(event)
            raise PermissionError('report rehearsal attempted forbidden I/O')
    sys.addaudithook(audit)
    return violations


def oracle_import_prelude(driver):
    """Run the real oracle entry up to its first evidence read.

    The report needs its import/path side effects, not a live oracle seal.
    No report function or import is mocked. The read boundary is intercepted
    by tracing the driver/authority's read or digest helper before it opens data.
    A later import in this data-validation phase is outside this report gate.
    """
    class EvidenceBoundary(Exception):
        pass
    def trace(frame, event, arg):
        if event == 'call' and (frame.f_code.co_name in ('read', 'digest', 'sha') or
                (frame.f_code.co_name == 'read_text' and
                 getattr(frame.f_locals.get('self'), 'suffix', None) != '.py')):
            raise EvidenceBoundary()
        return trace
    sys.settrace(trace)
    try:
        driver.oracle_inputs()
    except EvidenceBoundary:
        pass
    finally:
        sys.settrace(None)


def synthetic_report(common, output, kind, lane):
    """Generate screen-v5 receipts from scratch; never clone device evidence."""
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    oracle = output / 'oracle'
    common.D.ORACLE = oracle  # Data location only; real token parser is retained.
    for prompt in common.D.CHECK.PROMPT_IDS:
        save(oracle / 'results' / prompt / 'result.json', dict(
            schema='iq3-runtime-cpu-oracle.v1', status='token-cap',
            arithmetic=common.ARITHMETIC, tokens=[1] * 128))
    lineage = output / 'lineage'
    save(lineage / 'selection.json', dict(choices=dict(class_layout_bank='synthetic')))
    for rank in (0, 1):
        save(output / 'run/ranks' / f'rank{rank}' / 'class-layout.json', dict(
            class_layout_bank='synthetic', bytes=1, budget=600 * 1024**2, weights=[1]))
    views, selections = [], []
    sibling_cost = common.HERE.parent.name == 'packet151-sibling-cost'
    count = 64 if kind == 'smoke' else 128
    choices = ['candidate'] if kind == 'smoke' else ['control', 'candidate', 'control', 'candidate', 'control']
    for i, choice in enumerate(choices):
        dest = output / 'run/views' / f'{i:02d}-{choice}'
        selection = dict(choice=choice, selection_sha256='synthetic')
        boundary = dict(passed=True, total_reset=True, cached_tokens=0,
                        weight_uploads_after_load=0, selection_sha256='synthetic',
                        arena_descriptors_sha256='a', weight_descriptors_sha256='w')
        for rank in (0, 1):
            save(dest / 'boundary' / f'boundary-rank{rank}.json', boundary)
        incident = dict(passed=True, exact_oracle=True, cached_tokens=0, tokens=[1] * 64)
        receipt = dest / 'incident64/receipt.json'
        save(receipt, incident)
        incident['receipt_sha256'] = digest(receipt)
        requests = [dict(prompt_id=p, prompt_class=common.METRICS.PROMPT_CLASSES[p],
                         passed=True, exact_oracle=True, cached_tokens=0, tokens=[1] * count,
                         token_timestamps=[1 + j * .02 for j in range(count)],
                         tok_s_1_100_intervals_after_ttft=50., hits=1, guesses=2,
                         acceptance=.5, output_tokens=count, requested_max_new=count)
                    for p in common.D.CHECK.PROMPT_IDS]
        if sibling_cost:
            # Real packet151 analysis requires matched proposals and complete
            # half/sibling streams. Supply synthetic data, never mock analyze.
            for request in requests:
                request['guess_rows'] = [dict(position=1, guess=1, actual=1, hit=True)]
        for prompt in ['incident64', *common.D.CHECK.PROMPT_IDS]:
            save(dest / prompt / 'rank1/draft-rows.jsonl', dict(
                draft_position=1, confirmed_token=1, guess=1, head='synthetic'))
            for rank in (0, 1):
                folder = dest / prompt / f'rank{rank}'
                folder.mkdir(parents=True, exist_ok=True)
                (folder / 'p105-transfers.jsonl').write_text('')
                (folder / 'timings.jsonl').write_text('')
            if sibling_cost:
                candidate = choice == 'candidate'
                save(dest / prompt / 'rank0/timings.jsonl', dict(
                    speculative=True, corrected=False, position=1, fixture=1,
                    p151_sibling=candidate, p151_device_ms=2. if candidate else 1.,
                    half_completion_ms=3. if candidate else 2.,
                    p151_sibling_prepare_ms=.1, cancelled=False))
                if candidate:
                    save(dest / prompt / 'rank0/sibling-rows.jsonl', dict(
                        position=1, fixture=1, discarded=True,
                        paired_half_device_ms=2., cancelled=False))
        views.append(dict(index=i, choice=choice, selection_sha256='synthetic', output=str(dest),
                          passed=True, started_utc_ns=100+i*10, finished_utc_ns=105+i*10,
                          boundary=[boundary, boundary], incident64=incident, requests=requests))
        selections.append(selection)
    isolation = dict(passed=True, synthetic_cpu_fixture=True)
    save(output / 'run/device-isolation.json', isolation)
    save(output / 'run/bracket-inputs.json', dict(passed=True, kind=kind, views=views))
    save(output / 'run/report-inputs.json', dict(passed=True, device_isolation=isolation,
         lane=lane, requests=requests, incident64=incident, placement={}))
    return dict(lineage=str(lineage), profile='tp2', lane=lane, timing='token', placement={},
                conditions={}, bracket=dict(kind=kind, views=selections))


def report_statements(screen):
    """Select the unchanged post-device source block, never guess a module name.

    Supports factored report_completed and the older inline screen_main tail.
    Unknown layouts refuse; adding a new schema requires fixtures and tests here.
    """
    import ast
    tree = ast.parse(Path(screen.__file__).read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'screen_main')
    for node in ast.walk(function):
        for field, statements in ast.iter_fields(node):
            if not isinstance(statements, list):
                continue
            for i, statement in enumerate(statements):
                if not isinstance(statement, ast.stmt):
                    continue
                source = ast.unparse(statement)
                if (source.startswith('report_completed(') or
                        (source.startswith('proof = read(') and 'run/report-inputs.json' in source)):
                    end = i + 1
                    while end < len(statements) and not ast.unparse(statements[end]).startswith('record.update('):
                        end += 1
                    if end == len(statements):
                        raise ValueError('unknown report tail boundary')
                    return compile(ast.Module(body=statements[i:end], type_ignores=[]), screen.__file__, 'exec')
    raise ValueError('unsupported report entry layout')


def source_block(path, start, end):
    """Compile an unchanged, bounded report tail from a known main layout."""
    import ast
    tree = ast.parse(Path(path).read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    for node in ast.walk(main):
        for _, statements in ast.iter_fields(node):
            if not isinstance(statements, list):
                continue
            for i, statement in enumerate(statements):
                if isinstance(statement, ast.stmt) and ast.unparse(statement).startswith(start):
                    for j in range(i + 1, len(statements)):
                        if ast.unparse(statements[j]).startswith(end):
                            return compile(ast.Module(body=statements[i:j], type_ignores=[]), str(path), 'exec')
    raise ValueError('unsupported one-card report boundary')


def parse_entry(main, argv):
    """Execute the entry's real main/parser, stopping before admission or I/O."""
    class Parsed(Exception):
        pass
    result = []
    def trace(frame, event, arg):
        if frame.f_code is main.__code__ and event == 'line' and 'args' in frame.f_locals:
            result.append(frame.f_locals['args'])
            raise Parsed()
        return trace
    sys.settrace(trace)
    try:
        main(argv)
    except Parsed:
        pass
    finally:
        sys.settrace(None)
    if len(result) != 1:
        raise ValueError('entry parser boundary missing')
    return result[0]


def synthetic_onecard(driver, views, output, kind, candidate, maintenance):
    """Small invented token/timing receipts, consumed by unchanged packet code."""
    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
    driver['ORACLE'] = output / 'oracle'
    driver['ROOT'] = output
    views.P = output / 'selection-source'  # Data paths only; selection/digest stay real.
    selection = dict(schema='packet49d.selection.v1', decision=None, choices=dict(
        route='route-exp32-rank4', recurrence='rows4-shared', hc='production', down='down-tile16'))
    for view in ('tile16', *views.VIEWS):
        save(views.P / 'selections' / (view + '.json'), selection)
    save(driver['ORACLE'] / 'results/completion.json', dict(synthetic_cpu_fixture=True))
    prompts = []
    for prompt in driver['CHECK'].PROMPT_IDS:
        prompts.append(dict(prompt_id=prompt, prompt_tokens=4, input_bundle='inputs/' + prompt))
        save(output / 'inputs' / prompt / 'input.json', dict(tokens=[2, 3, 4, 5]))
        save(driver['ORACLE'] / 'results' / prompt / 'result.json', dict(
            schema='iq3-runtime-cpu-oracle.v1', status='token-cap',
            arithmetic=driver['ARITHMETIC'], tokens=[1] * 128))
    screen = kind in ('smoke', 'bracket')
    rows = views.bracket(candidate) if screen else [(None, candidate)]
    cap = 64 if kind == 'smoke' else 128
    native = dict(passed=True, safe_to_exit=True, device_executed=True, owner_cards=1,
                  cpu_affinity=[0, 1, 2, 3, 16, 17, 18, 19], observed_nice=0, native_nice=0,
                  selection_sha256=views.digest(candidate), teardown=[dict(
                      safe_to_exit=True, idle_marker_complete=True, exit_code=0, live_bytes=0, in_flight=0)])
    save(output / 'run/receipt.json', native)
    save(output / 'receipt.json', dict(passed=True, safe_to_exit=True,
                                     window='WSCREEN' if screen else kind))
    for label, view in rows:
        dest = output / 'run' if label is None else output / 'run' / label
        # Deliberately slow A0: amended packets must exclude it only from speed,
        # while the older 58v policy correctly returns a negative decision.
        rate = 10 if label == 'A0' else 60 if label in ('B0', 'B1') else 50
        save(dest / 'boundary.json', dict(passed=True, selection_sha256=views.digest(view),
            cache_maintenance=maintenance or view, cache_cap=view if view in ('18GB', 'max') else 'max',
            hc=view, cache_allocation_bytes=getattr(views, 'MAX_BYTES', 18_000_000_000),
            cache_started_empty=True, allocation_ids_preserved=True, weight_uploads_during_switch=0,
            model_loads=1, context_extent=32, arena_descriptors_sha256='a', weight_descriptors_sha256='w'))
        for prompt in prompts:
            request = dest / prompt['prompt_id']
            save(request / 'reset.json', dict(passed=True, cached_tokens=0, allocation_ids_preserved=True))
            save(request / 'result.json', dict(passed=True, arithmetic=driver['ARITHMETIC'],
                tokens=[1] * cap, cached_tokens=0, gpu_count=1, decode_mode='plain', context=4096,
                requested_max_new=cap, prompt_tokens=4, request_start_monotonic=0.,
                request_end_monotonic=1 + cap / rate,
                timing_rows=[dict(completed_monotonic=1 + i / rate) for i in range(cap)]))
    return dict(prompts=prompts)


def onecard_report_probe(job, kind, scratch, source_root):
    import importlib
    import runpy
    from types import SimpleNamespace
    path = report_entry(job)
    packet = path.parent
    # These two small declarative files are read at import by this lineage.
    # No evidence, seal, model input or device file is admitted.
    metadata = {(packet / name).resolve() for name in ('views.json', 'admission.json')}
    violations = report_guard(scratch, source_root, metadata)
    sys.path[0] = str(packet)
    sys.argv = [str(path), *job['argv'][3:]]
    for name in ('launch_env', 'entry_sandbox'):
        sys.modules.pop(name, None)
    entry = runpy.run_path(str(path), run_name='_onecard_entry')
    args = parse_entry(entry['main'], job['argv'][3:])
    window = entry['W']
    screen = 'WSCREEN' in entry['ORDER']
    if screen != (kind in ('smoke', 'bracket')) or job.get('lane', 'A') != 'A':
        raise ValueError('one-card report layout or lane differs')
    views = importlib.import_module('views')
    if screen:
        candidates = [v for a, v in entry['STAGES'] if a != 'smoke']
        if len(candidates) != 1:
            raise ValueError('ambiguous one-card candidate')
        candidate = 'smoke' if kind == 'smoke' else candidates[0]
    else:
        if kind not in entry['ORDER'] or kind not in ('WS128x', 'WS128'):
            raise ValueError('unsupported record window')
        candidate = args.view
    maintenance = getattr(args, 'cache_maintenance', None)
    window_name = 'WSCREEN' if screen else kind
    window_output = scratch / window_name
    driver_output = window_output / 'run'
    # Resolve the actual child route from window.py, without executing a command.
    window_args = SimpleNamespace(window=window_name, view=candidate, card=0,
                                  cache_maintenance=maintenance)
    command = window.native_command(window_args, window_output, 'zero-copy')
    driver_path = Path(command[2]).resolve()
    if command[:2] != ['/usr/bin/python3', '-B'] or driver_path != packet / 'suite_driver.py':
        raise ValueError('unsupported one-card driver route')
    driver = runpy.run_path(str(driver_path), run_name='_onecard_driver')
    # runpy's returned globals are a copy; functions retain the executing dict.
    driver = driver['main'].__globals__
    oracle_import_prelude(SimpleNamespace(oracle_inputs=driver['oracle_inputs']))
    manifest = synthetic_onecard(driver, views, driver_output, kind, candidate, maintenance)
    driver_args = SimpleNamespace(output=driver_output, view=candidate, window=window_name,
                                  cache_maintenance=maintenance)
    namespace = dict(driver, args=driver_args, manifest=manifest, row={})
    exec(source_block(driver_path, 'summary = summarize', 'row.update('), namespace)
    summary = json.loads((driver_output / 'summary.json').read_text())
    if summary.get('passed') is not True or summary.get('request_count') != (60 if kind == 'bracket' else 12):
        raise ValueError('incomplete one-card report')
    # Run the window's unchanged publication tail after its memory/teardown
    # gates. Device admission and postload observations are outside this gate.
    namespace = dict(window.__dict__, output=window_output,
                     args=window_args, admission=SimpleNamespace(scope='whole-host'),
                     record=dict(native_files={}))
    exec(source_block(window.__file__, 'receipt = json.loads(', "record['postload_memory']"), namespace)
    exec(source_block(window.__file__, "summary['timing_claim_eligible']", 'for leaf in'), namespace)
    published = json.loads((window_output / 'summary.json').read_text())
    if published != namespace['summary'] or namespace['record']['native_files']['summary.json'] != digest(window_output / 'summary.json'):
        raise ValueError('window summary closure differs')
    decision = None
    if screen:
        state = {}
        namespace = dict(entry, output=scratch, state=state, save=lambda: None)
        exec(source_block(path, 'decision = json.loads(', 'return 0'), namespace)
        decision = state['qualifies_for_fresh_screen']
        if decision != summary['candidate_beats_all_controls']:
            raise ValueError('queue summary decision differs')
    collisions = duplicate_modules(packet, sys.path)
    return dict(passed=not collisions and not violations, kind=kind, collisions=collisions,
                report_completed=True, synthetic_evidence=True, import_paths=list(sys.path),
                device_executed=False, real_entry_main=True, report_lineage='packet58-onecard',
                admission_executed=False, entry_execution='parser-only',
                window=window_name, request_count=summary['request_count'],
                candidate_beats_all_controls=decision, warmup_view=summary.get('warmup_view'),
                comparison_controls=summary.get('comparison_controls'))


def report_kinds(job):
    """Record chains have window reports, not fictitious smoke/bracket stages."""
    import ast
    path = report_entry(job)
    if path.name == 'queue_runner.py':
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ORDER' for t in node.targets):
                order = ast.literal_eval(node.value)
                if 'WSCREEN' not in order and {'WS128x', 'WS128'} <= set(order):
                    return ('WS128x', 'WS128')
    return ('smoke', 'bracket')


def report_probe(job, kind, scratch, source_root):
    import ast
    import importlib
    import runpy
    from unittest.mock import patch
    path = report_entry(job)
    tree = ast.parse(path.read_text())
    if path.name == 'queue_runner.py' and any(
            isinstance(n, ast.Import) and any(a.name == 'window' and a.asname == 'W' for a in n.names)
            for n in tree.body):
        return onecard_report_probe(job, kind, scratch, source_root)
    if not any(isinstance(n, ast.Call) and ast.unparse(n.func) == 'screen.main' for n in ast.walk(tree)):
        raise ValueError('unsupported entry: no screen.main route')
    packet = next((p for p in path.parents if p.name.startswith('packet')), path.parent)
    violations = report_guard(scratch, source_root)
    sys.path[0] = str(path.parent)
    # The harness's helpers must not shadow the packet's real modules.
    for name in ('launch_env', 'entry_sandbox'):
        sys.modules.pop(name, None)
    argv = [str(path), *job['argv'][3:]]
    for flag, value in [('--kind', kind), ('--output', str(scratch)),
                        ('--fault-review', str(scratch / 'unused-review.json'))]:
        if flag in argv:
            argv[argv.index(flag) + 1] = value
        else:
            argv.extend([flag, value])
    if '--authorized-device-window' not in argv:
        argv.append('--authorized-device-window')
    sys.argv = argv
    # Import the actual entry and its preflight dependencies, in entry order.
    # Only admission checks are replaced; imports and reporting stay real.
    entry_globals = runpy.run_path(str(path), run_name='_report_entry')
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    imports = [n for n in main.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    exec(compile(ast.Module(body=imports, type_ignores=[]), str(path), 'exec'), entry_globals)
    common = importlib.import_module('common')
    screen = importlib.import_module('screen')
    seal = importlib.import_module('cpu_seal')
    readiness = importlib.import_module('readiness')
    rows = []
    def finish(argv):
        # Exercise the screen's real parser as well as the outer entry parser.
        args = screen.parser().parse_args(argv)
        if args.output != scratch or args.lane != job.get('lane', 'B'):
            raise ValueError('entry routed unexpected report arguments')
        oracle_import_prelude(common.D)
        paths = list(sys.path)
        collisions = duplicate_modules(packet, [str(packet), str(path.parent), *paths])
        identity = synthetic_report(common, scratch, kind, args.lane)
        record = dict(started_utc_ns=1, boot_id='synthetic-cpu-only')
        namespace = dict(screen.__dict__, args=args, identity=identity,
                         record=record, coordination={})
        try:
            exec(report_statements(screen), namespace)
        except Exception as error:
            import traceback
            locations = [dict(file=Path(f.filename).name, line=f.lineno)
                         for f in traceback.extract_tb(error.__traceback__)]
            rows.append(dict(passed=False, kind=kind, collisions=collisions,
                             locations=locations, error_type=type(error).__name__,
                             error='report code failed'))
            return 1
        result = json.loads((scratch / 'bracket-summary.json').read_text())
        if result.get('passed') is not True or result.get('kind') != kind:
            raise ValueError('report did not complete requested kind')
        collisions = duplicate_modules(packet, [str(packet), str(path.parent), *sys.path])
        rows.append(dict(passed=not collisions and not violations, kind=kind,
                         collisions=collisions, report_completed=True, synthetic_evidence=True,
                         import_paths=paths, device_executed=False, real_entry_main=True))
        return 0
    # Bracket admission reads a previous device smoke. Replace only that
    # prerequisite reader, never finish/report/summary or its imported symbols.
    # Names come from the actual entry's `from ... import load`, not a guessed
    # generic compare module which could mask the very collision under test.
    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(patch.object(seal, 'verify', return_value=None))
        stack.enter_context(patch.object(readiness, 'verify_ready', return_value=None))
        stack.enter_context(patch.object(screen, 'main', side_effect=finish))
        if kind == 'bracket':
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == 'load' or (node.module == 'smoke_precondition' and alias.name == 'checked_smoke'):
                            module = importlib.import_module(node.module)
                            stack.enter_context(patch.object(module, alias.name, return_value=dict(
                                kind='smoke', passed=True, request_count=12, max_new=64)))
        try:
            runpy.run_path(str(path), run_name='__main__')
        except SystemExit as error:
            if error.code not in (None, 0, 1) or not rows:
                raise ValueError('entry refused report routing') from None
    if len(rows) != 1:
        raise ValueError('entry must route exactly one report')
    return rows[0]


def rehearse_report(job, env, source_root=ROOT):
    import subprocess
    import tempfile
    rows = []
    with tempfile.TemporaryDirectory(prefix='entry-report-') as directory:
        root = Path(directory)
        request = root / 'job.json'
        request.write_text(json.dumps(job))
        try:
            kinds = report_kinds(job)
        except (OSError, ValueError, SyntaxError):
            kinds = ('smoke', 'bracket')  # Child reports the sanitized entry error.
        for kind in kinds:
            scratch = root / kind
            scratch.mkdir()
            result_path = scratch / 'rehearsal-result.json'
            # No packet stdout/stderr is returned: exceptions may contain secrets.
            with tempfile.TemporaryFile() as out:
                try:
                    cp = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
                        '--report-probe', str(request), kind, str(scratch), str(source_root)],
                        env=env, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                        timeout=45, preexec_fn=report_limits)
                    row = json.loads(result_path.read_text()) if result_path.exists() else dict(
                        passed=False, kind=kind, error='report child failed before receipt')
                    row['passed'] &= cp.returncode == 0
                except (OSError, ValueError, subprocess.SubprocessError):
                    row = dict(passed=False, kind=kind, error='bounded report rehearsal failed')
                rows.append(row)
    return dict(passed=all(r['passed'] for r in rows), kinds=rows,
                synthetic_evidence=True, device_executed=False)


def report_child():
    request, kind, directory, source_root = sys.argv[2:]
    scratch = Path(directory).resolve()
    job = json.loads(Path(request).read_text())
    try:
        result = report_probe(job, kind, scratch, Path(source_root).resolve())
    except Exception as error:
        # Only a type, never exception text, packet output or proposal values.
        import traceback
        result = dict(passed=False, kind=kind, error_type=type(error).__name__,
                      locations=[dict(file=Path(f.filename).name, line=f.lineno)
                                 for f in traceback.extract_tb(error.__traceback__)],
                      error='entry import, report schema, or CPU isolation failed')
    (scratch / 'rehearsal-result.json').write_text(json.dumps(result))
    return 0 if result['passed'] else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('proposal', type=Path)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--report', action='store_true', help='also rehearse screen or one-card window reports on synthetic evidence')
    args = ap.parse_args()
    queue = lanequeue()
    # Read only the one non-secret P49_LDP assignment; never source/print file.
    ldp = queue.library_path()
    rows = []
    for line in args.proposal.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        try:
            job = json.loads(line)
            if not isinstance(job, dict) or not isinstance(job.get('name'), str) or not re.fullmatch(
                    r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', job['name']):
                raise ValueError('invalid job')
            row = rehearse(job, queue, ldp, report=args.report)
        except (ValueError, TypeError):
            row = dict(job='invalid-job', passed=False, error='invalid JSONL job')
        rows.append(row)
        for check in PACKAGING_CHECKS:
            result = row.get(check, {})
            if result.get('status') in ('FAIL', 'WARN'):
                print(f"{result['status']} screen-{row['job']}: {check}: "
                      f"{result.get('message', 'packaging check failed')}",
                      file=sys.stderr if args.json else sys.stdout)
        if not args.json:
            print(f'{"PASS" if row["passed"] else "FAIL"} screen-{row["job"]}: '
                  f'{sum(b["passed"] for b in row.get("binaries", []))}/'
                  f'{len(row.get("binaries", []))} native entries; '
                  f'report={row.get("report", {}).get("passed", "not requested")}; '
                  'CPU arm sequence still required')
    if args.json:
        print(json.dumps(dict(passed=bool(rows) and all(r['passed'] for r in rows), jobs=rows), indent=2))
    return 0 if rows and all(r['passed'] for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(storage_function_child() if sys.argv[1:2] == ['--storage-probe'] else
                     report_child() if sys.argv[1:2] == ['--report-probe'] else main())
