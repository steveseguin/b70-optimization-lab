#!/usr/bin/env python3
"""Seal an inactive one-pass state successor; no native imports or server actions."""
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
PARENT = ROOT / 'prepared-encoder-compiler-07'
PARENT_SHA = 'afdbad186a6873a286f93e9d1e715f6bf4c17e1552d75dbce2a3e03c0a1f35c1'
CHECKER_SHA = '42f76da4f9ac2cba46d8f8b8eeab5c77445f3b3ad9db2e6ead92df9c93cc51ac'
BUILDER_SHA = '6f1a58dc1d04ae30ac28a70583ce18853e9f2d946bf658765d3e5aaa79aeaa3c'
MULTIBLOCK_PARENT_SHA = '3676b1e47b514f5c28597063b42c9806ed13639cc2dde0f3b25fd44564c08394'
ORIGINAL_SHA = '79b4e76b10f49094f3ad11cc70ba62334c2ccf10e50960ac209fb5a0cdd2a584'
ADAPTER_SHA = 'ba89394822e9ec607cc8ec7aad092a3afa7d87e0f723b781cf27f1f6158c031b'
NODE_SHA = 'e7d6e69ff44d5b727dba27f52142647a06afe6d494abb043af49fa132a005d2f'
CANDIDATE = LANE / 'patches/multiblock-onepass-state-04/candidate.py'
SCHEMA = 'ltx.compiler-multiblock-onepass-state-runtime-packet.v1'
MODIFIED = ('launch/encoder_runtime_common.py', 'source/scripts/ltx_multiblock_compile.py')
builder_path = LANE / 'scripts/prepare-adjacent-state-runtime.py'
if hashlib.sha256(builder_path.read_bytes()).hexdigest() != BUILDER_SHA:
    raise RuntimeError('Pinned parent builder changed')
spec = importlib.util.spec_from_file_location('onepass_parent_preparer', builder_path)
parent_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent_builder)
base = parent_builder.base
require, sha, replace_once, write_json = base.require, base.sha, base.replace_once, base.write_json


def validate_adapter(original, candidate):
    require(hashlib.sha256(original.encode()).hexdigest() == ORIGINAL_SHA,
            'Original adapter changed')
    require(hashlib.sha256(candidate.encode()).hexdigest() == ADAPTER_SHA,
            'Reviewed one-pass adapter changed')
    before, after = ast.parse(original), ast.parse(candidate)
    before_class = next(n for n in before.body if isinstance(n, ast.ClassDef) and n.name == 'CompiledBlockRoute')
    after_class = next(n for n in after.body if isinstance(n, ast.ClassDef) and n.name == 'CompiledBlockRoute')
    old = next(n for n in before_class.body if isinstance(n, ast.FunctionDef) and n.name == '_validate')
    indices = [i for i, n in enumerate(after_class.body) if isinstance(n, ast.FunctionDef) and n.name == '_validate']
    require(len(indices) == 1, 'Expected one state validator')
    after_class.body[indices[0]] = old
    require(ast.dump(before) == ast.dump(after), 'Code outside reviewed state traversal changed')


