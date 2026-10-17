#!/usr/bin/env python3
"""Bind completed CPU preparations and all coordinator code. Never launch GPU."""
import json
from preparation import limits
from window_support import HERE,REPO,require,sha,verify_files

def main():
    limits();sources={};artifacts={};gates={}
    for mode in ('host','device'):
        path=HERE/f'build-layer-{mode}.json';r=json.loads(path.read_text())
        require(r['passed'] and r['device_executed'] is False and r['mode']==mode,'build receipt')
        verify_files(r['source_hashes'],REPO);verify_files(r['artifacts'],REPO);verify_files(r['baseline_provenance'],REPO)
        sources.update(r['source_hashes']);artifacts.update({str((REPO/n).relative_to(HERE)):h for n,h in r['artifacts'].items()});gates[path.name]=sha(path)
    for name in ('cpu-layer-gates.json','python-gates.json'):
        r=json.loads((HERE/name).read_text());require(r['passed'] and r['device_executed'] is False,'CPU gate')
        gates[name]=sha(HERE/name)
    cpu=json.loads((HERE/'cpu-layer-gates.json').read_text())
    require(cpu['build_receipt_sha256']==sha(HERE/'build-layer-host.json'),'CPU build identity')
    require(cpu['exact_capture_manifest_sha256']==sha(HERE/'exact-capture-manifest.json'),'capture manifest identity')
    require(len(cpu['repeats'])==2 and cpu['repeats'][0]['receipt']['exact_output_identity']==cpu['repeats'][1]['receipt']['exact_output_identity'],'fresh CPU exact repeats')
    for r in cpu['repeats']:verify_files(r['files'],REPO)
    for p in HERE.iterdir():
        if p.is_file() and (p.suffix in ('.py','.sh','.cpp','.hpp') or p.name in ('CMakeLists.txt','PREREGISTRATION.md','WINDOW.md','dispatch-baseline.json','exact-capture-manifest.json')):sources[str(p.relative_to(REPO))]=sha(p)
    row=dict(schema='own-runtime.packet48b.seal.v1',passed=True,device_executed=False,device_qualified=False,
             sources=sources,artifacts=artifacts,gates=gates,pending=['fresh E1/E2/T1/T2 matched full-layer device windows'],model_speed_claim=False)
    (HERE/'seal.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(dict(passed=True,device_executed=False,seal_sha256=sha(HERE/'seal.json'))))
if __name__=='__main__':main()
