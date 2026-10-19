#!/usr/bin/env python3
"""Replay finished 58aj smoke/v5 receipts using a privately vendored reader."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
sys.path.insert(0,str(P/'screen'))
import suite_driver as D
from fault_review import fault_lines
ORDER=('K1a','K1b','WSCREEN')
def main():
    expected=D.read(P/'screen/build-receipt.json')
    expected_hash=D.sha(P/'screen/build-receipt.json')
    V=P/'screen/evidence/card0-58ajb-screen-a'
    sources={};boots=set();summaries={};queues={}
    def pin(path):
        name=str(path.relative_to(ROOT));digest=D.sha(path)
        D.require(name not in sources or sources[name]==digest,'evidence changed while reading')
        sources[name]=digest;return digest
    manifest=D.oracle_inputs()
    for arm in ('smoke','resident'):
        root=V/arm;pin(root/'queue.json');queue=D.read(root/'queue.json')
        D.require(queue.get('passed') is True and queue.get('completed')==list(ORDER) and queue.get('running') is None and not queue.get('error'),'parent queue incomplete')
        D.require(queue.get('arm')==arm and queue.get('view')==arm,'parent arm differs')
        # Parent queue.json has no ended timestamp recognized by the shared
        # pin guard. Retain its exact bytes as a snapshot, just as we retain
        # the parent's mutable build manifest; never pin it as immutable code.
        raw=(root/'queue.json').read_text()
        D.require(hashlib.sha256(raw.encode()).hexdigest()==sources[str((root/'queue.json').relative_to(ROOT))],'queue snapshot changed')
        queues[arm]=dict(raw_json=raw,digest_sha256=sources[str((root/'queue.json').relative_to(ROOT))])
        for stage in ORDER:
            path=root/stage;pin(path/'window.json');row=D.read(path/'window.json')
            D.require(row.get('passed') is True and row.get('device_executed') is True and row.get('child_still_running') is False and row.get('returncode')==0 and not row.get('error') and not row.get('stop_reasons'),'parent window failed')
            D.require(row['build_receipt_sha256']==expected_hash and row['artifacts_sha256']==expected['artifacts'],'parent build identity differs')
            D.require(row['card']==0 and row['context']==4096 and row['gpu_count']==1,'parent placement differs')
            D.require(row['lane_admission']['passed'] and row['lane_admission']['scope']=='whole-host','parent whole-host admission differs')
            boots.add(row['boot_id'])
            closure={'summary.json','kernel-before.jsonl','kernel-window.jsonl'}
            closure.update(str(p.relative_to(path)) for p in (path/'run').rglob('*') if p.is_file())
            D.require(set(row['native_files'])==closure,'parent native evidence closure incomplete')
            for leaf,digest in row['native_files'].items():
                D.require(not Path(leaf).is_absolute() and '..' not in Path(leaf).parts,'unsafe native evidence path')
                D.require(pin(path/leaf)==digest,'native evidence hash differs')
            for leaf in ('kernel-before.jsonl','kernel-window.jsonl'):
                D.require(not fault_lines((path/leaf).read_text()),'parent window has GPU fault evidence')
            if stage=='WSCREEN':
                D.require(row['miss_path']=='zero-copy' and row['postload_memory']['complete_postload'] is True and row['postload_memory']['full_cache_bytes']==21552729600,'parent capacity/drain proof incomplete')
                D.require(pin(path/'host-memory.jsonl')==row['memory_samples_sha256'],'memory samples differ')
                for leaf,digest in row['postload_memory']['sources'].items():D.require(pin(path/leaf)==digest,'postload proof differs')
        if arm=='smoke':
            for name in ('first-minute-analysis.json','first-result-analysis.json'):
                report=D.read(root/'WSCREEN/run'/name)
                D.require(report.get('passed') is True and report.get('driver_schema_checked') is True,'smoke own-output analyzer missing/failed')
                if name=='first-result-analysis.json':D.require(report.get('complete_exact_requests',0)>0,'smoke analyzer never checked a completed request')
        D.verify_lookup_views(root/'WSCREEN/run',arm)
        summary=D.summarize_bracket(root/'WSCREEN/run',arm,manifest)
        D.require(summary==D.read(root/'WSCREEN/run/summary.json'),'native summary replay differs')
        summaries[arm]=summary
    D.require(summaries['smoke'].get('smoke_passed') is True,'smoke failed')
    D.require(len(boots)==1,'smoke/bracket boot differs')
    D.require(next(iter(boots))==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'same-hold chain requires current bracket boot')
    D.require(all(D.sha(ROOT/n)==h for n,h in sources.items()),'evidence changed during read')
    completed={n:h for n,h in sources.items() if not n.endswith('/queue.json')}
    print(json.dumps(dict(passed=True,smoke_passed=True,rows=summaries['resident']['views'],native_artifacts=expected['artifacts'],build_sha256=expected_hash,boot_id=next(iter(boots)),sources=completed,queue_snapshots=queues)))
if __name__=='__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
