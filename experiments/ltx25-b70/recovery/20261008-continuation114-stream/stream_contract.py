"""Packet114 chunk request contract: pure stdlib.

The ONLY accepted chunk graphs are the ones `build_chunk_graph` returns for a
parameter set. The server parses a submitted graph back into parameters and
requires canonical byte equality with the rebuilt graph, so no node, input or
edge outside this contract can reach execution. No Torch, Comfy, network or file
access happens here (launch options are read from the environment only by the
`launch_*` helpers).

One anchor chain per server: stream chunk 0 is the only unanchored
text-to-video request apart from client chain resets (packet113 form, kept);
every later chunk conditions on its predecessor. The prompt may change at any
chunk (a cut); the anchor chain continues through it.

Packet114 changes against packet113:

- The anchor is chosen at launch (LTX_ANCHOR). `latent` (default): stage A of
  chunk n conditions on the last latent slot of chunk n-1's stage-A output (node
  367, before the upsampler) and stage B on the last latent slot of chunk n-1's
  stage-B output (node 369); slot 0 is replaced by the anchor and its mask set
  to 0, exactly the copy LTXVImgToVideoInplace makes after its VAE encode
  (nodes_lt.py:156,172-175), without the encode. `frame`: packet113's decoded
  last-frame anchor through the native image conditioning node.
- The decoders are no longer graph nodes. The output node receives the three
  latents and the two VAEs and hands the decode to one in-order decode thread.
- The chunk length is chosen at launch (LTX_STREAM_FRAMES 49 or 97).
- Every name a server creates outside its run directory carries the
  `stream114-` prefix (the packet113 naming incident).
"""
import hashlib
import json
import os
import re

