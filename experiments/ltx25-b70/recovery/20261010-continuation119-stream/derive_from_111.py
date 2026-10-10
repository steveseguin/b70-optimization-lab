#!/usr/bin/env python3
"""Derive the three geometry-retargeted 111 helpers, as exact anchored replacements.

Packet115 adds guard115 (conditioning_guard first_stage).

conditioning_guard.py, native_bindings.py and continuation_anchor.py in this
directory must equal derive(<sealed 111 bytes>). `--write` regenerates them
(exclusive per file unless --replace); default only checks. CPU/stdlib only.
"""
import argparse
import hashlib
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-native-111')
SOURCES = {
    'conditioning_guard.py': '5cf7c634e35e111299552b086df4bbbbe856fc1db6838d0fde2f85f2927dfaa1',
    'native_bindings.py': 'b07b1fc71426ce2eaf8f47236d90140a5600347b88e451742d1d13916669bb02',
    'continuation_anchor.py': 'a3aa2c357f47af7cc3e98b941f7473bcaf37ef376e2772dc9270c81159e96319',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('Anchor count differs (%d != %d): %r' % (text.count(old), count, old[:80]))
    return text.replace(old, new)


def guard(text, candidate_sha):
    text = replace(text, '"""Inactive, CPU-only stage guards for two native continuation conditioning calls.',
                   '"""Packet112 stage guards for the two native conditioning calls (256x256, 49 or 25 frames).')
    text = replace(text, "SHAPES = {'A': [1, 128, 7, 6, 10], 'B': [1, 128, 7, 12, 20]}",
                   "import stream_contract as _contract\n"
                   "_GEOMETRY = _contract.geometry(_contract.launch_frames())\n"
                   "SHAPES = _GEOMETRY['stage_shapes']\n"
                   "ANCHOR_SHAPE = list(_contract.ANCHOR_SHAPE)\n"
                   "MASK_SHAPE = _GEOMETRY['noise_mask_shape']\n"
                   "CANDIDATE_SHA256 = '" + candidate_sha + "'")
    text = replace(text, '    """One controller, at most four conditioned requests (two per replay pass).',
                   '    """One candidate controller, serial conditioned requests without a count bound.')
    text = replace(text,
        "        need(cls.__name__ == 'NativeReferenceSafety' and path is not None and\n"
        "             hashlib.sha256(Path(path).read_bytes()).hexdigest() == CONTROLLER_SHA256,\n"
        "             'Exact sealed110 NativeReferenceSafety required')",
        "        base = cls.__mro__[1] if len(cls.__mro__) > 1 else None\n"
        "        base_path = inspect.getsourcefile(base) if base is not None else None\n"
        "        need(cls.__name__ == 'CandidateSafety' and path is not None and base is not None and\n"
        "             base.__name__ == 'NativeReferenceSafety' and base_path is not None and\n"
        "             hashlib.sha256(Path(path).read_bytes()).hexdigest() == CANDIDATE_SHA256 and\n"
        "             hashlib.sha256(Path(base_path).read_bytes()).hexdigest() == CONTROLLER_SHA256,\n"
        "             'Exact packet112 CandidateSafety over sealed NativeReferenceSafety required')")
    text = replace(text, 'self._tensor(self.anchor, [1, 384, 640, 3])', 'self._tensor(self.anchor, ANCHOR_SHAPE)')
    text = replace(text, 'self._tensor(anchor, [1, 384, 640, 3])', 'self._tensor(anchor, ANCHOR_SHAPE)')
    text = replace(text, "                 request_id == self.controller.active and len(self.seen) < 4,\n"
                         "                 'New active conditioned request required within four-request bound')",
                   "                 request_id == self.controller.active,\n"
                   "                 'New active conditioned request required')")
    text = replace(text, "self._tensor(output['noise_mask'], [1, 1, 7, 1, 1])", "self._tensor(output['noise_mask'], MASK_SHAPE)")
    return guard115(text)


def guard115(text):
    """Packet115: first_stage='B' admits a stage-B-only request (the mixed anchor). Default 'A' unchanged."""
    text = replace(text, '"""Packet112 stage guards for the two native conditioning calls (256x256, 49 or 25 frames).\n',
                   '"""Packet112 stage guards for the two native conditioning calls (256x256, 49 or 97 frames).\n\n'
                   "Packet115: begin_request(first_stage='B') admits a request whose only native conditioning\n"
                   'call is stage B (the mixed anchor: stage A is the latent slot-0 copy, stage B the native\n'
                   "image conditioning on the decoded frame). Default 'A' is the packet112-114 behaviour.\n")
    text = replace(text, '    def begin_request(self, request_id, *, anchor, expected_anchor_sha256):',
                   "    def begin_request(self, request_id, *, anchor, expected_anchor_sha256, first_stage='A'):")
    text = replace(text, "                 re.fullmatch('[0-9a-f]{64}', expected_anchor_sha256), 'Invalid anchor SHA256')\n",
                   "                 re.fullmatch('[0-9a-f]{64}', expected_anchor_sha256), 'Invalid anchor SHA256')\n"
                   "            need(first_stage in ('A', 'B'), 'First conditioning stage is A or B')\n")
    text = replace(text, "            self.next_stage = 'A'\n            self._identity(request_id)",
                   "            self.next_stage = first_stage\n            self._identity(request_id)")
    text = replace(text, "                                  'anchor_sha256': expected_anchor_sha256,\n",
                   "                                  'anchor_sha256': expected_anchor_sha256,\n"
                   "                                  'first_stage': first_stage,\n")
    text = replace(text, "                 'Expected stage A then B exactly once')",
                   "                 'Expected stage A then B (or B alone) exactly once')")
    text = replace(text, "            need(self.next_stage == 'done', 'Both conditioning stages must complete')",
                   "            need(self.next_stage == 'done', 'Every admitted conditioning stage must complete')")
    return text


def bindings(text):
    text = replace(text, '"""Trusted111 native conditioning bindings; inert until explicit runtime setup.',
                   '"""Packet112 native conditioning bindings (256x256 anchor); inert until runtime setup.')
    text = replace(text, "require(meta['shape'] == [1, 384, 640, 3], 'Anchor geometry changed')",
                   "require(meta['shape'] == [1, 256, 256, 3], 'Anchor geometry changed')")
    return text


def anchor(text):
    text = replace(text, '"""Inactive, CPU-only F32 continuation anchor verification; no Comfy registration.',
                   '"""Packet112 F32 anchor extraction from qualification captures (last frame, 256x256).')
    text = replace(text, "SHAPES = {'images': [49, 384, 640, 3], 'video_latent': [1, 128, 7, 12, 20],\n"
                         "          'audio_latent': [1, 8, 51, 16], 'waveform': [1, 2, 96480]}\n"
                         "ANCHOR_SHAPE = [1, 384, 640, 3]\nFRAME_INDEX = 48\nFRAME_BYTES = 2949120",
                   "import stream_contract as _contract\n"
                   "_GEOMETRY = _contract.geometry(_contract.launch_frames())\n"
                   "SHAPES = _GEOMETRY['tensor_shapes']\n"
                   "ANCHOR_SHAPE = list(_contract.ANCHOR_SHAPE)\nFRAME_INDEX = _GEOMETRY['anchor_frame_index']\n"
                   "FRAME_BYTES = _contract.ANCHOR_BYTES")
    text = replace(text, 'MAX_FILE = 146164992 + MAX_HEADER + 8',
                   "MAX_FILE = _GEOMETRY['full_payload_bytes'] + MAX_HEADER + 8")
    return text


def derive():
    candidate_sha = sha((HERE / 'candidate_safety.py').read_bytes())
    out = {}
    for name, expected in SOURCES.items():
        raw = (PARENT / 'source/scripts' / name).read_bytes()
        if sha(raw) != expected:
            raise ValueError('Sealed111 source changed: ' + name)
        text = raw.decode()
        text = {'conditioning_guard.py': lambda t: guard(t, candidate_sha),
                'native_bindings.py': bindings, 'continuation_anchor.py': anchor}[name](text)
        compile(text, name, 'exec')
        out[name] = text.encode()
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = derive()
    for name, raw in result.items():
        path = HERE / name
        if args.write:
            path.write_bytes(raw)
        elif not path.exists() or path.read_bytes() != raw:
            print('differs: ' + name)
            sys.exit(1)
    print({n: sha(r) for n, r in result.items()})


if __name__ == '__main__':
    main()
