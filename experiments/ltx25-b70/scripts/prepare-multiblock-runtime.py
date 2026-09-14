#!/usr/bin/env python3
"""Prepare an inactive sealed multiblock successor; no native imports or server actions."""
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
PARENT = ROOT / 'prepared-encoder-compiler-05'
PARENT_SHA = '45dc23a7c0a0a234412e31a36225716edf60bb16ad342d96fe12f65139bccbe5'
PARENT_CHECKER_SHA = '644ca25a9918038faa75b17813798530e341ddb48cb65109f312b05dc06f0732'
PARENT_BUILDER_SHA = 'cfbdb1c7aa7eeb34b50e610f0390c7463fc8b00b7044f6acaa620267e65f4f24'
RMS_PARENT_SHA = 'c4e0f7e56fc7bbc51101894d79d279dd9886f07272868dc99cc7953c647a65c9'
ADAPTER = 'ltx_multiblock_compile.py'
ADAPTER_SHA = '12ffb29cb4c8a61e8d9a22586a5f9f96ad170de882d62bfb4981f269d3b1bd3f'
NODE = 'multiblock_compile_node.py'
NODE_SHA = 'e7d6e69ff44d5b727dba27f52142647a06afe6d494abb043af49fa132a005d2f'
ACTIVATIONS_SHA = '62b78186fdfc6d9a22cb8cb10423869ecc37cc09c9c0994a7ccebe2eafd41c2a'
RMS_SHA = '09defae7340dc3d7f33e16ab80c76f22b6a2ae733617704f2e7b69086108d9fb'
SCHEMA = 'ltx.compiler-multiblock-runtime-packet.v1'
MODIFIED = ('launch/encoder_runtime_common.py',)
SELECTIONS = {'single24': [24], 'boundary4': [0, 20, 21, 47], 'all48': list(range(48))}
MODES = ('original', 'compiled', 'restored')

# Reuse only the pinned parent preparer's stdlib utilities. prepare() is not
# invoked at import time; tests can exercise source construction without a packet.
_parent_builder_path = LANE / 'scripts/prepare-native-activations-runtime.py'
if hashlib.sha256(_parent_builder_path.read_bytes()).hexdigest() != PARENT_BUILDER_SHA:
    raise RuntimeError('Frozen activation preparer changed')
_spec = importlib.util.spec_from_file_location('multiblock_parent_preparer', _parent_builder_path)
parent_builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parent_builder)
base = parent_builder.base
require, sha, text_sha = base.require, base.sha, base.text_sha
replace_once, write_json = base.replace_once, base.write_json


def graph_source(control, selection, mode):
    require(selection in SELECTIONS and mode in MODES, 'Only fixed multiblock graph choices are admitted')
    graph = copy.deepcopy(control)
    require('422' not in graph, 'Multiblock graph node collision')
    graph['422'] = {'class_type': 'LTXCompileBlocksGate', 'inputs': {
        'model': ['420', 0], 'mode': mode, 'selection': selection,
        'run_name': 'assign-unique-request-name'}}
    for node in ('388', '391'):
        require(graph[node]['inputs']['model'] == ['420', 0], 'Control model edge changed')
        graph[node]['inputs']['model'] = ['422', 0]
    return graph


