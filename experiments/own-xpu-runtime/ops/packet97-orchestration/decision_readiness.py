"""CPU-only packet97d evaluation of every identical sealed selection bracket.

Frozen source decisions retain their original bytes. Only the two replaced CPU
entry points may resolve to their byte-exact frozen97b copies; all runtime,
source, receipt and seal pins still use the original strict validator.
"""
import argparse
import copy
import json
import math
import statistics
import subprocess
from pathlib import Path
from types import SimpleNamespace

import orchestrate as o
import composite_jobs as c

RULE = 'identical-selection-v1'
IDENTITY_FIELDS = ('selection_sha256', 'binary_sha256', 'seal_sha256',
                   'dispatch_sha256', 'memory_plan_sha256', 'profile', 'timing',
                   'placement')


def preserved_pins(config):
    pins = dict(config['evidence_pins'])
    for leaf in ('orchestrate.py', 'verify_ready.py'):
        key = o.pin_path(o.O / leaf)
        if key in pins and o.sha(o.O / leaf) != pins[key]:
            archive = o.O / 'frozen97b' / leaf
            assert o.sha(archive) == pins[key], 'unrecognized historical policy: ' + key
            pins[o.pin_path(archive)] = pins.pop(key)
    return pins


def validate(config):
    checked = dict(config, evidence_pins=preserved_pins(config))
    c.validate(checked)


def sealed_identity(selection):
    from bootstrap import install
    install()
    from common import sealed
    view = c.view(selection)
    return sealed(SimpleNamespace(lineage=view, seal=view/'screen-seal.json',
                  binary=None, dispatch=None, profile='tp2', timing='token', placement='1'))


def identical(actual, expected):
    return all(key in actual and key in expected and actual[key] == expected[key]
               for key in IDENTITY_FIELDS)


def completed(root):
    path = root/'window.json'
    if not path.exists():
        return False
    row = json.loads(path.read_text())
    return bool(row.get('finished_utc_ns')) and not row.get('child_still_running')


def diagnostic_rates(roots):
    """Retain timestamp-derived drift even when exactness validation fails."""
    rates = []
    for root in roots:
        try:
            summary = json.loads((root/'run/summary.json').read_text())
            grouped = {}
            for request in summary['requests']:
                times = request['token_timestamps']
                grouped.setdefault(request['prompt_class'], []).append(99/(times[99]-times[0]))
            rates.append(statistics.median(statistics.median(values) for values in grouped.values()))
        except (OSError, ValueError, KeyError, IndexError, ZeroDivisionError):
            rates.append(None)
    return rates


def collect(config):
    """Enumerate both lanes independently, across all saved decisions/variants."""
    validate(config)
    expected = {'control': sealed_identity(config['control']),
                'candidate': sealed_identity(config['candidate'])}
    brackets, excluded, receipts = [], [], {}
    import compare
    for path in sorted((o.O/'decisions').glob('*.json')):
        source = json.loads(path.read_text())
        assert path.stem == c.identity(source), 'decision filename identity differs'
        for variant, selection in {**c.variants(source), **c.variants(source, True)}.items():
            if selection != config['candidate'] or source['control'] != config['control']:
                continue
            for lane in ('A', 'B'):
                jobs = c.jobs(source, lane, variant)
                roots = [c.WRAPPER/'evidence'/job['out'] for job in jobs]
                if not all(completed(root) for root in roots):
                    continue
                entry = dict(decision=o.pin_path(path), decision_sha256=o.sha(path),
                             variant=variant, lane=lane, outputs=list(map(str, roots)))
                identities = [json.loads((root/'identity.json').read_text()) for root in roots]
                if not all(identical(actual, expected[job['choice']])
                           for actual, job in zip(identities, jobs)):
                    excluded.append(dict(entry, reason='selection/binary/baseline/seal identity differs'))
                    continue
                # Validate every matching decision, not only the requested one.
                old_view, old_output = compare.view, compare.output
                try:
                    validate(source)
                    choices = {'control': source['control'], 'candidate': selection}
                    compare.view = lambda label: c.view(choices[label])
                    compare.output = lambda job: c.WRAPPER/'evidence'/job['out']
                    entry['rows'] = [compare.load(job) for job in jobs]
                except (AssertionError, ValueError, OSError, KeyError) as error:
                    entry['error'] = str(error)
                    # Retain rates/drift even when a completed receipt fails quality.
                    entry['raw_rates'] = diagnostic_rates(roots)
                finally:
                    compare.view, compare.output = old_view, old_output
                entry['identities'] = identities
                brackets.append(entry)
                receipts[o.pin_path(path)] = o.sha(path)
                for root in roots:
                    for receipt in sorted(root.rglob('*.json')):
                        receipts[o.pin_path(receipt)] = o.sha(receipt)
    from v5_readiness import collect as collect_v5
    extra, rejected, pins = collect_v5(expected)
    brackets.extend(extra)
    excluded.extend(rejected)
    receipts.update(pins)
    return brackets, excluded, receipts


