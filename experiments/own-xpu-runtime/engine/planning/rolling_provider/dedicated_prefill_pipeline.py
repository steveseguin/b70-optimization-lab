"""Bounded target-stage/OP28 pipeline. Native arithmetic and wire are unchanged."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from hashlib import sha256
import json
from pathlib import Path
import struct
import time
from . import dedicated_prefill as P,prefill
from .transport import pending,ring,base


def run(stages,provider,model,plan,output,*,source,stop_requested=None):
    P.need(len(stages)==3 and plan.get('dedicated_prefill_pipeline') is True,
           'explicit three-target dedicated prefix pipeline')
    rows=plan['prefill_rows'];bulk=len(model.prompt)-2;stream=provider.stream_bytes
    prompt_sha=bytes.fromhex(source['sha256']);total=(bulk+rows-1)//rows
    began=time.monotonic();next_chunk=[0]*4;completed=[set() for _ in range(4)]
    busy={};leases={};snapshots={};target_wall=[0.]*3;replay_wall=0.;last_ack=None;peak=0

    def target(index,k):
        stage=stages[index];start=k*rows;count=min(rows,bulk-start);parity=k%2
        if index==0:
            stage.prefill[16:16+4*count]=struct.pack(f'<{count}i',*model.prompt[start:start+count])
        else:
            kind='forward' if index==1 else 'reverse'
            prefill.region(stage.prefill,'forward',parity,rows,stream,count)[:]=prefill.region(stages[index-1].prefill,kind,parity,rows,stream,count)
        position=start+count-1
        row=ring.Row(model.epoch,position+1,position,position,model.prompt[position],0,model.request,
                     model.proposals.hashes[position],model.proposals.hashes[position+1])
        metadata=prefill.verified_metadata(pending.wire,row,index,index==2)
        stage.shared[pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+len(metadata)]=metadata
        t=time.monotonic();reply=stage.command(15,count,start,parity);end=time.monotonic()
        P.need(reply[3]==count*stream,'actual target chunk completion extent')
        off=P.RECORD_OFFSET+parity*P.RECORD_BYTES
        return dict(sequence=stage.sequence,reply=base.REPLY.pack(*reply).hex(),began=t,end=end,
                    record=bytes(stage.prefill[off:off+P.RECORD_BYTES]) if index in (0,2) else None)

    def replay(k):
        start=k*rows;count=min(rows,bulk-start);parity=k%2;parts=snapshots[k]
        seed,final=parts[0]['record'],parts[2]['record'];sequences=[p['sequence'] for p in parts]
        off=P.RECORD_OFFSET+parity*P.RECORD_BYTES
        raw_sha=sha256(prefill.region(stages[2].prefill,'reverse',parity,rows,stream,count)).digest()
        common=dict(stages=3,start=start,count=count,rows=rows,stream=stream,parity=parity,
            epoch=model.epoch,request=model.request,prompt_sha=prompt_sha,before=model.proposals.hashes[start],
            after=model.proposals.hashes[start+count],prompt=model.prompt,raw_sha=raw_sha)
        seed_sha=P.chunk_record(seed,role=1,stage=0,sequence=sequences[0],**common)
        final_sha=P.chunk_record(final,role=2,stage=2,sequence=sequences[2],**common)
        P.need(seed==bytes(stages[0].prefill[off:off+P.RECORD_BYTES]) and
               final==bytes(stages[2].prefill[off:off+P.RECORD_BYTES]),'source publication changed before replay')
        t=time.monotonic()
        command,reply,ack=P.replay(provider,start=start,count=count,parity=parity,rows=rows,stages=3,
            seed_sequence=sequences[0],final_sequence=sequences[2],request=model.request,prompt_sha=prompt_sha,
            seed_sha=seed_sha,final_sha=final_sha,raw_sha=raw_sha,epoch=model.epoch)
        # This check belongs inside the worker, before its Future releases parity.
        P.need(seed==bytes(stages[0].prefill[off:off+P.RECORD_BYTES]) and
               final==bytes(stages[2].prefill[off:off+P.RECORD_BYTES]),'source chunk publication changed before ACK')
        return dict(event='authenticated-prefill-chunk',start=start,count=count,parity=parity,
            target_sequences=sequences,target_reply_hex=[p['reply'] for p in parts],seed_record_hex=seed.hex(),
            final_record_hex=final.hex(),provider_command_hex=command.hex(),provider_reply_hex=reply.hex(),
            provider_ack_hex=ack.hex(),monotonic_s=time.monotonic()),t

    with (Path(output)/'dedicated-prefill.jsonl').open('x') as journal, \
         (Path(output)/'dedicated-prefill-pipeline.jsonl').open('x') as schedule, \
         ThreadPoolExecutor(max_workers=4,thread_name_prefix='dedicated-prefill') as pool:
        def event(actor,k,kind,**fields):
            schedule.write(json.dumps(dict(actor=actor,chunk=k,event=kind,monotonic_s=time.monotonic(),**fields))+'\n');schedule.flush()
        try:
            while len(completed[3])<total:
                provider.guard.check()
                P.need(stop_requested is None or not stop_requested(),'dedicated prefix interrupted; adoption/reset/retry refused')
                # Observe every currently completed failure before admitting more work.
                ready=[a for a,f in busy.items() if f.done()]
                results={a:busy[a].result() for a in ready}
                for actor,result in results.items():
                    k=next_chunk[actor]-1;del busy[actor];completed[actor].add(k)
                    if actor<3:
                        snapshots[k][actor]=result;target_wall[actor]+=result['end']-result['began']
                        event(actor,k,'completed',command_began=result['began'],command_end=result['end'])
                    else:
                        entry,t=result;last_ack=bytes.fromhex(entry['provider_ack_hex']);replay_wall+=entry['monotonic_s']-t
                        journal.write(json.dumps(entry)+'\n');journal.flush()
                        P.need(leases.get(k%2)==k,'full ACK releases actual parity owner')
                        del leases[k%2];del snapshots[k]
                        event(actor,k,'completed',command_began=t,command_end=entry['monotonic_s'])
                if len(completed[3])==total:break
                for actor in (3,2,1,0):
                    k=next_chunk[actor]
                    if actor in busy or k==total:continue
                    if actor and k not in completed[actor-1]:continue
                    if actor==0:
                        if len(leases)==2 or k%2 in leases:continue
                        leases[k%2]=k;snapshots[k]=[None]*3;peak=max(peak,len(leases))
                    event(actor,k,'issued')
                    busy[actor]=pool.submit(replay,k) if actor==3 else pool.submit(target,actor,k)
                    next_chunk[actor]+=1
                P.need(busy,'prefix pipeline dependency deadlock')
                wait(tuple(busy.values()),timeout=.1,return_when=FIRST_COMPLETED)
        except BaseException as error:
            # Cooperative Guard cancellation stops other socket workers; executor
            # joins them before outer lifecycle can close their maps. No adoption.
            provider.guard.fail('dedicated prefill pipeline: '+str(error))
            raise
    P.need(not busy and not leases and all(len(x)==total for x in completed),'all target/provider ACKs before adoption')
    receipt=P.Adoption(bulk,model.epoch,model.request,prompt_sha,tuple(s.sequence for s in stages),provider.sequence,
                       provider.provider_serial,total,last_ack)
    model.adopt_prefill(bulk,native=receipt)
    for stage in stages:stage.physical=stage.committed=bulk
    return dict(prefill_schedule='target-stage-pipeline',prefill_positions=bulk,prefill_chunks=total,prefill_draft_replay=bulk,prefill_source=source,
        prefill_timing=dict(schema='dedicated-stage-pipeline-prefill-host-wall-v1',total_wall_s=time.monotonic()-began,
            target_command_work_wall_s=target_wall,draft_replay_work_wall_s=replay_wall,peak_unfinished_chunks=peak,
            scope='host work durations overlap; full native OP28 ACK releases parity; no GPU duration/speed claim'))
