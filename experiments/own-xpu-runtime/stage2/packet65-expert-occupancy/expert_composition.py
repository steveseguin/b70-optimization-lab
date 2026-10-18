#!/usr/bin/env python3
"""CPU-only K2-style analysis of full-engine packet65 attribution screens.

Input is two independently loaded, matched control/candidate screen pairs.
This is a class-screen gate, never a public speed or quality promotion.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
FIXTURES = tuple(range(9, 17))
THRESHOLD = 30.0
COMPONENTS = ('router', 'route', 'expsgate', 'expsact', 'expsdown', 'moe', 'ffn.combine')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def rows(path):
    with Path(path).open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def median_by_class(values, prompt_classes):
    grouped = defaultdict(list)
    for prompt, value in values.items():
        grouped[prompt_classes[prompt]].append(value)
    return statistics.median(statistics.median(v) for v in grouped.values())


def collect_rank(path, rank):
    """Last complete attempt per fixture, summing actual events within each site.

    Failed speculative prefixes are retained as counts, never treated as a fast
    complete layer. The last completed attempt is the one resolving each target
    position; the outer screen separately checks every emitted oracle token.
    """
    events, completions = defaultdict(list), {}
    for row in rows(path):
        require(row.get('schema') in ('packet65.event.v1', 'packet65.half.v1'),
                'foreign/mixed attribution row: ' + str(path))
        require(row['rank'] == rank and row['fixture'] in FIXTURES, 'rank/sample mismatch')
        if row['schema'] == 'packet65.half.v1':
            require(row['half'] not in completions, 'duplicate half completion')
            completions[row['half']] = row
        else:
            require(row['class'] == 'moe_experts', 'foreign class')
            require(isinstance(row['start_ns'], int) and isinstance(row['end_ns'], int)
                    and 0 < row['start_ns'] < row['end_ns'], 'invalid event interval')
            events[row['half']].append(row)
    chosen = {}
    for half, row in sorted(completions.items()):
        if not row['cancelled']:
            chosen[row['fixture']] = half
    require(set(chosen) == set(FIXTURES), 'missing complete target fixture')
    result, signatures, positions, selected = {}, {}, {}, {}
    layers = set(range(0, 24) if rank == 0 else range(24, 48))
    for fixture, half in chosen.items():
        summary = completions[half]
        sums, counts, event_ids = defaultdict(int), defaultdict(int), set()
        for row in events[half]:
            require(all(row[k] == summary[k] for k in ('rank', 'fixture', 'position', 'speculative')),
                    'event belongs to another half')
            require(row['event'] not in event_ids, 'duplicate event')
            event_ids.add(row['event'])
            label = row['label']
            parts = label.split('.', 2)
            require(len(parts) == 3 and parts[0] == 'blk' and int(parts[1]) in layers,
                    'unexpected layer ownership')
            sums[label] += row['end_ns'] - row['start_ns']
            counts[label] += 1
        observed = {int(label.split('.')[1]) for label in sums}
        require(observed == layers, 'partial layer composition')
        require(set(sums) == {f'blk.{layer}.{component}' for layer in layers for component in COMPONENTS},
                'missing/extra site in registered packet57 routed class')
        result[fixture] = dict(sums)
        signatures[fixture] = dict(counts)
        positions[fixture] = summary['position']
        selected[fixture] = dict(half=half, speculative=summary['speculative'])
    return dict(sums=result, signatures=signatures, positions=positions, selected=selected,
                half_count=len(completions), cancelled_half_count=sum(r['cancelled'] for r in completions.values()),
                uncompleted_half_count=len(set(events) - set(completions)))


def load_screen(root):
    root = Path(root).resolve()
    window, identity = read(root / 'window.json'), read(root / 'identity.json')
    summary = read(root / 'run/summary.json')
    require(window.get('passed') is True and window.get('device_executed') is True,
            'unfinished/non-device screen: ' + str(root))
    require(not window.get('child_still_running') and not window.get('stop_reasons'), 'screen did not drain cleanly')
    require(window.get('whole_host_isolated') is True, 'whole-host class timing required')
    require(window['model_lifetimes'] == 1 and window['identity'] == identity, 'screen identity/lifetime mismatch')
    require(identity['timing'] == 'attribution' and identity['profile'] == 'tp2', 'in-engine attribution required')
    sys.path.insert(0,str(HERE/'screen'))
    from common import D, sealed
    admitted = sealed(SimpleNamespace(lineage=Path(identity['lineage']), seal=Path(identity['seal']),
        binary=Path(identity['binary']), dispatch=Path(identity['dispatch']),
        profile='tp2', timing='attribution', placement='1'))
    require(all(identity.get(key) == value for key,value in admitted.items()), 'screen CPU seal identity changed')
    require(identity['placement']['name'] == '1' and identity['placement']['target_layers'] == [24, 24],
            '24/24 rank1 draft placement required')
    selection = read(Path(identity['lineage']) / 'selection.json')
    require(sha(Path(identity['lineage']) / 'selection.json') == identity['selection_sha256'], 'selection changed')
    require(summary.get('passed') is True and summary.get('cached_tokens') == 0
            and summary.get('request_count') == 12 and summary.get('requested_max_new') == 128,
            'all twelve cold 128-token requests required')
    require(summary['incident64']['passed'] is True and summary['incident64']['tokens_compared'] == 64,
            '64-token incident gate failed')
    manifest = read(root / 'suite-manifest.snapshot.json')
    require(manifest == D.oracle_inputs(), 'registered oracle/input manifest differs')
    prompts = [row['prompt_id'] for row in manifest['prompts']]
    require(prompts == list(D.CHECK.PROMPT_IDS), 'prompt suite incomplete/reordered')
    receipts = {row['prompt_id']: row for row in summary['requests']}
    require(set(receipts) == set(prompts), 'summary suite differs')
    oracle = HERE.parent / 'packet49-integrate/oracle'
    spec = importlib.util.spec_from_file_location('packet65_oracle', oracle / 'suite_check.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    require(window['oracle_completion_sha256'] == sha(oracle / 'results/completion.json'),
            'packet49 oracle completion binding differs')
    classes, payloads = {}, {}
    for prompt in prompts:
        row = receipts[prompt]
        require(row.get('passed') is True and row.get('exact_oracle') is True, 'exact packet49 tokens failed')
        require(row['tokens'] == checker.token_record(oracle / 'results' / prompt)[:128]
                and len(row['tokens']) == 128, 'actual packet49 oracle token mismatch')
        classes[prompt] = row['prompt_class']
        require(classes[prompt] == D.METRICS.PROMPT_CLASSES[prompt], 'prompt class changed')
        payloads[prompt] = dict(prompt_token_sha256=row['prompt_token_sha256'], tokens=row['tokens'])
    require(len(set(classes.values())) >= 5, 'representative prompt classes missing')
    incident = read(root / 'run/incident64/receipt.json')
    require(incident['tokens'] == checker.token_record(oracle / 'results' / prompts[0])[:64]
            and len(incident['tokens']) == 64, 'actual incident64 oracle mismatch')
    attribution, hashes = {}, {}
    for prompt in ['incident64'] + prompts:
        rank_rows = {}
        for rank in (0, 1):
            matches = list((root / 'run' / prompt).glob(f'**/rank{rank}/sites.jsonl'))
            require(len(matches) == 1, f'one sites file required: {prompt}/rank{rank}')
            rank_rows[rank] = collect_rank(matches[0], rank)
            hashes[str(matches[0].relative_to(root))] = sha(matches[0])
        attribution[prompt] = rank_rows
    hashes.update({name:sha(root/name) for name in
        ('identity.json','run/summary.json','suite-manifest.snapshot.json','run/incident64/receipt.json')})
    for name,digest in hashes.items():
        require(window['files'].get(name)==digest, 'completed screen artifact changed: '+name)
    return dict(root=str(root), identity=identity, window=window, selection=selection,
                classes=classes, payloads=payloads, attribution=attribution,
                inputs_sha256={**hashes, 'window.json':sha(root/'window.json')})


def candidate_name(run):
    return run['selection']['choices']['experts']


def compare(control, candidate):
    require(candidate_name(control) == 'production', 'control is not production')
    require(candidate_name(candidate) in ('wg64', 'wg128', 'prefetch64', 'wide64'), 'unregistered candidate')
    require(control['classes'] == candidate['classes'] and control['payloads'] == candidate['payloads'],
            'prompt/output/quality identity differs')
    for field in ('binary_sha256', 'dispatch_sha256', 'memory_plan_sha256', 'profile', 'timing', 'lane', 'conditions'):
        require(control['identity'][field] == candidate['identity'][field], 'unmatched ' + field)
    for field in ('name','draft_rank','target_split','target_layers','context','memory_plan_sha256','rank_dispatch_sha256'):
        require(control['identity']['placement'][field] == candidate['identity']['placement'][field],
                'unmatched placement '+field)
    require(control['window']['boot_id'] == candidate['window']['boot_id'], 'matched pair spans boots')
    require(control['window']['environment'] == candidate['window']['environment'], 'closed runtime environment differs')
    require(control['window']['oracle_completion_sha256'] == candidate['window']['oracle_completion_sha256'],
            'packet49 oracle changed')
    left, right = dict(control['selection']), dict(candidate['selection'])
    left['choices'], right['choices'] = dict(left['choices']), dict(right['choices'])
    left['choices'].pop('experts'); right['choices'].pop('experts')
    require(left == right, 'selection changed outside experts')
    totals = {'control': {}, 'candidate': {}}
    rank_totals = {name:{0:{}, 1:{}} for name in totals}
    components = {name:defaultdict(dict) for name in totals}
    for prompt in control['attribution']:
        for rank in (0, 1):
            a, b = (run['attribution'][prompt][rank] for run in (control, candidate))
            require(a['signatures'] == b['signatures'] and a['positions'] == b['positions'],
                    f'composition/event count/position differs: {prompt}/rank{rank}')
        if prompt == 'incident64':
            continue  # Mandatory exactness and composition check, excluded from ranking.
        for name, run in (('control', control), ('candidate', candidate)):
            totals[name][prompt] = 0
            per_component = defaultdict(float)
            for rank in (0, 1):
                sampled = run['attribution'][prompt][rank]['sums']
                value = statistics.median(sum(labels.values()) for labels in sampled.values())
                rank_totals[name][rank][prompt] = value
                totals[name][prompt] += value
                all_components = {label.split('.',2)[2] for labels in sampled.values() for label in labels}
                for component in all_components:
                    per_component[component] += statistics.median(
                        sum(ns for label,ns in labels.items() if label.split('.',2)[2] == component)
                        for labels in sampled.values())
            for component, value in per_component.items():
                components[name][component][prompt] = value
    metric = {name:median_by_class(values, control['classes']) for name,values in totals.items()}
    reduction = 100*(1-metric['candidate']/metric['control'])
    rank_metrics = {str(rank):{name:median_by_class(rank_totals[name][rank], control['classes'])
                             for name in totals} for rank in (0,1)}
    for row in rank_metrics.values():
        row['latency_reduction_percent'] = 100*(1-row['candidate']/row['control'])
    details = {component:{name:median_by_class(components[name][component], control['classes'])
                         for name in totals} for component in components['control']}
    return dict(passed=reduction >= THRESHOLD and all(row['latency_reduction_percent'] >= 0 for row in rank_metrics.values()),
                control=control['root'], candidate=candidate['root'], candidate_name=candidate_name(candidate),
                class_ns_per_full_target_step=metric, latency_reduction_percent=reduction,
                per_rank_class_ns=rank_metrics, component_ns_per_full_target_step=details,
                prompt_class=control['classes'], prompt_class_ns=totals,
                input_sha256={run['root']:run['inputs_sha256'] for run in (control,candidate)})


def analyze(pairs):
    require(len(pairs) == 2, 'exactly two fresh matched pairs required')
    runs = [(load_screen(a), load_screen(b)) for a,b in pairs]
    require(len({run['root'] for pair in runs for run in pair}) == 4, 'fresh distinct screens required')
    require(len({run['window']['started_utc_ns'] for pair in runs for run in pair}) == 4,
            'duplicate process lifetime receipt')
    for role in (0,1):
        a,b = runs[0][role], runs[1][role]
        for field in ('binary_sha256','selection_sha256','seal_sha256','dispatch_sha256'):
            require(a['identity'][field] == b['identity'][field], 'candidate changed between repeats: '+field)
    results = [compare(a,b) for a,b in runs]
    return dict(schema='packet65.composition-screen.v1', passed=all(r['passed'] for r in results),
                device_executed=False, diagnostic=True, qualifying=False, submission_eligible=False,
                speed_evidence_eligible=False, integration_status='class screen only; full quality/record chain still required',
                required_latency_reduction_percent=THRESHOLD, arithmetic='iq3-p49-split32-v1',
                timing_definition='GPU event end minus start; sum p57 moe_experts sites in each actual half; median fixtures 9–16; sum rank medians; median prompts within class then median classes',
                scope='all 48 real target layers; router, routing, gather, experts, mixture and ffn combine under packet57 category precedence; gate/down components separate',
                no_cross_device_timestamp_subtraction=True, no_prompt_or_kv_reuse=True,
                repeats=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair', nargs=2, action='append', required=True, metavar=('CONTROL', 'CANDIDATE'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'fresh analysis output required')
    result = analyze(args.pair)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(passed=result['passed'], reductions_percent=[r['latency_reduction_percent'] for r in result['repeats']], output=str(args.output))))
    return 0 if result['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
