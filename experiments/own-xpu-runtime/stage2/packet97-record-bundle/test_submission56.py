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


def prefix_fixture(placement='1', draft='draft-hc', miss='batch', experts='wide64', dense='production', hc='hc-wide', host='ordered', route='production', norm='production',recurrence='rec-parallel',draft_head='production',head='production',hc_norm='production'):
    e = fixture(p.TEMPLATE_PACKET, speed=65)
    seal = e.read('seal.json')
    seal['schema'] = 'packet97.chain-cpu-seal.v1'
    seal['runtime_revision'] = 'a' * 40
    seal['device_executed'] = False
    seal['device_admission_ready'] = True
    seal['sources'] = {k.replace(p.TEMPLATE_PACKET, p.P56_PACKET): v for k, v in seal['sources'].items()}
    hashes = {}
    for key, leaf, value in [
        ('selection.json', 'selection.json', __import__('bundle_selection').selection((dense,hc,experts,host,route,norm,recurrence,draft_head,head,hc_norm))),
        ('draft-prefix-selection.json', 'calibration/selection.json', {'N': 91392}),
        ('draft-prefix-config.hpp', 'p56_config.hpp', b'constexpr unsigned prefix = 91392;\n')]:
        hashes[key] = put(e, key, value)
        seal['sources'][str(p.STAGE / p.P56_PACKET / leaf)] = hashes[key]
    screen_hash = put(e, 'screen-seal.json', {'artifacts': {'build/device/own-rt-iq3': seal['artifacts_sha256']['device/own-rt-iq3']}})
    seal.update(screen_seal_sha256=screen_hash, controller_spin=p.SPIN, hc_fusion=p.HC_FUSION)
    dr,split,boundary=__import__('bundle_selection').PLACEMENTS[placement]
    bundle=dict(dense=dense,hc=hc,experts=experts,host=host,route=route,norm=norm,recurrence=recurrence,draft_head=draft_head,head=head,hc_norm=hc_norm,name=__import__('bundle_selection').name(dense,hc,experts,host,route,norm,recurrence,draft_head,head,hc_norm),placement=placement,draft=draft,miss=miss,draft_rank=dr,target_split=split,layer_boundary=boundary,selection_sha256=hashes['selection.json'],screen_seal_sha256=screen_hash)
    from draft_identity import identity
    seal['draft_prefix']=identity(bundle)
    e.add('draft-head-coverage.json',P/'coverage.json');e.add('draft-head-config.hpp',P/'p83_head.hpp')
    seal['sources'][str(p.STAGE/p.P56_PACKET/'p83_head.hpp')]=p.sha(e.raw('draft-head-config.hpp'))
    seal['hc_fusion']=p.selected_hc_fusion(bundle)
    seal['bundle_selection']=bundle
    seal['sources'][str(p.STAGE/p.P56_PACKET/'bundle-selection.json')]=put(e,'bundle-selection.json',bundle)
    sh = put(e, 'seal.json', seal)
    pin = dict(screen_seal_sha256=screen_hash, runtime_revision=seal['runtime_revision'], build_receipt_sha256=sh,
               selection_sha256=hashes['selection.json'],
               draft_prefix_selection_sha256=hashes['draft-prefix-selection.json'],
               draft_prefix_config_sha256=hashes['draft-prefix-config.hpp'])
    put(e, 'submission-pins.json', dict(schema='lab.packet49.submission-pins.v1', lineages={p.P56_PACKET: pin}))
    e.add('record-threshold.json', ROOT / p.THRESHOLD_FILE)
    for name in p.WINDOWS:
        w = e.read(name + '/window.json')
        w.update(draft_rank=dr,target_split=split,draft_vocab_rows=seal['draft_prefix']['draft_vocab_rows'],screen_seal_sha256=screen_hash, controller_spin=p.SPIN, hc_fusion=p.selected_hc_fusion(bundle), schema='packet97.window.v1', build_receipt_sha256=sh,
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
        for leaf in list(w['receipts']):
            key=name+'/'+leaf
            if key in e.members and leaf.endswith('receipt.json'):
                native=e.read(key)
                if 'target_split' in native:
                    native['target_split']=split;w['receipts'][leaf]=put(e,key,native)
        if name == 'WS128':
            w['exactness_companion']['sha256'] = p.sha(e.raw('WS128x/window.json'))
        from window_adapter import receipt_digest
        from lane_admission import window_scope
        scope=window_scope(name)
        w['timing_claim_eligible']=scope=='whole-host'
        proof=dict(schema='own-runtime.chain-admission.v1',passed=True,window=name,scope=scope,
            timing_claim_eligible=scope=='whole-host',coordination=dict(boot_id=w['boot_id']),
            owners={str(pid):dict(seen=True,exited=True) for pid in w['launched_pids']},ready_checks=1,
            window_receipt_sha256_without_admission=receipt_digest(w))
        proof_hash=put(e,name+'/lane-admission.json',proof)
        w['lane_admission']=dict(passed=True,path='/synthetic/'+name+'-lane-admission.json',sha256=proof_hash,scope=scope)
        put(e, name + '/window.json', w)
    return e


def test_complete_synthetic_chain_and_current_floor():
    result = p.derive(prefix_fixture(), p.P56_PACKET)
    assert result['packet'] == p.P56_PACKET
    assert result['comparison']['threshold_tok_s'] == p.validate_threshold(
        json.loads((ROOT / p.THRESHOLD_FILE).read_bytes()))['threshold_tok_s']
    assert result['primary_metric']['value_tok_s'] == pytest.approx(71.25)
    assert result['realistic_final_gate']['passed'] is False


@pytest.mark.parametrize('config', __import__('bundle_selection').configurations())
def test_all_bundle_payloads_are_placement_and_selection_aware(config):
    name,v,placement=config
    dense,hc,experts,host,route,norm,recurrence,draft_head,head,hc_norm=v
    result=p.derive(prefix_fixture(placement=placement,dense=dense,hc=hc,experts=experts,host=host,route=route,norm=norm,recurrence=recurrence,draft_head=draft_head,head=head,hc_norm=hc_norm),p.P56_PACKET)
    payload=p.payload_for(result,{'path':'r','sha256':'a'},{'path':'a','sha256':'b'},'doc')['payload']
    dr,split,boundary=__import__('bundle_selection').PLACEMENTS[placement]
    assert payload['engineFlags']['targetSplit']==[boundary,48-boundary]
    assert payload['engineFlags']['draftRank']==dr
    assert payload['engineFlags']['targetHCFusion']['kernels_per_side']==(2 if hc_norm=='normfuse' else 3)
    assert payload['engineFlags']['packet97Changes']['head']==head
    if head=='head-transpose':assert 'separate unchanged expanded' in payload['notes']
    for key,value in dict(dense=dense,HC=hc,experts=experts,host=host,route=route,norm=norm,Placement=placement).items():
        assert f'{key}={value}' in payload['notes']
    assert len(payload['notes'])<=2000
    assert len(p.submission_notes(result['bundle_selection'],resumed=True))<=2000


def test_bundle_selection_and_admission_tampering_refuse():
    for name in ('bundle-selection.json','WS128/lane-admission.json'):
        evidence=prefix_fixture()
        put(evidence,name,{'tampered':True})
        with pytest.raises(ValueError):p.derive(evidence,p.P56_PACKET)


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
    with pytest.raises(ValueError, match='different window receipt|window prefix identity mismatch'):
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
    threshold['records'].append(dict(reference_submission='synthetic-new-record', threshold_tok_s=72,
                                     result=dict(path='synthetic/result.json', sha256='0' * 64)))
    (tmp_path / p.THRESHOLD_FILE).write_bytes(p.encoded(threshold))
    assert any('current pinned record threshold' in problem for problem in p.scope_problems(item, tmp_path))
    assert cli.preflight_payload(item)
    assert p.replay_result(result, tmp_path)['primary_metric']['value_tok_s'] == pytest.approx(71.25)


def test_payload_names_both_prefix_and_spin_changes(tmp_path):
    result = p.derive(prefix_fixture(), p.P56_PACKET)
    item = p.payload_for(result, {'path': 'r', 'sha256': 'a'}, {'path': 'a', 'sha256': 'b'}, 'doc')
    notes = item['payload']['notes']
    assert '91,392' in notes and 'PAUSE spin' in notes and '256' in notes
    assert 'profiling' in notes and 'Unchanged full target verifies' in notes
    assert item['payload']['engineFlags']['targetHCFusion']['kernels_per_side']==3
    assert 'HC consumer norm uses two kernels per side when selected' in notes


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
    with pytest.raises(ValueError, match='different window receipt|spin window identity mismatch'):
        p.derive(e, p.P56_PACKET)


def test_hc_fusion_window_mismatch_refused():
    e = prefix_fixture()
    row = e.read('KD/window.json')
    row['hc_fusion'] = dict(p.HC_FUSION, kernels_per_side=1)
    put(e, 'KD/window.json', row)
    with pytest.raises(ValueError, match='different window receipt|HC fusion window identity mismatch'):
        p.derive(e, p.P56_PACKET)


def test_old_wait_policy_window_refused():
    e = prefix_fixture()
    row = e.read('KD/window.json')
    row['controller_spin'] = dict(budget_us=250, mailbox_fallback_us=100, device_fallback_us=1000,
                                  rank0_queue_profiling=True, timing_reads=False)
    put(e, 'KD/window.json', row)
    with pytest.raises(ValueError, match='different window receipt|spin window identity mismatch'):
        p.derive(e, p.P56_PACKET)


def test_sleep20_wait_policy_window_refused():
    e = prefix_fixture()
    row = e.read('KD/window.json')
    row['controller_spin'] = dict(p.SPIN, wait_policy='sleep20')
    put(e, 'KD/window.json', row)
    with pytest.raises(ValueError, match='different window receipt|spin window identity mismatch'):
        p.derive(e, p.P56_PACKET)


def test_registered_chain_and_prepared_resume_admission(tmp_path, monkeypatch):
    import resume_chain as resume
    source=tmp_path/'device-cards01-a'; target=tmp_path/'device-cards01-b'
    calls=[]
    monkeypatch.setattr(resume,'pins',lambda:dict(source=str(source)))
    def validate(a,b,*,prepared):
        calls.append((a,b,prepared))
        if b != target:raise ValueError('destination is not pinned')
    monkeypatch.setattr(resume,'validate',validate)
    assert p.admit_chain(source,source)==source
    assert calls==[]
    assert p.admit_chain(target,source)==target
    assert calls==[(source,target,True)]
    with pytest.raises(ValueError,match='not pinned'):
        p.admit_chain(tmp_path/'arbitrary',source)
    # Registered resume destinations still revalidate; registration cannot bypass imports.
    target.mkdir();(target/'resume-manifest.json').write_text('{}')
    assert p.admit_chain(target,target)==target
    assert calls[-1]==(source,target,True)


def test_resume_disclosure_binds_manifest_and_pins():
    e=prefix_fixture()
    pin_hash=put(e,'resume-pins.json',dict(reason='test'))
    manifest=dict(schema='packet97.resume-manifest.v1',source='a',destination='b',
        imported_windows=['K0','K1a','K1b','K2','W0p'],fresh_windows=list(p.WINDOWS),
        resume_pins_sha256=pin_hash,current_build_receipt_sha256=p.sha(e.raw('seal.json')),
        original_build_receipt_sha256='a'*64,artifacts_sha256=e.read('seal.json')['artifacts_sha256'],files={'K0/window.json':'a'*64})
    put(e,'resume-manifest.json',manifest)
    result=p.derive(e,p.P56_PACKET)
    payload=p.payload_for(result,{'path':'r','sha256':'a'},{'path':'a','sha256':'b'},'doc')['payload']
    assert payload['engineFlags']['chainResume']['imported_windows']==manifest['imported_windows']
    assert 'Resumed within this sealed packet' in payload['notes']
    assert len(payload['notes'])<=2000
    put(e,'resume-pins.json',dict(reason='tampered'))
    with pytest.raises(ValueError,match='resume manifest identity'):p.derive(e,p.P56_PACKET)
