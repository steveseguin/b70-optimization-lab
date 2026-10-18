#!/usr/bin/env python3
"""Fresh host-only miniature engines: packet64, control and two attribution runs."""
import json,time
import subprocess
from pathlib import Path
import pipeline
from build_engine import limits, sha, save, P, B, ROOT, BASE


def run_one(label, binary, timing):
    links = subprocess.check_output(['readelf','-d',str(binary)], text=True).lower()
    assert not any(x in links for x in ('libsycl','libze_loader','libur_loader','libopencl'))
    dest = B/('cpu-final-default-'+label+'-'+str(time.time_ns()))
    args = pipeline.parser().parse_args(['--binary',str(binary),'--output',str(dest),
        '--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120',
        '--native-nice','19','--draft','mtp','--draft-rank','1','--target-split','0',
        '--controller','native','--timing','token','--retain-steps','1-24'])
    args.timing = timing
    args.host_memory = 'resident'
    args.selection_sha256 = None
    result = pipeline.run(args)
    assert result['passed'], result.get('error')
    fixtures = {str(f.relative_to(dest)):sha(f) for rank in ('rank0','rank1')
                for f in (dest/rank).glob('step*/layer-*.bf16')}
    assert len(fixtures)==96 and len(result['tokens'])==24
    proposals = [r['guess'] for line in (dest/'rank1/draft-rows.jsonl').read_text().splitlines()
                 if 'guess' in (r:=json.loads(line))]
    states = {str(f.relative_to(dest/'rank1/draft-final-state')):sha(f)
              for f in (dest/'rank1/draft-final-state').rglob('*')
              if f.is_file() and f.suffix in ('.bin','.bf16','.f32','.u32')}
    identity = dict(tokens=result['tokens'], fixtures=fixtures, proposals=proposals, draft_state=states)
    save(P/'evidence'/(label+'.json'), identity)
    return identity, dict(label=label, binary_sha256=sha(binary), timing=timing,
                         target_fixtures=len(fixtures), tokens=24, draft_proposals=len(proposals),
                         identity_sha256=sha(P/'evidence'/(label+'.json')))


def main():
    import shutil
    limits()
    adapter=B/"mini-adapter";adapter.mkdir(exist_ok=True)
    shutil.copyfile(P.with_name("packet77-attribution")/"selection.json",adapter/"selection.json")
    shutil.copyfile(P/"memory-plan.json",adapter/"memory-plan.json")
    pipeline.P=adapter
    build = json.loads((P/'build-device-receipt.json').read_text())
    for name, digest in build['artifacts'].items(): assert sha(P/name)==digest
    expected = None
    rows = []
    for label, binary, timing in [('parent124b',BASE/'build/gnu-host/own-rt-iq3','token'),
         ('control',B/'gnu-host/own-rt-iq3','token'),
         ('attribution-a',B/'gnu-host/own-rt-iq3','attribution'),
         ('attribution-b',B/'gnu-host/own-rt-iq3','attribution')]:
        value, row = run_one(label, binary, timing)
        if expected is None: expected=value
        assert value==expected, label+' changed output bytes/proposals/state'
        rows.append(row)
        print(label, '96 miniature target fixtures, 24 target tokens and draft state MATCH', flush=True)
    for label, value in [('expected',expected),('actual',value)]:
        (P/'evidence'/('fixture-'+label+'.bin')).write_bytes((json.dumps(value,sort_keys=True,indent=2)+'\n').encode())
    sources = {str((P/name).relative_to(ROOT)):sha(P/name) for name in
               ('cpu_gate.py','pipeline.py','selection.json','memory-plan.json')}
    save(P/'evidence/cpu-gates.json',dict(passed=True,device_executed=False,model_weights_read=False,
         rows=rows, sources=sources, build_receipt_sha256=sha(P/'build-device-receipt.json'),
         limitation='Synthetic CPU miniature; device target oracle and real class costs pending.'))

if __name__=='__main__': main()
