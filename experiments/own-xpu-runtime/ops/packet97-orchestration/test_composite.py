"""Review-14 source admission, immutable proposals and non-additive fallback."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
import composite_jobs as c
import orchestrate as o
import source_adapter as adapter
from test_orchestrate import screens, winner, all_winners


def one_lane(choice, lane='B', rate=10.2):
    result = winner(choice, rate)
    other = 'A' if lane == 'B' else 'B'
    result['lanes'].pop(other)
    result['ratios'].pop(other)
    return result


def configuration():
    source = all_winners()
    control, candidate, qualified = o.select(source)
    return o.composition(source, control, candidate, qualified, {}, {})


@pytest.mark.parametrize('lane', ['A', 'B'])
def test_first_lane_qualifies_without_pending_sources(lane):
    source = {n: dict(status='pending') for n in o.DIMENSIONS}
    source['93'] = one_lane('head-transpose', lane)
    control, candidate, qualified = o.select(source)
    config = o.composition(source, control, candidate, qualified, {}, {})
    assert config['confirmed_levers'] == ['93']
    assert len(config['deferred_sources']) == 5
    assert config['source_ratios'] == {'93': {lane: 1.02}}
    assert control == o.DEFAULTS


@pytest.mark.parametrize('changes,exception', [
    ({'passed': False}, FileNotFoundError),
    ({'passed': False, 'child_still_running': True}, FileNotFoundError),
    ({'passed': False, 'stop_reasons': ['bad identity']}, ValueError),
    ({'passed': False, 'child_retained': True}, ValueError),
    ({'passed': False, 'report_failed': True}, ValueError),
])
def test_incomplete_not_failed_but_real_failures_are_rejected(changes, exception):
    with pytest.raises(exception):
        adapter.require_finished(changes, Path('/evidence/p91-A-grid-4-control'))


def test_leave_one_out_keeps_other_expert_and_removes_packet91_as_one_source():
    config = configuration()
    views = c.variants(config, True)
    assert len(views) == 6
    assert views['without-90']['experts'] == 'wide64+grid-prefetch'
    assert views['without-95']['experts'] == 'wide64+halfcache'
    assert views['without-91']['route'] == 'production'
    assert views['without-91']['recurrence'] == 'rec-parallel'
    assert views['without-91']['head'] == 'head-transpose'
    for lane in ('A', 'B'):
        for variant, choice in views.items():
            jobs = c.jobs(config, lane, variant)
            assert [job['selection'] for job in jobs] == [o.DEFAULTS, choice, o.DEFAULTS]
            assert len({job['out'] for job in jobs}) == 3


@pytest.mark.parametrize('ratios,best,required', [
    ({'A': 1.006, 'B': 1.007}, 1.008, True),
    ({'A': 1.0049, 'B': 1.02}, 1.002, True),
    ({'A': 1.005, 'B': 1.005}, 1.005, False),
    ({'A': 1.01, 'B': 1.02}, 1.009, False),
    ({'A': .999, 'B': 1.02}, 1.002, True),
])
def test_fallback_thresholds(ratios, best, required):
    config = dict(source_ratios={'93': {'B': best}})
    assert c.leave_one_out_required(ratios, config)['required'] is required


def test_decision_and_output_identity_change_with_qualified_set():
    config = configuration()
    changed = copy.deepcopy(config)
    changed['candidate']['head'] = 'production'
    changed['confirmed_levers'].remove('93')
    assert c.identity(config) != c.identity(changed)
    assert c.jobs(config, 'A')[1]['out'] != c.jobs(changed, 'A')[1]['out']


@pytest.mark.parametrize('mutation', [
    lambda config: config['candidate'].update(head='production'),
    lambda config: config['qualified_screens'].pop('91'),
    lambda config: config['confirmed_levers'].remove('93'),
])
def test_decision_cannot_claim_an_unqualified_or_omitted_choice(mutation):
    config = configuration()
    c.check_selection(config)
    mutation(config)
    with pytest.raises(AssertionError):
        c.check_selection(config)


def test_generation_only_plans_temporary_queues(tmp_path, monkeypatch):
    config = configuration()
    queue = tmp_path/'lane-queue'
    ops = tmp_path/'ops'
    queue.mkdir(); ops.mkdir()
    live = queue/'queue-A.txt'
    live.write_text('live queue must not change\n')
    monkeypatch.setattr(c, 'O', ops)
    monkeypatch.setattr(c, 'QUEUE', queue)
    monkeypatch.setattr(c, 'ROOT', tmp_path)
    monkeypatch.setattr(c, 'WRAPPER', tmp_path/'wrapper')
    monkeypatch.setattr(c, 'validate', lambda config: None)
    commands = []
    def plan(argv, **kwargs):
        directory = Path(argv[argv.index('--directory')+1])
        assert directory != queue
        assert kwargs['stdin'] == c.subprocess.DEVNULL
        commands.append(argv)
        return SimpleNamespace(returncode=0, stdout='CPU plan passed\n', stderr='')
    monkeypatch.setattr(c.subprocess, 'run', plan)
    result = c.generate(config)
    assert len(commands) == 2 and result['live_queue_modified'] is False
    assert [p['jobs'] for p in result['plans']] == [3, 3]
    result = c.generate(config, True)
    assert [p['jobs'] for p in result['plans']] == [18, 18]
    assert live.read_text() == 'live queue must not change\n'
    row = json.loads((queue/'proposed-p97-composite-A.txt').read_text().splitlines()[1])
    decision = Path(row['argv'][row['argv'].index('--decision')+1])
    assert row['argv'][row['argv'].index('--decision-sha256')+1] == c.sha(decision)


def test_weak_composite_emits_fallback_and_never_reseals(tmp_path, monkeypatch):
    import read_screens
    monkeypatch.setattr(o, 'O', tmp_path)
    monkeypatch.setattr(o, 'limits', lambda: None)
    monkeypatch.setattr(read_screens, 'collect', all_winners)
    calls = []
    monkeypatch.setattr(c, 'prepare_proposals', lambda config, leave_one_out=False: calls.append(leave_one_out))
    monkeypatch.setattr(o, 'matched_composition', lambda config: dict(
        passed=False, chain_policy_passed=False, leave_one_out=dict(required=True)))
    monkeypatch.setattr(o, 'run', lambda *args: pytest.fail('must not prepare record chain'))
    monkeypatch.setattr(sys, 'argv', ['orchestrate.py'])
    assert o.main() == 2 and calls == [False, True]
    assert json.loads((tmp_path/'ready.json').read_text())['ready'] is False


def test_composite_needs_both_exact_lanes(monkeypatch):
    # Exercise the real composite comparator with realistic bracket metadata.
    config = configuration()
    rows = winner('candidate')['lanes']
    for lane_rows in rows.values():
        for row in lane_rows:
            row['choice'] = 'candidate' if row['choice'] == 'candidate' else 'control'
            row.update(all_13_exact=True, acceptance=.64, output='/nonexistent',
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    monkeypatch.setattr(c, 'read_brackets', lambda config: rows)
    assert o.matched_composition(config)['passed'] is True
    rows['B'][1]['exact_count'] = 12
    with pytest.raises((AssertionError, ValueError)):
        o.matched_composition(config)
    rows['B'][1]['exact_count'] = 13
    rows['B'][1]['acceptance_counts'] = [[63, 100]]
    with pytest.raises((AssertionError, ValueError)):
        o.matched_composition(config)
    rows.pop('B')
    with pytest.raises((AssertionError, KeyError)):
        o.matched_composition(config)


def test_resume_frozen_decision_does_not_reselect_new_sources(tmp_path, monkeypatch):
    import read_screens
    config = configuration()
    path = tmp_path/'decision.json'
    path.write_text(json.dumps(config))
    monkeypatch.setattr(o, 'O', tmp_path)
    monkeypatch.setattr(o, 'limits', lambda: None)
    monkeypatch.setattr(o, 'source_pins', lambda screens: config['evidence_pins'])
    monkeypatch.setattr(c, 'validate', lambda config: None)
    monkeypatch.setattr(read_screens, 'collect', lambda: pytest.fail('frozen decision must not poll new sources'))
    monkeypatch.setattr(sys, 'argv', ['orchestrate.py', '--decision', str(path), '--snapshot-only'])
    assert o.main() == 2
    result = json.loads((tmp_path/'ready.json').read_text())
    assert result['composition_ready'] is True and result['selection'] == config['candidate']


def test_ready_verifier_normalizes_partial_packet91_pin(tmp_path, monkeypatch):
    import verify_ready as v
    packet = tmp_path/'packet'
    packet.mkdir()
    monkeypatch.setattr(o, 'O', tmp_path)
    monkeypatch.setattr(v, 'O', tmp_path)
    monkeypatch.setattr(v, 'P', packet)
    monkeypatch.setattr(v, 'sha', lambda path: 'x')
    source = all_winners()
    control, choice, confirmed = o.select(source)
    choice, pins = o.apply_pins(choice, ['route=production'])
    config = o.composition(source, control, choice, confirmed, pins, {})
    result = dict(passed=True, chain_policy_passed=True, leave_one_out=dict(required=False))
    monkeypatch.setattr(v, 'matched_composition', lambda config: result)
    row = dict(schema='packet97.ready.v1', ready=True, preparation_passed=True,
        device_executed=False, chain_command=v.command(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        pins={'dummy': 'x'}, checks={k: 'x' for k in ('cpu-dry-run','seal','inputs','storage','queue-plan')},
        screens=source, qualified_sources=config['confirmed_levers'], coordinator_pins=pins,
        coordinator_closures={}, selection=config['candidate'], composition=result)
    (tmp_path/'ready.json').write_text(json.dumps(row))
    (packet/'composition-selection.json').write_text(json.dumps(config))
    assert v.verify()['ready'] is True


def test_started_bracket_is_evaluated_without_replanning_occupied_paths(tmp_path, monkeypatch):
    config = configuration()
    monkeypatch.setattr(c, 'O', tmp_path)
    monkeypatch.setattr(c, 'WRAPPER', tmp_path/'wrapper')
    decision = tmp_path/'decisions'/(c.identity(config)+'.json')
    decision.parent.mkdir()
    decision.write_text(json.dumps(config))
    output = c.WRAPPER/'evidence'/c.jobs(config, 'A')[0]['out']
    output.mkdir(parents=True)
    monkeypatch.setattr(c, 'generate', lambda *a: pytest.fail('existing outputs cannot be planned again'))
    assert c.prepare_proposals(config)['already_started'] is True
