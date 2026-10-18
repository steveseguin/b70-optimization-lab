"""Packet97d: aggregate identities, universal A gate, B veto and drift receipts."""
import copy
import json
from pathlib import Path

import pytest
import decision_readiness as d
from test_composite import configuration

BOOT = Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def bracket(lane, rates=(100., 101., 100.), decision='one', variant='composite'):
    rows = [dict(choice=choice, rate=rate, lane=lane, exact=True, exact_count=13,
                 all_13_exact=True, acceptance=.64, acceptance_counts=[[64, 100]],
                 boot_id=BOOT, started_utc_ns=3*i+1, finished_utc_ns=3*i+2)
            for i, (choice, rate) in enumerate(zip(('control', 'candidate', 'control'), rates))]
    return dict(lane=lane, rows=rows, decision=decision, variant=variant)


def evidence():
    return [bracket('A', decision='earlier', variant='without-93'), bracket('A'),
            bracket('B', decision='earlier', variant='without-93'),
            bracket('B', (100., 100.8, 101.))]


def test_all_mixed_decision_brackets_and_drift_report():
    rows = evidence()
    result = d.evaluate(rows, ['91', '90'])
    assert result['passed'] and result['chain_policy_passed']
    assert len(result['brackets']) == 4
    assert result['brackets'][-1]['qualified'] is False
    assert result['brackets'][-1]['below_both'] is False
    assert result['brackets'][-1]['control_drift_percent'] == pytest.approx(1.)
    assert result['brackets'][-1]['gain_percent'] == pytest.approx(100*(100.8/101-1))
    assert rows == evidence()  # reporting does not mutate source evidence


@pytest.mark.parametrize('rates', [(100., 100.49, 100.), (100., 99., 101.)])
def test_one_failing_lane_a_blocks_even_with_another_win(rates):
    rows = evidence()
    rows.append(bracket('A', rates))
    result = d.evaluate(rows, ['91', '90'])
    assert not result['passed'] and len(result['brackets']) == 5


def test_lane_b_below_both_vetoes_other_wins():
    rows = evidence()
    rows.append(bracket('B', (100., 99.9, 101.)))
    result = d.evaluate(rows, ['91', '90'])
    assert not result['passed'] and result['brackets'][-1]['below_both']


@pytest.mark.parametrize('lane', ['A', 'B'])
@pytest.mark.parametrize('change', [dict(exact=False), dict(exact_count=12),
                                    dict(acceptance_counts=[[63, 100]]), dict(boot_id='stale')])
def test_invalid_quality_or_boot_never_hidden(lane, change):
    rows = evidence()
    next(b for b in rows if b['lane'] == lane)['rows'][1].update(change)
    result = d.evaluate(rows, ['91', '90'])
    assert not result['passed']
    assert any(b.get('error') for b in result['brackets'])
    assert all(b['control_drift_percent'] is not None for b in result['brackets'])


def test_b_needs_one_threshold_win_and_both_lanes_are_required():
    assert not d.evaluate([bracket('A')], ['91', '90'])['passed']
    assert not d.evaluate([bracket('A'), bracket('B', (100., 100.4, 100.))], ['91', '90'])['passed']
    assert d.evaluate([bracket('A', (100., 100.5, 100.)),
                       bracket('B', (100., 100.5, 100.))], ['91', '90'])['passed']


def test_original_chain_policy_remains_independent():
    assert not d.evaluate(evidence(), ['91'])['chain_policy_passed']
    assert d.evaluate([bracket('A', (100., 101.5, 100.)),
                       bracket('B', (100., 101.5, 100.))], ['91'])['chain_policy_passed']


@pytest.mark.parametrize('key', d.IDENTITY_FIELDS)
def test_every_identity_field_must_match(key):
    expected = {field: field+'-hash' for field in d.IDENTITY_FIELDS}
    assert d.identical(dict(expected), expected)
    changed = dict(expected, **{key: 'different'})
    assert not d.identical(changed, expected)
    changed.pop(key)
    assert not d.identical(changed, expected)


