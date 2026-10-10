"""Long-chunk geometry and actual sink logic on CPU, without codecs or processes.

The sink's production decode_clip/Clip definitions are extracted by AST; fake
PyAV supplies frames and native-length audio in memory. This proves its frame
count, pad/trim and overlap-drop behavior, not real MP4 encoding or decoding.
169-frame arithmetic is design evidence only: packet121 refuses that runtime
length. Cone tests allocate interval plans, never production video tensors.
"""
import ast
from pathlib import Path
import types
import unittest

import stream_contract as contract


HERE = Path(__file__).resolve().parent
SINK = HERE.parents[1] / 'stream' / 'ltx_rtmp_sink.py'


class Plane:
    line_size = 6

    def __bytes__(self):
        return b'\x11' * 12


class VideoFrame:
    width = height = 2
    pts = None
    planes = [Plane()]

    def reformat(self, **kwargs):
        return self


class AudioFrame:
    def __init__(self, samples):
        self.samples = samples
        self.planes = [audio_bytes(samples)]


def audio_bytes(samples):
    # 8000 bytes (one frame of stereo audio) is not a multiple of 256,
    # so this pattern detects a missing or wrongly positioned overlap drop.
    return (bytes(range(256)) * ((4 * samples + 255) // 256))[:4 * samples]


class Resampler:
    def __init__(self, **kwargs):
        pass

    def resample(self, frame):
        return [frame] if frame else []


class Container:
    def __init__(self, frames, samples):
        self.frames, self.samples = frames, samples
        self.streams = types.SimpleNamespace(
            video=[types.SimpleNamespace(average_rate=24)], audio=['audio'])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def decode(self, stream):
        if stream == 'audio':
            return [AudioFrame(self.samples)]
        return [VideoFrame() for _ in range(self.frames)]


def sink_clip(frames, samples, skip):
    tree = ast.parse(SINK.read_text())
    definitions = [node for node in tree.body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                   and node.name in ('Clip', 'decode_clip')]
    assert len(definitions) == 2
    namespace = {'FPS': 24, 'SR': 48000, 'SPF': 2000, 'ABYTES': 8000,
                 'log': lambda message: None,
                 'av': types.SimpleNamespace(
                     open=lambda path: Container(frames, samples), AudioResampler=Resampler)}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(SINK), 'exec'), namespace)
    # Deliberately omit manifest frames: playback follows decoded MP4 contents.
    return namespace['decode_clip'](
        {'seq': 0, 'path': 'in-memory-fake', 'skip_first_frames': skip}, 2, 2)


class SinkLengths(unittest.TestCase):
    pass


def sink_check(frames, samples, skip, field):
    def check(self):
        clip = sink_clip(frames, samples, skip)
        if field == 'video_count':
            self.assertEqual(len(clip.frames), frames - skip)
        elif field == 'audio_length':
            self.assertEqual(len(clip.audio), (frames - skip) * 8000)
        elif field == 'padding':
            self.assertEqual(clip.audio[-1520 * 4:], b'\0' * (1520 * 4))
        else:
            # Verify that the overlap drop moves the corresponding audio start
            # and preserves every remaining native sample before tail silence.
            native_bytes = (samples - skip * 2000) * 4
            self.assertEqual(clip.audio[:native_bytes], audio_bytes(samples)[skip * 8000:])
            self.assertEqual(clip.audio[native_bytes:], b'\0' * (1520 * 4))
    return check


for _frames, _samples in ((145, 288480), (169, 336480)):
    for _skip in (0, 1):
        for _field in ('video_count', 'audio_length', 'padding', 'audio_alignment'):
            setattr(SinkLengths, 'test_%d_skip%d_%s' % (_frames, _skip, _field),
                    sink_check(_frames, _samples, _skip, _field))


