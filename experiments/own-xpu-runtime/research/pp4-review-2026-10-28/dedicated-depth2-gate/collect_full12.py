"""Offline full12 composition; invoke only after terminal and passive postflight."""
from pathlib import Path
import argparse,json,hashlib
p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('destination',type=Path);a=p.parse_args()
def read(p):return json.loads(p.read_text())
def need(x,s):
 if not x:raise ValueError(s)
need(not a.destination.exists(),'fresh exclusive summary')
r=a.root;o=r/'output';terminal=read(o/'terminal.json');post=read(r/'postflight.json')
need(terminal['passed'] and terminal.get('error')is None and terminal['requests']==12 and not terminal['live_pids'] and len(terminal['returncodes'])==4 and all(v==0 for v in terminal['returncodes'].values()),'complete clean terminal')
need(post['known_fault_baseline_matches'] and not post['holders'],'clean passive postflight')
plan=read(r/'plan.json');driver=read(o/'driver-result.json');reference=Path('/dev/shm/sc117-gpu-route-seven-plus-twelve-20261028-r1/output/result.json');refs=read(reference)['phase_B_records'];records=driver['request_results'];need(len(records)==len(refs)==12,'twelve actual records')
rows=[]
for i,(record,ref,prompt) in enumerate(zip(records,refs,plan['dedicated_requests'])):
 result=record['result'];ids=result['output_ids'];elapsed=result['emitted_elapsed_seconds'];need(record['id']==ref['id']==prompt['id'] and prompt['prompt_tokens']==ref['prompt_tokens'],'actual prompt identity');need(ids==ref['actual_output_ids'],'all actual output IDs');need(len(ids)==len(elapsed) and len(ids)>1,'actual emission intervals');need(len(ids)==512 or ids[-1] in ref['eos_token_ids'],'actual EOS termination');need(not result['scripted_oracle_assisted'],'runtime has no oracle')
 cold=o/f'request-{i:02d}'/'cold-proof.json'
 if i:need(read(cold)['passed'] is True,'each transition cold proof')
 duration=elapsed[-1]-elapsed[0];need(duration>0,'positive full decode interval')
 rows.append(dict(index=i,id=record['id'],prompt_sha256=hashlib.sha256(bytes().join(int(t).to_bytes(4,'little',signed=True) for t in prompt['prompt_tokens'])).hexdigest(),output_tokens=len(ids),actual_eos=len(ids)<512,request_wall_seconds=result['scheduler_wall_seconds'],ttft_seconds=elapsed[0],decode_intervals=len(ids)-1,full_decode_seconds=duration,full_decode_tokens_per_second=(len(ids)-1)/duration,prefill_timing=result['prefill_timing'],cold_proof=str(cold)if i else str(o/'cold-proof.json')))
summary=dict(schema='ownrt.dedicated-full12-offline-summary.v1',passed=True,root=str(r),depth=plan['speculative_depth'],reference=str(reference),reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),scope='All12 actual prompts/outputs vs saved CPU-qualified generic outputs; perrequest wall excludes separate cold reset/loading. Full n-1 emission intervals, not tail window. First pair is screening only.',requests=rows,request_wall_seconds=sum(x['request_wall_seconds']for x in rows),decode_intervals=sum(x['decode_intervals']for x in rows),decode_seconds=sum(x['full_decode_seconds']for x in rows),lifecycle_phases=terminal['lifecycle_phases'],owner_lifetime_wall_seconds=terminal['wall_seconds'])
a.destination.write_text(json.dumps(summary,indent=2)+'\n')
