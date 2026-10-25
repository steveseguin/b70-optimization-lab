#!/usr/bin/env python3
"""Join actual discarded recursive probes to an accepted true-pair live replay."""
import argparse
import json
from pathlib import Path
from finalize_wavefront_proof import HERE, identity, token_hash, save


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,default=HERE/'live-pp4-proof')
    p.add_argument('--probe',type=Path,default=HERE.parent/'review-2026-10-25/depth-suite-a/incident-retrospective/rank0/draft-depth-probe-final.jsonl')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();reference=a.reference.resolve();probe=a.probe.resolve()
    read=lambda path:json.loads(path.read_text())
    assert read(reference/'summary.json')['passed'] is True
    plan,result=read(reference/'plan.json'),read(reference/'result.json')
    draft=read(reference/'draft-state-set.json');legacy=read(HERE/'live-draft-legacy-prefix.json')
    pairs=[r for line in (reference/'schedule.jsonl').read_text().splitlines() if (r:=json.loads(line)).get('event')=='live-draft']
    inputs=plan['prompt_tokens']+result['output_ids'][:-1]
    assert [r['position'] for r in pairs]==list(range(1,len(inputs))) and [r['token'] for r in pairs]==inputs[1:]
    assert all(r['head'] is (r['position']+1>=len(plan['prompt_tokens'])) for r in pairs)
    heads=[r for r in pairs if r['head']]
    wanted={r['position'] for r in heads};selected={}
    for line in probe.read_text().splitlines():
        r=json.loads(line);pos=r['confirmed_position']
        if pos in wanted:
            assert pos not in selected;selected[pos]=r
    assert set(selected)==wanted and len(heads)==len(legacy['rows'])
    rows=[]
    for pair,old in zip(heads,legacy['rows']):
        pos=pair['position'];observed=selected[pos]
        assert old['position']==pos and observed['confirmed_token']==pair['token']==old['token']==inputs[pos]
        assert observed['guesses'][0]==pair['proposal']==old['proposal']
        assert observed['schema']=='ownrt.draft-depth.cycle.v1' and observed['requested_depth']>=2
        assert observed['mutable_bytes_verified'] is True and observed['discarded'] is True and observed['restored_position']==pos
        eligible=pos<plan['context'];assert len(observed['guesses'])>=1+int(eligible)
        rows.append(dict(seed_position=pos,confirmed_token=pair['token'],head=True,parent_final_input_position=pos-1,
            guesses=observed['guesses'][:2],raw_hidden_sha256=pair['hidden_sha256'],depth2_eligible=eligible,
            probe_snapshot_bytes=observed['snapshot_bytes'],probe_restored_extent=observed['restored_extent']))
    assert token_hash([[r['position'],r['token'],r['head'],r['hidden_sha256']] for r in pairs])==draft['input_identity']['pair_sequence_sha256']
    count=sum(r['depth2_eligible'] for r in rows)
    packet=dict(schema='ownrt.recursive-provider-reference.v1',passed=True,prompt_tokens=len(plan['prompt_tokens']),
        target_input_rows=len(inputs),output_tokens=len(result['output_ids']),canonical_draft_position=len(pairs),
        canonical_true_pairs=len(pairs),no_head_pairs=len(pairs)-len(heads),head_pairs=len(heads),
        depth2_eligible_pairs=count,expected_recursive_captures=count,expected_recursive_restores=count,
        target_output_ids=result['output_ids'],target_prompt_token_sha256=token_hash(plan['prompt_tokens']),
        canonical_draft_state_set=identity(reference/'draft-state-set.json'),canonical_draft_input_identity=draft['input_identity'],
        sources=[identity(path) for path in [probe,reference/'schedule.jsonl',reference/'plan.json',reference/'result.json',HERE/'live-draft-legacy-prefix.json']],
        canonical_pairs=[{k:r[k] for k in ('position','token','head','proposal','hidden_sha256')} for r in pairs],depth2_rows=rows,
        scope='The first two guesses are actual recursive outputs from verified discarded probes, joined by confirmed seed token/position and exact d1 against canonical live PP4. They are not inferred from consecutive k1 hits. Old diagnostic restore verified canonical device mutable bytes, not the two pinned allocations; full new73-allocation state equality must be checked separately against the accepted live PP4 sealed draft state.',
        first_gate='Actual existing-MTP proposals only, no target speculative use. Seed locally executed and ACCEPTed; parent final COMMIT independently retained; all target owners quiescent. Canonical pairs and exact head mask must match. Provider-private backup is separate from canonical73 allocation state.',
        builder=identity(Path(__file__)))
    assert not a.out.exists(),'fresh reference packet required'
    save(a.out,packet)
    print(json.dumps({k:packet[k] for k in ('passed','canonical_true_pairs','no_head_pairs','head_pairs','depth2_eligible_pairs')}))


if __name__=='__main__':main()
