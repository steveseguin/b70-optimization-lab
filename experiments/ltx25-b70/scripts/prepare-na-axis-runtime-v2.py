#!/usr/bin/env python3
"""Seal an inactive decoder-axis successor; no native imports or server actions."""
import argparse
import ast
import copy
import difflib
import hashlib
import importlib.util
import inspect
import re
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT = ROOT / 'prepared-encoder-compiler-08'
PARENT_SHA = 'a32f645772d2ef59d46b66c9181f1d9433950172bcc763924de8aa7acb679b6b'
ONEPASS_PARENT_SHA = 'afdbad186a6873a286f93e9d1e715f6bf4c17e1552d75dbce2a3e03c0a1f35c1'
ROUTER_SHA = '9aa3d6cc7be389555d60119ad3fd5960b762568e044eba49760fc03114c2b537'
CANDIDATE_SHA = '40e360bc1f791f0373997f907ca67e804087541498c86ffa5731c8a9eae40cc2'
NODE_SHA = 'ffd7549d29828a11f336f07873f63a407df7722328df519f2bec3514964ad32b'
SCHEMA = 'ltx.na-axis-runtime-packet.v2'
CHECKER = 'launch/encoder_runtime_common.py'
NEW_EXTENSIONS = ('ltx_na_axis_router.py', 'ltx_na_axis_candidate.py', 'na_axis_decode_node.py')
KITCHEN = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen')
DEPENDENCIES = {
    str(KITCHEN / 'backends/eager/na.py'): '4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995',
    str(KITCHEN / 'backends/eager/__init__.py'): '8a92e2b0b1b80781fe401fecba658bb7f79962c73ba2a463d4a44488feda375d',
    str(KITCHEN / 'registry.py'): '181b02ee1ee60154766cebb3cad6dc5d2015c38551e10071303a5a2a897f7015',
    str(KITCHEN / '__init__.py'): 'e19ad20021eb35986c9cfce19c4ee2fdc813f2783aeeae46559d62b649744117',
}
FAILED_PACKET = ROOT / 'prepared-encoder-na-axis-09'
FAILED_SHA = 'a53e06ae5bd1be8931eff11d4e9112b850912147b37fcabf1bda064b12f419ed'
CORRECTION_FILES = {
    'failed09-manifest.json': (FAILED_PACKET / 'manifest.json', FAILED_SHA),
    'failed09-startup-failure.json': (ROOT / 'na-axis-migration-09/startup-failure.json',
        'bdf914ee6fe908ea0bda69180bb9814b40db208b96b66b1e81fba16ad50a7729'),
    'failed09-startup-failure.log': (ROOT / 'na-axis-migration-09/startup-failure.log',
        '1989e73176d45dc4dc869c4e792bd25ee3ffe0593887dee8c9ed3b779ed9daee'),
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def literal_source_pins(path, names):
    """Read declarations without importing a node or executing its startup."""
    tree = ast.parse(Path(path).read_text(), filename=str(path))
    pins = {}
    for name in names:
        writes = [n for n in ast.walk(tree) if isinstance(n, ast.Name)
                  and isinstance(n.ctx, ast.Store) and n.id == name]
        declarations = [n for n in tree.body if isinstance(n, ast.Assign)
                        and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                        and n.targets[0].id == name]
        require(len(writes) == len(declarations) == 1, 'Ambiguous/missing startup pin: ' + name)
        value = declarations[0].value
        require(isinstance(value, ast.Constant) and type(value.value) is str
                and re.fullmatch(r'[0-9a-f]{64}', value.value), 'Nonliteral startup pin: ' + name)
        pins[name] = value.value
    return pins


def verify_na_source_closure(source, *, node_path=None, router_path=None, candidate_path=None,
        original_na_path='/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen/backends/eager/na.py'):
    """Close every startup hash edge over the actual sealed/inherited sources."""
    source = Path(source)
    node_path = Path(node_path) if node_path is not None else source / 'scripts/na_axis_decode_node.py'
    router_path = Path(router_path) if router_path is not None else source / 'scripts/ltx_na_axis_router.py'
    candidate_path = Path(candidate_path) if candidate_path is not None else source / 'scripts/ltx_na_axis_candidate.py'
    files = {'NODES_SHA': source / 'nodes.py', 'SD_SHA': source / 'comfy/sd.py',
             'DECODER_SHA': source / 'comfy/ldm/lightricks/vae/na_diffusion_decoder.py',
             'ROUTER_SHA': router_path, 'CANDIDATE_SHA': candidate_path}
    for path in (node_path, *files.values(), Path(original_na_path)):
        require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
                'Missing/linked startup dependency: ' + str(path))
    pins = literal_source_pins(node_path, files)
    router_pins = literal_source_pins(router_path, ('ORIGINAL_SHA', 'CANDIDATE_SHA'))
    rows = {name: {'declared_sha256': pins[name], 'actual_sha256': sha(path)}
            for name, path in files.items()}
    rows.update({'router.' + name: {'declared_sha256': router_pins[name], 'actual_sha256': sha(path)}
                 for name, path in {'ORIGINAL_SHA': original_na_path, 'CANDIDATE_SHA': candidate_path}.items()})
    mismatches = [name + ': declared=' + row['declared_sha256'] + ' actual=' + row['actual_sha256']
                  for name, row in rows.items() if row['declared_sha256'] != row['actual_sha256']]
    require(not mismatches, 'NA startup source closure failed: ' + '; '.join(mismatches))
    return {'status': 'passed-stdlib-source-pin-closure', 'dependencies': rows,
            'native_imports': False, 'startup_registration_qualified': False}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_once(text, before, after):
    require(text.count(before) == 1, 'Expected exactly one source context: ' + before)
    return text.replace(before, after, 1)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def graph_source(control, mode):
    require(mode in ('original', 'axis-cache') and '422' not in control, 'Unexpected control graph')
    graph = copy.deepcopy(control)
    require(graph['374']['class_type'] == 'VAEDecode', 'Original decode node differs')
    graph['374']['class_type'] = 'LTXNAAxisDecode'
    graph['374']['inputs'].update(mode=mode, run_name='assign-unique-request-name')
    return graph


