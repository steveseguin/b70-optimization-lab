#!/usr/bin/env python3
"""CPU-only packet-99 transition checker and generated launcher's common module.

Historical checks run against historical packet98, never against a forged new
parent. Final source bytes are checked against source99 plus exact port edits.
Dependency-pending packets can be inspected but cannot pass launch admission.
"""
import argparse
import ast
import copy
import difflib
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import re
import resource
import stat
import sys
import textwrap

sys.dont_write_bytecode = True
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
HISTORICAL = ROOT / 'prepared-encoder-size-98'
SOURCE_INPUT = ROOT / 'prepared-encoder-upstream-99-source'
PACKET = ROOT / 'prepared-encoder-upstream-99'
PIN = 'b00c6e95279053474955540ba4f551646722b9aa'
OLD_MANIFEST = '918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f'
MODEL_VERIFICATION_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
MIN_FREE = 50 * 1024**3
PLANNED_WRITE = 4 * 1024**3
DEPENDENCY_RECEIPT = Path('/home/steve/ltx25-upstream99-dependencies/receipt.json')
DEPENDENCY_ROOT = DEPENDENCY_RECEIPT.parent / 'site-packages'
REQUIREMENTS_SHA = '65ee57b99a4b6950c25a26dbbfaff0d00a7e2b56fa6e4a5be74c289b147567ee'
PACKAGE_PINS = {
    'comfy-kitchen': '0.2.37', 'comfy-aimdo': '0.5.5',
    'comfyui-frontend-package': '1.55.14', 'comfyui-embedded-docs': '0.5.13',
    'comfyui-workflow-templates': '0.11.77', 'comfyui-workflow-templates-core': '0.3.368',
    'comfyui-workflow-templates-json': '0.1.103',
    'comfyui-workflow-templates-media-assets-01': '0.1.48',
    'comfyui-workflow-templates-media-assets-02': '0.1.10',
    'cryptography': '50.0.2', 'cffi': '2.1.1', 'pycparser': '3.0',
}
BASELINE_SITE = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages')
INHERITED_PACKAGE_PINS = {'comfyui-workflow-templates-media-api': '0.3.84',
                          'comfyui-workflow-templates-media-video': '0.3.101',
                          'comfyui-workflow-templates-media-image': '0.3.160',
                          'comfyui-workflow-templates-media-other': '0.3.229'}
STATUS = b'Packet99 source/runtime candidate; no GPU, parity or speed qualification.\n'
PORT_PINS = {
    'scripts/na_axis_decode_node.py': {'NODES_SHA': 'nodes.py', 'SD_SHA': 'comfy/sd.py'},
    'custom_nodes/ltx_na_axis_decode_lab/__init__.py': {'NODES_SHA': 'nodes.py', 'SD_SHA': 'comfy/sd.py'},
    'scripts/ltx_graph_text_encoder.py': {'GEMMA_SOURCE_SHA256': 'comfy/text_encoders/gemma4.py'},
}
ATTENTION_FILES = ('scripts/host_embedding_resident_node.py',
                   'custom_nodes/ltx_host_embedding_lab/__init__.py')
ATTENTION_ANCHOR = "                _pending.append(model)\n"
ATTENTION_GUARD = '''                # Packet99: preserve native BF16 attention; reject checkpoint-selected backends.
                from comfy.ldm.modules.attention import ComfyAttention
                attention_modules = [m for m in model.model.diffusion_model.modules()
                                     if isinstance(m, ComfyAttention)]
                require(attention_modules and all(m.config is None and m.function is None
                        for m in attention_modules), 'Packet99 requires unconfigured native attention')
'''


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(regular(Path(path))).hexdigest()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path, limit=256 * 1024**2):
    require(path.is_absolute() and '..' not in path.parts, 'Absolute normalized path required')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlink refused: ' + str(path))
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'Nonregular/oversized input')
    raw = path.read_bytes(); after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Input changed during read')
    return raw


