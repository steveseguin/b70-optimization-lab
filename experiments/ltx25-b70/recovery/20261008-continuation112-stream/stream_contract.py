"""Packet112 chunk request contract: pure stdlib, importable by server and client.

The ONLY accepted chunk graphs are the ones `build_chunk_graph` returns for a
parameter set. The server parses a submitted graph back into parameters and
requires canonical byte equality with the rebuilt graph, so no node, input or
edge outside this contract can reach execution. No Torch, Comfy, network or file
access happens here (the launch frame count is read from LTX_STREAM_FRAMES only
by `launch_frames`).

One anchor chain per server: stream chunk 0 is the only unanchored
text-to-video request; every later chunk conditions on the previous chunk's
last decoded frame. The prompt may change at any chunk (a cut); the anchor
chain continues through it. `scene_id` is a client label only.
"""
import hashlib
import json
import os
import re

SCHEMA = 'ltx.stream112.chunk-contract.v2'
OUTPUT_SIZE = '256x256'
WIDTH = HEIGHT = 256
FPS = 24
FRAME_CHOICES = (49, 25)
DEFAULT_FRAMES = 49
# Sampler placement is a launch parameter too. 'two-way' (23/25) is the 256x256 lane's
# placement; 'two-way20-28' is the 111 placement, offered because of the xpu:0 floor margin.
PLACEMENTS = {'two-way': 23, 'two-way20-28': 20}
DEFAULT_PLACEMENT = 'two-way'
ANCHOR_SHAPE = [1, HEIGHT, WIDTH, 3]
ANCHOR_BYTES = HEIGHT * WIDTH * 3 * 4      # 786,432 bytes of little-endian F32
SAMPLE_RATE = 48000
COMPARISON_MODE = 'stream-candidate-112-v1'
RUN_PREFIX = 'stream112'
KINDS = ('qualify-eager', 'qualify-graph', 'qualify-repeat', 'stream')
CAPTURE_KINDS = ('qualify-eager', 'qualify-graph', 'qualify-repeat')
GATED_KINDS = ('qualify-eager', 'qualify-graph')   # the graph-capture and text gates are in these graphs only
QUALIFICATION_SCENES = {'qualify-eager': 'qeager', 'qualify-graph': 'qgraph', 'qualify-repeat': 'qrepeat'}
QUALIFICATION_SEEDS = (42, 43, 44)
QUALIFICATION_CLIP_BASE = 11200000
STREAM_CLIP_BASE = 11201000
CLIP_INDEX_MAX = 100000000                 # ltx_pipeline.CLIP_INDEX_MAX
MAX_STREAM_SEQ = CLIP_INDEX_MAX - STREAM_CLIP_BASE
SEED_MAX = 2 ** 64 - 1                     # RandomNoise noise_seed widget maximum
MAX_PROMPT_CHARS = 4000
SCENE_RE = re.compile(r'[a-z0-9]{1,32}')
SHA_RE = re.compile(r'[0-9a-f]{64}')
QUALIFICATION_PROMPT = (
    'A locked-off close-up shot of a small red wooden toy boat floating on calm clear water. '
    'The boat gently rocks once as soft ripples spread outward. Warm natural daylight, realistic '
    'wood texture, consistent lighting, no camera movement. Quiet water gently laps against the boat.')
QUALIFICATION_CUT_PROMPT = (
    'The same small red wooden toy boat drifts slowly to the left across the calm clear water as a '
    'gentle breeze ripples the surface. Warm natural daylight, realistic wood texture, consistent '
    'lighting, no camera movement. Soft wind and quiet water sounds.')
