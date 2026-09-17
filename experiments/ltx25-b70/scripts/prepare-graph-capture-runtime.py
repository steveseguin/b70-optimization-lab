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
CANDIDATE = 'source/scripts/ltx_na_axis_candidate.py'
CANDIDATE_SRC = 'ltx_na_axis_candidate_v2.py'
# Changing the candidate breaks two files that pin its digest as a literal; if
# they are not repointed the decode node fails to import and simply never
# registers, and the graph is rejected with "Node 'LTXNAAxisDecode' not found".
NA_REPLACED = ((CANDIDATE, CANDIDATE_SRC),
               ('source/scripts/ltx_na_axis_router.py', 'ltx_na_axis_router_v2.py'),
               ('source/scripts/na_axis_decode_node.py', 'na_axis_decode_node_v2.py'))
NA_NODE_COPY = 'source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'
VAE_ADAPTER = 'ltx_graph_vae.py'
VAE_NODE_FILE = 'graph_vae_node.py'
VAE_NODE_DIR = 'ltx_graph_vae_lab'
FUSE_ADAPTER = 'ltx_qkv_fusion.py'
FUSE_NODE_FILE = 'graph_fusion_node.py'
FUSE_NODE_DIR = 'ltx_qkv_fusion_lab'
FUSE_NODE = '424'
TEXT_ADAPTER = 'ltx_graph_text_encoder.py'
TEXT_NODE_FILE = 'graph_text_encoder_node.py'
TEXT_NODE_DIR = 'ltx_graph_text_encoder_lab'
TEXT_NODE = '425'
PIPE_ADAPTER = 'ltx_pipeline.py'
PIPE_NODE_FILE = 'pipeline_node.py'
PIPE_NODE_DIR = 'ltx_pipeline_lab'
PDEC_NODE_FILE = 'pipeline_decode_node.py'
PDEC_NODE_DIR = 'ltx_pipeline_decode_lab'
DECODE_NODE = '426'
CCFG_NODE_FILE = 'concurrent_cfg_node.py'
CCFG_NODE_DIR = 'ltx_concurrent_cfg_lab'
CCFG_NODE = '427'
PSAMP_NODE_FILE = 'pipeline_sampler_node.py'
PSAMP_NODE_DIR = 'ltx_pipeline_sampler_lab'
SAMPLER_NODE = '428'
UPS_ADAPTER = 'ltx_graph_upsampler.py'
UPS_NODE_FILE = 'graph_upsampler_node.py'
UPS_NODE_DIR = 'ltx_graph_upsampler_lab'
UPS_NODE = '429'
SAVE_NODE = '430'
PHASE_NODE_FILE = 'phase_timed_upsampler_node.py'
PHASE_NODE_DIR = 'ltx_phase_timed_upsampler_lab'
SAMPLER_DEPTH = 2
# The sealed sampler chain this node replaces, innermost first.
SAMPLER_CHAIN = ('377', '344', '367', '348', '340', '368', '369')
TEXT_ENCODE_NODE = '364'
PLACEMENT_NODE = '421'
SELECTION = 'all48'
MODES = ('original', 'graph', 'restored')
# Four named arms rather than a cross product, so one process can attribute each
# change separately. Fields: (arm, transformer gate mode, VAE gate mode, decoder).
# 'axis-cache' is the decoder qualified in na-axis-confirm-01 (18 clips, all four
# raw oracles exact, median -83.2 ms), a drop-in for the original VAEDecode node.
# (arm, transformer gate, VAE gate, decoder, projection fusion, chain)
# 'chain' is how many consecutive same-device blocks one graph may hold. The
# c4/c8/c48 ladder measures what the per-block route costs: the blocks, the
# kernels and the order are identical, so every chain length must stay exact.
# (arm, transformer gate, VAE gate, decoder, projection fusion, chain, text gate,
#  encode-ahead pipeline, concurrent dual-CFG, pipelined sampler)
# Result caching is disqualified, so no arm enables it and the cache node is no
# longer shipped. 'pipeline' does not cache: every clip computes its own
# conditioning with the native encode and consumes it once; only the moment the
# work runs changes, so it overlaps the sampler on other cards.
ARMS = (
    ('control',     'original', 'original', 'original',   'original', '1',  'original', 'original', 'original', 'original', 'original', 'original'),
    ('graph',       'graph',    'original', 'axis-cache', 'original', '1',  'original', 'original', 'original', 'original', 'original', 'original'),
    ('graph-c48',   'graph',    'original', 'axis-cache', 'original', '48', 'original', 'original', 'original', 'original', 'original', 'original'),
    ('text',        'original', 'original', 'original',   'original', '1',  'graph',    'original', 'original', 'original', 'original', 'original'),
    ('graph-text',  'graph',    'original', 'axis-cache', 'original', '1',  'graph',    'original', 'original', 'original', 'original', 'original'),
    ('pipe',        'graph',    'original', 'original',   'original', '1',  'graph',    'pipeline', 'original', 'original', 'original', 'original'),
    ('pipe-ccfg',   'graph',    'original', 'original',   'original', '1',  'graph',    'pipeline', 'concurrent', 'original', 'original', 'original'),
    ('graph-fused', 'graph',    'original', 'axis-cache', 'fused',    '1',  'original', 'original', 'original', 'original', 'original', 'original'),
    ('graph-vae',   'graph',    'graph',    'axis-cache', 'original', '1',  'original', 'original', 'original', 'original', 'original', 'original'),
    ('restored',    'restored', 'restored', 'original',   'restored', '1',  'restored', 'original', 'restored', 'original', 'restored', 'original'),
    ('pipe-samp',   'graph',    'original', 'original',   'original', '1',  'graph',    'pipeline', 'original', 'pipeline', 'original', 'original'),
    ('pipe-uptime', 'graph',    'original', 'original',   'original', '1',  'graph',    'pipeline', 'original', 'original', 'timed', 'original'),
    ('pipe-up',     'graph',    'original', 'original',   'original', '1',  'graph',    'pipeline', 'original', 'original', 'graph', 'original'),
    ('pipe-up-save', 'graph',   'original', 'original',   'original', '1',  'graph',    'pipeline-save', 'original', 'original', 'graph', 'original'),
    ('pipe-upphase', 'graph',   'original', 'original',   'original', '1',  'graph',    'pipeline', 'original', 'original', 'original', 'timed'),)
VAE_NODE = '423'


