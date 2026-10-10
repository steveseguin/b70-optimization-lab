#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Import sealed startup and every bundled helper in a fresh read-only CPU process.

Never calls prepare_start, launch, a health-receipt reader or a launcher CLI.
The launch directory is Python's script directory at this phase; source/scripts
is absent in the startup phase, then added for the inert runtime import census.
No helper functions doing runtime work are invoked. No native module stubs are used.
"""
import argparse
import fcntl
import importlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path('/home/steve/llm-optimizations')


def production_environment(mode='off'):
    env = dict(LTX_OUTPUT_SIZE='256x256', LTX_BUSY_WINDOWS='0',
        LTX_SAMPLER_WORKERS='1', LTX_SAMPLER_BATCH='1', LTX_SAMPLER_SHARED_POOL='1',
        LTX_DECODE_REPLICA_DEVICE='xpu:2', LTX_DECODE_REPLICAS='1',
        NEOReadDebugKeys='1', EnableDeferBacking='0', LTX_STREAM_FRAMES='145',
        LTX_SAMPLER_PLACEMENT='two-way20-28', LTX_ANCHOR='frame',
        LTX_DECODER_GRAPH='1', LTX_ANCHOR_DECODE='cone', LTX_BENCODE_OVERLAP='1',
        LTX_PREP_AHEAD='1', LTX_STREAM_TEXT_REUSE='1', LTX_SNAPSHOT_MODE='fingerprint',
        LTX_SNAPSHOT_SCHEDULE='full', LTX_ANCHOR_READ_AHEAD='0',
        LTX_AUX_RESIDENCY='legacy', LTX_AUDIO_RESIDENCY='legacy',
        LTX_DISPLAY_DEVICE='xpu:3', LTX_DISPLAY_SCHEDULE='eager-display',
        LTX_DISPLAY_WORKER='serial', LTX_DISPLAY_ALLOCATOR_RELEASE='off',
        LTX_CONE_GRAPH_MEMORY='text-shift', LTX_CONE_CAPTURE_RESERVE='parent',
        LTX_TEXT_RESIDENCY=('legacy' if mode == 'legacy' else 'split36'), LTX_GC_INTERVAL_SECONDS='60',
        LTX_STORAGE_SCAN_MODE='background', LTX_SNAPSHOT_DIGEST_CACHE='1',
        LTX_MAINTENANCE_MODE='idle', LTX_RUN_WRITE_ALLOWANCE_GIB='16')
    env['LTX_CHUNK_ARM'] = 'split36-169' if mode == 'split36-169' else 'off'
    if mode == 'split36-169':
        env.update(LTX_STREAM_FRAMES='169', LTX_DECODER_GRAPH='0', LTX_CONE_GRAPH_MEMORY='off')
    if mode == 'legacy':
        env.update(LTX_CONE_GRAPH_MEMORY='off', LTX_DECODER_GRAPH='0', LTX_DISPLAY_SCHEDULE='sampler-a')
    return env


def probe(packet, mode='off', block_helper=False, block_oracle=False, block_path=None):
    packet = Path(packet).resolve()
    if not sys.flags.dont_write_bytecode:
        raise RuntimeError('The sealed-import child requires interpreter -B')
    if os.environ.get('OMP_NUM_THREADS') != '2' or os.getpriority(os.PRIO_PROCESS, 0) != 19:
        raise RuntimeError('The sealed-import child requires nice 19 and OMP_NUM_THREADS=2')
    for name, module in tuple(sys.modules.items()):
        location = getattr(module, '__file__', None)
        if name != '__main__' and location and REPO in Path(location).resolve().parents:
            del sys.modules[name]
    if 'encoder_runtime_common' in sys.modules or 'text_residency133' in sys.modules:
        raise RuntimeError('Sealed import requires fresh module state')
    os.chdir(REPO)  # Exact cwd used by the shell launcher before its Python exec.
    for key in list(os.environ):
        if key.startswith('LTX_'):
            del os.environ[key]
    os.environ.update(production_environment(mode))
    # The parent unittest adapter inserts its author tree. Remove all such paths,
    # including the empty-string cwd fallback, before touching the sealed chain.
    baseline = []
    for item in sys.path:
        if not item:
            continue
        path = Path(item).resolve()
        if path == REPO or REPO in path.parents or packet == path or packet in path.parents:
            continue
        if any(path == prefix or prefix in path.parents for prefix in
               (Path(sys.base_prefix).resolve() / 'lib', Path(sys.prefix).resolve() / 'lib')):
            baseline.append(item)
    sys.path[:] = [str(packet / 'launch'), *baseline]
    launch_sys_path = list(sys.path)
    origins = set()
    completed_imports = set()
    blocked = packet / block_path if block_path else None
    if blocked is not None and (blocked.resolve() != blocked or packet not in blocked.parents):
        raise ValueError('Fault injection must name a regular packet-relative path')
    original_spec = importlib.util.spec_from_file_location

    def record_spec(name, location, *args, **kwargs):
        if blocked is not None and Path(location).resolve() == blocked:
            raise ModuleNotFoundError('Bundled helper missing (fault injection): ' + str(blocked))
        origins.add(str(Path(location).resolve()))
        return original_spec(name, location, *args, **kwargs)

    importlib.util.spec_from_file_location = record_spec

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] in ('torch', 'comfy', 'server'):
                raise RuntimeError('CPU import refuses device/server module: ' + fullname)
            if block_helper and fullname == 'text_residency133':
                raise ModuleNotFoundError("No module named 'text_residency133' (fault injection)", name=fullname)
            return None

    sys.meta_path.insert(0, Guard())

    def audit(event, args):
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.path.realpath(os.fsdecode(args[0])))
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            mode_arg = args[1] if len(args) > 1 else None
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND) or (
                    isinstance(mode_arg, str) and any(c in mode_arg for c in 'wax+')):
                raise RuntimeError('CPU sealed import refuses all file writes: ' + str(path))
            if str(path).startswith(('/dev/dri', '/run/lock/')) or 'health-receipt' in path.name:
                raise RuntimeError('CPU sealed import refuses device/lock/health access')
            if path.suffix in ('.py', '.pyc') and (path == REPO or REPO in path.parents):
                raise RuntimeError('Sealed import attempted author-tree fallback: ' + str(path))
            if blocked is not None and path == blocked:
                raise ModuleNotFoundError('Bundled helper missing (fault injection): ' + str(blocked))
            if block_oracle and path.name == 'text-oracle133.json':
                raise FileNotFoundError('Oracle missing (fault injection): ' + str(path))
        if event.startswith(('socket.', 'subprocess.', 'fcntl.')) or event in (
                'os.system', 'os.fork', 'os.forkpty', 'os.posix_spawn', 'os.exec',
                'os.kill', 'os.killpg', 'os.mkdir', 'os.remove', 'os.rmdir', 'os.rename',
                'os.symlink', 'os.link', 'os.chmod', 'os.truncate'):
            raise RuntimeError('CPU sealed import refuses operation: ' + event)

    sys.addaudithook(audit)

    def prohibited(*args, **kwargs):
        raise RuntimeError('CPU sealed import refuses lock/health/startup work')

    fcntl.flock = prohibited
    fcntl.lockf = prohibited
    path = packet / 'launch/serve-encoder.py'
    spec = importlib.util.spec_from_file_location('sealed_startup_cpu_probe', path)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    launcher.prepare_start = launcher.launch = launcher.load_health_receipt = prohibited
    common = launcher.common
    if Path(common.__file__).resolve() != packet / 'launch/encoder_runtime_common.py':
        raise RuntimeError('Launcher imported the wrong common module')
    # This is the exact pure environment-check call before prepare_start proceeds
    # to manifest/runtime checks. It executes every lazy import for this mode.
    common.check_control_environment()
    helper = __import__('text_residency133')
    origins.add(str(Path(helper.__file__).resolve()))
    oracle = helper.load_oracle()
    for module in tuple(sys.modules.values()):
        location = getattr(module, '__file__', None)
        if location and str(Path(location).resolve()).startswith(str(packet) + '/'):
            origins.add(str(Path(location).resolve()))
    if Path(helper.__file__).resolve() != packet / 'launch/text_residency133.py':
        raise RuntimeError('Text helper did not resolve from the sealed launch directory')
    # Every runtime helper is imported by its real bare name with the sealed
    # source/scripts path used after startup. Evict launch-stage helper aliases
    # so an earlier cached copy cannot conceal a missing runtime copy. No torch,
    # Comfy, server, helper mocks or author-tree paths are permitted in any stage.
    runtime = dict(common.MODULES)
    components = tuple(common.COMPONENTS)
    if set(runtime) - set(components):
        raise RuntimeError('Runtime inventory is not a subset of components')
    sys.path[:] = [str(packet / 'source/scripts'), str(packet / 'launch'), *baseline]
    runtime_names = {Path(name).stem for name in runtime.values()}
    for name in runtime_names:
        sys.modules.pop(name, None)
    runtime_origins = {}
    for author_name, filename in runtime.items():
        imported = importlib.import_module(Path(filename).stem)
        actual = Path(imported.__file__).resolve()
        expected = packet / 'source/scripts' / filename
        if actual != expected:
            raise RuntimeError('Runtime helper resolved outside sealed scripts: ' + author_name)
        completed_imports.add(str(actual))
        runtime_origins[author_name] = str(actual)
    # Also execute every component copy, including build/qualification helpers.
    # Use distinct module names so the runtime imports cannot mask these copies.
    # Dependencies still resolve via source/scripts as above. Builder code only
    # reads its immutable parent on import; its CLI and build are never called.
    component_origins = {}
    for index, filename in enumerate(components):
        expected = packet / 'resolution/components' / filename
        spec = importlib.util.spec_from_file_location('sealed_component_%d' % index, expected)
        imported = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(imported)
        actual = Path(imported.__file__).resolve()
        if actual != expected:
            raise RuntimeError('Component resolved outside sealed inventory: ' + filename)
        completed_imports.add(str(actual))
        component_origins[filename] = str(actual)
        # Some inert CLI helpers put their own directory first. Restore runtime
        # paths before the next import rather than admitting component fallback.
        sys.path[:] = [str(packet / 'source/scripts'), str(packet / 'launch'), *baseline]
    if len(runtime_origins) != len(runtime) or len(component_origins) != len(components):
        raise RuntimeError('Incomplete bundled-helper import census')
    return dict(passed=True, packet=str(packet), mode=mode, cwd=str(Path.cwd()),
        control_environment={key: os.environ[key] for key in production_environment(mode)},
        sys_path=launch_sys_path, runtime_sys_path=list(sys.path),
        runtime_helper_origins=runtime_origins, component_helper_origins=component_origins,
        runtime_helpers_imported=len(runtime_origins), components_imported=len(component_origins),
        completed_helper_imports=sorted(completed_imports), module_origins=sorted(origins), oracle_prompts=len(oracle['prompts']),
        oracle_window_rows=len(oracle['window_probe']['rows']),
        oracle_sha256=helper.ORACLE_SHA256, dont_write_bytecode=sys.flags.dont_write_bytecode,
        prepare_start_called=False, launch_called=False, health_receipt_read=False)


def validate_packet(packet):
    """Builder gate for a newly assembled packet, before its manifest is written.

    Both probes use separate -B children. This wrapper must run outside probe's
    read-only guard; the children themselves cannot spawn any process.
    """
    rows = {}
    for mode in ('off', 'split36-169'):
        env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
            '--packet', str(packet), '--mode', mode], cwd=REPO, env=env,
            text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError('Sealed startup import gate failed (%s): %s %s' %
                               (mode, result.stdout.strip(), result.stderr.strip()))
        rows[mode] = json.loads(result.stdout)
        if rows[mode].get('passed') is not True:
            raise RuntimeError('Sealed startup import gate did not pass: ' + mode)
    return dict(passed=True, checks=len(rows), modes=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--mode', choices=('off', 'split36-169', 'split36', 'legacy'), default='off')
    parser.add_argument('--block-helper', action='store_true')
    parser.add_argument('--block-oracle', action='store_true')
    parser.add_argument('--block-path', help='Fault injection: deny loading one packet-relative helper')
    args = parser.parse_args()
    try:
        result = probe(args.packet, args.mode, args.block_helper, args.block_oracle, args.block_path)
    except Exception as exc:
        print(json.dumps(dict(passed=False, error_type=type(exc).__name__, error=str(exc)), sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