def safe_path(root, name):
    require(isinstance(name, str) and name and str(Path(name)) == name and
            not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe relative path')
    return root / name


def load_json(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'Duplicate JSON key'); out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def historical_manifest():
    raw = regular(HISTORICAL / 'manifest.json')
    require(digest(raw) == OLD_MANIFEST, 'Historical packet manifest changed')
    return load_json(raw)


def legacy():
    manifest = historical_manifest()
    path = HISTORICAL / 'launch/encoder_runtime_common.py'
    require(sha(path) == manifest['files']['launch/encoder_runtime_common.py'], 'Historical checker changed')
    return module(path, 'packet98_history_checks')


# No runtime/model imports; expose the unchanged launcher-facing helper contract.
_LEGACY = legacy()
NODES = _LEGACY.NODES
EXTENSIONS = _LEGACY.EXTENSIONS
verify_runtime = _LEGACY.verify_runtime
verify_model_receipt = _LEGACY.verify_model_receipt
process_ticks = _LEGACY.process_ticks


def replace_once(text, old, new):
    require(text.count(old) == 1, 'Port anchor missing/ambiguous: ' + old[:100])
    return text.replace(old, new, 1)


def port_source(path, raw, source_rows):
    """Only five named literal pins and the two identical backend guards."""
    text = raw.decode('utf-8')
    for name, target in PORT_PINS.get(path, {}).items():
        nodes = [n for n in ast.parse(text).body if isinstance(n, ast.Assign)
                 and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                 and n.targets[0].id == name]
        require(len(nodes) == 1 and isinstance(nodes[0].value, ast.Constant) and
                re.fullmatch('[0-9a-f]{64}', nodes[0].value.value), 'Ambiguous startup pin')
        old = ast.get_source_segment(text, nodes[0])
        text = replace_once(text, old, name + ' = ' + repr(source_rows[target]['sha256']))
    if path in ATTENTION_FILES:
        text = replace_once(text, ATTENTION_ANCHOR, ATTENTION_ANCHOR + ATTENTION_GUARD)
    ast.parse(text, filename=path)
    return text.encode()


def progress_module(raw):
    """Keep the CPU-tested install function; exclude the old packet98 wrapper."""
    tree = ast.parse(raw)
    names = {'HERE', 'SOURCE', 'SOURCE_SHA', 'CANDIDATE_SHA', 'ORIGINAL_SHA'}
    functions = {'require', 'digest', 'regular', 'bound', 'code_identity', 'install'}
    selected = []
    for node in tree.body:
        keep = isinstance(node, (ast.Import, ast.ImportFrom))
        keep |= isinstance(node, ast.FunctionDef) and node.name in functions
        keep |= (isinstance(node, ast.Assign) and len(node.targets) == 1 and
                 isinstance(node.targets[0], ast.Name) and node.targets[0].id in names)
        if keep:
            selected.append(ast.get_source_segment(raw, node))
    result = ('"""Packet99 process-local progress lock overlay; no launch delegation."""\n' +
              '\n\n'.join(selected) + '\n').encode()
    require({n.name for n in ast.parse(result).body if isinstance(n, ast.FunctionDef)} == functions,
            'Progress installer extraction differs')
    return result


def launcher_source(raw):
    text = raw.decode()
    start = text.index("    match = re.fullmatch(r'encoder-server-size-98-")
    end = text.index('    run = common.ROOT / run_name\n', start)
    text = text[:start] + '''    common.require(re.fullmatch(r'encoder-server-upstream-99-two-way-w2-b1-p1-dxpu2-s256x256(?:-r[2-5])?', run_name),
                   'Packet99 admits only the frozen batch-one control')
    common.check_control_environment()
    common.check_file_limits()
''' + text[end:]
    text = replace_once(text, "    common.verify_runtime(manifest['runtime'])\n",
                        "    common.activate_dependencies(packet, manifest)\n    common.verify_runtime(manifest['runtime'])\n")
    text = replace_once(text, "    common.require(shutil.disk_usage(common.ROOT).free >= 5 * 1024**3, 'Less than 5 GiB disk available')\n",
                        '    common.admit_storage(packet, run)\n')
    text = replace_once(text, '    manifest, run = prepare_start(packet, digest, run_name)\n',
                        "    common.require(health_receipt is not None, 'Fresh four-card health receipt required')\n    manifest, run = prepare_start(packet, digest, run_name)\n")
    text = replace_once(text, "    (run / 'input').mkdir()\n", "    (run / 'input').mkdir()\n" +
                        "    progress_overlay = common.install_progress(packet)\n    write_json(run / 'progress-lock.json', progress_overlay)\n")
    text = replace_once(text, "    identity = {'pid': os.getpid(),", "    identity = {'runtime99_transition': manifest['upstream99'],\n" +
                        "                'process_file_limits': common.check_file_limits(),\n" +
                        "                'progress_lock': progress_overlay, 'pid': os.getpid(),")
    ast.parse(text)
    return text.encode()


def check_control_environment():
    expected = {'LTX_OUTPUT_SIZE': '256x256', 'LTX_BUSY_WINDOWS': '0',
                'LTX_SAMPLER_PLACEMENT': 'two-way', 'LTX_SAMPLER_WORKERS': '2',
                'LTX_SAMPLER_BATCH': '1', 'LTX_SAMPLER_SHARED_POOL': '1',
                'LTX_DECODE_REPLICA_DEVICE': 'xpu:2', 'LTX_DECODE_REPLICAS': '1',
                'NEOReadDebugKeys': '1', 'EnableDeferBacking': '0'}
    require(all(os.environ.get(k) == v for k, v in expected.items()), 'Explicit control environment differs')


def check_file_limits():
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    require(soft >= 65536 and hard == 1048576, 'Application NOFILE requires soft>=65536, hard1048576')
    return {'soft': soft, 'hard': hard, 'changed_by_launcher': False}


def admit_storage(packet, run):
    helper = module(packet / 'launch/check-storage-headroom.py', 'runtime99_storage')
    result = helper.inspect_destination(run, MIN_FREE, PLANNED_WRITE)
    require(result['admitted'], '50 GiB reserve plus 4 GiB full-run allowance required')
    return result


def install_progress(packet):
    helper = module(packet / 'launch/progress_lock.py', 'runtime99_progress')
    return helper.install()


def verify_dependencies(raw, baseline):
    receipt = load_json(raw)
    require(receipt.get('schema') == 'ltx.upstream99.dependencies.v1' and receipt.get('status') == 'ready',
            'Completed dependency receipt required')
    require(receipt.get('overlay_root') == str(DEPENDENCY_ROOT) and
            receipt.get('requirements_sha256') == REQUIREMENTS_SHA and
            receipt.get('packages') == PACKAGE_PINS, 'Pinned application dependency identity differs')
    require(receipt.get('baseline_python') == baseline['python_executable'] and
            receipt.get('baseline_runtime_sha256') == baseline['files'], 'Torch/Python baseline identity differs')
    for path, expected in baseline['files'].items():
        require(sha(Path(path)) == expected, 'Installed baseline changed')
    require(DEPENDENCY_ROOT.is_dir() and not any(p.is_symlink() for p in (DEPENDENCY_ROOT, *DEPENDENCY_ROOT.parents)),
            'Unsafe dependency root')
    actual = set()
    for directory, dirs, names in os.walk(DEPENDENCY_ROOT, followlinks=False):
        for name in dirs + names:
            path = Path(directory) / name; mode = path.lstat().st_mode
            require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'Dependency symlink/special file refused')
            relative = str(path.relative_to(DEPENDENCY_ROOT)); first = Path(relative).parts[0]
            require(name not in ('__pycache__', 'sitecustomize.py', 'usercustomize.py') and
                    not name.endswith(('.pth', '.pyc')) and not first.startswith(('torch', 'triton', 'intel_')),
                    'Dependency must not alter interpreter hooks or protected runtime')
            if stat.S_ISREG(mode):
                actual.add(relative)
                require(stat.S_IMODE(mode) == 0o644, 'Dependency mode differs')
    require(actual == set(receipt['files']), 'Dependency inventory differs')
    for name, expected in receipt['files'].items():
        require(sha(safe_path(DEPENDENCY_ROOT, name)) == expected, 'Dependency file differs: ' + name)
    versions, distributions = {}, {}
    for dist in importlib.metadata.distributions(path=[str(DEPENDENCY_ROOT)]):
        name = re.sub(r'[-_.]+', '-', dist.metadata['Name']).lower()
        require(name not in versions, 'Duplicate dependency distribution')
        versions[name] = dist.version
        distributions[name] = dist
    require(versions == PACKAGE_PINS, 'Installed dependency distribution versions differ')
    expected_closure = {'pycparser', 'cffi', 'comfyui-workflow-templates-core',
                        'comfyui-workflow-templates-json', 'comfyui-workflow-templates-media-assets-01',
                        'comfyui-workflow-templates-media-assets-02'} | set(INHERITED_PACKAGE_PINS)
    seen = set()
    for row in receipt['dependency_closure']:
        path = Path(row['metadata_path'])
        require(path.parent in (DEPENDENCY_ROOT, BASELINE_SITE), 'Unexpected dependency metadata root')
        require(sha(path / 'METADATA') == row['metadata_sha256'], 'Inherited dependency metadata changed')
        dist = importlib.metadata.PathDistribution(path)
        name = re.sub(r'[-_.]+', '-', dist.metadata['Name']).lower()
        require(name in expected_closure and name not in seen, 'Unexpected/duplicate dependency closure row')
        seen.add(name)
        expected_version = {**PACKAGE_PINS, **INHERITED_PACKAGE_PINS}[name]
        require(dist.version == row['version'] == expected_version, 'Inherited dependency version changed')
        require(path.parent == (BASELINE_SITE if name in INHERITED_PACKAGE_PINS else DEPENDENCY_ROOT),
                'Dependency resolved from wrong location')
        parent = re.sub(r'[-_.]+', '-', row['parent']).lower()
        require(parent in distributions and row['requirement'] in distributions[parent].metadata.get_all('Requires-Dist', []),
                'Dependency edge not present in actual parent metadata')
        match = re.match(r'[A-Za-z0-9_.-]+', row['requirement'])
        require(match and re.sub(r'[-_.]+', '-', match.group()).lower() == name, 'Dependency edge names wrong child')
    require(seen == expected_closure, 'Dependency closure omitted an inherited requirement')
    return receipt


