"""Recompute the diagnostic bracket from every native token and sealed receipt."""
import json
import math
from pathlib import Path
import window as W
import queue_runner as Q
import suite_driver as D
from views import digest
P=Path(__file__).resolve().parent
METRIC='class_balanced_tok_s_1_100_intervals_after_ttft'
RECORD=24.338653323339745


def verify_arm(root,view):
    root=Path(root).resolve()
    W.require(root.is_relative_to(P/'evidence'),'arm outside packet evidence')
    q=D.read(root/'queue.json')
    W.require(q.get('passed') is True and q.get('completed')==list(Q.ORDER) and q.get('view')==view,'incomplete/wrong-view screen')
    pins={str(root/'queue.json'):D.sha(root/'queue.json')};boot=None;owners=[]
    for name in Q.ORDER:
        path=root/name/'window.json';r=Q.verify_success(name,root,0,0)
        W.require(r.get('view')==view and r.get('selection_sha256')==digest(view),'selection differs')
        W.require(r.get('build_receipt_sha256')==D.sha(P/'build-receipt.json'),'sealed build differs')
        W.require(r.get('artifacts_sha256')==D.read(P/'build-receipt.json')['artifacts'],'binary identity differs')
        W.verify_files(path.parent,r['native_files'])
        for leaf in ('kernel-before.jsonl','kernel-window.jsonl'):
            W.require(leaf in r['native_files'] and not W.S.FAULT.search((path.parent/leaf).read_text()),'kernel evidence missing/faulted')
        if name.startswith('K1'): W.prerequisite(path,'K1',r)
        else:
            expected={str(f.relative_to(path.parent)) for f in (path.parent/'run').rglob('*') if f.is_file()} | {'summary.json','kernel-before.jsonl','kernel-window.jsonl'}
            W.require(set(r['native_files'])==expected,'native closure differs')
            proof=r.get('postload_memory',{})
            W.require(proof.get('complete_postload') is True,'complete post-load proof required')
            W.verify_files(path.parent,proof['sources'])
            W.require(D.sha(path.parent/'host-memory.jsonl')==r.get('memory_samples_sha256'),'memory samples changed')
        if boot is None:boot=r['boot_id']
        W.require(r['boot_id']==boot,'arm boot changed')
        owners.append((r['pid'],r['process_start_ticks']))
        pins[str(path)]=D.sha(path)
    W.require(len(set(owners))==3,'fresh K1 and model owners required')
    k1=[root/n/'window.json' for n in ('K1a','K1b')]
    miss=W.selected_miss_path(k1,r)
    W.require(r['miss_path']==miss,'screen did not use K1-selected path')
    expected_refs=[dict(path=str(p),sha256=D.sha(p),native_k1_sha256=D.sha(p.parent/'run/k1.json')) for p in k1]
    W.require(r.get('k1_refs')==expected_refs,'K1 provenance differs')
    manifest=D.oracle_inputs();summary=D.summarize(root/'WSCREEN/run','WSCREEN',manifest)
    stored=D.read(root/'WSCREEN/run/summary.json')
    native=D.read(root/'WSCREEN/run/run/receipt.json')
    W.require(native.get('selection_sha256')==digest(view),'native selection differs')
    W.require(stored[METRIC]==summary[METRIC] and stored.get('view')==view,'stored metric/view differs')
    W.require(stored.get('timing_claim_eligible') is False and stored.get('submission_eligible') is False,'screen mislabeled')
    summary.update(miss_path=miss,owners=owners,view=view)
    return summary,pins,boot


def decision(rows):
    W.require(len(rows)==3,'complete production/port/production bracket required')
    rates=[r[METRIC]['median'] for r in rows]
    W.require(all(type(v) in (float,int) and math.isfinite(v) and v>0 for v in rates),'invalid speed')
    signatures=[[(r['prompt_id'],r['prompt_token_sha256'],r['tokens']) for r in row['requests']] for row in rows]
    W.require(signatures[0]==signatures[1]==signatures[2],'bracket tokens differ')
    W.require(len({r['miss_path'] for r in rows})==1,'K1 miss paths differ; unmatched bracket')
    drift=max(rates[0],rates[2])/min(rates[0],rates[2])-1
    return dict(passed=True,qualifies_for_full_chain=rates[1]>max(rates[0],rates[2],RECORD) and drift<=0.03,
        rates=rates,control_drift=drift,control_drift_limit=0.03,previous_record=RECORD,
        evidence_label='screen',submission_eligible=False,realistic_final_gate=dict(passed=False,reason='128-token diagnostic screen'),
        independent_port_model_launches=1,quality='every token vs unchanged packet49 oracle; no layer-byte or fresh-process repeat gate',
        policy='Beat both controls and saved record, controls within 3%; then consider frozen 58j full chain. No retry or headline.')


def compare(root):
    W.build_gate();rows=[];pins={};boots=[]
    for name,view in Q.STAGES:
        row,files,boot=verify_arm(Path(root)/name,view);rows.append(row);pins.update(files);boots.append(boot)
    W.require(len(set(boots))==1,'matched bracket boot differs')
    W.require(len({tuple(x) for row in rows for x in row['owners']})==9,'owners reused between arms')
    return dict(decision(rows),sources=pins,build_receipt_sha256=D.sha(P/'build-receipt.json'))
