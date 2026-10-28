"""Sequential authenticated OP15/OP28 dedicated prefix replay; no ROW/ACCEPT journal synthesis."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import select
import stat
import struct
import time
from . import prefill

RECORD = struct.Struct('<16IQ32s32s32s32s32s24s')
TOKENS = struct.Struct('<256i')
ACK = struct.Struct('<16I2Q32s32s32s32s32s16s')
RECORD_BYTES, RECORD_OFFSET, ACK_OFFSET = 1280, 1536, 1024
CHUNK_MAGIC, ACK_MAGIC, OP = 0x314B4843, 0x314B4143, 28


def need(value,message):
    if not value:raise ValueError(message)

def prompt_source(plan):
    path=Path(plan['dedicated_prefill_prompt'])
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==4*len(plan['prompt_tokens'])
             and before.st_size<=4*262144,'bounded immutable prompt file')
        raw=b''
        while len(raw)<before.st_size:
            part=os.read(fd,before.st_size-len(raw));need(part,'prompt file truncated');raw+=part
        after=os.fstat(fd)
        signature=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(signature(before)==signature(after)==signature(os.stat(path,follow_symlinks=False)), 'prompt source changed')
        need(raw==struct.pack(f'<{len(plan["prompt_tokens"])}i',*plan['prompt_tokens'])
             and sha256(raw).hexdigest()==plan['dedicated_prefill_prompt_sha256'],'actual immutable prompt IDs/hash')
        return raw,dict(path=str(path),sha256=sha256(raw).hexdigest(),device=before.st_dev,inode=before.st_ino,bytes=len(raw))
    finally:os.close(fd)


def chunk_record(raw,*,role,stage,stages,start,count,rows,stream,parity,sequence,epoch,request,prompt_sha,
                 before,after,prompt,raw_sha):
    need(len(raw)==RECORD_BYTES and role in (1,2) and stages in (2,3)
         and stage==(0 if role==1 else stages-1) and 0<count<=rows<=256
         and start>=0 and start%rows==0 and parity==(start//rows)%2,'complete bounded1280 target chunk record')
    v=RECORD.unpack(raw[:RECORD.size]);tokens=TOKENS.unpack(raw[RECORD.size:])
    expected=(CHUNK_MAGIC,1,RECORD_BYTES,sequence,role,stage,stages,parity,start,count,rows,stream,15,sequence,
              prompt[start+count] if role==1 else 0xffffffff,0,epoch,request,prompt_sha,before,after,
              bytes(32) if role==1 else raw_sha,bytes(24))
    need(v==expected and 0<sequence<2**31 and 0<count<=rows<=256 and start+count<len(prompt),
         'actual target chunk publication/source identity')
    expected_tokens=tuple(prompt[start:start+count])+tuple([0]*(256-count)) if role==1 else tuple([0]*256)
    need(tokens==expected_tokens,'actual consumed chunk tokens/zero tail')
    return sha256(raw).digest()


def chunk_ack(raw,*,sequence,start,count,parity,rows,stream,stages,seed_sequence,final_sequence,epoch,
              request,prompt_sha,seed_sha,final_sha,raw_sha):
    need(0<count<=rows<=256 and start>=0 and start%rows==0 and parity==(start//rows)%2,'bounded native chunk ACK geometry')
    expected=(ACK_MAGIC,1,256,sequence,start,count,parity,rows,stream,stages,seed_sequence,final_sequence,
              start+count+1,1,0,0,epoch,start+count,request,prompt_sha,seed_sha,final_sha,raw_sha,bytes(16))
    need(len(raw)==ACK.size and ACK.unpack(raw)==expected,'actual dedicated chunk ACK/canonical serial/source binding')
    return start+count


@dataclass(frozen=True)
class Adoption:
    count:int
    epoch:int
    request:bytes
    prompt_sha:bytes
    target_sequences:tuple
    provider_sequence:int
    provider_serial:int
    chunks:int
    last_ack:bytes


def replay(provider,*,start,count,parity,rows,stages,seed_sequence,final_sequence,request,prompt_sha,
           seed_sha,final_sha,raw_sha,epoch):
    from .dedicated_transport import MAGIC,VERSION,base
    provider.guard.check()
    need(provider.command_pending is None and not provider.transmit and not provider.received
         and not getattr(provider,'prefill_bulk_busy',False) and provider.provider_serial==start,
         'exclusive contiguous dedicated chunk replay')
    provider.prefill_bulk_busy=True
    provider.sequence+=1;provider.owner.sequence=provider.sequence
    need(0<provider.sequence<2**31,'dedicated chunk sequence bound')
    provider.sock.settimeout(.2)
    command=base.REQUEST.pack(OP,count,start,parity,0,provider.sequence,MAGIC,VERSION)
    view=memoryview(command)
    while view:
        provider.guard.check();_,ready,_=select.select([],[provider.sock],[],.2)
        if ready:
            n=provider.sock.send(view);need(n>0,'dedicated chunk channel closed');view=view[n:]
    reply=provider._blocking_reply()
    provider._reply(reply,sequence=provider.sequence,token=-1,size=ACK.size)
    raw=bytes(provider.shared[ACK_OFFSET:ACK_OFFSET+ACK.size])
    serial=chunk_ack(raw,sequence=provider.sequence,start=start,count=count,parity=parity,rows=rows,stream=provider.stream_bytes,
        stages=stages,seed_sequence=seed_sequence,final_sequence=final_sequence,epoch=epoch,request=request,
        prompt_sha=prompt_sha,seed_sha=seed_sha,final_sha=final_sha,raw_sha=raw_sha)
    need(bytes(provider.shared[ACK_OFFSET:ACK_OFFSET+ACK.size])==raw,'provider chunk ACK changed while copying')
    provider.provider_serial=serial;provider.prefill_bulk_busy=False
    return command,reply,raw


def run(stages,provider,model,plan,output,*,stop_requested=None):
    from .transport import pending,ring,base
    need(plan.get('dedicated_bulk_prefill') is True and not plan.get('prefill_pipeline')
         and not plan.get('persistent_reset'),'dedicated bulk sequential explicit opt-in, no reset')
    rows=plan['prefill_rows'];bulk=len(model.prompt)-2
    need(rows==256 and bulk>=rows and len(stages)in (2,3) and model.frontier==0 and not model.rows
         and provider.provider_serial==provider.sequence==0,'cold bounded dedicated prefix')
    need(all(s.prefill_rows==rows and s.stream_bytes==provider.stream_bytes and s.sequence==0 for s in stages),
         'uniform fresh target prefill geometry')
    _,source=prompt_source(plan);prompt_sha=bytes.fromhex(source['sha256']);stream=provider.stream_bytes
    began=time.monotonic();target_wall=[0.]*len(stages);replay_wall=0.;chunks=0;last_ack=None
    with (Path(output)/'dedicated-prefill.jsonl').open('x') as journal:
        for start in range(0,bulk,rows):
            provider.guard.check()
            need(stop_requested is None or not stop_requested(), 'dedicated prefix interrupted; partial adoption/reset/retry refused')
            count=min(rows,bulk-start);parity=(start//rows)%2;replies=[]
            stages[0].prefill[16:16+4*count]=struct.pack(f'<{count}i',*model.prompt[start:start+count])
            position=start+count-1
            row=ring.Row(model.epoch,position+1,position,position,model.prompt[position],0,model.request,
                         model.proposals.hashes[position],model.proposals.hashes[position+1])
            for index,stage in enumerate(stages):
                if index:
                    kind='forward' if index==1 else 'reverse'
                    prefill.region(stage.prefill,'forward',parity,rows,stream,count)[:]=prefill.region(stages[index-1].prefill,kind,parity,rows,stream,count)
                metadata=prefill.verified_metadata(pending.wire,row,index,index==len(stages)-1)
                stage.shared[pending.wire.ROW_OFFSET:pending.wire.ROW_OFFSET+len(metadata)]=metadata
                t=time.monotonic();reply=stage.command(15,count,start,parity);target_wall[index]+=time.monotonic()-t
                need(reply[3]==count*stream,'actual target chunk completion extent');replies.append(base.REPLY.pack(*reply).hex())
            offset=RECORD_OFFSET+parity*RECORD_BYTES
            seed_raw=bytes(stages[0].prefill[offset:offset+RECORD_BYTES]);final_raw=bytes(stages[-1].prefill[offset:offset+RECORD_BYTES])
            hidden=prefill.region(stages[-1].prefill,'reverse',parity,rows,stream,count);raw_sha=sha256(hidden).digest();del hidden
            common=dict(stages=len(stages),start=start,count=count,rows=rows,stream=stream,parity=parity,
                epoch=model.epoch,request=model.request,prompt_sha=prompt_sha,before=model.proposals.hashes[start],
                after=model.proposals.hashes[start+count],prompt=model.prompt,raw_sha=raw_sha)
            seed_sha=chunk_record(seed_raw,role=1,stage=0,sequence=stages[0].sequence,**common)
            final_sha=chunk_record(final_raw,role=2,stage=len(stages)-1,sequence=stages[-1].sequence,**common)
            t=time.monotonic();command,reply,last_ack=replay(provider,start=start,count=count,parity=parity,rows=rows,
                stages=len(stages),seed_sequence=stages[0].sequence,final_sequence=stages[-1].sequence,
                request=model.request,prompt_sha=prompt_sha,seed_sha=seed_sha,final_sha=final_sha,raw_sha=raw_sha,epoch=model.epoch)
            replay_wall+=time.monotonic()-t
            need(seed_raw==bytes(stages[0].prefill[offset:offset+RECORD_BYTES]) and final_raw==bytes(stages[-1].prefill[offset:offset+RECORD_BYTES]),'source chunk publication changed before ACK')
            journal.write(json.dumps(dict(event='authenticated-prefill-chunk',start=start,count=count,parity=parity,
                target_sequences=[s.sequence for s in stages],target_reply_hex=replies,seed_record_hex=seed_raw.hex(),
                final_record_hex=final_raw.hex(),provider_command_hex=command.hex(),provider_reply_hex=reply.hex(),
                provider_ack_hex=last_ack.hex(),monotonic_s=time.monotonic()))+'\n');journal.flush();chunks+=1
    receipt=Adoption(bulk,model.epoch,model.request,prompt_sha,tuple(s.sequence for s in stages),provider.sequence,
                     provider.provider_serial,chunks,last_ack)
    model.adopt_prefill(bulk,native=receipt)
    for stage in stages:stage.physical=stage.committed=bulk
    return dict(prefill_positions=bulk,prefill_chunks=chunks,prefill_draft_replay=bulk,prefill_source=source,
        prefill_timing=dict(schema='dedicated-sequential-prefill-host-wall-v1',total_wall_s=time.monotonic()-began,
            target_command_work_wall_s=target_wall,draft_replay_work_wall_s=replay_wall,
            scope='sequential host wall durations; no overlap/speed claim'))


def prefix_evidence(journal_path,pairs_path,chunks_path,model,*,rows=256):
    """Read actual prefix records/ACKs/native pairs, never invent ROW/ACCEPT events.

    This is source ingestion, not sealed-state or reference parity. A qualifier
    must still compare these actual native hidden hashes and terminal state.
    """
    from .dedicated_transport import base,MAGIC,VERSION
    def read_lines(path):
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=128*1024**2,'bounded actual prefix trace')
            raw=b''
            while len(raw)<before.st_size:
                part=os.read(fd,min(1024**2,before.st_size-len(raw)));need(part,'prefix trace truncated');raw+=part
            stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            need(stamp(before)==stamp(os.fstat(fd))==stamp(os.stat(path,follow_symlinks=False)),'prefix trace changed')
            def unique(pairs):
                value={}
                for key,item in pairs:need(key not in value,'duplicate prefix JSON key');value[key]=item
                return value
            return [json.loads(line,object_pairs_hook=unique) for line in raw.splitlines()],dict(path=str(path),sha256=sha256(raw).hexdigest(),bytes=len(raw))
        finally:os.close(fd)
    journal,js=read_lines(journal_path);actual_pairs,ps=read_lines(pairs_path);native_chunks,cs=read_lines(chunks_path)
    need(type(rows)is int and 1<=rows<=256,'bounded prefix evidence rows')
    bulk=len(model.prompt)-2;count_chunks=(bulk+rows-1)//rows;stream=model.stream_bytes;stages=len(model.stages)
    need(1<=rows<=256 and len(journal)==len(native_chunks)==count_chunks and len(actual_pairs)==bulk,'complete actual native prefix trace inventory')
    prompt_sha=sha256(struct.pack(f'<{len(model.prompt)}i',*model.prompt)).digest()
    for index,(j,n) in enumerate(zip(journal,native_chunks)):
        start=index*rows;count=min(rows,bulk-start);parity=index%2;sequence=index+1
        need(j['event']=='authenticated-prefill-chunk' and (j['start'],j['count'],j['parity'])==(start,count,parity)
             and j['target_sequences']==[sequence]*stages,'actual sequential chunk schedule')
        seed,final=bytes.fromhex(j['seed_record_hex']),bytes.fromhex(j['final_record_hex'])
        raw_sha=RECORD.unpack(final[:RECORD.size])[-2]
        common=dict(stages=stages,start=start,count=count,rows=rows,stream=stream,parity=parity,epoch=model.epoch,
            request=model.request,prompt_sha=prompt_sha,before=model.proposals.hashes[start],after=model.proposals.hashes[start+count],
            prompt=model.prompt,raw_sha=raw_sha)
        seed_sha=chunk_record(seed,role=1,stage=0,sequence=sequence,**common)
        final_sha=chunk_record(final,role=2,stage=stages-1,sequence=sequence,**common)
        need(base.REQUEST.unpack(bytes.fromhex(j['provider_command_hex']))==(28,count,start,parity,0,sequence,MAGIC,VERSION), 'actual OP28 command frame')
        need(base.REPLY.unpack(bytes.fromhex(j['provider_reply_hex']))==(0,-1,0,256,sequence,-1,MAGIC,VERSION,0.,0.,0.,0.),'actual OP28 completion frame')
        chunk_ack(bytes.fromhex(j['provider_ack_hex']),sequence=sequence,start=start,count=count,parity=parity,rows=rows,
            stream=stream,stages=stages,seed_sequence=sequence,final_sequence=sequence,epoch=model.epoch,
            request=model.request,prompt_sha=prompt_sha,seed_sha=seed_sha,final_sha=final_sha,raw_sha=raw_sha)
        need(len(j['target_reply_hex'])==stages,'all actual target chunk replies')
        for stage,reply in enumerate(j['target_reply_hex']):
            v=base.REPLY.unpack(bytes.fromhex(reply))
            need(v[0]==v[2]==0 and v[3:8]==(count*stream,sequence,0 if stage==0 else 1,stage,int(stage==stages-1)), 'actual target OP15 source reply binding')
        expected=dict(epoch=model.epoch,request=model.request.hex(),sequence=sequence,start=start,count=count,serial=start+count,
            prompt_sha256=prompt_sha.hex(),seed_record_sha256=seed_sha.hex(),final_record_sha256=final_sha.hex(),raw_sha256=raw_sha.hex())
        need(n==expected and all(type(n[k])is type(v) for k,v in expected.items()),'native chunk receipt differs from actual source/ACK')
    keys={'position','token','head','provider_serial','hidden_bytes','hidden_sha256','command_sequence'}
    for position,row in enumerate(actual_pairs,1):
        hidden=row.get('hidden_sha256')
        need(set(row)==keys and all(type(row[k])is int for k in ('position','token','provider_serial','hidden_bytes','command_sequence')) and row['position']==position
             and row['token']==model.prompt[position] and row['head'] is False and row['provider_serial']==position
             and row['hidden_bytes']==stream and row['command_sequence']==(position-1)//rows+1
             and type(hidden)is str and len(hidden)==64 and hidden==hidden.lower()
             and len(bytes.fromhex(hidden))==32,'actual contiguous no-head canonical prefix pair')
    return dict(actual_native_pairs=actual_pairs,actual_native_chunks=native_chunks,
        sources=[js,ps,cs],positions=bulk,scope='Actual native trace ingestion only; no synthetic per-row acceptance and no sealed-state/reference parity assertion.')
