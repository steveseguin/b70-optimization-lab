#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Import sealed startup and every bundled helper in read-only CPU children.

Never calls prepare_start, launch, a health-receipt reader or a launcher CLI.
The exact startup phase exposes only launch/. The optional all-helpers phase
then imports every COMPONENTS and MODULES copy with sealed paths only, while
all device/server imports, writes, sockets, subprocesses and locks stay blocked.
"""
import argparse
import ast
import fcntl
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path('/home/steve/llm-optimizations')


def production_environment(mode='split36'):
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
        LTX_TEXT_RESIDENCY=mode, LTX_GC_INTERVAL_SECONDS='60',
        LTX_STORAGE_SCAN_MODE='background', LTX_SNAPSHOT_DIGEST_CACHE='1',
        LTX_MAINTENANCE_MODE='idle', LTX_RUN_WRITE_ALLOWANCE_GIB='16', LTX_F32_SCAN='bulk',
        LTX_TEXT_PREFETCH='scheduled' if mode == 'split36' else 'off')
    if mode == 'legacy':
        env.update(LTX_CONE_GRAPH_MEMORY='off', LTX_DECODER_GRAPH='0', LTX_DISPLAY_SCHEDULE='sampler-a')
    return env


def helper_inventory(packet):
    """Use the sealed builder's complete map, never the author tree or a shortlist."""
    source = Path(packet) / 'resolution/components/runtime_packet.py'
    tree = ast.parse(source.read_text(), filename=str(source))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id in ('COMPONENTS', 'MODULES')
                           for target in node.targets)]
    namespace = {'__builtins__': {}}
    exec(compile(ast.Module(body=assignments, type_ignores=[]), str(source), 'exec'), namespace)
    components, modules = namespace['COMPONENTS'], namespace['MODULES']
    if len(set(components)) != len(components) or len(set(modules.values())) != len(modules):
        raise RuntimeError('Sealed helper inventory contains duplicate paths')
    if not set(modules).issubset(components):
        raise RuntimeError('Sealed module map is not contained in component inventory')
    return ([('resolution/components/' + name) for name in components]
            + [('source/scripts/' + name) for name in modules.values()])


def probe(packet, mode='split36', block_helper=False, block_oracle=False,
          all_helpers=False, block_bundled_helper=None):
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
    origins = set()
    original_spec = importlib.util.spec_from_file_location

    def record_spec(name, location, *args, **kwargs):
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
    startup_sys_path = list(sys.path)
    helper_imports = []
    if all_helpers:
        inventory = helper_inventory(packet)
        for relative in inventory:
            location = packet / relative
            if relative == block_bundled_helper:
                raise ModuleNotFoundError('Missing bundled helper (fault injection): ' + relative)
            # Import each bundled copy, even if a dependency imported another copy
            # earlier. Source scripts include the inherited native_adapter helper.
            sys.path[:] = [str(location.parent), str(packet / 'source/scripts'),
                           str(packet / 'launch'), *baseline]
            name = location.stem
            spec = importlib.util.spec_from_file_location(name, location)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            if Path(module.__file__).resolve() != location:
                raise RuntimeError('Helper imported from the wrong sealed path: ' + relative)
            helper_imports.append(relative)
        if helper_imports != inventory:
            raise RuntimeError('Sealed helper import coverage is incomplete')
        sys.path[:] = startup_sys_path
    return dict(passed=True, packet=str(packet), mode=mode, cwd=str(Path.cwd()),
        all_helpers=all_helpers, helper_import_count=len(helper_imports),
        component_import_count=sum(p.startswith('resolution/components/') for p in helper_imports),
        runtime_helper_import_count=sum(p.startswith('source/scripts/') for p in helper_imports),
        helper_imports=helper_imports,
        sys_path=list(sys.path), module_origins=sorted(origins), oracle_prompts=len(oracle['prompts']),
        oracle_window_rows=len(oracle['window_probe']['rows']),
        oracle_sha256=helper.ORACLE_SHA256, dont_write_bytecode=sys.flags.dont_write_bytecode,
        prepare_start_called=False, launch_called=False, health_receipt_read=False)


def validate_packet(packet):
    """Builder gate for a newly assembled packet, before its manifest is written.

    Both startup modes and the complete helper probe use separate -B children. This wrapper must run outside probe's
    read-only guard; the children themselves cannot spawn any process.
    """
    rows = {}
    for key, mode, options in (('split36', 'split36', []), ('legacy', 'legacy', []),
                                ('all_helpers', 'split36', ['--all-helpers'])):
        env = dict(os.environ, OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
            '--packet', str(packet), '--mode', mode, *options], cwd=REPO, env=env,
            text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError('Sealed startup import gate failed (%s): %s %s' %
                               (key, result.stdout.strip(), result.stderr.strip()))
        rows[key] = json.loads(result.stdout)
        if rows[key].get('passed') is not True:
            raise RuntimeError('Sealed startup import gate did not pass: ' + key)
    return dict(passed=True, checks=len(rows), modes=rows,
                helper_import_count=rows['all_helpers']['helper_import_count'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', required=True, type=Path)
    parser.add_argument('--mode', choices=('split36', 'legacy'), default='split36')
    parser.add_argument('--block-helper', action='store_true')
    parser.add_argument('--block-oracle', action='store_true')
    parser.add_argument('--all-helpers', action='store_true')
    parser.add_argument('--block-bundled-helper')
    args = parser.parse_args()
    try:
        result = probe(args.packet, args.mode, args.block_helper, args.block_oracle,
                       args.all_helpers, args.block_bundled_helper)
    except Exception as exc:
        print(json.dumps(dict(passed=False, error_type=type(exc).__name__, error=str(exc)), sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