SCHEMA = 'ltx.stream114.chunk-contract.v1'
PACKET = 114
OUTPUT_SIZE = '256x256'
WIDTH = HEIGHT = 256
FPS = 24
FRAME_CHOICES = (49, 97)
DEFAULT_FRAMES = 49
# Sampler placement is a launch parameter. 'two-way' (23/25) is the 256x256 lane's
# placement; 'two-way20-28' is the 111 placement the live lane runs.
PLACEMENTS = {'two-way': 23, 'two-way20-28': 20}
DEFAULT_PLACEMENT = 'two-way'
ANCHORS = ('latent', 'frame')
DEFAULT_ANCHOR = 'latent'
ANCHOR_SHAPE = [1, HEIGHT, WIDTH, 3]       # frame anchor (packet113 form)
ANCHOR_BYTES = HEIGHT * WIDTH * 3 * 4      # 786,432 bytes of little-endian F32
# Latent anchor file: stage-A slot then stage-B slot, little-endian F32, no header.
LATENT_ANCHOR_PARTS = (('A', [1, 128, 1, HEIGHT // 64, WIDTH // 64]),
                       ('B', [1, 128, 1, HEIGHT // 32, WIDTH // 32]))
LATENT_ANCHOR_PART_BYTES = {name: 4 * 128 * shape[3] * shape[4] for name, shape in LATENT_ANCHOR_PARTS}
LATENT_ANCHOR_BYTES = sum(LATENT_ANCHOR_PART_BYTES.values())   # 8,192 + 32,768 = 40,960
SAMPLE_RATE = 48000
COMPARISON_MODE = 'stream-candidate-114-v1'
RUN_PREFIX = 'stream114'
KINDS = ('qualify-eager', 'qualify-graph', 'qualify-repeat', 'stream')
CAPTURE_KINDS = ('qualify-eager', 'qualify-graph', 'qualify-repeat')
GATED_KINDS = ('qualify-eager', 'qualify-graph')   # the graph-capture and text gates are in these graphs only
QUALIFICATION_SCENES = {'qualify-eager': 'qeager', 'qualify-graph': 'qgraph', 'qualify-repeat': 'qrepeat'}
QUALIFICATION_SEEDS = (42, 43, 44)
QUALIFICATION_CLIP_BASE = 11400000
STREAM_CLIP_BASE = 11401000
CLIP_INDEX_MAX = 100000000                 # ltx_pipeline.CLIP_INDEX_MAX
MAX_STREAM_SEQ = CLIP_INDEX_MAX - STREAM_CLIP_BASE
SEED_MAX = 2 ** 64 - 1                     # RandomNoise noise_seed widget maximum
MAX_PROMPT_CHARS = 4000
SCENE_RE = re.compile(r'[a-z0-9]{1,32}')
SHA_RE = re.compile(r'[0-9a-f]{64}')
RUN_NAME_RE = re.compile(RUN_PREFIX + r'-(s[0-9]{8}|q(eager|graph|repeat)-c00000[0-2])')
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
# frames -> (latent T, audio latents, waveform samples).
# 49: measured (packets 110-113). 97: derived from the sealed sources, not yet measured:
#   audio latents = round(97 / 24 * 25) = 101 (audio_vae.num_of_latents_from_frames, 16 kHz / hop 160 / 4)
#   samples = ((101 - 1) * 4 + 1) * 160 * 3 = 192,480 (the two measured lengths satisfy the same formula:
#   ((51-1)*4+1)*480 = 96,480 and ((26-1)*4+1)*480 = 48,480).
# The first eager chunk of every 97-frame launch checks these shapes exactly and records them
# (stream-geometry-measured.json); a mismatch latches before any stream chunk.
_GEOMETRY = {49: (7, 51, 96480), 97: (13, 101, 192480)}
GEOMETRY_PROVENANCE = {49: 'measured (packets 110-113)',
                       97: 'derived from audio_vae.py and the two measured lengths; checked on the first eager chunk'}


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
    require(value in ('49', '97'), 'LTX_STREAM_FRAMES must be 49 or 97')
    return int(value)


def launch_placement(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_SAMPLER_PLACEMENT', DEFAULT_PLACEMENT)
    require(value in PLACEMENTS, 'LTX_SAMPLER_PLACEMENT must be two-way or two-way20-28')
    return value


def launch_anchor(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_ANCHOR', DEFAULT_ANCHOR)
    require(value in ANCHORS, 'LTX_ANCHOR must be latent or frame')
    return value


def launch_text_reuse(environ=None):
    """Packet114: text reuse is ON unless LTX_STREAM_TEXT_REUSE=0."""
    value = (os.environ if environ is None else environ).get('LTX_STREAM_TEXT_REUSE', '1')
    require(value in ('0', '1'), 'LTX_STREAM_TEXT_REUSE must be 0 or 1')
    return int(value)


def geometry(frames):
    require(frames in FRAME_CHOICES, 'frames must be 49 or 97')
    temporal, audio_latents, audio_samples = _GEOMETRY[frames]
    tensors = {'images': [frames, HEIGHT, WIDTH, 3], 'video_latent': [1, 128, temporal, HEIGHT // 32, WIDTH // 32],
               'audio_latent': [1, 8, audio_latents, 16], 'waveform': [1, 2, audio_samples]}
    payload = sum(4 * _prod(s) for s in tensors.values())
    stage_a = [1, 128, temporal, HEIGHT // 64, WIDTH // 64]
    return {'frames': frames, 'temporal_latents': temporal, 'audio_latents': audio_latents,
            'audio_samples': audio_samples, 'tensor_shapes': tensors,
            'latent_shapes': {'video_latent': tensors['video_latent'], 'audio_latent': tensors['audio_latent'],
                              'stage_a_latent': stage_a},
            'decoded_shapes': {'images': tensors['images'], 'waveform': tensors['waveform']},
            'stage_shapes': {'A': stage_a, 'B': tensors['video_latent']},
            'noise_mask_shape': [1, 1, temporal, 1, 1], 'anchor_frame_index': frames - 1,
            'latent_anchor_slot': temporal - 1,
            'stage_tokens': {'A': temporal * (HEIGHT // 64) * (WIDTH // 64),
                             'B': temporal * (HEIGHT // 32) * (WIDTH // 32)},
            'full_payload_bytes': payload, 'new_frames_first_chunk': frames,
            'new_frames_continuation': frames - 1, 'seconds_per_chunk': frames / FPS,
            'provenance': GEOMETRY_PROVENANCE[frames]}


def _prod(shape):
    out = 1
    for n in shape:
        out *= n
    return out


def numerical_contract(frames, placement=DEFAULT_PLACEMENT, anchor=DEFAULT_ANCHOR):
    g = geometry(frames)
    require(placement in PLACEMENTS, 'Unknown placement')
    require(anchor in ANCHORS, 'Unknown anchor mode')
    split = PLACEMENTS[placement]
    if anchor == 'latent':
        conditioning = {
            'node': 'LTXStreamLatentCondition114 (nodes_lt.py:156,172-175 with t = the anchor latent; no VAE encode)',
            'strength': 1.0, 'stages': ['A', 'B'], 'stage_B_after_upsampler': True,
            'anchor': {'A': 'previous chunk node 367 video_latent[:, :, %d:%d] (stage A, before the upsampler)'
                            % (g['latent_anchor_slot'], g['latent_anchor_slot'] + 1),
                       'B': 'previous chunk node 369 video_latent[:, :, %d:%d] (stage B)'
                            % (g['latent_anchor_slot'], g['latent_anchor_slot'] + 1)},
            'format': 'F32 little-endian, %d bytes, whole-file SHA-256' % LATENT_ANCHOR_BYTES}
    else:
        conditioning = {'native': 'LTXVImgToVideoInplace.execute', 'strength': 1.0, 'bypass': False,
                        'stages': ['A', 'B'], 'stage_B_after_upsampler': True,
                        'anchor': 'previous chunk images[%d], F32, no conversion' % g['anchor_frame_index']}
    return {
        'schema': 'ltx.stream114.numerical-contract.v1',
        'workload': 'serial anchored continuation, 256x256, %d frames, 24 fps, %s anchor' % (frames, anchor),
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
        'anchor': anchor, 'conditioning': conditioning,
        'decoder': 'native VAEDecode.decode + LTXVAudioVAEDecode.execute on the resident VAEs (xpu:3), '
                   'called by one in-order decode thread under inference_mode',
        'text': 'LTXPipelineTextEncode pipeline-window on the accepted graph-sharded encoder',
        'preview': 'CreateVideo fps24 8-bit sRGB + SaveVideo mp4 auto, one in-order writer behind the decode thread',
    }


def qualification_id(frames, placement=DEFAULT_PLACEMENT, anchor=DEFAULT_ANCHOR):
    return sha256(canonical(numerical_contract(frames, placement, anchor)))


def variant(frames, placement, anchor):
    return '%d/%s/%s' % (frames, placement, anchor)


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


FIELDS = ('kind', 'frames', 'placement', 'anchor', 'scene_id', 'chunk_index', 'seed', 'prompt',
          'predecessor_anchor_sha256', 'stream_seq', 'reuse_text', 'reset')


def validate_params(params):
    """Shape/type checks only. Ordering and predecessor state belong to the authority.
    Returns the parameters; parameters without a 'reset' key are read as reset 0."""
    if type(params) is dict and 'reset' not in params:
        params = dict(params, reset=0)
    require(type(params) is dict and set(params) == set(FIELDS), 'Chunk parameter fields differ')
    require(params['reset'] in (0, 1) and type(params['reset']) is int, 'reset is 0 or 1')
    require(params['placement'] in PLACEMENTS, 'placement must be two-way or two-way20-28')
    require(params['anchor'] in ANCHORS, 'anchor must be latent or frame')
    require(params['kind'] in KINDS, 'Unknown chunk kind')
    require(params['frames'] in FRAME_CHOICES and type(params['frames']) is int, 'frames must be 49 or 97')
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
            require(pred == '' and params['reset'] == 0,
                    'Stream chunk 0 is unanchored (empty predecessor_anchor_sha256, no reset flag)')
        elif params['reset']:
            # A chain reset is unanchored; the predecessor hash is recorded, not consumed.
            require(pred == '' or (type(pred) is str and SHA_RE.fullmatch(pred)),
                    'A reset chunk names the predecessor anchor (64 hex) or nothing')
            require(params['reuse_text'] == 0, 'A reset chunk always encodes its prompt (reuse_text 0)')
        else:
            require(type(pred) is str and SHA_RE.fullmatch(pred), 'predecessor_anchor_sha256 must be 64 hex')
    else:
        k = params['chunk_index']
        require(params['stream_seq'] == -1 and k in (0, 1, 2) and pred == '' and params['reset'] == 0 and
                params['scene_id'] == QUALIFICATION_SCENES[params['kind']] and
                params['seed'] == QUALIFICATION_SEEDS[k] and params['prompt'] == QUALIFICATION_PROMPTS[k],
                'Qualification parameters are fixed (the server resolves their anchors)')
    require(not params['reuse_text'] or (anchored(params) and params['kind'] != 'qualify-eager'),
            'Text reuse needs an anchored, non-eager chunk')
    return params


def anchored(params):
    """True when the chunk conditions on its predecessor."""
    return params['chunk_index'] > 0 and not params['reset']


def build_chunk_graph(params):
    params = validate_params(params)
    g = geometry(params['frames'])
    name = run_name(params)
    conditioned = anchored(params)
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
        '365': {'class_type': 'LTXVConditioning', 'inputs': {
            'frame_rate': float(FPS), 'negative': ['stream_text', 0], 'positive': ['stream_text', 0]}},
        '366': {'class_type': 'LTXVEmptyLatentAudio', 'inputs': {
            'audio_vae': ['420', 3], 'batch_size': 1, 'frame_rate': float(FPS), 'frames_number': g['frames']}},
        '367': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['344', 0]}},
        '368': {'class_type': 'SamplerCustomAdvanced', 'inputs': {
            'guider': ['391', 0], 'latent_image': ['340', 0], 'noise': ['338', 0],
            'sampler': ['341', 0], 'sigmas': ['395', 0]}},
        '369': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['368', 0]}},
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
        'stream_text': {'class_type': 'LTXStreamText114', 'inputs': {'run_name': name, 'text': params['prompt']}},
        # Packet114: no decoder nodes. The output node takes the three latents and the two
        # resident VAEs and hands the decode to the server's in-order decode thread.
        'stream_output': {'class_type': 'LTXStreamChunk114', 'inputs': {
            'video_latent': ['369', 0], 'audio_latent': ['369', 1], 'stage_a_latent': ['367', 0],
            'vae': ['420', 2], 'audio_vae': ['420', 3],
            'run_name': name, 'kind': params['kind'], 'frames': params['frames'],
            'placement': params['placement'], 'anchor': params['anchor'],
            'scene_id': params['scene_id'], 'chunk_index': params['chunk_index'], 'seed': params['seed'],
            'stream_seq': params['stream_seq'], 'predecessor_anchor_sha256': params['predecessor_anchor_sha256'],
            'reuse_text': params['reuse_text']}},
    }
    if params['reset']:
        # Optional input: present only on a reset chunk.
        graph['stream_output']['inputs']['reset'] = 1
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
            'qualification_id': qualification_id(params['frames'], params['placement'], params['anchor']),
            'run_name': name, 'speed_only': False, 'text': params['prompt']}}
        graph['stream_text']['inputs']['conditioning'] = ['364', 0]
    if conditioned and params['anchor'] == 'latent':
        graph['stream_anchor'] = {'class_type': 'LTXStreamLatentAnchor114', 'inputs': {
            'run_name': name, 'predecessor_anchor_sha256': params['predecessor_anchor_sha256']}}
        for key, stage, edge, slot in (('stream_condition_a', 'A', ['356', 0], 0),
                                       ('stream_condition_b', 'B', ['348', 0], 1)):
            graph[key] = {'class_type': 'LTXStreamLatentCondition114', 'inputs': {
                'latent': edge, 'anchor': ['stream_anchor', slot], 'strength': 1.0,
                'run_name': name, 'stage': stage}}
    elif conditioned:
        graph['stream_anchor'] = {'class_type': 'LTXStreamAnchor114', 'inputs': {
            'run_name': name, 'predecessor_anchor_sha256': params['predecessor_anchor_sha256']}}
        for key, stage, edge in (('stream_condition_a', 'A', ['356', 0]),
                                 ('stream_condition_b', 'B', ['348', 0])):
            graph[key] = {'class_type': 'LTXStreamCondition114', 'inputs': {
                'vae': ['420', 2], 'image': ['stream_anchor', 0], 'latent': edge,
                'strength': 1.0, 'bypass': False, 'run_name': name, 'stage': stage}}
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


def parse_chunk_graph(graph, frames, placement=DEFAULT_PLACEMENT, anchor=DEFAULT_ANCHOR):
    """Return the parameters of an exact contract graph, or raise ValueError."""
    require(type(graph) is dict and type(graph.get('stream_output')) is dict and
            type(graph.get('stream_text')) is dict, 'Not a packet114 chunk graph')
    out = graph['stream_output']
    require(out.get('class_type') == 'LTXStreamChunk114' and type(out.get('inputs')) is dict,
            'Chunk output node differs (packet114 needs LTXStreamChunk114)')
    inputs = out['inputs']
    params = {'kind': inputs.get('kind'), 'frames': inputs.get('frames'), 'placement': inputs.get('placement'),
              'anchor': inputs.get('anchor'), 'scene_id': inputs.get('scene_id'),
              'chunk_index': inputs.get('chunk_index'), 'seed': inputs.get('seed'),
              'prompt': graph['stream_text'].get('inputs', {}).get('text'),
              'predecessor_anchor_sha256': inputs.get('predecessor_anchor_sha256'),
              'stream_seq': inputs.get('stream_seq'), 'reuse_text': inputs.get('reuse_text'),
              'reset': inputs.get('reset', 0)}
    validate_params(params)
    require(params['frames'] == frames, 'frames differs from this server (LTX_STREAM_FRAMES=%d)' % frames)
    require(params['placement'] == placement, 'placement differs from this server (%s)' % placement)
    require(params['anchor'] == anchor, 'anchor differs from this server (LTX_ANCHOR=%s)' % anchor)
    require(canonical(graph) == canonical(build_chunk_graph(params)),
            'Submitted graph differs from the exact packet114 contract graph')
    return params


def setup_graphs():
    probe, prepare = RUN_PREFIX + '-window-probe', RUN_PREFIX + '-prepare'
    return [
        {'name': probe, 'kind': 'window-probe', 'graph': {
            '420': {'class_type': 'LTXHostEmbeddingComponents', 'inputs': {'encoder_mode': 'control', 'placement': 'split'}},
            '425': {'class_type': 'LTXTextEncoderGraphGate', 'inputs': {'clip': ['420', 1], 'mode': 'graph-shard', 'run_name': probe}},
            '470': {'class_type': 'LTXTextWindowProbe', 'inputs': {'clip': ['425', 0], 'run_name': probe}}}},
        {'name': prepare, 'kind': 'prepare', 'graph': {
            '490': {'class_type': 'LTXStreamPrepare114', 'inputs': {'run_name': prepare}}}},
    ]


def qualification_params(frames, text_reuse_mode, placement=DEFAULT_PLACEMENT, anchor=DEFAULT_ANCHOR):
    """Chunk 1 repeats chunk 0's prompt; chunk 2 is a cut (new prompt, same anchor chain)."""
    rows = []
    for kind in KINDS[:3]:
        for chunk in range(3):
            reuse = int(bool(text_reuse_mode) and kind != 'qualify-eager' and chunk == 1)
            rows.append({'kind': kind, 'frames': frames, 'placement': placement, 'anchor': anchor,
                         'scene_id': QUALIFICATION_SCENES[kind],
                         'chunk_index': chunk, 'seed': QUALIFICATION_SEEDS[chunk],
                         'prompt': QUALIFICATION_PROMPTS[chunk], 'predecessor_anchor_sha256': '',
                         'stream_seq': -1, 'reuse_text': reuse, 'reset': 0})
    return rows


def fixed_names():
    """Every request name the setup and qualification create (all carry RUN_PREFIX)."""
    return [r['name'] for r in setup_graphs()] + [run_name(p) for p in qualification_params(49, 0)]


def stream_params(frames, stream_seq, prompt, seed, predecessor_anchor_sha256, scene_id, reuse_text=0,
                  placement=DEFAULT_PLACEMENT, reset=0, anchor=DEFAULT_ANCHOR):
    """Client helper: the parameter dict for one streaming chunk (frames/placement/anchor from
    GET /ltx-stream/status). reset=1 (stream_seq > 0) restarts the anchor chain with an unanchored chunk."""
    return validate_params({'kind': 'stream', 'frames': frames, 'placement': placement, 'anchor': anchor,
                            'scene_id': scene_id, 'chunk_index': stream_seq,
                            'seed': seed, 'prompt': prompt,
                            'predecessor_anchor_sha256': predecessor_anchor_sha256 if stream_seq else '',
                            'stream_seq': stream_seq, 'reuse_text': reuse_text, 'reset': reset})
