#!/usr/bin/env python3
"""Verify a completed portable target replay against retained PP2 raw state."""
import argparse
import gzip
import json
from pathlib import Path
import shutil

from finalize_wavefront_proof import HERE, compare, identity, token_hash, save
from finalize_live_proof import retain_bundle, compressed


def option(argv, key):
    assert argv.count(key)==1
    return argv[argv.index(key)+1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    run,out=args.run.resolve(),args.out.resolve()
    result=json.loads((run/'result.json').read_text())
    plan=json.loads((run/'plan.json').read_text())
    out.mkdir(parents=True,exist_ok=False)
    assert plan['schema']=='ownrt.portable-launch-plan.v1' and plan['mode']=='target-only'
    baseline=HERE.parent/'review-2026-10-25/pp-proof/pp2'
    reference=json.loads((baseline/'state-set.json').read_text())
    ref_result=json.loads((baseline/'result.json').read_text())
    reference['provenance']=dict(original_state_set=identity(baseline/'state-set.json'),
                                engine_sha256=reference['input_identity'].pop('engine_sha256'))
    for stage in reference['stages']:
        for key in ('dump','plan','metadata'):stage[key]=str((baseline/stage[key]).resolve())
    save(out/'reference-state-set.json',reference)
    auth=Path(option(plan['stages'][0]['argv'],'--identity'))
    auth_receipt=identity(auth)
    # Legacy model identity is the SHA256 of shard-auth.tsv, not the old host
    # path or the new profile's JSON digest. Require direct byte identity.
    auth_matches=auth_receipt['sha256']==plan['pins'][str(auth)]==reference['input_identity']['model_sha256']
    semantic=dict(model_sha256=auth_receipt['sha256'],prompt_token_sha256=token_hash(plan['prompt_tokens']),
                  output_token_sha256=token_hash(result.get('output_ids',[])),arithmetic=plan['activation_dtype'],
                  position=result.get('input_position',-1))
    candidate=dict(schema='ownrt.pipeline-state-set.v1',mode='target-only',layer_count=plan['boundaries'][-1],
        input_identity=semantic,provenance=dict(plan=identity(run/'plan.json'),result=identity(run/'result.json'),
            model_profile_sha256=plan['model_profile_sha256'],deployment_binding_sha256=plan['deployment_binding_sha256'],
            shard_auth=auth_receipt),stages=[])
    for name in ('plan.json','result.json','admission.json','unit.json','tokens.jsonl','initial-observation.json'):
        if (run/name).is_file():shutil.copyfile(run/name,out/name)
    raw_bundles=[]
    for stage in plan['stages']:
        native=Path(stage['native_output']);local=out/f'stage{stage["id"]}';local.mkdir()
        dump=native/'state-2147483647'
        if dump.is_dir():retain_bundle(dump,local/dump.name,raw_bundles)
        for name in ('launch-plan.json','pipeline-stage.json','receipt.json','request-state-inventory.json'):
            if (native/name).is_file():shutil.copyfile(native/name,local/name)
        candidate['stages'].append(dict(id=stage['id'],begin=stage['begin'],end=stage['end'],dump=str(dump),
            plan=str(local/'launch-plan.json'),metadata=str(local/'pipeline-stage.json')))
    save(out/'candidate-state-set.json',candidate)
    try:
        comparison=compare.compare(compare.load_set(out/'reference-state-set.json'),compare.load_set(out/'candidate-state-set.json'))
    except (ValueError,KeyError,OSError,TypeError) as error:
        comparison=dict(passed=False,input_error=str(error))
    comparison_receipt=compressed(out/'comparison.json.gz',comparison)
    codes=result.get('returncodes',{})
    clean=result.get('passed') is True and result.get('error') is None and result.get('live_pids')==[] \
        and set(codes)=={str(s['id']) for s in plan['stages']} and all(type(v) is int and v==0 for v in codes.values())
    outputs_exact=result.get('output_ids')==ref_result['output_ids']
    passed=clean and auth_matches and outputs_exact and comparison['passed']
    summary=dict(schema='ownrt.portable-target-proof.v1',passed=passed,terminal_clean=clean,
        model_shard_auth_identical=auth_matches,output_tokens_exact=outputs_exact,canonical_state_exact=comparison['passed'],
        target_buffer_count=len(comparison.get('compared_source_keys',[])),boundaries=plan['boundaries'],
        position=result.get('input_position'),prompt_tokens=len(plan['prompt_tokens']),output_tokens=len(result.get('output_ids',[])),
        model_profile_sha256=plan['model_profile_sha256'],deployment_binding_sha256=plan['deployment_binding_sha256'],
        comparison=comparison_receipt,raw_bundles=raw_bundles,raw_bytes=sum(r['bytes'] for r in raw_bundles),
        source_run=str(run),speed_claim=False,diagnostic_only=True,finalizer=identity(Path(__file__)),
        comparator=identity(Path(compare.__file__)))
    save(out/'summary.json',summary)
    (out/'RESULT.md').write_text(f'''# Portable target replay: {'PASSED' if passed else 'FAILED'}

Boundaries {plan['boundaries']}; {summary['prompt_tokens']} prompt tokens and
{summary['output_tokens']} outputs; final position {summary['position']}.
Terminal native exits clean: {clean}. Model shard-auth bytes identical to the
retained gold PP2 run: {auth_matches}. All output IDs exact: {outputs_exact}.
All {summary['target_buffer_count']} canonical target state buffers and layouts
match the gold run: {comparison['passed']}.

See [summary.json](summary.json) and [full comparison](comparison.json.gz).
New profile/binding/build identities stay in provenance; shared semantic model
identity is independently tied to the exact shard-auth bytes. Historical
reference manifests remain unchanged.

This is target-only execution/state qualification for the generated local
deployment, not portable MTP or throughput certification. Raw state bundles
remain external with retained seals and hashes; preserve originals pending
durable archival. No model payload was reread by this evidence audit.
''')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('raw_bundles','comparison','finalizer','comparator')}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