QUALIFICATION_PROMPTS = (QUALIFICATION_PROMPT, QUALIFICATION_PROMPT, QUALIFICATION_CUT_PROMPT)
SIGMAS_A = '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'
SIGMAS_B = '0.85, 0.7250, 0.4219, 0.0'
_GEOMETRY = {49: (7, 51, 96480), 25: (4, 26, 48480)}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def launch_frames(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_STREAM_FRAMES', str(DEFAULT_FRAMES))
    require(value in ('49', '25'), 'LTX_STREAM_FRAMES must be 49 or 25')
    return int(value)


def launch_placement(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_SAMPLER_PLACEMENT', DEFAULT_PLACEMENT)
    require(value in PLACEMENTS, 'LTX_SAMPLER_PLACEMENT must be two-way or two-way20-28')
    return value


def geometry(frames):
    require(frames in FRAME_CHOICES, 'frames must be 49 or 25')
    temporal, audio_latents, audio_samples = _GEOMETRY[frames]
    tensors = {'images': [frames, HEIGHT, WIDTH, 3], 'video_latent': [1, 128, temporal, HEIGHT // 32, WIDTH // 32],
               'audio_latent': [1, 8, audio_latents, 16], 'waveform': [1, 2, audio_samples]}
    payload = sum(4 * _prod(s) for s in tensors.values())
    return {'frames': frames, 'temporal_latents': temporal, 'audio_latents': audio_latents,
            'audio_samples': audio_samples, 'tensor_shapes': tensors,
            'stage_shapes': {'A': [1, 128, temporal, HEIGHT // 64, WIDTH // 64],
                             'B': [1, 128, temporal, HEIGHT // 32, WIDTH // 32]},
            'noise_mask_shape': [1, 1, temporal, 1, 1], 'anchor_frame_index': frames - 1,
            'full_payload_bytes': payload, 'new_frames_first_chunk': frames,
            'new_frames_continuation': frames - 1, 'seconds_per_chunk': frames / FPS}


def _prod(shape):
    out = 1
    for n in shape:
        out *= n
    return out


def numerical_contract(frames, placement=DEFAULT_PLACEMENT):
    g = geometry(frames)
    require(placement in PLACEMENTS, 'Unknown placement')
    split = PLACEMENTS[placement]
    return {
        'schema': 'ltx.stream112.numerical-contract.v1',
        'workload': 'serial image-conditioned continuation, 256x256, %d frames, 24 fps' % frames,
        'model_verification_sha256': '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f',
        'precision': 'BF16 weights, F32 CPU intermediates, strict deterministic algorithms',
        'steps': {'stage_A_sigmas': SIGMAS_A, 'stage_B_sigmas': SIGMAS_B, 'sampler': 'euler_ancestral',
                  'cfg': {'video': 1.0, 'audio': 1.0}},
        'stage_A_latent_shape': g['stage_shapes']['A'], 'stage_B_latent_shape': g['stage_shapes']['B'],
        'output_tensor_shapes': g['tensor_shapes'], 'sample_rate': SAMPLE_RATE,
        'placement': placement, 'sampler_blocks': {'xpu:0': [0, split], 'xpu:1': [split, 48]},
        'sampler_workers': 1, 'sampler_batch': 1, 'shared_pool': 1,
        'graph_replay': {'node': 'LTXGraphCaptureGate', 'selection': 'all48', 'chain': '1',
                         'lean_memo': False, 'max_signatures_per_block': 8, 'freeze_after_qualification': True},
        'conditioning': {'native': 'LTXVImgToVideoInplace.execute', 'strength': 1.0, 'bypass': False,
                         'stages': ['A', 'B'], 'stage_B_after_upsampler': True,
                         'anchor': 'previous chunk images[%d], F32, no conversion' % g['anchor_frame_index']},
        'decoder': 'native VAEDecode + LTXVAudioVAEDecode on the resident VAEs (xpu:3)',
        'text': 'LTXPipelineTextEncode pipeline-window on the accepted graph-sharded encoder',
        'preview': 'pipeline_decode_node.save_preview (CreateVideo fps24 8-bit sRGB + SaveVideo mp4 auto)',
    }


def qualification_id(frames, placement=DEFAULT_PLACEMENT):
    return sha256(canonical(numerical_contract(frames, placement)))


def run_name(params):
    if params['kind'] == 'stream':
        return '%s-s%08d' % (RUN_PREFIX, params['stream_seq'])
    return '%s-%s-c%06d' % (RUN_PREFIX, params['scene_id'], params['chunk_index'])


def text_sha256(text):
    return sha256(text.encode('utf-8'))


def clip_index(params):
    if params['kind'] == 'stream':
        return STREAM_CLIP_BASE + params['stream_seq']
    return QUALIFICATION_CLIP_BASE + list(KINDS).index(params['kind']) * 3 + params['chunk_index']


def validate_params(params):
    """Shape/type checks only. Ordering and predecessor state belong to the authority."""
    require(type(params) is dict and set(params) == {
        'kind', 'frames', 'placement', 'scene_id', 'chunk_index', 'seed', 'prompt', 'predecessor_anchor_sha256',
        'stream_seq', 'reuse_text'}, 'Chunk parameter fields differ')
    require(params['placement'] in PLACEMENTS, 'placement must be two-way or two-way20-28')
    require(params['kind'] in KINDS, 'Unknown chunk kind')
    require(params['frames'] in FRAME_CHOICES and type(params['frames']) is int, 'frames must be 49 or 25')
    require(type(params['scene_id']) is str and SCENE_RE.fullmatch(params['scene_id']),
            'scene_id must match [a-z0-9]{1,32}')
    require(type(params['chunk_index']) is int and type(params['stream_seq']) is int, 'Integer indices required')
    require(type(params['seed']) is int and 0 <= params['seed'] <= SEED_MAX, 'seed must be uint64')
    prompt = params['prompt']
    require(type(prompt) is str and 0 < len(prompt) <= MAX_PROMPT_CHARS and prompt == prompt.strip() and
            prompt.isprintable(), 'prompt must be 1..4000 printable characters without leading/trailing space')
    require(params['reuse_text'] in (0, 1) and type(params['reuse_text']) is int, 'reuse_text is 0 or 1')
    pred = params['predecessor_anchor_sha256']
    if params['kind'] == 'stream':
        require(0 <= params['stream_seq'] < MAX_STREAM_SEQ and params['chunk_index'] == params['stream_seq'],
                'stream chunks carry chunk_index == stream_seq')
        if params['stream_seq'] == 0:
            require(pred == '', 'Stream chunk 0 is unanchored (empty predecessor_anchor_sha256)')
        else:
            require(type(pred) is str and SHA_RE.fullmatch(pred), 'predecessor_anchor_sha256 must be 64 hex')
    else:
        k = params['chunk_index']
        require(params['stream_seq'] == -1 and k in (0, 1, 2) and pred == '' and
                params['scene_id'] == QUALIFICATION_SCENES[params['kind']] and
                params['seed'] == QUALIFICATION_SEEDS[k] and params['prompt'] == QUALIFICATION_PROMPTS[k],
                'Qualification parameters are fixed (the server resolves their anchors)')
    require(not params['reuse_text'] or (params['chunk_index'] > 0 and params['kind'] != 'qualify-eager'),
            'Text reuse needs an anchored, non-eager chunk')
    return params


def build_chunk_graph(params):
    validate_params(params)
    g = geometry(params['frames'])
    name = run_name(params)
    conditioned = params['chunk_index'] > 0
    gated = params['kind'] in GATED_KINDS
    model = ['stream_gate', 0] if gated else ['420', 0]
    graph = {
        '338': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': params['seed']}},
        '339': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': params['seed']}},
        '340': {'class_type': 'LTXVConcatAVLatent', 'inputs': {
            'audio_latent': ['367', 1],
            'video_latent': ['stream_condition_b', 0] if conditioned else ['348', 0]}},
        '341': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'euler_ancestral'}},
        '344': {'class_type': 'SamplerCustomAdvanced', 'inputs': {
            'guider': ['388', 0], 'latent_image': ['377', 0], 'noise': ['339', 0],
            'sampler': ['352', 0], 'sigmas': ['404', 0]}},
        '348': {'class_type': 'LTXVLatentUpsampler', 'inputs': {
            'samples': ['367', 0], 'upscale_model': ['420', 4], 'vae': ['420', 2]}},
        '352': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'euler_ancestral'}},
        '356': {'class_type': 'EmptyLTXVLatentVideo', 'inputs': {
            'batch_size': 1, 'height': HEIGHT // 2, 'length': g['frames'], 'width': WIDTH // 2}},
        '358': {'class_type': 'LTXVAudioVAEDecode', 'inputs': {'audio_vae': ['420', 3], 'samples': ['369', 1]}},
        '365': {'class_type': 'LTXVConditioning', 'inputs': {
            'frame_rate': float(FPS), 'negative': ['stream_text', 0], 'positive': ['stream_text', 0]}},
        '366': {'class_type': 'LTXVEmptyLatentAudio', 'inputs': {
            'audio_vae': ['420', 3], 'batch_size': 1, 'frame_rate': float(FPS), 'frames_number': g['frames']}},
        '367': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['344', 0]}},
        '368': {'class_type': 'SamplerCustomAdvanced', 'inputs': {
            'guider': ['391', 0], 'latent_image': ['340', 0], 'noise': ['338', 0],
            'sampler': ['341', 0], 'sigmas': ['395', 0]}},
        '369': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['368', 0]}},
        '374': {'class_type': 'VAEDecode', 'inputs': {'samples': ['369', 0], 'vae': ['420', 2]}},
        '377': {'class_type': 'LTXVConcatAVLatent', 'inputs': {
            'audio_latent': ['366', 0],
            'video_latent': ['stream_condition_a', 0] if conditioned else ['356', 0]}},
        '388': {'class_type': 'LTXVDualCFGGuider', 'inputs': {
            'audio_cfg': 1.0, 'model': model, 'negative': ['365', 1], 'positive': ['365', 0], 'video_cfg': 1.0}},
        '391': {'class_type': 'LTXVDualCFGGuider', 'inputs': {
            'audio_cfg': 1.0, 'model': model, 'negative': ['365', 1], 'positive': ['365', 0], 'video_cfg': 1.0}},
        '395': {'class_type': 'ManualSigmas', 'inputs': {'sigmas': SIGMAS_B}},
        '404': {'class_type': 'ManualSigmas', 'inputs': {'sigmas': SIGMAS_A}},
        '420': {'class_type': 'LTXHostEmbeddingComponents', 'inputs': {
            'encoder_mode': 'control', 'placement': 'split'}},
        'stream_text': {'class_type': 'LTXStreamText112', 'inputs': {'run_name': name, 'text': params['prompt']}},
        'stream_output': {'class_type': 'LTXStreamChunk112', 'inputs': {
            'images': ['374', 0], 'audio': ['358', 0], 'video_latent': ['369', 0],
            'audio_latent': ['369', 1], 'run_name': name, 'kind': params['kind'], 'frames': params['frames'],
            'placement': params['placement'],
            'scene_id': params['scene_id'], 'chunk_index': params['chunk_index'], 'seed': params['seed'],
            'stream_seq': params['stream_seq'], 'predecessor_anchor_sha256': params['predecessor_anchor_sha256'],
            'reuse_text': params['reuse_text']}},
    }
    if gated:
        graph['stream_gate'] = {'class_type': 'LTXGraphCaptureGate', 'inputs': {
            'model': ['420', 0], 'mode': 'original' if params['kind'] == 'qualify-eager' else 'graph',
            'selection': 'all48', 'chain': '1', 'run_name': name}}
    if not params['reuse_text']:
        clip = ['420', 1]
        if gated:
            graph['425'] = {'class_type': 'LTXTextEncoderGraphGate', 'inputs': {
                'clip': ['420', 1], 'mode': 'graph-shard', 'run_name': name}}
            clip = ['425', 0]
        graph['364'] = {'class_type': 'LTXPipelineTextEncode', 'inputs': {
            'clip': clip, 'clip_index': clip_index(params), 'comparison_mode': COMPARISON_MODE,
            'depth': 2, 'mode': 'pipeline-window', 'output_size': OUTPUT_SIZE,
            'qualification_id': qualification_id(params['frames'], params['placement']), 'run_name': name,
            'speed_only': False,
            'text': params['prompt']}}
        graph['stream_text']['inputs']['conditioning'] = ['364', 0]
    if conditioned:
        graph['stream_anchor'] = {'class_type': 'LTXStreamAnchor112', 'inputs': {
            'run_name': name, 'predecessor_anchor_sha256': params['predecessor_anchor_sha256']}}
        for key, stage, edge in (('stream_condition_a', 'A', ['356', 0]),
                                 ('stream_condition_b', 'B', ['348', 0])):
            graph[key] = {'class_type': 'LTXStreamCondition112', 'inputs': {
                'vae': ['420', 2], 'image': ['stream_anchor', 0], 'latent': edge,
                'strength': 1.0, 'bypass': False, 'run_name': name, 'stage': stage}}
    if params['kind'] in CAPTURE_KINDS:
        graph['414'] = {'class_type': 'LTXBaselineCapture', 'inputs': {
            'audio': ['358', 0], 'audio_latent': ['369', 1], 'images': ['374', 0],
            'run_name': name, 'video_latent': ['369', 0]}}
    validate_edges(graph)
    return graph


