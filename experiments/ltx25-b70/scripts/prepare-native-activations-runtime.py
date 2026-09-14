#!/usr/bin/env python3
"""Prepare an inactive native-activation successor; no native imports or server actions."""
import argparse
import ast
import copy
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-encoder-compiler-04'
PARENT_SHA = 'c4e0f7e56fc7bbc51101894d79d279dd9886f07272868dc99cc7953c647a65c9'
PARENT_CHECKER_SHA = 'd039c6874d097549abd469402a6c07fe16d9c02e586ed3c277de93c8b979b043'
PARENT_ADAPTER_SHA = 'd3daa4a7b7150a4fa316c346fdea259139147419a59950642bf06b2ec62fe3d4'
PARENT_NODE_SHA = '4ef8a1e844620e3810c1e456f16f9502e0de2b9cec2d0993cfe1e649fb6a4555'
ADAPTER_SHA = 'c3f3e4ede85b2798981dca40562bd77586ad63afe55b043c0705fceddda29a1e'
BACKEND = 'ltx_native_activations_backend.py'
BACKEND_SHA = '62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a'
RMS_SHA = '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb'
BASE_BUILDER_SHA = 'dbe470120c3ecd5f6f0f42786958494acf8e99b8dc693540f0289495b13e6db6'
SCHEMA = 'ltx.compiler-native-activations-runtime-packet.v1'
MODIFIED = ('launch/encoder_runtime_common.py', 'source/scripts/ltx_block_compile.py',
            'source/scripts/block_compile_node.py',
            'source/custom_nodes/ltx_block_compile_lab/__init__.py')

# Reuse only stdlib utilities from the frozen, archived parent preparer.
_base_path = LANE / 'scripts/prepare-native-rms-runtime.py'
if hashlib.sha256(_base_path.read_bytes()).hexdigest() != BASE_BUILDER_SHA:
    raise RuntimeError('Frozen source-preparation helper changed')
_spec = importlib.util.spec_from_file_location('activation_parent_preparer', _base_path)
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
require, sha, text_sha = base.require, base.sha, base.text_sha
replace_once, write_json = base.replace_once, base.write_json


def adapter_source(original):
    return replace_once(replace_once(original,
        'from ltx_native_rms_backend import make_backend',
        'from ltx_native_activations_backend import make_backend'),
        "'native-rms-graphs'", "'native-activation-graphs'")


def checker_source(original):
    changes = [
        ("'ltx_native_rms_backend.py')", "'ltx_native_rms_backend.py', 'ltx_native_activations_backend.py')"),
        ("manifest['schema'] == 'ltx.compiler-native-rms-runtime-packet.v1'",
         f"manifest['schema'] == '{SCHEMA}'"),
        ("manifest['parent_manifest_sha256'] == '9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980'",
         "manifest['compiler_parent_manifest_sha256'] == '9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980'"),
        (f"manifest['compiler']['effective_adapter_sha256'] ==\n            '{PARENT_ADAPTER_SHA}'",
         f"manifest['compiler']['effective_adapter_sha256'] ==\n            '{ADAPTER_SHA}'"),
    ]
    text = original
    for old, new in changes:
        text = replace_once(text, old, new)
    checks = f'''    # Retain the complete RMS04 ancestry and add this immediate-parent gate.
    require(manifest['parent_manifest_sha256'] == {PARENT_SHA!r}, 'Unexpected native RMS parent')
    rms_parent_path = safe_path(packet, 'native-rms-parent-manifest.json')
    require(sha(rms_parent_path) == {PARENT_SHA!r}, 'Native RMS parent manifest changed')
    rms_parent = json.loads(rms_parent_path.read_text())
    require(rms_parent['schema'] == 'ltx.compiler-native-rms-runtime-packet.v1', 'Unexpected RMS parent schema')
    require(manifest['runtime'] == rms_parent['runtime'], 'Activation runtime changed')
    changed_activation_files = {MODIFIED!r}
    for name, digest in rms_parent['files'].items():
        if name in changed_activation_files:
            require(manifest['files']['provenance/native-activations-parent/' + name] == digest,
                    'Original RMS parent source changed: ' + name)
        else:
            require(manifest['files'].get(name) == digest, 'Inherited RMS source changed: ' + name)
    require(manifest['native_activations']['backend_sha256'] == {BACKEND_SHA!r}
            and manifest['extension_sha256s']['ltx_native_activations_backend.py'] == {BACKEND_SHA!r},
            'Native activation backend changed')
    require(manifest['native_activations']['rms_dependency_sha256'] == {RMS_SHA!r}
            and manifest['native_activations']['effective_adapter_sha256'] == {ADAPTER_SHA!r}
            and manifest['native_activations']['expected_count'] == 15
            and manifest['native_activations']['expected_activation_counts'] == {{'sigmoid': 6, 'gelu': 2}},
            'Native activation intervention changed')
'''
    text = replace_once(text, '    return manifest\n', checks + '    return manifest\n')
    reverse = replace_once(text, checks, '')
    for old, new in reversed(changes):
        reverse = replace_once(reverse, new, old)
    require(ast.dump(ast.parse(reverse)) == ast.dump(ast.parse(original)), 'Parent checker gates were altered')
    return text


