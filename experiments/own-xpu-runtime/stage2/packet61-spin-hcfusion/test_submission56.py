"""CPU-only synthetic evidence tests; never touches devices or shared pins."""
import json
from pathlib import Path
import sys

import pytest

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/tests'))
sys.path.insert(0, str(P))
import packet56_submission as p
from test_packet49_submission import fixture, put


def prefix_fixture():
    e = fixture(p.TEMPLATE_PACKET)
    seal = e.read('seal.json')
    seal['schema'] = 'packet61.chain-cpu-seal.v1'
    seal['runtime_revision'] = 'a' * 40
    seal['device_executed'] = False
    seal['device_admission_ready'] = True
    seal['sources'] = {k.replace(p.TEMPLATE_PACKET, p.P56_PACKET): v for k, v in seal['sources'].items()}
    hashes = {}
    for key, leaf, value in [
        ('selection.json', 'selection.json', {'selected': 'inherited'}),
        ('draft-prefix-selection.json', 'calibration/selection.json', {'N': 91392}),
        ('draft-prefix-config.hpp', 'p56_config.hpp', b'constexpr unsigned prefix = 91392;\n')]:
        hashes[key] = put(e, key, value)
        seal['sources'][str(p.STAGE / p.P56_PACKET / leaf)] = hashes[key]
    screen_hash = put(e, 'screen-seal.json', {'artifacts': {'build/device/own-rt-iq3': seal['artifacts_sha256']['device/own-rt-iq3']}})
    seal.update(screen_seal_sha256=screen_hash, controller_spin=p.SPIN, hc_fusion=p.HC_FUSION)
    sh = put(e, 'seal.json', seal)
    pin = dict(screen_seal_sha256=screen_hash, runtime_revision=seal['runtime_revision'], build_receipt_sha256=sh,
               selection_sha256=hashes['selection.json'],
               draft_prefix_selection_sha256=hashes['draft-prefix-selection.json'],
               draft_prefix_config_sha256=hashes['draft-prefix-config.hpp'])
    put(e, 'submission-pins.json', dict(schema='lab.packet49.submission-pins.v1', lineages={p.P56_PACKET: pin}))
    e.add('record-threshold.json', ROOT / p.THRESHOLD_FILE)
    for name in p.WINDOWS:
        w = e.read(name + '/window.json')
        w.update(screen_seal_sha256=screen_hash, controller_spin=p.SPIN, hc_fusion=p.HC_FUSION, schema='packet61.window.v1', build_receipt_sha256=sh,
                 selection_sha256=pin['selection_sha256'],
                 draft_prefix_selection_sha256=pin['draft_prefix_selection_sha256'],
                 draft_prefix_config_sha256=pin['draft_prefix_config_sha256'])
        for leaf in list(w['receipts']):
            if (leaf == 'host-reference-identity.json'
                    or leaf in ('owner0/receipt.json', 'owner1/receipt.json')
                    or leaf.endswith(('/rank0/receipt.json', '/rank1/receipt.json'))):
                native = e.read(name + '/' + leaf)
                native['selection_sha256'] = pin['selection_sha256']
                w['receipts'][leaf] = put(e, name + '/' + leaf, native)
        if name == 'WS128':
            w['exactness_companion']['sha256'] = p.sha(e.raw('WS128x/window.json'))
        put(e, name + '/window.json', w)
    return e


def test_complete_synthetic_chain_and_current_floor():
    result = p.derive(prefix_fixture(), p.P56_PACKET)
    assert result['packet'] == p.P56_PACKET
    assert result['comparison']['threshold_tok_s'] == p.validate_threshold(
        json.loads((ROOT / p.THRESHOLD_FILE).read_bytes()))['threshold_tok_s']
    assert result['primary_metric']['value_tok_s'] == pytest.approx(51.25)
    assert result['realistic_final_gate']['passed'] is False


@pytest.mark.parametrize('key', ['draft-prefix-selection.json', 'draft-prefix-config.hpp'])
def test_changed_prefix_evidence_refused(key):
    e = prefix_fixture()
    put(e, key, {'tampered': True})
    with pytest.raises(ValueError, match='bound receipt hash mismatch'):
        p.derive(e, p.P56_PACKET)


def test_window_prefix_mismatch_refused():
    e = prefix_fixture()
    w = e.read('KD/window.json')
    w['draft_prefix_selection_sha256'] = '0' * 64
    put(e, 'KD/window.json', w)
    with pytest.raises(ValueError, match='window prefix identity mismatch'):
        p.derive(e, p.P56_PACKET)


def test_current_threshold_required():
    e = prefix_fixture()
    del e.members['record-threshold.json']
    with pytest.raises(ValueError, match='requires current pinned record threshold'):
        p.derive(e, p.P56_PACKET)