def require_clean_dependency_modules(modules):
    roots = {name.replace('-', '_') for name in PACKAGE_PINS} | {
        'torch', 'triton', 'comfy', '_cffi_backend'}
    # Namespace roots of unchanged media siblings are covered too: previously
    # loaded template modules cannot survive a change to their parent package.
    stale = [name for name in modules if name.split('.', 1)[0] in roots or
             name.split('.', 1)[0].startswith('comfyui_workflow_templates')]
    require(not stale, 'Dependency activation after application import refused: ' + ','.join(sorted(stale)))


def activate_dependencies(packet, manifest):
    contract = manifest['upstream99']['dependencies']
    require(contract.get('state') == 'matched',
            'Packet99 dependency overlay pending; newest source cannot launch on old application dependencies')
    raw = regular(packet / 'provenance/dependencies.json')
    require(digest(raw) == contract['receipt_sha256'] and raw == regular(DEPENDENCY_RECEIPT),
            'Dependency receipt changed')
    verify_dependencies(raw, manifest['runtime'])
    require_clean_dependency_modules(sys.modules)
    sys.path.insert(0, str(DEPENDENCY_ROOT))  # No addsitedir/.pth execution.
    _LEGACY.verify_na_source_closure(packet / 'source',
        original_na_path=DEPENDENCY_ROOT / 'comfy_kitchen/backends/eager/na.py')