def validate_edges(graph):
    visiting, done = set(), set()

    def visit(key):
        require(key not in visiting, 'Graph cycle')
        if key in done:
            return
        visiting.add(key)
        node = graph[key]
        require(type(node) is dict and set(node) == {'class_type', 'inputs'} and
                type(node['inputs']) is dict, 'Graph node fields differ')
        for value in node['inputs'].values():
            if isinstance(value, list):
                require(len(value) == 2 and type(value[0]) is str and type(value[1]) is int and
                        value[1] >= 0 and value[0] in graph, 'Dangling or malformed edge')
                visit(value[0])
        visiting.remove(key)
        done.add(key)
    for key in graph:
        visit(key)


def parse_chunk_graph(graph, frames, placement=DEFAULT_PLACEMENT):
    """Return the parameters of an exact contract graph, or raise ValueError."""
    require(type(graph) is dict and type(graph.get('stream_output')) is dict and
            type(graph.get('stream_text')) is dict, 'Not a packet112 chunk graph')
    out = graph['stream_output']
    require(out.get('class_type') == 'LTXStreamChunk112' and type(out.get('inputs')) is dict,
            'Chunk output node differs')
    inputs = out['inputs']
    params = {'kind': inputs.get('kind'), 'frames': inputs.get('frames'), 'placement': inputs.get('placement'),
              'scene_id': inputs.get('scene_id'),
              'chunk_index': inputs.get('chunk_index'), 'seed': inputs.get('seed'),
              'prompt': graph['stream_text'].get('inputs', {}).get('text'),
              'predecessor_anchor_sha256': inputs.get('predecessor_anchor_sha256'),
              'stream_seq': inputs.get('stream_seq'), 'reuse_text': inputs.get('reuse_text')}
    validate_params(params)
    require(params['frames'] == frames, 'frames differs from this server (LTX_STREAM_FRAMES=%d)' % frames)
    require(params['placement'] == placement, 'placement differs from this server (%s)' % placement)
    require(canonical(graph) == canonical(build_chunk_graph(params)),
            'Submitted graph differs from the exact packet112 contract graph')
    return params