def test_pin_writer_is_local_and_preserves_existing_entries(tmp_path):
    e = prefix_fixture()
    d = tmp_path / p.STAGE / p.P56_PACKET
    (d / 'calibration').mkdir(parents=True)
    for key, leaf in [('seal.json', 'build-receipt.json'), ('selection.json', 'selection.json'),
                      ('draft-prefix-selection.json', 'calibration/selection.json'),
                      ('draft-prefix-config.hpp', 'p56_config.hpp')]:
        (d / leaf).write_bytes(e.raw(key))
    old = dict(schema='lab.packet49.submission-pins.v1', lineages={p.D_PACKET: {'retained': True}})
    (tmp_path / p.PINS_FILE).write_bytes(p.encoded(old))
    pin = p.pin_resealed_packet56(repo=tmp_path)
    after = json.loads((tmp_path / p.PINS_FILE).read_bytes())
    assert after['lineages'][p.D_PACKET] == old['lineages'][p.D_PACKET]
    assert pin['draft_prefix_selection_sha256'] == p.sha(e.raw('draft-prefix-selection.json'))
    assert not (tmp_path / 'scripts/packet49_submission_pins.json').exists()


def test_prepared_queue_replays_current_pins_and_refuses_changed_pin(tmp_path):
    e = prefix_fixture()
    for leaf, key in [(p.PINS_FILE, 'submission-pins.json'), (p.THRESHOLD_FILE, 'record-threshold.json')]:
        path = tmp_path / leaf
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(e.raw(key))
    out = tmp_path / p.STAGE / p.P56_PACKET / 'submission/prepared'
    result = p.write_prepared(e, p.P56_PACKET, out, tmp_path)
    item = json.loads((out / 'payload-queue.json').read_bytes())[0]
    assert p.scope_problems(item, tmp_path) == []
    from submission_cli import load_submitter
    cli = load_submitter()
    cli.REPO_ROOT = tmp_path
    assert cli.preflight_payload(item) == []
    pins = json.loads((tmp_path / p.PINS_FILE).read_bytes())
    pins['lineages'][p.P56_PACKET]['build_receipt_sha256'] = '0' * 64
    (tmp_path / p.PINS_FILE).write_bytes(p.encoded(pins))
    assert p.scope_problems(item, tmp_path)
    assert cli.preflight_payload(item)
    assert p.replay_result(result, tmp_path)['packet'] == p.P56_PACKET


def test_posting_rechecks_advanced_record_floor_but_historical_replay_survives(tmp_path):
    e = prefix_fixture()
    for leaf, key in [(p.PINS_FILE, 'submission-pins.json'), (p.THRESHOLD_FILE, 'record-threshold.json')]:
        path = tmp_path / leaf
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(e.raw(key))
    out = tmp_path / p.STAGE / p.P56_PACKET / 'submission/prepared'
    result = p.write_prepared(e, p.P56_PACKET, out, tmp_path)
    item = json.loads((out / 'payload-queue.json').read_bytes())[0]
    from submission_cli import load_submitter
    cli = load_submitter()
    cli.REPO_ROOT = tmp_path
    assert cli.preflight_payload(item) == []
    threshold = json.loads((tmp_path / p.THRESHOLD_FILE).read_bytes())
    threshold['records'].append(dict(reference_submission='synthetic-new-record', threshold_tok_s=52,
                                     result=dict(path='synthetic/result.json', sha256='0' * 64)))
    (tmp_path / p.THRESHOLD_FILE).write_bytes(p.encoded(threshold))
    assert any('current pinned record threshold' in problem for problem in p.scope_problems(item, tmp_path))
    assert cli.preflight_payload(item)
    assert p.replay_result(result, tmp_path)['primary_metric']['value_tok_s'] == pytest.approx(51.25)


def test_payload_names_both_prefix_and_spin_changes(tmp_path):
    result = p.derive(prefix_fixture(), p.P56_PACKET)
    item = p.payload_for(result, {'path': 'r', 'sha256': 'a'}, {'path': 'a', 'sha256': 'b'}, 'doc')
    notes = item['payload']['notes']
    assert '91,392' in notes and 'Controller spin' in notes and '250 us' in notes
    assert 'queue profiling' in notes and 'unchanged full target verifies' in notes
    assert 'Packet60 HC fusion' in notes and 'three exact-order kernels per side' in notes


def test_screen_seal_tampering_refused():
    e = prefix_fixture()
    put(e, 'screen-seal.json', {'artifacts': {'build/device/own-rt-iq3': '0'*64}})
    with pytest.raises(ValueError, match='bound receipt hash mismatch'):
        p.derive(e, p.P56_PACKET)


def test_spin_window_mismatch_refused():
    e = prefix_fixture()
    w = e.read('KD/window.json')
    w['screen_seal_sha256'] = '0'*64
    put(e, 'KD/window.json', w)
    with pytest.raises(ValueError, match='spin window identity mismatch'):
        p.derive(e, p.P56_PACKET)


def test_hc_fusion_window_mismatch_refused():
    e = prefix_fixture()
    row = e.read('KD/window.json')
    row['hc_fusion'] = dict(p.HC_FUSION, kernels_per_side=1)
    put(e, 'KD/window.json', row)
    with pytest.raises(ValueError, match='HC fusion window identity mismatch'):
        p.derive(e, p.P56_PACKET)