def checker_source(original):
    changes = [
        ('import hashlib\n', 'import ast\nimport hashlib\n'),
        ("manifest['schema'] == 'ltx.compiler-multiblock-onepass-state-runtime-packet.v1'",
         f"manifest['schema'] == '{SCHEMA}'"),
        (f"manifest['parent_manifest_sha256'] == '{ONEPASS_PARENT_SHA}'",
         f"manifest['onepass_parent_manifest_sha256'] == '{ONEPASS_PARENT_SHA}'"),
        ("'ltx_multiblock_compile.py', 'multiblock_compile_node.py')",
         "'ltx_multiblock_compile.py', 'multiblock_compile_node.py',\n"
         "              'ltx_na_axis_router.py', 'ltx_na_axis_candidate.py', 'na_axis_decode_node.py')"),
        ("'ltx_multiblock_compile_lab': 'multiblock_compile_node.py'}",
         "'ltx_multiblock_compile_lab': 'multiblock_compile_node.py',\n"
         "         'ltx_na_axis_decode_lab': 'na_axis_decode_node.py'}"),
    ]
    text = original
    for before, after in changes:
        text = replace_once(text, before, after)
    checks = f'''    # Decoder successor retains every packet08 numerical source and graph.
    require(manifest['parent_manifest_sha256'] == {PARENT_SHA!r}, 'Unexpected packet08 parent')
    axis_parent_path = safe_path(packet, 'onepass-08-parent-manifest.json')
    require(sha(axis_parent_path) == {PARENT_SHA!r}, 'Packet08 parent manifest changed')
    axis_parent = json.loads(axis_parent_path.read_text())
    require(axis_parent['schema'] == 'ltx.compiler-multiblock-onepass-state-runtime-packet.v1',
            'Unexpected packet08 schema')
    require(manifest['runtime'] == axis_parent['runtime'], 'Decoder runtime changed')
    for name, digest in axis_parent['files'].items():
        if name == {CHECKER!r}:
            require(manifest['files']['provenance/na-axis-parent/' + name] == digest,
                    'Original packet08 checker changed')
        else:
            require(manifest['files'].get(name) == digest, 'Inherited packet08 source changed: ' + name)
    axis = manifest['na_axis']
    require(axis['router_sha256'] == {ROUTER_SHA!r} and axis['candidate_sha256'] == {CANDIDATE_SHA!r}
            and axis['node_sha256'] == {NODE_SHA!r}, 'Decoder source identities changed')
    for name, digest in zip({NEW_EXTENSIONS!r}, ({ROUTER_SHA!r}, {CANDIDATE_SHA!r}, {NODE_SHA!r})):
        require(manifest['extension_sha256s'][name] == digest, 'Decoder extension identity differs')
    require(axis['dependencies'] == {DEPENDENCIES!r}, 'Kitchen dependency identity changed')
    for name, digest in axis['dependencies'].items():
        path = Path(name)
        require(not any(p.is_symlink() for p in (path, *path.parents)) and sha(path) == digest,
                'Installed Kitchen dependency changed: ' + name)
    require(axis['modes'] == ['original', 'axis-cache'] and axis['node_class'] == 'LTXNAAxisDecode'
            and axis['cache_scope'] == 'one-na3d-invocation' and axis['max_cache_entries'] == 64
            and axis['max_axis_bool_elements'] == 4096 and axis['max_cache_tensor_bytes'] == 262144
            and axis['transformer_dispatch'] == 'original', 'Decoder qualification scope changed')
    axis_control = json.loads(safe_path(packet, 'graphs/control.json').read_text())
    require('422' not in axis_control, 'Unexpected compiler gate in decoder control')
    for mode in ('original', 'axis-cache'):
        graph = json.loads(safe_path(packet, 'graphs/na-axis-' + mode + '.json').read_text())
        require(graph['374']['class_type'] == 'LTXNAAxisDecode'
                and graph['374']['inputs'].pop('mode') == mode
                and graph['374']['inputs'].pop('run_name') == 'assign-unique-request-name',
                'Unexpected private decoder node')
        graph['374']['class_type'] = 'VAEDecode'
        require(graph == axis_control, 'Decoder graph changed original quality recipe')
    require(axis['graphs'] == ['graphs/na-axis-original.json', 'graphs/na-axis-axis-cache.json'],
            'Decoder graph inventory changed')
    require(axis['source_pin_closure'] == verify_na_source_closure(safe_path(packet, 'source')),
            'Decoder startup source closure receipt differs')
    correction = manifest['na_axis_correction']
    require(correction == {correction_manifest()!r}, 'Decoder correction provenance differs')
    for name, digest in correction['files'].items():
        require(sha(safe_path(packet, 'provenance/na-axis-correction/' + name)) == digest,
                'Decoder failed09 correction evidence changed: ' + name)
'''
    text = replace_once(text, '    return manifest\n', checks + '    return manifest\n')
    helpers = '\n\n' + inspect.getsource(literal_source_pins) + '\n\n' + inspect.getsource(verify_na_source_closure) + '\n'
    text = replace_once(text, '\ndef verify_packet(', helpers + '\ndef verify_packet(')
    reverse = replace_once(text, helpers, '')
    reverse = replace_once(reverse, checks, '')
    for before, after in reversed(changes):
        reverse = replace_once(reverse, after, before)
    require(reverse == original, 'Inherited checker source did not reverse byte-for-byte')
    ast.parse(text)
    return text


