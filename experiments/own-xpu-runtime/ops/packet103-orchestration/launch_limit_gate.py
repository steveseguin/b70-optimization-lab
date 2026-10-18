"""CPU-only pre-exec rehearsal of the real composite, shell and chain entries.

Only host/device admission and future composite *results* are synthetic. Source,
selection, startup, seal, oracle and command validation execute the real code.
Native Popen calls are intercepted after their real argv has been constructed.
No executable from a build directory may run. All writes go to a temp directory.
"""
import argparse
import ast
import contextlib
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import resource
import re
import runpy
import shlex
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

O = Path(__file__).resolve().parent
ROOT = O.parents[3]
P = ROOT/'experiments/own-xpu-runtime/stage2/packet103-record-bundle'
DECISION = O/'decisions/1ad512f75aab3fce.json'
SELF = Path(__file__).resolve()
sys.path[:0] = [str(O), str(P)]
REAL_POPEN = subprocess.Popen


def limits():
    return {name: list(resource.getrlimit(getattr(resource, name)))
            for name in sorted(dir(resource)) if name.startswith('RLIMIT_')}


class Reached(BaseException):
    pass


class GateRefusal(BaseException):
    """Leave before real error recovery, which is also device-owning code."""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class OldReader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Replay the exact old import, in an expendable child (hard cap irreversible)."""
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'read_screens':
            return importlib.util.spec_from_loader(fullname, self, origin=str(O/'read_screens.py'))

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = str(O/'read_screens.py')
        exec(compile((O/'frozen103/read_screens.py').read_bytes(), module.__file__, 'exec'), module.__dict__)


def module_audit():
    paths = set()
    pending = list(sys.modules.values())
    seen = set()
    while pending:
        module = pending.pop()
        if id(module) in seen:
            continue
        seen.add(id(module))
        filename = getattr(module, '__file__', None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(ROOT) and path.suffix == '.py':
                paths.add(path)
                pending.extend(value for value in vars(module).values() if isinstance(value, ModuleType))
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def resource_audit(cases):
    paths = set(O.glob('*.py')) | set(P.glob('*.py'))
    for case in cases:
        paths.update(ROOT/name for name in case.get('imports', {}))
    rows, callers = [], []
    for path in sorted(paths):
        tree = ast.parse(path.read_text())
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call): continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ''
            if name not in ('setrlimit', 'prlimit', 'limits'): continue
            ancestor = node
            scope = None
            while ancestor in parents:
                ancestor = parents[ancestor]
                if isinstance(ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scope = ancestor.name; break
                if isinstance(ancestor, ast.If) and '__name__' in ast.unparse(ancestor.test) and '__main__' in ast.unparse(ancestor.test):
                    scope = '__main__'; break
            row = dict(path=str(path.relative_to(ROOT)), line=node.lineno, call=name, scope=scope)
            (callers if name == 'limits' else rows).append(row)
            assert scope is not None, 'import-time resource mutation: '+str(row)
    shell = [O/'device-entry.sh', Path('/tmp/claude-1000/-home-steve/fn-run/p49.env')]
    shell_rows = []
    for path in shell:
        # Read deployment configuration only for this audit; never retain content.
        text = path.read_text()
        assert not re.search(r'\b(?:ulimit|prlimit|setrlimit)\b', text), 'shell resource mutation: '+str(path)
        shell_rows.append(dict(path=str(path), sha256=digest(path), resource_mutations=0))
    return dict(passed=True, scanned_python_files=len(paths), mutations=rows,
                explicit_cpu_limit_callers=callers, shell=shell_rows,
                historical_snapshots='frozen103 and lineage-inputs are evidence, never active imports')


def probe(args):
    baseline = json.loads(args.baseline.read_text())
    observations = []
    child_imports = {}
    tmp = args.scratch
    tmp.mkdir(parents=True, exist_ok=True)
    allowed = args.baseline.parent.resolve()
    def audit(event, values):
        if event == 'open' and isinstance(values[0], (str, bytes)):
            path = Path(os.fsdecode(values[0])).absolute()
            if str(path).startswith('/dev/dri/'):
                raise GateRefusal('device open forbidden in CPU rehearsal')
            flags = values[2] or 0
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                if path != Path('/dev/null') and not path.resolve().is_relative_to(allowed):
                    raise GateRefusal('write outside rehearsal directory: '+str(path))
        if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
            for value in values[:2] if event == 'os.rename' else values[:1]:
                if isinstance(value, (str, bytes)) and not Path(os.fsdecode(value)).resolve().is_relative_to(allowed):
                    raise GateRefusal('filesystem change outside rehearsal directory')
        if event in ('os.system', 'os.exec', 'os.posix_spawn'):
            raise GateRefusal('unintercepted execution forbidden in CPU rehearsal')
    sys.addaudithook(audit)
    if args.old_reader:
        sys.meta_path.insert(0, OldReader())

    def observe(stage, argv, assert_equal=True):
        actual = limits()
        row = dict(stage=stage, argv=list(map(str, argv)), limits=actual,
                   unchanged=actual == baseline, pid=os.getpid())
        observations.append(row)
        if assert_equal:
            if actual['RLIMIT_AS'] != [resource.RLIM_INFINITY]*2:
                raise GateRefusal('RLIMIT_AS is not unlimited at '+stage)
            if actual != baseline:
                raise GateRefusal('resource limits changed at '+stage)

    def child(role, argv, env=None):
        cmd = [sys.executable, '-B', str(SELF), '--probe', role,
               '--baseline', str(args.baseline), '--scratch', str(tmp/role),
               '--receipt', str(tmp/(role+'.json')), '--', *map(str, argv)]
        # This launches only this CPU interception harness, never the device entry.
        cp = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, env=env, timeout=240)
        if (tmp/(role+'.json')).exists():
            nested = json.loads((tmp/(role+'.json')).read_text())
            observations.extend(nested['observations'])
            child_imports.update(nested['imports'])
        assert cp.returncode == 0, cp.stderr[-4000:]
        raise Reached()

    def popen(cmd, *pos, **kw):
        argv = list(map(str, cmd))
        if str(SELF) in argv or str(O/'source_adapter.py') in argv or str(P/'check_inputs.py') in argv:
            return REAL_POPEN(cmd, *pos, **kw)
        if str(P/'worker.py') in argv:
            observe('composite-to-worker', argv, assert_equal=False)
            return child('worker', argv[argv.index(str(P/'worker.py'))+1:], kw.get('env'))
        if str(P/'chain103.py') in argv:
            observe('chain-to-window', argv)
            return child('window', argv[argv.index(str(P/'chain103.py'))+1:])
        if any('/build/' in arg for arg in argv[:4]):
            observe('native-pre-exec', argv)
            # Reach both rank/card launch sites without starting either binary.
            native = [r for r in observations if r['stage'] == 'native-pre-exec']
            if len(native) == 2:
                raise Reached()
            return SimpleNamespace(pid=99999999, poll=lambda: 0, returncode=0)
        raise AssertionError('unregistered subprocess in CPU-only launch gate: '+repr(argv[:4]))

    result = dict(passed=False, device_executed=False, synthetic_admission=True,
                  entry=args.probe, observations=observations)
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(subprocess, 'Popen', side_effect=popen))
            if args.probe == 'composite':
                import composite_screen as entry
                import run_screen
                import screen
                wrapper_seal = screen.HERE/'placement-validation/wrapper-seal.json'
                screen.HERE = tmp/'wrapper'
                screen.HERE.mkdir()
                (screen.HERE/'placement-validation').mkdir()
                (screen.HERE/'placement-validation/wrapper-seal.json').write_bytes(wrapper_seal.read_bytes())
                (tmp/'v3').mkdir()
                entry.WRAPPER = screen.HERE
                # No actual lease, systemd service, journal, device census or latch.
                class Lease:
                    record = {}
                    def __init__(self, *a, **k): self.record = {}
                    def __enter__(self): return self
                    def __exit__(self, *a): return False
                fixtures = {'lane_gate': None, 'screen_teardown_admit': None,
                            'unit_gate': None, 'unit_conditions': {},
                            'topology_admit': {}, 'selected_clients': []}
                for name, value in fixtures.items():
                    stack.enter_context(patch.object(screen, name, return_value=value))
                stack.enter_context(patch.object(screen, 'Reservation', Lease))
                stack.enter_context(patch.object(screen.fault_review, 'validate', return_value=({}, '', '', 'CPU-fixture')))
                stack.enter_context(patch.object(screen.S, 'journal', return_value=('', 'CPU-fixture')))
                stack.enter_context(patch.object(screen.W, 'memory_fence', return_value={}))
                stack.enter_context(patch.object(screen.S, 'ldd_preflight', return_value={'cpu_fixture': True}))
                rc = entry.main(['--decision', str(DECISION), '--decision-sha256', digest(DECISION),
                            '--attempt', 'x', '--lane', args.lane, '--index', str(args.index),
                            '--fault-review', str(tmp/'synthetic-review.json'), '--authorized-device-window'])
                reasons = [json.loads(path.read_text()).get('stop_reasons')
                           for path in tmp.rglob('window.json')]
                raise AssertionError(f'entry returned {rc} without completing native interception: {reasons}')
            elif args.probe == 'worker':
                from bootstrap import install
                install()
                import conditions
                import devices
                stack.enter_context(patch.object(conditions, 'lane_gate'))
                stack.enter_context(patch.object(devices.DeviceMonitor, 'register'))
                stack.enter_context(patch.object(devices.DeviceMonitor, 'poll'))
                stack.enter_context(patch.object(conditions, 'Teardown', side_effect=lambda *a, **k: contextlib.nullcontext()))
                sys.argv = [str(P/'worker.py'), *args.entry_args]
                runpy.run_path(str(P/'worker.py'), run_name='__main__')
            elif args.probe == 'chain':
                import chain103
                q, w = chain103.install()
                for name in ('user_unit_gate',):
                    stack.enter_context(patch.object(q, name))
                stack.enter_context(patch.object(q.os, 'getpriority', return_value=0))
                stack.enter_context(patch.object(q.os, 'sched_getaffinity', return_value=q.DEVICE_CORES))
                stack.enter_context(patch.object(q, 'journal', return_value='CPU-fixture'))
                stack.enter_context(patch.object(q, 'admitted_output', return_value=tmp/'chain'))
                # Prefix proof and input preflight remain real, including --window K0.
                sys.argv = [str(P/'chain103.py'), *args.entry_args]
                chain103.main()
            elif args.probe == 'window':
                import chain103
                q, w = chain103.install()
                admission = SimpleNamespace(check=lambda: None, record={'clients': []}, scope='lane-A')
                stack.enter_context(patch.object(w, 'run_window', side_effect=lambda main, **kw: main(admission=admission)))
                stack.enter_context(patch.object(w, 'journal', return_value=('', 'CPU-fixture')))
                stack.enter_context(patch.object(w, 'environment_gate', return_value={'native': {'PATH': '/usr/bin:/bin', 'OMP_NUM_THREADS': '2'}}))
                stack.enter_context(patch.object(w, 'output_path', side_effect=lambda path, **kw: path))
                stack.enter_context(patch.object(w, 'admit_output', return_value={'cpu_fixture': True}))
                stack.enter_context(patch.object(w, 'ldd_preflight', return_value={'cpu_fixture': True}))
                stack.enter_context(patch.object(w.Watch, 'check'))
                stack.enter_context(patch.object(w.Watch, 'mark_launched'))
                stack.enter_context(patch.object(w.Watch, 'latch'))
                sys.argv = [str(P/'chain103.py'), *args.entry_args]
                chain103.main()
            else:
                raise AssertionError(args.probe)
    except Reached:
        result['passed'] = True
    except BaseException as error:
        result['error'] = type(error).__name__+': '+str(error)
    finally:
        result['refusals'] = [json.loads(path.read_text()).get('error') for path in tmp.rglob('failure.json')]
        if result.get('error') and result['refusals']:
            result['error'] += ': '+str(result['refusals'])
        result['imports'] = {**child_imports, **module_audit()}
        args.receipt.write_text(json.dumps(result, indent=2)+'\n')
    if not result['passed']:
        print(result.get('error', 'no native boundary reached'), file=sys.stderr)
    return 0 if result['passed'] else 1


def shell_python(argv, baseline, scratch):
    """PATH shim for the *unchanged* device-entry.sh, with future-result fixture."""
    argv = list(argv)
    if argv and argv[0] == '-B': argv.pop(0)
    if argv and argv[0] == str(O/'verify_ready.py'):
        import verify_ready
        import decision_readiness as d
        config = json.loads(DECISION.read_text())
        row = json.loads((O/'ready.json').read_text())
        # Only the as-yet-unmeasured composite result is synthetic. It cannot
        # escape this temp directory or authorize a real launch.
        measured = dict(passed=True, chain_policy_passed=True, fixture_only=True)
        row.update(ready=True, preparation_passed=True, composition=measured,
                   checks={label: digest(O/(label+'.log')) for label in
                           ('cpu-dry-run', 'seal', 'inputs', 'storage', 'queue-plan')},
                   pins={str(P.relative_to(ROOT))+'/build-receipt.json': digest(P/'build-receipt.json')})
        scratch.mkdir(exist_ok=True)
        (scratch/'ready.json').write_text(json.dumps(row))
        with patch.object(verify_ready, 'O', scratch), patch.object(d, 'matched', return_value=measured):
            verify_ready.verify()
        assert limits() == json.loads(baseline.read_text())
        return 0
    if argv and argv[0] == '-c':
        # The shell's exact output-path check, no model import or execution.
        assert 'chain_output' in argv[1]
        exec(compile(argv[1], '<device-entry output check>', 'exec'), {'__name__': '__main__'})
        return 0
    raise AssertionError('unexpected shell Python command')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe', choices=('composite', 'worker', 'chain', 'window'))
    ap.add_argument('--lane', choices=('A', 'B'), default='A')
    ap.add_argument('--index', type=int, choices=range(3), default=0)
    ap.add_argument('--old-reader', action='store_true')
    ap.add_argument('--baseline', type=Path)
    ap.add_argument('--scratch', type=Path)
    ap.add_argument('--receipt', type=Path)
    ap.add_argument('--shell-python', action='store_true')
    ap.add_argument('--chain-only', action='store_true', help='CPU harness debugging; not the complete gate')
    ap.add_argument('entry_args', nargs=argparse.REMAINDER)
    args = ap.parse_args()
    if args.entry_args[:1] == ['--']: args.entry_args.pop(0)
    if args.shell_python:
        return shell_python(args.entry_args, args.baseline, args.scratch)
    if args.probe:
        return probe(args)
    assert limits()['RLIMIT_AS'] == [resource.RLIM_INFINITY]*2, 'coordinator baseline must be unlimited'
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    report = dict(passed=False, device_executed=False, coordinator_limits=limits(), cases=[])
    with tempfile.TemporaryDirectory(prefix='p103x-launch-') as directory:
        tmp = Path(directory)
        baseline = tmp/'baseline.json'
        baseline.write_text(json.dumps(limits()))
        for old, lane, index in ([] if args.chain_only else [(True, 'A', 0), *[(False, l, i) for l in ('A', 'B') for i in range(3)]]):
            label = 'old-reader' if old else f'composite-{lane}-{index}'
            receipt = tmp/(label+'.json')
            cmd = [sys.executable, '-B', str(SELF), '--probe', 'composite', '--lane', lane,
                   '--index', str(index), '--baseline', str(baseline), '--scratch', str(tmp/label),
                   '--receipt', str(receipt), *(['--old-reader'] if old else [])]
            cp = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300,
                                env={'PATH': '/usr/bin:/bin', 'OMP_NUM_THREADS': '2', 'LD_LIBRARY_PATH': '/usr/lib'})
            row = json.loads(receipt.read_text())
            row['case'] = label
            row['expected_failure'] = old
            report['cases'].append(row)
            (O/'evidence/103x-launch-limits.json').write_text(json.dumps(report, indent=2)+'\n')
            assert (cp.returncode != 0 and 'RLIMIT_AS is not unlimited' in row.get('error', '')) if old else cp.returncode == 0, row.get('error')
            print(label, 'EXPECTED REFUSAL' if old else 'PASS', flush=True)
        # Execute the shell portion of ready.json's command, without systemd,
        # priority changes or device-core affinity. Shell command bytes stay exact.
        ready = json.loads((O/'ready.json').read_text())
        parts = shlex.split(ready['chain_command'].removesuffix(' </dev/null'))
        shell = parts[parts.index('/usr/bin/bash'):]
        shim = tmp/'shim'; shim.mkdir()
        shim_args = shlex.join([sys.executable, '-B', str(SELF), '--shell-python',
                               '--baseline', str(baseline), '--scratch', str(tmp/'readiness'), '--'])
        (shim/'python3').write_text('#!/bin/bash\nexec '+shim_args+' "$@"\n')
        (shim/'python3').chmod(0o755)
        chain_receipt = tmp/'chain.json'
        chain_cmd = shlex.join([sys.executable, '-B', str(SELF), '--probe', 'chain',
                               '--baseline', str(baseline), '--scratch', str(tmp/'chain-probe'),
                               '--receipt', str(chain_receipt), '--'])
        # Shell-only fixtures: no trap writes to live orchestration logs, and no
        # secret-bearing deployment environment is sourced by a CPU rehearsal.
        init = tmp/'bash-env'
        init.write_text('trap() { :; }\nsource() { P49_LDP=/usr/lib; }\n'
                        'env() {\n  while [[ "$1" != "python3" ]]; do shift; done\n'
                        '  shift\n  [[ "$1" == "-B" ]] || return 2\n  shift\n'
                        '  [[ "$1" == '+shlex.quote(str(P/'chain103.py'))+' || "$1" == "experiments/own-xpu-runtime/stage2/packet103-record-bundle/chain103.py" ]] || return 2\n'
                        '  shift\n  command env -i PATH=/usr/bin:/bin OMP_NUM_THREADS=2 LD_LIBRARY_PATH=/usr/lib '+chain_cmd+' "$@"\n}\n')
        env = dict(os.environ, PATH=str(shim)+':'+os.environ['PATH'], BASH_ENV=str(init))
        cp = subprocess.run(shell, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=300)
        assert cp.returncode == 0, cp.stderr[-4000:]
        row = json.loads(chain_receipt.read_text()); row['case'] = 'ready-json-shell-chain'
        row['shell_argv'] = shell
        report['cases'].append(row)
        assert row['passed']
        print('ready-json-shell-chain PASS', flush=True)
    report['passed'] = True
    report['complete_gate'] = not args.chain_only
    report['resource_audit'] = resource_audit(report['cases'])
    report['sources'] = {str(path.relative_to(ROOT)): digest(path) for path in O.glob('*.py')}
    (O/('evidence/103x-chain-limits.json' if args.chain_only else 'evidence/103x-launch-limits.json')).write_text(json.dumps(report, indent=2)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
