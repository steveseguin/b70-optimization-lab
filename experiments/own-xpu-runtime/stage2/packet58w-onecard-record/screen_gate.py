#!/usr/bin/env python3
"""Read 58v's real runner outputs, rehash closures and replay every native token."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
V=P.parent/'packet58v-async-cache'
# Isolated process: imports must be the frozen parent's own implementation.
sys.path.insert(0,str(V))
import window as W
import queue_runner as Q
import suite_driver as D
from shared_oracle import completed_binding

def main():
    seal=W.build_gate();sources={};boots=set();summaries={}
    expected=json.loads((P/'lineage/58v-build-receipt.json').read_text())
    W.require(seal==expected,'58v build changed after preparation')
    completed_binding()
    def pin(path):
        digest=W.sha(path);sources[str(path.relative_to(ROOT))]=digest;return digest
    pin(V/'build-receipt.json')
    for arm in ('smoke','overlap'):
        root=Q.ROOT/arm
        queue=D.read(root/'queue.json');pin(root/'queue.json')
        W.require(queue.get('passed') is True and queue.get('completed')==list(Q.ORDER) and queue.get('running') is None and not queue.get('error') and not queue.get('child_still_running'),'parent queue incomplete: '+arm)
        for stage in Q.ORDER:
            receipt=Q.verify_success(stage,root,0,0);path=root/stage
            W.require(receipt['build_receipt_sha256']==W.sha(V/'build-receipt.json') and receipt['artifacts_sha256']==seal['artifacts'],'parent window build differs')
            W.require(receipt.get('returncode')==0 and not receipt.get('error'),'parent window failed')
            pin(path/'window.json');boots.add(receipt['boot_id'])
            expected_closure={'summary.json','kernel-before.jsonl','kernel-window.jsonl'}
            if stage.startswith('K1'):expected_closure|={'run/k1.json','run/k1-cases.jsonl'}
            else:expected_closure|={str(f.relative_to(path)) for f in (path/'run').rglob('*') if f.is_file()}
            W.require(set(receipt['native_files'])==expected_closure,'parent native closure incomplete')
            W.verify_files(path,receipt['native_files'])
            for leaf,digest in receipt['native_files'].items():
                W.require(pin(path/leaf)==digest,'parent native evidence changed')
            for leaf in ('kernel-before.jsonl','kernel-window.jsonl'):
                W.require(not W.S.FAULT.search((path/leaf).read_text()),'parent fault evidence')
            if stage.startswith('K1'):
                k=W.k1_summary(D.read(path/'run/k1.json'))
                W.require(k['selected_miss_path']=='zero-copy','parent K1 not zero-copy')
            else:
                W.require(receipt['miss_path']=='zero-copy','parent miss path differs')
                W.require(receipt['postload_memory'].get('complete_postload') is True,'parent full postload census missing')
                W.verify_files(path,receipt['postload_memory']['sources'])
                W.require(pin(path/'host-memory.jsonl')==receipt['memory_samples_sha256'],'parent memory samples changed')
                for leaf,digest in receipt['postload_memory']['sources'].items():W.require(pin(path/leaf)==digest,'postload evidence changed')
        summary=D.summarize_bracket(root/'WSCREEN/run',arm,D.oracle_inputs())
        W.require(summary==D.read(root/'WSCREEN/run/summary.json'),'parent summary differs from native replay')
        summaries[arm]=summary
    W.require(summaries['smoke'].get('smoke_passed') is True,'smoke failed')
    W.require(len(boots)==1,'smoke and bracket boots differ')
    W.require(all(W.sha(ROOT/n)==h for n,h in sources.items()),'parent evidence changed during replay')
    print(json.dumps(dict(passed=True,smoke_passed=True,rows=summaries['overlap']['views'],native_artifacts=seal['artifacts'],build_sha256=W.sha(V/'build-receipt.json'),boot_id=next(iter(boots)),sources=sources)))
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
