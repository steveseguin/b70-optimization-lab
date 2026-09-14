#!/usr/bin/env python3
"""Prepare inactive packet07 from packet06; --check-only writes nothing.

Only the compiler adapter and packet checker change. No native imports, server
admission, process/device operations, or changes to inherited source packets.
"""
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
PARENT = ROOT / 'prepared-encoder-compiler-06'
PARENT_SHA = '3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394'
PARENT_CHECKER_SHA = 'cf1e30f7f4b78fe018d992a5e914adaf5bdf1b7be1f44f7c324fdb57b59432f1'
PARENT_BUILDER_SHA = '6969d5871924d696e962620dca21680fe05b597a15d1400328a911c7d09d3f56'
ACTIVATION_PARENT_SHA = '45dc23a7c0a0a234412e31a36225716edf60bb16ad342d96fe12f65139bccbe5'
ORIGINAL_SHA = '12ffb29cb4c8a61e8d9a22586a5f9f96ad170de882d62bfb4981f269d3b1bd3f'
ADAPTER_SHA = '79b4e76b10f49094f3ad11cc70ba62334c2ccf10e50960ac209fb5a0cdd2a584'
CANDIDATE = LANE / 'patches/multiblock-adjacent-state-03/candidate.py'
NODE_SHA = 'e7d6e69ff44d5b727dba27f52142647a06afe6d494abb043af49fa132a005d2f'
SCHEMA = 'ltx.compiler-multiblock-adjacent-state-runtime-packet.v1'
MODIFIED = ('launch/encoder_runtime_common.py', 'source/scripts/ltx_multiblock_compile.py')
_parent_builder = LANE / 'scripts/prepare-multiblock-runtime.py'
if hashlib.sha256(_parent_builder.read_bytes()).hexdigest() != PARENT_BUILDER_SHA:
    raise RuntimeError('Pinned parent preparer changed')
_spec = importlib.util.spec_from_file_location('adjacent_state_parent_preparer', _parent_builder)
parent_builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parent_builder)
base = parent_builder.base
require, sha, text_sha = base.require, base.sha, base.text_sha
replace_once, write_json = base.replace_once, base.write_json


def validate_adapter(original, candidate):
    """Reconstruct the only admitted edit, then reverse its complete module AST."""
    changes = [
        ('            self._lifecycle.validate_current_execution(self)\n',
         '            self._lifecycle.validate_current_execution(self)\n            return True\n        return False\n'),
        ('        self._validate_execution()\n        self._validate(check_device=True)\n',
         '        if not self._validate_execution():\n            self._validate(check_device=True)\n'),
        ('        self._validate_execution()\n        self._validate(check_device=False)\n',
         '        if not self._validate_execution():\n            self._validate(check_device=False)\n'),
    ]
    expected = original
    for old, new in changes:
        expected = replace_once(expected, old, new)
    require(expected == candidate, 'Candidate differs from reviewed adjacent-check edits')
    reverse = candidate
    for old, new in reversed(changes):
        reverse = replace_once(reverse, new, old)
    require(ast.dump(ast.parse(reverse)) == ast.dump(ast.parse(original)), 'Adapter AST did not reverse exactly')


