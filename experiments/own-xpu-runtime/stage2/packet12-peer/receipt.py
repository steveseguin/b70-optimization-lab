"""Reject incomplete evidence; end-to-end latency is always a wall measurement."""
import math
import statistics

SIZES = (10240, 65536, 1048576, 16777216)

def summarize(native):
    if native.get('schema') != 'own-runtime.peer.native.v1' or native.get('passed') is not True or native.get('error'):
        raise ValueError('native run failed or incomplete')
    if not native.get('identity'):
        raise ValueError('missing device identity')
    teardown = native['teardown']
    if (teardown.get('safe_to_exit') is not True or teardown.get('idle_marker_complete') is not True
            or teardown.get('status') != 'complete' or teardown.get('in_flight') != 0 or teardown.get('live_bytes') != 0):
        raise ValueError('unsafe teardown')
    modes = ['peer', 'host-bounce'] if native['access_ab'] and native['access_ba'] else ['host-bounce']
    expected = {(mode, 'copy', n, direction) for mode in modes for n in SIZES for direction in ('A->B', 'B->A')}
    expected |= {(mode, 'exchange', 10240, 60) for mode in modes}
    seen, rows = set(), []
    for row in native['cases']:
        kind, mode, n = row['kind'], row['mode'], row['bytes']
        key = (mode, kind, n, row.get('direction') if kind == 'copy' else row.get('rounds'))
        if key not in expected or key in seen or row.get('exact') is not True:
            raise ValueError('case coverage/exactness')
        seen.add(key)
        if len(row['samples']) != (20 if kind == 'copy' else 5):
            raise ValueError('sample coverage')
        wall, event = [], []
        for sample in row['samples']:
            w = sample['wall_ns']
            if not isinstance(w, (int, float)) or not math.isfinite(w) or w <= 0:
                raise ValueError('invalid wall interval')
            wall.append(w)
            count = (2 if mode == 'host-bounce' else 1) if kind == 'copy' else 60*(5 if mode == 'host-bounce' else 3)
            times = sample['events']
            if len(times) != count:
                raise ValueError('event coverage')
            if any(len(t) != 2 or any(type(v) is not int or v < 0 for v in t) for t in times):
                raise ValueError('invalid timestamps')
            event.append(sum(end-start for start, end in times) if all(end > start for start, end in times) else None)
        median = statistics.median(wall)
        result = dict(mode=mode, kind=kind, bytes=n, wall_samples_ns=wall,
                      wall_median_us=median/1000, wall_min_us=min(wall)/1000, wall_max_us=max(wall)/1000,
                      event_sum_samples_ns=event, samples_without_event_timing=event.count(None))
        if kind == 'copy':
            result.update(direction=row['direction'], payload_wall_GBps=n/median,
                          payload_event_GBps=statistics.median([n/t for t in event if t is not None]) if any(t is not None for t in event) else None,
                          link_bytes=n*(2 if mode == 'host-bounce' else 1))
        else:
            result.update(rounds=60, measured_60_round_wall_ms=median/1e6,
                          mean_per_round_us=median/60000,
                          caveat='60 serialized changed-state diagnostic exchanges; not a model token or wire latency')
        rows.append(result)
    if seen != expected:
        raise ValueError('missing cases')
    return dict(schema='own-runtime.peer.summary.v1', transport_only=True,
                selected='peer' if 'peer' in modes else 'host-bounce', rows=rows,
                cross_device_timestamps_subtracted=False, model_quality_passed=False)
