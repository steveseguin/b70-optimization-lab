"""Fast mini-only SPEED2 full-state and deliberate-exclusion checks."""
import hashlib,json,os,time
from pathlib import Path
import pipeline as pipe
from cpu_merged_gate import Campaign,target_equal,assert_host_build
from strict_terminal_gate import state
from storage import admit,discard
P=Path(__file__).resolve().parent;E=P/'evidence/speed2'

def terminal(binary,root,rank,controller,prompt,count,guesses=(),eos=(),cut=-1,omit=False):
 admit(100_000_000);root.mkdir();transport=None
 args=pipe.parser().parse_args(['--binary',str(binary),'--output',str(root),'--mini','--context','256',
  '--draft','none','--draft-rank',str(rank),'--controller',controller,'--tokens',str(count),
  '--retain-steps','none','--cancel-launch',str(cut),'--dispatch',str(P/'dispatch-all-new.json')])
 args.host_memory='resident'
 row=dict(passed=False,draft_rank=rank,controller=controller,cancel_launch=cut,omit_required_extent=omit)
 try:
  transport=pipe.Transport(args,root)
  result=pipe.request_run(transport,pipe.Draft('script' if guesses else 'none',guesses),prompt,count,eos)
  if omit:
   transport.call(0,pipe.HALF,token=(result['tokens'][-1]+1)%16,position=len(prompt)+len(result['tokens'])-1,fixture=count+1,speculative=1)
   transport.call(0,12,token=2);transport.call(0,pipe.ROLLBACK)
  for rank_id in (0,1):transport.call(rank_id,pipe.DUMP,position=2147483647)
  signature,events=state(root)
  signature['shared-slot']=hashlib.sha256(transport.mapping[:pipe.SLOT]).hexdigest()
  snapshot=json.loads((root/'rank0/speculative-snapshot.json').read_text())
  assert snapshot['private_backup_zeroed'] and snapshot['private_host_backup_empty'] and not snapshot['snapshot_valid']
  transport.close(True);transport=None
  timings=[json.loads(x) for x in (root/'rank0/timings.jsonl').read_text().splitlines()]
  row.update(passed=True,tokens=result['tokens'],state=signature,raw_events=events,snapshot=snapshot,timings=timings)
  return row
 finally:
  if transport is not None:transport.stop('SPEED2 gate cleanup');transport.close(False)
  pipe.save(root/'speed2-owner.json',row)
  row['archive']=discard(root)

def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 binary=P/'build/gnu-host/own-rt-iq3';proof=assert_host_build(binary)
 receipt=dict(passed=False,device_executed=False,real_model=False,build=proof,rows=[],negative_controls=[],owners=[])
 c=Campaign(binary,P/'dispatch-all-new.json',E/'mini-cases.json')
 root=P/'build'/('speed2-terminal-'+str(time.time_ns()));root.mkdir();prompt=[2,5,3,7,1]
 try:
  for rank in (0,1):
   out,row=c.case(f'r{rank}-control',256,rank,'python',mode='none',count=3,prompt_tokens=prompt)
   reference=row['signature'];c.retain(out,row)
   for controller in ('python','native'):
    for label,options in [('hit',dict(mode='script',guesses=reference['tokens'])),
                          ('miss',dict(mode='script',guesses=[(t+1)%16 for t in reference['tokens']])),
                          ('mtp',dict(mode='mtp')),('mtp-wrong',dict(mode='mtp',fault='wrong'))]:
     out,row=c.case(f'r{rank}-{controller}-{label}',256,rank,controller,count=3,prompt_tokens=prompt,**options)
     target_equal(row['signature'],reference)
     if label=='hit':assert row['stats']['hits']>0 and row['stats']['misses']==0
     if label=='miss':assert row['stats']['misses']>0
     c.retain(out,row);receipt['rows'].append(dict(case=label,draft_rank=rank,controller=controller,full_state_equal=True))
    # A 32-token prompt puts the discarded half on the first capacity boundary.
    boundary_prompt=(prompt*7)[:32]
    base=terminal(binary,root/f'r{rank}-{controller}-reference',rank,controller,boundary_prompt,1)
    receipt['owners'].append(base)
    n=next(r['launches_issued'] for r in base['timings'] if r['position']==31)
    for cut in sorted({0,n//2,n,n+1}):
     actual=terminal(binary,root/f'r{rank}-{controller}-cut{cut}',rank,controller,boundary_prompt,2,
       [(base['tokens'][0]+1)%16],base['tokens'],cut)
     receipt['owners'].append(actual)
     assert actual['state']==base['state'] and actual['tokens']==base['tokens'],'terminal rollback changed full state'
     assert actual['snapshot']['captures']==actual['snapshot']['restores']==1
     receipt['rows'].append(dict(case='cancel-terminal-boundary',draft_rank=rank,controller=controller,cut=cut,full_state_equal=True))
    negative=terminal(binary,root/f'r{rank}-{controller}-omitted-streams',rank,controller,boundary_prompt,1,cut=n+1,omit=True)
    receipt['owners'].append(negative)
    assert negative['state']!=base['state'],'wrongly excluded output escaped full-state comparator'
    receipt['negative_controls'].append(dict(draft_rank=rank,controller=controller,extent='streams',required_extent_omitted=True,rejected=True))
  c.completed=True;c.seal()
  receipt.update(passed=True,cases=c.seal()['cases']+len(receipt['owners']),gate_count=len(receipt['rows'])+len(receipt['negative_controls']),
   protected_state='all plan and alternate allocation bytes, standalone scratch, invalid tails, host launch/bank/cache metadata and shared slot; only logical event telemetry differs',
   request_boundary='DUMP invokes snapshot boundary and full private-backup retirement; no model allocation is scrubbed',
   source_sha256={n:pipe.sha(P/n) for n in ('speed2_snapshot_gate.py','strict_snapshot.hpp','p39_plan.hpp','rank.hpp','main.cpp','request_state_inventory.hpp','pipeline.py','cpu_merged_gate.py','strict_terminal_gate.py')})
 finally:pipe.save(P/'speed2-snapshot-gates.json',receipt)
 print(json.dumps({k:receipt[k] for k in ('passed','cases','gate_count')}))
if __name__=='__main__':main()
