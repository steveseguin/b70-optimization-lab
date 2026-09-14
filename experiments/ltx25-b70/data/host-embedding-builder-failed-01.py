#!/usr/bin/env python3
"""Prepare an inactive CPU-table encoder successor using reviewed CPU receipts.

No native imports, application changes, or requests. Missing/failed admission
receipts refuse even --check-only; all caller-supplied hashes must be reviewed.
"""
import argparse
import ast
import copy
import difflib
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
import re
import shutil
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-encoder-na-axis-10'
PARENT_SHA = 'd6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a'
NA_PARENT_SHA = 'a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b'
OUTPUT = ROOT / 'prepared-encoder-host-embedding-11'
CHECKER = 'launch/encoder_runtime_common.py'
SCHEMA = 'ltx.host-embedding-runtime-packet.v1'
INPUTS = {
    'ltx_host_embedding_candidate.py': 'scripts/ltx_host_embedding_candidate.py',
    'host_embedding_clip.py': 'scripts/host_embedding_clip_v2.py',
    'host_embedding_placement_node.py': 'scripts/host_embedding_placement_node_v2.py',
    'host_embedding_resident_node.py': 'scripts/host_embedding_resident_node.py',
}
CPU_DRIVER = 'scripts/test-host-embedding-integration-cpu.py'
RESIDENT_TEST = 'scripts/test-host-embedding-resident-stdlib.py'
PROVENANCE = 'provenance/host-embedding'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def regular(path):
    path = Path(path)
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
            'Missing/linked source or evidence: ' + str(path))
    return path


def digest(value):
    require(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value), 'Explicit SHA256 required')
    return value


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_once(text, before, after):
    require(text.count(before) == 1, 'Expected unique checker context: ' + before)
    return text.replace(before, after, 1)


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def graph_source(control, mode):
    require(mode in ('control', 'host-table'), 'Unknown encoder mode')
    graph = copy.deepcopy(control)
    require(graph['420'] == {'class_type': 'LTXResidentComponents',
            'inputs': {'placement': 'split', 'encoder_variant': 'control'}}, 'Original component graph differs')
    require(graph['421']['class_type'] == 'LTXEncoderPlacementCheck'
            and graph['421']['inputs']['encoder_variant'] == 'control', 'Original placement graph differs')
    graph['420']['class_type'] = 'LTXHostEmbeddingComponents'
    graph['421']['class_type'] = 'LTXHostEmbeddingPlacementCheck'
    for name in ('420', '421'):
        del graph[name]['inputs']['encoder_variant']
        graph[name]['inputs']['encoder_mode'] = mode
    return graph


def validate_admissions(cpu, resident, source_hashes):
    require(cpu['schema'] == 'ltx.host-embedding-integration-guarded-cpu.v1'
            and cpu['status'] == 'passed-guarded-cpu-integration'
            and cpu['phase'] == 'finished' and cpu['tests_run'] == 6
            and cpu['native_cpu_tests_executed'] is True and cpu['torch_imported'] is True,
            'Reviewed actual CPU integration pass required')
    require(cpu['xpu_initialized'] is False and cpu['cuda_initialized'] is False
            and cpu['final_guards_intact'] is True and cpu['native_gpu_requests'] == 0
            and cpu['compilation_permitted'] is False,
            'CPU integration accelerator/guard boundaries differ')
    require(not cpu['test_failures'] and not cpu['test_errors'] and not cpu['test_skips']
            and len(cpu['test_names']) == len(set(cpu['test_names'])) == 6,
            'Incomplete CPU integration test result')
    require(cpu['determinism'] == {'enabled': True, 'warn_only': False}, 'CPU deterministic gate differs')
    require(cpu['accelerator_guard_attempts'] == [] and cpu['backend_refusals']['attempts'] == []
            and cpu['backend_refusals']['tripped'] is False, 'CPU forbidden native attempt recorded')
    omissions = cpu['cpu_comfy_import_omissions']
    require(len(omissions) == 1 and omissions[0]['ordinal'] == 1
            and omissions[0]['args_cpu'] is True and omissions[0]['caller_function'] == '<module>'
            and omissions[0]['source_sha256'] == cpu['comfy_model_management_sha256']
            and cpu['cpu_comfy_import_policy']['complete'] is True,
            'CPU import refusal boundary incomplete')
    for stage in ('identity_after_import', 'identity_after_tests'):
        require(cpu[stage] == {'guards_intact': True, 'xpu_initialized': False, 'cuda_initialized': False},
                'CPU identity boundary differs: ' + stage)
    for canonical, filename in (
            ('ltx_host_embedding_candidate.py', 'scripts/ltx_host_embedding_candidate.py'),
            ('host_embedding_clip.py', 'scripts/host_embedding_clip_v2.py'),
            ('host_embedding_placement_node.py', 'scripts/host_embedding_placement_node_v2.py')):
        require(cpu['helper_sha256s'][filename] == source_hashes[canonical],
                'CPU integration did not test this added source: ' + canonical)
    require(resident['schema'] == 'ltx.host-embedding-resident-stdlib.v1'
            and resident['status'] == 'passed-source-only-assembly' and resident['tests_run'] == 9
            and resident['native_imports'] is False and resident['gpu_actions'] == 0
            and resident['runtime_requests'] == 0, 'Resident nine-test source admission required')
    require(resident['source_sha256s']['experiments/ltx25-b70/scripts/host_embedding_resident_node.py']
            == source_hashes['host_embedding_resident_node.py'], 'Resident admission source differs')


