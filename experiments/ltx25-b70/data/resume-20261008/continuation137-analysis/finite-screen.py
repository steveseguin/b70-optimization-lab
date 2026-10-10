#!/usr/bin/env python3
"""CPU-only packet137 screening: fresh finite-byte predicates, no runtime imports.

Run with nice -n 19 env OMP_NUM_THREADS=2 python3 -B finite-screen.py.
Emits JSON to stdout; writes no files and allocates no device state.
"""
import hashlib
import json
import random
import statistics
import struct
import time

BLOCK = 65536
TABLE = bytes(128 if (byte & 127) == 127 else 0 for byte in range(256))


def scalar(raw):
    if type(raw) is not bytes or len(raw) % 4:
        raise ValueError('immutable complete F32 bytes required')
    return all(word & 0x7f800000 != 0x7f800000
               for (word,) in struct.iter_unpack('<I', raw))


def bulk(raw):
    if type(raw) is not bytes or len(raw) % 4:
        raise ValueError('immutable complete F32 bytes required')
    for offset in range(0, len(raw), BLOCK):
        part = raw[offset:offset + BLOCK]
        if (int.from_bytes(part[3::4].translate(TABLE), 'little') &
                int.from_bytes(part[2::4], 'little')):
            return False
    return True


def main():
    checks = 0
    # The finiteness decision depends only on the upper two bytes. Exhaustively
    # cover those, at four lower-byte patterns including signalling/quiet NaNs.
    for lower in (b'\0\0', b'\xff\xff', b'\x01\0', b'\x55\xaa'):
        for high in range(256):
            for low in range(256):
                raw = lower + bytes((low, high))
                assert scalar(raw) == bulk(raw)
                checks += 1
    # Flags on different words must not combine, including across a block edge.
    for prefix in (0, BLOCK - 4, BLOCK, BLOCK + 4):
        raw = bytes(prefix) + bytes((0, 0, 0, 127, 0, 0, 128, 0))
        assert scalar(raw) is True and bulk(raw) is True
        checks += 1
    frame = bytes(786432)
    for offset in (0, 4, BLOCK - 4, BLOCK, BLOCK + 4, len(frame) - 4):
        for word in (0x7f800000, 0xff800000, 0x7f800001, 0x7fffffff,
                     0xff800001, 0xffffffff, 0x7f7fffff, 0xff7fffff,
                     0x00000000, 0x80000000, 0x00000001, 0x807fffff):
            raw = frame[:offset] + struct.pack('<I', word) + frame[offset + 4:]
            assert scalar(raw) == bulk(raw)
            checks += 1
    for bad in (None, '', bytearray(4), memoryview(bytes(4)), b'\0', bytes(3), bytes(5)):
        for fn in (scalar, bulk):
            try:
                fn(bad)
            except ValueError:
                checks += 1
            else:
                raise AssertionError('invalid input admitted')
    assert scalar(b'') is True and bulk(b'') is True
    checks += 1
    rng = random.Random(137)
    raw = b''.join(struct.pack('<f', rng.random()) for _ in range(256 * 256 * 3))
    samples = {'scalar': [], 'bulk': []}
    # Alternate the order to avoid assigning steady drift to either predicate.
    for trial in range(51):
        order = ((scalar, bulk) if trial % 2 == 0 else (bulk, scalar))
        for fn in order:
            started = time.perf_counter()
            assert fn(raw) is True
            samples[fn.__name__].append(time.perf_counter() - started)
    medians = {name: statistics.median(values) for name, values in samples.items()}
    delta = medians['scalar'] - medians['bulk']
    result = {
        'schema': 'ltx.continuation137.finite-cpu-screen.v1',
        'cpu_only': True, 'runtime_imports': False,
        'source_parent_manifest_sha256': '4356482eae2f1d7ac95b17e6483379ceed0cc90ed488d46765803451980402c3',
        'checks': checks, 'frame_bytes': len(raw), 'block_bytes': BLOCK,
        'frame_sha256': hashlib.sha256(raw).hexdigest(),
        'trials_per_arm': 51, 'seconds': samples, 'median_seconds': medians,
        'median_delta_seconds': delta,
        'call_census': {
            'pre_sampler_a': {'read_anchor': 1, 'conditioning_begin': 1, 'stage_a': 4},
            'prompt_thread': {'read_anchor': 1, 'conditioning_begin': 1, 'stage_a': 4,
                              'stage_b': 4, 'conditioning_finish': 1},
            'cone_to_anchor_publication': {'write_anchor': 1},
            'overlapped_decode_precompute': {'stage_a': 2, 'stage_b': 2},
        },
        'predicted_cpu_seconds_removed': {
            'pre_sampler_a_6_checks': 6 * delta,
            'prompt_thread_11_checks': 11 * delta,
            'prompt_and_anchor_publication_12_checks': 12 * delta,
            'overlapped_precompute_4_checks_not_added_to_period': 4 * delta,
        },
        'limits': ['Synthetic finite-frame CPU predicate benchmark, not native timing.',
                   'Twelve serially dependent checks are a CPU-work estimate, not an observed period gain.',
                   'Precompute checks overlap other work and are not added to period savings.',
                   'No model output, snapshot, hash, memory floor, owner check or source pin is removed.'],
    }
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