class LongGeometry(unittest.TestCase):
    def test_145_admitted_geometry(self):
        geometry = contract.geometry(145)
        self.assertEqual(geometry['temporal_latents'], 19)
        self.assertEqual(geometry['stage_tokens'], {'A': 304, 'B': 1216})
        self.assertEqual(geometry['stage_shapes'],
                         {'A': [1, 128, 19, 4, 4], 'B': [1, 128, 19, 8, 8]})
        self.assertEqual(geometry['tensor_shapes']['audio_latent'], [1, 8, 151, 16])
        self.assertEqual(geometry['tensor_shapes']['waveform'], [1, 2, 288480])
        self.assertEqual(geometry['new_frames_continuation'], 144)
        self.assertEqual(geometry['anchor_frame_index'], 144)
        self.assertEqual(contract.launch_frames({'LTX_STREAM_FRAMES': '145'}), 145)

    def test_169_sealed_formulas_design_only(self):
        frames = 169
        latent = (frames - 1) // 8 + 1
        audio_latent = round(frames / 24 * 25)
        samples = ((audio_latent - 1) * 4 + 1) * 160 * 3
        self.assertEqual((latent, latent * 16, latent * 64), (22, 352, 1408))
        self.assertEqual((audio_latent, samples), (176, 336480))
        self.assertEqual((frames - 1, (frames - 1) / 24), (168, 7.0))
        self.assertEqual(frames * 2000 - samples, 1520)

    def test_169_not_admitted(self):
        self.assertNotIn(169, contract.FRAME_CHOICES)
        with self.assertRaises(ValueError):
            contract.launch_frames({'LTX_STREAM_FRAMES': '169'})
        with self.assertRaises(ValueError):
            contract.geometry(169)


class ConePlanning(unittest.TestCase):
    def check_length(self, frames):
        import cpu_decoder
        import stream_anchor_decode
        torch, decoder, na = cpu_decoder.load()
        torch.set_num_threads(4)
        plan = stream_anchor_decode.ConePlan(
            frames, 64, 64, 256, (11, 11, 11), 8,
            na._window_bounds, na._pick_tiles, decoder.MLP_TOKEN_CHUNK)
        starts, ends = na._window_bounds(frames, 11, False)
        needed = {frames - 1}
        brute = [sorted(needed)]
        for _ in range(8):
            needed = {j for q in needed for j in range(starts[q], ends[q])}
            brute.append(sorted(needed))
        self.assertEqual([list(range(lo, hi)) for lo, hi in plan.need], brute[::-1])
        self.assertEqual(plan.need[0], (frames - 46, frames))
        self.assertFalse(torch.xpu.is_initialized())

    def test_145_cone_dependency(self):
        self.check_length(145)

    def test_169_cone_dependency_design_only(self):
        self.check_length(169)


class DecoderMaskPlanning(unittest.TestCase):
    def check_length(self, frames):
        import cpu_decoder
        import stream_decoder_graph
        _, decoder, na = cpu_decoder.load()
        # Read constructor defaults from sealed source, avoiding allocation of
        # the real decoder's weights. Follow its trailing pad, temporal shuffle
        # leading-frame drop and final context crop exactly.
        tree = ast.parse(cpu_decoder.DECODER_FILE.read_text())
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'NADiffusionDecoder')
        init = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                    and node.name == '__init__')
        names = [arg.arg for arg in init.args.args][-len(init.args.defaults):]
        defaults = dict(zip(names, init.args.defaults))
        kernels = ast.literal_eval(defaults['stage_kernels'])
        upsamples = ast.literal_eval(defaults['upsamples'])
        pad = (kernels[0][0] // 2) * 2
        dims = [(frames - 1) // 8 + 1 + pad, 8, 8]
        geometries = []
        scale_t = 1
        for stride, reduction in upsamples:
            geometries.append(tuple(dims))
            dims = [1 + (dims[0] - 1) * stride[0], dims[1] * stride[1], dims[2] * stride[2]]
            scale_t *= stride[0]
        dims[0] -= pad * scale_t
        geometries.append(tuple(dims))
        self.assertEqual(dims, [frames, 64, 64])
        entries = set()
        for geometry, kernel in zip(geometries, kernels):
            widths = [min(k, size) for k, size in zip(kernel, geometry)]
            tiles = na._pick_tiles(list(geometry), widths)
            for size, width, tile in zip(geometry, widths, tiles):
                starts, ends = na._window_bounds(size, width, False)
                for begin in range(0, size, tile):
                    end = min(size, begin + tile)
                    origin = starts[begin]
                    entries.add((tuple(v - origin for v in starts[begin:end]),
                                 tuple(v - origin for v in ends[begin:end])))
        self.assertLessEqual(len(entries), stream_decoder_graph.AXIS_MAX_ENTRIES)
        self.assertLessEqual(max(len(starts) * max(ends) for starts, ends in entries),
                             stream_decoder_graph.AXIS_MAX_ELEMENTS)
        self.assertGreater(len(entries), 0)

    def test_145_mask_cache_bounds(self):
        self.check_length(145)

    def test_169_mask_cache_bounds_design_only(self):
        self.check_length(169)


if __name__ == '__main__':
    unittest.main()
