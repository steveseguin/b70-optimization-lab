"""Inactive stdlib host-memory admission for CLIP-only replacement.

The tensor overlap is source-derived; the 8GiB margin is the existing screen's
operational headroom, not a proven bound on tokenizer/allocator/driver overhead.
"""
import json
from pathlib import Path
import struct

REGISTERED_STATE_BYTES = 26231584372
CHECKPOINT_TENSOR_BYTES = 26263774294
EXISTING_HEADROOM_BYTES = 8 * 1024**3


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def checkpoint_geometry(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Expected original regular checkpoint')
    with path.open('rb') as stream:
        size = struct.unpack('<Q', stream.read(8))[0]
        require(0 < size < 16 * 1024**2, 'Unexpected safetensors header size')
        header = json.loads(stream.read(size))
    records = [v for k, v in header.items() if k != '__metadata__']
    offsets = sorted(tuple(v['data_offsets']) for v in records)
    cursor = 0
    for start, end in offsets:
        require(type(start) is int and type(end) is int and start == cursor and end >= start, 'Unexpected checkpoint offsets')
        cursor = end
    require(cursor == CHECKPOINT_TENSOR_BYTES and path.stat().st_size == 8 + size + cursor,
            'Checkpoint extent differs from source-audited model')
    return {'checkpoint_tensor_bytes': cursor, 'checkpoint_header_bytes': size,
            'registered_state_bytes': REGISTERED_STATE_BYTES,
            'construction_overlap_bytes': cursor + REGISTERED_STATE_BYTES,
            'existing_headroom_bytes': EXISTING_HEADROOM_BYTES,
            'scope': 'Conservative mapped-checkpoint plus allocated CPU parameter/buffer overlap; not a measured total peak'}


def memory_snapshot():
    raw = Path('/proc/meminfo').read_text()
    parsed = dict(line.split(':', 1) for line in raw.splitlines())
    fields = {}
    for key in ('MemTotal', 'MemAvailable', 'MemFree', 'SwapFree', 'SwapTotal'):
        parts = parsed[key].split()
        require(len(parts) == 2 and parts[1] == 'kB' and parts[0].isdigit(), 'Malformed meminfo: ' + key)
        fields[key] = int(parts[0]) * 1024
    require(0 < fields['MemTotal'] and fields['MemAvailable'] <= fields['MemTotal'] and
            fields['MemFree'] <= fields['MemTotal'] and fields['SwapFree'] <= fields['SwapTotal'], 'Inconsistent meminfo')
    return {'source': '/proc/meminfo', 'raw': raw, 'bytes': fields}


def admission(stage, allocation_bytes, *, snapshot=None):
    require(type(allocation_bytes) is int and allocation_bytes >= 0, 'Invalid source-derived memory request')
    observed = memory_snapshot() if snapshot is None else snapshot
    required = allocation_bytes + EXISTING_HEADROOM_BYTES
    available = observed['bytes']['MemAvailable']
    require(type(available) is int and available >= 0, 'Invalid available RAM observation')
    return {'schema': 'ltx.host-embedding-memory-admission.v1', 'stage': stage,
            'tracked_allocation_bytes': allocation_bytes, 'existing_headroom_bytes': EXISTING_HEADROOM_BYTES,
            'required_available_bytes': required, 'observed': observed, 'passed': available >= required,
            'swap_counted_as_headroom': False, 'runtime_memory_settings_changed': False}


def restore_allocation(inspection):
    return sum(row['bytes'] for kind in ('parameters', 'buffers') for row in inspection[kind]['records']
               if row['device'] != 'cpu')
