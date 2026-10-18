#!/usr/bin/env python3
"""Sealed empirical admission for FUTURE one-card copies; no launch authority.

Import has no side effects. All views require explicit selection. The resident
view is a design allowance, not a resident measurement. Copy the entire sealed
module bundle and bind its seal hash in the new packet's immutable build seal.
"""
import argparse
import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
GIB = 1024**3
HOST_RESERVE = 8 * GIB
CACHE_BYTES = 18_000_000_000
VIEWS = ('production', 'tile16', 'tile16-resident')
WINDOWS = ('K1', 'K1a', 'K1b', 'KD', 'W2m', 'WS', 'WS128x', 'WS128', 'WSCREEN')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name):
    require(type(value) is int and value >= 0, name + ' must be a nonnegative integer')
    return value


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_seal(root=HERE):
    root = Path(root)
    seal = json.loads((root / 'seal.json').read_text())
    require(seal['schema'] == 'own-runtime.packet58u.seal.v1', 'unknown admission seal')
    require({'memory_plan.py', 'base-plan.json', 'measured-peaks.json', 'derive.py',
             'test_memory_plan.py', 'seal.py', 'README.md', 'CPU-CLOSEOUT.md',
             'DO-NOT-REPEAT.md'} <= set(seal['files']), 'incomplete admission seal')
    for name, digest in seal['files'].items():
        require(Path(name).name == name, 'seal path must be local')
        require(sha(root / name) == digest, 'admission seal mismatch: ' + name)
    return seal


@lru_cache(maxsize=1)
def _inputs():
    verify_seal()
    return (json.loads((HERE / 'base-plan.json').read_text()),
            json.loads((HERE / 'measured-peaks.json').read_text()))


def _plan(view, window):
    require(view in VIEWS, 'unknown one-card memory view')
    require(window in WINDOWS, 'unknown memory window')
    base, evidence = _inputs()
    budget = copy.deepcopy(base)
    profile = copy.deepcopy(evidence['profiles'][view])
    pinned = budget['census']['pinned_expert_bytes']
    # Preserve the measured combined overhead (anon + shadow) as a conservative
    # process allowance, THEN add an independent 4 GiB shadow allowance.
    overhead = profile['empirical_core_peak_bytes'] - pinned
    require(overhead >= 0, 'invalid measured core peak')
    host = dict(pinned_packed_experts=pinned,
                file_backed_nonexpert_and_lookup_bound=profile['file_allowance_bytes'],
                resident_lookup_bytes=profile['resident_lookup_bytes'],
                measured_process_overhead_allowance=overhead,
                gpuactive_shadow_bound=4 * GIB)
    bound = sum(host.values())
    require(bound == profile['host_bound_bytes'], 'profile accounting differs')
    budget.update(schema='own-runtime.packet58u.memory.v1', memory_view=view, window=window,
                  admission_mode='measured-peak-whole-host', whole_host_required=True,
                  host_categories=host, host_reserve_bytes=HOST_RESERVE,
                  host_bound_bytes=bound, host_required_available_bytes=bound+HOST_RESERVE,
                  derivation=profile, source_seal_sha256=sha(HERE/'seal.json'),
                  caveat='Empirical bound for the pinned one-card target-only 18 GB cache, '
                         '4K BF16 allocation and <=128 generated-token receipts. '
                         'Resident lookup bytes are a design substitution, not measured. '
                         'Keep whole-host ownership, all native census/quality gates and live stops.')
    if window.startswith('K1'):
        budget.update(admission_mode='bounded-K1', host_bound_bytes=4*GIB,
                      host_required_available_bytes=12*GIB)
    return budget


def plan(view):
    return window_plan('WSCREEN', view=view)


def window_plan(window, observation=None, *, view):
    # A caller cannot use a new observation to shrink the frozen empirical fit.
    require(observation is None, 'new observations require a new sealed policy')
    verify_seal()
    return _plan(view, window)


def _validate(budget):
    expected = _plan(budget.get('memory_view'), budget.get('window'))
    require(budget == expected, 'memory plan differs from sealed policy')
    require(budget['device_owned_bound_bytes'] <= budget['arena_limit_bytes']
            and budget['device_margin_bytes'] >= 0, 'device bound does not fit')


def admit(snapshot, budget):
    verify_seal()
    _validate(budget)
    available = integer(snapshot['MemAvailable'], 'MemAvailable')
    required = budget['host_required_available_bytes']
    require(available >= required,
            f'host admission refused: available {available}, required {required}, '
            f'shortage {required-available}; no pin or model load')
    return dict(passed=True, available_bytes=available, required_bytes=required,
                margin_bytes=available-required,
                baseline_gpuactive_bytes=integer(snapshot.get('GPUActive', 0), 'GPUActive'),
                snapshot=copy.deepcopy(snapshot), plan=copy.deepcopy(budget),
                scope='host-memory-only; coordinator admission is still required')


