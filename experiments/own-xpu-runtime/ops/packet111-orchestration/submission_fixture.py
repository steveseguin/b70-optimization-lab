"""CPU-only synthetic evidence tests; never touches devices or shared pins."""
import json
from pathlib import Path
import sys

import pytest

P = Path(__file__).resolve().parents[2] / "stage2/packet111-record-bundle"
ROOT = P.parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'scripts/tests'))
sys.path.insert(0, str(P))
import submission_evidence as p
from test_packet49_submission import fixture, put


def prefix_fixture(placement='1', draft='draft-hc', miss='batch', experts='wide64+halfcache', dense='production', hc='hc-wide', host='ordered', route='fast', norm='production',recurrence='rec-both-plus',draft_head='production',head='production',hc_norm='production',down='tile16',draft_attention='split32',other_fusion='production',target_head='production'):
    e = fixture(p.TEMPLATE_PACKET, speed=65)
    seal = e.read('seal.json')
    seal['schema'] = 'packet103.chain-cpu-seal.v1'
    seal['runtime_revision'] = 'a' * 40
    seal['device_executed'] = False
    seal['device_admission_ready'] = True
    seal['sources'] = {k.replace(p.TEMPLATE_PACKET, p.P56_PACKET): v for k, v in seal['sources'].items()}
    hashes = {}
    for key, leaf, value in [
        ('selection.json', 'selection.json', __import__('bundle_selection').selection((dense,hc,experts,host,route,norm,recurrence,draft_head,head,hc_norm,down,draft_attention,other_fusion,target_head))),
        ('draft-prefix-selection.json', 'calibration/selection.json', {'N': 91392}),
        ('draft-prefix-config.hpp', 'p56_config.hpp', b'constexpr unsigned prefix = 91392;\n')]:
        hashes[key] = put(e, key, value)
        seal['sources'][str(p.STAGE / p.P56_PACKET / leaf)] = hashes[key]
    screen_hash = put(e, 'screen-seal.json', {'artifacts': {'build/device/own-rt-iq3': seal['artifacts_sha256']['device/own-rt-iq3']}})
    seal.update(screen_seal_sha256=screen_hash, controller_spin=p.SPIN, hc_fusion=p.HC_FUSION)
    dr,split,boundary=__import__('bundle_selection').PLACEMENTS[placement]
    bundle=dict(dense=dense,hc=hc,experts=experts,host=host,route=route,norm=norm,recurrence=recurrence,draft_head=draft_head,head=head,hc_norm=hc_norm,down=down,draft_attention=draft_attention,other_fusion=other_fusion,target_head=target_head,name=__import__('bundle_selection').name(dense,hc,experts,host,route,norm,recurrence,draft_head,head,hc_norm,down,draft_attention,other_fusion,target_head),placement=placement,draft=draft,miss=miss,draft_rank=dr,target_split=split,layer_boundary=boundary,selection_sha256=hashes['selection.json'],screen_seal_sha256=screen_hash)
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
        w.update(draft_rank=dr,target_split=split,draft_vocab_rows=seal['draft_prefix']['draft_vocab_rows'],screen_seal_sha256=screen_hash, controller_spin=p.SPIN, hc_fusion=p.selected_hc_fusion(bundle), schema='packet103.window.v1', build_receipt_sha256=sh,
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
        if name == 'KD':
            from kd_reference import project,TARGET_ONLY
            target=e.read('selection.json');ref=project(target)
            reference_hash=put(e,'KD/draft-reference-selection.json',ref)
            binding=dict(schema='packet103.kd-draft-projection.v1',passed=True,
                selection_sha256=pin['selection_sha256'],target_selection_sha256=pin['selection_sha256'],
                reference_selection_sha256=reference_hash,target_only=TARGET_ONLY,draft=target['draft'],target_executed=False)
            proof=dict(passed=True,selection_sha256=pin['selection_sha256'],reference_selection_sha256=reference_hash,
                draft_kernel_choices=dict(selection_sha256=reference_hash,choices=target['draft'],target_mutable_aliases=0))
            additions={'draft-reference-selection.json':ref,'draft-reference-binding.json':binding,
                'owner0/draft-reference-identity.json':proof,'owner1/draft-reference-identity.json':proof}
            host=e.read('KD/host-reference-identity.json');host.update(reference_selection_sha256=reference_hash,draft_reference=proof)
            additions['host-reference-identity.json']=host
            for owner in ('owner0','owner1'):
                native=e.read('KD/'+owner+'/receipt.json');native['selection_sha256']=reference_hash
                additions[owner+'/receipt.json']=native
            for leaf,value in additions.items():w['receipts'][leaf]=put(e,'KD/'+leaf,value)
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
