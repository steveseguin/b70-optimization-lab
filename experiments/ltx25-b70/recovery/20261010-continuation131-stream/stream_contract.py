"""Packet123 chunk request contract: pure stdlib.

Packet123 moves optional auxiliary owners and publishes previews atomically.
169 is conditional on auxiliary xpu2 residency, dg0 and display3.
The measured-geometry, three-chain and per-chunk cone/display gates remain mandatory.

Packet120 = packet117 (below) plus three launch-selectable server-side levers that do not change the request
graph and are exact by construction, and its own names (`stream131-` prefix, string packet id 123, comparison mode
stream-candidate-131-v1, clip bases 13100000 / 13101000, schemas `ltx.stream118.*`):

A. Timing split (always on, measurement only): receipts split `submit_to_sampler_start` and the
   receipt -> next-submit turnaround into named sub-buckets (stream_receipts.SUBMIT_SPLIT / TURNAROUND_SPLIT).
B. `snapshot_mode` (LTX_SNAPSHOT_MODE, 'walk' or 'fingerprint', default 'fingerprint'): how the four-card
   safety snapshot inspects residence (snapshot_fingerprint.py). It is a launch parameter returned by the status
   route and recorded in every receipt; it is NOT a request field and NOT part of the qualification id (it does not
   touch a graph, a tensor or a numerical contract), packet123 retains all176 numerical identities from121 unchanged.
C. `decoder_graph_pool_cap_gb` (LTX_DECODER_GRAPH_POOL_CAP_GB, unset = packet 117 behaviour): a capture-time
   bound on the decoder-graph pool (stream_decoder_graph.py); launch parameter, status and decode records only.

The run name carries the snapshot mode (`-sm<walk|fp>-`, launcher rule), not the pool cap.

Packet117 (kept) = packet116b (frame anchor by default, 116a scheduling, the decoder-graph experiment, the
packet-113/114 frame references, the pinned NA axis-router acceptance) plus four launch-selectable
levers for the frame anchor, each exact by construction and gated in qualification:

1. `anchor_decode` (LTX_ANCHOR_DECODE, 'full' or 'cone'): with 'cone' the anchor frame comes from a
   cone-restricted decode that issues, for the stage-5 diffusion blocks, only the kernel calls of the
   full decode that the last pixel frame depends on (same calls, same shapes, same input rows; the other
   rows are zero-filled); the full decode for display runs later on the decode thread and its last frame
   must equal the cone's byte for byte (a mismatch latches).
2. `bencode_overlap` (LTX_BENCODE_OVERLAP, 0 or 1): the stage-B anchor encode (the native VAE encode of
   the anchor frame inside LTXVImgToVideoInplace) runs on the decode thread beside stage A, guarded by an
   xpu:3-only safety snapshot; the stage-B node then runs the native node with the precomputed encode.
3. chunk length 121 (LTX_STREAM_FRAMES=121, 5.04 s; 16 latent frames, 256/1024 tokens).
4. `prep_ahead` (LTX_PREP_AHEAD, 0 or 1): the stage-A anchor encode runs on the decode thread right after
   the predecessor's receipt commits (beside the client turnaround). The anchor-independent rest of the
   stage-A preparation (noise, empty latents, sigmas, LTXVConditioning, the reused text copy) are the
   successor request's own graph nodes and cost milliseconds; they are not moved (that would need node
   outputs cached across requests, which the executor guard refuses).

The three levers are frame-anchor features: with the mixed, latent or guide anchor they must be
`full`, 0, 0. They are part of every request (stream_output inputs) and of the qualification id.

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

Packet116 changes against packet115 (whose four anchor modes, sharpness profile, decode thread,
49/97-frame chunks and text reuse are kept unchanged):

- The default anchor is `frame` again (packet113 semantics at both stages: the decoded last
  frame of chunk n-1 through the native image conditioning with its VAE encode). It is the only
  measured mode whose seams are sharp. `mixed`, `latent` and `guide` stay launch options for A/B.
- 116a scheduling (no arithmetic change): in frame mode the chain waits only for the VIDEO decode
  of its own chunk. The decode thread writes the anchor file right after the video decode and
  hands it to the chain; the audio decode, the tensor hashing, the diagnostics, the fsynced decode
  record and the preview move behind it on the decode thread while the next chunk runs.
- `decoder_graph` (launch parameter LTX_DECODER_GRAPH, 0 or 1, default 1): graph replay of the NA
  diffusion video decoder with bounded, device-resident caches (RoPE inverse frequencies, the
  per-axis neighbourhood-attention window masks and the seed-0 decoder noise), qualified by byte
  identity against the uncached eager decode. It is part of every request and of the qualification
  id, like the anchor mode.
- Every name a server creates outside its run directory carries the packet's own prefix (the
  packet113 naming incident; `stream131-` in packet 118).

Packet115 changes against packet114 (kept):

- Four launch-selectable anchor modes (LTX_ANCHOR):
  - `mixed`: stage A conditions on the last latent slot of chunk n-1's
    stage-A output (node 367, packet114's latent anchor for stage A); stage B
    conditions on chunk n-1's DECODED last frame through the native image
    conditioning node with its VAE encode (packet113's frame anchor for stage B),
    re-pinned after the upsampler. Chunk n's text encode and stage A therefore
    need only chunk n-1's latents; its stage-B condition node waits (bounded) for
    chunk n-1's decode record. The decode overlaps chunk n's text + stage A.
  - `guide`: the native LTXVAddLatentGuide (nodes_lt.py:525-646) appends the last
    two latent slots of chunk n-1 (stage A from node 367, stage B from node 369)
    as guide tokens at latent index -2 (pixel frames -16..-1) for both stages,
    instead of the slot-0 still-frame conditioning; LTXVCropGuides removes them
    after each sampler (before the upsampler and before the output node). Frame
    0 of chunk n is generated, so an anchored guide chunk delivers all frames.
  - `latent` (packet114's default) and `frame` (packet113's anchor).
- The decode thread computes a per-frame sharpness profile (Laplacian variance of
  decoded frames 0, 1, 2, 5, 10, 24, the middle and the last frame) for every chunk.
"""
import hashlib
import json
import os
import re

