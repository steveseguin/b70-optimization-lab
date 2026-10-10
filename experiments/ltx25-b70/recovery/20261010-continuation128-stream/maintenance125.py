"""Packet 125: bounded periodic process maintenance, with CPU timing evidence.

The 10-second form preserves the parent's calls and cadence.  The 60-second
candidate retains both full Python collection and allocator cleanup, and leaves
automatic Python collection and explicit free/unload handling unchanged.
"""
import copy
import os
import threading
import time

ENV = 'LTX_GC_INTERVAL_SECONDS'
CHOICES = (10, 60)
_lock = threading.Lock()
_events = []
_count = 0


def launch_interval(environ=None):
    value = (os.environ if environ is None else environ).get(ENV, '10')
    if type(value) is not str or value not in ('10', '60'):
        raise ValueError(ENV + ' must be 10 (parent) or 60 (candidate)')
    return int(value)


def snapshot():
    """A bounded copy; callers cannot mutate the maintenance evidence."""
    with _lock:
        return {'schema': 'ltx.stream125.maintenance.v1', 'count': _count,
                'retained': len(_events), 'events': copy.deepcopy(_events)}


def run_maintenance(collect, empty_cache, interval, prompt_id=None):
    """Run the native pair in order, preserving failures and return semantics.

Only timing is added.  A failed collection never proceeds to allocator cleanup.
No callback runs under the evidence lock.  The prompt id identifies the most
recent prompt, including a deferred idle-time collection after that prompt.
    """
    if type(interval) is not int or interval not in CHOICES:
        raise ValueError('Invalid maintenance interval')
    if not callable(collect) or not callable(empty_cache):
        raise TypeError('Native maintenance callbacks required')
    event = {'interval_s': interval, 'prompt_id': prompt_id,
             'timing_ns': {'gc_start': time.time_ns(), 'gc_done': None, 'cache_done': None},
             'failed_stage': None}
    stage = 'gc'
    try:
        collect()
        event['timing_ns']['gc_done'] = time.time_ns()
        stage = 'cache'
        empty_cache()
        event['timing_ns']['cache_done'] = time.time_ns()
    except BaseException:
        event['failed_stage'] = stage
        raise
    finally:
        event['end_ns'] = time.time_ns()
        global _count
        with _lock:
            _count += 1
            event['sequence'] = _count
            _events.append(event)
            del _events[:-32]


def transform_main(raw):
    """Transform exactly the sealed parent's periodic block, never a guess."""
    if type(raw) is not bytes:
        raise TypeError('main source must be bytes')
    old_interval = b'    gc_collect_interval = 10.0\n'
    old_calls = (b'                    gc.collect()\n'
                 b'                    comfy.model_management.soft_empty_cache()\n')
    if raw.count(old_interval) != 1 or raw.count(old_calls) != 1:
        raise ValueError('Parent maintenance anchors differ')
    value = raw.replace(old_interval,
                        b'    import maintenance125\n'
                        b'    gc_collect_interval = maintenance125.launch_interval()\n')
    value = value.replace(old_calls,
                          b'                    maintenance125.run_maintenance(\n'
                          b'                        gc.collect, comfy.model_management.soft_empty_cache,\n'
                          b'                        gc_collect_interval, getattr(server_instance, "last_prompt_id", None))\n')
    compile(value, 'packet125-main.py', 'exec')
    return value