def checker_source(original):
    changes = [
        ("'ltx_native_rms_backend.py', 'ltx_native_activations_backend.py')",
         "'ltx_native_rms_backend.py', 'ltx_native_activations_backend.py',\n              'ltx_multiblock_compile.py', 'multiblock_compile_node.py')"),
        ("'ltx_block_compile_lab': 'block_compile_node.py'}",
         "'ltx_block_compile_lab': 'block_compile_node.py',\n         'ltx_multiblock_compile_lab': 'multiblock_compile_node.py'}"),
        ("manifest['schema'] == 'ltx.compiler-native-activations-runtime-packet.v1'",
         f"manifest['schema'] == '{SCHEMA}'"),
        (f"manifest['parent_manifest_sha256'] == '{RMS_PARENT_SHA}'",
         f"manifest['native_rms_parent_manifest_sha256'] == '{RMS_PARENT_SHA}'"),
    ]
    text = original
    for old, new in changes:
        text = replace_once(text, old, new)
    checks = f'''    # Preserve all single-block ancestry/gates; only this checker changes.
    require(manifest['parent_manifest_sha256'] == {PARENT_SHA!r}, 'Unexpected activation parent')
    activation_parent_path = safe_path(packet, 'native-activations-parent-manifest.json')
    require(sha(activation_parent_path) == {PARENT_SHA!r}, 'Activation parent manifest changed')
    activation_parent = json.loads(activation_parent_path.read_text())
    require(activation_parent['schema'] == 'ltx.compiler-native-activations-runtime-packet.v1',
            'Unexpected activation parent schema')
    require(manifest['runtime'] == activation_parent['runtime'], 'Multiblock runtime changed')
    for name, digest in activation_parent['files'].items():
        if name == 'launch/encoder_runtime_common.py':
            require(manifest['files']['provenance/multiblock-parent/' + name] == digest,
                    'Original activation checker changed')
        else:
            require(manifest['files'].get(name) == digest, 'Inherited activation source changed: ' + name)
    require(manifest['extension_sha256s']['ltx_multiblock_compile.py'] == {ADAPTER_SHA!r}
            and manifest['extension_sha256s']['multiblock_compile_node.py'] == {NODE_SHA!r},
            'Multiblock source identity changed')
    multi = manifest['multiblock']
    require(multi['adapter_sha256'] == {ADAPTER_SHA!r} and multi['node_sha256'] == {NODE_SHA!r}
            and multi['backend_sha256'] == {ACTIVATIONS_SHA!r} and multi['rms_dependency_sha256'] == {RMS_SHA!r},
            'Multiblock implementation identity changed')
    require(multi['selections'] == {SELECTIONS!r} and multi['modes'] == {list(MODES)!r}
            and multi['maximum_retained_candidates'] == 3 and multi['split_index'] == 21
            and multi['calls_per_block_per_clip'] == 11 and multi['stages_per_block'] == 2
            and multi['dynamo_limits_required'] == {{'recompile_limit': 8, 'accumulated_recompile_limit': 256}}
            and multi['expected_rms_count'] == 15
            and multi['expected_activation_counts'] == {{'sigmoid': 6, 'gelu': 2}},
            'Bounded multiblock contract changed')
    control = json.loads(safe_path(packet, 'graphs/control.json').read_text())
    expected_graph_paths = []
    for selection in {tuple(SELECTIONS)!r}:
        for mode in {MODES!r}:
            graph_name = 'graphs/multiblock-' + selection + '-' + mode + '.json'
            expected_graph_paths.append(graph_name)
            graph = json.loads(safe_path(packet, graph_name).read_text())
            require(graph.pop('422') == {{'class_type': 'LTXCompileBlocksGate', 'inputs': {{
                    'model': ['420', 0], 'mode': mode, 'selection': selection,
                    'run_name': 'assign-unique-request-name'}}}}, 'Multiblock graph node changed')
            for node in ('388', '391'):
                require(graph[node]['inputs']['model'] == ['422', 0], 'Multiblock graph edge changed')
                graph[node]['inputs']['model'] = ['420', 0]
            require(graph == control, 'Multiblock graph changed original quality recipe')
    require(multi['graphs'] == expected_graph_paths, 'Multiblock graph inventory changed')
'''
    text = replace_once(text, '    return manifest\n', checks + '    return manifest\n')
    reverse = replace_once(text, checks, '')
    for old, new in reversed(changes):
        reverse = replace_once(reverse, new, old)
    require(ast.dump(ast.parse(reverse)) == ast.dump(ast.parse(original)), 'Parent checker gates were altered')
    return text


