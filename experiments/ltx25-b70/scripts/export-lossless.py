#!/usr/bin/env python3
"""Export float FFV1/PCM and prove decoded samples equal the tensor archive."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import av
import numpy as np
from safetensors.numpy import load_file


def export(source, destination):
    assert not destination.exists(), destination
    tensors = load_file(str(source / 'tensors.safetensors'))
    summary = json.loads((source / 'summary.json').read_text())
    images = tensors['images']
    audio = tensors['waveform'][0]
    sample_rate = summary['sample_rate']
    assert images.dtype == np.float32 and audio.dtype == np.float32
    assert audio.shape[0] in (1, 2)
    layout = 'mono' if audio.shape[0] == 1 else 'stereo'
    with av.open(str(destination), 'w') as out:
        video = out.add_stream('ffv1', rate=24)
        video.width, video.height = images.shape[2], images.shape[1]
        video.pix_fmt = 'gbrpf32le'
        # Float RGB is supported by FFV1 version 4, marked experimental by FFmpeg.
        video.options = {'level': '4', 'strict': 'experimental'}
        sound = out.add_stream('pcm_f32le', rate=sample_rate)
        sound.layout = layout
        for i, array in enumerate(images):
            frame = av.VideoFrame.from_ndarray(array, format='gbrpf32le')
            frame.pts, frame.time_base = i, Fraction(1, 24)
            for packet in video.encode(frame):
                out.mux(packet)
        for packet in video.encode():
            out.mux(packet)
        frame = av.AudioFrame.from_ndarray(audio, format='fltp', layout=layout)
        frame.sample_rate, frame.pts, frame.time_base = sample_rate, 0, Fraction(1, sample_rate)
        for packet in sound.encode(frame):
            out.mux(packet)
        for packet in sound.encode():
            out.mux(packet)
    with av.open(str(destination)) as inp:
        decoded_images = np.stack([f.to_ndarray(format='gbrpf32le') for f in inp.decode(video=0)])
    with av.open(str(destination)) as inp:
        decoded_audio = []
        for frame in inp.decode(audio=0):
            array = frame.to_ndarray()
            if not frame.format.is_planar:
                array = array.reshape(-1, audio.shape[0]).T
            decoded_audio.append(array)
        decoded_audio = np.ascontiguousarray(np.concatenate(decoded_audio, axis=1))
    video_equal = np.array_equal(images.view(np.uint8), decoded_images.view(np.uint8))
    audio_equal = np.array_equal(audio.view(np.uint8), decoded_audio.view(np.uint8))
    report = {'path': str(destination), 'video_codec': 'FFV1 v4 float RGB32 (experimental codec profile)',
              'audio_codec': 'PCM float32', 'video_roundtrip_bitwise': video_equal,
              'audio_roundtrip_bitwise': audio_equal,
              'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}
    destination.with_suffix('.verification.json').write_text(json.dumps(report, indent=2) + '\n')
    assert video_equal and audio_equal, report
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.source, args.destination), indent=2))
