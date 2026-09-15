#!/usr/bin/env python3
"""Prepare packet14: per-block XPU graph capture as a bounded, restorable gate.

Inherits every packet13 byte. Adds two extensions, one custom-node copy and
three gate graphs, and replaces only the checker so it can pin them. No
numerical source file and no original graph is touched.

No native imports, endpoint calls, device discovery or application action.
"""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
PARENT_NAME = 'prepared-encoder-host-residency-13'
PARENT_SHA = '174e80b56ce16d712f1315832463baa0f86657c5568d587719f421925ea7a29f'
OUTPUT = ROOT / 'prepared-encoder-graph-capture-14'
CHECKER = 'launch/encoder_runtime_common.py'
PROV = 'provenance/graph-capture/parent/'
PARENT_MANIFEST_FILE = 'host-residency-13-parent-manifest.json'
ADAPTER = 'ltx_graph_capture.py'
NODE = 'graph_capture_node.py'
NODE_DIR = 'ltx_graph_capture_lab'
SELECTION = 'all48'
MODES = ('original', 'graph', 'restored')
BASE_GRAPH = 'graphs/host-embedding-control.json'

NEW_VERIFY = '''def verify_packet(packet, expected_manifest_sha256):
    """Packet14 gate: inherit packet13 wholesale, permit only the graph-capture additions.

    Packet13's manifest digest is pinned here and packet13 pinned packet12's, which
    was verified against the complete encoder/compiler/RMS/activation/multiblock/
    adjacent-state/onepass/na-axis/host-embedding ancestry. Requiring every packet13
    file to reappear byte-identically therefore preserves that chain, including all
    numerical source and every original graph.
    """
    packet = Path(packet)
    require(packet.is_absolute() and packet.parent == ROOT and
            re.fullmatch(r'prepared-encoder-[a-z0-9-]+', packet.name), 'Unexpected packet path')
    manifest_path = safe_path(packet, 'manifest.json')
    require(re.fullmatch(r'[0-9a-f]{64}', expected_manifest_sha256) is not None,
            'Explicit manifest SHA256 required')
    require(sha(manifest_path) == expected_manifest_sha256, 'Packet manifest changed')
    manifest = json.loads(manifest_path.read_text())
    require(manifest['schema'] == 'ltx.graph-capture-runtime-packet.v1', 'Launcher requires graph-capture packet')
    require(manifest['source_commit'] == PIN, 'Core revision changed')
    require(manifest['model_verification_sha256'] == MODEL_VERIFICATION_SHA256, 'Model identity changed')
    require(manifest['status'] == 'prepared-inactive-not-deployed', 'Unexpected packet status')
    for name, digest in manifest['files'].items():
        p = safe_path(packet, name)
        require(p.is_file() and sha(p) == digest, 'Packet file changed: ' + name)
    actual = set()
    for p in packet.rglob('*'):
        require(not p.is_symlink(), 'Unexpected packet symlink')
        if p.is_file():
            actual.add(str(p.relative_to(packet)))
    require(actual == set(manifest['files']) | {'manifest.json', 'STATUS.txt'},
            'Uninventoried packet files; inspect before use')
    require(set(manifest['extension_sha256s']) == set(EXTENSIONS), 'Extension set changed')
    for name, digest in manifest['extension_sha256s'].items():
        require(manifest['files']['source/scripts/' + name] == digest, 'Extension hash disagrees')
    for node, helper in NODES.items():
        require(manifest['files'][f'source/custom_nodes/{node}/__init__.py'] ==
                manifest['extension_sha256s'][helper], 'Custom node copy differs from helper')
    for name, digest in manifest['startup_tools'].items():
        require(manifest['files']['launch/' + name] == digest, 'Startup tool hash disagrees')

    capture = manifest['graph_capture']
    require(capture['parent_packet'] == 'prepared-encoder-host-residency-13' and
            capture['parent_manifest_sha256'] ==
            '174e80b56ce16d712f1315832463baa0f86657c5568d587719f421925ea7a29f',
            'Unexpected graph-capture parent')
    parent_path = safe_path(packet, 'host-residency-13-parent-manifest.json')
    require(sha(parent_path) == capture['parent_manifest_sha256'], 'Parent manifest changed')
    parent = json.loads(parent_path.read_text())
    require(parent['schema'] == 'ltx.host-residency-runtime-packet.v1', 'Unexpected parent schema')
    require(manifest['runtime'] == parent['runtime'], 'Graph-capture runtime differs from parent')
    require(manifest['model_verification_sha256'] == parent['model_verification_sha256'] and
            manifest['source_commit'] == parent['source_commit'], 'Parent identity differs')

    added = {'source/scripts/ltx_graph_capture.py', 'source/scripts/graph_capture_node.py',
             'source/custom_nodes/ltx_graph_capture_lab/__init__.py',
             'provenance/graph-capture/parent/launch/encoder_runtime_common.py',
             'host-residency-13-parent-manifest.json'}
    added |= {'graphs/graph-capture-all48-' + mode + '.json' for mode in ('original', 'graph', 'restored')}
    for name, digest in parent['files'].items():
        if name == 'launch/encoder_runtime_common.py':
            require(manifest['files']['provenance/graph-capture/parent/' + name] == digest,
                    'Original packet13 checker changed')
        else:
            require(manifest['files'].get(name) == digest, 'Inherited packet13 file changed: ' + name)
    require(set(manifest['files']) == set(parent['files']) | added, 'Packet14 file inventory changed')
    for name in parent['files']:
        if name.startswith(('source/', 'graphs/')):
            require(manifest['files'][name] == parent['files'][name],
                    'Inherited numerical source or original graph changed: ' + name)
    require(manifest['files']['source/custom_nodes/ltx_graph_capture_lab/__init__.py'] ==
            manifest['files']['source/scripts/graph_capture_node.py'],
            'Graph-capture custom-node copy differs from its helper')
    require(capture['adapter_sha256'] == manifest['extension_sha256s']['ltx_graph_capture.py'] and
            capture['node_sha256'] == manifest['extension_sha256s']['graph_capture_node.py'],
            'Graph-capture source inventory mismatch')

    # Gate graphs are the original control recipe plus one restorable gate node.
    control = json.loads(safe_path(packet, 'graphs/host-embedding-control.json').read_text())
    expected_graphs = []
    for mode in ('original', 'graph', 'restored'):
        name = 'graphs/graph-capture-all48-' + mode + '.json'
        expected_graphs.append(name)
        graph = json.loads(safe_path(packet, name).read_text())
        require(graph.pop('422') == {'class_type': 'LTXGraphCaptureGate', 'inputs': {
                'model': ['420', 0], 'mode': mode, 'selection': 'all48',
                'run_name': 'assign-unique-request-name'}}, 'Graph-capture gate node changed')
        for node in ('388', '391'):
            require(graph[node]['inputs']['model'] == ['422', 0], 'Graph-capture edge changed')
            graph[node]['inputs']['model'] = ['420', 0]
        require(graph == control, 'Graph-capture graph changed the original quality recipe')
    require(capture['graphs'] == expected_graphs, 'Graph-capture graph inventory changed')
    require(capture['selection'] == 'all48' and capture['block_indices'] == list(range(48)) and
            capture['modes'] == ['original', 'graph', 'restored'] and
            capture['numerical_source_changed'] is False and capture['graphs_changed'] is False and
            capture['native_gpu_qualified'] is False and capture['full_clip_qualified'] is False and
            capture['speed_qualified'] is False, 'Graph-capture contract changed')
    return manifest
'''


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def build_checker(text):
    require(text.count('def verify_packet(') == 1, 'Ambiguous verify_packet')
    start = text.index('def verify_packet(packet, expected_manifest_sha256):')
    end = text.index('def verify_model_receipt():')
    updated = text[:start] + NEW_VERIFY + '\n\n' + text[end:]
    old_ext = "              'host_embedding_transition_memory.py')"
    require(updated.count(old_ext) == 1, 'Unexpected EXTENSIONS layout')
    updated = updated.replace(old_ext, "              'host_embedding_transition_memory.py',\n"
                                       "              'ltx_graph_capture.py', 'graph_capture_node.py')", 1)
    old_nodes = "         'ltx_host_embedding_lab': 'host_embedding_resident_node.py'}"
    require(updated.count(old_nodes) == 1, 'Unexpected NODES layout')
    updated = updated.replace(old_nodes, "         'ltx_host_embedding_lab': 'host_embedding_resident_node.py',\n"
                                         "         'ltx_graph_capture_lab': 'graph_capture_node.py'}", 1)
    ast.parse(updated)
    return updated


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parent', type=Path, default=ROOT / PARENT_NAME)
    ap.add_argument('--output', type=Path, default=OUTPUT)
    a = ap.parse_args()
    parent, output = a.parent, a.output
    require(parent.is_dir() and parent.name == PARENT_NAME, 'Unexpected parent packet')
    require(sha(parent / 'manifest.json') == PARENT_SHA, 'Parent manifest is not the verified packet13')
    require(not output.exists(), 'Output packet already exists; refuse to overwrite')
    parent_manifest = json.loads((parent / 'manifest.json').read_text())
    for name, digest in parent_manifest['files'].items():
        p = parent / name
        require(p.is_file() and not p.is_symlink() and sha(p) == digest, 'Parent file changed: ' + name)

    adapter_src = LANE / 'scripts' / ADAPTER
    node_src = LANE / 'scripts' / NODE
    for p in (adapter_src, node_src):
        require(p.is_file(), 'Missing prepared source: ' + str(p))
        ast.parse(p.read_text())

    staging = output.with_name(output.name + '.staging')
    require(not staging.exists(), 'Stale staging directory')
    shutil.copytree(parent, staging, symlinks=False)

    checker_new = build_checker((staging / CHECKER).read_text())
    prov = staging / PROV / 'launch'
    prov.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(parent / CHECKER, prov / 'encoder_runtime_common.py')
    shutil.copyfile(parent / 'manifest.json', staging / PARENT_MANIFEST_FILE)
    (staging / CHECKER).write_text(checker_new)

    shutil.copyfile(adapter_src, staging / 'source/scripts' / ADAPTER)
    shutil.copyfile(node_src, staging / 'source/scripts' / NODE)
    node_dir = staging / 'source/custom_nodes' / NODE_DIR
    node_dir.mkdir(exist_ok=False)
    shutil.copyfile(node_src, node_dir / '__init__.py')

    control = json.loads((staging / BASE_GRAPH).read_text())
    for mode in MODES:
        graph = copy.deepcopy(control)
        graph['422'] = {'class_type': 'LTXGraphCaptureGate', 'inputs': {
            'model': ['420', 0], 'mode': mode, 'selection': SELECTION,
            'run_name': 'assign-unique-request-name'}}
        for node in ('388', '391'):
            require(graph[node]['inputs']['model'] == ['420', 0], 'Unexpected control graph edge')
            graph[node]['inputs']['model'] = ['422', 0]
        path = staging / 'graphs' / ('graph-capture-' + SELECTION + '-' + mode + '.json')
        with path.open('x') as handle:
            json.dump(graph, handle, indent=2, sort_keys=True)
            handle.write('\n')

    files = {}
    for p in sorted(staging.rglob('*')):
        require(not p.is_symlink(), 'Unexpected symlink while inventorying')
        if p.is_file():
            rel = str(p.relative_to(staging))
            if rel in ('manifest.json', 'STATUS.txt'):
                continue
            files[rel] = sha(p)

    added = {'source/scripts/' + ADAPTER, 'source/scripts/' + NODE,
             f'source/custom_nodes/{NODE_DIR}/__init__.py',
             PROV + 'launch/encoder_runtime_common.py', PARENT_MANIFEST_FILE}
    added |= {f'graphs/graph-capture-{SELECTION}-{m}.json' for m in MODES}
    require(set(files) == set(parent_manifest['files']) | added, 'Unexpected packet14 inventory')
    for name, digest in parent_manifest['files'].items():
        if name == CHECKER:
            require(files[PROV + 'launch/encoder_runtime_common.py'] == digest, 'Provenance copy differs')
            require(files[name] != digest, 'Checker is unchanged')
        else:
            require(files[name] == digest, 'Inherited file drifted: ' + name)
    require(files[f'source/custom_nodes/{NODE_DIR}/__init__.py'] == files['source/scripts/' + NODE],
            'Custom-node copy differs from helper')

    extensions = dict(parent_manifest['extension_sha256s'])
    extensions[ADAPTER] = files['source/scripts/' + ADAPTER]
    extensions[NODE] = files['source/scripts/' + NODE]
    manifest = {
        'schema': 'ltx.graph-capture-runtime-packet.v1',
        'status': 'prepared-inactive-not-deployed',
        'source_commit': parent_manifest['source_commit'],
        'model_verification_sha256': parent_manifest['model_verification_sha256'],
        'runtime': parent_manifest['runtime'],
        'files': files,
        'extension_sha256s': extensions,
        'startup_tools': {'encoder_runtime_common.py': files[CHECKER],
                          'serve-encoder.py': files['launch/serve-encoder.py']},
        'preparer_sha256': sha(Path(__file__)),
        'host_residency': parent_manifest['host_residency'],
        'graph_capture': {
            'parent_packet': PARENT_NAME, 'parent_manifest_sha256': PARENT_SHA,
            'adapter_sha256': extensions[ADAPTER], 'node_sha256': extensions[NODE],
            'selection': SELECTION, 'block_indices': list(range(48)), 'modes': list(MODES),
            'graphs': [f'graphs/graph-capture-{SELECTION}-{m}.json' for m in MODES],
            'mechanism': 'per-block torch.xpu.XPUGraph capture and replay behind the existing '
                         'set_model_patch_replace route; the native block, its registration and the '
                         'shard routing are unchanged',
            'capture_proof': 'every captured graph must replay bit-identically to a fresh eager execution '
                             'of the same block on the same inputs, and must be proven non-inert',
            'warmup_iterations': 3, 'split_index': 21,
            'numerical_source_changed': False, 'graphs_changed': False,
            'native_gpu_qualified': False, 'full_clip_qualified': False, 'speed_qualified': False,
        },
        'limitations': [
            'Prepared offline only: no native import, endpoint call, device discovery or application action.',
            'Graph capture is validated on a synthetic LTX-shaped block, not on the real checkpoint blocks.',
            'Capture-safety of the real block forward is enforced at runtime, not proven here.',
            'Bitwise clip equality is expected but unproven until the four original raw oracles pass.',
            'No speed result is promoted by preparation.',
            'Parent packets and all earlier evidence remain unmodified.',
        ],
    }
    with (staging / 'manifest.json').open('w') as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write('\n')
    (staging / 'STATUS.txt').write_text(
        'PREPARED, INACTIVE per-block XPU graph capture gate. Quality/speed unqualified.\n')
    staging.rename(output)
    print(json.dumps({'status': 'prepared', 'packet': str(output),
                      'manifest_sha256': sha(output / 'manifest.json'),
                      'parent_manifest_sha256': PARENT_SHA,
                      'added_files': sorted(added), 'changed_files': [CHECKER],
                      'inherited_files': len(parent_manifest['files']) - 1}, indent=2))


if __name__ == '__main__':
    main()