def checker_source(original):
    changes = [
        ("manifest['schema'] == 'ltx.compiler-multiblock-runtime-packet.v1'",
         f"manifest['schema'] == '{SCHEMA}'"),
        (f"manifest['parent_manifest_sha256'] == '{ACTIVATION_PARENT_SHA}'",
         f"manifest['native_activations_parent_manifest_sha256'] == '{ACTIVATION_PARENT_SHA}'"),
        (f"manifest['extension_sha256s']['ltx_multiblock_compile.py'] == '{ORIGINAL_SHA}'",
         f"manifest['extension_sha256s']['ltx_multiblock_compile.py'] == '{ADAPTER_SHA}'"),
        (f"multi['adapter_sha256'] == '{ORIGINAL_SHA}'", f"multi['adapter_sha256'] == '{ADAPTER_SHA}'"),
    ]
    text = original
    for old, new in changes:
        text = replace_once(text, old, new)
    checks = f'''    # Packet07 retains all06 graphs, lifecycle boundaries and numerical code.
    require(manifest['parent_manifest_sha256'] == {PARENT_SHA!r}, 'Unexpected multiblock06 parent')
    multiblock_parent_path = safe_path(packet, 'multiblock-06-parent-manifest.json')
    require(sha(multiblock_parent_path) == {PARENT_SHA!r}, 'Multiblock06 parent manifest changed')
    multiblock_parent = json.loads(multiblock_parent_path.read_text())
    require(multiblock_parent['schema'] == 'ltx.compiler-multiblock-runtime-packet.v1',
            'Unexpected multiblock parent schema')
    require(manifest['runtime'] == multiblock_parent['runtime'], 'Adjacent-state runtime changed')
    for name, digest in multiblock_parent['files'].items():
        if name in {MODIFIED!r}:
            require(manifest['files']['provenance/adjacent-state-parent/' + name] == digest,
                    'Original multiblock06 source changed: ' + name)
        else:
            require(manifest['files'].get(name) == digest, 'Inherited multiblock06 source changed: ' + name)
    adjacent = manifest['adjacent_state']
    require(adjacent['parent_adapter_sha256'] == {ORIGINAL_SHA!r}
            and adjacent['adapter_sha256'] == {ADAPTER_SHA!r}
            and adjacent['node_sha256'] == {NODE_SHA!r}
            and adjacent['changed_parent_files'] == {list(MODIFIED)!r},
            'Adjacent-state candidate identity changed')
    require(adjacent['bound_state_scans_before'] == 5 and adjacent['bound_state_scans_after'] == 3
            and adjacent['lifecycle_registry_boundaries'] == 3 and adjacent['unbound_state_scans'] == 2,
            'Adjacent-state validation contract changed')
'''
    text = replace_once(text, '    return manifest\n', checks + '    return manifest\n')
    reverse = replace_once(text, checks, '')
    for old, new in reversed(changes):
        reverse = replace_once(reverse, new, old)
    require(ast.dump(ast.parse(reverse)) == ast.dump(ast.parse(original)), 'Inherited checker gates changed')
    return text


def validate_inputs(output):
    require(output.is_absolute() and output.parent == ROOT and
            re.fullmatch(r'prepared-encoder-compiler-[a-z0-9-]+', output.name), 'Use a new compiler packet path')
    require(not output.exists() and not output.is_symlink(), 'Packet exists; never overwrite')
    require(sha(PARENT / 'manifest.json') == PARENT_SHA and
            sha(PARENT / 'launch/encoder_runtime_common.py') == PARENT_CHECKER_SHA, 'Parent packet pins changed')
    common = base.load_checker(PARENT / 'launch/encoder_runtime_common.py', 'adjacent_state_parent_checker')
    common.safe_path(ROOT, output.name)
    parent = common.verify_packet(PARENT, PARENT_SHA)
    common.verify_runtime(parent['runtime'])
    common.verify_model_receipt()
    require(not CANDIDATE.is_symlink() and sha(CANDIDATE) == ADAPTER_SHA, 'Candidate source pin changed')
    original = (PARENT / MODIFIED[1]).read_text()
    candidate = CANDIDATE.read_text()
    require(text_sha(original) == ORIGINAL_SHA, 'Parent adapter source changed')
    require(parent['extension_sha256s']['multiblock_compile_node.py'] == NODE_SHA, 'Parent node changed')
    validate_adapter(original, candidate)
    checker = checker_source((PARENT / MODIFIED[0]).read_text())
    require('torch' not in sys.modules, 'Preparation unexpectedly imported Torch')
    return common, parent, candidate, checker


