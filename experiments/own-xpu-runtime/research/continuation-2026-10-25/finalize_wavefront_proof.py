#!/usr/bin/env python3
"""Retain a completed diagnostic wavefront proof; no device or process actions."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
OWNRT = HERE.parents[1]
COMPARATOR = OWNRT/'engine/tools/compare_pipeline_state.py'
spec = importlib.util.spec_from_file_location('compare_pipeline',COMPARATOR)
compare = importlib.util.module_from_spec(spec);spec.loader.exec_module(compare)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    raw=path.read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':digest(raw)}


def token_hash(tokens):
    return digest(json.dumps(tokens,separators=(',',':')).encode())


def save(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    run,out=args.run.resolve(),args.out.resolve()
    terminal=json.loads((run/'result.json').read_text()) # absent means still active: write nothing
    out.mkdir(parents=True,exist_ok=False)
    plan=json.loads((run/'plan.json').read_text())
    baseline=HERE.parent/'review-2026-10-25/pp-proof/pp2'
    reference=json.loads((baseline/'state-set.json').read_text())
    ref_plan=json.loads((baseline/'plan.json').read_text())
    ref_result=json.loads((baseline/'result.json').read_text())
    ref_identity={k:v for k,v in reference['input_identity'].items() if k!='engine_sha256'}
    assert ref_identity['prompt_token_sha256']==token_hash(ref_plan['prompt_tokens'])
    assert ref_identity['output_token_sha256']==token_hash(ref_result['output_ids'])
    reference['input_identity']=ref_identity
    reference['provenance']={'original_state_set':identity(baseline/'state-set.json'),
                             'engine_sha256':json.loads((baseline/'state-set.json').read_text())['input_identity']['engine_sha256']}
    for stage in reference['stages']:
        for key in ('dump','plan','metadata'):
            stage[key]=str((baseline/stage[key]).resolve())
    save(out/'reference-state-set.json',reference)
    engine=next(Path(arg) for arg in plan['stages'][0]['argv'] if str(arg) in plan['pins'] and Path(arg).name=='own-engine')
    candidate={'schema':'ownrt.pipeline-state-set.v2','mode':'verified-wavefront','layer_count':plan['boundaries'][-1],
               'require_byte_verified_restores':True,
               'input_identity':{'model_sha256':plan['model_identity_sha256'],'prompt_token_sha256':token_hash(plan['prompt_tokens']),
                                 'output_token_sha256':token_hash(terminal.get('output_ids',[])),
                                 'arithmetic':plan['activation_dtype'],'position':terminal.get('input_position',-1)},
               'provenance':{'plan':identity(run/'plan.json'),'result':identity(run/'result.json'),
                             'engine_path':str(engine),'engine_sha256':plan['pins'][str(engine)]},'stages':[]}
    for name in ('plan.json','result.json','admission.json','unit.json','tokens.jsonl','schedule.jsonl'):
        shutil.copyfile(run/name,out/name)
    receipts=[];raw_bundles=[];attestations=[]
    for stage in plan['stages']:
        native=Path(stage['native_output']);local=out/f'stage{stage["id"]}';local.mkdir()
        dump=native/'state-2147483647';retained_dump=local/dump.name
        if dump.is_dir():
            retained_dump.mkdir()
            for name in ('state-seal.txt','state-index.tsv','state.json'):
                shutil.copyfile(dump/name,retained_dump/name)
            seal=(dump/'state-seal.txt').read_text().splitlines()
            raw_bundles.append({'path':str(dump/'state.bundle'),'bytes':int(seal[1]),'sha256':seal[2],
                                'retained_metadata':str(retained_dump.relative_to(out)),
                                'retention':'original external raw bundle; durable archive pending'})
        for name in ('launch-plan.json','pipeline-stage.json','wavefront-checkpoint-layout.json',
                     'state-2147483647.wavefront-state.json','wavefront-quiescence.json'):
            if (native/name).is_file():
                shutil.copyfile(native/name,local/name);receipts.append(identity(native/name))
        att_path=native/'state-2147483647.wavefront-state.json'
        if att_path.is_file():attestations.append(json.loads(att_path.read_text()))
        candidate['stages'].append({'id':stage['id'],'begin':stage['begin'],'end':stage['end'],'dump':str(dump),
            'plan':str(local/'launch-plan.json'),'metadata':str(local/'pipeline-stage.json'),
            'quiescence':str(att_path)}) # exact native dump sibling is required by comparator
    save(out/'candidate-state-set.json',candidate)
    try:
        comparison=compare.compare(compare.load_set(out/'reference-state-set.json'),compare.load_set(out/'candidate-state-set.json'))
    except (ValueError,KeyError,OSError,TypeError) as error:
        comparison={'schema':'ownrt.pipeline-state-comparison.v1','passed':False,'input_error':str(error)}
    encoded=json.dumps(comparison,indent=2,ensure_ascii=False).encode()+b'\n'
    (out/'comparison.json.gz').write_bytes(gzip.compress(encoded,mtime=0))
    expected_stages={str(s['id']) for s in plan['stages']}
    terminal_clean=(terminal.get('passed') is True and terminal.get('error') is None and terminal.get('live_pids')==[]
                    and set(terminal.get('returncodes',{}))==expected_stages and all(v==0 for v in terminal['returncodes'].values()))
    coverage=terminal.get('forced_miss_coverage',{})
    covered=set(coverage)==set(map(str,plan['force_miss_positions'])) and all(r.get('target_rejected') is True and r.get('native_abort_completed') is True for r in coverage.values())
    exact_outputs=terminal.get('output_ids')==ref_result['output_ids']
    passed=terminal_clean and covered and exact_outputs and comparison['passed']
    result={'schema':'ownrt.wavefront-proof-audit.v1','passed':passed,'diagnostic_only':True,'speed_claim':False,
            'terminal_clean':terminal_clean,'all_forced_misses_covered':covered,'output_tokens_exact':exact_outputs,
            'canonical_state_exact':comparison['passed'],'compared_buffer_count':len(comparison.get('compared_source_keys',[])),
            'prompt_tokens':len(plan['prompt_tokens']),'output_tokens':len(terminal.get('output_ids',[])),
            'position':terminal.get('input_position'),'boundaries':plan['boundaries'],'forced_miss_positions':plan['force_miss_positions'],
            'stage_abort_counts':[r['abort_count'] for r in attestations],
            'stage_byteverified_restore_counts':[r['byteverified_restore_count'] for r in attestations],
            'comparison_file':identity(out/'comparison.json.gz'),'comparison_uncompressed_sha256':digest(encoded),
            'raw_state_bytes':sum(r['bytes'] for r in raw_bundles),'raw_bundles':raw_bundles,
            'reference_engine_sha256':reference['provenance']['engine_sha256'],
            'candidate_engine_sha256':candidate['provenance']['engine_sha256'],'native_metadata_sources':receipts,
            'source_run':str(run),'comparator':identity(COMPARATOR),'finalizer':identity(Path(__file__))}
    save(out/'summary.json',result)
    status='PASSED' if passed else 'FAILED'
    note=f'''# Four-stage forced-miss state proof: {status}

This is a scripted proposal and rollback diagnostic, not live drafting or a speed result.
The run used boundaries {plan['boundaries']}, {len(plan['prompt_tokens'])} prompt tokens,
and {len(terminal.get('output_ids',[]))} outputs. Native terminal cleanliness: {terminal_clean}.

The {len(plan['force_miss_positions'])} forced positions were {plan['force_miss_positions']}.
Every requested rejection and rollback was observed: {covered}.
Per-stage abort counts: {result['stage_abort_counts']}; byte-verified restores:
{result['stage_byteverified_restore_counts']}.

Output tokens match the retained PP2 target-only baseline: {exact_outputs}.
Strict canonical state/layout comparison passed: {comparison['passed']} across
{result['compared_buffer_count']} buffers. Comparison checks every canonical buffer,
sealed native wavefront quiescence, restored-state counters and committed position.
The two engine identities are recorded separately in [summary.json](summary.json);
the derived manifests share only model, tokens, arithmetic and position identity.
Pinned historical manifests remain unchanged.

Full comparison: [comparison.json.gz](comparison.json.gz). All native stage metadata,
state seals/indexes, terminal result and schedule are retained alongside it.
Raw state payloads total {result['raw_state_bytes']:,} bytes and remain at their original
external paths with hashes; a durable archive is pending. Do not remove originals.
No diagnostic throughput is promoted to a performance claim.
'''
    if not comparison['passed']:
        note+='\nFailure details remain in the compressed comparison and summary; no buffers were ignored to force a pass.\n'
    (out/'RESULT.md').write_text(note)
    print(json.dumps({k:result[k] for k in ('passed','terminal_clean','canonical_state_exact','compared_buffer_count','raw_state_bytes','stage_abort_counts')}))
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':main()
