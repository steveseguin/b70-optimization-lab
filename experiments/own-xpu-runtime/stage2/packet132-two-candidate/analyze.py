#!/usr/bin/env python3
"""Independent-corpus threshold counts and explicitly hypothetical latency model."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import resource

P = Path(__file__).resolve().parent
ANCHOR = 17.4


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def costs():
    manifest = json.loads((P / 'inputs/manifest.json').read_text())
    for row in manifest['files']:
        assert sha(P / row['snapshot']) == row['sha256']
    raw = (P / 'inputs/BUDGET.md').read_text()
    assert 'Overhead gate: FAIL' in raw
    table = {}
    for line in raw.splitlines():
        cells = [s.strip() for s in line.split('|')[1:-1]]
        if len(cells) != 7 or cells[0] not in ('0', '1'):
            continue
        rank, outcome, clock, name, mean, median, n = cells
        table[int(rank), outcome, clock, name] = float(mean)

    def value(name, outcome='hit', rank=0, clock='compute'):
        return table.get((rank, outcome, clock, name), 0.0)

    names = [k[3] for k in table if k[:3] == (0, 'hit', 'compute')
             and k[3] not in ('compute_idle_observed', 'snapshot_capture', 'target_head_suffix')]
    groups = {group: sum(value(n) for n in names if n.split('/')[0] == group)
              for group in sorted({n.split('/')[0] for n in names})}
    experts = value('moe_experts/expsgate') + value('moe_experts/expsdown')
    favorable = experts * (1 - 10 / 512) + sum(value(n) for n in (
        'attention/gdn.recurrence', 'moe_experts/expsact', 'moe_experts/ffn.combine',
        'moe_experts/route', 'attention/qsa.attention', 'attention/qsa.pool',
        'attention/qsa.select'))
    redo = sum(value(n, 'miss') - value(n) for n in names)
    restore = value('rollback', 'miss')
    result = dict(target_class_groups_ms=groups, target_half_compute_ms=sum(groups.values()),
                  expert_gate_down_ms=experts, redo_compute_ms=redo, restore_compute_ms=restore,
                  observed_idle_delta_ms=value('compute_idle_observed', 'miss') - value('compute_idle_observed'),
                  host_gap_delta_ms=value('host.command_gap', 'miss', clock='host') - value('host.command_gap', clock='host'),
                  rank1_suffix_wait_hit_ms=value('wait.head.suffix', rank=1, clock='host'),
                  rank1_suffix_wait_miss_ms=value('wait.head.suffix', 'miss', 1, 'host'),
                  rank0_snapshot_hit_ms=value('snapshot_capture'),
                  overhead_gate_passed=False, source_sha256=sha(P / 'inputs/BUDGET.md'))
    scenarios = [
        dict(name='favorable_primary', extra_half_ms=favorable, rescued_miss_ms=15.0,
             per_cycle_policy_ms=0.0, rescued_state_selection_ms=0.0),
        dict(name='expert_only_extreme', extra_half_ms=experts * (1 - 10 / 512), rescued_miss_ms=15.0,
             per_cycle_policy_ms=0.0, rescued_state_selection_ms=0.0),
        dict(name='favorable_compute_saving', extra_half_ms=favorable, rescued_miss_ms=redo + restore,
             per_cycle_policy_ms=0.0, rescued_state_selection_ms=0.0),
        dict(name='duplicate_half_with_state', extra_half_ms=sum(groups.values()) + value('snapshot_capture') + .1,
             rescued_miss_ms=redo + restore, per_cycle_policy_ms=value('draft/argmax/argmax', rank=1),
             rescued_state_selection_ms=restore),
    ]
    return result, scenarios


def policies():
    return ([dict(feature='never', tau=None)] +
            [dict(feature='margin', tau=i / 8) for i in range(129)] +
            [dict(feature='margin', tau=x) for x in (32, 64)] +
            [dict(feature='prefix_probability', tau=i / 40) for i in range(41)] +
            [dict(feature='prefix_probability', tau=1.01), dict(feature='always', tau=None)])


def flagged(row, policy):
    if policy['feature'] in ('never', 'always'):
        return policy['feature'] == 'always'
    return row[policy['feature']] < policy['tau']


def metrics(rows, policy, scenario):
    n = len(rows)
    assert n
    flags = [flagged(row, policy) for row in rows]
    hits = [row['top1'] == row['target_token'] for row in rows]
    rescue = [f and not h and row['top2'] == row['target_token']
              for row, f, h in zip(rows, flags, hits)]
    misses = n - sum(hits)
    second = sum(not h and row['top2'] == row['target_token'] for row, h in zip(rows, hits))
    f = sum(flags)
    r = sum(rescue)
    overhead = scenario['per_cycle_policy_ms'] if policy['feature'] != 'never' else 0
    benefit = scenario['rescued_miss_ms'] - scenario['rescued_state_selection_ms']
    delta = f / n * scenario['extra_half_ms'] - r / n * benefit + overhead
    projected_ms = ANCHOR + delta
    affordable = (r/n*benefit - (ANCHOR-ANCHOR/1.03) - overhead)/(f/n) if f else None
    # An interval after token i pays the speculation for i+1. No cross-prompt edge.
    intervals = []
    for i in range(n - 1):
        if rows[i]['prompt_id'] != rows[i + 1]['prompt_id']:
            continue
        assert rows[i + 1]['generated_index'] == rows[i]['generated_index'] + 1
        intervals.append(flags[i + 1] * scenario['extra_half_ms'] - rescue[i] * benefit + overhead)
    finite_delta = sum(intervals) / len(intervals) if intervals else None
    standardized = None
    if misses and sum(hits):
        fs = .79 * sum(f and h for f, h in zip(flags, hits))/sum(hits) + .21 * sum(f and not h for f, h in zip(flags, hits))/misses
        rs = .21 * r/misses
        ds = fs*scenario['extra_half_ms'] - rs*benefit + overhead
        standardized = dict(assumed_miss_fraction=.21, flagged_fraction=fs, rescued_fraction=rs,
                            delta_ms=ds, gain_percent=100*(ANCHOR/(ANCHOR+ds)-1))
    return dict(positions=n, flags=f, flagged_fraction=f/n, top1_hits=sum(hits), misses=misses,
                baseline_acceptance=sum(hits)/n, second_choice_equals_target_on_misses=second,
                second_choice_fraction_of_misses=second/misses if misses else None,
                flagged_misses=sum(f and not h for f, h in zip(flags, hits)), rescued_misses=r,
                rescued_fraction_of_all_misses=r/misses if misses else None,
                rescue_per_flag=r/f if f else None, acceptance_with_two_candidates=(sum(hits)+r)/n,
                delta_ms=delta, projected_ms=projected_ms, projected_tok_s=1000/projected_ms,
                maximum_extra_half_ms_for_three_percent=affordable,
                gain_percent=100*(ANCHOR/projected_ms-1),
                finite_intervals=len(intervals), finite_delta_ms=finite_delta,
                finite_gain_percent=100*(ANCHOR/(ANCHOR+finite_delta)-1) if intervals else None,
                standardized_to_brief_miss_rate=standardized)


def validate_rows(rows):
    seen = set()
    for row in rows:
        key = row['prompt_id'], row['generated_index']
        assert key not in seen
        seen.add(key)
        assert 1 <= row['source_index'] <= 5
        assert row['top1'] != row['top2']
        assert all(type(row[k]) is int and row[k] >= 0 for k in ('top1', 'top2', 'target_token'))
        assert row['top1'] < 80128 and row['top2'] < 80128
        assert math.isfinite(row['margin']) and row['margin'] >= 0
        assert 0 <= row['prefix_probability'] <= 1
    for source in range(1, 6):
        selected = [row for row in rows if row['source_index'] == source]
        assert selected and len({r['prompt_id'] for r in selected}) == 1
        assert [r['generated_index'] for r in selected] == list(range(len(selected)))
        assert len(selected) <= 24


def validate_capture(path, rows):
    root = path.parent
    complete = json.loads((root/'completion.json').read_text())
    assert complete['device_executed'] is False
    assert complete['rows'] == len(rows)
    assert sha(root/'rows.jsonl') == complete['rows_sha256']
    assert [json.loads(s) for s in (root/'rows.jsonl').read_text().splitlines()] == rows
    inputs = json.loads((root/'inputs.json').read_text())
    assert len(inputs['sources']) == 5
    rule = json.loads((P/'inputs/preregistration.json').read_text())
    assert inputs['preregistration_sha256'] == sha(P/'inputs/preregistration.json')
    for i, source in enumerate(inputs['sources']):
        directory = root/f'doc-{i}'
        target = json.loads((directory/'target/result.json').read_text())
        receipt = json.loads((directory/'draft-receipt.json').read_text())
        selected = [r for r in rows if r['source_index'] == i+1]
        assert target['arithmetic'] == 'iq3-p49-split32-v1'
        assert target['device_executed'] is False and receipt['device_executed'] is False
        assert target['status'] in ('token-cap', 'eos') and target['error'] == ''
        assert len(selected) == len(target['tokens']) == receipt['count']
        assert target['status'] == 'eos' or len(selected) == 24
        assert len(source['tokens']) == 16 and source['generated_token_cap'] == 24
        assert source['source_commit'] == rule['source_commit']
        assert all(source[k] == rule['sources'][i][k] for k in ('path', 'sha256', 'bytes'))
        assert source['excerpt_start'] == source['full_token_count']//2
        assert [r['target_token'] for r in selected] == target['tokens']
        assert all(r['draft_prefix_rows'] == 80128 for r in selected)
        assert all(r['source_path'] == source['path'] for r in selected)
        assert [r['position'] for r in selected] == list(range(14, 14+len(selected)))
        consumed = source['tokens'] + target['tokens']
        assert all(r['next_input_token'] == consumed[r['position']+1] for r in selected)
    return dict(complete=True, completion_sha256=sha(root/'completion.json'),
                inputs_sha256=sha(root/'inputs.json'))


def analyze(rows):
    validate_rows(rows)
    budget, scenarios = costs()
    groups = dict(train=[r for r in rows if r['source_index'] <= 3],
                  heldout=[r for r in rows if r['source_index'] >= 4], pooled=rows)
    sweep, decisions = [], []
    for scenario in scenarios:
        choices = []
        for policy in policies():
            record = dict(scenario=scenario['name'], policy=policy,
                          **{name: metrics(group, policy, scenario) for name, group in groups.items()})
            choices.append(record)
        selected = min(choices, key=lambda r: (r['train']['delta_ms'], r['train']['flags']))
        pooled = min(choices, key=lambda r: (r['pooled']['delta_ms'], r['pooled']['flags']))
        active = min((r for r in choices if r['pooled']['flags']),
                     key=lambda r: (r['pooled']['delta_ms'], r['pooled']['flags']))
        affordable = max((r for r in choices if r['pooled']['flags']),
                         key=lambda r: r['pooled']['maximum_extra_half_ms_for_three_percent'])
        decisions.append(dict(scenario=scenario, train_selected=selected, pooled_best_in_sample=pooled,
                              pooled_best_active_in_sample=active,
                              pooled_most_affordable_cost_in_sample=affordable))
        sweep.extend(choices)
    primary = decisions[0]['train_selected']
    passed = decisions[0]['pooled_best_in_sample']['pooled']['gain_percent'] >= 3
    return dict(schema='lab.packet132.cpu-projection.v1', performance_claim=False,
                device_executed=False, implementation_built=False,
                target_arithmetic='iq3-p49-split32-v1', draft_prefix_rows=80128,
                draft_scope='packet31 CPU INT8 semantic reference; device numerical parity unestablished',
                realistic_final_gate=dict(passed=False, reason='CPU acceptance/cost projection; no device benchmark or implementation quality gate'),
                anchor_ms=ANCHOR, anchor_tok_s=1000/ANCHOR, required_saving_ms=ANCHOR-ANCHOR/1.03,
                budget=budget, decisions=decisions, gate_passed=passed,
                heldout_robustness_passed=primary['heldout']['gain_percent'] >= 3,
                disposition='design-note-only' if passed else 'close-no-implementation',
                rows_sha256=None), sweep


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rows', type=Path, default=P/'evidence/capture/rows.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    resource.setrlimit(resource.RLIMIT_AS, (512_000_000, 512_000_000))
    data = json.loads(args.rows.read_text())
    rows = data if isinstance(data, list) else data['rows']
    complete = validate_capture(args.rows, rows)
    audit = json.loads((P/'evidence/source-audit.json').read_text())
    assert audit['passed'] and audit['device_executed'] is False
    assert audit['capture_receipt_sha256'] == sha(args.rows.parent/'build-receipt.json')
    result, sweep = analyze(rows)
    frozen_path = P/'evidence/training-selection.json'
    frozen = json.loads(frozen_path.read_text())
    assert frozen['heldout_confidence_rows_read'] is False
    assert frozen['positions'] == sum(r['source_index'] <= 3 for r in rows)
    for source, digest in frozen['sources'].items():
        assert sha(args.rows.parent/f'doc-{int(source)-1}/draft-rows.jsonl') == digest
    for old, decision in zip(frozen['decisions'], result['decisions'], strict=True):
        assert old['scenario'] == decision['scenario']['name']
        assert old['policy'] == decision['train_selected']['policy']
        assert old['train'] == decision['train_selected']['train']
    result['training_selection_sha256'] = sha(frozen_path)
    result['capture'] = complete
    result['source_audit_sha256'] = sha(P/'evidence/source-audit.json')
    result['rows_sha256'] = sha(args.rows)
    for name, obj in [('result.json', result), ('thresholds.json.gz', sweep)]:
        raw = (json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode()
        if name.endswith('.gz'):
            compressed = gzip.compress(raw, mtime=0)
            assert gzip.decompress(compressed) == raw
            raw = compressed
        if args.check:
            assert (P/name).read_bytes() == raw, name
        else:
            (P/name).write_bytes(raw)
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['scenario', 'feature', 'tau', 'group', 'positions', 'flags',
                     'flagged_fraction', 'top1_hits', 'misses', 'flagged_misses',
                     'rescued_misses', 'rescued_fraction_of_all_misses',
                     'acceptance_with_two_candidates', 'projected_tok_s', 'gain_percent',
                     'finite_gain_percent', 'maximum_extra_half_ms_for_three_percent'])
    for record in sweep:
        for group in ('train', 'heldout', 'pooled'):
            m = record[group]
            writer.writerow([record['scenario'], record['policy']['feature'], record['policy']['tau'], group,
                             *[m[k] for k in ('positions', 'flags', 'flagged_fraction', 'top1_hits', 'misses',
                                             'flagged_misses', 'rescued_misses', 'rescued_fraction_of_all_misses',
                                             'acceptance_with_two_candidates', 'projected_tok_s', 'gain_percent',
                                             'finite_gain_percent', 'maximum_extra_half_ms_for_three_percent')]])
    raw = out.getvalue().encode()
    if args.check:
        assert (P/'thresholds.csv').read_bytes() == raw
    else:
        (P/'thresholds.csv').write_bytes(raw)
    print(json.dumps(dict(gate_passed=result['gate_passed'], disposition=result['disposition'],
                          decisions=[dict(scenario=d['scenario']['name'], policy=d['train_selected']['policy'],
                                          heldout_gain=d['train_selected']['heldout']['gain_percent'],
                                          pooled_best_gain=d['pooled_best_in_sample']['pooled']['gain_percent'])
                                     for d in result['decisions']]), indent=2))


if __name__ == '__main__':
    main()
