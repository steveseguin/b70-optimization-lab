#!/usr/bin/env python3
"""Replay completed 58x smoke-d/max receipts without importing mutable parents."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
V=P.parent/'packet58x-cache-capacity/evidence/card0-capacity-d'
sys.path.insert(0,str(P/'screen-reader'))
import suite_driver as D
ORDER=('K1a','K1b','WSCREEN')
def main():
    expected=D.read(P/'lineage/58x-build-receipt.json')
    expected_hash=D.sha(P/'lineage/58x-build-receipt.json')
    bindings=D.read(P/'parent-evidence.json')['sources']
    sources={};boots=set();summaries={}
    def pin(path):
        name=str(path.relative_to(ROOT));digest=D.sha(path)
        D.require(bindings.get(name)==digest,'parent evidence changed: '+name)
        sources[name]=digest
        return digest
    manifest=D.oracle_inputs()
    for arm in ('smoke','max'):
        root=V/arm
        queue=D.read(P/'lineage'/f'58x-{arm}-queue.json')
        D.require(queue.get('passed') is True and queue.get('completed')==list(ORDER) and queue.get('running') is None and not queue.get('error'),'parent queue incomplete')
        for stage in ORDER:
            path=root/stage;pin(path/'window.json');row=D.read(path/'window.json')
            D.require(row.get('passed') is True and row.get('device_executed') is True and row.get('child_still_running') is False and row.get('returncode')==0 and not row.get('error') and not row.get('stop_reasons'),'parent window failed')
            D.require(row['build_receipt_sha256']==expected_hash and row['artifacts_sha256']==expected['artifacts'],'parent build identity differs')
            D.require(row['card']==0 and row['context']==4096 and row['gpu_count']==1,'parent placement differs')
            D.require(row['lane_admission']['passed'] and row['lane_admission']['scope']=='whole-host','parent host admission differs')
            boots.add(row['boot_id'])
            for leaf,digest in row['native_files'].items():
                D.require(pin(path/leaf)==digest,'native evidence hash differs')
            if stage=='WSCREEN':
                D.require(row['miss_path']=='zero-copy' and row['postload_memory']['complete_postload'] is True and row['postload_memory']['full_cache_bytes']==21552729600,'parent capacity/drain proof incomplete')
                D.require(pin(path/'host-memory.jsonl')==row['memory_samples_sha256'],'memory samples differ')
                for leaf,digest in row['postload_memory']['sources'].items():D.require(pin(path/leaf)==digest,'postload proof differs')
        summary=D.summarize_bracket(root/'WSCREEN/run',arm,manifest)
        D.require(summary==D.read(root/'WSCREEN/run/summary.json'),'native summary replay differs')
        summaries[arm]=summary
    D.require(summaries['smoke'].get('smoke_passed') is True,'smoke-d failed')
    D.require(len(boots)==1,'smoke/bracket boot differs')
    D.require(set(sources)==set(bindings),'evidence closure differs')
    D.require(all(D.sha(ROOT/n)==h for n,h in sources.items()),'evidence changed during read')
    print(json.dumps(dict(passed=True,smoke_passed=True,rows=summaries['max']['views'],native_artifacts={n:h for n,h in expected['artifacts'].items() if n in D.read(P/'copy-manifest.json')['native_artifacts']},build_sha256=expected_hash,boot_id=next(iter(boots)),sources=sources)))
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    main()
