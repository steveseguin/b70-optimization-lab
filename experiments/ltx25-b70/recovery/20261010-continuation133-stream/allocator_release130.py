"""Optional bounded allocator release. Inert until called by the display owner.

empty_cache has no device argument: the operation is process-wide, not a
card-local API. Never move tensors, destroy graphs, collect Python objects,
reset peaks or change the decode/reserve. Reserved-minus-allocated is only an
upper bound on reclaimable memory, not admission credit.
"""
import os
import math
import time

ENV = 'LTX_DISPLAY_ALLOCATOR_RELEASE'
CHOICES = ('off', 'before-admission')
GIB = 2 ** 30


def launch_mode(environ=None):
    mode = (os.environ if environ is None else environ).get(ENV, 'off')
    if type(mode) is not str or mode not in CHOICES:
        raise ValueError(ENV + ' must be off or before-admission')
    return mode


def validate_scope(environ=None):
    env = os.environ if environ is None else environ
    mode = launch_mode(env)
    if mode == 'off':
        return mode
    required = {
        'LTX_STREAM_FRAMES': '169', 'LTX_SAMPLER_PLACEMENT': 'two-way20-28',
        'LTX_ANCHOR': 'frame', 'LTX_DECODER_GRAPH': '0',
        'LTX_ANCHOR_DECODE': 'cone', 'LTX_BENCODE_OVERLAP': '1',
        'LTX_PREP_AHEAD': '1', 'LTX_DISPLAY_DEVICE': 'xpu:2',
        'LTX_DISPLAY_SCHEDULE': 'eager-display', 'LTX_DISPLAY_WORKER': 'parallel',
        'LTX_AUX_RESIDENCY': 'legacy', 'LTX_SNAPSHOT_MODE': 'fingerprint',
        'LTX_SNAPSHOT_SCHEDULE': 'full', 'LTX_ANCHOR_READ_AHEAD': '0',
    }
    if any(env.get(key) != value for key, value in required.items()):
        raise ValueError('Allocator release requires explicit169 parallel display2 legacy scope')
    return mode


def snapshot(torch):
    xpu = torch.xpu
    result = {}
    for i in range(4):
        card = 'xpu:%d' % i
        free, total = xpu.mem_get_info(card)
        allocated, reserved = xpu.memory_allocated(card), xpu.memory_reserved(card)
        peak = xpu.max_memory_allocated(card)
        values = (free, total, allocated, reserved, peak)
        if any(type(v) is not int or v < 0 for v in values) or reserved < allocated or free > total:
            raise RuntimeError('Invalid allocator release census: ' + card)
        result[card] = dict(free_bytes=free, total_bytes=total, allocated_bytes=allocated,
                            reserved_bytes=reserved, peak_allocated_bytes=peak,
                            reserved_unused_upper_bound_bytes=reserved-allocated)
    return result


def before_admission(torch, free_bytes, *, mode, required_bytes, phase):
    """One optional release followed by a fresh physical reading, never a retry.

    Caller runs the unchanged budget on the returned free bytes. The release
    cannot itself admit a model, and receives no model or decoder reference.
    The physical reading, not the reservation delta, determines admission.
    """
    if mode not in CHOICES or type(required_bytes) is not int or required_bytes < 0:
        raise ValueError('Invalid allocator release admission')
    free = free_bytes()
    if type(free) is not int or free < 0:
        raise RuntimeError('Invalid display memory census')
    if mode == 'off':
        return free, None
    record = dict(schema='ltx.stream130.allocator-release.v1', mode=mode, phase=phase,
                  required_bytes=required_bytes, admission_free_before_bytes=free,
                  release_called=False, scope='process-wide XPU allocator',
                  reclaim_is_not_guaranteed=True,
                  counter_observations='sequential non-atomic samples; deltas are net concurrent observations, not isolated release credit')
    if free >= required_bytes:
        record['admission_free_after_bytes'] = free
        return free, record
    started = time.monotonic_ns()
    # No graph-pool release, Python GC, peak reset or tensor eviction. The XPU
    # allocator owns the synchronization needed to return its unused blocks.
    record['before'] = snapshot(torch)
    torch.xpu.empty_cache()
    record['release_called'] = True
    record['after'] = snapshot(torch)
    free = free_bytes()
    if type(free) is not int or free < 0:
        raise RuntimeError('Invalid display memory census after allocator release')
    record['admission_free_after_bytes'] = free
    record['physical_free_delta_bytes'] = free - record['admission_free_before_bytes']
    record['reserved_released_bytes_by_card'] = {
        card: row['reserved_bytes'] - record['after'][card]['reserved_bytes']
        for card, row in record['before'].items()}
    record['seconds'] = (time.monotonic_ns() - started) / 1e9
    return free, record


