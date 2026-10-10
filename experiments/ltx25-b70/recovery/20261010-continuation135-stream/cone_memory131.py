"""Packet132 opt-in cone graph admission; inert and stdlib-only until called.

A 5 GiB capture allowance is conservative planning, not an allocator hard cap.
No output or floor changes. One optional process-wide unused-cache release per
cone admission, never a retry. Qualification full card3 references are retained.
"""
import os

ENV = 'LTX_CONE_GRAPH_MEMORY'
GIB = 2**30
CAPTURE_RESERVE = 5 * GIB
RESERVE_ENV = 'LTX_CONE_CAPTURE_RESERVE'
RESERVE_CHOICES = ('parent', 'scaled-476')
# Integer arithmetic rounds upward; never grant admission on a rounded-down byte.
SCALED_RESERVE = (476 * GIB + 99) // 100
MEASURED_121_GROWTH = 3430940672
SCALED_145_ESTIMATE = MEASURED_121_GROWTH * 19 * 19 // (16 * 16)
RESERVE_BLOCKED = ('scaled-476 is not qualified: repeated 121-frame reserved-growth '
                   'receipts do not establish a 145-frame capture peak or an upper bound; '
                   'retain parent reserve until matched 145-frame evidence exists')
FLOOR = 9 * GIB
SCREEN = 3 * GIB // 4
CHOICES = ('off', 'replica-release', 'text-shift')
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

def reserve_mode(env=None):
    """Parse the requested mode; selection is not permission to admit a capture."""
    env = os.environ if env is None else env
    value = env.get(RESERVE_ENV, 'parent')
    if value not in RESERVE_CHOICES:
        raise ValueError('Invalid cone capture reserve mode')
    return value

def reserve_bytes(mode='parent'):
    """Return a qualified planning allowance or fail closed, without ambient env."""
    if mode not in RESERVE_CHOICES:
        raise ValueError('Invalid cone capture reserve mode')
    if mode == 'scaled-476':
        raise ValueError(RESERVE_BLOCKED)
    return CAPTURE_RESERVE

def reserve_projection(mode='parent'):
    """CPU planning arithmetic only; this record cannot authorize admission."""
    if mode not in RESERVE_CHOICES:
        raise ValueError('Invalid cone capture reserve mode')
    proposed = CAPTURE_RESERVE if mode == 'parent' else SCALED_RESERVE
    return dict(mode=mode, capture_reserve_bytes=proposed,
                reserve_is_measured=False, launch_admitted=mode == 'parent',
                measured_121_reserved_growth_bytes=MEASURED_121_GROWTH,
                scaled_145_estimate_bytes=SCALED_145_ESTIMATE,
                estimate_margin_bytes=proposed-SCALED_145_ESTIMATE,
                reduction_from_parent_bytes=CAPTURE_RESERVE-proposed,
                floor_bytes=FLOOR, screening_bytes=SCREEN,
                first_capture_required_bytes=FLOOR+SCREEN+proposed,
                evidence_limitation='121 reserved-growth repeats are not a 145 peak or upper bound')

def launch_mode(env=None):
    env = os.environ if env is None else env
    value = env.get(ENV, 'off')
    if value not in CHOICES:
        raise ValueError('Invalid cone graph memory mode')
    return value

def validate_scope(env=None):
    env = os.environ if env is None else env
    reserve_bytes(reserve_mode(env))
    mode = launch_mode(env)
    if mode == 'text-shift':
        import text_residency133
        text_residency133.validate_scope(env)
        return mode
    if mode != 'off':
        if any(env.get(k, DEFAULTS.get(k)) != v for k, v in SCOPE.items()):
            raise ValueError('Cone memory requires fixed145 dg1 cone serial replica2 scope')
        if env.get('LTX_DECODER_GRAPH_POOL_CAP_GB') is not None:
            raise ValueError('Cone memory uses exactly one private graph; pool cap must be unset')
    return mode

def admit(torch, free_bytes, *, mode, first_capture, reserve_mode='parent'):
    reserve = reserve_bytes(reserve_mode)
    if mode not in CHOICES or type(first_capture) is not bool:
        raise ValueError('Invalid cone memory admission')
    if mode == 'off':
        return None
    required = FLOOR + SCREEN + (reserve if first_capture else 0)
    import allocator_release130
    free, release = allocator_release130.before_admission(torch, free_bytes,
        mode='off' if mode == 'text-shift' else 'before-admission', required_bytes=required, phase='before-cone')
    record = dict(schema='ltx.stream131.cone-memory.v1', mode=mode,
        first_capture=first_capture, capture_reserve_bytes=reserve if first_capture else 0,
        floor_bytes=FLOOR, screening_bytes=SCREEN, required_bytes=required,
        free_bytes=free, margin_bytes=free-required, allocator_release=release,
        reserve_is_measured=False)
    if free < required:
        error = RuntimeError('Cone graph memory refused: physical free below capture/floor/screen: ' + repr(record))
        error.admission = record
        raise error
    return record

def validate_record(record, *, reserve_mode='parent'):
    """Validate the physical admission and complete release audit, never reservation credit."""
    reserve = reserve_bytes(reserve_mode)
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
    require(record.get('mode') in ('replica-release', 'text-shift'), 'mode differs')
    first = record.get('first_capture')
    require(type(first) is bool, 'capture phase must be boolean')
    required = FLOOR + SCREEN + (reserve if first else 0)
    expected = dict(capture_reserve_bytes=reserve if first else 0,
                    floor_bytes=FLOOR, screening_bytes=SCREEN, required_bytes=required)
    for key, wanted in expected.items():
        literal(record.get(key), wanted, key)
    free = integer(record.get('free_bytes'), 'free_bytes', required)
    literal(record.get('margin_bytes'), free - required, 'margin_bytes')
    literal(record.get('reserve_is_measured'), False, 'reserve_is_measured')
    if record['mode'] == 'text-shift':
        literal(record.get('allocator_release'), None, 'allocator_release')
        return True
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
