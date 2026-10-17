#!/usr/bin/env python3
"""Seal CPU preparation, never enumerate devices or launch a device program."""
import json
from build import HERE,ROOT,sha,limits
from window_support import verify_files,require
from summarize import exact

def main():
    limits();sources={};artifacts={};gates={}
    for kind in ('gnu','intel','device'):
        p=HERE/f'build-{kind}.json';b=json.loads(p.read_text())
        require(b.get('passed') is True and b.get('device_executed') is False and b['kind']==kind,'build missing')
        verify_files(b['sources'],ROOT);verify_files(b['artifacts'],HERE)
        for name,h in b['sources'].items():
            require(name not in sources or sources[name]==h,'build source mismatch');sources[name]=h
        artifacts.update(b['artifacts']);gates[p.name]=sha(p)
    for name in ('cpu-gates.json','python-gates.json'):
        p=HERE/name;b=json.loads(p.read_text());require(b.get('passed') is True and b.get('device_executed') is False,'CPU gate missing')
        verify_files(b['source_hashes'],ROOT);verify_files(b['files'],HERE);sources.update(b['source_hashes']);gates[name]=sha(p)
        if name=='cpu-gates.json':
            require(set(b['builds'])=={'gnu','intel'} and set(b['repeats'])=={'gnu','intel'},'both compiler gates required')
            for kind,repeats in b['repeats'].items():
                require(b['builds'][kind]==sha(HERE/f'build-{kind}.json'),'CPU build gate changed')
                require(len(repeats)==2 and repeats[0]['path']!=repeats[1]['path'],'two fresh CPU runs')
                rs=[exact(HERE/x['path'],cpu=True) for x in repeats]
                require(all(x==y['receipt'] for x,y in zip(rs,repeats)) and rs[0]['exact_output_identity']==rs[1]['exact_output_identity'],'CPU output receipt changed')
    for p in HERE.iterdir():
        if p.suffix in ('.py','.cpp','.hpp','.sh') or p.name in ('WINDOW.md','PREREGISTRATION.md','byte-census.json'):
            sources[str(p.relative_to(ROOT))]=sha(p)
    # Inherited supervisor is imported by path. Pin its entire local import
    # closure explicitly, even though it is not part of C++ dependencies.
    for name in ('window.py',):
        p=HERE.parent/'packet34-replay-bench'/name;sources[str(p.relative_to(ROOT))]=sha(p)
    result=dict(schema='own-runtime.packet48.seal.v1',passed=True,device_executed=False,
        device_qualified=False,model_speed_claim=False,card=0,sources=sources,
        artifacts=artifacts,gates=gates,pending=['E1/E2 card0 byte gates','T1/T2 card0 timing and bar','full-engine integration and original oracle'])
    (HERE/'seal.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(passed=True,device_executed=False,seal_sha256=sha(HERE/'seal.json'),sources=len(sources))))

if __name__=='__main__':main()