def correction_manifest():
    return {'failed_packet_manifest_sha256': FAILED_SHA,
            'reason': 'startup-pin-mismatch-before-native-requests',
            'files': {name: digest for name, (_, digest) in CORRECTION_FILES.items()}}


def prepare(output, check_only=False):
    require(output == ROOT / 'prepared-encoder-na-axis-10' and not output.exists() and not output.is_symlink(),
            'Use the new, absent packet10 directory')
    require(sha(PARENT / 'manifest.json') == PARENT_SHA, 'Parent08 manifest changed')
    parent = json.loads((PARENT / 'manifest.json').read_text())
    require(sha(PARENT / CHECKER) == parent['files'][CHECKER], 'Parent08 checker changed')
    common = load(PARENT / CHECKER, 'axis_parent08_common')
    common.safe_path(ROOT, output.name)
    common.verify_packet(PARENT, PARENT_SHA)
    common.verify_runtime(parent['runtime'])
    common.verify_model_receipt()
    inputs = {
        'ltx_na_axis_router.py': (LANE / 'scripts/ltx_na_axis_router.py', ROUTER_SHA),
        'ltx_na_axis_candidate.py': (LANE / 'data/na-axis-cache-01/candidate-na.py', CANDIDATE_SHA),
        'na_axis_decode_node.py': (LANE / 'scripts/na_axis_decode_node_v2.py', NODE_SHA),
    }
    for path, digest in inputs.values():
        require(not path.is_symlink() and path.is_file() and sha(path) == digest, 'Unreviewed decoder source: ' + str(path))
    for path, digest in DEPENDENCIES.items():
        require(sha(path) == digest, 'Kitchen source changed: ' + path)
    for path, digest in CORRECTION_FILES.values():
        require(not path.is_symlink() and sha(path) == digest, 'Failed09 evidence changed: ' + str(path))
    closure = verify_na_source_closure(PARENT / 'source',
        node_path=inputs['na_axis_decode_node.py'][0],
        router_path=inputs['ltx_na_axis_router.py'][0],
        candidate_path=inputs['ltx_na_axis_candidate.py'][0])
    checker = checker_source((PARENT / CHECKER).read_text())
    control = json.loads((PARENT / 'graphs/control.json').read_text())
    graphs = {mode: graph_source(control, mode) for mode in ('original', 'axis-cache')}
    checks = {'inherited_checker_reverses_byte_for_byte': True,
        'only_modified_parent_file': CHECKER, 'launcher_inherited_unchanged': True,
        'graphs_change_only_decode374': True, 'transformer_dispatch': 'original',
        'source_pin_closure': closure,
        'torch_imported': 'torch' in sys.modules, 'native_admission': False}
    require(not checks['torch_imported'], 'Source preparation imported Torch')
    if check_only:
        return {'status': 'inactive-source-check-passed', 'files_written': 0, 'source_checks': checks,
                'builder_sha256': sha(Path(__file__)), 'node_sha256': NODE_SHA}
    require(shutil.disk_usage(ROOT).free >= 5 * 1024**3, 'Less than5GiB disk free')
    builder_sha = sha(Path(__file__))
    output.mkdir()
    (output / 'STATUS.txt').write_text('INCOMPLETE decoder-axis packet; do not launch.\n')
    for name in parent['files']:
        target = common.safe_path(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PARENT / name, target)
    shutil.copyfile(PARENT / 'manifest.json', output / 'onepass-08-parent-manifest.json')
    provenance = output / 'provenance/na-axis-parent' / CHECKER
    provenance.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PARENT / CHECKER, provenance)
    shutil.copyfile(Path(__file__), output / 'provenance' / Path(__file__).name)
    correction = output / 'provenance/na-axis-correction'
    correction.mkdir()
    for name, (path, _) in CORRECTION_FILES.items():
        shutil.copyfile(path, correction / name)
    (output / CHECKER).write_text(checker)
    for name, (path, _) in inputs.items():
        shutil.copyfile(path, output / 'source/scripts' / name)
    node_target = output / 'source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'
    node_target.parent.mkdir()
    shutil.copyfile(inputs['na_axis_decode_node.py'][0], node_target)
    for mode, graph in graphs.items():
        write_json(output / ('graphs/na-axis-' + mode + '.json'), graph)
    patch_name = 'na-axis-runtime.patch'
    (output / 'patches' / patch_name).write_text(''.join(difflib.unified_diff(
        (PARENT / CHECKER).read_text().splitlines(True), checker.splitlines(True),
        fromfile='a/' + CHECKER, tofile='b/' + CHECKER)))
    write_json(output / 'provenance/na-axis-source-checks.json', checks)
    local = load(output / CHECKER, 'axis_packet10_common')
    manifest = copy.deepcopy(parent)
    manifest.update(schema=SCHEMA, parent_packet=str(PARENT), parent_manifest_sha256=PARENT_SHA,
        onepass_parent_manifest_sha256=parent['parent_manifest_sha256'], na_axis_preparer_sha256=builder_sha,
        startup_tools={name: sha(output / 'launch' / name) for name in parent['startup_tools']},
        extension_sha256s={name: sha(output / 'source/scripts' / name) for name in local.EXTENSIONS})
    manifest['na_axis'] = {'router_sha256': ROUTER_SHA, 'candidate_sha256': CANDIDATE_SHA,
        'node_sha256': NODE_SHA, 'dependencies': DEPENDENCIES, 'modes': ['original', 'axis-cache'],
        'node_class': 'LTXNAAxisDecode', 'cache_scope': 'one-na3d-invocation', 'max_cache_entries': 64,
        'max_axis_bool_elements': 4096, 'max_cache_tensor_bytes': 262144, 'transformer_dispatch': 'original',
        'graphs': ['graphs/na-axis-original.json', 'graphs/na-axis-axis-cache.json'],
        'source_pin_closure': closure,
        'native_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False}
    manifest['na_axis_correction'] = correction_manifest()
    manifest['patch_order'].append(patch_name)
    manifest['patch_sha256s'][patch_name] = sha(output / 'patches' / patch_name)
    manifest['limitations'].append('Decoder axis-cache source/CPU gates do not qualify native full clips or speed; no C++ candidate included.')
    common.verify_packet(PARENT, PARENT_SHA)
    require(sha(Path(__file__)) == builder_sha, 'Builder changed during preparation')
    for path, digest in inputs.values():
        require(sha(path) == digest, 'Preparation input changed')
    files = {str(p.relative_to(output)): sha(p) for p in output.rglob('*') if p.is_file() and p.name != 'STATUS.txt'}
    require({name for name, digest in parent['files'].items() if files[name] != digest} == {CHECKER},
            'Unexpected parent file change')
    manifest['files'] = files
    write_json(output / 'manifest.json', manifest)
    digest = sha(output / 'manifest.json')
    local.verify_packet(output, digest)
    local.verify_runtime(manifest['runtime'])
    require('torch' not in sys.modules, 'Source preparation imported Torch')
    (output / 'STATUS.txt').write_text('PREPARED, INACTIVE decoder axis cache. Native exactness/speed pending.\n')
    return {'status': 'prepared-inactive-not-deployed', 'packet': str(output), 'manifest_sha256': digest,
        'files': len(files), 'node_sha256': NODE_SHA, 'source_checks': checks}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.check_only), indent=2))
