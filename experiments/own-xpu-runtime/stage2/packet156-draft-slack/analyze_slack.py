"""Read retained packet154 receipts, never a device or model payload.

This bounds the proposed HOST insertion after rank.hpp's completed drain.
It does not timestamp hardware prefix completion or price an earlier enqueue.
All reported gain ceilings are counterfactual arithmetic, not measurements.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import shutil
import statistics as st

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
THRESHOLD_MS_PER_HIT = 0.423078
spec = importlib.util.spec_from_file_location('packet154_original', P/'method/packet154_analyze.py')
original = importlib.util.module_from_spec(spec)
spec.loader.exec_module(original)


def demand(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def balanced(rows, key):
    classes = {}
    for row in rows:
        classes.setdefault(row['prompt_class'], []).append(row[key])
    demand(len(classes) >= 5, 'varied prompt classes missing')
    return st.median(st.median(v) for v in classes.values())


def windows(r1, request):
    """Use only unique, identity-matched actual command scopes; fail missing."""
    groups = {}
    for row in r1:
        key = (row['sequence'], row['op'], row['position'])
        groups.setdefault(key, {}).setdefault(row['p154_segment'], []).append(row)
    timestamps = request['token_timestamps']
    demand(len(timestamps) == 64 and all(math.isfinite(t) for t in timestamps)
           and all(b > a for a, b in zip(timestamps, timestamps[1:])), '64 monotone timestamps required')
    first, last = timestamps[0], timestamps[-1]
    out = []
    for (sequence, op, position), group in groups.items():
        if 'prefix_pack' not in group and 'wait_rank0_suffix' not in group:
            continue  # prefill HALF has no split head
        required = ('command', 'b_completion', 'prefix_pack', 'prefix_export', 'wait_rank0_suffix')
        demand(all(len(group.get(name, [])) == 1 for name in required),
               'missing/duplicate command-bound suffix scope')
        c, b, pack, export, wait = (group[name][0] for name in required)
        demand(op == 1 and sequence > 0 and position >= 0, 'invalid HALF identity')
        demand(c['start'] <= b['start'] <= b['end'] <= pack['start'] <= pack['end']
               <= export['start'] <= export['end'] <= wait['start'] <= wait['end'] <= c['end'],
               'illegal prefix/suffix scope order')
        # Actual insertion boundary is after b_completion returns. Include
        # pack/export and host overhead as FREE slack: deliberately optimistic.
        begin, end = b['end'], wait['end']
        clipped = max(0., min(last, end) - max(first, begin)) * 1000
        out.append(dict(sequence=sequence, op=op, position=position,
                        prefix_drain_return=begin, suffix_observed_ready=end,
                        enclosing_ms=(end-begin)*1000, credited_ms=clipped,
                        explicit_suffix_wait_ms=wait['ms'],
                        fully_inside_interval_window=first <= begin <= end <= last))
    demand(out and any(r['credited_ms'] > 0 for r in out), 'no suffix window samples')
    ordered = sorted(out, key=lambda r: r['prefix_drain_return'])
    demand(all(a['suffix_observed_ready'] <= b['prefix_drain_return']
               for a, b in zip(ordered, ordered[1:])), 'overlapping suffix windows')
    return out


def request_bound(folder, request):
    # Original parser must first validate BOTH streams, full census, and joins.
    split = original.request_split(folder.parent, request)
    r1 = original.stream(folder/'rank1/timings.jsonl', 1)
    samples = windows(r1, request)
    clipped_total = sum(r['credited_ms'] for r in samples)
    # Also donate boundary windows, even when outside the timed interval or
    # followed by no DRAFT. A shifted branch may benefit the next interval;
    # this avoids excluding first-interval credit by assuming cycle alignment.
    total = sum(r['enclosing_ms'] for r in samples)
    elapsed = (request['token_timestamps'][-1]-request['token_timestamps'][0])*1000
    demand(0 < total < elapsed, 'invalid total enclosing window')
    demand(request['passed'] and request['cached_tokens'] == 0 and request['exact_oracle'],
           'request quality/cold gate failed')
    hits = request['hits']
    demand(type(hits) is int and 0 < hits <= 63, 'invalid hit count')
    return dict(prompt_id=request['prompt_id'], prompt_class=request['prompt_class'],
                interval_count=63, hits=hits, elapsed_ms=elapsed,
                sampled_windows=len(samples),
                fully_contained_windows=sum(r['fully_inside_interval_window'] for r in samples),
                credited_total_ms=total, interval_clipped_total_ms=clipped_total,
                extra_boundary_credit_ms=total-clipped_total,
                enclosing_ms_per_interval=total/63,
                all_window_credit_per_hit_ms=total/hits,
                explicit_wait_ms_per_interval=sum(r['explicit_suffix_wait_ms']
                    for r in samples if r['fully_inside_interval_window'])/63,
                observed_fixed64_rate=63000/elapsed,
                counterfactual_all_window_removed_rate=63000/(elapsed-total),
                remote_reply_wait_ms_per_interval=split['remote_reply_wait_ms_per_cycle'],
                draft_overlap_ms_per_interval=split['overlap_ms_per_cycle']['draft'],
                below_hit_threshold=total/hits < THRESHOLD_MS_PER_HIT,
                windows=samples)


def analyze(run, summary):
    demand(summary['passed'], 'packet154 equality/report gate failed')
    views = run['views']
    smoke = run['kind'] == 'smoke'
    demand([v['choice'] for v in views] == (['candidate'] if smoke else
           ['control', 'candidate', 'control', 'candidate', 'control']), 'incomplete view sequence')
    # Full, unmodified analyzer replay, including every per-command overlap.
    replay = original.analyze(views, smoke=smoke)
    demand(replay == summary['rank1_split'], 'original complete split replay differs')
    output = []
    for view in views:
        demand(view['passed'] and len(view['requests']) == 12, 'incomplete/failed view')
        demand(len({r['prompt_id'] for r in view['requests']}) == 12, 'duplicate prompt')
        root = Path(view['output'])
        # No elapsed-wall deadline: the FIRST completed request itself is proof.
        first = original.request_split(root, view['requests'][0])
        demand(first['waits'], 'first request missing actual timing data')
        requests = [request_bound(root/r['prompt_id'], r) for r in view['requests']]
        observed = balanced(requests, 'observed_fixed64_rate')
        ceiling = balanced(requests, 'counterfactual_all_window_removed_rate')
        output.append(dict(index=view['index'], choice=view['choice'],
            first_request_analyzer_passed=True,
            median_enclosing_ms_per_interval=st.median(r['enclosing_ms_per_interval'] for r in requests),
            max_all_window_credit_per_hit_ms=max(r['all_window_credit_per_hit_ms'] for r in requests),
            observed_class_balanced_fixed64_rate=observed,
            counterfactual_all_window_removed_class_balanced_rate=ceiling,
            counterfactual_gain_ceiling_percent=100*(ceiling/observed-1),
            all_prompts_below_hit_threshold=all(r['below_hit_threshold'] for r in requests),
            requests=requests))
    decision_rows = output if smoke else [v for v in output if v['choice'] == 'control']
    below = all(v['all_prompts_below_hit_threshold'] and v['counterfactual_gain_ceiling_percent'] < 2
                for v in decision_rows)
    return dict(schema='packet156.host-suffix-slack-bound.v1', passed=True,
        kind=run['kind'], complete_original_analyzer_replay=True,
        threshold_ms_per_hit=THRESHOLD_MS_PER_HIT,
        scope='host insertion after completed prefix drain; not hardware prefix completion',
        bound='credit every enclosing window, including misses, boundary windows and required pack/export, with zero adoption/dispatch cost',
        device_speed_measurement=False, candidate_implemented=False,
        branch_service_measured_on_bundle8=False,
        below_threshold=below,
        decision=('close this host suffix-slack arm before implementation' if below else 'bound does not close arm'),
        views=output)


def retain(source, destination):
    raw = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    packed = gzip.compress(raw, mtime=0)
    destination.write_bytes(packed)
    demand(gzip.decompress(destination.read_bytes()) == raw, 'retention round-trip failed')
    return dict(source=str(source.relative_to(ROOT)), sha256=digest(raw), bytes=len(raw),
                retained=str(destination.relative_to(P)), retained_sha256=digest(packed),
                retained_bytes=len(packed))


def main():
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    demand(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    demand(set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32)), 'CPU affinity')
    demand(shutil.disk_usage('/').free >= 27_000_000_000, 'CPU preparation disk floor 27 GB')
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('--retain', action='store_true')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    source = args.source.resolve()
    inputs = source/'run/bracket-inputs.json'
    report = source/'bracket-summary.json'
    run, summary = json.loads(inputs.read_text()), json.loads(report.read_text())
    result = analyze(run, summary)
    files = [inputs, report]
    for view in run['views']:
        for r in view['requests']:
            for rank in (0,1):
                files.append(Path(view['output'])/r['prompt_id']/f'rank{rank}/timings.jsonl')
    result['inputs'] = []
    for path in files:
        if args.retain:
            result['inputs'].append(retain(path, P/'evidence/raw'/source.name/(str(path.relative_to(source))+'.gz')))
        else:
            raw = path.read_bytes()
            result['inputs'].append(dict(source=str(path.relative_to(ROOT)), sha256=digest(raw), bytes=len(raw)))
    result['analyzer_sha256'] = digest((P/'method/packet154_analyze.py').read_bytes())
    result['method_sha256'] = digest(Path(__file__).read_bytes())
    result['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('views','inputs')}, indent=2))
    print(json.dumps([{k:v for k,v in view.items() if k!='requests'} for view in result['views']], indent=2))


if __name__ == '__main__':
    main()
