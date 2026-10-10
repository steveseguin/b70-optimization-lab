"""Packet131 opt-in cone graph admission; inert and stdlib-only until called.

A 5 GiB capture allowance is conservative planning, not an allocator hard cap.
No output or floor changes. One optional process-wide unused-cache release per
cone admission, never a retry. Qualification full card3 references are retained.
"""
import os

ENV = 'LTX_CONE_GRAPH_MEMORY'
GIB = 2**30
CAPTURE_RESERVE = 5 * GIB
FLOOR = 9 * GIB
SCREEN = 3 * GIB // 4
CHOICES = ('off', 'replica-release')
SCOPE = {
    'LTX_STREAM_FRAMES': '145', 'LTX_SAMPLER_PLACEMENT': 'two-way20-28',
    'LTX_ANCHOR': 'frame', 'LTX_DECODER_GRAPH': '1', 'LTX_ANCHOR_DECODE': 'cone',
    'LTX_BENCODE_OVERLAP': '1', 'LTX_PREP_AHEAD': '1',
    'LTX_SNAPSHOT_MODE': 'fingerprint', 'LTX_SNAPSHOT_SCHEDULE': 'full',
    'LTX_ANCHOR_READ_AHEAD': '0', 'LTX_AUX_RESIDENCY': 'legacy',
    'LTX_DISPLAY_DEVICE': 'xpu:2', 'LTX_DISPLAY_SCHEDULE': 'eager-display',
    'LTX_DISPLAY_WORKER': 'serial', 'LTX_DISPLAY_ALLOCATOR_RELEASE': 'off',
}
DEFAULTS = {'LTX_SNAPSHOT_SCHEDULE': 'full', 'LTX_ANCHOR_READ_AHEAD': '0',
            'LTX_AUX_RESIDENCY': 'legacy', 'LTX_DISPLAY_WORKER': 'serial',
            'LTX_DISPLAY_ALLOCATOR_RELEASE': 'off'}

def launch_mode(env=None):
    env = os.environ if env is None else env
    value = env.get(ENV, 'off')
    if value not in CHOICES:
        raise ValueError('Invalid cone graph memory mode')
    return value

def validate_scope(env=None):
    env = os.environ if env is None else env
    mode = launch_mode(env)
    if mode != 'off':
        if any(env.get(k, DEFAULTS.get(k)) != v for k, v in SCOPE.items()):
            raise ValueError('Cone memory requires fixed145 dg1 cone serial replica2 scope')
        if env.get('LTX_DECODER_GRAPH_POOL_CAP_GB') is not None:
            raise ValueError('Cone memory uses exactly one private graph; pool cap must be unset')
    return mode

def admit(torch, free_bytes, *, mode, first_capture):
    if mode not in CHOICES or type(first_capture) is not bool:
        raise ValueError('Invalid cone memory admission')
    if mode == 'off':
        return None
    required = FLOOR + SCREEN + (CAPTURE_RESERVE if first_capture else 0)
    import allocator_release130
    free, release = allocator_release130.before_admission(torch, free_bytes,
        mode='before-admission', required_bytes=required, phase='before-cone')
    record = dict(schema='ltx.stream131.cone-memory.v1', mode=mode,
        first_capture=first_capture, capture_reserve_bytes=CAPTURE_RESERVE if first_capture else 0,
        floor_bytes=FLOOR, screening_bytes=SCREEN, required_bytes=required,
        free_bytes=free, margin_bytes=free-required, allocator_release=release,
        reserve_is_measured=False)
    if free < required:
        error = RuntimeError('Cone graph memory refused: physical free below capture/floor/screen: ' + repr(record))
        error.admission = record
        raise error
    return record

