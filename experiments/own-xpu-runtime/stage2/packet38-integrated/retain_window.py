#!/usr/bin/env python3
"""Compare finished coordinator pairs, retain verified evidence, remove raw scratch."""
import argparse,gzip,hashlib,json
from pathlib import Path
from compare_controllers import signature
from storage import P,B,discard,digest

PAIRS=('W2s','W2m','W2d','W2n','W2x','W2mc')

def require(condition,message):
    if not condition:raise ValueError(message)

def save(path,value):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n')
    temporary.replace(path)

def finished(root,pair):
    row=json.loads((root/'window.json').read_text())
    require(row['passed'] is True,'failed window retains ownership/evidence')
    require(row['window'] in (PAIRS if pair else ('WS','WSs')),'prerequisites cannot be removed')
    receipts=row.get('receipts',{})
    require('run/receipt.json' in receipts,'window run receipt binding missing')
    for name,expected in receipts.items():
        path=root/name
        require(path.resolve().is_relative_to(root) and not path.is_symlink(),'receipt escapes window')
        require(digest(path)==expected,'window receipt hash mismatch: '+name)
    run=root/'run';request=json.loads((run/'receipt.json').read_text())
    require(request.get('passed') is True,'unfinished or failed run')
    owner=run if pair else run/'ranks'
    ownership=json.loads((owner/'ownership.json').read_text())
    require(ownership.get('retained_pids')==[] and ownership.get('returncodes')==[0,0],'window still owns ranks')
    for rank in (0,1):
        path=owner/f'rank{rank}/receipt.json'
        require(str(path.relative_to(root)) in receipts,'rank receipt binding missing')
        closed=json.loads(path.read_text());teardown=closed.get('teardown',[])
        require(closed.get('passed') is True and closed.get('rank')==rank and len(teardown)==1 and
                teardown[0].get('safe_to_exit') is True and teardown[0].get('live_bytes')==0 and teardown[0].get('in_flight')==0,'rank teardown incomplete')
    for entry in row.get('retained_artifacts',{}).values():
        path=root/entry['path']
        require(path.resolve().is_relative_to(root) and not path.is_symlink(),'compressed evidence escapes window')
        require(digest(path)==entry['sha256'],'compressed evidence hash mismatch')
        h=hashlib.sha256();size=0
        with gzip.open(path,'rb') as source:
            for chunk in iter(lambda:source.read(1024*1024),b''):h.update(chunk);size+=len(chunk)
        require(h.hexdigest()==entry['uncompressed_sha256'] and size==entry['uncompressed_bytes'],'compressed evidence content mismatch')
    return row,request

def check_target_state(run,state):
    require(set(state['final_states'])=={'0','1'},'final state proof missing')
    for rank in (0,1):
        recorded=state['final_states'][str(rank)]['buffers']
        require(recorded,'empty target state inventory')
        for name,expected in recorded.items():
            leaf=('alternate-'+name[len('alternate:'):] if name.startswith('alternate:') else name)+'.bin'
            key=f'rank{rank}/state-2147483647/{leaf}'
            require(state['final_state_bytes'].get(key)==expected,'missing or changed target state bytes: '+key)
    require(all(any(k.startswith(f'rank{rank}/step') for k in state['fixtures']) for rank in (0,1)),'rank fixture evidence missing')

