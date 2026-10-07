#!/usr/bin/env python3
"""Build packet 98 using the unchanged graph-capture generator, then a checked overlay.

Only the newly created packet is written. Existing packets and live helpers are
read-only. Rebuilding requires a new empty output path; no overwrite option.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
R = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
P97 = R / 'prepared-encoder-place-97'
P98 = R / 'prepared-encoder-size-98'
PIN97 = '6e232f72a9835727323c383bc9baaa167844b58dc6400a5de43a3b9eb4e44b9f'
SIZES = ('256x256', '512x320', '640x384')
MODULE = 'ltx_output_size_98.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old), count)
    return text.replace(old, new)


def runtime_overlay(name, text):
    if name not in ('pipeline_node.py', 'pipeline_sampler_node.py', 'pipeline_decode_node.py', 'ltx_graph_capture.py'):
        return text
    text = replace(text, 'import torch\n', 'import torch\nimport ltx_output_size_98 as size98\n')
    if name != 'ltx_graph_capture.py':
        text = replace(text, 'def write_json(path, value):\n',
                       'def write_json(path, value):\n    value = {**value, **size98.receipt_metadata()}\n')
    if name == 'pipeline_node.py':
        start = text.index("class LTXPipelineTextEncode:")
        end = text.index("    RETURN_TYPES", start)
        section = text[start:end]
        section = replace(section, "'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}", "'run_name': ('STRING', {'default': 'assign-unique-request-name'})},\n                'optional': {'output_size': ('STRING', {'default': '256x256'}),\n                             'speed_only': ('BOOLEAN', {'default': False})}}")
        text = text[:start] + section + text[end:]
        text = replace(text, 'def apply(self, clip, text, mode, clip_index, depth, run_name):',
                       'def apply(self, clip, text, mode, clip_index, depth, run_name, output_size="256x256", speed_only=False):\n        size98.admit_arm(output_size, speed_only)')
    elif name == 'pipeline_sampler_node.py':
        text = replace(text, "'optional': {'batch':", "'optional': {'output_size': ('STRING', {'default': '256x256'}),\n                         'speed_only': ('BOOLEAN', {'default': False}), 'batch':")
        text = replace(text, 'batch=None, stream_last=None, **chain):',
                       'batch=None, stream_last=None, output_size="256x256", speed_only=False, **chain):\n        size98.admit_arm(output_size, speed_only)\n        if size98.OUTPUT_SIZE != size98.DEFAULT:\n            size98.check_latent(chain["video_latent"]["samples"], 1)')
        text = text.replace("**identity, 'run_name': run_name,", "**identity, 'run_name': run_name, 'output_size': size98.OUTPUT_SIZE,")
        text = replace(text, 'transient_bytes=CHAIN_TRANSIENT_BYTES_PER_BATCH * SAMPLER_BATCH)',
                       'transient_bytes=int(CHAIN_TRANSIENT_BYTES_PER_BATCH * SAMPLER_BATCH * size98.TOKEN_SCALE))')
    elif name == 'pipeline_decode_node.py':
        text = replace(text, 'def _load_fixture_tensors(row):\n',
                       'def _load_fixture_tensors(row):\n    size98.require_reference_size()\n')
        text = replace(text, '        run, identity, server, hashes = _child_node_context(run_name)\n',
                       '        size98.require_reference_size()\n        run, identity, server, hashes = _child_node_context(run_name)\n')
        # Only the decode node's optional inputs; maintenance probes have no arm inputs.
        start = text.index('class LTXPipelineDecode:')
        end = text.index('    RETURN_TYPES', start)
        section = text[start:end]
        section = replace(section, "'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}", "'run_name': ('STRING', {'default': 'assign-unique-request-name'})},\n                'optional': {'output_size': ('STRING', {'default': '256x256'}),\n                             'speed_only': ('BOOLEAN', {'default': False})}}")
        text = text[:start] + section + text[end:]
        text = replace(text, '\n              run_name, upstream_depth=0):',
                       '\n              run_name, upstream_depth=0, output_size="256x256", speed_only=False):\n        size98.admit_arm(output_size, speed_only)')
        text = text.replace("**identity, 'run_name': run_name,", "**identity, 'run_name': run_name, 'output_size': size98.OUTPUT_SIZE,")
        text = replace(text, 'passed, rows = placement.probe_rows(fixtures, _load_fixture_tensors, native, decoders)',
                       'probe_fn = placement.probe_rows if size98.OUTPUT_SIZE == size98.DEFAULT else size98.probe_rows\n            passed, rows = probe_fn(fixtures, _load_fixture_tensors, native, decoders)\n            if size98.OUTPUT_SIZE != size98.DEFAULT:\n                report["references"] = "none (speed only)"')
        # Validate real latents before either native or replica decode. Fills never reach these helpers.
        for fn in ('decode_native', 'decode_replica'):
            # Insert after function docstring with AST offsets (the functions have differing signatures).
            tree = ast.parse(text)
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == fn)
            first = node.body[0]
            line = first.end_lineno if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str) else node.lineno
            lines = text.splitlines(keepends=True)
            lines.insert(line, '    if size98.OUTPUT_SIZE != size98.DEFAULT:\n        size98.check_latent(video_latent["samples"], 2)\n')
            text = ''.join(lines)
    else:
        text = replace(text, 'MAX_SIGNATURES_PER_BLOCK = 8', 'MAX_SIGNATURES_PER_BLOCK = size98.MAX_SIGNATURES_PER_BLOCK')
        text = replace(text, '        self.img = static_img', '        if size98.OUTPUT_SIZE != size98.DEFAULT and int(static_img[0].shape[1]) not in size98.TOKENS:\n            raise RuntimeError("Slot video token count does not match output size")\n        self.img = static_img')
    if name != 'ltx_graph_capture.py':
        # Scope the graph's explicit speed flag through the writer, also on exceptions.
        tree = ast.parse(text)
        entries = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                   and any(a.arg == 'speed_only' for a in n.args.args)]
        assert len(entries) == 1
        lines = text.splitlines(keepends=True)
        lines.insert(entries[0].lineno - 1, '    @size98.receipt_scope\n')
        text = ''.join(lines)
    ast.parse(text)
    return text


def speed_graph(graph, size):
    graph = copy.deepcopy(graph)
    w, h = map(int, size.split('x'))
    nodes = [n for n in graph.values() if n['class_type'] == 'EmptyLTXVLatentVideo']
    assert len(nodes) == 1
    nodes[0]['inputs'].update(width=w // 2, height=h // 2)
    for key in ('364', '428', '426'):
        graph[key]['inputs'].update(output_size=size, speed_only=True)
    return graph


def speed_bases(manifest):
    names = [a[0] for a in manifest['graph_capture']['arms']]
    return [n for n in names if n in ('pipe-samp2-tsh-win', 'pipe-samp2-tsh-rep-wlean') or
            n.startswith('pipe-samp2-tsh-rep-wlean-s') or
            n.startswith('pipe-samp2-tsh-win-b') or
            (n.startswith('pipe-samp2-tsh-rep-wlean-b') and '-ref' not in n)]


def seal(packet):
    """Called only on this invocation's newly created packet; no existing-packet CLI."""
    m = json.loads((P97 / 'manifest.json').read_text())
    old = copy.deepcopy(m)
    for name in ('pipeline_node.py', 'pipeline_sampler_node.py', 'pipeline_decode_node.py', 'ltx_graph_capture.py'):
        rel = 'source/scripts/' + name
        text = runtime_overlay(name, (P97 / rel).read_text())
        digest = m['files'][rel]
        # Replace precisely its source and custom-node mirror, never unrelated equal files.
        for target, d in m['files'].items():
            if target == rel or (target.startswith('source/custom_nodes/') and d == digest):
                (packet / target).write_text(text)
    (packet / 'source/scripts' / MODULE).write_bytes((HERE / MODULE).read_bytes())
    extra = ['source/scripts/' + MODULE]
    arms = {}
    for base in speed_bases(m):
        original = json.loads((packet / ('graphs/graph-capture-all48-' + base + '.json')).read_text())
        for size in SIZES:
            arm = base + '-speed-s' + size
            rel = 'graphs/graph-capture-all48-' + arm + '.json'
            (packet / rel).write_text(json.dumps(speed_graph(original, size), indent=2, sort_keys=True) + '\n')
            extra.append(rel)
            arms[arm] = {'base': base, 'size': size}
    m['output_size'] = {'environment': 'LTX_OUTPUT_SIZE', 'choices': list(SIZES), 'default': '256x256',
                        'speed_arms': arms, 'references': 'none (speed only)',
                        'tokens': {'256x256': [64, 256], '512x320': [160, 640], '640x384': [240, 960]},
                        'module_sha256': sha(packet / 'source/scripts' / MODULE)}
    checker = packet / 'launch/encoder_runtime_common.py'
    text = (P97 / 'launch/encoder_runtime_common.py').read_text()
    text = replace(text, "'ltx_sampler_batch.py')", "'ltx_sampler_batch.py', 'ltx_output_size_98.py')")
    text = replace(text, "    require(set(manifest['files']) == set(parent['files']) | added,", '    added |= set(' + repr(sorted(extra)) + ')'  + "\n    require(set(manifest['files']) == set(parent['files']) | added,")
    gate = '''    size_contract = manifest['output_size']
    require(size_contract == SIZE_CONTRACT_98, 'Output size contract changed')
    require(size_contract['module_sha256'] == manifest['extension_sha256s']['ltx_output_size_98.py'], 'Size module hash changed')
    for arm, row in size_contract['speed_arms'].items():
        original = json.loads(safe_path(packet, 'graphs/graph-capture-all48-' + row['base'] + '.json').read_text())
        graph = json.loads(safe_path(packet, 'graphs/graph-capture-all48-' + arm + '.json').read_text())
        w, h = map(int, row['size'].split('x'))
        original['356']['inputs'].update(width=w // 2, height=h // 2)
        for key in ('364', '428', '426'):
            original[key]['inputs'].update(output_size=row['size'], speed_only=True)
        require(graph == original, 'Speed graph differs beyond size and admission: ' + arm)
'''
    text = replace(text, '    return manifest\n', gate + '    return manifest\n')
    text += '\nSIZE_CONTRACT_98 = ' + repr(m['output_size']) + '\n'
    checker.write_text(text)
    launcher = packet / 'launch/serve-encoder.py'
    text = (P97 / 'launch/serve-encoder.py').read_text()
    text = replace(text, "    run = common.ROOT / run_name\n", '''    match = re.fullmatch(r'encoder-server-size-98-(two-way|shard4-a|shard3-c)-w([1-4])-b(1|2|4)(-p1)?-d(xpu1|xpu2|xpu1xpu2|xpu2xpu1)-s(256x256|512x320|640x384)(?:-r([2-5]))?', run_name)
    common.require(match is not None, 'Invalid packet 98 run name')
    common.require(os.environ.get('LTX_OUTPUT_SIZE', '256x256') == match[6], 'Run name and LTX_OUTPUT_SIZE differ')
    run = common.ROOT / run_name
''')
    launcher.write_text(text)
    m['files'].update({p: sha(packet / p) for p in list(m['files']) + extra})
    m['extension_sha256s'][MODULE] = sha(packet / 'source/scripts' / MODULE)
    for name in m['startup_tools']:
        m['startup_tools'][name] = m['files']['launch/' + name]
    # Propagate only old extension/startup file hash values, preserving every semantic section.
    pins = {old['files'][p]: m['files'][p] for p in old['files'] if old['files'][p] != m['files'][p]}
    def repin(v):
        if isinstance(v, str): return pins.get(v, v)
        if isinstance(v, list): return [repin(x) for x in v]
        if isinstance(v, dict): return {k: repin(x) for k, x in v.items()}
        return v
    m = repin(m)
    m['preparer_sha256'] = sha(Path(__file__))
    (packet / 'manifest.json').write_text(json.dumps(m, indent=2, sort_keys=True) + '\n')
    (packet / 'STATUS.txt').write_text('Packet 98; prepared offline, never launched. Larger sizes are speed only; no saved output oracle.\n')
    return sha(packet / 'manifest.json')


def main():
    assert sys.executable == '/home/steve/.venvs/ltx25-baseline/bin/python'
    assert not P98.exists() and not P98.is_symlink(), 'Refuse to overwrite packet 98'
    assert sha(P97 / 'manifest.json') == PIN97
    subprocess.run([sys.executable, '-B', str(HERE / 'prepare-graph-capture-runtime.py'), '--output', str(P98)], check=True)
    # The generator must reproduce 97 before applying any overlay.
    baseline = json.loads((P97 / 'manifest.json').read_text())
    generated = json.loads((P98 / 'manifest.json').read_text())
    assert baseline['files'] == generated['files'], 'Lane source no longer reproduces packet 97'
    print(json.dumps({'packet': str(P98), 'manifest_sha256': seal(P98)}, indent=2))


if __name__ == '__main__':
    main()
