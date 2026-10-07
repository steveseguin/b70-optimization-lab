"""CPU metadata/source prototype for the fixed49-frame, three-fixture pilot.

No tensor/driver imports, tensor conversions, numeric tensor operations or writes.
The parent owns authoritative session binding, storage admission and deployment.
"""
import ast
import copy
import hashlib
import json
import math
import re
import threading

GEOMETRY_SHA256 = '895b1c02ac764838b5d69446b0e5cf054884b191dd8b9446c5ce641ec40f2e52'
CAPTURE_SHA256 = '6495b0c4de7ac054e35a39fb00e7c7b979d5fb51d6e77bc0dee18bad9d0ec9da'
CAPTURE_PATHS = ('capture_node.py', 'source/scripts/capture_node.py', 'source/custom_nodes/ltx_baseline_capture/__init__.py')
SERIALIZER_SHA256 = {
    'torch.py': 'f3f476d1f8c04fe65fa3797426556a0b7afa43f8c4db9db6b799c7cf84748f3d',
    '_safetensors_rust.abi3.so': 'e6f17a9e9846bc2bc4ad94cc5431746b59785de3d2681ef2666e8890ae192dfb',
}
FULL_SHAPES = {'images': (49, 384, 640, 3), 'video_latent': (1, 128, 7, 12, 20),
               'audio_latent': (1, 8, 51, 16), 'waveform': (1, 2, 96480)}
FILL_SHAPES = {'images': (1, 8, 8, 3), 'video_latent': FULL_SHAPES['video_latent'],
               'audio_latent': FULL_SHAPES['audio_latent'], 'waveform': (1, 2, 8)}
STAGE_A = (1, 128, 7, 6, 10)
FULL_PAYLOAD_BYTES = 146164992
HEADER_BOUND = 65544  # 8-byte LE length plus at most65536 padded JSON bytes.
FULL_FILE_BOUND = FULL_PAYLOAD_BYTES + HEADER_BOUND
FILL_FILE_BOUND = 1024 ** 2
RAW_CAPTURE_BUDGET = 14 * FULL_FILE_BOUND + 8 * FILL_FILE_BOUND
WRITE_ALLOWANCE = 4 * 1024 ** 3


