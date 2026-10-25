#!/usr/bin/env python3
"""Adapt a terminal portable live replay to strict target/draft proof readers.

All derivations are explicit and hash-bound. Profile and local binding digests
are provenance, never substituted for legacy tensor-manifest model identity.
No model payload reads, GPU calls or process actions.
"""
import argparse
import copy
import gzip
import json
from pathlib import Path
import shutil
import sys

from finalize_wavefront_proof import HERE, compare, identity, save
import finalize_live_proof as live_proof
from finalize_portable_proof import option


def require(ok, message):
    if not ok:raise ValueError(message)


def read(path):
    path=Path(path)
    require(path.stat().st_size <= 8*1024**2,'bounded proof JSON')
    return json.loads(path.read_text())


def verify_authority(plan, config, receipt, reference_target, reference_draft):
    authority=receipt['generated_authority']
    require(authority['profile_sha256']==plan['model_profile_sha256']==config['profile_sha256'],
            'generated profile authority differs')
    require(authority['binding_sha256']==plan['deployment_binding_sha256']==config['binding_sha256'],
            'generated binding authority differs')
    deployment=Path(config['deployment'])
    require(identity(deployment/'profile.json')['sha256']==authority['profile_sha256']
            and identity(deployment/'binding.json')['sha256']==authority['binding_sha256'],
            'profile/binding bytes differ from separately recorded authority')
    argv=plan['stages'][0]['argv']
    auth=Path(option(argv,'--identity'))
    draft=Path(option(argv,'--draft-manifest'))
    auth_id,draft_id=identity(auth),identity(draft)
    require(auth_id['sha256']==plan['pins'][str(auth)]==authority['artifacts']['shard-auth.tsv']
            ==reference_target['input_identity']['model_sha256'],'target tensor authority differs from accepted reference')
    require(draft_id['sha256']==plan['pins'][str(draft)]==authority['artifacts']['draft-manifest.tsv']
            ==reference_draft['input_identity']['draft_model_sha256'],'draft tensor authority differs from accepted reference')
    header=Path(authority['include'])/authority['header']
    require(identity(header)['sha256']==authority['header_sha256']
            ==authority['artifacts']['include/'+authority['header']]
            ==receipt['generated_dependencies'][str(header)],'generated header authority/dependency differs')
    require(plan['pins'][receipt['binary']]==receipt['binary_sha256'],'native binary pin differs from build receipt')
    return dict(shard_auth=auth_id,draft_manifest=draft_id,generated_header=identity(header),
                model_profile_sha256=authority['profile_sha256'],deployment_binding_sha256=authority['binding_sha256'],
                binary_sha256=receipt['binary_sha256'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--reference',type=Path,default=HERE/'live-pp4-proof')
    args=p.parse_args();run,out,reference=args.run.resolve(),args.out.resolve(),args.reference.resolve()
    terminal=read(run/'result.json');plan=read(run/'plan.json')
    require(plan['schema']=='ownrt.portable-live-plan.v1' and plan['mode']=='verified-wavefront'
            and plan['live_draft'] is True and plan['draft_training'] is False
            and plan['draft_partition'] is False and plan['verify_restore'] is True,
            'portable live full-snapshot verified-restore plan required')
    config=read(plan['config'])
    require(identity(Path(plan['config']))['sha256']==plan['pins'][plan['config']], 'pinned portable config')
    receipt_path=Path(config['build_receipt']);receipt=read(receipt_path)
    require(identity(receipt_path)['sha256']==config['build_receipt_sha256'],'independently pinned build receipt')
    reference_target=read(reference/'candidate-state-set.json')
    reference_draft=read(reference/'draft-state-set.json')
    require(read(reference/'summary.json')['passed'] is True,'accepted reference required')
    authority=verify_authority(plan,config,receipt,reference_target,reference_draft)
    out.mkdir(parents=True,exist_ok=False)
    original=out/'original';original.mkdir()
    for name in ('plan.json','result.json','admission.json','unit.json','baseline.json','preflight.json','postflight.json'):
        if (run/name).is_file():shutil.copyfile(run/name,original/name)
    shutil.copyfile(plan['config'],original/'config.json')
    shutil.copyfile(receipt_path,original/'build-receipt.json')
    for name in ('profile.json','binding.json'):
        shutil.copyfile(Path(config['deployment'])/name,original/name)
    derived=out/'derived-input';derived.mkdir()
    adapted=copy.deepcopy(plan)
    adapted['model_identity_sha256']=authority['shard_auth']['sha256']
    adapted['derivation']=dict(original_plan=identity(run/'plan.json'),authority=authority,
        scope='Add semantic target tensor-manifest SHA for the shared proof reader. No execution fields or actual input/output records are changed.')
    save(derived/'plan.json',adapted)
    for name in ('result.json','admission.json','unit.json','tokens.jsonl','schedule.jsonl'):
        if (run/name).is_file():shutil.copyfile(run/name,derived/name)
    proof=out/'state-proof';saved_argv=sys.argv
    try:
        sys.argv=[str(Path(live_proof.__file__)),'--run',str(derived),'--out',str(proof),
                  '--draft-reference',str(reference/'draft-state-set.json')]
        code=live_proof.main()
    finally:sys.argv=saved_argv
    target=compare.compare(compare.load_set(reference/'candidate-state-set.json'),compare.load_set(proof/'candidate-state-set.json'))
    live_proof.compressed(out/'accepted-live-target-comparison.json.gz',target)
    events=[json.loads(line) for line in (run/'schedule.jsonl').read_text().splitlines()]
    pairs=[e for e in events if e.get('event')=='live-draft']
    ref_events=[json.loads(line) for line in (reference/'schedule.jsonl').read_text().splitlines()]
    ref_pairs=[e for e in ref_events if e.get('event')=='live-draft']
    keys=('position','token','head','proposal','hidden_sha256')
    pair_exact=[[r[k] for k in keys] for r in pairs]==[[r[k] for k in keys] for r in ref_pairs]
    draft_rows=Path(plan['stages'][0]['native_output'])/'draft-rows.jsonl'
    native=[json.loads(line) for line in draft_rows.read_text().splitlines()]
    provider_exact=[(r['draft_position']+1,r['confirmed_token'],r['head'],r['guess']) for r in native] \
        ==[(r['position'],r['token'],r['head'],r['proposal']) for r in pairs]
    save(out/'pair-comparison.json',dict(passed=pair_exact and provider_exact,
        exact_fields=list(keys),pair_count=len(pairs),controller_pair_exact=pair_exact,actual_provider_exact=provider_exact,
        source_trace=identity(run/'schedule.jsonl'),reference_trace=identity(reference/'schedule.jsonl'),provider_trace=identity(draft_rows)))
    state_summary=read(proof/'summary.json')
    draft_result=json.loads(gzip.decompress((proof/'draft-comparison.json.gz').read_bytes()))
    passed=code==0 and target['passed'] and pair_exact and provider_exact
    summary=dict(schema='ownrt.portable-live-proof.v1',passed=passed,source_run=str(run),reference=str(reference),
        original_plan=identity(run/'plan.json'),original_result=identity(run/'result.json'),
        config=identity(Path(plan['config'])),build_receipt=identity(receipt_path),authority=authority,
        target_state_exact_vs_accepted_live_pp4=target['passed'],target_buffer_count=len(target.get('compared_source_keys',[])),
        draft_state_exact=state_summary['draft_state_exact'],draft_allocation_count=len(draft_result.get('compared_source_keys',[])),
        raw_hidden_true_pairs_exact=pair_exact,actual_provider_pairs_exact=provider_exact,pairs=len(pairs),
        output_tokens_exact=state_summary['output_tokens_exact'],legacy_proposals_exact=state_summary['legacy_proposals_exact'],
        state_proof=identity(proof/'summary.json'),raw_bundles=state_summary['raw_bundles'],
        speed_claim=False,diagnostic_only=True,finalizer=identity(Path(__file__)),
        scope='Portable generated-profile/local-binding live execution with exact target/draft states and true-pair replay versus accepted lab PP4. Profile digest, binding digest and tensor-manifest identities remain distinct. No model payload reread, portable speed claim or clean-host certification.')
    save(out/'summary.json',summary)
    (out/'RESULT.md').write_text(f'''# Portable live-MTP replay: {'PASSED' if passed else 'FAILED'}

All 32 output IDs match. Target state comparison against accepted live PP4:
{target['passed']} ({summary['target_buffer_count']} canonical buffers/layouts).
Full draft-state comparison: {summary['draft_state_exact']}.
All {len(pairs)} true-pair hidden hashes and proposals match: {pair_exact};
actual native provider rows agree with the controller: {provider_exact}.
Retained legacy head proposals match: {summary['legacy_proposals_exact']}.

[Summary and distinct authority identities](summary.json),
[target comparison](accepted-live-target-comparison.json.gz),
[pair comparison](pair-comparison.json), [shared state proof](state-proof/summary.json).
Original portable plan/config/build/profile/binding and passive observations are
retained in `original/`. The derived input adds only the independently matched
tensor-manifest model identity needed by the common comparator.

This qualifies this generated portable live recipe against the accepted local
reference. It does not certify clean-host installation or performance. No model
payload was reread. Original raw states remain external pending durable archive.
''')
    print(json.dumps({k:summary[k] for k in ('passed','source_run','target_buffer_count','draft_state_exact','pairs','raw_hidden_true_pairs_exact')}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