def prepare(output):
    require(output.is_absolute() and output.parent == ROOT
            and re.fullmatch(r'prepared-encoder-compiler-[a-z0-9-]+', output.name), 'Use a new compiler packet path')
    require(not output.exists() and not output.is_symlink(), 'Packet already exists; never overwrite')
    require(sha(PARENT / 'manifest.json') == PARENT_SHA, 'Parent manifest changed')
    require(sha(PARENT / 'launch/encoder_runtime_common.py') == PARENT_CHECKER_SHA, 'Parent checker changed')
    backend = LANE / 'scripts' / BACKEND
    require(not backend.is_symlink() and sha(backend) == BACKEND_SHA, 'Activation backend input changed')
    backend_text = backend.read_text()
    ast.parse(backend_text)
    builder_sha = sha(Path(__file__))
    common = base.load_checker(PARENT / 'launch/encoder_runtime_common.py', 'activation_parent_checker')
    common.safe_path(ROOT, output.name)
    parent = common.verify_packet(PARENT, PARENT_SHA)
    common.verify_runtime(parent['runtime'])
    require(parent['extension_sha256s']['ltx_native_rms_backend.py'] == RMS_SHA, 'Pinned RMS dependency changed')
    model = common.safe_path(ROOT, 'model-verification.json')
    require(sha(model) == common.MODEL_VERIFICATION_SHA256
            and json.loads(model.read_text())['status'] == 'passed', 'Model provenance changed')
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than 5 GiB disk free')
    old_adapter = (PARENT / 'source/scripts/ltx_block_compile.py').read_text()
    old_node = (PARENT / 'source/scripts/block_compile_node.py').read_text()
    require(text_sha(old_adapter) == PARENT_ADAPTER_SHA and text_sha(old_node) == PARENT_NODE_SHA,
            'Parent compiler source pins changed')
    adapter = adapter_source(old_adapter)
    require(text_sha(adapter) == ADAPTER_SHA, 'Candidate adapter differs from the two reviewed edits')
    reverse_adapter = adapter.replace('from ltx_native_activations_backend import make_backend',
                                      'from ltx_native_rms_backend import make_backend', 1).replace(
                                      "'native-activation-graphs'", "'native-rms-graphs'", 1)
    require(ast.dump(ast.parse(reverse_adapter)) == ast.dump(ast.parse(old_adapter)), 'Adapter math/lifecycle changed')
    node = replace_once(old_node, f'ADAPTER_SHA256 = {PARENT_ADAPTER_SHA!r}', f'ADAPTER_SHA256 = {ADAPTER_SHA!r}')
    require(ast.dump(ast.parse(node.replace(ADAPTER_SHA, PARENT_ADAPTER_SHA))) == ast.dump(ast.parse(old_node)),
            'Compiler node changed beyond the adapter identity literal')
    checker = checker_source((PARENT / 'launch/encoder_runtime_common.py').read_text())
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE native activations packet; do not launch.\n')
    for name in parent['files']:
        source, target = common.safe_path(PARENT, name), common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(PARENT / 'manifest.json', output / 'native-rms-parent-manifest.json')
    for name in MODIFIED:
        target = output / 'provenance/native-activations-parent' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, target)
    shutil.copyfile(Path(__file__), output / 'provenance' / Path(__file__).name)
    (output / 'source/scripts' / BACKEND).write_text(backend_text)
    replacements = {'launch/encoder_runtime_common.py': checker,
                    'source/scripts/ltx_block_compile.py': adapter,
                    'source/scripts/block_compile_node.py': node,
                    'source/custom_nodes/ltx_block_compile_lab/__init__.py': node}
    delta = []
    for name, content in replacements.items():
        (output / name).write_text(content)
        delta.extend(difflib.unified_diff((PARENT / name).read_text().splitlines(keepends=True),
                    content.splitlines(keepends=True), fromfile='a/' + name, tofile='b/' + name))
    patch_name = 'native-activations-backend-runtime.patch'
    (output / 'patches' / patch_name).write_text(''.join(delta))
    common.verify_packet(PARENT, PARENT_SHA)
    require(sha(backend) == BACKEND_SHA and sha(Path(__file__)) == builder_sha
            and sha(_base_path) == BASE_BUILDER_SHA, 'Preparation inputs changed')
    files = base.inventory(output)
    changed = {name for name, digest in parent['files'].items() if files[name] != digest}
    require(changed == set(MODIFIED), 'Unexpected inherited source changes')
    checks = {'changed_parent_files': sorted(changed),
              'whole_adapter_ast_only_backend_import_and_receipt_directory_changed': True,
              'node_ast_only_adapter_hash_changed': True, 'all_parent_checker_gates_retained': True,
              'rms_dependency_unchanged': files['source/scripts/ltx_native_rms_backend.py'] == RMS_SHA,
              'launcher_graphs_model_loader_decoder_unchanged': True,
              'original_options_fullgraph_static_lifecycle_unchanged': True,
              'backend_sha256': BACKEND_SHA, 'native_imported_or_executed': False,
              'runtime_admission_attempted': False}
    require(checks['rms_dependency_unchanged'], 'RMS dependency bytes changed')
    write_json(output / 'provenance/native-activations-source-checks.json', checks)
    local = base.load_checker(output / 'launch/encoder_runtime_common.py', 'activation_packet_checker')
    manifest = copy.deepcopy(parent)
    manifest.update(schema=SCHEMA, parent_packet=str(PARENT), parent_manifest_sha256=PARENT_SHA,
                    compiler_parent_manifest_sha256=parent['parent_manifest_sha256'],
                    native_activations_preparer_sha256=builder_sha,
                    offline_preparation={'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
                        'fault_latch_present_at_preparation': (ROOT / 'FAULT.json').exists(),
                        'runtime_admission': 'not attempted; source preparation only'},
                    startup_tools={name: sha(output / 'launch' / name) for name in parent['startup_tools']},
                    extension_sha256s={name: sha(output / 'source/scripts' / name) for name in local.EXTENSIONS})
    manifest['compiler']['effective_adapter_sha256'] = ADAPTER_SHA
    manifest['native_activations'] = {'backend_sha256': BACKEND_SHA, 'rms_dependency_sha256': RMS_SHA,
        'expected_count': 15, 'expected_activation_counts': {'sigmoid': 6, 'gelu': 2},
        'effective_adapter_sha256': ADAPTER_SHA, 'parent_adapter_sha256': PARENT_ADAPTER_SHA,
        'receipt_directory': "Path(os.environ['LTX_ENCODER_RUN_DIR']) / 'native-activation-graphs'",
        'scope': 'One native block24; retain RMS boundary and add native sigmoid/explicit tanh-GELU boundaries',
        'options': 'Original OPTIONS bound at backend; fullgraph=True and dynamic=False unchanged',
        'native_block_xpu_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False}
    manifest['patch_order'].append(patch_name)
    manifest['patch_sha256s'][patch_name] = sha(output / 'patches' / patch_name)
    manifest['limitations'].extend([
        'Native activation candidate is distinct from failed native RMS-only block qualification; no new native result is claimed.',
        'Inherited native_rms metadata describes unchanged RMS dependency and parent04 intervention provenance; current directory/counts are native_activations.',
        'A separately pinned client must accept the new adapter/backend and verify 15 RMS, six sigmoid, two tanh-GELU replacements per native stage.',
        'Packet04 and its preparer remain unchanged; no active-server, decoder or loader edits are included.'])
    manifest['files'] = base.inventory(output)
    manifest['files'].pop('STATUS.txt')
    write_json(output / 'manifest.json', manifest)
    digest = sha(output / 'manifest.json')
    local.verify_packet(output, digest)
    local.verify_runtime(manifest['runtime'])
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE native activation successor. Native XPU/full-clip gates pending.\n')
    return {'status': 'prepared-inactive-not-deployed', 'packet': str(output), 'manifest_sha256': digest,
            'parent_manifest_sha256': PARENT_SHA, 'backend_sha256': BACKEND_SHA,
            'effective_adapter_sha256': ADAPTER_SHA, 'files': len(manifest['files']), 'source_checks': checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
