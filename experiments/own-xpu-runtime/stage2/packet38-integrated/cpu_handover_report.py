#!/usr/bin/env python3
"""Report CPU handover diagnostics from already-qualified host window receipts."""
import argparse,json,math,statistics
from pathlib import Path
from seal import P,B,sha,archived_run

def stats(values):
    assert values and all(math.isfinite(x) and x>=0 for x in values)
    ordered=sorted(values)
    return dict(samples=len(values),median_us=statistics.median(values),p95_nearest_rank_us=ordered[math.ceil(.95*len(ordered))-1],values_us=values)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('scratch_root',type=Path);a=ap.parse_args()
    archive,table=archived_run(a.scratch_root)
    gate=json.loads((P/'window-cpu-models.json').read_text());assert gate['passed'] and not gate['device_executed']
    binary_sha=sha(B/'gnu-host/own-rt-iq3');assert gate['binary_sha256']==binary_sha
    rows=[];tokens=[]
    for controller in ('python','native'):
        name=f'W2s-{controller}/receipt.json';record=json.loads(table[name]['text'])
        assert record['passed'] and record['device_executed'] is False and record['binary_sha256']==binary_sha
        assert record['controller']==controller and record['draft']=='none'
        tokens.append(record['tokens'])
        forward=[r['rank0_to_rank1_handover_ms']*1000 for r in record['timing_rows'] if r.get('rank0_to_rank1_handover_ms') is not None]
        reverse=[r['rank1_to_rank0_handover_ms']*1000 for r in record['timing_rows'] if r.get('rank1_to_rank0_handover_ms') is not None and not r.get('rank1_to_rank0_overlapped')]
        rows.append(dict(controller=controller,receipt=name,receipt_sha256=table[name]['sha256'],
                         rank0_finish_to_rank1_start=stats(forward),rank1_finish_to_next_rank0_start=stats(reverse)))
    assert tokens[0]==tokens[1]
    micro=json.loads((P/'native-controller-cpu.json').read_text());assert micro['passed'] and not micro['device_executed']
    result=dict(passed=True,device_executed=False,no_speed_claim=True,binary_sha256=binary_sha,
                source_sha256={n:sha(P/n) for n in ('cpu_handover_report.py','pipeline.py')},
                archive=str(archive.relative_to(P)),archive_sha256=sha(archive),window_gate_sha256=sha(P/'window-cpu-models.json'),rows=rows,
                two_thread_microbenchmark=dict(receipt_sha256=sha(P/'native-controller-cpu.json'),handover=micro['cpu_handover'],mailbox=micro['cpu_mailbox_wakeup']),
                scope='one fresh two-rank miniature CPU window per controller, draft none, retained fixtures and full state capture enabled; observed host gap includes rank handover/capture/scheduling work; eight forward samples, diagnostic only; no cross-server speed verdict or GPU prediction',
                definition='forward: rank1 start at position minus rank0 finish at same position; reverse: next rank0 start using verified token minus rank1 finish, excluding speculative overlap and terminal rollback')
    real=[];real_tokens=[]
    for controller,name in (('python','real-none.json'),('native','real-native-none.json')):
        gate_path=P/name;gate=json.loads(gate_path.read_text())
        assert gate['passed'] and gate['binary_sha256']==binary_sha
        archive,table=archived_run(gate['root']);r=json.loads(table['receipt.json']['text'])
        assert r['passed'] and r['device_executed'] is False and r['controller']==controller and r['draft']=='none' and r['binary_sha256']==binary_sha
        if controller=='native':
            assert gate['python_receipt_sha256']==sha(P/'real-none.json')
            assert gate['native_receipt_sha256']==table['receipt.json']['sha256']
        real_tokens.append(r['tokens'])
        values=[v['rank0_to_rank1_handover_ms']*1000 for v in r['timing_rows'] if v.get('rank0_to_rank1_handover_ms') is not None]
        real.append(dict(controller=controller,gate=name,gate_sha256=sha(gate_path),archive=str(archive.relative_to(P)),archive_sha256=sha(archive),
                         receipt_sha256=table['receipt.json']['sha256'],rank0_finish_to_rank1_start=stats(values)))
    assert real_tokens[0]==real_tokens[1] and len(real_tokens[0])==8
    result['real_model_none']=dict(rows=real,scope='one fresh real-model host rank pair per controller, eight generated tokens, retained layer fixtures and final state; full observed handover gap including host scheduling/prepared work; diagnostic only, no speed verdict or GPU prediction')
    (P/'cpu-handover-cost.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({r['controller']:r['rank0_finish_to_rank1_start']['median_us'] for r in rows}))
if __name__=='__main__':main()