def prepare(output, *, check_only=False):
    common, parent, candidate, checker = validate_inputs(output)
    checks = {'changed_parent_files': list(MODIFIED), 'adapter_whole_ast_reverses_to_parent': True,
              'all_parent_checker_gates_retained': True, 'node_plugin_graphs_backends_launcher_unchanged': True,
              'arithmetic_kwargs_routing_private_entry_OPTIONS_Dynamo_limits_unchanged': True,
              'native_imported_or_executed': False, 'runtime_admission_attempted': False}
    if check_only:
        return {'status': 'inactive-source-check-passed', 'proposed_packet': str(output),
                'parent_manifest_sha256': PARENT_SHA, 'adapter_sha256': ADAPTER_SHA,
                'node_sha256': NODE_SHA, 'source_checks': checks, 'files_written': 0,
                'builder_sha256': sha(Path(__file__))}
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than5 GiB disk free')
    builder_sha = sha(Path(__file__))
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE adjacent-state packet; do not launch.\n')
    for name in parent['files']:
        source, target = common.safe_path(PARENT, name), common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(PARENT / 'manifest.json', output / 'multiblock-06-parent-manifest.json')
    for name in MODIFIED:
        path = output / 'provenance/adjacent-state-parent' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, path)
    shutil.copyfile(Path(__file__), output / 'provenance' / Path(__file__).name)
    replacements = {MODIFIED[0]: checker, MODIFIED[1]: candidate}
    delta = []
    for name, content in replacements.items():
        (output / name).write_text(content)
        delta.extend(difflib.unified_diff((PARENT / name).read_text().splitlines(keepends=True),
            content.splitlines(keepends=True), fromfile='a/' + name, tofile='b/' + name))
    patch_name = 'multiblock-adjacent-state-runtime.patch'
    (output / 'patches' / patch_name).write_text(''.join(delta))
    common.verify_packet(PARENT, PARENT_SHA)
    require(sha(CANDIDATE) == ADAPTER_SHA and sha(Path(__file__)) == builder_sha and
            sha(_parent_builder) == PARENT_BUILDER_SHA, 'Preparation inputs changed')
    files = base.inventory(output)
    require({name for name, digest in parent['files'].items() if files[name] != digest} == set(MODIFIED),
            'Unexpected inherited file changes')
    write_json(output / 'provenance/adjacent-state-source-checks.json', checks)
    local = base.load_checker(output / MODIFIED[0], 'adjacent_state_packet_checker')
    manifest = copy.deepcopy(parent)
    manifest.update(schema=SCHEMA, parent_packet=str(PARENT), parent_manifest_sha256=PARENT_SHA,
        native_activations_parent_manifest_sha256=parent['parent_manifest_sha256'],
        adjacent_state_preparer_sha256=builder_sha,
        offline_preparation={'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
            'fault_latch_present_at_preparation': (ROOT / 'FAULT.json').exists(),
            'runtime_admission': 'not attempted; source preparation only'},
        startup_tools={name: sha(output / 'launch' / name) for name in parent['startup_tools']},
        extension_sha256s={name: sha(output / 'source/scripts' / name) for name in local.EXTENSIONS})
    manifest['multiblock']['adapter_sha256'] = ADAPTER_SHA
    manifest['multiblock'].update(native_block_xpu_qualified=False, full_clip_qualified=False, speed_qualified=False)
    manifest['adjacent_state'] = {'parent_adapter_sha256': ORIGINAL_SHA, 'adapter_sha256': ADAPTER_SHA,
        'node_sha256': NODE_SHA, 'changed_parent_files': list(MODIFIED),
        'bound_state_scans_before': 5, 'bound_state_scans_after': 3, 'lifecycle_registry_boundaries': 3,
        'unbound_state_scans': 2,
        'scope': 'Reuse only immediately completed bound state checks; retain all three execution boundaries',
        'counts_scope': 'Source control-flow counts, not a measured speed result',
        'native_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False}
    manifest['patch_order'].append(patch_name)
    manifest['patch_sha256s'][patch_name] = sha(output / 'patches' / patch_name)
    manifest['limitations'].extend([
        'Packet07 adds only the adjacent-state candidate; inherited packet06 native results do not qualify this source change.',
        'The node and graph templates stay unchanged; a new pinned client/validator must bind packet07 and adapter79b4e76b.',
        'No guard hoisting across routing/native-gate boundaries, compiler-limit mutation, reload, reset or native execution is performed.'])
    manifest['files'] = base.inventory(output)
    manifest['files'].pop('STATUS.txt')
    write_json(output / 'manifest.json', manifest)
    digest = sha(output / 'manifest.json')
    local.verify_packet(output, digest)
    local.verify_runtime(manifest['runtime'])
    require('torch' not in sys.modules, 'Preparation unexpectedly imported Torch')
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE adjacent-state successor. Native exactness/speed pending.\n')
    return {'status': 'prepared-inactive-not-deployed', 'packet': str(output), 'manifest_sha256': digest,
            'parent_manifest_sha256': PARENT_SHA, 'adapter_sha256': ADAPTER_SHA, 'node_sha256': NODE_SHA,
            'source_checks': checks, 'files': len(manifest['files'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, check_only=args.check_only), indent=2))
