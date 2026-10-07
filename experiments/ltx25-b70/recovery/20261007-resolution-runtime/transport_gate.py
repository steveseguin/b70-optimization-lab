"""CPU-only sparse107 evidence checks; model-quality gates remain independent."""
import hashlib
import json
import math
import re

MAX_RECEIPT_BYTES = 1024 * 1024
ELIGIBLE = set(range(99907104, 99907110))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def check(snapshot, observations, rows, identity, phase):
    """Validate actual sampler coverage from pre-existing input/output sentries.

    Observations cover every planned physical index having any original sampler
    sentry or trace receipt. Equality with the census includes uncollected tails;
    request count is deliberately not used as sampler execution count.
    """
    errors = []
    def need(ok, why):
        if not ok:
            errors.append(why)
    def integer(value):
        return type(value) is int and value >= 0
    def worker_map(value):
        need(all((type(k) is int and k in (0,1)) or (type(k) is str and k in ('0','1')) for k in value), 'noncanonical-worker-key')
        converted = {int(k): v for k, v in value.items()}
        need(len(converted) == len(value), 'duplicate-worker-key')
        return converted
    try:
        need(phase in ('candidate-check', 'timed-fast'), 'phase')
        need(snapshot['schema'] == 'ltx.sparse-transport-census.v1', 'schema')
        need(snapshot['identity'] == identity, 'identity')
        need(snapshot['candidate_closed'] is True, 'candidate-not-closed')
        need(type(snapshot['active_jobs']) is int and snapshot['active_jobs'] == 0, 'active-jobs')
        need(type(snapshot['binding_failures']) is int and snapshot['binding_failures'] == 0 and snapshot['audit_error'] is None, 'census-error')
        jobs = snapshot['jobs']
        need(isinstance(jobs, list) and len(jobs) <= 64, 'job-cap')
        keys = [(j['phase'], j['clip_index']) for j in jobs]
        need(len(keys) == len(set(keys)), 'duplicate-job')
        need(all(j['finished'] is True and j['existing_drains_succeeded'] is True for j in jobs), 'unfinished-job')
        workers = worker_map(snapshot['workers'])
        need(set(workers) == {0, 1} and workers[0]['ident'] != workers[1]['ident'], 'worker-bindings')
        for job in jobs:
            need(type(job['worker_index']) is int and type(job['clip_index']) is int and type(job['selected']) is bool, 'job-types')
            binding = workers[job['worker_index']]
            need((job['thread_ident'], job['thread_name']) == (binding['ident'], binding['name']), 'job-worker')
            need(integer(job['events_recorded']), 'event-count')
            if job['phase'] != 'candidate-check':
                need(job['selected'] is False and job['events_recorded'] == 0, 'events-outside-candidate')
        planned = {r['clip_index']: r for r in rows if r['phase'] == phase}
        need(len(planned) == 14, 'phase-plan')
        if phase == 'timed-fast':
            need(all(r.get('trace_enabled') is False for r in planned.values()), 'timed-policy')
        actual = {j['clip_index']: j for j in jobs if j['phase'] == phase}
        observed = {o['clip_index']: o for o in observations}
        need(len(observed) == len(observations) and set(actual) == set(observed), 'sampler-census-coverage')
        need(bool(actual) and set(actual) <= set(planned), 'unplanned-or-missing-sampler-jobs')
        producers = list(planned.values())
        scored = {producers[r['expected_emitted_index']]['clip_index'] for r in planned.values()
                  if r['expected_emitted_index'] is not None}
        need(len(scored) == 10 and scored <= set(actual), 'scored-producer-coverage')
        for index, job in actual.items():
            observation = observed[index]
            need(isinstance(observation['sample_inputs'], dict) and
                 set(observation['sample_inputs']) == {'guider_a_conds','guider_b_conds','noise_seeds','video_latent','audio_latent'},
                 'missing-original-input-sentry')
            sentry = observation['sample_output']
            need(sentry['video_finite'] is True and sentry['audio_finite'] is True, 'missing-original-output-sentry')
            need(all(isinstance(sentry.get(k),str) and re.fullmatch('[0-9a-f]{64}',sentry[k])
                     for k in ('video_sha256','audio_sha256')), 'output-sentry-digest')
            trace = observation['trace_receipt']
            need(trace['schema'] == 'ltx.sparse-transport-job.v1' and trace['clip_index'] == index and
                 trace['phase'] == phase and trace['worker_index'] == job['worker_index'], 'trace-job-identity')
            need(trace['existing_drains_succeeded'] is True and trace['events_recorded'] == job['events_recorded'] and
                 trace['selected'] is job['selected'], 'trace-census-mismatch')
            if not trace['selected']:
                need(trace['events_recorded'] == trace['operation_count'] == 0, 'disabled-events')
        # No elapsed sum across devices: clocks and overlapping intervals differ.
        if phase == 'candidate-check':
            receipts = worker_map(snapshot['receipts'])
            claims = worker_map(snapshot['claims'])
            need(set(receipts) == set(claims) == {0, 1}, 'both-workers-required')
            selected = [j for j in jobs if j['selected']]
            need(len(selected) == 2, 'selected-job-count')
            for worker, receipt in receipts.items():
                index = receipt['clip_index']
                need(index in ELIGIBLE and index == claims[worker] and receipt['worker_index'] == worker, 'claim-binding')
                need(receipt == observed[index]['trace_receipt'], 'worker-receipt-binding')
                need((receipt['thread_ident'],receipt['thread_name']) == (workers[worker]['ident'],workers[worker]['name']), 'selected-worker-binding')
                need(receipt['identity'] == identity and receipt['valid'] is True and receipt['error'] is None, 'selected-invalid')
                need(receipt['coverage'] == {s: {'blocks':48,'replays':48,'moves':4,'partitions':2} for s in ('a','b')}, 'forward-coverage')
                ops = receipt['operations']
                need(len(ops) == receipt['operation_count'] <= 128, 'operation-cap')
                need(all(integer(v) and v <= 128 for v in receipt['events_reserved'].values()) and
                     set(receipt['events_reserved']) == {'xpu:0','xpu:1'}, 'event-reservation-cap')
                events = 0
                by_device = {'xpu:0': 0, 'xpu:1': 0}
                for op in ops:
                    n = 4 if op['kind'] == 'move' else 2
                    need(op['kind'] in ('move','fill','partition') and op['stage'] in ('a','b') and
                         op['forward_ordinal'] == 2, 'operation-scope')
                    need(op['recorded_indices'] == list(range(n)) and len(op['event_devices']) == n, 'unpaired-events')
                    if op['kind'] == 'move':
                        need((op['src'],op['dst']) in (('xpu:0','xpu:1'),('xpu:1','xpu:0')) and
                             op['event_devices'] == [op['src'],op['src'],op['dst'],op['dst']], 'move-event-route')
                    else:
                        need(op['device'] in ('xpu:0','xpu:1') and op['event_devices'] == [op['device']]*2, 'event-route')
                    for device in op['event_devices']:
                        if device in by_device:
                            by_device[device] += 1
                    durations = op['elapsed_ms']
                    need(len(durations) == n // 2 and all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in durations), 'elapsed-duration')
                    events += n
                need(by_device == receipt['events_reserved'], 'per-device-event-total')
                need(events == receipt['events_recorded'] == sum(receipt['events_reserved'].values()) <= 256, 'event-total')
                for stage in ('a','b'):
                    need(sum(o['kind']=='move' and o['stage']==stage for o in ops)==4 and
                         sum(o['kind']=='partition' and o['stage']==stage for o in ops)==2, 'operation-coverage')
            need(snapshot['complete'] is True, 'candidate-incomplete')
        else:
            need(type(snapshot['phase_events']['timed-fast']) is int and snapshot['phase_events']['timed-fast'] == 0, 'timed-events')
            need(all(j['selected'] is False and j['events_recorded'] == 0 for j in actual.values()), 'timed-job-instrumented')
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as error:
        errors.append('malformed-evidence:' + type(error).__name__)
    return {'schema': 'ltx.sparse-transport107-gate.v1', 'phase': phase,
            'identity': identity, 'valid': not errors, 'errors': sorted(set(errors)),
            'snapshot': snapshot, 'sampler_observations': observations,
            'claim': ('Sparse candidate timing metadata only; intervals overlap and include submission gaps. '
                      'Timed checks prove zero timing events; dormant hooks and bounded CPU bookkeeping remain. '
                      'Model quality is checked separately by the unchanged exact-output gates.')}
