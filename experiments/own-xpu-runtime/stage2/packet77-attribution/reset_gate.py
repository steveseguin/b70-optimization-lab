#!/usr/bin/env python3
"""Exercise the new RESET observation flag on one host-only rank pair."""
import json
import sys
from build_engine import limits, P, B, sha, save
import pipeline
import suite


def main():
    limits()
    from worker import reset_observation
    out=B/'cpu-reset-one-load';out.mkdir()
    args=pipeline.parser().parse_args(['--binary',str(B/'gnu-host/own-rt-iq3'),'--output',str(out),
         '--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120',
         '--native-nice','19','--draft','mtp','--draft-rank','1','--target-split','0',
         '--controller','native','--timing','token','--retain-steps','1-24'])
    args.timing='attribution';args.host_memory='resident';args.selection_sha256=sha(P/'selection.json')
    ranks=out/'ranks';ranks.mkdir()
    transport=pipeline.Transport.__new__(pipeline.Transport)
    passed=False
    try:
        pipeline.Transport.__init__(transport,args,ranks)
        rows=[];expected=None
        for name,arm in [('control-a','control'),('instrumented','attribution'),('control-b','control')]:
            dest=out/name
            reset_observation(suite,transport,dest,arm)
            result=suite.run_request(transport,args,[2,5,3,7,1],24)
            assert result['passed']
            # Reset drains and persists output before the next request. Token
            # identity also compares the new flag with the standalone parent gate.
            if expected is None:expected=result['tokens']
            assert result['tokens']==expected
            assert expected==json.loads((P/'evidence/parent64.json').read_text())['tokens']
            rows.append(dict(arm=arm,tokens=24,output_sha256=result['output_token_sha256']))
        reset_observation(suite,transport,out/'after', 'control')
        identities=[]
        for name in ('control-a','instrumented','control-b'):
            dest=out/name
            hashes={str(f.relative_to(dest)):sha(f) for rank in ('rank0','rank1') for f in (dest/rank).glob('step*/layer-*.bf16')}
            assert len(hashes)==96
            identities.append(hashes)
        assert identities[0]==identities[1]==identities[2]
        transport.close(True);passed=True
        save(P/'evidence/reset-gate.json',dict(passed=True,device_executed=False,model_lifetimes=1,
             requests=rows,target_fixtures_per_request=96,binary_sha256=sha(B/'gnu-host/own-rt-iq3'),
             source_sha256=sha(P/'reset_gate.py')))
        print('One-load control / attribution / control: 3 x 96 fixtures and 24 tokens MATCH')
    finally:
        if not passed and hasattr(transport,'stop_write') and not transport.closed:
            transport.stop('CPU reset gate failed');transport.close(False)

if __name__=='__main__':main()
