"""Read final per-rank cleanup receipts without importing a device runtime.

A receipt certifies observed Python cleanup calls, not native queue destruction.
Only fresh controller-owned run directories are valid input.
"""
import datetime
import json
from pathlib import Path

SCHEMA = 'screen1b.teardown.v1'
REQUIRED_PHASES = ('submissions_stopped', 'async_output_drained', 'queues_closed',
                   'drained', 'graphs_released', 'expert_tables_released',
                   'uva_released', 'ple_closed', 'pinned_released',
                   'registries_cleared', 'worker_released', 'distributed_released',
                   'final_sync', 'device_cache_empty', 'host_cache_empty',
                   'post_cache_sync', 'complete')


def _validate(row, path):
    if row.get('schema') != SCHEMA or row.get('status') != 'complete':
        raise ValueError('wrong schema or unsuccessful release')
    rank, pid = row.get('rank'), row.get('pid')
    if type(rank) is not int or rank < 0 or type(pid) is not int or pid <= 0:
        raise ValueError('invalid rank/PID')
    if path.name != f'loader-{pid}.jsonl':
        raise ValueError('receipt PID does not match loader filename')
    if row.get('error') or row.get('errors'):
        raise ValueError('receipt contains cleanup errors')
    timestamps = row.get('timestamps', {})
    previous = -1
    for phase in REQUIRED_PHASES:
        stamp = timestamps.get(phase, {})
        mono, unix = stamp.get('monotonic_ns'), stamp.get('unix_ns')
        if (type(mono) is not int or type(unix) is not int or
                mono < previous or mono < 0 or unix <= 0):
            raise ValueError('missing or unordered release timestamp: ' + phase)
        utc = datetime.datetime.fromisoformat(stamp['utc'].replace('Z', '+00:00'))
        if utc.utcoffset() != datetime.timedelta(0):
            raise ValueError('timestamp must be UTC')
        if abs(utc.timestamp() - unix / 1_000_000_000) > 1:
            raise ValueError('UTC and Unix timestamp disagree')
        previous = mono
    return rank


def validate_rank_receipts(run, expected_ranks=range(4)):
    expected, found, errors = set(expected_ranks), {}, []
    for path in sorted(Path(run).glob('loader-*.jsonl')):
        try:
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('non-object loader event')
                if row.get('event') == 'rank_teardown_failed':
                    raise ValueError('worker reported failed teardown')
                if row.get('event') != 'rank_teardown_complete':
                    continue
                rank = _validate(row, path)
                if rank not in expected or rank in found:
                    raise ValueError('unexpected or duplicate rank ' + str(rank))
                found[rank] = row
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append(f'{path.name}: {exc}')
    missing = sorted(expected - set(found))
    if missing:
        errors.append('missing final rank receipts: ' + str(missing))
    return {'schema': 'screen1b.teardown-validation.v1',
            'passed': not errors, 'expected_ranks': sorted(expected),
            'received_ranks': sorted(found), 'errors': errors}