def check_suite(root,window,summary):
    run=root/'run';stored=json.loads((run/'summary.json').read_text())
    require(window.get('summary')==stored==summary and bool(summary.get('rows')),'suite summary binding missing')
    proof=[]
    for row in summary['rows']:
        require(row.get('passed') is True,'failed suite request')
        receipt=run/row['receipt'];require(receipt.resolve().is_relative_to(run),'suite receipt escapes run')
        require(str(receipt.relative_to(root)) in window['receipts'],'suite request receipt not bound')
        request=json.loads(receipt.read_text())
        require(request.get('passed') is True and request.get('oracle_check',{}).get('passed') is True,'suite exactness receipt missing')
        require(request['prompt_id']==row['prompt_id'] and request['repeat']==row['repeat'],'suite request identity mismatch')
        from suite_export import retained_state_binding
        state=retained_state_binding(receipt.parent)
        expected_steps={f'step{i}' for i in range(1,min(len(request['tokens']),8)+1)}
        require({d.name for d in receipt.parent.glob('step*') if d.is_dir()}==expected_steps,'suite fixture steps missing')
        fixtures=0
        for step in expected_steps:
            directory=receipt.parent/step
            inventory=[json.loads(line) for line in (directory/'layers.jsonl').read_text().splitlines()]
            require([r['layer'] for r in inventory]==list(range(48)),'suite fixture layers missing')
            for item in inventory:
                path=directory/f"layer-{item['layer']:02}.bf16"
                require(path.stat().st_size==20480 and digest(path)==item['sha256'],'suite fixture hash differs')
                fixtures+=1
        proof.append(dict(prompt_id=row['prompt_id'],repeat=row['repeat'],tokens=len(request['tokens']),fixtures=fixtures,**state))
    return dict(requests=proof,no_speed_claim=True)

def retain(roots, pair=False):
    inputs=[Path(r) for r in roots]
    require(all(not root.is_symlink() for root in inputs),'symlink window refused')
    roots=[root.resolve() for root in inputs]
    require(len(roots)==(2 if pair else 1) and len(set(roots))==len(roots),'window count/identity')
    records=[];requests=[]
    for root in roots:
        require(root.parent==B and root.is_dir(),'only direct packet build children')
        row,request=finished(root,pair);records.append(row);requests.append(request)
    if pair:
        require(records[0]['window']==records[1]['window'],'window class mismatch')
        for key in ('card','boot_id','artifacts_sha256','build_receipt_sha256','dispatch_sha256','oracle_hashes','expected_tokens','prompt_overlap'):
            require(key in records[0] and records[0][key]==records[1].get(key),'pair identity mismatch: '+key)
        left,right=[signature(root/'run') for root in roots]
        for root,state in zip(roots,(left,right)):
            check_target_state(root/'run',state)
            if records[0]['window'] in ('W2m','W2mc'):
                expected={f'rank1/draft-final-state/{name}.bin' for name in ('blk.0.qsa.keys','blk.0.qsa.values','blk.0.qsa.raw','blk.0.qsa.pooled','position')}
                require(expected<=set(state['draft_final_state']),'draft final-state proof missing')
        require(left==right,'controller token/guess/state/fixture difference')
        for row,request,controller in zip(records,requests,('python','native')):
            require(request['controller']==controller,'controller ordering')
            require(request['tokens']==row['expected_tokens'],'window oracle token mismatch')
            actual={name.split('/',1)[1]:h for name,h in left['fixtures'].items()}
            require(actual==row['oracle_hashes'] and row['layer_matches']==len(actual),'window oracle fixture mismatch')
        proof=dict(tokens=len(left['tokens']),fixtures=len(left['fixtures']),final_state_ranks=2,
                   signature=left,no_speed_claim=True)
    else:proof=check_suite(roots[0],records[0],requests[0])
    name=records[0]['window']+('-controller-parity-retention' if pair else '-retention')
    receipt=P/'evidence'/(name+'.json');receipt.parent.mkdir(exist_ok=True)
    require(not receipt.exists(),'unique window retention receipt required')
    result=dict(passed=False,comparison_passed=True,retention_complete=False,device_executed=False,meaning='offline comparison/retention only',
                windows=[dict(path=str(r),window_sha256=digest(r/'window.json')) for r in roots],proof=proof,archives=[])
    # Publish verified comparison before deletion; incomplete archiving never reports pass.
    save(receipt,result)
    for root in roots:
        result['archives'].append(discard(root));save(receipt,result)
    result.update(passed=True,retention_complete=True);save(receipt,result)
    return result

def main():
    ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--pair',choices=PAIRS);g.add_argument('--suite',choices=('WS','WSs'));a=ap.parse_args()
    roots=[B/(a.pair+'-'+c) for c in ('python','native')] if a.pair else [B/a.suite]
    result=retain(roots,pair=bool(a.pair));print(json.dumps(dict(passed=True,retention_complete=result['retention_complete'],archives=result['archives'])))
if __name__=='__main__':main()