def validate_record(record):
    """Validate the physical admission and complete release audit, never reservation credit."""
    import math

    def require(ok, message):
        if not ok:
            raise ValueError('Cone admission evidence: ' + message)

    def mapping(value, label):
        require(type(value) is dict, label + ' must be an object')
        return value

    def integer(value, label, minimum=0):
        require(type(value) is int and value >= minimum, label + ' must be an integer >= ' + str(minimum))
        return value

    def literal(value, wanted, label):
        require(type(value) is type(wanted) and value == wanted, label + ' differs')

    record = mapping(record, 'record')
    literal(record.get('schema'), 'ltx.stream131.cone-memory.v1', 'schema')
    literal(record.get('mode'), 'replica-release', 'mode')
    first = record.get('first_capture')
    require(type(first) is bool, 'capture phase must be boolean')
    required = FLOOR + SCREEN + (CAPTURE_RESERVE if first else 0)
    expected = dict(capture_reserve_bytes=CAPTURE_RESERVE if first else 0,
                    floor_bytes=FLOOR, screening_bytes=SCREEN, required_bytes=required)
    for key, wanted in expected.items():
        literal(record.get(key), wanted, key)
    free = integer(record.get('free_bytes'), 'free_bytes', required)
    literal(record.get('margin_bytes'), free - required, 'margin_bytes')
    literal(record.get('reserve_is_measured'), False, 'reserve_is_measured')
    release = mapping(record.get('allocator_release'), 'allocator_release')
    for key, wanted in dict(schema='ltx.stream130.allocator-release.v1', mode='before-admission',
                            phase='before-cone', required_bytes=required,
                            scope='process-wide XPU allocator', reclaim_is_not_guaranteed=True,
                            admission_free_after_bytes=free).items():
        literal(release.get(key), wanted, 'allocator_release.' + key)
    before = integer(release.get('admission_free_before_bytes'), 'admission_free_before_bytes')
    called = release.get('release_called')
    require(type(called) is bool, 'release_called must be boolean')
    if not called:
        require(before == free and before >= required, 'no-release reading differs or is insufficient')
        require(not any(key in release for key in ('before', 'after', 'physical_free_delta_bytes',
                                                   'reserved_released_bytes_by_card', 'seconds')),
                'skipped release carries fabricated release counters')
        return True
    require(before < required, 'release ran despite sufficient memory')
    cards = {'xpu:%d' % i for i in range(4)}

    def counters(value, label):
        rows = mapping(value, label)
        require(set(rows) == cards, label + ' must cover exactly four cards')
        for card, row in rows.items():
            row = mapping(row, label + '.' + card)
            for key in ('free_bytes', 'total_bytes', 'allocated_bytes', 'reserved_bytes',
                        'peak_allocated_bytes', 'reserved_unused_upper_bound_bytes'):
                integer(row.get(key), label + '.' + card + '.' + key)
            require(row['free_bytes'] <= row['total_bytes'], label + ' physical free exceeds total')
            require(row['reserved_bytes'] >= row['allocated_bytes'], label + ' reserved below allocated')
            require(row['peak_allocated_bytes'] >= row['allocated_bytes'], label + ' peak below allocated')
            require(row['reserved_unused_upper_bound_bytes'] == row['reserved_bytes'] - row['allocated_bytes'],
                    label + ' unused reservation differs from counters')
        return rows

    pre, post = counters(release.get('before'), 'before'), counters(release.get('after'), 'after')
    literal(release.get('physical_free_delta_bytes'), free - before, 'physical_free_delta_bytes')
    released = mapping(release.get('reserved_released_bytes_by_card'), 'reserved_released_bytes_by_card')
    require(set(released) == cards, 'reservation deltas must cover exactly four cards')
    for card in cards:
        require(pre[card]['total_bytes'] == post[card]['total_bytes'], 'card total changed')
        require(post[card]['peak_allocated_bytes'] >= pre[card]['peak_allocated_bytes'], 'peak decreased')
        literal(released[card], pre[card]['reserved_bytes'] - post[card]['reserved_bytes'],
                'reservation delta ' + card)
    seconds = release.get('seconds')
    require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0,
            'release seconds must be finite and nonnegative')
    return True