def checker_source(original):
    changes = [
        ("manifest['schema'] == 'ltx.compiler-multiblock-adjacent-state-runtime-packet.v1'",
         f"manifest['schema'] == '{SCHEMA}'"),
        (f"manifest['parent_manifest_sha256'] == '{MULTIBLOCK_PARENT_SHA}'",
         f"manifest['multiblock_parent_manifest_sha256'] == '{MULTIBLOCK_PARENT_SHA}'"),
        (f"manifest['extension_sha256s']['ltx_multiblock_compile.py'] == '{ORIGINAL_SHA}'",
         f"manifest['extension_sha256s']['ltx_multiblock_compile.py'] == '{ADAPTER_SHA}'"),
        (f"multi['adapter_sha256'] == '{ORIGINAL_SHA}'", f"multi['adapter_sha256'] == '{ADAPTER_SHA}'"),
    ]
    text = original
    for old, new in changes:
        text = replace_once(text, old, new)
    checks = f'''    # Current adapter identity is in multiblock/onepass_state; adjacent_state
    # retains the historical packet07 source identity and its provenance gates.
    require(manifest['parent_manifest_sha256'] == {PARENT_SHA!r}, 'Unexpected adjacent-state07 parent')
    onepass_parent_path = safe_path(packet, 'adjacent-state-07-parent-manifest.json')
    require(sha(onepass_parent_path) == {PARENT_SHA!r}, 'Adjacent-state07 parent manifest changed')
    onepass_parent = json.loads(onepass_parent_path.read_text())
    require(onepass_parent['schema'] == 'ltx.compiler-multiblock-adjacent-state-runtime-packet.v1',
            'Unexpected one-pass parent schema')
    require(manifest['runtime'] == onepass_parent['runtime'], 'One-pass runtime changed')
    require(manifest['adjacent_state'] == onepass_parent['adjacent_state'],
            'Historical adjacent-state provenance changed')
    for name, digest in onepass_parent['files'].items():
        if name in {MODIFIED!r}:
            require(manifest['files']['provenance/onepass-state-parent/' + name] == digest,
                    'Original adjacent-state source changed: ' + name)
        else:
            require(manifest['files'].get(name) == digest, 'Inherited packet07 source changed: ' + name)
    onepass = manifest['onepass_state']
    require(onepass['parent_adapter_sha256'] == {ORIGINAL_SHA!r}
            and onepass['adapter_sha256'] == {ADAPTER_SHA!r}
            and onepass['node_sha256'] == {NODE_SHA!r}
            and onepass['changed_parent_files'] == {list(MODIFIED)!r},
            'One-pass candidate identity changed')
    require(onepass['hierarchy_traversals_per_state_check_before'] == 3
            and onepass['hierarchy_traversals_per_state_check_after'] == 1
            and onepass['lifecycle_registry_boundaries'] == 3
            and onepass['cross_call_state_cache'] is False,
            'One-pass validation contract changed')
'''
    text = replace_once(text, '    return manifest\n', checks + '    return manifest\n')
    reverse = replace_once(text, checks, '')
    for old, new in reversed(changes):
        reverse = replace_once(reverse, new, old)
    require(ast.dump(ast.parse(reverse)) == ast.dump(ast.parse(original)), 'Inherited checker gates changed')
    return text