def test_collector_mixes_decisions_and_keeps_independent_completed_lanes(tmp_path, monkeypatch):
    import compare
    monkeypatch.setattr('v5_readiness.collect', lambda expected: ([], [], {}))
    config = configuration()
    # Earlier head-transpose composition has the selected composition as LOO.
    earlier = copy.deepcopy(config)
    config['candidate']['head'] = 'production'
    config['confirmed_levers'].remove('93')
    decisions = tmp_path/'decisions'
    decisions.mkdir()
    wrapper = tmp_path/'wrapper'
    monkeypatch.setattr(d.o, 'O', tmp_path)
    monkeypatch.setattr(d.c, 'WRAPPER', wrapper)
    monkeypatch.setattr(d, 'validate', lambda config: None)
    expected = {field: field+'-hash' for field in d.IDENTITY_FIELDS}
    monkeypatch.setattr(d, 'sealed_identity', lambda selection: expected)
    monkeypatch.setattr(compare, 'load', lambda job: bracket(job['lane'])['rows'][job['index']])
    for source, variant in [(earlier, 'without-93'), (config, 'composite')]:
        (decisions/(d.c.identity(source)+'.json')).write_text(json.dumps(source))
        for lane in ('A', 'B'):
            for job in d.c.jobs(source, lane, variant):
                root = wrapper/'evidence'/job['out']
                root.mkdir(parents=True)
                (root/'window.json').write_text(json.dumps(dict(finished_utc_ns=10)))
                (root/'identity.json').write_text(json.dumps(expected))
    rows, excluded, receipts = d.collect(config)
    assert len(rows) == 4 and not excluded and receipts
    assert {b['variant'] for b in rows} == {'composite', 'without-93'}
    # A non-identical selection hash cannot be pooled, even with equal choices.
    root = wrapper/'evidence'/d.c.jobs(earlier, 'B', 'without-93')[1]['out']
    (root/'identity.json').write_text(json.dumps(dict(expected, selection_sha256='different')))
    rows, excluded, _ = d.collect(config)
    assert len(rows) == 3 and len(excluded) == 1
    # Incomplete B does not hide the completed A bracket.
    root = wrapper/'evidence'/d.c.jobs(config, 'B')[2]['out']
    (root/'window.json').unlink()
    rows, _, _ = d.collect(config)
    assert len(rows) == 2 and all(b['lane'] == 'A' for b in rows)


def test_each_candidate_keeps_its_own_two_control_veto_in_extended_bracket():
    rows = []
    for i, rate in enumerate((100., 99., 100., 101., 90.)):
        row = copy.deepcopy(bracket('B')['rows'][i % 2])
        row.update(rate=rate, started_utc_ns=3*i+1, finished_utc_ns=3*i+2)
        rows.append(row)
    # The final, weaker control cannot erase the first candidate's loss to
    # both of its adjacent controls, even with another qualifying B bracket.
    result = d.evaluate([*evidence(), dict(lane='B', wrapper='v5', rows=rows)], ['91', '90'])
    assert not result['passed'] and result['brackets'][-1]['below_both']


def test_preserved_policy_bytes_only_and_no_arbitrary_hash_bypass(tmp_path, monkeypatch):
    monkeypatch.setattr(d.o, 'O', tmp_path)
    archive = tmp_path/'frozen97b'
    archive.mkdir()
    original = tmp_path/'orchestrate.py'
    original.write_text('new policy')
    (archive/'orchestrate.py').write_text('old policy')
    old_hash = d.o.sha(archive/'orchestrate.py')
    config = dict(evidence_pins={str(original): old_hash, '/runtime': 'unchanged'})
    pins = d.preserved_pins(config)
    assert pins == {str(archive/'orchestrate.py'): old_hash, '/runtime': 'unchanged'}
    assert config['evidence_pins'][str(original)] == old_hash
    (archive/'orchestrate.py').write_text('tampered')
    with pytest.raises(AssertionError, match='unrecognized historical policy'):
        d.preserved_pins(config)


def test_completed_invalid_bracket_retains_drift_and_blocks():
    rows = evidence()
    rows.append(dict(lane='B', decision='bad', error='target output mismatch',
                     raw_rates=[100., 100.8, 101.]))
    result = d.evaluate(rows, ['91', '90'])
    assert not result['passed']
    assert result['brackets'][-1]['control_drift_percent'] == pytest.approx(1.)
    assert result['brackets'][-1]['error'] == 'target output mismatch'


@pytest.mark.parametrize('failure', [None, 'cpu-dry-run', 'seal', 'inputs', 'storage', 'queue-plan', 'verify_ready'])
def test_all_cpu_checks_and_verify_ready_remain_mandatory(tmp_path, monkeypatch, failure):
    import sys
    config = configuration()
    decision = tmp_path/(d.c.identity(config)+'.json')
    decision.write_text(json.dumps(config))
    packet = tmp_path/'packet'
    packet.mkdir()
    monkeypatch.setattr(d.o, 'O', tmp_path)
    monkeypatch.setattr(d.o, 'P', packet)
    monkeypatch.setattr(d.o, 'limits', lambda: None)
    monkeypatch.setattr(d.o, 'sha', lambda path: 'bound-hash')
    monkeypatch.setattr(d, 'validate', lambda config: None)
    monkeypatch.setattr(d, 'matched', lambda config: dict(chain_policy_passed=True, reason=None))
    monkeypatch.setattr(d, 'preparation_config', lambda config, decision: config)
    calls = []
    def check(label, args):
        calls.append(label)
        if label == failure:
            raise ValueError(label+' failed')
    def verify(row):
        calls.append('verify_ready')
        if failure == 'verify_ready':
            raise ValueError('verify_ready failed')
    monkeypatch.setattr(d.o, 'run', check)
    monkeypatch.setattr(d, 'verify', verify)
    monkeypatch.setattr(sys, 'argv', ['orchestrate.py', '--decision', str(decision)])
    assert d.main() == (2 if failure else 0)
    row = json.loads((tmp_path/'ready.json').read_text())
    assert row['ready'] is (failure is None)
    if failure:
        assert row['reason'] == failure+' failed'
    else:
        assert calls == ['composition-queue-plan', 'reseal', 'cpu-dry-run', 'seal',
                         'inputs', 'storage', 'queue-plan', 'verify_ready']