def prepare(output):
    require(output.is_absolute() and output.parent == ROOT and
            re.fullmatch(r'prepared-encoder-compiler-[a-z0-9-]+', output.name), 'Use a new compiler packet path')
    require(not output.exists() and not output.is_symlink(), 'Packet exists; never overwrite')
    require(sha(PARENT / 'manifest.json') == PARENT_SHA, 'Parent manifest changed')
    require(sha(PARENT / 'launch/encoder_runtime_common.py') == PARENT_CHECKER_SHA, 'Parent checker changed')
    inputs = {ADAPTER: ADAPTER_SHA, NODE: NODE_SHA}
    sources = {}
    for name, digest in inputs.items():
        path = LANE / 'scripts' / name
        require(not path.is_symlink() and sha(path) == digest, 'Multiblock source input changed: ' + name)
        sources[name] = path.read_text()
        ast.parse(sources[name])
    builder_sha = sha(Path(__file__))
    common = base.load_checker(PARENT / 'launch/encoder_runtime_common.py', 'multiblock_parent_checker')
    common.safe_path(ROOT, output.name)
    parent = common.verify_packet(PARENT, PARENT_SHA)
    common.verify_runtime(parent['runtime'])
    require(parent['extension_sha256s']['ltx_native_activations_backend.py'] == ACTIVATIONS_SHA and
            parent['extension_sha256s']['ltx_native_rms_backend.py'] == RMS_SHA, 'Native backend dependency changed')
    model = common.safe_path(ROOT, 'model-verification.json')
    require(sha(model) == common.MODEL_VERIFICATION_SHA256 and
            json.loads(model.read_text())['status'] == 'passed', 'Model provenance changed')
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than 5 GiB disk free')
    checker = checker_source((PARENT / 'launch/encoder_runtime_common.py').read_text())
    control = json.loads((PARENT / 'graphs/control.json').read_text())
    graphs = {f'graphs/multiblock-{selection}-{mode}.json': graph_source(control, selection, mode)
              for selection in SELECTIONS for mode in MODES}
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE multiblock packet; do not launch.\n')
    for name in parent['files']:
        source, target = common.safe_path(PARENT, name), common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(PARENT / 'manifest.json', output / 'native-activations-parent-manifest.json')
    provenance = output / 'provenance/multiblock-parent/launch/encoder_runtime_common.py'
    provenance.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PARENT / 'launch/encoder_runtime_common.py', provenance)
    shutil.copyfile(Path(__file__), output / 'provenance' / Path(__file__).name)
    replacements = {'launch/encoder_runtime_common.py': checker,
                    'source/scripts/' + ADAPTER: sources[ADAPTER],
                    'source/scripts/' + NODE: sources[NODE],
                    'source/custom_nodes/ltx_multiblock_compile_lab/__init__.py': sources[NODE]}
    for name, graph in graphs.items():
        replacements[name] = json.dumps(graph, indent=2, sort_keys=True) + '\n'
    delta = []
    for name, content in replacements.items():
        target = common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        original = (PARENT / name).read_text() if name in parent['files'] else ''
        delta.extend(difflib.unified_diff(original.splitlines(keepends=True), content.splitlines(keepends=True),
                    fromfile='a/' + name if name in parent['files'] else '/dev/null', tofile='b/' + name))
    patch_name = 'multiblock-runtime.patch'
    (output / 'patches' / patch_name).write_text(''.join(delta))
    common.verify_packet(PARENT, PARENT_SHA)
    require(sha(Path(__file__)) == builder_sha and sha(_parent_builder_path) == PARENT_BUILDER_SHA and
            all(sha(LANE / 'scripts' / name) == digest for name, digest in inputs.items()),
            'Preparation inputs changed')
    files = base.inventory(output)
    changed = {name for name, digest in parent['files'].items() if files[name] != digest}
    require(changed == set(MODIFIED), 'Unexpected inherited source changes')
    checks = {'changed_parent_files': sorted(changed), 'all_parent_checker_gates_retained': True,
              'all_inherited_singleblock_files_unchanged': True, 'original_control_recipe_unchanged': True,
              'native_backends_unchanged': True, 'launcher_runtime_model_unchanged': True,
              'added_source_sha256s': inputs, 'native_imported_or_executed': False,
              'runtime_admission_attempted': False}
    write_json(output / 'provenance/multiblock-source-checks.json', checks)
    local = base.load_checker(output / 'launch/encoder_runtime_common.py', 'multiblock_packet_checker')
    manifest = copy.deepcopy(parent)
    manifest.update(schema=SCHEMA, parent_packet=str(PARENT), parent_manifest_sha256=PARENT_SHA,
                    native_rms_parent_manifest_sha256=parent['parent_manifest_sha256'],
                    multiblock_preparer_sha256=builder_sha,
                    offline_preparation={'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
                        'fault_latch_present_at_preparation': (ROOT / 'FAULT.json').exists(),
                        'runtime_admission': 'not attempted; source preparation only'},
                    startup_tools={name: sha(output / 'launch' / name) for name in parent['startup_tools']},
                    extension_sha256s={name: sha(output / 'source/scripts' / name) for name in local.EXTENSIONS})
    manifest['multiblock'] = {'adapter_sha256': ADAPTER_SHA, 'node_sha256': NODE_SHA,
        'backend_sha256': ACTIVATIONS_SHA, 'rms_dependency_sha256': RMS_SHA,
        'selections': SELECTIONS, 'modes': list(MODES), 'maximum_retained_candidates': 3,
        'split_index': 21, 'calls_per_block_per_clip': 11, 'stages_per_block': 2,
        'dynamo_limits_required': {'recompile_limit': 8, 'accumulated_recompile_limit': 256},
        'expected_rms_count': 15, 'expected_activation_counts': {'sigmoid': 6, 'gelu': 2},
        'graphs': list(graphs), 'receipt_layout': 'native-multiblock-{selection}/block-{index:02d}',
        'scope': 'Fixed selected native blocks; independent exact stage gates and retained original/compiled/restored choices',
        'options': 'Original native-activation OPTIONS; fullgraph=True, dynamic=False; no compiler-limit changes',
        'native_block_xpu_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False}
    manifest['patch_order'].append(patch_name)
    manifest['patch_sha256s'][patch_name] = sha(output / 'patches' / patch_name)
    manifest['limitations'].extend([
        'Multiblock code is a new inactive candidate; no native block, full-clip or speed qualification is claimed.',
        'All inherited single-block sources, plugin, graphs and native backends remain byte-identical to packet05.',
        'A pinned multiblock client must enforce per-block receipts, both stages, full original four-output equality and fault-halt.',
        'No compiler-limit override, application admission, server action, power or memory setting change is performed by preparation.'])
    manifest['files'] = base.inventory(output)
    manifest['files'].pop('STATUS.txt')
    write_json(output / 'manifest.json', manifest)
    digest = sha(output / 'manifest.json')
    local.verify_packet(output, digest)
    local.verify_runtime(manifest['runtime'])
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE multiblock successor. Native/full-clip gates pending.\n')
    return {'status': 'prepared-inactive-not-deployed', 'packet': str(output), 'manifest_sha256': digest,
            'parent_manifest_sha256': PARENT_SHA, 'adapter_sha256': ADAPTER_SHA, 'node_sha256': NODE_SHA,
            'files': len(manifest['files']), 'source_checks': checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), indent=2))