class GuardError(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise GuardError(message)


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def serializer_binding(sources):
    """CPU bytes supplied by packet builder; binds both wrapper and native writer."""
    require(set(sources) == set(SERIALIZER_SHA256), 'Missing serializer source binding')
    for name, expected in SERIALIZER_SHA256.items():
        require(hashlib.sha256(sources[name]).hexdigest() == expected, 'Serializer changed: ' + name)
    return dict(SERIALIZER_SHA256)


def _replace(text, old, new):
    require(text.count(old) == 1, 'Source anchor differs: ' + repr(old))
    return text.replace(old, new)


def transform_geometry(raw):
    """Transform pristine99b shape constants, BEFORE parent's authority extension.

    This does not permit old25-frame reference checks or authorize a runtime.
    The original ten seeded decoder-probe inputs remain unchanged in count.
    """
    require(hashlib.sha256(raw).hexdigest() == GEOMETRY_SHA256, 'Geometry parent source changed')
    text = raw.decode('utf-8')
    text = _replace(text, "WIDTH, HEIGHT = dimensions(OUTPUT_SIZE)",
                    "WIDTH, HEIGHT = dimensions(OUTPUT_SIZE)\n"
                    "if OUTPUT_SIZE != '640x384':\n"
                    "    raise RuntimeError('duration108 requires640x384')\n"
                    "FRAMES, TEMPORAL_LATENTS, AUDIO_LATENTS, AUDIO_SAMPLES = 49, 7, 51, 96480")
    text = _replace(text, 'TOKENS = (4 * (HEIGHT // 64) * (WIDTH // 64), 4 * (HEIGHT // 32) * (WIDTH // 32))',
                    'TOKENS = (TEMPORAL_LATENTS * (HEIGHT // 64) * (WIDTH // 64), TEMPORAL_LATENTS * (HEIGHT // 32) * (WIDTH // 32))')
    text = _replace(text, 'return (batch, 128, 4, h // divisor, w // divisor)',
                    'return (batch, 128, TEMPORAL_LATENTS, h // divisor, w // divisor)')
    text = _replace(text, 'return (25, h, w, 3)', 'return (FRAMES, h, w, 3)')
    text = _replace(text, '(1, 8, 26, 16)', '(1, 8, AUDIO_LATENTS, 16)')
    text = _replace(text, '(1, 2, 48480)', '(1, 2, AUDIO_SAMPLES)')
    text = _replace(text, "'video_latent_shape': list(v.shape),",
                    "'video_latent_shape': list(v.shape), 'frame_count': FRAMES,\n"
                    "               'audio_latent_shape': list(a.shape),")
    text = _replace(text,
                    "    if OUTPUT_SIZE != DEFAULT:\n        raise RuntimeError('stored reference path refused at output size ' + OUTPUT_SIZE)",
                    "    raise RuntimeError('duration108 refuses historical25-frame references')")
    ast.parse(text)
    return text.encode('utf-8')


def transform_capture(path, raw):
    """Move directory creation after existing stats and new guard; retain arithmetic."""
    require(path in CAPTURE_PATHS, 'Unknown capture source path')
    require(hashlib.sha256(raw).hexdigest() == CAPTURE_SHA256, 'Capture parent source changed')
    text = raw.decode('utf-8')
    text = _replace(text, 'from safetensors.torch import save_file',
                    'from safetensors.torch import save_file\nimport ltx_duration_guard')
    text = _replace(text, '        out.mkdir(parents=True, exist_ok=False)\n', '')
    text = _replace(text, "        save_file(tensors, str(out / 'tensors.safetensors'))",
                    "        ltx_duration_guard.require_capture_prewrite(tensors, report, run_name)\n"
                    "        out.mkdir(parents=True, exist_ok=False)\n"
                    "        save_file(tensors, str(out / 'tensors.safetensors'))")
    ast.parse(text)
    return text.encode('utf-8')


def _shape(tensor):
    shape = tuple(tensor.shape)
    require(all(type(x) is int and x > 0 for x in shape), 'Invalid tensor dimensions')
    return shape


def header_size_bound(shapes):
    """Fixed four F32 names, dimensions/offsets, no user metadata;8-byte padding.

    Sorted keys mirror the equal-dtype serializer order. Spaces deliberately
    overestimate compact JSON. This is format accounting, not serialization.
    """
    offset, header = 0, {}
    for name in sorted(shapes):
        size = math.prod(shapes[name]) * 4
        header[name] = {'dtype': 'F32', 'shape': list(shapes[name]), 'data_offsets': [offset, offset + size]}
        offset += size
    length = len(json.dumps(header, ensure_ascii=True, allow_nan=False).encode('utf-8'))
    return 8 + ((length + 7) // 8) * 8


class CaptureGuard:
    """Bind22 capture rows to a trusted, synchronous current-session callback.

    capture_rows: ordered dictionaries with name, graph_sha256 and role.
    role counts are12 full,8 fill,2 setup; setup is charged as full and accepts
    either an exact full tuple or an exact fill tuple. No roles come from graphs'
    caller-controlled node arguments or output names at capture time.
    """
    def __init__(self, plan_sha256, capture_rows, active_request):
        require(_sha(plan_sha256), 'Invalid plan binding')
        require(callable(active_request), 'Trusted active-request callback required')
        require(type(capture_rows) is list and len(capture_rows) == 22, 'Exactly22 capture rows required')
        require(all(type(r) is dict and set(r) == {'name', 'graph_sha256', 'role'} for r in capture_rows),
                'Capture row schema differs')
        require(all(isinstance(r['name'], str) and re.fullmatch('[a-z0-9][a-z0-9_-]{0,119}', r['name'])
                    and _sha(r['graph_sha256']) and r['role'] in ('full', 'fill', 'setup') for r in capture_rows),
                'Invalid registered capture row')
        require(len({r['name'] for r in capture_rows}) == 22, 'Duplicate registered capture name')
        require({role: sum(r['role'] == role for r in capture_rows) for role in ('full', 'fill', 'setup')}
                == {'full': 12, 'fill': 8, 'setup': 2}, 'Capture role counts differ')
        self.plan_sha256, self.rows = plan_sha256, copy.deepcopy(capture_rows)
        self.active_request = active_request
        self.lock, self.failed = threading.Lock(), None
        self.used, self.reserved_bytes = [], 0

    def _authorization(self, run_name):
        active = self.active_request()
        require(type(active) is dict, 'Missing active authoritative request')
        require(active.get('plan_sha256') == self.plan_sha256 and active.get('name') == run_name,
                'Active plan/request identity differs')
        require(isinstance(active.get('prompt_id'), str) and 0 < len(active['prompt_id']) <= 128,
                'Missing active prompt identity')
        require(len(self.used) < len(self.rows), 'Capture attempt allowance exhausted')
        row = self.rows[len(self.used)]
        require(row['name'] == run_name and active.get('graph_sha256') == row['graph_sha256'],
                'Capture not next registered authoritative graph')
        require(active['prompt_id'] not in {r['prompt_id'] for r in self.used}, 'Repeated capture prompt')
        return dict(active), row

    def validate(self, tensors, report, run_name):
        with self.lock:
            require(self.failed is None, 'Capture guard already failed: ' + str(self.failed))
            try:
                active, row = self._authorization(run_name)
                require(type(tensors) is dict and set(tensors) == set(FULL_SHAPES), 'Exactly four captured tensors required')
                require(type(report) is dict and report.get('run_name') == run_name
                        and type(report.get('sample_rate')) is int and report['sample_rate'] == 48000,
                        'Capture report identity/sample rate differs')
                require(type(report.get('tensors')) is dict and set(report['tensors']) == set(tensors),
                        'Capture report tensor keys differ')
                shapes = {name: _shape(t) for name, t in tensors.items()}
                is_full = shapes == FULL_SHAPES
                fill_video = shapes['video_latent'] in (STAGE_A, FULL_SHAPES['video_latent'])
                is_fill = fill_video and all(shapes[k] == FILL_SHAPES[k] for k in ('images', 'audio_latent', 'waveform'))
                require((row['role'] == 'full' and is_full) or (row['role'] == 'fill' and is_fill)
                        or (row['role'] == 'setup' and (is_full or is_fill)), 'Capture role/shape tuple differs')
                payload_bytes = 0
                for name, tensor in tensors.items():
                    require(str(tensor.dtype) == 'torch.float32' and str(tensor.device) == 'cpu'
                            and str(tensor.layout) == 'torch.strided' and tensor.is_contiguous() is True,
                            'Capture must already be dense contiguous CPU float32: ' + name)
                    expected = math.prod(shapes[name]) * 4
                    require(type(tensor.element_size()) is int and tensor.element_size() == 4
                            and type(tensor.numel()) is int and tensor.numel() * 4 == expected,
                            'Tensor byte metadata differs: ' + name)
                    stats = report['tensors'][name]
                    require(type(stats) is dict and stats.get('dtype') == 'torch.float32'
                            and stats.get('shape') == list(shapes[name]) and stats.get('finite') is True
                            and _sha(stats.get('sha256')), 'Existing capture statistics differ/nonfinite: ' + name)
                    require(all(type(stats.get(k)) in (int, float) and math.isfinite(stats[k]) for k in ('min', 'max', 'std')),
                            'Nonfinite capture statistics: ' + name)
                    payload_bytes += expected
                header_bound = header_size_bound(shapes)
                require(header_bound <= HEADER_BOUND, 'Safetensors header exceeds reserved bound')
                require(not is_full or payload_bytes == FULL_PAYLOAD_BYTES, 'Full payload byte count differs')
                actual_file_bound = payload_bytes + HEADER_BOUND
                require(not is_fill or actual_file_bound <= FILL_FILE_BOUND, 'Placeholder exceeds1MiB before write')
                charge = FILL_FILE_BOUND if row['role'] == 'fill' else FULL_FILE_BOUND
                require(actual_file_bound <= charge, 'Capture exceeds role byte allowance')
                require(self.reserved_bytes + charge <= RAW_CAPTURE_BUDGET, 'Raw capture byte allowance exhausted')
                again, _ = self._authorization(run_name)
                require(again == active, 'Active session changed during prewrite validation')
                evidence = {'name': run_name, 'prompt_id': active['prompt_id'], 'graph_sha256': row['graph_sha256'],
                            'role': row['role'], 'actual_shape_kind': 'full' if is_full else 'fill',
                            'payload_bytes': payload_bytes, 'header_bound': HEADER_BOUND,
                            'format_header_size_bound': header_bound, 'file_bound': actual_file_bound, 'charged_bytes': charge}
                # Charge BEFORE mkdir/save; failures are never refunded/retried.
                self.used.append(evidence)
                self.reserved_bytes += charge
                return copy.deepcopy(evidence)
            except Exception as error:
                self.failed = str(error)
                raise

    def receipt(self):
        with self.lock:
            return {'schema': 'ltx.duration108-prewrite.v1', 'plan_sha256': self.plan_sha256,
                    'captures_reserved': len(self.used), 'capture_cap': 22,
                    'reserved_bytes': self.reserved_bytes, 'raw_budget_bytes': RAW_CAPTURE_BUDGET,
                    'failed': self.failed, 'captures': copy.deepcopy(self.used)}


_guard = None


def configure(plan_sha256, capture_rows, active_request):
    global _guard
    require(_guard is None, 'Duration capture guard already configured')
    _guard = CaptureGuard(plan_sha256, capture_rows, active_request)
    return _guard


def require_capture_prewrite(tensors, report, run_name):
    require(_guard is not None, 'Duration capture guard is not configured')
    return _guard.validate(tensors, report, run_name)
