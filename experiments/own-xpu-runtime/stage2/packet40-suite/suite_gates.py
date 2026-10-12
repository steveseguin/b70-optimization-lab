#!/usr/bin/env python3
"""CPU-only persistent-process reset proof and exact checker receipt integration."""
import argparse,copy,hashlib,json,shutil,statistics
from pathlib import Path
import pipeline,suite
P=Path(__file__).resolve().parent

def invariant(directory):
    result=json.loads((directory/'receipt.json').read_text())
    retained=suite.retained_state(directory)
    state={name:row['sha256'] for name,row in retained.items()}
    for rank in (0,1):
        inventory=json.loads(retained[f'rank{rank}/request-state-inventory.json']['text'])
        # The actual number of discarded launches can depend on scheduling.
        # Retain the raw archive/hash; compare every model/host-state field except
        # its event-issue counter, which is execution bookkeeping.
        inventory.pop('logical_event',None)
        state[f'rank{rank}/request-state-inventory.json']=hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()
        pipeline.require(inventory['standalone_target_mutable'] and inventory['loaded_layer']==[-1], 'standalone target/loaded-layer reset evidence missing')
        pipeline.require(all(row['bytes']>0 and len(row['sha256'])==64 for row in inventory['standalone_target_mutable'].values()), 'standalone inventory malformed')
    fixtures={str(file.relative_to(directory)):pipeline.sha(file) for file in sorted(directory.glob('step*/*.bf16'))}
    return dict(tokens=result['tokens'],stats={k:v for k,v in result['stats'].items() if k!='redo_ms'},
                fixtures=fixtures,state=state)

def reset_gate(binary,output,controller,draft):
    entries=[dict(prompt_id=name,mini_tokens=tokens,mini_count=8,input_bundle='unused-mini')
             for name,tokens in [('alpha',[2,5,3,7,1]),('beta',[1,2,1]),('gamma',[3,5,7,2])]]
    manifests=[]
    for index,ordered in enumerate((entries,[entries[2],entries[0],entries[1]])):
        path=output/f'{controller}-{draft}-manifest-{index}.json'
        pipeline.save(path,dict(arithmetic='iq3-p17-detmath-v2',token_cap=64,context=32,complete=False,prompts=ordered));manifests.append(path)
    outputs=[]
    for index,manifest in enumerate(manifests):
        dest=output/f'{controller}-{draft}-order-{index}';outputs.append(dest)
        args=suite.parser().parse_args(['--binary',str(binary),'--mini','--output',str(dest),
             '--suite-manifest',str(manifest),'--controller',controller,'--draft',draft,'--context','32',
             '--seconds','300','--wait-seconds','300'])
        args.host_memory='resident';args.argument_audit=True
        result=suite.run(args);pipeline.require(result['passed'],'mini suite failed')
        launches=[json.loads((dest/'ranks'/f'rank{r}-launch.json').read_text())['pid'] for r in (0,1)]
        pipeline.require(len(set(launches))==2,'persistent two-rank PIDs')
    retained=[]
    for entry in entries:
        name=entry['prompt_id'];left=invariant(outputs[0]/'repeat-1'/name);right=invariant(outputs[1]/'repeat-1'/name)
        pipeline.require(left==right,f'order dependence {controller}/{draft}/{name}')
        pipeline.require(left['state'] and len(left['fixtures'])==32,'full state/fixture reset evidence missing')
        retained.append(dict(raw_inventory_sha256_by_order=[{str(rank):suite.retained_state(dest/'repeat-1'/name)[f'rank{rank}/request-state-inventory.json']['sha256'] for rank in (0,1)} for dest in outputs],bookkeeping_excluded=['logical_event'],prompt_id=name,tokens=left['tokens'],stats=left['stats'],fixture_files=len(left['fixtures']),state_files=len(left['state']),
             canonical_sha256_by_order=[hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest() for value in (left,right)]))
    return dict(host_memory='resident',host_path='prepared',argument_audit=True,prompt_evidence=retained,controller=controller,draft=draft,prompts=3,orders=2,exact=True,
                compared='tokens, counters, every plan buffer and both banks, standalone target mutable allocation hashes, lookup/selected/loaded-layer/FP32 host metadata, all draft mutable allocation hashes and host position/disabled state, all 8x4 retained mini layer fixtures')

def oracle_gate(output):
    manifest_path=suite.ROOT/'experiments/own-xpu-runtime/stage2/suite-inputs-20261012/suite-manifest.json'
    manifest=json.loads(manifest_path.read_text());checker=suite.checker_module();rows=[]
    for entry in manifest['prompts']:
        oracle=suite.ROOT/entry['oracle_directory'];dest=output/'checker-fixtures'/entry['prompt_id'];dest.mkdir(parents=True)
        tokens=json.loads((oracle/'result.json').read_text())['tokens']
        pipeline.save(dest/'receipt.json',dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,arithmetic=manifest['arithmetic'],tokens=tokens))
        for directory in oracle.glob('step*'):
            if directory.is_dir():shutil.copytree(directory,dest/directory.name,copy_function=__import__('os').link)
        n,f=checker.check_prompt(dest,oracle,entry,suite.ROOT)
        wrong=dict(schema='own-runtime.iq3.packet26.run.v1',passed=True,arithmetic=manifest['arithmetic'],tokens=[tokens[0]^1]+tokens[1:])
        pipeline.save(dest/'receipt.json',wrong)
        rejected=False
        try:checker.check_prompt(dest,oracle,entry,suite.ROOT)
        except ValueError:rejected=True
        pipeline.require(rejected,'checker accepted corrupt token')
        rows.append(dict(prompt_id=entry['prompt_id'],tokens=n,fixtures=f,exact_schema_roundtrip=True,corrupt_token_rejected=True,
                         checker_sha256=checker.source_sha256,evidence='oracle-derived fixture receipt only; not a real-model runtime execution'))
    return rows