def validate_residency(residency):
    """Validate completed on-mode evidence without importing a device runtime.

    The caller selects this only for declared before-admission mode. Each
    physical admission reading must independently clear the original floor,
    transient and screening terms. Counter deltas are signed observations;
    they never substitute for physical free memory or prove isolated reclaim.
    """
    def require(ok, message):
        if not ok:
            raise ValueError('Allocator evidence: ' + message)

    def integer(value, label, minimum=0):
        require(type(value) is int and value >= minimum, label + ' must be an integer >= ' + str(minimum))
        return value

    def mapping(value, label):
        require(type(value) is dict, label + ' must be an object')
        return value

    residency = mapping(residency, 'residency')
    resident = integer(residency.get('resident_bytes'), 'resident_bytes', 1)
    transient = integer(residency.get('transient_budget_bytes'), 'transient_budget_bytes', 13 * GIB // 2)
    require(residency.get('device') == 'xpu:2', 'wrong replica device')
    require(type(residency.get('floor_bytes')) is int and residency['floor_bytes'] == 2 * GIB,
            'replica floor changed')
    floor, screen = 2 * GIB, 3 * GIB // 4
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
            require(row['reserved_bytes'] >= row['allocated_bytes'], label + ' reservation below allocation')
            require(row['peak_allocated_bytes'] >= row['allocated_bytes'], label + ' peak below allocation')
            require(row['reserved_unused_upper_bound_bytes'] == row['reserved_bytes'] - row['allocated_bytes'],
                    label + ' unused reservation does not match counters')
        return rows

    def admission(value, phase, new_resident):
        value = mapping(value, phase)
        free = integer(value.get('free_bytes'), phase + '.free_bytes')
        expected = new_resident + transient + floor + screen
        for key, wanted in (('new_resident_bytes', new_resident), ('transient_budget_bytes', transient),
                            ('floor_bytes', floor), ('margin_bytes', free - new_resident - transient - floor)):
            require(type(value.get(key)) is int and value[key] == wanted, phase + '.' + key + ' differs')
        require(free >= expected and value['margin_bytes'] >= screen, phase + ' fails unchanged screening')
        record = mapping(value.get('allocator_release'), phase + '.allocator_release')
        require(record.get('schema') == 'ltx.stream130.allocator-release.v1', phase + ' wrong audit schema')
        require(record.get('mode') == 'before-admission' and record.get('phase') == phase,
                phase + ' wrong audit mode or phase')
        require(record.get('scope') == 'process-wide XPU allocator'
                and record.get('reclaim_is_not_guaranteed') is True, phase + ' wrong allocator scope or reclaim claim')
        require(type(record.get('required_bytes')) is int and record['required_bytes'] == expected,
                phase + ' required bytes omit or change a budget term')
        before = integer(record.get('admission_free_before_bytes'), phase + '.admission_free_before_bytes')
        after = integer(record.get('admission_free_after_bytes'), phase + '.admission_free_after_bytes')
        require(after == free, phase + ' final physical reading differs from admission')
        called = record.get('release_called')
        require(type(called) is bool, phase + ' release_called must be boolean')
        if not called:
            require(before >= expected and after == before, phase + ' skipped release without sufficient unchanged free')
            require(not any(k in record for k in ('before', 'after', 'physical_free_delta_bytes',
                                                  'reserved_released_bytes_by_card', 'seconds')),
                    phase + ' skipped release carries fabricated release counters')
            return
        require(before < expected, phase + ' released despite sufficient admission memory')
        pre, post = counters(record.get('before'), phase + '.before'), counters(record.get('after'), phase + '.after')
        delta = record.get('physical_free_delta_bytes')
        require(type(delta) is int and delta == after - before, phase + ' physical net delta differs')
        released = mapping(record.get('reserved_released_bytes_by_card'), phase + '.reserved_released_bytes_by_card')
        require(set(released) == cards, phase + ' reservation deltas must cover four cards')
        for card in cards:
            require(pre[card]['total_bytes'] == post[card]['total_bytes'], phase + ' card total changed')
            require(post[card]['peak_allocated_bytes'] >= pre[card]['peak_allocated_bytes'], phase + ' peak counter decreased')
            require(type(released[card]) is int and released[card] == pre[card]['reserved_bytes'] - post[card]['reserved_bytes'],
                    phase + ' reservation net delta differs on ' + card)
        seconds = record.get('seconds')
        require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0,
                phase + ' duration must be finite and nonnegative')

    admission(residency.get('before_install'), 'before-install', resident)
    admission(residency.get('after_install'), 'after-install', 0)
    last = mapping(residency.get('last_decode'), 'last_decode')
    admission(last.get('before'), 'before-decode', 0)
    require(integer(last.get('after_free_bytes'), 'last_decode.after_free_bytes') >= floor + screen,
            'post-decode physical free fails unchanged screening')
    return True