def meminfo(path=Path('/proc/meminfo')):
    fields = {}
    for line in Path(path).read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemAvailable', 'MemTotal', 'SwapFree', 'SwapTotal', 'GPUActive'):
            fields[key] = integer(int(value.split()[0]), key) * 1024
    require('MemAvailable' in fields, 'MemAvailable sensor missing')
    return fields


def account_memory(sample, snapshot, baseline_gpuactive, pinned_bytes, budget, full_model=True):
    """Existing disjoint accounting, with the sealed margin and unchanged floor.

    RssAnon includes the actual resident copies. Do not subtract them and do not
    add their planned size again. Pinned credit must come from completed native
    progress checked against the tensor census, as in packet58r/t.
    """
    _validate(budget)
    require(full_model == (not budget['window'].startswith('K1')), 'window/model memory mode differs')
    sample['host'] = snapshot
    require(integer(snapshot['MemAvailable'], 'MemAvailable') >= HOST_RESERVE,
            'host available memory below 8 GiB stop floor')
    require('GPUActive' in snapshot, 'GPUActive sensor missing')
    active = integer(snapshot['GPUActive'], 'GPUActive')
    baseline = integer(baseline_gpuactive, 'baseline GPUActive')
    pinned = integer(pinned_bytes, 'pinned expert bytes')
    anonymous = integer(sample['anonymous_bytes'], 'anonymous bytes')
    require(pinned <= (budget['census']['pinned_expert_bytes'] if full_model else 0),
            'pinned expert total exceeds admitted bound')
    growth = max(0, active-baseline)
    shadow = max(0, growth-pinned)
    sample.update(gpuactive_growth_bytes=growth, pinned_expert_bytes=pinned,
                  gpuactive_pinned_credit_bytes=min(growth, pinned),
                  gpuactive_shadow_bytes=shadow, gpuactive_shadow_bound_bytes=4*GIB)
    require(shadow <= 4*GIB, 'GPUActive shadow exceeds admitted bound')
    if full_model:
        combined = pinned + shadow + anonymous + budget['host_categories']['file_backed_nonexpert_and_lookup_bound']
        sample.update(host_accounted_bytes=combined, host_accounted_bound_bytes=budget['host_bound_bytes'])
        require(combined <= budget['host_bound_bytes'], 'combined host memory exceeds admitted bound')
    return sample


def live_memory_sensor(pid, baseline_gpuactive=0, *, budget, process_sampler,
                       pinned_progress=None, sample_log=None, admission=None,
                       snapshot_reader=meminfo):
    """Use as the existing supervisor's memory_sensor; exceptions request drain.

    process_sampler must be the future packet's existing checked process-tree
    sampler (including its exited-root handling). No sampler or supervisor is
    silently substituted here. Offending samples are flushed before re-raising.
    """
    full_model = not budget['window'].startswith('K1')
    pinned = pinned_progress.read() if full_model and pinned_progress is not None else 0
    sample = process_sampler(pid)
    sample['sample_utc_ns'] = time.time_ns()
    try:
        if admission is not None:
            admission.observe(sample)
        return account_memory(sample, snapshot_reader(), baseline_gpuactive, pinned, budget, full_model)
    except Exception as error:
        sample['sensor_error'] = str(error)
        raise
    finally:
        if sample_log is not None:
            sample_log.write(json.dumps(sample, allow_nan=False) + '\n')
            sample_log.flush()


def observed_shadow(samples, baseline, pinned_limit):
    """Retain the post-load checker interface; these observations never lower a bound."""
    require(bool(samples), 'missing measured shadow samples')
    integer(baseline, 'baseline GPUActive')
    peak = 0
    for row in samples:
        pinned = integer(row['pinned_expert_bytes'], 'pinned expert bytes')
        require(pinned <= pinned_limit, 'pinned expert total exceeds admitted bound')
        shadow = max(0, integer(row['host']['GPUActive'], 'GPUActive')-baseline-pinned)
        require(shadow == row['gpuactive_shadow_bytes'], 'measured shadow arithmetic differs')
        peak = max(peak, shadow)
    return peak


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--view', choices=VIEWS, required=True)
    parser.add_argument('--window', choices=WINDOWS, default='WSCREEN')
    parser.add_argument('--admit-current-host', action='store_true')
    args = parser.parse_args()
    budget = window_plan(args.window, view=args.view)
    print(json.dumps(admit(meminfo(), budget) if args.admit_current_host else budget, indent=2))


if __name__ == '__main__':
    main()