def admission_gate(output):
    class Checker:
        source_sha256='synthetic-admission-test'
        def check_prompt(self,*args):return 64,384
    entries=[]
    for name in ('first','second'):
        bundle=output/'admission-source'/name;bundle.mkdir(parents=True)
        values={'tokens.txt':b'1 2 3','input.json':json.dumps(dict(tokens=[1,2,3],model_dir='/same/model')).encode(),
                'plan.tsv':b'same-plan','identity.tsv':b'same-identity','vocab.bin':b'vocabulary'}
        for leaf,data in values.items():(bundle/leaf).write_bytes(data)
        entries.append(dict(prompt_id=name,input_bundle=str(bundle.resolve()),prompt_tokens=3,
                    oracle_directory='unused',input_bundle_hashes={leaf:hashlib.sha256(data).hexdigest() for leaf,data in values.items()}))
    frozen=suite.admit_inputs(entries,output/'admission-good',Checker())
    pipeline.require(frozen['first'][1]==[1,2,3],'admitted tokens snapshot')
    for leaf in ('plan.tsv','identity.tsv','input.json'):
        changed=copy.deepcopy(entries);bundle=Path(changed[1]['input_bundle']);path=bundle/leaf;old=path.read_bytes()
        replacement=json.dumps(dict(tokens=[1,2,3],model_dir='/other/model')).encode() if leaf=='input.json' else b'different'
        path.write_bytes(replacement);changed[1]['input_bundle_hashes'][leaf]=hashlib.sha256(replacement).hexdigest()
        failed=False
        try:suite.admit_inputs(changed,output/('admission-bad-'+leaf),Checker())
        except ValueError:failed=True
        finally:path.write_bytes(old)
        pipeline.require(failed,'mixed model/plan identity admitted: '+leaf)
    return dict(snapshot=True,mixed_plan_rejected=True,mixed_identity_rejected=True,mixed_model_directory_rejected=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binary',type=Path,default=P/'build/gnu-host/own-rt-iq3')
    ap.add_argument('--output',type=Path,default=P/'build/suite-gates');ap.add_argument('--controller',choices=['python','native','both'],default='both')
    a=ap.parse_args();pipeline.require(not a.output.exists(),'fresh gate output');a.output.mkdir(parents=True)
    rows=[]
    for controller in (['python','native'] if a.controller=='both' else [a.controller]):
        for draft in ('none','mtp'):rows.append(reset_gate(a.binary,a.output,controller,draft))
    from test_receipt_metadata import run_gates
    metadata=run_gates();pipeline.save(P/'receipt-metadata-gates.json',metadata)
    oracle=oracle_gate(a.output);admission=admission_gate(a.output)
    checker_copy=a.output/'checker-snapshot.py'
    original=b'VALUE = 7\n';checker_copy.write_bytes(original)
    loaded=suite.checker_module(checker_copy);checker_copy.write_bytes(b'VALUE = 99\n')
    pipeline.require(loaded.VALUE==7 and loaded.source_sha256==hashlib.sha256(original).hexdigest(),'checker bytes/hash changed after import')
    from unittest.mock import patch
    class FaultThenExact:
        source_sha256='synthetic-failure-continuation-test'
        def token_record(self,*unused):return [7]
    check=FaultThenExact();outcomes=[]
    with patch.object(pipeline,'sha',return_value='a'),patch.object(Path,'read_text',return_value='{"result_sha256":"a"}'):
        for tokens in ([8],[7],[7]):
            outcomes.append(suite.compare_request(a.output,dict(passed=True,tokens=tokens,requested_max_new=1,retain_steps='none'),dict(oracle_directory='unused',oracle_receipt_sha256='a'),check)['passed'])
    pipeline.require(outcomes==[False,True,True],'exactness failure skipped remaining requests')
    example=[dict(prompt_id='a',repeat=1,passed=True,decode_tok_s=20),dict(prompt_id='b',repeat=1,passed=True,decode_tok_s=30),
             dict(prompt_id='a',repeat=2,passed=False,decode_tok_s=999),dict(prompt_id='b',repeat=2,passed=True,decode_tok_s=None)]
    summary=suite.summarize(example,False);pipeline.require(summary['decode_median_tok_s']==25 and not summary['passed'],'median/failure semantics')
    timed=dict(timing_rows=[dict(token_id=7,completed_monotonic=1.),dict(token_id=8,completed_monotonic=1.05),dict(token_id=248044,completed_monotonic=1.10)])
    pipeline.require(abs(suite.rate(timed,True)-20)<1e-10,'EOS interval rate')
    pipeline.require(suite.rate(dict(timing_rows=[dict(token_id=248044,completed_monotonic=1.)]),True) is None,'immediate EOG rate')
    result=dict(passed=True,device_executed=False,reset_proofs=rows,oracle_receipt_checks=oracle,formula_test=True,receipt_metadata=metadata,input_admission=admission,checker_snapshot_binding=True,exactness_failure_continues=outcomes,
                real_model_execution=False,binary_sha256=pipeline.sha(a.binary))
    pipeline.save(P/'suite-gate-results.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