def semantic_manifest(parent, files, builder_sha, transition):
    result = copy.deepcopy(parent)
    result.update(schema='ltx.upstream-runtime-packet.v1', source_commit=PIN,
                  status='prepared-inactive-not-deployed', preparer_sha256=builder_sha,
                  files=files, upstream99=transition)
    for name in ('host_embedding_resident_node.py', 'na_axis_decode_node.py', 'ltx_graph_text_encoder.py'):
        result['extension_sha256s'][name] = files['source/scripts/' + name]
    result['graph_capture']['na_decode_node_sha256'] = result['extension_sha256s']['na_axis_decode_node.py']
    result['graph_capture']['text_adapter_sha256'] = result['extension_sha256s']['ltx_graph_text_encoder.py']
    for name in result['startup_tools']:
        result['startup_tools'][name] = files['launch/' + name]
    return result


def verify_packet(packet, expected_manifest_sha256):
    packet = Path(packet)
    require(packet == PACKET, 'Unexpected runtime99 packet path')
    raw = regular(packet / 'manifest.json')
    require(re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256 or '') and
            digest(raw) == expected_manifest_sha256, 'Runtime99 manifest changed')
    manifest = load_json(raw); files = manifest['files']
    # This checks the real preserved historical packet, never a synthetic old identity.
    parent = _LEGACY.verify_packet(HISTORICAL, OLD_MANIFEST)
    for path, expected in files.items():
        require(sha(safe_path(packet, path)) == expected, 'Runtime99 file changed: ' + path)
    source_checker = module(packet / 'provenance/source99/check-upstream-source-99.py', 'runtime99_source_check')
    require(source_checker.inventory(packet) == set(files) | {'manifest.json', 'STATUS.txt'}, 'Unexpected packet inventory')
    require(regular(packet / 'STATUS.txt') == STATUS, 'Runtime status differs')
    plan_path = packet / 'provenance/source99/source-plan.json'
    plan = load_json(regular(plan_path)); upstream, _ = source_checker.validate_plan(plan)
    transition = manifest['upstream99']
    require(transition['source_input'] == str(SOURCE_INPUT) and plan['output'] == str(SOURCE_INPUT), 'Source input identity differs')
    require(transition['source_plan_sha256'] == sha(plan_path) and
            transition['historical_manifest_sha256'] == OLD_MANIFEST and
            transition['qualification'] is False, 'Transition provenance differs')
    require(regular(packet / 'provenance/source99/packet98-manifest.json') == regular(HISTORICAL / 'manifest.json'),
            'Historical manifest provenance differs')
    archive = packet / 'provenance/source99/upstream-source.tar'
    require(sha(archive) == plan['archive_sha256'] and archive.stat().st_size == plan['archive_bytes'],
            'Upstream archive provenance differs')
    source_checker.check_archive(archive, upstream, plan['source_files'])
    expected_source = {}
    expected_overlays = {}
    for path, row in plan['source_files'].items():
        if path in PORT_PINS or path in ATTENTION_FILES:
            original = regular(packet / 'provenance/source-before-port' / path)
            require(digest(original) == row['sha256'], 'Pre-port source differs')
            modified = port_source(path, original, plan['source_files'])
            expected = digest(modified)
            expected_overlays[path] = {'before_sha256': digest(original), 'after_sha256': expected,
                'diff': ''.join(difflib.unified_diff(original.decode().splitlines(keepends=True),
                    modified.decode().splitlines(keepends=True), fromfile='source99/' + path,
                    tofile='runtime99/' + path))}
        else:
            expected = row['sha256']
        expected_source['source/' + path] = expected
        require(stat.S_IMODE((packet / 'source' / path).stat().st_mode) == int(row['mode'], 8) & 0o777,
                'Final source mode differs')
    require({p: h for p, h in files.items() if p.startswith('source/')} == expected_source, 'Final source overlay differs')
    require(transition['source_runtime_overlays'] == expected_overlays, 'Runtime source-delta provenance differs')
    for path, expected in parent['files'].items():
        if not path.startswith(('source/', 'launch/')):
            require(files.get(path) == expected, 'Historical graph/provenance dependency changed: ' + path)
    require(regular(packet / 'launch/serve-encoder.py') == launcher_source(regular(HISTORICAL / 'launch/serve-encoder.py')),
            'Launcher differs beyond reviewed insertions')
    require(regular(packet / 'launch/encoder_runtime_common.py') == regular(packet / 'provenance/check-runtime-99.py'),
            'Runtime checker provenance differs')
    require(regular(packet / 'launch/progress_lock.py') ==
            progress_module(regular(packet / 'provenance/progress-lock/launch_with_progress_lock.py').decode()),
            'Progress installer differs from reviewed extraction')
    require(transition['control'] == {'layout': 'two-way', 'blocks': [23, 25], 'workers': 2, 'batch': 1,
            'shared_pool': 1, 'decode_replica': 'xpu:2', 'size': '256x256', 'references': 'w93c'}, 'Control identity differs')
    require(set(transition['campaign_bindings']) == {'runner', 'memory_helper'}, 'Campaign binding inventory differs')
    require(transition['dependencies']['state'] in ('pending', 'matched'), 'Unknown dependency state')
    if transition['dependencies']['state'] == 'matched':
        dep_raw = regular(packet / 'provenance/dependencies.json')
        require(digest(dep_raw) == transition['dependencies']['receipt_sha256'], 'Dependency provenance differs')
        verify_dependencies(dep_raw, manifest['runtime'])
    expected_files = set(expected_source)
    expected_files.update(('provenance/packet98/' + p if p.startswith('launch/') else p)
                          for p in parent['files'] if not p.startswith('source/'))
    expected_files.update('provenance/source-before-port/' + p for p in expected_overlays)
    expected_files.update('provenance/source99/' + p for p in (
        'prepare-upstream-99.py', 'check-upstream-source-99.py', 'source-plan.json',
        'source-check.json', 'packet98-manifest.json', 'upstream-source.tar'))
    expected_files.update('launch/' + p for p in (
        'serve-encoder.py', 'encoder_runtime_common.py', 'check-storage-headroom.py',
        'progress_lock.py', 'refresh.original.py', 'refresh.candidate.py'))
    expected_files.update('provenance/progress-lock/' + p for p in (
        'launch_with_progress_lock.py', 'refresh.original.py', 'refresh.candidate.py',
        'identity.json', 'result.json', 'TQDM-LICENCE'))
    expected_files.update({'provenance/build-runtime-99.py', 'provenance/check-runtime-99.py',
                           'provenance/runtime-port.json'})
    for binding in transition['campaign_bindings'].values():
        require(binding['packet_path'] == 'campaign/' + Path(binding['source']).name, 'Campaign snapshot path differs')
        expected_files.add(binding['packet_path'])
    if transition['dependencies']['state'] == 'matched':
        expected_files.add('provenance/dependencies.json')
    require(set(files) == expected_files, 'Runtime closure contains missing/unreviewed files')
    expected = semantic_manifest(parent, files, sha(packet / 'provenance/build-runtime-99.py'), transition)
    require(manifest == expected, 'Runtime semantic contract differs beyond explicit transition')
    for name, binding in transition['campaign_bindings'].items():
        require(sha(Path(binding['source'])) == binding['sha256'] == files[binding['packet_path']],
                'Campaign helper identity changed: ' + name)
    _LEGACY.verify_na_source_closure(packet / 'source')
    return manifest