def checker_source(original, admission):
    changes = [
        ('import ast\n', 'import ast\nimport copy\n'),
        ("manifest['schema'] == 'ltx.na-axis-runtime-packet.v2'", f"manifest['schema'] == {SCHEMA!r}"),
        (f"manifest['parent_manifest_sha256'] == {NA_PARENT_SHA!r}",
         f"manifest['na_axis_parent_manifest_sha256'] == {NA_PARENT_SHA!r}"),
        ("'ltx_na_axis_router.py', 'ltx_na_axis_candidate.py', 'na_axis_decode_node.py')",
         "'ltx_na_axis_router.py', 'ltx_na_axis_candidate.py', 'na_axis_decode_node.py',\n"
         "              'ltx_host_embedding_candidate.py', 'host_embedding_clip.py',\n"
         "              'host_embedding_placement_node.py', 'host_embedding_resident_node.py')"),
        ("'ltx_na_axis_decode_lab': 'na_axis_decode_node.py'}",
         "'ltx_na_axis_decode_lab': 'na_axis_decode_node.py',\n"
         "         'ltx_host_embedding_lab': 'host_embedding_resident_node.py'}"),
    ]
    text = original
    for before, after in changes:
        text = replace_once(text, before, after)
    checks = f'''    # All packet10 numerical bytes, graphs, and NA closure remain inherited.
    require(manifest['parent_manifest_sha256'] == {PARENT_SHA!r}, 'Unexpected packet10 parent')
    host_parent_path = safe_path(packet, 'na-axis-10-parent-manifest.json')
    require(sha(host_parent_path) == {PARENT_SHA!r}, 'Packet10 parent manifest changed')
    host_parent = json.loads(host_parent_path.read_text())
    require(host_parent['schema'] == 'ltx.na-axis-runtime-packet.v2', 'Unexpected packet10 schema')
    require(manifest['runtime'] == host_parent['runtime'], 'Host embedding runtime changed')
    require(manifest['na_axis'] == host_parent['na_axis']
            and manifest['na_axis_correction'] == host_parent['na_axis_correction'], 'Inherited NA scope changed')
    for name, expected in host_parent['files'].items():
        target = {PROVENANCE!r} + '/parent/' + name if name == {CHECKER!r} else name
        require(manifest['files'].get(target) == expected, 'Inherited packet10 bytes changed: ' + name)
    host = manifest['host_embedding']
    require(host == {admission!r}, 'Host embedding admission/scope changed')
    for name, expected in host['extension_sha256s'].items():
        require(manifest['extension_sha256s'][name] == expected, 'Added extension pin differs: ' + name)
    receipts = {{}}
    for kind, row in host['admissions'].items():
        require(sha(safe_path(packet, row['path'])) == row['sha256'], 'Admission receipt changed: ' + kind)
        receipts[kind] = json.loads(safe_path(packet, row['path']).read_text())
    validate_admissions(receipts['cpu_integration'], receipts['resident_assembly'], host['extension_sha256s'])
    for name, expected in host['proof_source_sha256s'].items():
        require(sha(safe_path(packet, name)) == expected, 'Admission proof source changed: ' + name)
    for name, expected in host['cpu_actual_source_sha256s'].items():
        require(sha(safe_path(packet, 'source/' + name)) == expected, 'CPU actual source closure differs: ' + name)
    host_control = json.loads(safe_path(packet, 'graphs/control.json').read_text())
    for mode in ('control', 'host-table'):
        graph = json.loads(safe_path(packet, 'graphs/host-embedding-' + mode + '.json').read_text())
        require(graph == graph_source(host_control, mode), 'Host graph differs beyond nodes420/421')
'''
    text = replace_once(text, '    return manifest\n', checks + '    return manifest\n')
    helpers = '\n\n' + inspect.getsource(graph_source) + '\n\n' + inspect.getsource(validate_admissions) + '\n'
    text = replace_once(text, '\ndef verify_packet(', helpers + '\ndef verify_packet(')
    reverse = replace_once(replace_once(text, helpers, ''), checks, '')
    for before, after in reversed(changes):
        reverse = replace_once(reverse, after, before)
    require(reverse == original, 'Inherited checker does not reverse byte-for-byte')
    ast.parse(text)
    return text


