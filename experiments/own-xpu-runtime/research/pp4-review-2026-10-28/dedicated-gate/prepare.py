#!/usr/bin/env python3
"""Write fresh comparison manifests after dedicated owners have exited.
No bundle extraction, device work, or mutation of original manifests.
"""
import argparse
import json
from pathlib import Path
import compare as C

def prepare(plan_path,reference,destination):
    plan,_=C.read(plan_path);output=Path(plan['output'])
    result,_=C.driver_result(output/'driver-result.json')
    raw,_=C.trace_source(output/'commands.jsonl')
    pairs=C.canonical_pairs([json.loads(line) for line in raw.splitlines()],result['input_position'])
    pairhash=C.T.sha(json.dumps(pairs,sort_keys=True,separators=(',',':')).encode())
    reference_draft,_=C.read(reference/'draft-set.json')
    identity=dict(reference_draft['input_identity'],pair_sequence_sha256=pairhash,position=result['input_position']-1)
    C.need(identity['draft_model_sha256']==plan['draft_model_sha256'] and identity['model_sha256']==plan['model_identity_sha256'],'actual model identity')
    provider=Path(plan['provider']['native_output'])
    dumps=list(provider.glob('provider-dump-*'));C.need(len(dumps)==1,'one actual retained provider DUMP')
    receipts=[str(Path(stage['native_output'])/'receipt.json') for stage in plan['stages']]+[str(provider/'receipt.json')]
    for path in receipts:
        receipt,_=C.read(path);C.need(receipt['passed'] is True,'owners must finish before preparing state comparison')
    destination.mkdir(mode=0o700)
    draft=destination/'draft-set.json'
    draft.write_text(json.dumps(dict(schema='ownrt.draft-state-set.v1',dump=str(dumps[0]),input_identity=identity),indent=2)+'\n')
    stages=[]
    for stage in plan['stages']:
        native=Path(stage['native_output']);dump=native/'state-2147483647'
        stages.append(dict(id=stage['id'],begin=stage['begin'],end=stage['end'],dump=str(dump),
            plan=str(native/'launch-plan.json'),metadata=str(native/'pipeline-stage.json'),
            quiescence=str(dump)+'.ring-state.json'))
    manifest=destination/'inputs.json'
    manifest.write_text(json.dumps(dict(schema='ownrt.dedicated-parity-inputs.v1',reference_request=str(reference),
        plan=str(plan_path.resolve()),result=str(output/'driver-result.json'),commands=str(output/'commands.jsonl'),
        draft_set=str(draft.resolve()),stages=stages,process_receipts=receipts),indent=2)+'\n')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--reference-request',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    print(prepare(args.plan,args.reference_request,args.out))
