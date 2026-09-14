#!/usr/bin/env python3
"""Prepare packet12 with the qualified CLIP-only retirement lifecycle.

No native imports, endpoints or application actions. Preserve every packet11
byte except the reviewed checker/resident/custom-node replacements as evidence.
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
import shutil
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-encoder-host-embedding-11'
PARENT_SHA = '34b7ff2f7a74b6951f87dd2621738b37930d15a5de9d064409c8b12351adcf08'
OUTPUT = ROOT / 'prepared-encoder-host-embedding-12'
SCHEMA = 'ltx.host-embedding-runtime-packet.v2'
PROVENANCE = 'provenance/host-transition'
CHECKER = 'launch/encoder_runtime_common.py'
RESIDENT = 'source/scripts/host_embedding_resident_node.py'
NODE = 'source/custom_nodes/ltx_host_embedding_lab/__init__.py'
CHANGED = (CHECKER, RESIDENT, NODE)
INPUTS = {
    'host_embedding_resident_node.py': ('scripts/host_embedding_resident_node_v2.py', 'bdaa14a06bd9937946eee470e562f6109df239273e905197d6e94fad28dd02f7'),
    'host_embedding_transition_memory.py': ('scripts/host_embedding_transition_memory.py', '707de7176a47a26063b7282fc7368818d3362b1bd917c76141d58ed00dfcdb86'),
}
CPU = ROOT / 'host-embedding-cpu-resident-lifecycle-native-01/result.json'
CPU_SHA = 'c9c2d81db33ab5d3174aaaaa87a31c6cf03e5d7923f1b9c305bae554e51ea452'
DRIVER = 'scripts/test-host-embedding-resident-lifecycle-cpu.py'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def regular(path):
    path = Path(path)
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), 'Missing/linked proof: ' + str(path))
    return path


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def replace_once(text, before, after):
    require(text.count(before) == 1, 'Expected unique checker context: ' + before)
    return text.replace(before, after, 1)


def validate_lifecycle(cpu, host):
    require(cpu['schema'] == 'ltx.host-embedding-resident-lifecycle-guarded-cpu.v1'
            and cpu['status'] == 'passed-guarded-cpu-resident-lifecycle'
            and cpu['phase'] == 'finished' and cpu['tests_run'] == 6
            and cpu['native_cpu_tests_executed'] is True and cpu['torch_imported'] is True,
            'Actual CPU resident lifecycle pass required')
    require(cpu['xpu_initialized'] is False and cpu['cuda_initialized'] is False
            and cpu['final_guards_intact'] is True and cpu['native_gpu_requests'] == 0
            and cpu['compilation_permitted'] is False, 'CPU guard boundary changed')
    require(not cpu['test_failures'] and not cpu['test_errors'] and not cpu['test_skips'], 'Incomplete CPU lifecycle result')
    require(cpu['test_names'] == sorted([
        'test_actual_control_host_control_registry_death_and_exactness',
        'test_construction_memory_refusal_after_actual_owner_death',
        'test_external_actual_clone_refuses_replacement',
        'test_external_actual_model_refuses_replacement',
        'test_external_output_tuple_refuses_replacement',
        'test_restore_memory_refusal_before_retirement']), 'Wrong lifecycle coverage')
    require(cpu['determinism'] == {'enabled': True, 'warn_only': False}, 'Deterministic mode changed')
    require(cpu['accelerator_guard_attempts'] == [] and cpu['backend_refusals']['attempts'] == []
            and cpu['backend_refusals']['tripped'] is False, 'Forbidden native attempt recorded')
    omissions = cpu['cpu_comfy_import_omissions']
    require(len(omissions) == 1 and omissions[0]['ordinal'] == 1 and omissions[0]['args_cpu'] is True
            and omissions[0]['caller_function'] == '<module>'
            and omissions[0]['source_sha256'] == cpu['comfy_model_management_sha256']
            and cpu['cpu_comfy_import_policy']['complete'] is True, 'CPU import boundary incomplete')
    for stage in ('identity_after_import', 'identity_after_tests'):
        require(cpu[stage] == {'guards_intact': True, 'xpu_initialized': False, 'cuda_initialized': False}, 'CPU identity differs: ' + stage)
    for canonical, source in (
            ('host_embedding_resident_node.py', 'scripts/host_embedding_resident_node_v2.py'),
            ('host_embedding_transition_memory.py', 'scripts/host_embedding_transition_memory.py'),
            ('host_embedding_clip.py', 'scripts/host_embedding_clip_v2.py'),
            ('host_embedding_placement_node.py', 'scripts/host_embedding_placement_node_v2.py'),
            ('ltx_host_embedding_candidate.py', 'scripts/ltx_host_embedding_candidate.py')):
        require(cpu['helper_sha256s'][source] == host['extension_sha256s'][canonical], 'Lifecycle source differs: ' + canonical)
    require(cpu['integration_cpu_receipt_sha256'] == host['admissions']['cpu_integration']['sha256'], 'Original integration proof differs')


def checker_source(original, host):
    changes = [
        ("manifest['schema'] == 'ltx.host-embedding-runtime-packet.v1'", f"manifest['schema'] == {SCHEMA!r}"),
        ("'host_embedding_placement_node.py', 'host_embedding_resident_node.py')",
         "'host_embedding_placement_node.py', 'host_embedding_resident_node.py',\n              'host_embedding_transition_memory.py')"),
        ("manifest['parent_manifest_sha256'] == 'd6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a'",
         "manifest['host_embedding_parent_manifest_sha256'] == 'd6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a'"),
        ("host = manifest['host_embedding']", "host = manifest['host_embedding_parent11']"),
        ("require(manifest['extension_sha256s'][name] == expected, 'Added extension pin differs: ' + name)",
         "require((manifest['files']['provenance/host-transition/parent/source/scripts/' + name]\n"
         "                 if name == 'host_embedding_resident_node.py' else manifest['extension_sha256s'][name])\n"
         "                == expected, 'Historical packet11 extension pin differs: ' + name)"),
    ]
    text = original
    for before, after in changes:
        text = replace_once(text, before, after)
    checks = f'''    # Parent11 numerical sources/graphs remain byte-identical. The old
    # resident/checker are provenance only; current lifecycle proof is separate.
    require(manifest['parent_manifest_sha256'] == {PARENT_SHA!r}, 'Unexpected packet11 parent')
    transition_parent_path = safe_path(packet, 'host-embedding-11-parent-manifest.json')
    require(sha(transition_parent_path) == {PARENT_SHA!r}, 'Packet11 parent manifest changed')
    transition_parent = json.loads(transition_parent_path.read_text())
    require(manifest['runtime'] == transition_parent['runtime'], 'Transition runtime changed')
    require(manifest['host_embedding_parent11'] == transition_parent['host_embedding'], 'Historical host admission changed')
    for name, expected in transition_parent['files'].items():
        destination = {PROVENANCE!r} + '/parent/' + name if name in {CHANGED!r} else name
        require(manifest['files'].get(destination) == expected, 'Inherited packet11 bytes changed: ' + name)
    transition = manifest['host_embedding']
    require(transition == {host!r}, 'Current lifecycle admission changed')
    for name, expected in transition['extension_sha256s'].items():
        require(manifest['extension_sha256s'][name] == expected, 'Current lifecycle extension differs: ' + name)
    for name, expected in transition['proof_source_sha256s'].items():
        require(sha(safe_path(packet, name)) == expected, 'Current lifecycle proof differs: ' + name)
    row = transition['admissions']['resident_lifecycle']
    cpu = json.loads(safe_path(packet, row['path']).read_text())
    require(sha(safe_path(packet, row['path'])) == row['sha256'], 'Lifecycle receipt changed')
    validate_lifecycle(cpu, transition)
    require(sha(safe_path(packet, {PROVENANCE!r} + '/fixture-evidence.json')) == cpu['fixture_evidence_sha256'], 'Native lifecycle evidence changed')
    for name, expected in cpu['source_pins'].items():
        require(manifest['files']['source/' + name] == expected, 'Lifecycle actual source differs: ' + name)
    require(manifest['files']['source/comfy/model_management.py'] == cpu['comfy_model_management_sha256'], 'Lifecycle model manager differs')
'''
    text = replace_once(text, '    return manifest\n', checks + '    return manifest\n')
    helper = '\n\n' + inspect.getsource(validate_lifecycle) + '\n'
    text = replace_once(text, '\ndef verify_packet(', helper + '\ndef verify_packet(')
    reverse = replace_once(replace_once(text, helper, ''), checks, '')
    for before, after in reversed(changes):
        reverse = replace_once(reverse, after, before)
    require(reverse == original, 'Parent checker does not reverse byte-for-byte')
    ast.parse(text)
    return text


def prepare(check_only=False):
    require(not OUTPUT.exists() and not OUTPUT.is_symlink(), 'Packet12 must not already exist')
    require(sha(regular(PARENT / 'manifest.json')) == PARENT_SHA, 'Parent11 manifest changed')
    parent = json.loads((PARENT / 'manifest.json').read_text())
    require(sha(regular(PARENT / CHECKER)) == parent['files'][CHECKER], 'Parent checker changed')
    common = load(PARENT / CHECKER, 'host_transition_parent11')
    common.verify_packet(PARENT, PARENT_SHA)
    common.verify_runtime(parent['runtime'])
    common.verify_model_receipt()
    for filename, expected in INPUTS.values():
        require(sha(regular(LANE / filename)) == expected, 'Qualified successor source changed')
    require(sha(regular(CPU)) == CPU_SHA, 'Actual CPU qualification changed')
    cpu = json.loads(CPU.read_text())
    proofs = {}
    def add(name, source, expected):
        common.safe_path(ROOT, name)
        require(name not in proofs and sha(regular(source)) == expected, 'Proof source changed: ' + str(source))
        proofs[name] = (Path(source), expected)
    add(PROVENANCE + '/cpu-lifecycle-result.json', CPU, CPU_SHA)
    add(PROVENANCE + '/cpu-startup-identity.json', CPU.parent / 'startup-identity.json', cpu['startup_sha256'])
    add(PROVENANCE + '/fixture-evidence.json', CPU.parent / 'fixture-evidence.json', cpu['fixture_evidence_sha256'])
    add(PROVENANCE + '/cpu-sources/' + DRIVER, LANE / DRIVER, cpu['driver_sha256'])
    for name, expected in cpu['helper_sha256s'].items():
        common.safe_path(LANE, name)
        add(PROVENANCE + '/cpu-sources/' + name, LANE / name, expected)
    host = copy.deepcopy(parent['host_embedding'])
    host['extension_sha256s'].update({name: row[1] for name, row in INPUTS.items()})
    host.update(component_receipt_schema='ltx.host-embedding-components.v2',
        cache_scope='nonencoder-components-retained; encoder-replaced',
        native_cpu_resident_lifecycle_qualified=True)
    host['admissions']['resident_lifecycle'] = {'path': PROVENANCE + '/cpu-lifecycle-result.json', 'sha256': CPU_SHA}
    host['proof_source_sha256s'].update({name: row[1] for name, row in proofs.items()})
    validate_lifecycle(cpu, host)
    for name, expected in {**cpu['source_pins'], 'comfy/model_management.py': cpu['comfy_model_management_sha256']}.items():
        require(parent['files']['source/' + name] == expected, 'CPU qualified source differs from parent: ' + name)
    checker = checker_source((PARENT / CHECKER).read_text(), host)
    checks = {'inherited_checker_reverses_byte_for_byte': True, 'changed_parent_files': list(CHANGED),
              'all_parent_numerical_sources_and_graphs_unchanged': True, 'launcher_inherited_unchanged': True,
              'torch_imported': 'torch' in sys.modules, 'native_admission': False,
              'cold_assembly_ram_gate': 'Separate client admission required before first model initialization'}
    require(not checks['torch_imported'], 'Source preparation imported Torch')
    if check_only:
        return {'status': 'inactive-source-check-passed', 'files_written': 0,
                'builder_sha256': sha(Path(__file__)), 'host_embedding': host, 'source_checks': checks}
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than5GiB disk free')
    builder_sha = sha(Path(__file__))
    OUTPUT.mkdir()
    (OUTPUT / 'STATUS.txt').write_text('INCOMPLETE lifecycle packet; do not launch.\n')
    for name in parent['files']:
        target = common.safe_path(OUTPUT, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, target)
    shutil.copyfile(PARENT / 'manifest.json', OUTPUT / 'host-embedding-11-parent-manifest.json')
    for name in CHANGED:
        target = OUTPUT / PROVENANCE / 'parent' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, target)
    shutil.copyfile(Path(__file__), OUTPUT / PROVENANCE / Path(__file__).name)
    for name, (source, _) in proofs.items():
        target = common.safe_path(OUTPUT, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (OUTPUT / CHECKER).write_text(checker)
    for canonical, (source, _) in INPUTS.items():
        shutil.copyfile(LANE / source, OUTPUT / 'source/scripts' / canonical)
    shutil.copyfile(LANE / INPUTS['host_embedding_resident_node.py'][0], OUTPUT / NODE)
    patch_name = 'host-transition-runtime.patch'
    patch = ''.join(''.join(difflib.unified_diff((PARENT / name).read_text().splitlines(True),
        (OUTPUT / name).read_text().splitlines(True), fromfile='a/' + name, tofile='b/' + name)) for name in CHANGED)
    (OUTPUT / 'patches' / patch_name).write_text(patch)
    write_json(OUTPUT / PROVENANCE / 'source-checks.json', checks)
    local = load(OUTPUT / CHECKER, 'host_transition_packet12')
    manifest = copy.deepcopy(parent)
    manifest.update(schema=SCHEMA, parent_packet=str(PARENT), parent_manifest_sha256=PARENT_SHA,
        host_embedding_parent_manifest_sha256=parent['parent_manifest_sha256'],
        host_embedding_parent11=parent['host_embedding'], host_embedding=host,
        host_transition_preparer_sha256=builder_sha,
        startup_tools={name: sha(OUTPUT / 'launch' / name) for name in parent['startup_tools']},
        extension_sha256s={name: sha(OUTPUT / 'source/scripts' / name) for name in local.EXTENSIONS})
    manifest['patch_order'].append(patch_name)
    manifest['patch_sha256s'][patch_name] = sha(OUTPUT / 'patches' / patch_name)
    manifest['limitations'].append('Actual tiny CPU lifecycle is qualified; full-model transitions/residency, full clips and speed remain pending. Initial cold assembly requires separate client RAM admission.')
    common.verify_packet(PARENT, PARENT_SHA)
    require(sha(Path(__file__)) == builder_sha, 'Builder changed during preparation')
    for source, expected in proofs.values():
        require(sha(source) == expected, 'CPU proof changed during preparation')
    files = {str(p.relative_to(OUTPUT)): sha(p) for p in OUTPUT.rglob('*') if p.is_file() and p.name != 'STATUS.txt'}
    require({name for name, expected in parent['files'].items() if files[name] != expected} == set(CHANGED), 'Unexpected parent byte change')
    for name, (_, expected) in INPUTS.items():
        require(files['source/scripts/' + name] == expected, 'Installed successor source changed')
    manifest['files'] = files
    write_json(OUTPUT / 'manifest.json', manifest)
    manifest_sha = sha(OUTPUT / 'manifest.json')
    local.verify_packet(OUTPUT, manifest_sha)
    local.verify_runtime(manifest['runtime'])
    require('torch' not in sys.modules, 'Source preparation imported Torch')
    (OUTPUT / 'STATUS.txt').write_text('PREPARED, INACTIVE CLIP-only lifecycle. Full-model admission/quality/speed pending.\n')
    return {'status': 'prepared-inactive-not-deployed', 'packet': str(OUTPUT), 'manifest_sha256': manifest_sha,
            'files': len(files), 'source_checks': checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.check_only), indent=2))
