"""Bound periodic maintenance to idle gaps without moving either native callback.

No background collector, automatic-GC change or lost maintenance debt. The
hard age is checked at prompt boundaries, so an in-flight prompt may exceed it.
"""
import os
import time

ENV = 'LTX_MAINTENANCE_MODE'
IDLE_GRACE_S = 0.25
MAX_AGE_S = 60.0
_events = []
_count = 0


def snapshot():
    return {"schema": "ltx.stream130.maintenance-schedule.v1", "count": _count,
            "events": [dict(row) for row in list(_events)]}



def launch_mode(environ=None):
    value = (os.environ if environ is None else environ).get(ENV, 'parent')
    if type(value) is not str or value not in ('parent', 'idle'):
        raise ValueError(ENV + ' must be parent or idle')
    return value


def wait_timeout(mode, now, last_gc, interval):
    """Same parent wait; due idle candidates sleep rather than spin."""
    if mode not in ('parent', 'idle'):
        raise ValueError('Invalid maintenance mode')
    due_in = max(interval - (now - last_gc), 0.0)
    if mode == 'parent' or due_in > 0:
        return due_in
    return min(IDLE_GRACE_S, max(MAX_AGE_S - (now - last_gc), 0.0))


def should_run(mode, now, last_gc, last_completed, interval, forced=False):
    """Only select the time. Calls, order, thread and exception flow stay native."""
    if mode not in ('parent', 'idle'):
        raise ValueError('Invalid maintenance mode')
    if now - last_gc <= interval:
        return False
    run = (mode == 'parent' or forced or now - last_gc >= MAX_AGE_S
           or now - last_completed >= IDLE_GRACE_S)
    if mode == 'idle':
        reason = ('explicit' if forced else 'max-age' if now-last_gc >= MAX_AGE_S
                  else 'quiet' if run else 'handoff-deferred')
        global _count
        _count += 1
        _events.append({'time_ns': time.time_ns(), 'sequence': _count, 'run': run,
                        'reason': reason, 'age_s': now-last_gc,
                        'quiet_s': now-last_completed, 'interval_s': interval})
        del _events[:-32]
    return run


def transform_main(raw):
    """Exactly four substitutions in sealed127 main; fail closed on drift."""
    if type(raw) is not bytes:
        raise TypeError('main source must be bytes')
    substitutions = (
        (b'    gc_collect_interval = maintenance125.launch_interval()\n',
         b'    gc_collect_interval = maintenance125.launch_interval()\n'
         b'    import maintenance128\n'
         b'    maintenance_mode = maintenance128.launch_mode()\n'
         b'    maintenance_last_completed = 0.0\n'),
        (b'                timeout = max(gc_collect_interval - (current_time - last_gc_collect), 0.0)\n',
         b'                timeout = maintenance128.wait_timeout(maintenance_mode, current_time, last_gc_collect, gc_collect_interval)\n'),
        (b'                execution_time = current_time - execution_start_time\n',
         b'                execution_time = current_time - execution_start_time\n'
         b'                maintenance_last_completed = current_time\n'),
        (b'                if (current_time - last_gc_collect) > gc_collect_interval:\n',
         b'                if maintenance128.should_run(maintenance_mode, current_time, last_gc_collect,\n'
         b'                        maintenance_last_completed, gc_collect_interval,\n'
         b'                        forced=bool(free_memory or flags.get("unload_models", free_memory))):\n'),
    )
    for before, after in substitutions:
        if raw.count(before) != 1:
            raise ValueError('Parent maintenance anchor differs: ' + repr(before))
        raw = raw.replace(before, after)
    compile(raw, 'packet128-main.py', 'exec')
    return raw