def setup_graphs():
    probe, prepare = RUN_PREFIX + '-window-probe', RUN_PREFIX + '-prepare'
    return [
        {'name': probe, 'kind': 'window-probe', 'graph': {
            '420': {'class_type': 'LTXHostEmbeddingComponents', 'inputs': {'encoder_mode': 'control', 'placement': 'split'}},
            '425': {'class_type': 'LTXTextEncoderGraphGate', 'inputs': {'clip': ['420', 1], 'mode': 'graph-shard', 'run_name': probe}},
            '470': {'class_type': 'LTXTextWindowProbe', 'inputs': {'clip': ['425', 0], 'run_name': probe}}}},
        {'name': prepare, 'kind': 'prepare', 'graph': {
            '490': {'class_type': 'LTXStreamPrepare112', 'inputs': {'run_name': prepare}}}},
    ]


def qualification_params(frames, text_reuse_mode, placement=DEFAULT_PLACEMENT):
    """Chunk 1 repeats chunk 0's prompt; chunk 2 is a cut (new prompt, same anchor chain)."""
    rows = []
    for kind in KINDS[:3]:
        for chunk in range(3):
            reuse = int(bool(text_reuse_mode) and kind != 'qualify-eager' and chunk == 1)
            rows.append({'kind': kind, 'frames': frames, 'placement': placement, 'scene_id': QUALIFICATION_SCENES[kind],
                         'chunk_index': chunk, 'seed': QUALIFICATION_SEEDS[chunk],
                         'prompt': QUALIFICATION_PROMPTS[chunk], 'predecessor_anchor_sha256': '',
                         'stream_seq': -1, 'reuse_text': reuse})
    return rows


def stream_params(frames, stream_seq, prompt, seed, predecessor_anchor_sha256, scene_id, reuse_text=0,
                  placement=DEFAULT_PLACEMENT):
    """Client helper: the parameter dict for one streaming chunk (frames/placement from GET /ltx-stream/status)."""
    return validate_params({'kind': 'stream', 'frames': frames, 'placement': placement, 'scene_id': scene_id,
                            'chunk_index': stream_seq,
                            'seed': seed, 'prompt': prompt,
                            'predecessor_anchor_sha256': predecessor_anchor_sha256 if stream_seq else '',
                            'stream_seq': stream_seq, 'reuse_text': reuse_text})
