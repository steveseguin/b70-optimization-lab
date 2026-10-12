#!/usr/bin/env python3
"""Export hash-bound evidence from an actually executed CPU suite directory."""
import argparse,hashlib,json
from pathlib import Path
import pipeline,suite
P=Path(__file__).resolve().parent

CPU_SUITE_COMPILER='icpx-host'
CPU_SUITE_BINARY=CPU_SUITE_COMPILER+'/own-rt-iq3'

def cpu_suite_identity(packet=P):
    binary=packet/'build'/CPU_SUITE_BINARY
    pipeline.require(binary.is_file(),'Intel CPU suite binary missing')
    return dict(host_compiler=CPU_SUITE_COMPILER,binary_relative_to_build=CPU_SUITE_BINARY,binary_sha256=pipeline.sha(binary))

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def frozen_coverage(manifest,checker,authority=None):
    ids=[entry['prompt_id'] for entry in manifest['prompts']]
    expected=list(checker.PROMPT_IDS)
    pipeline.require(len(expected)==12 and len(set(expected))==12,'frozen prompt identity')
    pipeline.require(len(ids)==len(set(ids)) and set(ids)<=set(expected),'duplicate/unknown admitted prompt')
    if authority is None:
        authority=json.loads((suite.ROOT/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012/suite-manifest.json').read_text())
    bindings={}
    for key in ('suite_sha256','prompts_manifest_sha256'):
        if key in manifest:
            pipeline.require(isinstance(manifest[key],str) and len(manifest[key])==64 and manifest[key]==authority.get(key),'frozen '+key+' identity differs')
            bindings[key]=manifest[key]
    complete=manifest.get('complete') is True
    pipeline.require(not complete or (len(ids)==12 and set(ids)==set(expected)),'complete flag without twelve frozen prompts')
    return dict(expected_prompt_ids=expected,admitted_prompt_ids=ids,complete=complete,identity_bindings_verified=bindings)

def retained_state_binding(output):
    archive=output/'state-evidence.json.gz';receipt=output/'state-retention.json'
    metadata=json.loads(receipt.read_text());rows=suite.retained_state(output)
    pipeline.require(metadata['sha256']==pipeline.sha(archive) and metadata['retained_bytes']==archive.stat().st_size,'state archive binding differs')
    pipeline.require(metadata['files']==len(rows) and metadata['original_bytes']==sum(r['bytes'] for r in rows.values()),'state retention extent differs')
    inventory={}
    for rank in (0,1):
        key=f'rank{rank}/request-state-inventory.json'
        record=json.loads(rows[key]['text'])
        pipeline.require(bool(record['standalone_target_mutable']) and record['loaded_layer']==[-1],'runtime state inventory missing')
        state=json.loads(rows[f'rank{rank}/state-2147483647/state.json']['text'])
        for name,expected in state['buffers'].items():
            leaf=('alternate-'+name[len('alternate:'):] if name.startswith('alternate:') else name)+'.bin'
            pipeline.require(rows[f'rank{rank}/state-2147483647/{leaf}']['sha256']==expected,'retained target buffer binding differs')
        inventory[str(rank)]=rows[key]['sha256']
    return dict(state_evidence_sha256=pipeline.sha(archive),state_retention_sha256=pipeline.sha(receipt),
                runtime_state_inventory_sha256=inventory,retained_state_files=len(rows))

def export_run(run,destination):
    run=run.resolve();summary=json.loads((run/'summary.json').read_text())
    manifest=json.loads((run/'suite-manifest.snapshot.json').read_text())
    pipeline.require(summary.get('device_executed') is False,'CPU suite export requires no device execution')
    pipeline.require(summary.get('passed') is True,'cannot export failed suite as passing')
    pipeline.require(summary['manifest_sha256']==pipeline.sha(run/'suite-manifest.snapshot.json'),'suite manifest snapshot changed')
    checker=suite.checker_module();coverage=frozen_coverage(manifest,checker)
    entries={entry['prompt_id']:entry for entry in manifest['prompts']};rows=summary['rows']
    repeats={row['repeat'] for row in rows};pipeline.require(repeats and repeats==set(range(1,max(repeats)+1)),'repeat coverage')
    pipeline.require(len(rows)==len(entries)*len(repeats) and {(r['prompt_id'],r['repeat']) for r in rows}=={(p,r) for p in entries for r in repeats},'executed request coverage')
    identity=cpu_suite_identity()
    expected_binary=(P/'build'/identity['binary_relative_to_build']).resolve()
    ranks=[]
    for rank in (0,1):
        launch=run/'ranks'/f'rank{rank}-launch.json';teardown=run/'ranks'/f'rank{rank}/receipt.json'
        launched=json.loads(launch.read_text());closed=json.loads(teardown.read_text())
        pipeline.require(launched.get('device_executed') is False and closed.get('passed') is True,'rank execution receipt failed')
        pipeline.require(Path(launched['argv'][0]).resolve()==expected_binary,'CPU suite rank compiler/executable identity differs')
        pipeline.require(closed.get('rank')==rank and len(closed['teardown'])==1 and all(row.get('safe_to_exit') and row.get('live_bytes')==0 and row.get('in_flight')==0 for row in closed['teardown']),'rank teardown ownership')
        ranks.append(dict(rank=rank,pid=launched['pid'],launch_sha256=pipeline.sha(launch),teardown_sha256=pipeline.sha(teardown)))
    pipeline.require(ranks[0]['pid']!=ranks[1]['pid'],'rank PID identity')
    checker_bytes=Path(checker.__file__).read_bytes()
    pipeline.require(hashlib.sha256(checker_bytes).hexdigest()==checker.source_sha256,'checker changed during export snapshot')
    checker_snapshot=run/'export-suite-checker.py';checker_snapshot.write_bytes(checker_bytes)
    observed=[];binaries=set()
    for row in rows:
        receipt=run/row['receipt'];pipeline.require(receipt.resolve().is_relative_to(run),'receipt escapes run directory')
        output=receipt.parent;result=json.loads(receipt.read_text());entry=entries[row['prompt_id']]
        pipeline.require(result.get('device_executed') is False and result.get('passed') is True,'request execution failed')
        pipeline.require(result.get('oracle_check',{}).get('passed') is True,'request lacked exact oracle check')
        pipeline.require(result.get('schema')=='own-runtime.iq3.packet26.run.v1','actual runtime receipt schema')
        trace=result['rank_trace']
        pipeline.require(all(any(r['rank']==rank and r['op']==pipeline.HALF for r in trace) for rank in (0,1)),'missing executed rank HALF evidence')
        timing_hashes={str(rank):pipeline.sha(output/f'rank{rank}/timings.jsonl') for rank in (0,1)}
        tokens,fixtures=checker.check_prompt(output,suite.ROOT/entry['oracle_directory'],entry,suite.ROOT)
        inventory=checker.fixture_inventory(output,tokens);binaries.add(result['binary_sha256'])
        pipeline.require(result['binary_sha256']==identity['binary_sha256'],'CPU suite request differs from qualified Intel binary')
        state_binding=retained_state_binding(output)
        observed.append(dict(prompt_id=row['prompt_id'],repeat=row['repeat'],tokens=result['tokens'],token_count=tokens,
                    token_sha256=canonical_hash(result['tokens']),fixture_files=fixtures,fixture_inventory_sha256=canonical_hash(inventory),
                    receipt_sha256=pipeline.sha(receipt),rank_timing_sha256=timing_hashes,rank_trace_sha256=canonical_hash(trace),binary_sha256=result['binary_sha256'],
                    run_checker_sha256=result['oracle_check']['checker_sha256'],export_checker_sha256=checker.source_sha256,
                    acceptance=result.get('acceptance'),stats=result['stats'],controller=result['controller'],draft=result['draft'],exact=True,**state_binding))
    pipeline.require(len(binaries)==1,'CPU suite mixed binary identities')
    pipeline.require(cpu_suite_identity()==identity,'CPU suite binary changed during export')
    result=dict(schema='packet38.real-suite-cpu.v1',passed=True,device_executed=False,real_model_execution=True,
                no_speed_claim=True,complete_frozen_suite=coverage['complete'],frozen_coverage=coverage,
                export_checker_sha256=checker.source_sha256,export_checker_snapshot=str(checker_snapshot.relative_to(P)),
                admitted_prompts=len(entries),expected_frozen_prompts=12,repeats=len(repeats),requests=len(observed),
                token_count=sum(r['token_count'] for r in observed),fixture_files=sum(r['fixture_files'] for r in observed),
                **identity,manifest_sha256=summary['manifest_sha256'],summary_sha256=pipeline.sha(run/'summary.json'),
                input_admission_sha256=pipeline.sha(run/'input-admission.json'),ranks=ranks,rows=observed,
                evidence_directory=str(run.relative_to(P)) if run.is_relative_to(P) else str(run),
                scope='actual persistent CPU rank executions; exact tokens and every retained fixture rechecked; incomplete manifest explicitly reported')
    pipeline.save(destination,result);return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--output',type=Path,default=P/'suite-real-cpu.json')
    a=ap.parse_args();print(json.dumps(export_run(a.run,a.output),indent=2))