def prepare(output, source_hashes, cpu_receipt, cpu_sha, resident_receipt, resident_sha, check_only=False):
    require(output == OUTPUT and not output.exists() and not output.is_symlink(), 'Require absent packet11 directory')
    require(set(source_hashes) == set(INPUTS), 'Require exact four added-source hashes')
    for canonical, source in INPUTS.items():
        require(sha(regular(LANE / source)) == digest(source_hashes[canonical]), 'Unreviewed added source: ' + source)
        ast.parse((LANE / source).read_text())
    require(sha(regular(PARENT / 'manifest.json')) == PARENT_SHA, 'Parent10 manifest changed')
    parent = json.loads((PARENT / 'manifest.json').read_text())
    require(sha(regular(PARENT / CHECKER)) == parent['files'][CHECKER], 'Parent10 checker changed')
    common = load(PARENT / CHECKER, 'host_parent10_common')
    common.safe_path(ROOT, output.name)
    common.verify_packet(PARENT, PARENT_SHA)
    common.verify_runtime(parent['runtime'])
    common.verify_model_receipt()
    proofs = {}
    def add_proof(name, path, expected):
        require(name not in proofs, 'Duplicate proof target')
        common.safe_path(ROOT, name)
        require(sha(regular(path)) == digest(expected), 'Unreviewed proof bytes: ' + str(path))
        proofs[name] = (Path(path), expected)
    add_proof(PROVENANCE + '/cpu-integration-result.json', cpu_receipt, cpu_sha)
    add_proof(PROVENANCE + '/resident-assembly-result.json', resident_receipt, resident_sha)
    cpu = json.loads(Path(cpu_receipt).read_text())
    resident = json.loads(Path(resident_receipt).read_text())
    validate_admissions(cpu, resident, source_hashes)
    add_proof(PROVENANCE + '/cpu-startup-identity.json', Path(cpu_receipt).parent / 'startup-identity.json', cpu['startup_sha256'])
    for name, expected in cpu['helper_sha256s'].items():
        common.safe_path(LANE, name)
        add_proof(PROVENANCE + '/cpu-sources/' + name, LANE / name, expected)
    add_proof(PROVENANCE + '/cpu-sources/' + CPU_DRIVER, LANE / CPU_DRIVER, cpu['driver_sha256'])
    test_key = 'experiments/ltx25-b70/' + RESIDENT_TEST
    add_proof(PROVENANCE + '/resident-sources/' + RESIDENT_TEST, LANE / RESIDENT_TEST, resident['source_sha256s'][test_key])
    parent_resident_key = str(PARENT / 'source/scripts/resident_node.py')
    require(resident['source_sha256s'][parent_resident_key] == parent['files']['source/scripts/resident_node.py'],
            'Resident admission parent source differs')
    actual_sources = dict(cpu['source_pins'])
    actual_sources['comfy/model_management.py'] = cpu['comfy_model_management_sha256']
    require('comfy/sd.py' in actual_sources and 'comfy/model_patcher.py' in actual_sources
            and 'scripts/encoder_diagnostics.py' in actual_sources, 'Incomplete actual CLIP source closure')
    for name, expected in actual_sources.items():
        require(parent['files']['source/' + name] == expected, 'CPU admission inherited source differs: ' + name)
    admission = {'modes': ['control', 'host-table'], 'component_node_class': 'LTXHostEmbeddingComponents',
        'placement_node_class': 'LTXHostEmbeddingPlacementCheck', 'extension_sha256s': source_hashes,
        'graphs': ['graphs/host-embedding-control.json', 'graphs/host-embedding-host-table.json'],
        'transformer_dispatch': 'original', 'reserve_override': False, 'force_full_load': False,
        'construction_device': 'cpu', 'encoder_load_device': 'xpu:2', 'table_device': 'cpu',
        'cache_scope': 'one-shared-component-generation', 'prompt_encoding_cache': False,
        'generated_output_cache': False, 'native_gpu_qualified': False, 'full_clip_qualified': False,
        'speed_qualified': False,
        'admissions': {'cpu_integration': {'path': PROVENANCE + '/cpu-integration-result.json', 'sha256': cpu_sha},
                       'resident_assembly': {'path': PROVENANCE + '/resident-assembly-result.json', 'sha256': resident_sha}},
        'proof_source_sha256s': {name: expected for name, (_, expected) in proofs.items()},
        'cpu_actual_source_sha256s': actual_sources}
    checker = checker_source((PARENT / CHECKER).read_text(), admission)
    control = json.loads((PARENT / 'graphs/control.json').read_text())
    graphs = {mode: graph_source(control, mode) for mode in ('control', 'host-table')}
    checks = {'inherited_checker_reverses_byte_for_byte': True, 'only_modified_parent_file': CHECKER,
        'all_parent_numerical_sources_unchanged': True, 'launcher_inherited_unchanged': True,
        'graphs_change_only_nodes420_421': True, 'new_custom_node_directories': ['ltx_host_embedding_lab'],
        'torch_imported': 'torch' in sys.modules, 'native_admission': False}
    require(not checks['torch_imported'], 'Source preparation imported Torch')
    if check_only:
        return {'status': 'inactive-source-check-passed', 'files_written': 0,
                'builder_sha256': sha(Path(__file__)), 'host_embedding': admission, 'source_checks': checks}
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than 5GiB disk free')
    builder_sha = sha(Path(__file__))
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE host embedding packet; do not launch.\n')
    for name in parent['files']:
        target = common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, target)
    shutil.copyfile(PARENT / 'manifest.json', output / 'na-axis-10-parent-manifest.json')
    provenance = output / PROVENANCE
    (provenance / 'parent/launch').mkdir(parents=True)
    shutil.copyfile(PARENT / CHECKER, provenance / 'parent' / CHECKER)
    shutil.copyfile(Path(__file__), provenance / Path(__file__).name)
    for name, (path, _) in proofs.items():
        target = common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (output / CHECKER).write_text(checker)
    for name, source in INPUTS.items():
        target = output / 'source/scripts' / name
        require(not target.exists(), 'Added extension collides with inherited source')
        shutil.copyfile(LANE / source, target)
    node = output / 'source/custom_nodes/ltx_host_embedding_lab/__init__.py'
    node.parent.mkdir()
    shutil.copyfile(LANE / INPUTS['host_embedding_resident_node.py'], node)
    for mode, graph in graphs.items():
        write_json(output / ('graphs/host-embedding-' + mode + '.json'), graph)
    patch_name = 'host-embedding-runtime.patch'
    (output / 'patches' / patch_name).write_text(''.join(difflib.unified_diff(
        (PARENT / CHECKER).read_text().splitlines(True), checker.splitlines(True),
        fromfile='a/' + CHECKER, tofile='b/' + CHECKER)))
    write_json(provenance / 'source-checks.json', checks)
    local = load(output / CHECKER, 'host_packet11_common')
    manifest = copy.deepcopy(parent)
    manifest.update(schema=SCHEMA, parent_packet=str(PARENT), parent_manifest_sha256=PARENT_SHA,
        na_axis_parent_manifest_sha256=parent['parent_manifest_sha256'], host_embedding_preparer_sha256=builder_sha,
        startup_tools={name: sha(output / 'launch' / name) for name in parent['startup_tools']},
        extension_sha256s={name: sha(output / 'source/scripts' / name) for name in local.EXTENSIONS},
        host_embedding=admission)
    manifest['patch_order'].append(patch_name)
    manifest['patch_sha256s'][patch_name] = sha(output / 'patches' / patch_name)
    manifest['limitations'].append('CPU integration and source assembly receipts do not qualify accelerator exactness, full encoder residency, full clips, or speed. Packet10 NA and original transformer paths retained.')
    common.verify_packet(PARENT, PARENT_SHA)
    require(sha(Path(__file__)) == builder_sha, 'Builder changed during preparation')
    for canonical, source in INPUTS.items():
        require(sha(LANE / source) == source_hashes[canonical], 'Added source changed during preparation')
    for path, expected in proofs.values():
        require(sha(path) == expected, 'Admission proof changed during preparation')
    files = {str(p.relative_to(output)): sha(p) for p in output.rglob('*') if p.is_file() and p.name != 'STATUS.txt'}
    require({name for name, expected in parent['files'].items() if files[name] != expected} == {CHECKER},
            'Unexpected inherited file change')
    manifest['files'] = files
    write_json(output / 'manifest.json', manifest)
    manifest_sha = sha(output / 'manifest.json')
    local.verify_packet(output, manifest_sha)
    local.verify_runtime(manifest['runtime'])
    require('torch' not in sys.modules, 'Source preparation imported Torch')
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE host embedding. Accelerator exactness/residency/speed pending.\n')
    return {'status': 'prepared-inactive-not-deployed', 'packet': str(output),
            'manifest_sha256': manifest_sha, 'files': len(files), 'source_checks': checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-sha256s', type=json.loads, required=True, help='Reviewed JSON map of four canonical extension names to SHA256')
    parser.add_argument('--cpu-receipt', type=Path, required=True)
    parser.add_argument('--cpu-receipt-sha256', required=True)
    parser.add_argument('--resident-receipt', type=Path, required=True)
    parser.add_argument('--resident-receipt-sha256', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.source_sha256s, args.cpu_receipt, args.cpu_receipt_sha256,
        args.resident_receipt, args.resident_receipt_sha256, args.check_only), indent=2))