def graph_name(arm):
    return 'graphs/graph-capture-all48-' + arm + '.json'
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
             'source/scripts/ltx_graph_vae.py', 'source/scripts/graph_vae_node.py',
             'source/custom_nodes/ltx_graph_vae_lab/__init__.py',
             'source/scripts/ltx_qkv_fusion.py', 'source/scripts/graph_fusion_node.py',
             'source/custom_nodes/ltx_qkv_fusion_lab/__init__.py',
             'source/scripts/ltx_graph_text_encoder.py', 'source/scripts/graph_text_encoder_node.py',
             'source/custom_nodes/ltx_graph_text_encoder_lab/__init__.py',
             'source/scripts/ltx_pipeline.py', 'source/scripts/pipeline_node.py',
             'source/custom_nodes/ltx_pipeline_lab/__init__.py',
             'source/scripts/pipeline_decode_node.py',
             'source/custom_nodes/ltx_pipeline_decode_lab/__init__.py',
             'source/scripts/concurrent_cfg_node.py',
             'source/custom_nodes/ltx_concurrent_cfg_lab/__init__.py',
             'source/scripts/pipeline_sampler_node.py',
             'source/custom_nodes/ltx_pipeline_sampler_lab/__init__.py',
             'source/scripts/ltx_graph_upsampler.py', 'source/scripts/graph_upsampler_node.py',
             'source/custom_nodes/ltx_graph_upsampler_lab/__init__.py',
             'source/scripts/phase_timed_upsampler_node.py',
             'source/custom_nodes/ltx_phase_timed_upsampler_lab/__init__.py',
             'provenance/graph-capture/parent/launch/encoder_runtime_common.py',
             'provenance/graph-capture/parent/source/scripts/ltx_na_axis_candidate.py',
             'provenance/graph-capture/parent/source/scripts/ltx_na_axis_router.py',
             'provenance/graph-capture/parent/source/scripts/na_axis_decode_node.py',
             'host-residency-13-parent-manifest.json'}
    added |= {'graphs/graph-capture-all48-' + arm + '.json'
              for arm in ('control', 'graph', 'graph-c48', 'text', 'graph-text', 'pipe',
                          'pipe-ccfg', 'graph-fused', 'graph-vae', 'restored', 'pipe-samp',
                          'pipe-uptime', 'pipe-up', 'pipe-up-save', 'pipe-upphase')}
    replaced = ('launch/encoder_runtime_common.py', 'source/scripts/ltx_na_axis_candidate.py',
                'source/scripts/ltx_na_axis_router.py', 'source/scripts/na_axis_decode_node.py')
    node_copy = 'source/custom_nodes/ltx_na_axis_decode_lab/__init__.py'
    for name, digest in parent['files'].items():
        if name in replaced:
            require(manifest['files']['provenance/graph-capture/parent/' + name] == digest,
                    'Original packet13 source changed: ' + name)
        elif name == node_copy:
            require(manifest['files'][name] == manifest['files']['source/scripts/na_axis_decode_node.py'],
                    'NA decode custom-node copy differs from its helper')
        else:
            require(manifest['files'].get(name) == digest, 'Inherited packet13 file changed: ' + name)
    require(set(manifest['files']) == set(parent['files']) | added, 'Packet14 file inventory changed')
    for name in parent['files']:
        if name.startswith(('source/', 'graphs/')) and name not in replaced and name != node_copy:
            require(manifest['files'][name] == parent['files'][name],
                    'Inherited numerical source or original graph changed: ' + name)

    # The NA candidate differs from packet13 by exactly the removed host read.
    original_na = safe_path(packet, 'provenance/graph-capture/parent/source/scripts/ltx_na_axis_candidate.py').read_text()
    current_na = safe_path(packet, 'source/scripts/ltx_na_axis_candidate.py').read_text()
    strip = lambda text: [line.split('#', 1)[0].rstrip() for line in text.splitlines()
                          if line.split('#', 1)[0].strip()]
    diff = [line for line in difflib.unified_diff(strip(original_na), strip(current_na), n=0)
            if line.startswith(('+', '-')) and not line.startswith(('+++', '---'))]
    # Exactly three substantive changes, all required by graph capture and all
    # proven bitwise equivalent on CPU (288 cold-path and 48 cache-hit cases):
    # remove the host read, and give the geometry cache a lifetime longer than
    # one call so the masks are device-resident when capture happens.
    # Exactly these substantive changes, all required by graph capture and all
    # proven bitwise equivalent on CPU (288 cold-path and 48 cache-hit cases):
    # remove the host read of tensor contents, and give the geometry cache a
    # lifetime longer than one call so the masks are device-resident when capture
    # happens. The cache is a keyword-only default rather than a module global
    # because the router admits only the four functions plus two pinned budget
    # constants into its namespace.
    expected_na_diff = [
        '-            kj = torch.arange(int(en.max()), device=device)',
        '+            kj = torch.arange(max(ends), device=device)',
        '+    *,',
        '+    _axis_cache: dict = {},',
        '-    axis_cache = {}',
        '+    axis_cache = _axis_cache',
    ]
    require([line.rstrip() for line in diff] == expected_na_diff,
            'NA candidate differs from packet13 beyond the removed host read and the cache lifetime')
    require(not any('int(en.max())' in line for line in strip(current_na)),
            'NA candidate still reads a tensor for a size')
    require(capture['na_candidate_sha256'] == manifest['extension_sha256s']['ltx_na_axis_candidate.py'] and
            capture['na_router_sha256'] == manifest['extension_sha256s']['ltx_na_axis_router.py'] and
            capture['na_decode_node_sha256'] == manifest['extension_sha256s']['na_axis_decode_node.py'],
            'NA source inventory mismatch')

    # The two files that pin the candidate's digest differ by exactly that
    # literal, and the literal must be the digest the packet actually ships.
    shipped = manifest['extension_sha256s']['ltx_na_axis_candidate.py']
    pins = {'CANDIDATE_SHA': shipped,
            'ROUTER_SHA': manifest['extension_sha256s']['ltx_na_axis_router.py']}
    for name in ('source/scripts/ltx_na_axis_router.py', 'source/scripts/na_axis_decode_node.py'):
        before = safe_path(packet, 'provenance/graph-capture/parent/' + name).read_text()
        after = safe_path(packet, name).read_text()
        d = [line for line in difflib.unified_diff(strip(before), strip(after), n=0)
             if line.startswith(('+', '-')) and not line.startswith(('+++', '---'))]
        # Only digest-pin lines may move, and each must name the shipped file.
        for line in d:
            body = line[1:].strip()
            const = body.split(' =')[0]
            require(re.fullmatch(r"[A-Z_]+_SHA[0-9]* = '[0-9a-f]{64}'", body) is not None and const in pins,
                    'NA source differs from packet13 beyond its digest pins: ' + name)
            if line.startswith('+'):
                require(body == const + " = '" + pins[const] + "'",
                        'Repointed ' + const + ' does not name the shipped file in ' + name)
        for const, want in pins.items():
            if const + ' = ' in after:
                require(after.count(const + " = '" + want + "'") == 1,
                        'Stale ' + const + ' pin in ' + name)
    for node_dir, helper in (('ltx_graph_capture_lab', 'graph_capture_node.py'),
                             ('ltx_graph_vae_lab', 'graph_vae_node.py'),
                             ('ltx_graph_upsampler_lab', 'graph_upsampler_node.py'),
                             ('ltx_phase_timed_upsampler_lab', 'phase_timed_upsampler_node.py'),
                             ('ltx_qkv_fusion_lab', 'graph_fusion_node.py'),
                             ('ltx_graph_text_encoder_lab', 'graph_text_encoder_node.py'),
                             ('ltx_pipeline_lab', 'pipeline_node.py'),
                             ('ltx_pipeline_decode_lab', 'pipeline_decode_node.py'),
                             ('ltx_concurrent_cfg_lab', 'concurrent_cfg_node.py'),
                             ('ltx_pipeline_sampler_lab', 'pipeline_sampler_node.py')):
        require(manifest['files'][f'source/custom_nodes/{node_dir}/__init__.py'] ==
                manifest['files']['source/scripts/' + helper],
                'Graph custom-node copy differs from its helper: ' + node_dir)
    require(capture['adapter_sha256'] == manifest['extension_sha256s']['ltx_graph_capture.py'] and
            capture['node_sha256'] == manifest['extension_sha256s']['graph_capture_node.py'] and
            capture['vae_adapter_sha256'] == manifest['extension_sha256s']['ltx_graph_vae.py'] and
            capture['vae_node_sha256'] == manifest['extension_sha256s']['graph_vae_node.py'] and
            capture['fusion_adapter_sha256'] == manifest['extension_sha256s']['ltx_qkv_fusion.py'] and
            capture['fusion_node_sha256'] == manifest['extension_sha256s']['graph_fusion_node.py'] and
            capture['text_adapter_sha256'] == manifest['extension_sha256s']['ltx_graph_text_encoder.py'] and
            capture['text_node_sha256'] == manifest['extension_sha256s']['graph_text_encoder_node.py'] and
            capture['pipe_adapter_sha256'] ==
            manifest['extension_sha256s']['ltx_pipeline.py'] and
            capture['pipe_node_sha256'] == manifest['extension_sha256s']['pipeline_node.py'] and
            capture['pipe_decode_node_sha256'] ==
            manifest['extension_sha256s']['pipeline_decode_node.py'] and
            capture['concurrent_cfg_node_sha256'] ==
            manifest['extension_sha256s']['concurrent_cfg_node.py'] and
            capture['pipe_sampler_node_sha256'] ==
            manifest['extension_sha256s']['pipeline_sampler_node.py'] and
            capture['upsampler_adapter_sha256'] ==
            manifest['extension_sha256s']['ltx_graph_upsampler.py'] and
            capture['upsampler_node_sha256'] ==
            manifest['extension_sha256s']['graph_upsampler_node.py'] and
            capture['phase_node_sha256'] ==
            manifest['extension_sha256s']['phase_timed_upsampler_node.py'],
            'Graph-capture source inventory mismatch')
    require(capture['fusion_groups'] == [['audio_attn1', ['to_q', 'to_k', 'to_v']],
                                         ['audio_attn2', ['to_k', 'to_v']],
                                         ['audio_to_video_attn', ['to_k', 'to_v']],
                                         ['video_to_audio_attn', ['to_k', 'to_v']]],
            'Fusion group set changed')
    require(capture['vae_captured_methods'] == ['forward_pre_diffusion', 'forward_diff_step'],
            'Captured decoder method set changed')
    require(capture['upsampler_captured_methods'] == ['forward'], 'Captured upsampler method set changed')

    # Gate graphs are the original control recipe plus one restorable gate node.
    control = json.loads(safe_path(packet, 'graphs/host-embedding-control.json').read_text())
    expected_arms = [['control', 'original', 'original', 'original', 'original', '1', 'original', 'original', 'original', 'original', 'original', 'original'],
                     ['graph', 'graph', 'original', 'axis-cache', 'original', '1', 'original', 'original', 'original', 'original', 'original', 'original'],
                     ['graph-c48', 'graph', 'original', 'axis-cache', 'original', '48', 'original', 'original', 'original', 'original', 'original', 'original'],
                     ['text', 'original', 'original', 'original', 'original', '1', 'graph', 'original', 'original', 'original', 'original', 'original'],
                     ['graph-text', 'graph', 'original', 'axis-cache', 'original', '1', 'graph', 'original', 'original', 'original', 'original', 'original'],
                     ['pipe', 'graph', 'original', 'original', 'original', '1', 'graph', 'pipeline', 'original', 'original', 'original', 'original'],
                     ['pipe-ccfg', 'graph', 'original', 'original', 'original', '1', 'graph', 'pipeline', 'concurrent', 'original', 'original', 'original'],
                     ['graph-fused', 'graph', 'original', 'axis-cache', 'fused', '1', 'original', 'original', 'original', 'original', 'original', 'original'],
                     ['graph-vae', 'graph', 'graph', 'axis-cache', 'original', '1', 'original', 'original', 'original', 'original', 'original', 'original'],
                     ['restored', 'restored', 'restored', 'original', 'restored', '1', 'restored', 'original', 'restored', 'original', 'restored', 'original'],
                     ['pipe-samp', 'graph', 'original', 'original', 'original', '1', 'graph', 'pipeline', 'original', 'pipeline', 'original', 'original'],
                     ['pipe-uptime', 'graph', 'original', 'original', 'original', '1', 'graph', 'pipeline', 'original', 'original', 'timed', 'original'],
                     ['pipe-up', 'graph', 'original', 'original', 'original', '1', 'graph', 'pipeline', 'original', 'original', 'graph', 'original'],
                     ['pipe-up-save', 'graph', 'original', 'original', 'original', '1', 'graph', 'pipeline-save', 'original', 'original', 'graph', 'original'],
                     ['pipe-upphase', 'graph', 'original', 'original', 'original', '1', 'graph', 'pipeline', 'original', 'original', 'original', 'timed']]
    require(capture['arms'] == expected_arms, 'Graph-capture arm set changed')
    expected_graphs = []
    for (arm, mode, vae_mode, decode, fuse_mode, chain, text_mode, pipe_mode, ccfg_mode,
         samp_mode, ups_mode, phase_mode) in expected_arms:
        name = 'graphs/graph-capture-all48-' + arm + '.json'
        expected_graphs.append(name)
        graph = json.loads(safe_path(packet, name).read_text())
        # Undo the gate rewiring before comparing, innermost edge first.
        if pipe_mode == 'pipeline-save':
            require('370' not in graph and '75' not in graph, 'Save-behind arm still carries the video assembly')
            require(graph.pop('430') == {'class_type': 'LTXPipelineSaveRecord', 'inputs': {
                    'saved_file': ['426', 4], 'run_name': 'assign-unique-request-name'}},
                    'Save-record node changed')
            graph['370'] = copy.deepcopy(control['370'])
            graph['75'] = copy.deepcopy(control['75'])
            graph['370']['inputs']['images'] = ['426', 0]
            graph['370']['inputs']['audio'] = ['426', 1]
        if phase_mode != 'original':
            require(samp_mode == 'original', 'Phase timing and the pipelined sampler cannot combine')
            require(graph['348'] == {'class_type': 'LTXPhaseTimedUpsampler', 'inputs': {
                    'samples': ['367', 0], 'upscale_model': ['429', 0], 'vae': ['420', 2],
                    'mode': phase_mode, 'run_name': 'assign-unique-request-name'}},
                    'Phase-timed upsampler node changed')
            graph['348'] = {'class_type': 'LTXVLatentUpsampler', 'inputs': {
                'samples': ['367', 0], 'upscale_model': ['429', 0], 'vae': ['420', 2]}}
        ups_consumer = '428' if samp_mode != 'original' else '348'
        require(graph[ups_consumer]['inputs']['upscale_model'] == ['429', 0],
                'Upsampler gate edge changed')
        graph[ups_consumer]['inputs']['upscale_model'] = ['420', 4]
        require(graph.pop('429') == {'class_type': 'LTXUpsamplerGraphGate', 'inputs': {
                'upscale_model': ['420', 4], 'mode': ups_mode,
                'run_name': 'assign-unique-request-name'}}, 'Upsampler gate node changed')
        if pipe_mode != 'original':
            require('421' not in graph, 'Pipelined arm still carries the placement observer')
            require(graph['365']['inputs']['negative'] == ['364', 0] and
                    graph['365']['inputs']['positive'] == ['364', 0],
                    'Pipelined arm conditioning edge changed')
            graph['365']['inputs']['negative'] = ['421', 0]
            graph['365']['inputs']['positive'] = ['421', 0]
            graph['421'] = {'class_type': 'LTXHostEmbeddingPlacementCheck', 'inputs': {
                'clip': ['420', 1], 'conditioning': ['364', 0], 'encoder_mode': 'control',
                'run_name': 'assign-unique-request-name'}}
        if samp_mode != 'original':
            require(all(k not in graph for k in ('377', '344', '367', '348', '340', '368', '369')),
                    'Pipelined-sampler arm still carries the sealed sampler chain')
            require(graph.pop('428') == {'class_type': 'LTXPipelineSampler', 'inputs': {
                    'noise_a': ['339', 0], 'guider_a': ['388', 0], 'sampler_a': ['352', 0],
                    'sigmas_a': ['404', 0], 'noise_b': ['338', 0], 'guider_b': ['391', 0],
                    'sampler_b': ['341', 0], 'sigmas_b': ['395', 0],
                    'video_latent': ['356', 0], 'audio_latent': ['366', 0],
                    'upscale_model': ['420', 4], 'vae': ['420', 2],
                    'mode': samp_mode, 'clip_index': 0, 'depth': 2,
                    'run_name': 'assign-unique-request-name'}}, 'Pipelined sampler node changed')
            require(graph['426']['inputs']['video_latent'] == ['428', 0] and
                    graph['426']['inputs']['audio_latent'] == ['428', 1] and
                    graph['426']['inputs']['upstream_depth'] == 2,
                    'Pipelined sampler edges changed')
            graph['426']['inputs']['video_latent'] = ['369', 0]
            graph['426']['inputs']['audio_latent'] = ['369', 1]
            graph['426']['inputs']['upstream_depth'] = 0
            graph['377'] = {'class_type': 'LTXVConcatAVLatent',
                            'inputs': {'audio_latent': ['366', 0], 'video_latent': ['356', 0]}}
            graph['344'] = {'class_type': 'SamplerCustomAdvanced', 'inputs': {
                'guider': ['388', 0], 'latent_image': ['377', 0], 'noise': ['339', 0],
                'sampler': ['352', 0], 'sigmas': ['404', 0]}}
            graph['367'] = {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['344', 0]}}
            graph['348'] = {'class_type': 'LTXVLatentUpsampler', 'inputs': {
                'samples': ['367', 0], 'upscale_model': ['420', 4], 'vae': ['420', 2]}}
            graph['340'] = {'class_type': 'LTXVConcatAVLatent',
                            'inputs': {'audio_latent': ['367', 1], 'video_latent': ['348', 0]}}
            graph['368'] = {'class_type': 'SamplerCustomAdvanced', 'inputs': {
                'guider': ['391', 0], 'latent_image': ['340', 0], 'noise': ['338', 0],
                'sampler': ['341', 0], 'sigmas': ['395', 0]}}
            graph['369'] = {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['368', 0]}}
        if pipe_mode != 'original':
            require('374' not in graph and '358' not in graph,
                    'Pipelined arm still carries the separate decode nodes')
            require(graph.pop('426') == {'class_type': 'LTXPipelineDecode', 'inputs': {
                    'vae': ['423', 0], 'audio_vae': ['420', 3],
                    'video_latent': ['369', 0], 'audio_latent': ['369', 1],
                    'mode': pipe_mode, 'clip_index': 0, 'depth': 1, 'upstream_depth': 0,
                    'run_name': 'assign-unique-request-name'}}, 'Pipelined decode node changed')
            require(graph['370']['inputs']['images'] == ['426', 0] and
                    graph['370']['inputs']['audio'] == ['426', 1] and
                    graph['414']['inputs']['images'] == ['426', 0] and
                    graph['414']['inputs']['audio'] == ['426', 1] and
                    graph['414']['inputs']['video_latent'] == ['426', 2] and
                    graph['414']['inputs']['audio_latent'] == ['426', 3],
                    'Pipelined decode edges changed')
            graph['370']['inputs']['images'] = ['374', 0]
            graph['370']['inputs']['audio'] = ['358', 0]
            graph['414']['inputs']['images'] = ['374', 0]
            graph['414']['inputs']['audio'] = ['358', 0]
            graph['414']['inputs']['video_latent'] = ['369', 0]
            graph['414']['inputs']['audio_latent'] = ['369', 1]
            graph['358'] = {'class_type': 'LTXVAudioVAEDecode',
                            'inputs': {'audio_vae': ['420', 3], 'samples': ['369', 1]}}
            graph['374'] = {'class_type': 'VAEDecode',
                            'inputs': {'samples': ['369', 0], 'vae': ['423', 0]}}
        require(graph['364']['class_type'] == 'LTXPipelineTextEncode' and
                graph['364']['inputs']['mode'] == ('original' if pipe_mode == 'original' else 'pipeline') and
                graph['364']['inputs']['clip_index'] == 0 and
                graph['364']['inputs']['depth'] == 1 and
                graph['364']['inputs']['run_name'] == 'assign-unique-request-name',
                'Pipeline text-encode node changed')
        graph['364'] = {'class_type': 'CLIPTextEncode', 'inputs': {
            'clip': graph['364']['inputs']['clip'], 'text': graph['364']['inputs']['text']}}
        require(graph['364']['inputs']['clip'] == ['425', 0], 'Text-encoder gate edge changed')
        graph['364']['inputs']['clip'] = ['420', 1]
        require(graph.pop('425') == {'class_type': 'LTXTextEncoderGraphGate', 'inputs': {
                'clip': ['420', 1], 'mode': text_mode,
                'run_name': 'assign-unique-request-name'}}, 'Text-encoder gate node changed')
        require(graph['422']['inputs']['model'] == ['427', 0], 'Concurrent-CFG edge changed')
        require(graph.pop('427') == {'class_type': 'LTXConcurrentCFG', 'inputs': {
                'model': ['424', 0], 'mode': ccfg_mode,
                'run_name': 'assign-unique-request-name'}}, 'Concurrent-CFG node changed')
        graph['422']['inputs']['model'] = ['424', 0]
        require(graph['422']['inputs']['model'] == ['424', 0], 'Fusion gate edge changed')
        graph['422']['inputs']['model'] = ['420', 0]
        require(graph.pop('422') == {'class_type': 'LTXGraphCaptureGate', 'inputs': {
                'model': ['420', 0], 'mode': mode, 'selection': 'all48', 'chain': chain,
                'run_name': 'assign-unique-request-name'}}, 'Graph-capture gate node changed')
        require(graph.pop('423') == {'class_type': 'LTXVAEGraphGate', 'inputs': {
                'vae': ['420', 2], 'mode': vae_mode,
                'run_name': 'assign-unique-request-name'}}, 'VAE graph gate node changed')
        require(graph.pop('424') == {'class_type': 'LTXFusionGate', 'inputs': {
                'model': ['420', 0], 'mode': fuse_mode,
                'run_name': 'assign-unique-request-name'}}, 'Fusion gate node changed')
        for node in ('388', '391'):
            require(graph[node]['inputs']['model'] == ['422', 0], 'Graph-capture edge changed')
            graph[node]['inputs']['model'] = ['420', 0]
        if decode == 'original':
            require(graph['374'] == {'class_type': 'VAEDecode',
                                     'inputs': {'samples': ['369', 0], 'vae': ['423', 0]}},
                    'Original decode node changed')
        else:
            require(graph['374'] == {'class_type': 'LTXNAAxisDecode', 'inputs': {
                    'samples': ['369', 0], 'vae': ['423', 0], 'mode': 'axis-cache',
                    'run_name': 'assign-unique-request-name'}}, 'Axis-cache decode node changed')
        graph['374'] = {'class_type': 'VAEDecode',
                        'inputs': {'samples': ['369', 0], 'vae': ['420', 2]}}
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
                                       "              'ltx_graph_capture.py', 'graph_capture_node.py',\n"
                                       "              'ltx_graph_vae.py', 'graph_vae_node.py',\n"
                                       "              'ltx_qkv_fusion.py', 'graph_fusion_node.py',\n"
                                       "              'ltx_graph_text_encoder.py', 'graph_text_encoder_node.py',\n"
                                       "              'ltx_pipeline.py', 'pipeline_node.py',\n"
                                       "              'pipeline_decode_node.py',\n"
                                       "              'concurrent_cfg_node.py',\n"
                                       "              'pipeline_sampler_node.py',\n"
                                       "              'ltx_graph_upsampler.py', 'graph_upsampler_node.py',\n"
                                       "              'phase_timed_upsampler_node.py')", 1)
    old_nodes = "         'ltx_host_embedding_lab': 'host_embedding_resident_node.py'}"
    require(updated.count(old_nodes) == 1, 'Unexpected NODES layout')
    updated = updated.replace(old_nodes, "         'ltx_host_embedding_lab': 'host_embedding_resident_node.py',\n"
                                         "         'ltx_graph_capture_lab': 'graph_capture_node.py',\n"
                                         "         'ltx_graph_vae_lab': 'graph_vae_node.py',\n"
                                         "         'ltx_qkv_fusion_lab': 'graph_fusion_node.py',\n"
                                         "         'ltx_graph_text_encoder_lab': 'graph_text_encoder_node.py',\n"
                                         "         'ltx_pipeline_lab': 'pipeline_node.py',\n"
                                         "         'ltx_pipeline_decode_lab': 'pipeline_decode_node.py',\n"
                                         "         'ltx_concurrent_cfg_lab': 'concurrent_cfg_node.py',\n"
                                         "         'ltx_pipeline_sampler_lab': 'pipeline_sampler_node.py',\n"
                                         "         'ltx_graph_upsampler_lab': 'graph_upsampler_node.py',\n"
                                         "         'ltx_phase_timed_upsampler_lab': 'phase_timed_upsampler_node.py'}", 1)
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
    cand_prov = staging / PROV / 'source/scripts'
    cand_prov.mkdir(parents=True, exist_ok=False)
    for packet_path, lane_name in NA_REPLACED:
        shutil.copyfile(parent / packet_path, cand_prov / Path(packet_path).name)
        fixed = LANE / 'scripts' / lane_name
        require(fixed.is_file(), 'Missing prepared NA source: ' + lane_name)
        ast.parse(fixed.read_text())
        shutil.copyfile(fixed, staging / packet_path)
    # The custom-node copy must stay byte-identical to its helper.
    shutil.copyfile(LANE / 'scripts' / 'na_axis_decode_node_v2.py', staging / NA_NODE_COPY)
    # Every pinned digest in the NA chain must name the file actually shipped.
    # The chain is candidate -> router -> node; a stale pin does not fail loudly,
    # it makes the custom node fail to import and silently never register, and
    # the graph is then rejected with "Node 'LTXNAAxisDecode' not found".
    pins = {'CANDIDATE_SHA': sha(staging / CANDIDATE),
            'ROUTER_SHA': sha(staging / 'source/scripts/ltx_na_axis_router.py')}
    for packet_path, _ in NA_REPLACED[1:]:
        text = (staging / packet_path).read_text()
        for const, want in pins.items():
            if const + ' = ' in text:
                require(text.count(const + " = '" + want + "'") == 1,
                        'Stale ' + const + ' pin in ' + packet_path)
    shutil.copyfile(staging / 'source/scripts/na_axis_decode_node.py', staging / NA_NODE_COPY)
    shutil.copyfile(parent / 'manifest.json', staging / PARENT_MANIFEST_FILE)
    (staging / CHECKER).write_text(checker_new)

    for src_name, dir_name in ((ADAPTER, None), (NODE, NODE_DIR),
                               (VAE_ADAPTER, None), (VAE_NODE_FILE, VAE_NODE_DIR),
                               (FUSE_ADAPTER, None), (FUSE_NODE_FILE, FUSE_NODE_DIR),
                               (TEXT_ADAPTER, None), (TEXT_NODE_FILE, TEXT_NODE_DIR),
                               (PIPE_ADAPTER, None), (PIPE_NODE_FILE, PIPE_NODE_DIR),
                               (PDEC_NODE_FILE, PDEC_NODE_DIR), (CCFG_NODE_FILE, CCFG_NODE_DIR),
                               (PSAMP_NODE_FILE, PSAMP_NODE_DIR),
                               (UPS_ADAPTER, None), (UPS_NODE_FILE, UPS_NODE_DIR),
                               (PHASE_NODE_FILE, PHASE_NODE_DIR)):
        src = LANE / 'scripts' / src_name
        require(src.is_file(), 'Missing prepared source: ' + str(src))
        ast.parse(src.read_text())
        shutil.copyfile(src, staging / 'source/scripts' / src_name)
        if dir_name is not None:
            target = staging / 'source/custom_nodes' / dir_name
            target.mkdir(exist_ok=False)
            shutil.copyfile(src, target / '__init__.py')

    control = json.loads((staging / BASE_GRAPH).read_text())
    require(control['374'] == {'class_type': 'VAEDecode',
                               'inputs': {'samples': ['369', 0], 'vae': ['420', 2]}},
            'Unexpected original video decode node')
    for (arm, mode, vae_mode, decode, fuse_mode, chain, text_mode, pipe_mode, ccfg_mode,
         samp_mode, ups_mode, phase_mode) in ARMS:
        graph = copy.deepcopy(control)
        require(graph['348']['inputs']['upscale_model'] == ['420', 4], 'Unexpected upsampler edge')
        graph[UPS_NODE] = {'class_type': 'LTXUpsamplerGraphGate', 'inputs': {
            'upscale_model': ['420', 4], 'mode': ups_mode, 'run_name': 'assign-unique-request-name'}}
        graph['348']['inputs']['upscale_model'] = [UPS_NODE, 0]
        if phase_mode != 'original':
            require(samp_mode == 'original', 'Phase timing and the pipelined sampler cannot combine')
            graph['348'] = {'class_type': 'LTXPhaseTimedUpsampler', 'inputs': {
                'samples': ['367', 0], 'upscale_model': [UPS_NODE, 0], 'vae': ['420', 2],
                'mode': phase_mode, 'run_name': 'assign-unique-request-name'}}
        require(graph['364']['inputs']['clip'] == ['420', 1], 'Unexpected control text-encode edge')
        require(graph['364']['class_type'] == 'CLIPTextEncode', 'Unexpected control text-encode node')
        prompt_text = graph[TEXT_ENCODE_NODE]['inputs']['text']
        graph[TEXT_NODE] = {'class_type': 'LTXTextEncoderGraphGate', 'inputs': {
            'clip': ['420', 1], 'mode': text_mode, 'run_name': 'assign-unique-request-name'}}
        graph['364']['inputs']['clip'] = [TEXT_NODE, 0]
        # The encode node itself becomes the cache-capable one in every arm, so
        # the arms differ only by mode. 'original' calls the native node.
        graph[TEXT_ENCODE_NODE] = {'class_type': 'LTXPipelineTextEncode', 'inputs': {
            'clip': [TEXT_NODE, 0], 'text': prompt_text,
            'mode': 'original' if pipe_mode == 'original' else 'pipeline',
            'clip_index': 0, 'depth': 1, 'run_name': 'assign-unique-request-name'}}
        graph['422'] = {'class_type': 'LTXGraphCaptureGate', 'inputs': {
            'model': ['420', 0], 'mode': mode, 'selection': SELECTION, 'chain': chain,
            'run_name': 'assign-unique-request-name'}}
        for node in ('388', '391'):
            require(graph[node]['inputs']['model'] == ['420', 0], 'Unexpected control graph edge')
            graph[node]['inputs']['model'] = ['422', 0]
        graph[VAE_NODE] = {'class_type': 'LTXVAEGraphGate', 'inputs': {
            'vae': ['420', 2], 'mode': vae_mode, 'run_name': 'assign-unique-request-name'}}
        graph[FUSE_NODE] = {'class_type': 'LTXFusionGate', 'inputs': {
            'model': ['420', 0], 'mode': fuse_mode, 'run_name': 'assign-unique-request-name'}}
        graph[CCFG_NODE] = {'class_type': 'LTXConcurrentCFG', 'inputs': {
            'model': [FUSE_NODE, 0], 'mode': ccfg_mode,
            'run_name': 'assign-unique-request-name'}}
        graph['422']['inputs']['model'] = [CCFG_NODE, 0]
        if pipe_mode != 'original':
            # LTXHostEmbeddingPlacementCheck requires exactly one new completed
            # encoding per request, and a clip served from cache performs none.
            # It is a pure pass-through observer (`return (conditioning,)`), so
            # dropping it changes no arithmetic, and the four raw oracles still
            # gate the arm. Only arms that skip the encode lose the observer.
            require(graph['365']['inputs']['negative'] == [PLACEMENT_NODE, 0] and
                    graph['365']['inputs']['positive'] == [PLACEMENT_NODE, 0],
                    'Unexpected placement-check consumer wiring')
            graph['365']['inputs']['negative'] = [TEXT_ENCODE_NODE, 0]
            graph['365']['inputs']['positive'] = [TEXT_ENCODE_NODE, 0]
            del graph[PLACEMENT_NODE]
        if pipe_mode != 'original':
            # Video and audio are decoded and emitted together, with their
            # latents, so a prompt's four oracle inputs always describe the same
            # clip. The plain VAEDecode is used: the axis-cache decoder memoises
            # mask tensors and is retired under the no-caching rule.
            require(graph['370']['inputs']['images'] == ['374', 0] and
                    graph['370']['inputs']['audio'] == ['358', 0],
                    'Unexpected video assembly wiring')
            require(graph['414']['inputs']['images'] == ['374', 0] and
                    graph['414']['inputs']['audio'] == ['358', 0] and
                    graph['414']['inputs']['video_latent'] == ['369', 0] and
                    graph['414']['inputs']['audio_latent'] == ['369', 1],
                    'Unexpected oracle capture wiring')
            graph[DECODE_NODE] = {'class_type': 'LTXPipelineDecode', 'inputs': {
                'vae': [VAE_NODE, 0], 'audio_vae': ['420', 3],
                'video_latent': ['369', 0], 'audio_latent': ['369', 1],
                'mode': pipe_mode, 'clip_index': 0, 'depth': 1, 'upstream_depth': 0,
                'run_name': 'assign-unique-request-name'}}
            graph['370']['inputs']['images'] = [DECODE_NODE, 0]
            graph['370']['inputs']['audio'] = [DECODE_NODE, 1]
            graph['414']['inputs']['images'] = [DECODE_NODE, 0]
            graph['414']['inputs']['audio'] = [DECODE_NODE, 1]
            graph['414']['inputs']['video_latent'] = [DECODE_NODE, 2]
            graph['414']['inputs']['audio_latent'] = [DECODE_NODE, 3]
            del graph['374'], graph['358']
            if pipe_mode == 'pipeline-save':
                # The decode worker writes the preview itself; the prompt only
                # records the path. The video assembly and SaveVideo nodes go.
                graph[SAVE_NODE] = {'class_type': 'LTXPipelineSaveRecord', 'inputs': {
                    'saved_file': [DECODE_NODE, 4], 'run_name': 'assign-unique-request-name'}}
                del graph['370'], graph['75']
            if samp_mode != 'original':
                # One node replaces the sealed sampler chain and runs it on a worker,
                # so two clips sample at once: one occupies xpu:1's blocks while the
                # other occupies xpu:0's. Each clip is still sampled exactly once, by
                # its own sampler, from its own conditioning and its own noise.
                require(all(k in graph for k in SAMPLER_CHAIN), 'Sampler chain node missing')
                require(graph['377']['inputs'] == {'audio_latent': ['366', 0],
                                                   'video_latent': ['356', 0]},
                        'Stage-A latent assembly changed')
                require(graph['344']['inputs'] == {'guider': ['388', 0], 'latent_image': ['377', 0],
                                                   'noise': ['339', 0], 'sampler': ['352', 0],
                                                   'sigmas': ['404', 0]}, 'Stage-A sampler changed')
                require(graph['348']['inputs'] == {'samples': ['367', 0],
                                                   'upscale_model': [UPS_NODE, 0],
                                                   'vae': ['420', 2]}, 'Latent upsampler changed')
                require(graph['368']['inputs'] == {'guider': ['391', 0], 'latent_image': ['340', 0],
                                                   'noise': ['338', 0], 'sampler': ['341', 0],
                                                   'sigmas': ['395', 0]}, 'Stage-B sampler changed')
                graph[SAMPLER_NODE] = {'class_type': 'LTXPipelineSampler', 'inputs': {
                    'noise_a': ['339', 0], 'guider_a': ['388', 0], 'sampler_a': ['352', 0],
                    'sigmas_a': ['404', 0], 'noise_b': ['338', 0], 'guider_b': ['391', 0],
                    'sampler_b': ['341', 0], 'sigmas_b': ['395', 0],
                    'video_latent': ['356', 0], 'audio_latent': ['366', 0],
                    'upscale_model': [UPS_NODE, 0], 'vae': ['420', 2],
                    'mode': samp_mode, 'clip_index': 0, 'depth': SAMPLER_DEPTH,
                    'run_name': 'assign-unique-request-name'}}
                graph[DECODE_NODE]['inputs']['video_latent'] = [SAMPLER_NODE, 0]
                graph[DECODE_NODE]['inputs']['audio_latent'] = [SAMPLER_NODE, 1]
                graph[DECODE_NODE]['inputs']['upstream_depth'] = SAMPLER_DEPTH
                for node_id in SAMPLER_CHAIN:
                    del graph[node_id]
        elif decode == 'original':
            graph['374'] = {'class_type': 'VAEDecode',
                            'inputs': {'samples': ['369', 0], 'vae': [VAE_NODE, 0]}}
        else:
            graph['374'] = {'class_type': 'LTXNAAxisDecode', 'inputs': {
                'samples': ['369', 0], 'vae': [VAE_NODE, 0], 'mode': decode,
                'run_name': 'assign-unique-request-name'}}
        path = staging / graph_name(arm)
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
             PROV + 'launch/encoder_runtime_common.py',
             PARENT_MANIFEST_FILE}
    added |= {PROV + 'source/scripts/' + Path(pp).name for pp, _ in NA_REPLACED}
    added |= {graph_name(a[0]) for a in ARMS}
    added |= {'source/scripts/' + VAE_ADAPTER, 'source/scripts/' + VAE_NODE_FILE,
              f'source/custom_nodes/{VAE_NODE_DIR}/__init__.py',
              'source/scripts/' + FUSE_ADAPTER, 'source/scripts/' + FUSE_NODE_FILE,
              f'source/custom_nodes/{FUSE_NODE_DIR}/__init__.py',
              'source/scripts/' + TEXT_ADAPTER, 'source/scripts/' + TEXT_NODE_FILE,
              f'source/custom_nodes/{TEXT_NODE_DIR}/__init__.py',
              'source/scripts/' + PIPE_ADAPTER, 'source/scripts/' + PIPE_NODE_FILE,
              f'source/custom_nodes/{PIPE_NODE_DIR}/__init__.py',
              'source/scripts/' + PDEC_NODE_FILE,
              f'source/custom_nodes/{PDEC_NODE_DIR}/__init__.py',
              'source/scripts/' + CCFG_NODE_FILE,
              f'source/custom_nodes/{CCFG_NODE_DIR}/__init__.py',
              'source/scripts/' + PSAMP_NODE_FILE,
              f'source/custom_nodes/{PSAMP_NODE_DIR}/__init__.py',
              'source/scripts/' + UPS_ADAPTER, 'source/scripts/' + UPS_NODE_FILE,
              f'source/custom_nodes/{UPS_NODE_DIR}/__init__.py',
              'source/scripts/' + PHASE_NODE_FILE,
              f'source/custom_nodes/{PHASE_NODE_DIR}/__init__.py'}
    require(set(files) == set(parent_manifest['files']) | added, 'Unexpected packet14 inventory')
    for name, digest in parent_manifest['files'].items():
        if name == CHECKER:
            require(files[PROV + 'launch/encoder_runtime_common.py'] == digest, 'Provenance copy differs')
            require(files[name] != digest, 'Checker is unchanged')
        elif name in {pp for pp, _ in NA_REPLACED} or name == NA_NODE_COPY:
            if name != NA_NODE_COPY:
                require(files[PROV + 'source/scripts/' + Path(name).name] == digest,
                        'NA provenance copy differs: ' + name)
            require(files[name] != digest, 'NA source is unchanged: ' + name)
        else:
            require(files[name] == digest, 'Inherited file drifted: ' + name)
    for src_name, dir_name in ((NODE, NODE_DIR), (VAE_NODE_FILE, VAE_NODE_DIR),
                               (FUSE_NODE_FILE, FUSE_NODE_DIR), (TEXT_NODE_FILE, TEXT_NODE_DIR),
                               (PIPE_NODE_FILE, PIPE_NODE_DIR), (PDEC_NODE_FILE, PDEC_NODE_DIR),
                               (CCFG_NODE_FILE, CCFG_NODE_DIR), (PSAMP_NODE_FILE, PSAMP_NODE_DIR),
                               (UPS_NODE_FILE, UPS_NODE_DIR), (PHASE_NODE_FILE, PHASE_NODE_DIR)):
        require(files[f'source/custom_nodes/{dir_name}/__init__.py'] == files['source/scripts/' + src_name],
                'Custom-node copy differs from helper: ' + dir_name)

    extensions = dict(parent_manifest['extension_sha256s'])
    for src_name in (ADAPTER, NODE, VAE_ADAPTER, VAE_NODE_FILE, FUSE_ADAPTER, FUSE_NODE_FILE,
                     TEXT_ADAPTER, TEXT_NODE_FILE, PIPE_ADAPTER, PIPE_NODE_FILE, PDEC_NODE_FILE,
                     CCFG_NODE_FILE, PSAMP_NODE_FILE, UPS_ADAPTER, UPS_NODE_FILE, PHASE_NODE_FILE):
        extensions[src_name] = files['source/scripts/' + src_name]
    for packet_path, _ in NA_REPLACED:
        extensions[Path(packet_path).name] = files[packet_path]
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
            'graphs': [graph_name(a[0]) for a in ARMS],
            'arms': [list(a) for a in ARMS],
            'vae_adapter_sha256': extensions[VAE_ADAPTER], 'vae_node_sha256': extensions[VAE_NODE_FILE],
            'fusion_adapter_sha256': extensions[FUSE_ADAPTER], 'fusion_node_sha256': extensions[FUSE_NODE_FILE],
            'text_adapter_sha256': extensions[TEXT_ADAPTER], 'text_node_sha256': extensions[TEXT_NODE_FILE],
            'pipe_adapter_sha256': extensions[PIPE_ADAPTER],
            'pipe_node_sha256': extensions[PIPE_NODE_FILE],
            'pipe_decode_node_sha256': extensions[PDEC_NODE_FILE],
            'concurrent_cfg_node_sha256': extensions[CCFG_NODE_FILE],
            'pipe_sampler_node_sha256': extensions[PSAMP_NODE_FILE],
            'upsampler_adapter_sha256': extensions[UPS_ADAPTER],
            'upsampler_node_sha256': extensions[UPS_NODE_FILE],
            'upsampler_captured_methods': ['forward'],
            'phase_node_sha256': extensions[PHASE_NODE_FILE],
            'fusion_groups': [[g[0], list(g[1])] for g in __import__('ltx_qkv_fusion_groups').GROUPS]
                             if False else [['audio_attn1', ['to_q', 'to_k', 'to_v']],
                                            ['audio_attn2', ['to_k', 'to_v']],
                                            ['audio_to_video_attn', ['to_k', 'to_v']],
                                            ['video_to_audio_attn', ['to_k', 'to_v']]],
            'vae_captured_methods': ['forward_pre_diffusion', 'forward_diff_step'],
            'vae_not_captured': 'NADiffusionDecoder.forward draws x_t from a generator and stays eager',
            'na_candidate_sha256': extensions['ltx_na_axis_candidate.py'],
            'na_router_sha256': extensions['ltx_na_axis_router.py'],
            'na_decode_node_sha256': extensions['na_axis_decode_node.py'],
            'na_pinned_digest_repointed': True,
            'na_candidate_change': 'int(en.max()) -> max(ends): the window ends are already a host tuple of '
                                   'ints, and a tensor read inside a graph capture returns unexecuted memory '
                                   'and was being used as an allocation size',
            'axis_cache_provenance': 'na-axis-confirm-01: 18 clips, all four raw oracles exact, '
                                     'median decoder effect -83.2 ms; drop-in for node 374',
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
