#!/usr/bin/env python3
"""Read-only comparison of Python/native CPU or coordinator-window receipts."""
import argparse, hashlib, json
from pathlib import Path

def inventory_evidence(root):
    """Keep raw scheduler bookkeeping beside model-state comparisons."""
    rows={}
    for rank in (0,1):
        path=root/f'rank{rank}/request-state-inventory.json'
        if path.exists():
            raw=path.read_bytes();row=json.loads(raw)
            rows[str(rank)]=dict(raw_sha256=hashlib.sha256(raw).hexdigest(),logical_event=row['logical_event'])
    return rows

def signature(root):
    r=json.loads((root/'receipt.json').read_text())
    assert r['passed'],f'failed source receipt: {root}'
    assert all(k in r for k in ('tokens','stats','guess_sequence','guess_rows')),'missing controller sequence evidence'
    target={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for rank in (0,1) for p in sorted((root/f'rank{rank}').glob('step*/layer-*.bf16'))}
    assert target,'missing target fixtures'
    final={}
    for rank in (0,1):
        state=root/f'rank{rank}/state-2147483647/state.json'
        if state.exists():final[str(rank)]=json.loads(state.read_text())
    final_bytes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for rank in (0,1) for p in sorted((root/f'rank{rank}/state-2147483647').rglob('*')) if p.is_file() and p.name!='state.json'}
    inventories={}
    for rank in (0,1):
        path=root/f'rank{rank}/request-state-inventory.json'
        if path.exists():
            row=json.loads(path.read_text());row.pop('logical_event')
            inventories[str(rank)]=row
    draft={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for rank in (0,1) for p in sorted((root/f'rank{rank}/draft-final-state').rglob('*')) if p.is_file()}
    return dict(tokens=r['tokens'],guess_sequence=r['guess_sequence'],hit_miss_sequence=[{k:row[k] for k in ('position','guess','actual','hit')} for row in r['guess_rows']],
                counts={k:r['stats'][k] for k in ('guesses','hits','misses','no_guess')},fixtures=target,final_states=final,final_state_bytes=final_bytes,request_state_inventories=inventories,draft_final_state=draft)

def main():
    p=argparse.ArgumentParser();p.add_argument('--python',type=Path,required=True);p.add_argument('--native',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--require-final-state',action='store_true');a=p.parse_args()
    left,right=signature(a.python),signature(a.native)
    differences=[k for k in left if left[k]!=right[k]]
    if a.require_final_state:
        if len(left['final_states'])!=2:differences.append('missing final target states')
        for rank in (0,1):
            if not any(k.startswith(f'rank{rank}/state-2147483647/') and k.endswith('.bin') for k in left['final_state_bytes']):differences.append(f'missing rank{rank} final target bytes')
    result=dict(passed=not differences,python=str(a.python),native=str(a.native),differences=differences,tokens=len(left['tokens']),fixture_files=len(left['fixtures']),final_state_ranks=len(left['final_states']),no_speed_claim=True,raw_inventory_records=dict(python=inventory_evidence(a.python),native=inventory_evidence(a.native)),bookkeeping_normalization='Only logical_event omitted from model-state signature; raw counter and inventory hash retained')
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(bool(differences))
if __name__=='__main__':main()