def evaluate(brackets, levers):
    """No bracket is dropped; A is universal, B needs a win and has a veto."""
    from compare import compare
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    reports = []
    acceptance = None
    for bracket in brackets:
        report = copy.deepcopy(bracket)
        report.update(qualified=False, below_both=False, control_drift_percent=None)
        rows = report.get('rows', [])
        rates = [r.get('rate') for r in rows] if rows else report.get('raw_rates', [])
        v5 = report.get('wrapper') == 'v5'
        order = ('control', 'candidate', 'control', 'candidate', 'control') if v5 else ('control', 'candidate', 'control')
        if len(rates) == len(order) and all(isinstance(rate, (int, float)) and
                                   math.isfinite(rate) and rate > 0 for rate in rates):
            controls, candidates = rates[::2], rates[1::2]
            ratio = min(candidates)/max(controls)
            report.update(control_drift_percent=100*(max(controls)/min(controls)-1) if v5 else 100*(controls[-1]/controls[0]-1),
                          ratio=ratio, gain_percent=100*(ratio-1),
                          below_both=any(candidate < min(controls[i:i+2])
                                         for i, candidate in enumerate(candidates)))
            if v5:
                report.update(candidate_ratios=[rate/max(controls) for rate in candidates],
                              ratio_definition='slower candidate divided by maximum of all three controls')
        try:
            assert not report.get('error'), report.get('error')
            compare(rows, order=order)
            assert all(r['lane'] == report['lane'] for r in rows), 'bracket lane differs'
            assert all(r['boot_id'] == boot for r in rows), 'stale composition boot'
            if acceptance is None:
                acceptance = rows[0]['acceptance_counts']
            assert rows[0]['acceptance_counts'] == acceptance, 'cross-bracket acceptance changed'
            report['qualified'] = report['ratio'] >= 1.005
        except (AssertionError, ValueError, KeyError, IndexError) as error:
            report['error'] = str(error)
        reports.append(report)
    lanes = {lane: [r for r in reports if r['lane'] == lane] for lane in ('A', 'B')}
    a_pass = bool(lanes['A']) and all(r['qualified'] for r in lanes['A'])
    b_pass = (any(r['qualified'] for r in lanes['B']) and
              all(not r['below_both'] and not r.get('error') for r in lanes['B']))
    # Conservative minimum qualifying gain on each lane, never an average or
    # an addition of source gains. All B non-wins remain visible above.
    ratios = {lane: min((r['ratio'] for r in rows if r['qualified']), default=0.)
              for lane, rows in lanes.items()}
    passed = a_pass and b_pass
    chain = passed and o.chain_policy(ratios, levers)
    reason = ('lane A requires every identical bracket exact, unchanged and >=+0.5%' if not a_pass
              else 'lane B requires a >=+0.5% bracket, unchanged quality and no loss to both controls' if not b_pass
              else 'chain policy needs >=1.5% on both lanes or >=2 qualified selected sources' if not chain
              else None)
    return dict(passed=passed, chain_policy_passed=chain, reason=reason,
                brackets=reports, ratios=ratios, lane_passed={'A': a_pass, 'B': b_pass},
                ratio_definition='minimum qualifying bracket gain over stronger control per lane',
                confirmed_levers=levers)


def matched(config):
    brackets, excluded, receipts = collect(config)
    return dict(evaluate(brackets, config['confirmed_levers']),
                excluded_brackets=excluded, receipts=receipts)


def preparation_config(config, decision):
    # A new CPU preparation binds both the historical evidence and current
    # evaluator, without rewriting the decision or any sealed selection.
    pins = preserved_pins(config)
    for path in [decision, *o.O.glob('*.py')]:
        pins[o.pin_path(path)] = o.sha(path)
    return dict(config, evidence_pins=pins)


