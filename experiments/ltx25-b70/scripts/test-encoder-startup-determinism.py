#!/usr/bin/env python3
"""Regression for actual Comfy import ordering, with CPU-only startup tails.

Fresh subprocesses execute the AST tail of each real launcher, after ownership /
preflight and before runpy.main. A marker replaces main and imports the actual
pinned model_management module. No server, watcher, device probe or GPU work runs.
"""
import argparse
import ast
from contextlib import ExitStack
import hashlib
import functools
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/steve/src/ComfyUI-ltx25-baseline')
HISTORICAL = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-02/launch/serve-encoder.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def child(launcher_path, report_path):
    # Parse and import only definitions; launch() itself is never called.
    source = launcher_path.read_text()
    parsed = ast.parse(source, filename=str(launcher_path))
    launch = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == 'launch')
    starts = [i for i, n in enumerate(launch.body) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'argv' for t in n.targets)
              and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
              and n.value.func.id == 'server_args']
    if len(starts) != 1:
        raise RuntimeError('Launcher post-preflight boundary changed')
    tail = ast.fix_missing_locations(ast.Module(body=launch.body[starts[0]:], type_ignores=[]))
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr in ('start', 'launch', 'device_count', 'synchronize') for n in ast.walk(tail)):
        raise RuntimeError('Unexpected device/process work entered tested launcher tail')
    sys.path.insert(0, str(launcher_path.parent))
    spec = importlib.util.spec_from_file_location('inactive_launcher_under_test', launcher_path)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    import torch
    events = []
    original_set = torch.use_deterministic_algorithms
    @functools.wraps(original_set)
    def set_determinism(mode, *, warn_only=False):
        events.append({'enabled': mode, 'warn_only': warn_only})
        return original_set(mode, warn_only=warn_only)
    def flags():
        return {'enabled': torch.are_deterministic_algorithms_enabled(),
                'warn_only': torch.is_deterministic_algorithms_warn_only_enabled()}
    result = {'launcher': str(launcher_path), 'launcher_sha256': sha(launcher_path),
              'model_management_sha256': sha(SOURCE/'comfy/model_management.py'),
              'watcher_started': False, 'server_started': False,
              'scope': 'Actual pinned model_management import and actual launcher post-preflight tail; CPU only'}
    with tempfile.TemporaryDirectory(prefix='ltx-strict-import-cpu-') as temp:
        packet = Path(temp)/'packet'
        packet.mkdir()
        # Read-only alias to the existing source; never a checkout or worktree.
        (packet/'source').symlink_to(SOURCE, target_is_directory=True)
        run = Path(temp)/'encoder-server-cpu-fixture'
        run.mkdir()
        for name in ('user', 'input', 'temp'):
            (run/name).mkdir()
        def cpu_args(packet_arg, run_arg):
            return launcher.server_args(packet_arg, run_arg) + ['--cpu']
        def main_marker(path, *, run_name):
            if Path(path).resolve() != SOURCE/'main.py' or run_name != '__main__':
                raise RuntimeError('Unexpected main entry')
            result['before_main_marker'] = flags()
            # This is the relevant real import in main's dependency chain.
            mm = importlib.import_module('comfy.model_management')
            result['after_main_model_management_import'] = flags()
            result['actual_module_sha256'] = sha(mm.__file__)
            result['actual_device'] = str(mm.get_torch_device())
            identity_path = run/'server-identity.json'
            result['server_identity_sha256'] = sha(identity_path)
            result['identity_env_matches_file'] = os.environ['LTX_ENCODER_IDENTITY_SHA256'] == sha(identity_path)
            after_import = run/'determinism-after-import.json'
            result['after_import_receipt'] = json.loads(after_import.read_text()) if after_import.exists() else None
            result['main_marker_reached'] = True
            return {}
        namespace = dict(vars(launcher))
        namespace.update(packet=packet, run=run, digest='0'*64,
                         manifest={'runtime': {'torch': torch.__version__}, 'extension_sha256s': {}},
                         since='CPU fixture; no watcher', devices=[], torch=torch,
                         server_args=cpu_args, runpy=types.SimpleNamespace(run_path=main_marker))
        with ExitStack() as stack:
            # Upstream probes counts even with --cpu; stub discovery explicitly.
            probes = {'xpu_device_count': 0, 'xpu_is_available': 0, 'xpu_init': 0, 'cuda_init': 0}
            def stub(original, key, result=None, reject=False):
                @functools.wraps(original)
                def call(*args, **kwargs):
                    probes[key] = probes.get(key, 0) + 1
                    if reject:
                        raise AssertionError('Device initialization prohibited')
                    return result
                return call
            for obj, name, key, result_value, reject in (
                (torch.xpu, 'device_count', 'xpu_device_count', 0, False),
                (torch.xpu, 'is_available', 'xpu_is_available', False, False),
                (torch.xpu, '_lazy_init', 'xpu_init', None, True),
                (torch.cuda, '_lazy_init', 'cuda_init', None, True),
                (torch.cuda, 'is_available', 'cuda_is_available', False, False),
                (torch.backends.mps, 'is_available', 'mps_is_available', False, False)):
                stack.enter_context(patch.object(obj, name, new=stub(getattr(obj, name), key, result_value, reject)))
            stack.enter_context(patch.object(torch, 'use_deterministic_algorithms', new=set_determinism))
            set_determinism(True, warn_only=False)  # State established by the real preflight.
            result['before_tail'] = flags()
            exec(compile(tail, str(launcher_path)+':post-preflight-tail', 'exec'), namespace)
            if probes['xpu_init'] or probes['cuda_init']:
                raise RuntimeError('Device initialization was attempted')
            result['mocked_discovery_calls'] = probes
        result['determinism_events'] = events
    with report_path.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher', type=Path, default=LANE/'scripts/serve-encoder.py')
    parser.add_argument('--historical-launcher', type=Path, default=HISTORICAL)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    if args.child:
        child(args.launcher, args.output)
        return
    if args.output and (args.output.exists() or args.output.is_symlink()):
        raise FileExistsError(args.output)
    with tempfile.TemporaryDirectory(prefix='ltx-strict-import-driver-') as temp:
        rows = []
        for index, path in enumerate((args.historical_launcher, args.launcher)):
            output = Path(temp)/f'case-{index}.json'
            subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--child', '--launcher', str(path),
                            '--output', str(output)], check=True, timeout=45)
            rows.append(json.loads(output.read_text()))
    old, new = rows
    strict = {'enabled': True, 'warn_only': False}
    warning = {'enabled': True, 'warn_only': True}
    checks = {
        'historical_preflight_was_strict': old['before_tail'] == strict,
        'historical_main_import_reproduces_warn_only_reset': old['after_main_model_management_import'] == warning,
        'historical_has_no_after_import_receipt': old['after_import_receipt'] is None,
        'fixed_before_main_is_strict': new['before_main_marker'] == strict,
        'fixed_main_import_keeps_strict': new['after_main_model_management_import'] == strict,
        'actual_module_matches_pinned_source': all(r['actual_module_sha256'] == r['model_management_sha256'] for r in rows),
        'both_runs_use_cpu_only': all(r['actual_device'] == 'cpu' for r in rows),
        'identity_env_bound_to_written_file': all(r['identity_env_matches_file'] for r in rows),
        'strict_receipt_bound_to_server_identity': new['after_import_receipt']['server_identity_sha256'] == new['server_identity_sha256'],
        'strict_receipt_stage_and_flags_correct': all(new['after_import_receipt'][k] == v for k, v in {
            'enabled': True, 'warn_only': False, 'stage': 'after_model_management_import_before_main'}.items()),
        'fixed_import_warn_mode_then_restores_strict': new['determinism_events'] == [strict, warning, strict],
    }
    report = {'passed': all(checks.values()), 'checks': checks, 'rows': rows,
              'driver_sha256': sha(__file__),
              'scope': 'Regression of real import-order failure, not a server/watcher/GPU/clip qualification'}
    if args.output:
        with args.output.open('x') as handle:
            json.dump(report, handle, indent=2)
            handle.write('\n')
    print(json.dumps(report, indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