SCHEMA = 'ltx.stream118.chunk-contract.v1'
PACKET = 131
OUTPUT_SIZE = '256x256'
WIDTH = HEIGHT = 256
FPS = 24
FRAME_CHOICES = (49, 97, 121, 145, 169)
DEFAULT_FRAMES = 49
# Sampler placement is a launch parameter. 'two-way' (23/25) is the 256x256 lane's
# placement; 'two-way20-28' is the 111 placement the live lane runs.
PLACEMENTS = {'two-way': 23, 'two-way20-28': 20}
DEFAULT_PLACEMENT = 'two-way'
ANCHORS = ('mixed', 'latent', 'frame', 'guide')
DEFAULT_ANCHOR = 'frame'          # packet116: sharp seams (packet113 semantics)
# Anchor modes whose anchor_out is written by the output node before the decode (the decode is off
# the chain). 'frame' waits for its own decode.
OFF_CHAIN_DECODE = ('mixed', 'latent', 'guide')
# Packet116 decoder graph capture (launch parameter LTX_DECODER_GRAPH); default on, gated by byte
# identity against the uncached eager decode in qualification.
DECODER_GRAPH_CHOICES = (0, 1)
DEFAULT_DECODER_GRAPH = 1
# Packet117 levers (frame anchor only; the other anchors require full/0/0). Defaults: everything on.
ANCHOR_DECODE_CHOICES = ('full', 'cone')
BENCODE_OVERLAP_CHOICES = (0, 1)
PREP_AHEAD_CHOICES = (0, 1)
LEVER_ANCHORS = ('frame',)
NEUTRAL_LEVERS = ('full', 0, 0)
DEFAULT_LEVERS = ('cone', 1, 1)
# Packet123 server-side launch parameters (not request fields, not in the qualification id).
SNAPSHOT_MODES = ('walk', 'fingerprint')
DEFAULT_SNAPSHOT_MODE = 'fingerprint'
SNAPSHOT_MODE_TOKENS = {'walk': 'walk', 'fingerprint': 'fp'}      # run-name token: -sm<walk|fp>-
POOL_CAP_MIN_GB, POOL_CAP_MAX_GB = 0.25, 16.0
POOL_CAP_RE = re.compile(r'(0|[1-9][0-9]?)(\.[0-9]{1,2})?')
# Anchor modes that condition slot 0 (and therefore deliver one overlap frame to drop).
SLOT0_ANCHORS = ('mixed', 'latent', 'frame')
ANCHOR_SHAPE = [1, HEIGHT, WIDTH, 3]       # frame anchor (packet113 form)
ANCHOR_BYTES = HEIGHT * WIDTH * 3 * 4      # 786,432 bytes of little-endian F32
# Latent anchor file: stage-A slot then stage-B slot, little-endian F32, no header.
LATENT_ANCHOR_PARTS = (('A', [1, 128, 1, HEIGHT // 64, WIDTH // 64]),
                       ('B', [1, 128, 1, HEIGHT // 32, WIDTH // 32]))
LATENT_ANCHOR_PART_BYTES = {name: 4 * 128 * shape[3] * shape[4] for name, shape in LATENT_ANCHOR_PARTS}
LATENT_ANCHOR_BYTES = sum(LATENT_ANCHOR_PART_BYTES.values())   # 8,192 + 32,768 = 40,960
# Guide anchor file (LTX_ANCHOR=guide): the last TWO latent slots of stage A then of stage B.
GUIDE_FRAMES = 2
GUIDE_LATENT_IDX = -GUIDE_FRAMES                # pixel frames -16..-1 (nodes_lt.py:625-628)
GUIDE_ANCHOR_PARTS = (('A', [1, 128, GUIDE_FRAMES, HEIGHT // 64, WIDTH // 64]),
                      ('B', [1, 128, GUIDE_FRAMES, HEIGHT // 32, WIDTH // 32]))
GUIDE_ANCHOR_PART_BYTES = {name: 4 * 128 * GUIDE_FRAMES * shape[3] * shape[4] for name, shape in GUIDE_ANCHOR_PARTS}
GUIDE_ANCHOR_BYTES = sum(GUIDE_ANCHOR_PART_BYTES.values())     # 16,384 + 65,536 = 81,920
# Sharpness profile (decode thread, diagnostic): Laplacian variance of these decoded frames, plus
# the middle frame (frames // 2) and the last frame; ratios are relative to the middle frame.
SHARPNESS_FRAMES = (0, 1, 2, 5, 10, 24)
SAMPLE_RATE = 48000
COMPARISON_MODE = 'stream-candidate-131-v1'
RUN_PREFIX = 'stream131'
KINDS = ('qualify-eager', 'qualify-graph', 'qualify-repeat', 'stream')
CAPTURE_KINDS = ('qualify-eager', 'qualify-graph', 'qualify-repeat')
GATED_KINDS = ('qualify-eager', 'qualify-graph')   # the graph-capture and text gates are in these graphs only
QUALIFICATION_SCENES = {'qualify-eager': 'qeager', 'qualify-graph': 'qgraph', 'qualify-repeat': 'qrepeat'}
QUALIFICATION_SEEDS = (42, 43, 44)
QUALIFICATION_CLIP_BASE = 13100000
STREAM_CLIP_BASE = 13101000
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
# 49: measured (packets 110-113). 97: measured (packets 114-116b, stream-geometry-measured.json).
# 121 (packet117): derived from the sealed sources and MEASURED by packet 117 at 121 frames (2026-10-09, dg0 run:
#   stream-geometry-measured.json matches: images [121,256,256,3], audio [1,8,126,16], waveform [1,2,240480]):
#   latent T = (121 - 1) // 8 + 1 = 16 (EmptyLTXVLatentVideo); tokens 16*4*4 = 256 (stage A), 16*8*8 = 1024 (B)
#   audio latents = round(121 / 24 * 25) = round(126.04) = 126 (audio_vae.num_of_latents_from_frames)
#   samples = ((126 - 1) * 4 + 1) * 160 * 3 = 240,480 (the formula the measured 49 and 97 lengths satisfy:
#   ((51-1)*4+1)*480 = 96,480 and ((101-1)*4+1)*480 = 192,480).
# The first eager chunk of every launch checks these shapes exactly and records them
# (stream-geometry-measured.json); a mismatch latches before any stream chunk.
_GEOMETRY = {49: (7, 51, 96480), 97: (13, 101, 192480), 121: (16, 126, 240480), 145: (19, 151, 288480), 169: (22, 176, 336480)}
GEOMETRY_PROVENANCE = {145: 'derived from sealed formulas; launch shape measurement required',
                       169: 'derived from sealed formulas; launch shape measurement required',
                       49: 'measured (packets 110-113)',
                       97: 'measured (packets 114-116b; derived from audio_vae.py before that)',
                       121: 'measured (packet 117 at 121 frames, 2026-10-09; derived from audio_vae.py '
                            '(round(121/24*25)=126) and the formula the measured 49/97 lengths satisfy before that)'}


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
    require(value in ('49', '97', '121', '145', '169'), 'LTX_STREAM_FRAMES must be 49, 97, 121 or 145')
    return int(value)


def launch_placement(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_SAMPLER_PLACEMENT', DEFAULT_PLACEMENT)
    require(value in PLACEMENTS, 'LTX_SAMPLER_PLACEMENT must be two-way or two-way20-28')
    return value


def launch_anchor(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_ANCHOR', DEFAULT_ANCHOR)
    require(value in ANCHORS, 'LTX_ANCHOR must be mixed, latent, frame or guide')
    return value


def launch_decoder_graph(environ=None):
    """Packet116: decoder graph replay is ON unless LTX_DECODER_GRAPH=0."""
    value = (os.environ if environ is None else environ).get('LTX_DECODER_GRAPH', str(DEFAULT_DECODER_GRAPH))
    require(value in ('0', '1'), 'LTX_DECODER_GRAPH must be 0 or 1')
    return int(value)


def launch_anchor_decode(environ=None):
    """Packet117: LTX_ANCHOR_DECODE 'full' or 'cone' (the default; frame anchor only)."""
    environ = os.environ if environ is None else environ
    value = environ.get('LTX_ANCHOR_DECODE', default_levers(launch_anchor(environ))[0])
    require(value in ANCHOR_DECODE_CHOICES, 'LTX_ANCHOR_DECODE must be full or cone')
    return value


def launch_bencode_overlap(environ=None):
    """Packet117: LTX_BENCODE_OVERLAP 0 or 1 (default 1; frame anchor only)."""
    environ = os.environ if environ is None else environ
    value = environ.get('LTX_BENCODE_OVERLAP', str(default_levers(launch_anchor(environ))[1]))
    require(value in ('0', '1'), 'LTX_BENCODE_OVERLAP must be 0 or 1')
    return int(value)


def launch_prep_ahead(environ=None):
    """Packet117: LTX_PREP_AHEAD 0 or 1 (default 1; frame anchor only)."""
    environ = os.environ if environ is None else environ
    value = environ.get('LTX_PREP_AHEAD', str(default_levers(launch_anchor(environ))[2]))
    require(value in ('0', '1'), 'LTX_PREP_AHEAD must be 0 or 1')
    return int(value)


def launch_levers(environ=None):
    """(anchor_decode, bencode_overlap, prep_ahead) of this launch, checked against the anchor."""
    environ = os.environ if environ is None else environ
    levers = (launch_anchor_decode(environ), launch_bencode_overlap(environ), launch_prep_ahead(environ))
    check_levers(launch_anchor(environ), *levers)
    return levers


def default_levers(anchor):
    """Packet117 defaults: every lever on for the frame anchor; the other anchors cannot use them."""
    return DEFAULT_LEVERS if anchor in LEVER_ANCHORS else NEUTRAL_LEVERS


def check_levers(anchor, anchor_decode, bencode_overlap, prep_ahead):
    require(anchor_decode in ANCHOR_DECODE_CHOICES and type(anchor_decode) is str, 'anchor_decode is full or cone')
    require(bencode_overlap in BENCODE_OVERLAP_CHOICES and type(bencode_overlap) is int, 'bencode_overlap is 0 or 1')
    require(prep_ahead in PREP_AHEAD_CHOICES and type(prep_ahead) is int, 'prep_ahead is 0 or 1')
    require(anchor in LEVER_ANCHORS or (anchor_decode, bencode_overlap, prep_ahead) == NEUTRAL_LEVERS,
            'The cone decode, the stage-B encode overlap and prep-ahead need the frame anchor (anchor %s requires '
            'full/0/0)' % anchor)
    return anchor_decode, bencode_overlap, prep_ahead


def _levers(anchor, anchor_decode, bencode_overlap, prep_ahead):
    defaults = default_levers(anchor)
    values = tuple(d if v is None else v for v, d in zip((anchor_decode, bencode_overlap, prep_ahead), defaults))
    return check_levers(anchor, *values)


def launch_snapshot_mode(environ=None):
    """Packet123: LTX_SNAPSHOT_MODE 'walk' (packet 117's residence walk) or 'fingerprint' (the default)."""
    value = (os.environ if environ is None else environ).get('LTX_SNAPSHOT_MODE', DEFAULT_SNAPSHOT_MODE)
    require(value in SNAPSHOT_MODES, 'LTX_SNAPSHOT_MODE must be walk or fingerprint')
    return value


def parse_pool_cap(value):
    """Packet123: LTX_DECODER_GRAPH_POOL_CAP_GB as bytes (decimal GB = 10**9 bytes), or None when unset/empty.
    Accepted: a plain decimal with at most two decimals, 0.25 <= value <= 16."""
    if value is None or value == '':
        return None
    require(type(value) is str and POOL_CAP_RE.fullmatch(value) is not None,
            'LTX_DECODER_GRAPH_POOL_CAP_GB must be a decimal such as 1.0 (at most two decimals)')
    number = float(value)
    require(POOL_CAP_MIN_GB <= number <= POOL_CAP_MAX_GB,
            'LTX_DECODER_GRAPH_POOL_CAP_GB must be between %.2f and %.1f' % (POOL_CAP_MIN_GB, POOL_CAP_MAX_GB))
    whole, _, frac = value.partition('.')
    return int(whole) * 10 ** 9 + int((frac + '00')[:2]) * 10 ** 7


def launch_pool_cap(environ=None):
    """Packet123: the decoder-graph pool cap in bytes, or None (packet 117 behaviour). Needs the decoder graph."""
    environ = os.environ if environ is None else environ
    cap = parse_pool_cap(environ.get('LTX_DECODER_GRAPH_POOL_CAP_GB'))
    require(cap is None or launch_decoder_graph(environ) == 1,
            'LTX_DECODER_GRAPH_POOL_CAP_GB needs LTX_DECODER_GRAPH=1')
    return cap


def launch_text_reuse(environ=None):
    """Packet116: text reuse is ON unless LTX_STREAM_TEXT_REUSE=0."""
    value = (os.environ if environ is None else environ).get('LTX_STREAM_TEXT_REUSE', '1')
    require(value in ('0', '1'), 'LTX_STREAM_TEXT_REUSE must be 0 or 1')
    return int(value)


def geometry(frames):
    require(frames in FRAME_CHOICES, 'frames must be 49, 97, 121 or 145')
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
            # LTX_ANCHOR=guide: anchored chunks carry GUIDE_FRAMES extra latent frames per stage.
            'guided_stage_tokens': {'A': (temporal + GUIDE_FRAMES) * (HEIGHT // 64) * (WIDTH // 64),
                                    'B': (temporal + GUIDE_FRAMES) * (HEIGHT // 32) * (WIDTH // 32)},
            'guided_stage_shapes': {'A': [1, 128, temporal + GUIDE_FRAMES, HEIGHT // 64, WIDTH // 64],
                                    'B': [1, 128, temporal + GUIDE_FRAMES, HEIGHT // 32, WIDTH // 32]},
            'guided_noise_mask_shape': [1, 1, temporal + GUIDE_FRAMES, 1, 1],
            'sharpness_frames': sharpness_frames(frames),
            'full_payload_bytes': payload, 'new_frames_first_chunk': frames,
            'new_frames_continuation': frames - 1, 'seconds_per_chunk': frames / FPS,
            'provenance': GEOMETRY_PROVENANCE[frames]}


def sharpness_frames(frames):
    """Decoded frame indices of the per-chunk sharpness profile (sorted, unique, all < frames)."""
    return sorted({i for i in SHARPNESS_FRAMES if i < frames} | {frames // 2, frames - 1})


def _prod(shape):
    out = 1
    for n in shape:
        out *= n
    return out


def numerical_contract(frames, placement=DEFAULT_PLACEMENT, anchor=DEFAULT_ANCHOR, decoder_graph=DEFAULT_DECODER_GRAPH,
                       anchor_decode=None, bencode_overlap=None, prep_ahead=None):
    anchor_decode, bencode_overlap, prep_ahead = _levers(anchor, anchor_decode, bencode_overlap, prep_ahead)
    g = geometry(frames)
    require(placement in PLACEMENTS, 'Unknown placement')
    require(anchor in ANCHORS, 'Unknown anchor mode')
    require(decoder_graph in DECODER_GRAPH_CHOICES and type(decoder_graph) is int, 'decoder_graph must be 0 or 1')
    split = PLACEMENTS[placement]
    slot = g['latent_anchor_slot']
    latent_a = 'previous chunk node 367 video_latent[:, :, %d:%d] (stage A, before the upsampler)' % (slot, slot + 1)
    if anchor == 'latent':
        conditioning = {
            'node': 'LTXStreamLatentCondition116 (nodes_lt.py:156,172-175 with t = the anchor latent; no VAE encode)',
            'strength': 1.0, 'stages': ['A', 'B'], 'stage_B_after_upsampler': True,
            'anchor': {'A': latent_a,
                       'B': 'previous chunk node 369 video_latent[:, :, %d:%d] (stage B)' % (slot, slot + 1)},
            'format': 'F32 little-endian, %d bytes, whole-file SHA-256' % LATENT_ANCHOR_BYTES}
    elif anchor == 'mixed':
        conditioning = {
            'stage_A': {'node': 'LTXStreamLatentCondition116 (nodes_lt.py:156,172-175 with t = the anchor latent; '
                                'no VAE encode)', 'strength': 1.0, 'anchor': latent_a},
            'stage_B': {'native': 'LTXVImgToVideoInplace.execute', 'strength': 1.0, 'bypass': False,
                        'anchor': 'previous chunk images[%d] from the decode thread, F32, no conversion'
                                  % g['anchor_frame_index'],
                        'after_upsampler': True,
                        'waits_for': 'the predecessor decode record (bounded), on the prompt thread'},
            'stages': ['A', 'B'],
            'format': 'latent file F32 little-endian, %d bytes (stage A slot used); frame file %d bytes '
                      '(decode thread)' % (LATENT_ANCHOR_BYTES, ANCHOR_BYTES)}
    elif anchor == 'guide':
        conditioning = {
            'native': 'LTXVAddLatentGuide.execute', 'latent_idx': GUIDE_LATENT_IDX, 'strength': 1.0,
            'guide_frames': GUIDE_FRAMES, 'stages': ['A', 'B'], 'stage_B_after_upsampler': True,
            'guide': {'A': 'previous chunk node 367 video_latent[:, :, %d:%d]' % (slot - 1, slot + 1),
                      'B': 'previous chunk node 369 video_latent[:, :, %d:%d]' % (slot - 1, slot + 1)},
            'crop': 'LTXVCropGuides.execute after each sampler (before the upsampler and before the output node)',
            'tokens': {'A': g['guided_stage_tokens']['A'], 'B': g['guided_stage_tokens']['B']},
            'format': 'F32 little-endian, %d bytes, whole-file SHA-256' % GUIDE_ANCHOR_BYTES}
    else:
        conditioning = {'native': 'LTXVImgToVideoInplace.execute', 'strength': 1.0, 'bypass': False,
                        'stages': ['A', 'B'], 'stage_B_after_upsampler': True,
                        'anchor': 'previous chunk images[%d], F32, no conversion' % g['anchor_frame_index']}
    return {
        'schema': 'ltx.stream118.numerical-contract.v1',
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
        'decoder_graph': decoder_graph_contract(decoder_graph),
        'levers': lever_contract(frames, anchor_decode, bencode_overlap, prep_ahead),
        'scheduling': ('frame anchor: the chain waits for the anchor frame and the anchor file only; audio, '
                       'hashing, diagnostics, record and preview follow on the decode thread'
                       if anchor == 'frame' else 'as packet115'),
        'text': 'LTXPipelineTextEncode pipeline-window on the accepted graph-sharded encoder',
        'preview': 'CreateVideo fps24 8-bit sRGB + SaveVideo mp4 auto, one in-order writer behind the decode thread',
        'diagnostics': 'decode thread: border diagnostic of the last frame and Laplacian-variance sharpness of '
                       'frames %s (float64, CPU; never gated)' % g['sharpness_frames'],
    }


def decoder_graph_contract(decoder_graph):
    if not decoder_graph:
        return {'enabled': False, 'decode': 'uncached eager NADiffusionDecoder (packet115)'}
    return {'enabled': True,
            'captured': ['NADiffusionDecoder.forward_pre_diffusion', 'NADiffusionDecoder.forward_diff_step'],
            'not_captured': 'NADiffusionDecoder.forward (seed-0 noise drawn once per shape and cached)',
            'caches': {'rope_inv_freqs': 'device tensor per (dim, base, device), computed by the original '
                                         'function (fp64 on the CPU when the device lacks fp64)',
                       'na_axis_masks': 'per-axis window boolean matrix per (starts, ends, device), built by the '
                                        'original expressions outside capture',
                       'noise': 'torch.randn(pixel_shape, generator=seed 0) per (shape, dtype, device), drawn once'},
            'pool': 'one graph memory pool on xpu:3 shared by the two captures',
            'pool_cap': 'packet118 server option LTX_DECODER_GRAPH_POOL_CAP_GB: methods are captured in first-call '
                        'order while the reserved growth of the captures already made is below the cap; a capped '
                        'method runs eagerly with the same caches (the byte gates are unchanged)',
            'qualification': 'graph chain: uncached eager decode and graph decode of the same latents, '
                             'byte-identical images; every chain byte-identical to the eager chain',
            'freeze_after_qualification': True, 'fallback': 'none (a mismatch latches and halts)'}


def lever_contract(frames, anchor_decode, bencode_overlap, prep_ahead):
    """Packet117: what each lever does to the arithmetic (nothing) and to the schedule."""
    return {
        'anchor_decode': ({'mode': 'full', 'anchor': 'images[%d] of the full native decode' % (frames - 1)}
                          if anchor_decode == 'full' else
                          {'mode': 'cone',
                           'anchor': 'images[%d] of a native VAEDecode whose NADiffusionDecoder.forward_diff_step is '
                                     'the cone-restricted step (stream_anchor_decode.py)' % (frames - 1),
                           'cone': 'stage-5 DiffusionNABlocks issue only the context_proj/qkv/proj/mlp chunk calls '
                                   'and na3d query tiles whose frames reach the last pixel frame (same calls, same '
                                   'shapes, same input rows); skipped rows are zero; conv_in_x_t, norm_out and '
                                   'conv_out run on the whole tensor; stages 1-4 and the seed-0 noise unchanged',
                           'display': 'the full native decode on the decode thread after the successor\'s sampler A '
                                      'starts (bounded wait)',
                           'check': 'per chunk: cone images[last] == full images[last] byte for byte, else latch',
                           'refuses': 'na3d not dispatched to the eager backend, CUDA tile stacking (g_max > 1)'}),
        'bencode_overlap': ({'enabled': False, 'stage_B_encode': 'native, on the prompt thread'}
                            if not bencode_overlap else
                            {'enabled': True,
                             'stage_B_encode': 'native LTXVImgToVideoInplace.execute with a capturing VAE, on the '
                                               'decode thread beside stage A, between xpu:3-only safety snapshots '
                                               '(9 GiB before, 2 GiB after)',
                             'stage_B_node': 'native LTXVImgToVideoInplace.execute with the precomputed encode, '
                                             'inside the unchanged four-card conditioning guard'}),
        'prep_ahead': ({'enabled': False, 'stage_A_encode': 'native, on the prompt thread'}
                       if not prep_ahead else
                       {'enabled': True,
                        'stage_A_encode': 'native LTXVImgToVideoInplace.execute with a capturing VAE, on the decode '
                                          'thread after the predecessor receipt commits, between xpu:3-only safety '
                                          'snapshots',
                        'stage_A_node': 'native LTXVImgToVideoInplace.execute with the precomputed encode, inside the '
                                        'unchanged four-card conditioning guard'}),
        'qualification': 'eager chain: all levers off (the reference); graph chain: levers on plus the native '
                         'path on the same inputs, byte-identical; repeat chain: levers on (stream form)'}


def qualification_id(frames, placement=DEFAULT_PLACEMENT, anchor=DEFAULT_ANCHOR, decoder_graph=DEFAULT_DECODER_GRAPH,
                     anchor_decode=None, bencode_overlap=None, prep_ahead=None):
    return sha256(canonical(numerical_contract(frames, placement, anchor, decoder_graph, anchor_decode,
                                               bencode_overlap, prep_ahead)))


def variant(frames, placement, anchor, decoder_graph=DEFAULT_DECODER_GRAPH, anchor_decode=None, bencode_overlap=None,
            prep_ahead=None):
    ad, bo, pa = _levers(anchor, anchor_decode, bencode_overlap, prep_ahead)
    return '%d/%s/%s/dg%d/ad-%s/bo%d/pa%d' % (frames, placement, anchor, decoder_graph, ad, bo, pa)


def variant_keys():
    """Every launch variant of packet123 (as packet117): (frames, placement, anchor, dg, anchor_decode, bencode_overlap,
    prep_ahead). The levers vary only with the frame anchor."""
    keys = []
    for f in FRAME_CHOICES:
        for p in PLACEMENTS:
            for a in ANCHORS:
                for d in DECODER_GRAPH_CHOICES:
                    if a in LEVER_ANCHORS:
                        keys.extend((f, p, a, d, ad, bo, pa) for ad in ANCHOR_DECODE_CHOICES
                                    for bo in BENCODE_OVERLAP_CHOICES for pa in PREP_AHEAD_CHOICES)
                    else:
                        keys.append((f, p, a, d) + NEUTRAL_LEVERS)
    return keys


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


FIELDS = ('kind', 'frames', 'placement', 'anchor', 'decoder_graph', 'anchor_decode', 'bencode_overlap', 'prep_ahead',
          'scene_id', 'chunk_index', 'seed', 'prompt', 'predecessor_anchor_sha256', 'stream_seq', 'reuse_text', 'reset')
LEVER_FIELDS = ('anchor_decode', 'bencode_overlap', 'prep_ahead')


def validate_params(params):
    """Shape/type checks only. Ordering and predecessor state belong to the authority.
    Returns the parameters; parameters without a 'reset' key are read as reset 0."""
    if type(params) is dict and 'reset' not in params:
        params = dict(params, reset=0)
    require(type(params) is dict and set(params) == set(FIELDS), 'Chunk parameter fields differ')
    require(params['reset'] in (0, 1) and type(params['reset']) is int, 'reset is 0 or 1')
    require(params['placement'] in PLACEMENTS, 'placement must be two-way or two-way20-28')
    require(params['anchor'] in ANCHORS, 'anchor must be mixed, latent, frame or guide')
    require(params['decoder_graph'] in DECODER_GRAPH_CHOICES and type(params['decoder_graph']) is int,
            'decoder_graph is 0 or 1')
    check_levers(params['anchor'], params['anchor_decode'], params['bencode_overlap'], params['prep_ahead'])
    require(params['kind'] in KINDS, 'Unknown chunk kind')
    require(params['frames'] in FRAME_CHOICES and type(params['frames']) is int, 'frames must be 49, 97, 121 or 145')
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
        'stream_text': {'class_type': 'LTXStreamText116', 'inputs': {'run_name': name, 'text': params['prompt']}},
        # Packet116: no decoder nodes. The output node takes the three latents and the two
        # resident VAEs and hands the decode to the server's in-order decode thread.
        'stream_output': {'class_type': 'LTXStreamChunk116', 'inputs': {
            'video_latent': ['369', 0], 'audio_latent': ['369', 1], 'stage_a_latent': ['367', 0],
            'vae': ['420', 2], 'audio_vae': ['420', 3],
            'run_name': name, 'kind': params['kind'], 'frames': params['frames'],
            'placement': params['placement'], 'anchor': params['anchor'], 'decoder_graph': params['decoder_graph'],
            'anchor_decode': params['anchor_decode'], 'bencode_overlap': params['bencode_overlap'],
            'prep_ahead': params['prep_ahead'],
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
            'qualification_id': qualification_id(params['frames'], params['placement'], params['anchor'],
                                                 params['decoder_graph'], params['anchor_decode'],
                                                 params['bencode_overlap'], params['prep_ahead']),
            'run_name': name, 'speed_only': False, 'text': params['prompt']}}
        graph['stream_text']['inputs']['conditioning'] = ['364', 0]
    anchor = params['anchor']
    if conditioned and anchor in ('latent', 'mixed'):
        graph['stream_anchor'] = {'class_type': 'LTXStreamLatentAnchor116', 'inputs': {
            'run_name': name, 'predecessor_anchor_sha256': params['predecessor_anchor_sha256']}}
        graph['stream_condition_a'] = {'class_type': 'LTXStreamLatentCondition116', 'inputs': {
            'latent': ['356', 0], 'anchor': ['stream_anchor', 0], 'strength': 1.0, 'run_name': name, 'stage': 'A'}}
        if anchor == 'latent':
            graph['stream_condition_b'] = {'class_type': 'LTXStreamLatentCondition116', 'inputs': {
                'latent': ['348', 0], 'anchor': ['stream_anchor', 1], 'strength': 1.0, 'run_name': name,
                'stage': 'B'}}
        else:
            # Mixed: stage B is the native image conditioning on the predecessor's decoded last frame.
            # The node consumes the upsampler output, so it runs after stage A; it waits (bounded) for
            # the predecessor's decode record before its VAE encode.
            graph['stream_condition_b'] = {'class_type': 'LTXStreamFrameConditionB116', 'inputs': {
                'vae': ['420', 2], 'latent': ['348', 0], 'strength': 1.0, 'bypass': False, 'run_name': name}}
    elif conditioned and anchor == 'guide':
        graph['stream_anchor'] = {'class_type': 'LTXStreamGuideAnchor116', 'inputs': {
            'run_name': name, 'predecessor_anchor_sha256': params['predecessor_anchor_sha256']}}
        for key, crop, stage, edge, slot, sampled, guider in (
                ('stream_condition_a', 'stream_crop_a', 'A', ['356', 0], 0, ['367', 0], '388'),
                ('stream_condition_b', 'stream_crop_b', 'B', ['348', 0], 1, ['369', 0], '391')):
            graph[key] = {'class_type': 'LTXStreamGuide116', 'inputs': {
                'positive': ['365', 0], 'negative': ['365', 1], 'vae': ['420', 2], 'latent': edge,
                'guide': ['stream_anchor', slot], 'strength': 1.0, 'run_name': name, 'stage': stage}}
            graph[crop] = {'class_type': 'LTXStreamCropGuides116', 'inputs': {
                'positive': [key, 0], 'negative': [key, 1], 'latent': sampled, 'run_name': name, 'stage': stage}}
            graph[guider]['inputs']['positive'] = [key, 0]
            graph[guider]['inputs']['negative'] = [key, 1]
        graph['377']['inputs']['video_latent'] = ['stream_condition_a', 2]
        graph['340']['inputs']['video_latent'] = ['stream_condition_b', 2]
        graph['348']['inputs']['samples'] = ['stream_crop_a', 2]
        graph['stream_output']['inputs']['video_latent'] = ['stream_crop_b', 2]
        graph['stream_output']['inputs']['stage_a_latent'] = ['stream_crop_a', 2]
    elif conditioned:
        graph['stream_anchor'] = {'class_type': 'LTXStreamAnchor116', 'inputs': {
            'run_name': name, 'predecessor_anchor_sha256': params['predecessor_anchor_sha256']}}
        for key, stage, edge in (('stream_condition_a', 'A', ['356', 0]),
                                 ('stream_condition_b', 'B', ['348', 0])):
            graph[key] = {'class_type': 'LTXStreamCondition116', 'inputs': {
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


def parse_chunk_graph(graph, frames, placement=DEFAULT_PLACEMENT, anchor=DEFAULT_ANCHOR,
                      decoder_graph=DEFAULT_DECODER_GRAPH, levers=None):
    """Return the parameters of an exact contract graph, or raise ValueError. `levers` is this server's
    (anchor_decode, bencode_overlap, prep_ahead); None means the defaults for its anchor."""
    levers = _levers(anchor, *(levers if levers is not None else (None, None, None)))
    require(type(graph) is dict and type(graph.get('stream_output')) is dict and
            type(graph.get('stream_text')) is dict, 'Not a packet123 chunk graph')
    out = graph['stream_output']
    require(out.get('class_type') == 'LTXStreamChunk116' and type(out.get('inputs')) is dict,
            'Chunk output node differs (packet116 needs LTXStreamChunk116)')
    inputs = out['inputs']
    params = {'kind': inputs.get('kind'), 'frames': inputs.get('frames'), 'placement': inputs.get('placement'),
              'anchor': inputs.get('anchor'), 'decoder_graph': inputs.get('decoder_graph'),
              'anchor_decode': inputs.get('anchor_decode'), 'bencode_overlap': inputs.get('bencode_overlap'),
              'prep_ahead': inputs.get('prep_ahead'),
              'scene_id': inputs.get('scene_id'),
              'chunk_index': inputs.get('chunk_index'), 'seed': inputs.get('seed'),
              'prompt': graph['stream_text'].get('inputs', {}).get('text'),
              'predecessor_anchor_sha256': inputs.get('predecessor_anchor_sha256'),
              'stream_seq': inputs.get('stream_seq'), 'reuse_text': inputs.get('reuse_text'),
              'reset': inputs.get('reset', 0)}
    validate_params(params)
    require(params['frames'] == frames, 'frames differs from this server (LTX_STREAM_FRAMES=%d)' % frames)
    require(params['placement'] == placement, 'placement differs from this server (%s)' % placement)
    require(params['anchor'] == anchor, 'anchor differs from this server (LTX_ANCHOR=%s)' % anchor)
    require(params['decoder_graph'] == decoder_graph,
            'decoder_graph differs from this server (LTX_DECODER_GRAPH=%d)' % decoder_graph)
    require(tuple(params[k] for k in LEVER_FIELDS) == levers,
            'anchor_decode/bencode_overlap/prep_ahead differ from this server (%s/%d/%d)' % levers)
    require(canonical(graph) == canonical(build_chunk_graph(params)),
            'Submitted graph differs from the exact packet123 contract graph')
    return params


def setup_graphs():
    probe, prepare = RUN_PREFIX + '-window-probe', RUN_PREFIX + '-prepare'
    return [
        {'name': probe, 'kind': 'window-probe', 'graph': {
            '420': {'class_type': 'LTXHostEmbeddingComponents', 'inputs': {'encoder_mode': 'control', 'placement': 'split'}},
            '425': {'class_type': 'LTXTextEncoderGraphGate', 'inputs': {'clip': ['420', 1], 'mode': 'graph-shard', 'run_name': probe}},
            '470': {'class_type': 'LTXTextWindowProbe', 'inputs': {'clip': ['425', 0], 'run_name': probe}}}},
        {'name': prepare, 'kind': 'prepare', 'graph': {
            '490': {'class_type': 'LTXStreamPrepare116', 'inputs': {'run_name': prepare}}}},
    ]


def qualification_params(frames, text_reuse_mode, placement=DEFAULT_PLACEMENT, anchor=DEFAULT_ANCHOR,
                         decoder_graph=DEFAULT_DECODER_GRAPH, anchor_decode=None, bencode_overlap=None, prep_ahead=None):
    """Chunk 1 repeats chunk 0's prompt; chunk 2 is a cut (new prompt, same anchor chain). The levers are the
    launch's (the request fields name them; the eager chain still runs with them off, see lever_contract)."""
    ad, bo, pa = _levers(anchor, anchor_decode, bencode_overlap, prep_ahead)
    rows = []
    for kind in KINDS[:3]:
        for chunk in range(3):
            reuse = int(bool(text_reuse_mode) and kind != 'qualify-eager' and chunk == 1)
            rows.append({'kind': kind, 'frames': frames, 'placement': placement, 'anchor': anchor,
                         'decoder_graph': decoder_graph, 'anchor_decode': ad, 'bencode_overlap': bo,
                         'prep_ahead': pa,
                         'scene_id': QUALIFICATION_SCENES[kind],
                         'chunk_index': chunk, 'seed': QUALIFICATION_SEEDS[chunk],
                         'prompt': QUALIFICATION_PROMPTS[chunk], 'predecessor_anchor_sha256': '',
                         'stream_seq': -1, 'reuse_text': reuse, 'reset': 0})
    return rows


def fixed_names():
    """Every request name the setup and qualification create (all carry RUN_PREFIX)."""
    return [r['name'] for r in setup_graphs()] + [run_name(p) for p in qualification_params(49, 0)]


def stream_params(frames, stream_seq, prompt, seed, predecessor_anchor_sha256, scene_id, reuse_text=0,
                  placement=DEFAULT_PLACEMENT, reset=0, anchor=DEFAULT_ANCHOR, decoder_graph=DEFAULT_DECODER_GRAPH,
                  anchor_decode=None, bencode_overlap=None, prep_ahead=None):
    """Client helper: the parameter dict for one streaming chunk (frames/placement/anchor/decoder_graph and,
    packet117/118, anchor_decode/bencode_overlap/prep_ahead from GET /ltx-stream/status). reset=1 (stream_seq > 0)
    restarts the anchor chain with an unanchored chunk."""
    ad, bo, pa = _levers(anchor, anchor_decode, bencode_overlap, prep_ahead)
    return validate_params({'kind': 'stream', 'frames': frames, 'placement': placement, 'anchor': anchor,
                            'decoder_graph': decoder_graph, 'anchor_decode': ad, 'bencode_overlap': bo,
                            'prep_ahead': pa,
                            'scene_id': scene_id, 'chunk_index': stream_seq,
                            'seed': seed, 'prompt': prompt,
                            'predecessor_anchor_sha256': predecessor_anchor_sha256 if stream_seq else '',
                            'stream_seq': stream_seq, 'reuse_text': reuse_text, 'reset': reset})


def display_transient_bytes(frames):
    """Preregistered display allowance, not measured: 4GiB times (latent T/16)^2."""
    require(type(frames) is int and frames in (121, 145, 169), 'Unadmitted display length')
    temporal = (frames - 1) // 8 + 1
    return 13 * 2**29 if frames == 169 else (4 * 2**30 * temporal * temporal + 255) // 256


def checked_display_transient_bytes(frames, value):
    """An explicit launch reserve may increase, never reduce, the sealed census."""
    minimum = display_transient_bytes(frames)
    require(type(value) is int and minimum <= value <= 8 * 2**30,
            'Replica reserve must be integer bytes between the length census and 8 GiB')
    return value


def launch_display_transient_bytes(frames, env=None):
    from decimal import Decimal, DecimalException
    env = os.environ if env is None else env
    raw = env.get('LTX_DISPLAY_REPLICA_TRANSIENT_GIB')
    if raw is None:
        return display_transient_bytes(frames)
    require(env.get('LTX_DISPLAY_DEVICE', 'xpu:3') == 'xpu:2',
            'Explicit replica reserve requires xpu:2 display')
    try:
        value = Decimal(raw) * 2**30
        require(value.is_finite() and value == value.to_integral_value(),
                'Replica reserve must represent whole bytes')
        return checked_display_transient_bytes(frames, int(value))
    except (DecimalException, TypeError, OverflowError):
        raise ValueError('Invalid replica transient GiB') from None


def receipt_display_transient_bytes(frames, options):
    return checked_display_transient_bytes(frames, options.get(
        'display_replica_transient_budget_bytes', display_transient_bytes(frames)))


def launch_aux_residency(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_AUX_RESIDENCY', 'legacy')
    require(value in ('legacy', 'xpu2'), 'LTX_AUX_RESIDENCY must be legacy or xpu2')
    return value


def residency_qualification_id(qid, mode):
    require(mode in ('legacy', 'xpu2') and SHA_RE.fullmatch(qid) is not None, 'Invalid residency identity')
    return sha256(canonical({'numerical_qualification_id': qid, 'aux_residency': mode,
        'devices': {'upsampler': 'xpu:2' if mode == 'xpu2' else 'xpu:0',
                    'audio_vae': 'xpu:2' if mode == 'xpu2' else 'xpu:3'}}))


def check_residency_scope(frames, placement, anchor, decoder_graph, anchor_decode, mode, display, cone_graph_memory="off"):
    require(mode in ('legacy', 'xpu2'), 'Invalid auxiliary residency')
    require(mode == 'legacy' or (frames in (145, 169) and placement == 'two-way20-28'
        and anchor == 'frame' and decoder_graph == 0 and anchor_decode == 'cone'),
        'xpu2 auxiliary residency requires145/169 two-way20-28 frame dg0 cone')
    require(mode == 'legacy' or display == 'xpu:3', 'Auxiliary residency plus display replica lacks workspace margin')
    require(frames != 169 or mode == 'xpu2' or (mode == 'legacy' and display == 'xpu:2'
        and placement == 'two-way20-28' and anchor == 'frame' and decoder_graph == 0 and anchor_decode == 'cone'),
        '169 requires xpu2 auxiliaries/display3 or legacy auxiliaries/dg0 replica')
    require(cone_graph_memory in ('off', 'replica-release'), 'Invalid cone graph memory mode')
    candidate = cone_graph_memory == 'replica-release'
    require(not (frames >= 145 and decoder_graph == 1 and display == 'xpu:2') or
        (candidate and (frames, placement, anchor, decoder_graph, anchor_decode, mode, display) ==
         (145, 'two-way20-28', 'frame', 1, 'cone', 'legacy', 'xpu:2')),
        '145/169 dg1 display replica is memory-inadmissible')


DISPLAY_WORKERS = ('serial', 'parallel')

def launch_display_worker(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_DISPLAY_WORKER', 'serial')
    require(value in DISPLAY_WORKERS, 'LTX_DISPLAY_WORKER must be serial or parallel')
    return value


def check_display_worker_scope(worker, frames, placement, anchor, decoder_graph, anchor_decode,
                               auxiliary, device, schedule):
    require(worker in DISPLAY_WORKERS, 'Invalid display worker')
    require(worker == 'serial' or (frames in (145, 169) and placement == 'two-way20-28'
        and anchor == 'frame' and decoder_graph == 0 and anchor_decode == 'cone'
        and auxiliary == 'legacy' and device == 'xpu:2' and schedule == 'eager-display'),
        'Parallel display requires145/169 two-way20-28 frame dg0 cone legacy xpu:2 eager-display')


# Packet125: bounded native periodic maintenance; arithmetic and automatic GC unchanged.
def launch_snapshot_digest_cache(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_SNAPSHOT_DIGEST_CACHE', '0')
    if type(value) is not str or value not in ('0', '1'):
        raise ValueError('LTX_SNAPSHOT_DIGEST_CACHE must be 0 or 1')
    return int(value)


def check_snapshot_digest_scope(enabled, frames, placement, anchor, decoder_graph, levers, options):
    if type(enabled) is not int or enabled not in (0, 1):
        raise ValueError('Invalid snapshot digest cache')
    if not enabled:
        return
    if cone_memory_scope(frames, placement, anchor, decoder_graph, levers, options):
        return
    if (frames, placement, anchor, decoder_graph, tuple(levers)) != (
            145, 'two-way20-28', 'frame', 0, ('cone', 1, 1)) or any(
            options.get(k) != v for k, v in {
                'snapshot_mode': 'fingerprint', 'snapshot_schedule': 'full',
                'display_worker': 'serial', 'display_device': 'xpu:3',
                'aux_residency': 'legacy', 'display_schedule': 'sampler-a',
                'anchor_read_ahead': 0}.items()):
        raise ValueError('Snapshot digest cache requires the fixed 145-frame fingerprint scope')


def launch_gc_interval(environ=None):
    env = os.environ if environ is None else environ
    value = env.get('LTX_GC_INTERVAL_SECONDS', '10')
    require(value in ('10', '60'), 'LTX_GC_INTERVAL_SECONDS must be 10 or 60')
    return int(value)


def check_gc_scope(interval, frames, placement, anchor, decoder_graph, levers, options):
    require(type(interval) is int and interval in (10, 60), 'GC interval must be integer10 or60')
    if interval == 10:
        return
    if cone_memory_scope(frames, placement, anchor, decoder_graph, levers, options):
        return
    require((frames, placement, anchor, decoder_graph, tuple(levers)) ==
            (145, 'two-way20-28', 'frame', 0, ('cone', 1, 1)) and
            options.get('display_device') == 'xpu:3' and
            options.get('display_schedule') == 'sampler-a' and
            options.get('anchor_read_ahead') == 0 and
            options.get('snapshot_schedule') == 'full' and
            options.get('display_worker', 'serial') == 'serial',
            '60s GC interval requires145 frame dg0 cone bo1 pa1 serial display3 sampler-a full snapshots read-ahead0')


# Packet128 moves only periodic maintenance admission; native calls stay unchanged.
def launch_maintenance_mode(environ=None):
    value = (os.environ if environ is None else environ).get('LTX_MAINTENANCE_MODE', 'parent')
    if type(value) is not str or value not in ('parent', 'idle'):
        raise ValueError('LTX_MAINTENANCE_MODE must be parent or idle')
    return value


def check_maintenance_scope(mode, frames, placement, anchor, decoder_graph, levers, options):
    if type(mode) is not str or mode not in ('parent', 'idle'):
        raise ValueError('Invalid maintenance mode')
    if mode == 'parent':
        return
    if cone_memory_scope(frames, placement, anchor, decoder_graph, levers, options):
        return
    if (frames not in (145, 169) or placement != 'two-way20-28' or anchor != 'frame'
            or decoder_graph != 0 or tuple(levers) != ('cone', 1, 1)
            or any(options.get(k) != v for k, v in {
                'snapshot_mode': 'fingerprint', 'snapshot_schedule': 'full',
                'aux_residency': 'legacy', 'anchor_read_ahead': 0}.items())
            or (options.get('display_worker'), options.get('display_device'),
                options.get('display_schedule')) not in (
                    ('serial', 'xpu:3', 'sampler-a'),
                    ('parallel', 'xpu:2', 'eager-display'))):
        raise ValueError('Idle maintenance requires the fixed145/169 frame/cone legacy fingerprint scope')


# Packet131 changes allocator admission only, never numerical identity.
def check_display_allocator_release_scope(mode, frames, placement, anchor, decoder_graph, levers, options):
    if mode not in ('off', 'before-admission'):
        raise ValueError('Invalid display allocator release mode')
    if mode == 'off':
        return
    if not (frames == 169 and placement == 'two-way20-28' and anchor == 'frame'
            and decoder_graph == 0 and tuple(levers) == ('cone', 1, 1)
            and options.get('aux_residency', 'legacy') == 'legacy'
            and options.get('display_device') == 'xpu:2'
            and options.get('display_schedule') == 'eager-display'
            and options.get('display_worker', 'serial') == 'parallel'
            and options.get('snapshot_schedule') == 'full'
            and options.get('snapshot_mode') == 'fingerprint'
            and options.get('anchor_read_ahead') == 0):
        raise ValueError('Allocator release requires the fixed169 parallel display2 scope')


def cone_memory_scope(frames, placement, anchor, decoder_graph, levers, options):
    return options.get('cone_graph_memory', 'off') == 'replica-release' and (
        frames, placement, anchor, decoder_graph, tuple(levers)) == (
        145, 'two-way20-28', 'frame', 1, ('cone', 1, 1)) and all(
        options.get(k, default) == value for k, value, default in (
            ('display_device', 'xpu:2', None), ('display_schedule', 'eager-display', None),
            ('display_worker', 'serial', 'serial'), ('anchor_read_ahead', 0, None),
            ('snapshot_schedule', 'full', None), ('snapshot_mode', 'fingerprint', 'fingerprint'),
            ('aux_residency', 'legacy', 'legacy')))


def check_cone_memory_scope(mode, frames, placement, anchor, decoder_graph, levers, options):
    require(mode in ('off', 'replica-release'), 'Invalid cone graph memory mode')
    if mode == 'off':
        return
    require(cone_memory_scope(frames, placement, anchor, decoder_graph, levers, options),
            'Cone memory scope differs')
    require(options.get('decoder_graph_pool_cap_bytes') is None and
            options.get('display_allocator_release', 'off') == 'off',
            'Cone memory requires no cap and no replica allocator mode')