def verify(row):
    assert row['schema'] == 'packet97.ready.v1', 'readiness schema differs'
    assert row['ready'] is True and row['preparation_passed'] is True, 'CPU preparation incomplete'
    assert row['device_executed'] is False and row['evidence_rule'] == RULE
    if row.get('chain_entry')=='packet97e':
        from fresh_chain import command, startup
        assert row['chain_command']==command(row['chain_output'])
        assert json.loads((o.P/'chain-registration.json').read_text())['output']==row['chain_output']
        startup()
    else:
        assert row['chain_command'] == o.command()
    assert row['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert set(row['checks']) == {'cpu-dry-run', 'seal', 'inputs', 'storage', 'queue-plan'}
    for key, digest in row['pins'].items():
        assert o.sha(o.ROOT/key) == digest, key
    for key, digest in row['checks'].items():
        assert o.sha(o.O/(key+'.log')) == digest, key
    decision = o.ROOT/row['decision']
    assert o.sha(decision) == row['decision_sha256'], 'decision changed'
    config = json.loads(decision.read_text())
    validate(config)
    assert row['selection'] == config['candidate']
    assert row['qualified_sources'] == config['confirmed_levers']
    assert json.loads((o.P/'composition-selection.json').read_text()) == preparation_config(config, decision), 'prepared selection or evaluator pins changed'
    result = matched(config)
    assert result == row['composition'] and result['passed'] and result['chain_policy_passed'], 'identical-selection evidence changed or failed'
    assert not (o.P/'build'/row.get('chain_output','device-cards01-a')).exists(), 'chain already started'
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decision', type=Path, required=True)
    parser.add_argument('--snapshot-only', action='store_true')
    parser.add_argument('--chain-output', help='Fresh directory for the unchanged decision; e.g. device-cards01-b')
    args = parser.parse_args()
    o.limits()
    decision = args.decision.resolve()
    row = dict(schema='packet97.ready.v1', evidence_rule=RULE, ready=False,
               composition_ready=False, device_executed=False,
               boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
               chain_command=o.command(), decision=o.pin_path(decision))
    try:
        if args.chain_output:
            from fresh_chain import command
            row.update(chain_entry='packet97e',chain_output=args.chain_output,chain_command=command(args.chain_output))
        config = json.loads(decision.read_text())
        assert decision.stem == c.identity(config), 'decision filename identity differs'
        validate(config)
        row.update(decision_sha256=o.sha(decision), selection=config['candidate'],
                   qualified_sources=config['confirmed_levers'], composition_ready=True)
        if args.snapshot_only:
            raise ValueError('snapshot only; no preparation changed')
        row['composition'] = matched(config)
        assert row['composition']['chain_policy_passed'], row['composition']['reason']
        if args.chain_output:
            from fresh_chain import prepare
            o.save(o.P/'composition-selection.json', preparation_config(config, decision))
            chain_output=prepare(config,args.chain_output)
        else:
            from stopped_archive import require_fresh_chain
            require_fresh_chain(o.P/'build')
            o.save(o.P/'composition-selection.json', preparation_config(config, decision))
            o.run('composition-queue-plan', [o.P/'queue_plan.py'])
            o.run('reseal', [o.P/'fast_reseal.py', *[x for k, v in config['candidate'].items() for x in ('--'+k, v)]])
            chain_output=o.P/'build/device-cards01-a'
        checks = [('cpu-dry-run', [o.P/'dry_run.py']), ('seal', [o.P/'chain_seal.py', '--verify']),
                  ('inputs', [o.P/'check_inputs.py']), ('storage', [o.P/'storage_precheck.py']),
                  ('queue-plan', [*([o.P/'chain97e.py','queue'] if args.chain_output else [o.P/'queue_runner.py']), '--plan', '--output-root', chain_output])]
        for label, argv in checks:
            o.run(label, argv)
        row['checks'] = {label: o.sha(o.O/(label+'.log')) for label, _ in checks}
        files = [o.P/leaf for leaf in ('build-receipt.json', 'bundle-selection.json', 'submission-pins.json',
                 'screen-jobs-seal.json', 'composition-selection.json', 'evidence/dry-run.json', 'evidence/selection-dry-run.json')]
        files += [*o.O.glob('*.py'), * (o.O/'frozen97b').glob('*.py'), o.O/'device-entry.sh', decision]
        row['pins'] = {o.pin_path(path): o.sha(path) for path in files}
        row.update(preparation_passed=True, ready=True)
        verify(row)
        row['reason'] = 'identical-selection evidence and all CPU readiness checks passed'
    except (ValueError, OSError, AssertionError, KeyError, subprocess.SubprocessError) as error:
        row.update(ready=False, reason=str(error))
    o.save(o.O/'ready.json', row)
    print(json.dumps({key: row.get(key) for key in ('ready', 'reason', 'selection')}, indent=2))
    return 0 if row['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
