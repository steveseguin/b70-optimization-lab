#!/usr/bin/env python3
"""Retain completed live-MTP diagnostics and verify CPU-only evidence gates."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import shutil
import sys

from finalize_wavefront_proof import HERE, OWNRT, compare, digest, identity, token_hash, save

sys.path.insert(0, str(OWNRT/'engine/tools'))
import compare_draft_state as draft_compare


def retain_bundle(dump, local, raw_bundles):
    local.mkdir()
    for name in ('state-seal.txt','state-index.tsv','state.json'):
        shutil.copyfile(dump/name,local/name)
    seal=(dump/'state-seal.txt').read_text().splitlines()
    raw_bundles.append(dict(path=str(dump/'state.bundle'),bytes=int(seal[1]),sha256=seal[2],
                            retained_metadata=str(local),retention='external raw; durable archive pending'))


def compressed(path, value):
    raw=json.dumps(value,indent=2,ensure_ascii=False).encode()+b'\n'
    path.write_bytes(gzip.compress(raw,mtime=0))
    return dict(**identity(path),uncompressed_sha256=digest(raw))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--draft-reference',type=Path)
    args=parser.parse_args()
    run,out=args.run.resolve(),args.out.resolve()
    terminal=json.loads((run/'result.json').read_text())
    plan=json.loads((run/'plan.json').read_text())
    out.mkdir(parents=True,exist_ok=False)
    for name in ('plan.json','result.json','admission.json','unit.json','tokens.jsonl','schedule.jsonl'):
        if (run/name).is_file():shutil.copyfile(run/name,out/name)
    base=HERE.parent/'review-2026-10-25/pp-proof/pp2'
    reference=json.loads((base/'state-set.json').read_text())
    base_result=json.loads((base/'result.json').read_text())
    reference['provenance']=dict(original_state_set=identity(base/'state-set.json'),
                                engine_sha256=reference['input_identity'].pop('engine_sha256'))
    for stage in reference['stages']:
        for key in ('dump','plan','metadata'):stage[key]=str((base/stage[key]).resolve())
    save(out/'reference-state-set.json',reference)
    semantic=dict(model_sha256=plan['model_identity_sha256'],prompt_token_sha256=token_hash(plan['prompt_tokens']),
                  output_token_sha256=token_hash(terminal.get('output_ids',[])),arithmetic=plan['activation_dtype'],
                  position=terminal.get('input_position',-1))
    candidate=dict(schema='ownrt.pipeline-state-set.v2',mode='verified-wavefront',
                   require_byte_verified_restores=True,layer_count=plan['boundaries'][-1],input_identity=semantic,
                   provenance=dict(plan=identity(run/'plan.json'),result=identity(run/'result.json')),stages=[])
    raw_bundles=[]
    for stage in plan['stages']:
        native=Path(stage['native_output']);local=out/f'stage{stage["id"]}';local.mkdir()
        dump=native/'state-2147483647'
        if dump.is_dir():retain_bundle(dump,local/dump.name,raw_bundles)
        for name in ('launch-plan.json','pipeline-stage.json','wavefront-checkpoint-layout.json',
                     'state-2147483647.wavefront-state.json','wavefront-quiescence.json','receipt.json','draft-rows.jsonl'):
            if (native/name).is_file():shutil.copyfile(native/name,local/name)
        candidate['stages'].append(dict(id=stage['id'],begin=stage['begin'],end=stage['end'],dump=str(dump),
            plan=str(local/'launch-plan.json'),metadata=str(local/'pipeline-stage.json'),
            quiescence=str(native/'state-2147483647.wavefront-state.json')))
        if stage['first']:
            draft_dump=dump.with_name(dump.name+'.draft')
            if draft_dump.is_dir():retain_bundle(draft_dump,local/draft_dump.name,raw_bundles)
    save(out/'candidate-state-set.json',candidate)
    try:
        target_result=compare.compare(compare.load_set(out/'reference-state-set.json'),
                                      compare.load_set(out/'candidate-state-set.json'))
    except (ValueError,KeyError,OSError,TypeError) as error:
        target_result=dict(passed=False,input_error=str(error))
    target_receipt=compressed(out/'target-comparison.json.gz',target_result)
    events=[json.loads(line) for line in (run/'schedule.jsonl').read_text().splitlines()]
    pairs=[row for row in events if row.get('event')=='live-draft']
    input_tokens=plan['prompt_tokens']+terminal.get('output_ids',[])[:-1]
    pairs_valid=len(pairs)==len(input_tokens)-1 and terminal.get('draft_pairs')==len(pairs)
    for position,row in enumerate(pairs,1):
        pairs_valid=pairs_valid and row['position']==position and row['token']==input_tokens[position] \
            and row['head'] is (position+1>=len(plan['prompt_tokens'])) \
            and compare.BUNDLE.hexhash(row.get('hidden_sha256')) \
            and type(row.get('proposal')) is int \
            and (0 <= row['proposal'] < plan['vocab'] if row['head'] else row['proposal']==-1)
    legacy=json.loads((HERE/'live-draft-legacy-prefix.json').read_text())
    current=[{key:row[key] for key in ('position','token','head','proposal')} for row in pairs if row['head']]
    legacy_exact=current==legacy['rows']
    save(out/'pair-comparison.json',dict(pairs_valid=pairs_valid,legacy_exact=legacy_exact,
        legacy_source=identity(HERE/'live-draft-legacy-prefix.json'),expected_legacy=legacy['rows'],observed_head=current))
    argv=plan['stages'][0]['argv'];manifest=Path(argv[argv.index('--draft-manifest')+1])
    manifest_receipt=identity(manifest)
    manifest_valid=manifest_receipt['sha256']==plan['pins'][str(manifest)]
    pair_identity=[[r['position'],r['token'],r['head'],r.get('hidden_sha256')] for r in pairs]
    draft_identity=dict(model_sha256=semantic['model_sha256'],draft_model_sha256=plan['pins'][str(manifest)],
        pair_sequence_sha256=token_hash(pair_identity),position=len(pairs),arithmetic='F32-target/BF16-draft',
        context=plan['context'],vocab=plan['vocab'],draft_experts=argv[argv.index('--draft-experts')+1])
    draft_set=dict(schema='ownrt.draft-state-set.v1',dump=str(draft_dump),input_identity=draft_identity,
                   provenance=dict(plan=identity(run/'plan.json'),draft_manifest=manifest_receipt,
                       draft_model_identity_scope='SHA256 of pinned manifest of per-tensor draft hashes/descriptors'))
    save(out/'draft-state-set.json',draft_set)
    try:
        loaded=draft_compare.load_set(out/'draft-state-set.json')
        draft_result=draft_compare.compare(draft_compare.load_set(args.draft_reference),loaded) if args.draft_reference else None
        draft_valid=True
    except (ValueError,KeyError,OSError,TypeError) as error:
        draft_valid=False;draft_result=dict(passed=False,input_error=str(error))
    if draft_result is not None:compressed(out/'draft-comparison.json.gz',draft_result)
    codes=terminal.get('returncodes',{})
    clean=terminal.get('passed') is True and terminal.get('error') is None and terminal.get('live_pids')==[] \
        and set(codes)=={str(s['id']) for s in plan['stages']} and all(type(v) is int and v==0 for v in codes.values())
    outputs_exact=terminal.get('output_ids')==base_result['output_ids']
    passed=clean and outputs_exact and target_result['passed'] and pairs_valid and legacy_exact and draft_valid and manifest_valid \
        and (draft_result is None or draft_result['passed'])
    summary=dict(schema='ownrt.live-mtp-proof.v1',passed=passed,terminal_clean=clean,diagnostic_only=True,speed_claim=False,
        use_proposals=plan['use_proposals'],boundaries=plan['boundaries'],output_tokens_exact=outputs_exact,
        canonical_target_state_exact=target_result['passed'],target_buffer_count=len(target_result.get('compared_source_keys',[])),
        canonical_pair_sequence_valid=pairs_valid,legacy_proposals_exact=legacy_exact,legacy_head_rows=len(current),
        draft_seal_valid=draft_valid,draft_manifest_pin_valid=manifest_valid,
        draft_reference=str(args.draft_reference) if args.draft_reference else None,
        draft_state_exact=None if draft_result is None else draft_result['passed'],draft_pairs=len(pairs),
        target_comparison=target_receipt,raw_bundles=raw_bundles,raw_bytes=sum(r['bytes'] for r in raw_bundles),
        source_run=str(run),finalizer=identity(Path(__file__)),
        comparators=[identity(Path(compare.__file__)),identity(Path(draft_compare.__file__))])
    save(out/'summary.json',summary)
    note=f'''# Live existing-MTP qualification: {'PASSED' if passed else 'FAILED'}

Boundaries {plan['boundaries']}; proposal use {plan['use_proposals']}. No speed claim.
Clean terminal exit: {clean}. All 32 baseline outputs exact: {outputs_exact}.
All {summary['target_buffer_count']} canonical target buffers/layouts exact: {target_result['passed']}.
Canonical true-pair sequence ({len(pairs)} steps) valid: {pairs_valid}.
All {len(current)} retained legacy draft head rows exact: {legacy_exact}.
Full draft seal and quiescent host metadata valid: {draft_valid}.
Cross-run full draft state comparison: {summary['draft_state_exact']}.

See [summary.json](summary.json), [target comparison](target-comparison.json.gz),
[pair comparison](pair-comparison.json) and [draft state manifest](draft-state-set.json).
Full target and draft raw bytes remain in external run paths, with retained seals
and per-buffer hashes. Durable archival remains pending; preserve original files.
Legacy proposal equality does not establish raw hidden or full legacy draft-state
equality. Cross-run draft-state equality, when present, compares the two new runs.
'''
    (out/'RESULT.md').write_text(note)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('raw_bundles','target_comparison','finalizer')}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
