#!/usr/bin/env python3
"""Seal an inactive decoder-axis successor; no native imports or server actions."""
import argparse
import ast
import copy
import difflib
import hashlib
import importlib.util
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
NODE_SHA = '27e95788b3213adab52a72df46049cda2c17ed9c32afb85338c7c7f839bebf03'
SCHEMA = 'ltx.na-axis-runtime-packet.v1'
CHECKER = 'launch/encoder_runtime_common.py'
NEW_EXTENSIONS = ('ltx_na_axis_router.py', 'ltx_na_axis_candidate.py', 'na_axis_decode_node.py')
KITCHEN = Path('/home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/comfy_kitchen')
DEPENDENCIES = {
    str(KITCHEN / 'backends/eager/na.py'): '4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995',
    str(KITCHEN / 'backends/eager/__init__.py'): '8a92e2b0b1b80781fe401fecba658bb7f79962c73ba2a463d4a44488feda375d',
    str(KITCHEN / 'registry.py'): '181b02ee1ee60154766cebb3cad6dc5d2015c38551e10071303a5a2a897f7015',
    str(KITCHEN / '__init__.py'): 'e19ad20021eb35986c9cfce19c4ee2fdc813f2783aeeae46559d62b649744117',
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
'''
    text = replace_once(text, '    return manifest\n', checks + '    return manifest\n')
    reverse = replace_once(text, checks, '')
    for before, after in reversed(changes):
        reverse = replace_once(reverse, after, before)
    require(reverse == original, 'Inherited checker source did not reverse byte-for-byte')
    ast.parse(text)
    return text


def prepare(output, check_only=False):
    require(output == ROOT / 'prepared-encoder-na-axis-09' and not output.exists() and not output.is_symlink(),
            'Use the new, absent packet09 directory')
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
        'na_axis_decode_node.py': (LANE / 'scripts/na_axis_decode_node.py', NODE_SHA),
    }
    for path, digest in inputs.values():
        require(not path.is_symlink() and path.is_file() and sha(path) == digest, 'Unreviewed decoder source: ' + str(path))
    for path, digest in DEPENDENCIES.items():
        require(sha(path) == digest, 'Kitchen source changed: ' + path)
    checker = checker_source((PARENT / CHECKER).read_text())
    control = json.loads((PARENT / 'graphs/control.json').read_text())
    graphs = {mode: graph_source(control, mode) for mode in ('original', 'axis-cache')}
    checks = {'inherited_checker_reverses_byte_for_byte': True,
        'only_modified_parent_file': CHECKER, 'launcher_inherited_unchanged': True,
        'graphs_change_only_decode374': True, 'transformer_dispatch': 'original',
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
    local = load(output / CHECKER, 'axis_packet09_common')
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
        'native_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False}
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