def self_test():
    checks = []
    rows = {'nodes.py': {'sha256': 'a' * 64}, 'comfy/sd.py': {'sha256': 'b' * 64}}
    raw = ("NODES_SHA = '" + '1' * 64 + "'\nSD_SHA = '" + '2' * 64 + "'\nvalue = 7\n").encode()
    changed = port_source('scripts/na_axis_decode_node.py', raw, rows)
    require(b'value = 7\n' in changed and ('a' * 64).encode() in changed, 'Pin-only control failed')
    try:
        port_source('scripts/na_axis_decode_node.py', raw + raw, rows)
    except RuntimeError:
        checks.append('ambiguous-pin-refused')
    else:
        raise RuntimeError('Ambiguous pin accepted')
    # Execute the actual inserted guard with fake CPU modules, excluding only
    # its real import (which would initialize the native application).
    from types import SimpleNamespace
    class FakeAttention(SimpleNamespace):
        pass
    guard = textwrap.dedent(ATTENTION_GUARD).replace('from comfy.ldm.modules.attention import ComfyAttention\n', '')
    namespace = {'ComfyAttention': FakeAttention, 'require': require}
    exec('def checked(model):\n' + textwrap.indent(guard, '    '), namespace)
    for items, accepted in [([], False), ([FakeAttention(config=None, function=None)], True),
                            ([FakeAttention(config={}, function=None)], False),
                            ([FakeAttention(config=None, function=lambda: None)], False)]:
        model = SimpleNamespace(model=SimpleNamespace(diffusion_model=SimpleNamespace(modules=lambda: items)))
        try:
            namespace['checked'](model); passed = True
        except RuntimeError:
            passed = False
        require(passed == accepted, 'Attention backend refusal control failed')
    checks += ['named-pin-only-edit', 'empty-configured-custom-function-attention-refused', 'native-attention-admitted']
    ast.parse(launcher_source(regular(HISTORICAL / 'launch/serve-encoder.py')))
    checks.append('actual-launcher-transform-compiles')
    from unittest.mock import patch
    for limits, accepted in [((1024, 1048576), False), ((65536, 1048576), True),
                             ((65536, 65536), False)]:
        with patch.object(resource, 'getrlimit', return_value=limits):
            try:
                check_file_limits(); passed = True
            except RuntimeError:
                passed = False
        require(passed == accepted, 'File-limit boundary control failed')
    checks.append('actual-file-limit-boundary-refuses-low-soft-and-wrong-hard')
    require_clean_dependency_modules({'json': object()})
    for name in ('comfyui_frontend_package', 'cryptography.hazmat', '_cffi_backend',
                 'comfyui_workflow_templates_media_api.child', 'torch.xpu'):
        try:
            require_clean_dependency_modules({name: object()})
        except RuntimeError:
            pass
        else:
            raise RuntimeError('Stale module admitted: ' + name)
    checks.append('all-replaced-module-roots-and-descendants-refused')
    try:
        activate_dependencies(PACKET, {'upstream99': {'dependencies': {'state': 'pending'}}})
    except RuntimeError:
        checks.append('pending-dependencies-refuse-launch')
    else:
        raise RuntimeError('Pending dependencies admitted')
    return {'status': 'passed', 'controls': checks, 'model_requests': 0, 'prepared_sources': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--packet', type=Path, default=PACKET)
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args()
    if args.self_test:
        result = self_test()
    else:
        manifest = verify_packet(args.packet, args.manifest_sha256)
        result = {'status': 'runtime-source-integrity-passed-not-GPU-qualified',
                  'dependency_state': manifest['upstream99']['dependencies']['state'],
                  'qualification': False, 'model_requests': 0}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
