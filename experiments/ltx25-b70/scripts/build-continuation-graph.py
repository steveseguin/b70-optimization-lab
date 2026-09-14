#!/usr/bin/env python3
"""Construct inactive LTX continuation modules; standard library only, no submission.

The external IMAGE edge is a contract for a future float-anchor provider, not an
implemented Comfy node. Output is an envelope, deliberately not a /prompt body.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re

LANE = Path(__file__).resolve().parents[1]
BASE = LANE / 'data/speed-resident-split-api.json'
BASE_SHA256 = 'fa3868afb3d81056a776d256e68ed5e239cb501bd8b254af7ff2d33339d742d7'
COMFY_COMMIT = '19e1058f4c445ef74047e77a23f9ca7684c1e4b6'
SOURCE_HASHES = {
    'nodes.py': 'dddf275f6dbcbd1a9cbdc02ebee2bad86bf022cc968c58a3f14cb26a2d08926e',
    'comfy_extras/nodes_custom_sampler.py': 'b0ba1521c72475e06fed15db004274ed7c8bb2bf73f1d58849faf6f9f9d264fe',
    'comfy_extras/nodes_video.py': '5879633287808ba2dac6753bcbc90acf8d73c72e8df1d0a9755a4ab70e712a0d',
    'comfy_extras/nodes_lt_audio.py': '7bb3117d159135e9049d589bc457433c8b88ea8cee35c399dd2959524304258f',
    'comfy_extras/nodes_lt.py': '01575b886e9abacd08c7ce39e7bde9ef7c7cc8f17063d726e2bf4a320a512d95',
    'comfy_extras/nodes_lt_upsampler.py': 'c9f225e4c54f19f31452016fd4e546119d69e9dec37b60a9dc4ddf133848a892',
}
# Narrow schemas for precisely this graph, not a replacement Comfy validator.
# Scalar enum choices are frozen to this workload. All listed inputs required.
SPECS = {
    'CLIPTextEncode': ({'clip': 'CLIP', 'text': 'STRING'}, ['CONDITIONING']),
    'LTXVDualCFGGuider': ({'model': 'MODEL', 'positive': 'CONDITIONING', 'negative': 'CONDITIONING', 'video_cfg': 'FLOAT', 'audio_cfg': 'FLOAT'}, ['GUIDER']),
    'LTXResidentComponents': ({'placement': ('split',)}, ['MODEL', 'CLIP', 'VAE', 'VAE', 'LATENT_UPSCALE_MODEL']),
    'LTXVConditioning': ({'positive': 'CONDITIONING', 'negative': 'CONDITIONING', 'frame_rate': 'FLOAT'}, ['CONDITIONING', 'CONDITIONING']),
    'EmptyLTXVLatentVideo': ({'width': 'INT', 'height': 'INT', 'length': 'INT', 'batch_size': 'INT'}, ['LATENT']),
    'LTXVEmptyLatentAudio': ({'audio_vae': 'VAE', 'frames_number': 'INT', 'frame_rate': 'FLOAT', 'batch_size': 'INT'}, ['LATENT']),
    'LTXVConcatAVLatent': ({'video_latent': 'LATENT', 'audio_latent': 'LATENT'}, ['LATENT']),
    'LTXVSeparateAVLatent': ({'av_latent': 'LATENT'}, ['LATENT', 'LATENT']),
    'RandomNoise': ({'noise_seed': 'INT'}, ['NOISE']),
    'KSamplerSelect': ({'sampler_name': ('euler_ancestral',)}, ['SAMPLER']),
    'ManualSigmas': ({'sigmas': 'STRING'}, ['SIGMAS']),
    'SamplerCustomAdvanced': ({'noise': 'NOISE', 'guider': 'GUIDER', 'sampler': 'SAMPLER', 'sigmas': 'SIGMAS', 'latent_image': 'LATENT'}, ['LATENT', 'LATENT']),
    'LTXVLatentUpsampler': ({'samples': 'LATENT', 'upscale_model': 'LATENT_UPSCALE_MODEL', 'vae': 'VAE'}, ['LATENT']),
    'LTXVImgToVideoInplace': ({'vae': 'VAE', 'image': 'IMAGE', 'latent': 'LATENT', 'strength': 'FLOAT', 'bypass': 'BOOLEAN'}, ['LATENT']),
    'VAEDecode': ({'samples': 'LATENT', 'vae': 'VAE'}, ['IMAGE']),
    'LTXVAudioVAEDecode': ({'samples': 'LATENT', 'audio_vae': 'VAE'}, ['AUDIO']),
    'CreateVideo': ({'images': 'IMAGE', 'audio': 'AUDIO', 'fps': 'FLOAT', 'bit_depth': (8,), 'color_space': ('sRGB',), 'codec': ('none',)}, ['VIDEO']),
    # format.codec is the serialized child of the native dynamic format input.
    'SaveVideo': ({'video': 'VIDEO', 'filename_prefix': 'STRING', 'format': ('mp4',), 'format.codec': ('auto',)}, ['VIDEO']),
    'LTXBaselineCapture': ({'images': 'IMAGE', 'video_latent': 'LATENT', 'audio_latent': 'LATENT', 'audio': 'AUDIO', 'run_name': 'STRING'}, []),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_base():
    raw = BASE.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == BASE_SHA256, 'base graph identity changed')
    return json.loads(raw)


def validate_edges(graph, external_image_edge=None):
    """Validate every input, edge source/output/type, DAG, and external reference."""
    require(isinstance(graph, dict) and graph, 'graph must be a nonempty mapping')
    for node_id, node in graph.items():
        require(isinstance(node_id, str) and node_id, 'invalid node id')
        require(isinstance(node, dict) and set(node) == {'class_type', 'inputs'}, 'invalid node fields')
        require(node['class_type'] in SPECS, f'unknown node class: {node["class_type"]}')
        require(isinstance(node['inputs'], dict), 'inputs must be a mapping')
    if external_image_edge is not None:
        require(isinstance(external_image_edge, list) and len(external_image_edge) == 2,
                'external edge must be [node_id, output_index]')
        node_id, index = external_image_edge
        require(isinstance(node_id, str) and re.fullmatch(r'[A-Za-z0-9_-]+', node_id), 'invalid external id')
        require(type(index) is int and index >= 0, 'invalid external output index')
        require(node_id not in graph, 'external provider collides with a graph node')
    dependencies = {key: [] for key in graph}
    used_external = 0
    scalar_types = {'STRING': (str,), 'INT': (int,), 'FLOAT': (int, float), 'BOOLEAN': (bool,)}
    for node_id, node in graph.items():
        fields, _ = SPECS[node['class_type']]
        require(set(node['inputs']) == set(fields), f'{node_id}: missing/unknown inputs')
        for name, kind in fields.items():
            value = node['inputs'][name]
            if isinstance(value, list):
                require(len(value) == 2 and isinstance(value[0], str) and type(value[1]) is int and value[1] >= 0,
                        f'{node_id}.{name}: malformed edge')
                if external_image_edge is not None and value == external_image_edge:
                    output_type = 'IMAGE'
                    used_external += 1
                else:
                    require(value[0] in graph, f'{node_id}.{name}: dangling edge')
                    outputs = SPECS[graph[value[0]]['class_type']][1]
                    require(value[1] < len(outputs), f'{node_id}.{name}: invalid output index')
                    output_type = outputs[value[1]]
                    dependencies[node_id].append(value[0])
                require(output_type == kind, f'{node_id}.{name}: edge type mismatch')
            elif isinstance(kind, tuple):
                require(any(type(value) is type(choice) and value == choice for choice in kind),
                        f'{node_id}.{name}: unsupported enum')
            else:
                require(kind in scalar_types and type(value) in scalar_types[kind],
                        f'{node_id}.{name}: expected {kind}')
                if kind == 'FLOAT':
                    require(math.isfinite(value), f'{node_id}.{name}: nonfinite scalar')
    visiting, done = set(), set()
    def visit(key):
        require(key not in visiting, 'graph contains a cycle')
        if key in done:
            return
        visiting.add(key)
        for dep in dependencies[key]:
            visit(dep)
        visiting.remove(key)
        done.add(key)
    for key in graph:
        visit(key)
    require(external_image_edge is None or used_external == 2, 'anchor must feed exactly both stages')


def build_chunk(chunk_index, run_name, seed=42, prompt=None, anchor_edge=None, anchor_sha256=None):
    require(type(chunk_index) is int and chunk_index >= 0, 'chunk index must be nonnegative')
    require(type(seed) is int and 0 <= seed < 2**64, 'seed must be uint64')
    require(isinstance(run_name, str) and re.fullmatch(r'continuation-[A-Za-z0-9_-]+', run_name),
            'run name must start continuation- and contain safe filename characters')
    require(prompt is None or isinstance(prompt, str) and prompt.strip(), 'prompt must be nonempty')
    subsequent = chunk_index > 0
    require(subsequent == (anchor_edge is not None), 'only subsequent chunks require an anchor edge')
    if subsequent:
        require(isinstance(anchor_sha256, str) and re.fullmatch(r'[0-9a-f]{64}', anchor_sha256),
                'subsequent chunk requires predecessor float-frame SHA256')
    else:
        require(anchor_sha256 is None, 'first chunk cannot declare a predecessor hash')
    graph = load_base()
    graph['364']['inputs']['text'] = prompt if prompt is not None else graph['364']['inputs']['text']
    for key in ('339', '338'):
        graph[key]['inputs']['noise_seed'] = seed
    graph['414']['inputs']['run_name'] = run_name
    graph['75']['inputs']['filename_prefix'] = f'{run_name}/preview'
    if subsequent:
        for key, latent_edge in [('continuation_anchor_stage1', ['356', 0]),
                                 ('continuation_anchor_stage2', ['348', 0])]:
            graph[key] = {'class_type': 'LTXVImgToVideoInplace', 'inputs': {
                'vae': ['420', 2], 'image': copy.deepcopy(anchor_edge), 'latent': latent_edge,
                'strength': 1.0, 'bypass': False}}
        graph['377']['inputs']['video_latent'] = ['continuation_anchor_stage1', 0]
        graph['340']['inputs']['video_latent'] = ['continuation_anchor_stage2', 0]
    validate_edges(graph, anchor_edge)
    return {
        'schema': 'ltx25.continuation-graph-module.v1',
        'status': 'inactive-source-only', 'ready_for_submission': False,
        'graph': graph,
        'identity': {'base_graph_sha256': BASE_SHA256, 'comfy_commit': COMFY_COMMIT,
                     'native_source_sha256': dict(SOURCE_HASHES), 'model_precision': 'native BF16',
                     'stage_steps': [8, 3], 'dimensions': [256, 256], 'frames': 25, 'fps': 24},
        'chunk': {'index': chunk_index, 'seed': seed,
                  'delivery_frame_start': 1 if subsequent else 0,
                  'new_video_frames': 24 if subsequent else 25,
                  'raw_video_frames': 25, 'output_slicing_implemented': False},
        'external_image_input': None if not subsequent else {
            'edge': copy.deepcopy(anchor_edge), 'provider_implemented': False,
            'predecessor_chunk_index': chunk_index - 1,
            'predecessor_frame_index': 24, 'sha256': anchor_sha256,
            'hash_definition': 'SHA256 of contiguous little-endian float32 RGB sample bytes',
            'shape': [1, 256, 256, 3], 'dtype': 'float32',
            'payload_hash_verified': False,
            'required_validation': 'finite, exact shape/dtype/hash; captured predecessor float tensor; no media decode, clamp or quantization'},
        'audio': {'raw_output_edge': ['358', 0], 'modified': False,
                  'timeline_policy': 'unresolved; do not trim, resample, crossfade or concatenate'},
        'qualification': {'gpu_execution': False, 'deterministic_replay': False,
                          'seam_quality': False, 'audio_alignment': False,
                          'runtime_binding': 'required separately before any submission'},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chunk-index', type=int, required=True)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--prompt')
    parser.add_argument('--anchor-node')
    parser.add_argument('--anchor-output', type=int, default=0)
    parser.add_argument('--anchor-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.anchor_node is None and args.anchor_output != 0:
        parser.error('--anchor-output requires --anchor-node')
    edge = None if args.anchor_node is None else [args.anchor_node, args.anchor_output]
    try:
        result = build_chunk(args.chunk_index, args.run_name, args.seed, args.prompt, edge, args.anchor_sha256)
        # Exclusive creation protects prior construction evidence.
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
