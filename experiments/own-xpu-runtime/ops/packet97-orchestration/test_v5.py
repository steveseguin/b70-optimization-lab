"""Five-view gates, frozen-native refusals and exact identity boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import decision_readiness as d
import v5_jobs as j
import v5_readiness as r
from test_decision_readiness import BOOT, bracket


def five(lane, rates=(100., 101., 100., 101., 100.)):
    rows = [dict(choice=choice, rate=rate, lane=lane, exact=True, exact_count=13,
                 all_13_exact=True, acceptance=.64, acceptance_counts=[[64, 100]],
                 boot_id=BOOT, started_utc_ns=3*i+1, finished_utc_ns=3*i+2)
            for i, (choice, rate) in enumerate(zip(j.ORDER, rates))]
    return dict(wrapper='v5', lane=lane, rows=rows, shared_model_lifetime=True)


def test_both_candidate_repeats_against_maximum_of_all_controls():
    # Candidate 1 beats adjacent controls but loses to the final control.
    a = five('A', (100., 101., 100., 102., 101.2))
    result = d.evaluate([a, five('B')], ['91', '90'])
    assert not result['passed']
    assert result['brackets'][0]['ratio'] == pytest.approx(101/101.2)
    assert result['brackets'][0]['control_drift_percent'] == pytest.approx(1.2)
    # A strong first repeat must not hide a weak second repeat.
    assert not d.evaluate([five('A', (100., 103., 100., 100.4, 100.)), five('B')], ['91', '90'])['passed']
    assert d.evaluate([five('A'), five('B')], ['91', '90'])['passed']


@pytest.mark.parametrize('index', range(5))
@pytest.mark.parametrize('change', [dict(exact_count=12), dict(exact=False),
                                    dict(all_13_exact=False), dict(acceptance_counts=[[63, 100]]),
                                    dict(boot_id='stale'), dict(rate=float('nan'))])
def test_every_view_is_gated(index, change):
    a = five('A')
    a['rows'][index].update(change)
    assert not d.evaluate([a, five('B')], ['91', '90'])['passed']


def test_five_views_required_and_no_overlap():
    for a in (five('A'), five('A')):
        a['rows'].pop(2)
        assert not d.evaluate([a, five('B')], ['91', '90'])['passed']
    a = five('A')
    a['rows'][3]['started_utc_ns'] = a['rows'][2]['finished_utc_ns']
    assert not d.evaluate([a, five('B')], ['91', '90'])['passed']


def test_identical_selection_policy_and_chain_policy_survive():
    assert not d.evaluate([five('A')], ['91', '90'])['passed']
    assert not d.evaluate([five('A'), five('B')], ['91'])['chain_policy_passed']
    assert not d.evaluate([five('A'), five('B'), bracket('A', (100., 99., 100.))], ['91', '90'])['passed']
    assert not d.evaluate([five('A'), five('B'), five('B', (100., 102., 100., 99., 100.))], ['91', '90'])['passed']
    assert d.evaluate([five('A'), five('B'), bracket('B', (100., 100.8, 101.))], ['91', '90'])['passed']


def test_identity_does_not_pool_v4_and_v5_binaries_or_change_selection():
    expected = {label: {key: key for key in r.FIELDS} for label in ('control', 'candidate')}
    expected['control']['selection_sha256'] = 'control'
    expected['candidate']['selection_sha256'] = 'candidate'
    identity = dict(expected['control'], bracket=dict(views=[dict(choice=label, selection_sha256=label) for label in j.ORDER]))
    assert r.identity_matches(identity, expected)
    for key in r.FIELDS:
        changed = copy.deepcopy(identity)
        if key == 'selection_sha256':
            changed['bracket']['views'][3][key] = 'different'
        else:
            changed[key] = 'different'
        assert not r.identity_matches(changed, expected)


def test_collector_keeps_completed_failure_and_uses_validated_window_lane(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'V5', tmp_path)
    monkeypatch.setattr(r, 'ROOT', tmp_path)
    root = tmp_path/'evidence/bracket'
    root.mkdir(parents=True)
    expected = {label: {key: key for key in r.FIELDS} for label in ('control', 'candidate')}
    for label in expected:
        expected[label]['selection_sha256'] = label
    identity = dict(expected['control'], lane='invalid', bracket=dict(kind='bracket',
                    views=[dict(choice=label, selection_sha256=label) for label in j.ORDER]))
    (root/'identity.json').write_text(json.dumps(identity))
    window = dict(finished_utc_ns=10, lane='A')
    (root/'window.json').write_text(json.dumps(window))
    monkeypatch.setattr(r.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        returncode=1, stdout='', stderr='lane identity failed'))
    rows, excluded, pins = r.collect(expected)
    assert len(rows) == 1 and rows[0]['lane'] == 'A' and rows[0]['error']
    assert not excluded and len(pins) == 2
    assert not d.evaluate([*rows, five('A'), five('B')], ['91', '90'])['passed']
    window['lane'] = 'invalid'
    (root/'window.json').write_text(json.dumps(window))
    with pytest.raises(AssertionError, match='invalid completed v5 lane'):
        r.collect(expected)


def test_frozen_native_compatibility_and_layout_refusals():
    control = j.read(j.V5/'lineage/selection.json')
    candidate = j.read(j.V5/'lineage/candidate.json')
    assert not j.compatibility(control, candidate)
    for key, value, message in [('experts', 'wide64+halfcache', 'load-time layout'),
                                ('head', 'head-transpose', 'load-time layout'),
                                ('host_retire', 'reply-first', 'unqualified native switch'),
                                ('hc_norm', 'consumer', 'unqualified native switch')]:
        changed = copy.deepcopy(control)
        changed['choices'][key] = value
        assert any(message in reason for reason in j.compatibility(control, changed))
    candidate['draft']['qsa_attention'] = 'packet59'
    assert any('draft selection differs' in reason for reason in j.compatibility(control, candidate))


def test_registered_lineage_is_not_silently_substituted():
    row = dict(schema='packet98b.bracket-intent.v1', lane='A', record_lane='A', pins={},
               views=j.read(j.V5/'configs/bracket.json')['views'])
    assert j.admission(row)['admitted']
    changed = copy.deepcopy(row)
    changed['views'][3]['selection_sha256'] = 'wrong'
    with pytest.raises(AssertionError, match='selection changed'):
        j.admission(changed)


@pytest.mark.parametrize('lane', ['A', 'B'])
def test_registered_v5_pair_passes_real_plan_on_both_lanes(tmp_path, lane):
    # Positive control for the adapter; never relabel this packet91 pair as p97.
    row = dict(schema='packet98b.bracket-intent.v1', lane=lane, record_lane='A', pins={},
               views=j.read(j.V5/'configs/bracket.json')['views'])
    path = tmp_path/'registered.json'
    path.write_text(json.dumps(row))
    output = j.V5/'evidence'/('p98b-test-plan-only-'+lane)
    cp = subprocess.run([sys.executable, '-B', str(j.O/'v5_screen.py'), '--manifest', str(path),
                         '--manifest-sha256', j.sha(path), '--lane', lane, '--output', str(output), '--plan'],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    assert cp.returncode == 0, cp.stderr
    planned = json.loads(cp.stdout)
    assert planned['views'] == 5 and planned['target_loads'] == planned['teardown_count'] == 1
    assert planned['device_executed'] is False and not output.exists()


def test_requested_proposals_keep_exact_selection_and_refuse_before_launch(tmp_path, monkeypatch):
    import v5_screen
    manifest = j.manifest(j.STAGE/'packet100-down-locality/selections/production',
                          j.STAGE/'packet100-down-locality/selections/down-tile16', 'A', 'test')
    path = tmp_path/'intent.json'
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(v5_screen.subprocess, 'run', lambda *a, **k: pytest.fail('no child may start'))
    for plan in ([], ['--plan']):
        assert v5_screen.main(['--manifest', str(path), '--manifest-sha256', j.sha(path),
                               '--lane', 'A', '--output', str(tmp_path/'out'), *plan]) == 2
    assert not (tmp_path/'out').exists()


def test_composed_choice_gets_a_valid_queue_name(tmp_path):
    import re
    path = tmp_path/'p94-v5-hc-normfuse+weightcache-A.json'
    path.write_text(json.dumps(dict(lane='A')))
    row = j.job(path)
    assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,100}', row['name'])
    assert '-plus-' in row['name']


def test_real_smoke_readback_cpu_only():
    smoke = j.V5/'evidence/p98-smoke-B'
    if not (smoke/'window.json').exists():
        pytest.skip('host-local smoke evidence unavailable')
    cp = subprocess.run([sys.executable, '-B', str(j.O/'v5_evidence.py'), '--smoke', str(smoke)],
                        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    assert cp.returncode == 0, cp.stderr
    result = json.loads(cp.stdout)
    assert len(result['rows']) == 2 and all(row['exact_count'] == 13 for row in result['rows'])