def prepare(output, check_only=False):
    require(output.is_absolute() and output.parent == ROOT and
            re.fullmatch(r'prepared-encoder-compiler-[a-z0-9-]+', output.name), 'Use a new compiler packet path')
    require(not output.exists() and not output.is_symlink(), 'Packet exists; never overwrite')
    require(sha(PARENT / 'manifest.json') == PARENT_SHA and
            sha(PARENT / MODIFIED[0]) == CHECKER_SHA, 'Parent source pins changed')
    common = base.load_checker(PARENT / MODIFIED[0], 'onepass_parent_checker')
    common.safe_path(ROOT, output.name)
    parent = common.verify_packet(PARENT, PARENT_SHA)
    common.verify_runtime(parent['runtime'])
    common.verify_model_receipt()
    require(not CANDIDATE.is_symlink() and sha(CANDIDATE) == ADAPTER_SHA, 'Candidate source changed')
    require(parent['extension_sha256s']['multiblock_compile_node.py'] == NODE_SHA, 'Native gate node changed')
    candidate = CANDIDATE.read_text()
    validate_adapter((PARENT / MODIFIED[1]).read_text(), candidate)
    checker = checker_source((PARENT / MODIFIED[0]).read_text())
    checks = {'only_state_validator_method_changed': True, 'all_parent_checker_gates_retained': True,
              'changed_parent_files': list(MODIFIED), 'node_graphs_backends_launcher_unchanged': True,
              'arithmetic_routing_private_entry_OPTIONS_Dynamo_limits_unchanged': True,
              'native_imported_or_executed': False, 'runtime_admission_attempted': False}
    require('torch' not in sys.modules, 'Preparation unexpectedly imported Torch')
    if check_only:
        return {'status': 'inactive-source-check-passed', 'files_written': 0,
                'proposed_packet': str(output), 'parent_manifest_sha256': PARENT_SHA,
                'adapter_sha256': ADAPTER_SHA, 'source_checks': checks, 'builder_sha256': sha(Path(__file__))}
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than 5 GiB disk free')
    builder_sha = sha(Path(__file__))
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE one-pass packet; do not launch.\n')
    for name in parent['files']:
        source, target = common.safe_path(PARENT, name), common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(PARENT / 'manifest.json', output / 'adjacent-state-07-parent-manifest.json')
    for name in MODIFIED:
        path = output / 'provenance/onepass-state-parent' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, path)
    shutil.copyfile(Path(__file__), output / 'provenance' / Path(__file__).name)
    delta = []
    for name, content in {MODIFIED[0]: checker, MODIFIED[1]: candidate}.items():
        (output / name).write_text(content)
        delta.extend(difflib.unified_diff((PARENT / name).read_text().splitlines(keepends=True),
            content.splitlines(keepends=True), fromfile='a/' + name, tofile='b/' + name))
    patch_name = 'multiblock-onepass-state-runtime.patch'
    (output / 'patches' / patch_name).write_text(''.join(delta))
    common.verify_packet(PARENT, PARENT_SHA)
    require(sha(CANDIDATE) == ADAPTER_SHA and sha(Path(__file__)) == builder_sha and
            sha(builder_path) == BUILDER_SHA, 'Preparation inputs changed')
    files = base.inventory(output)
    require({name for name, digest in parent['files'].items() if files[name] != digest} == set(MODIFIED),
            'Unexpected inherited file changes')
    write_json(output / 'provenance/onepass-state-source-checks.json', checks)
    local = base.load_checker(output / MODIFIED[0], 'onepass_packet_checker')
    manifest = copy.deepcopy(parent)
    manifest.update(schema=SCHEMA, parent_packet=str(PARENT), parent_manifest_sha256=PARENT_SHA,
        multiblock_parent_manifest_sha256=parent['parent_manifest_sha256'],
        onepass_state_preparer_sha256=builder_sha,
        offline_preparation={'model_verification_sha256': common.MODEL_VERIFICATION_SHA256,
            'fault_latch_present_at_preparation': (ROOT / 'FAULT.json').exists(),
            'runtime_admission': 'not attempted; source preparation only'},
        startup_tools={name: sha(output / 'launch' / name) for name in parent['startup_tools']},
        extension_sha256s={name: sha(output / 'source/scripts' / name) for name in local.EXTENSIONS})
    manifest['multiblock'].update(adapter_sha256=ADAPTER_SHA, native_block_xpu_qualified=False,
                                   full_clip_qualified=False, speed_qualified=False)
    manifest['onepass_state'] = {'parent_adapter_sha256': ORIGINAL_SHA, 'adapter_sha256': ADAPTER_SHA,
        'node_sha256': NODE_SHA, 'changed_parent_files': list(MODIFIED),
        'hierarchy_traversals_per_state_check_before': 3, 'hierarchy_traversals_per_state_check_after': 1,
        'lifecycle_registry_boundaries': 3, 'cross_call_state_cache': False,
        'scope': 'Same current-state acceptance checks in one module traversal; first error can differ for simultaneous violations',
        'native_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False}
    manifest['patch_order'].append(patch_name)
    manifest['patch_sha256s'][patch_name] = sha(output / 'patches' / patch_name)
    manifest['limitations'].extend([
        'Packet08 changes only one-pass traversal; previous packet native results do not qualify this source change.',
        'adjacent_state retains historical07 identity; current adapter identity is in multiblock/onepass_state.',
        'No native execution, reload, reset, numerical operation or cross-call validation cache during preparation.'])
    manifest['files'] = base.inventory(output)
    manifest['files'].pop('STATUS.txt')
    write_json(output / 'manifest.json', manifest)
    digest = sha(output / 'manifest.json')
    local.verify_packet(output, digest)
    local.verify_runtime(manifest['runtime'])
    require('torch' not in sys.modules, 'Preparation unexpectedly imported Torch')
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE one-pass successor. Native exactness/speed pending.\n')
    return {'status': 'prepared-inactive-not-deployed', 'packet': str(output), 'manifest_sha256': digest,
            'parent_manifest_sha256': PARENT_SHA, 'adapter_sha256': ADAPTER_SHA,
            'node_sha256': NODE_SHA, 'source_checks': checks, 'files': len(manifest['files'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.check_only), indent=2))
