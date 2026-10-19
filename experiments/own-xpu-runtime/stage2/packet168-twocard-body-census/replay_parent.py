"""Replay REAL device token streams; do not fabricate missing census arms."""
import gzip,hashlib,json,math,statistics
from pathlib import Path
from census_contract import P,IDS,read,require
from build_engine import save,sha,limits
from analyze import analyze,historical_control
import suite_metrics

def load(path):
    raw=path.read_bytes();return json.loads(gzip.decompress(raw) if path.suffix=='.gz' else raw)
def rate(rows):
    classes={}
    for pid,r in rows:
        stamps=[x['completed_monotonic'] for x in r['timing_rows'][:100]]
        require(len(stamps)==100 and all(b>a for a,b in zip(stamps,stamps[1:])),'real parent event stream')
        value=99/(stamps[-1]-stamps[0]);classes.setdefault(suite_metrics.PROMPT_CLASSES[pid],[]).append(value)
    return statistics.median(statistics.median(v) for v in classes.values())
def main():
    limits();stage=P.parent;records=[];pins={}
    parent_roots=[('packet136',stage/'packet136-record-bundle/build/device-cards01-a/WS128/run','repeat-1'),
      ('packet163-a',stage/'packet163-full-gate/two-card/evidence/device-full512-B-a/run','requests'),
      ('packet163-b',stage/'packet163-full-gate/two-card/evidence/device-full512-B-b/run','requests')]
    # Include completed packet165 two-card runs, if they exist. Never pretend
    # an unrun proposal is real device evidence.
    for root in sorted((stage/'packet165-warm-prefill/two-card/evidence').glob('device-warm512-*/run')):
        if all((root/'requests'/i/'receipt.json').is_file() for i in IDS):parent_roots.append(('packet165-'+root.parent.name,root,'requests'))
    for label,root,sub in parent_roots:
        rows=[];control_checks=0
        for pid in IDS:
            path=root/sub/pid/'receipt.json'
            if not path.is_file():path=path.with_suffix('.json.gz')
            r=load(path);expected=read(P/'lineage/oracle128'/(pid+'.json'))['tokens']
            tokens=r['tokens'];require(tokens[:128]==expected[:min(128,len(tokens))],'real parent oracle prefix')
            require(r.get('cached_tokens')==0,'real parent cache')
            resets=[]
            for rank in(0,1):
                reset=root/sub/pid/f'rank{rank}/reset.json';resets.append(load(reset));pins[str(reset.relative_to(P.parents[3]))]=sha(reset)
            historical_control(r,pid,resets);control_checks+=1
            broken=dict(r,tokens=list(r['tokens']));broken['tokens'][0]^=1
            try:historical_control(broken,pid,resets)
            except ValueError:pass
            else:raise AssertionError('real parent oracle corruption accepted')
            pins[str(path.relative_to(P.parents[3]))]=sha(path);rows.append((pid,r))
        value=rate(rows)
        if label=='packet136':require(math.isclose(value,58.798108759182306,rel_tol=1e-12),'record replay drift')
        # Preserve the actual token/timing stream in a compact private packet
        # for future parser regressions; this is historical evidence only.
        compact=[dict(prompt_id=i,tokens=r['tokens'],timing_rows=r['timing_rows'],cached_tokens=r['cached_tokens'])for i,r in rows]
        blob=json.dumps(compact,separators=(',',':')).encode()
        target=P/'lineage'/f'{label}-streams.json.gz';target.write_bytes(gzip.compress(blob,mtime=0))
        records.append(dict(parent=label,real_device_evidence=True,prompt_count=len(rows),
          exact_oracle_prefix=True,primary_tok_s=value,census_class_costs=None,actual_census_control_validator_checks=control_checks,
          reason='No class differencing/restore stream in parent; cannot rank classes',
          retained_stream_sha256=sha(target)))
    save(P/'evidence/real-parent-replay.json',dict(passed=True,device_executed=False,
      new_performance_measurement=False,records=records,source_sha256=pins))
    print('PASS real parent streams:',[(r['parent'],r['primary_tok_s'])for r in records])
if __name__=='__main__':main()
