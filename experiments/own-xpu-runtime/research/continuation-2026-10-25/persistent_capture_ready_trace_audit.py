"""Opt-in capture-ready replay; frozen persistent auditor remains unchanged."""
import hashlib
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'engine/tools'))
import pending_ring_live_driver as native
from finalize_ring_proof import need
from pending_provider_trace_audit import prefix

wire,codec,ring,base=native.wire,native.codec,native.ring,native.base


def sha(value):return hashlib.sha256(value).hexdigest()
def raw(value,size):
    need(isinstance(value,str) and len(value)==2*size,'exact raw witness extent')
    return bytes.fromhex(value)


def audit_controller(commands,records,batches,prompt,outputs,request,stages,stream_bytes,vocab,context,*,epoch,initial_sequences,check_policy,max_new,provider_stage=0,speculative_depth=2):
    need(type(epoch)is int and 0<epoch<2**64 and check_policy in ('qualification','measured'), 'explicit persistent epoch and fixed policy')
    need(len(initial_sequences)==stages and all(type(n)is int and 0<n<2**31 for n in initial_sequences), 'exact per-owner post-reset wire sequences')
    need(type(max_new)is int and len(outputs)<=max_new<=512, 'admitted persistent output bound')
    need(type(provider_stage)is int and 0<=provider_stage<stages-1,'explicit nonfinal provider owner')
    need(type(speculative_depth)is int and speculative_depth in (2,3),'supported speculative depth')
    version=1 if speculative_depth==2 else 2
    proposal_bytes=192 if speculative_depth==2 else 224
    verify=check_policy=='qualification'
    initial=hashlib.sha256(b'ownrt.ring-request.v1\0'+bytes.fromhex(request)+struct.pack('<Q',epoch)).digest()
    inputs=prompt+outputs[:-1];truth=list(prompt);created={};origin={};sent=[[] for _ in range(stages)]
    states=[dict(physical=0,committed=0,pending=[],accepted=None,busy=None,last_sequence=initial_sequences[i]) for i in range(stages)]
    providers=[];aborts=[];all_aborts=[];publications={};parents={};available={};provider_position=0
    owner_rows=[set() for _ in range(stages)]
    observed_outputs=[];record_index=batch_index=0;cut=None;observed_miss_depths=set();parent_lease=None;captured=set();overlap_rows=overlap_head_rows=0

    def rowcheck(r):
        need(set(r)==set('epoch id parent position token fixture request before after'.split()),'complete immutable row witness')
        need(all(type(r[k]) is int for k in ('epoch','id','parent','position','token','fixture'))
             and r['epoch']==epoch and r['request']==request and r['id']>r['parent']>=0
             and 0<=r['position']<len(prompt)+max_new-1 and 0<=r['token']<vocab
             and r['fixture']==max(0,r['position']-len(prompt)+2),'row request/geometry')
        before=initial if r['parent']==0 else bytes.fromhex(created[r['parent']]['after'])
        need((r['position']==0 if r['parent']==0 else created[r['parent']]['position']+1==r['position'])
             and r['before']==before.hex() and r['after']==prefix(before,r['position'],r['token']).hex(),'full row prefix')

    def local(event):
        r=event['row']
        return dict(r,before=bytes.fromhex(r['before']),after=bytes.fromhex(r['after']),
            tentative=event['tentative'],row_sequence=event['row_ticket'],provider_position_at_capture=provider_position,
            provider_serial_at_capture=provider_position)

    def proposal(r,p):
        need(isinstance(p,dict) and set(p)==set('batch_ticket seed_length depth parent_digest after_digest'.split()),'original proposal witness')
        batch=available.get(p['batch_ticket']);need(batch is not None,'proposal used before actual provider completion')
        depth=r['position']-batch['seed_position']
        need(p['seed_length']==batch['seed_position']+1 and p['depth']==depth and 1<=depth<=len(batch['guesses']),
             'actual proposal depth identity')
        before=bytes.fromhex(batch['seed_prefix_sha256'])
        for i,t in enumerate(batch['guesses'][:depth-1],batch['seed_position']+1):before=prefix(before,i,t)
        need(r['token']==batch['guesses'][depth-1] and r['before']==p['parent_digest']==before.hex()
             and r['after']==p['after_digest'],'proposal token/hypothetical prefix differs')

    for event in commands:
        need(event['schema']=='ownrt.rolling-command.v1' and event['event'] in ('issued','completed','parent-captured'),'command witness schema')
        owner,seq,op=event['stage'],event['sequence'],event['op']
        need(type(owner)is int and 0<=owner<stages and type(seq)is int and 0<seq<2**31 and op in (24,25,26,27),'wire owner/op')
        s=states[owner];r=event['row'];final=owner==stages-1
        rowcheck(r);need(type(event['tentative'])is bool,'original tentative flag type')
        if event['event']=='parent-captured':
            issued=s['busy']
            need(owner==provider_stage and op==27 and issued is not None and seq not in captured
                 and all(event[k]==issued[k] for k in ('stage','sequence','op','row','tentative','row_ticket')),
                 'capture exact outstanding provider; no duplicates')
            reply=base.REPLY.unpack(raw(event['reply_hex'],base.REPLY.size))
            need(reply[:8]==(2,-1,0,128,seq,0 if owner==0 else 1,owner,0) and __import__('math').isfinite(reply[8])
                 and reply[8]>=0 and reply[9:]==(0,0,0),'capture raw nonterminal header')
            parent=issued['context']['parent']
            expected=(0x315950414352574f,1,128,epoch,seq,r['id'],r['parent'],parent['accept_sequence'],
                      issued['context']['serial'],bytes.fromhex(request),bytes.fromhex(issued['parent_record_sha256']))
            need(struct.unpack('<QII6Q32s32s',raw(event['metadata_hex'],128))==expected,
                 'capture owned epoch/request/seed/serial/final record binding')
            need(parent_lease==r['parent'],'capture releases exact live parent lease')
            captured.add(seq);parent_lease=None
            continue
        if event['event']=='issued':
            need(s['busy'] is None and seq==s['last_sequence']+1,'exclusive monotonic owner reservation')
            need((event['target_physical'],event['target_committed'],event['pending_target_rows'])==
                 (s['physical'],s['committed'],[v['id'] for v in s['pending']]),'issued target cursor/pending witness')
            if r['id'] in created:need(created[r['id']]==r,'issued global row mutated')
            else:
                need(op==24 and owner==0 and r['id']>max(created,default=0),'new global row owner/order')
                created[r['id']]=dict(r);origin[r['id']]=event['proposal']
                if event['tentative']:proposal(r,event['proposal'])
                else:need(event['proposal'] is None,'known input has speculative origin')
            need(event['proposal']==origin[r['id']],'issued proposal origin changed')
            if cut is not None and op in (24,27):
                need(not any(t['busy'] and t['busy']['op']==26 or any(p['position']>=cut for p in t['pending']) for t in states),
                     'correction before every suffix abort acknowledgment')
                cut=None
            if op==24:
                need(r['id'] not in owner_rows[owner],'global ROW id reused on one owner')
                owner_rows[owner].add(r['id'])
                need(event['tentative'] is (r['position']>=len(truth)),'ROW tentative flag differs from verified input frontier')
                parent=s['pending'][-1] if s['pending'] else s['accepted']
                need(r['position']==s['physical'] and r['parent']==(parent['id'] if parent else 0)
                     and event['row_ticket']==seq and len(s['pending'])<(1 if final else speculative_depth),'ROW cursor/parent/capacity')
                need(not s['pending'] or event['tentative'] and all(p['tentative'] for p in s['pending']),'ROW bypassed unaccepted verified input')
                need(not final or not event['tentative'],'final stage speculated')
                if not event['tentative']:need(r['position']<len(truth) and r['token']==truth[r['position']],'unverified ROW promoted to truth')
                if final:
                    need(parent_lease is None,'final record overwritten during provider lease')
                    provider_busy=states[provider_stage]['busy']
                    if provider_busy and provider_busy['op']==27:
                        need(provider_busy['sequence'] in captured,'overlap ROW before capture')
                        overlap_rows+=1;overlap_head_rows+=int(r['fixture']>0)
                source=event['source']
                if owner:
                    need(source==publications.get((owner-1,r['id'])),'upstream owned stream identity differs')
                else:need(source is None,'first-stage source must be absent')
            elif op in (25,26):
                need(s['pending'] and r['id']==s['pending'][0]['id'] and event['row_ticket']==s['pending'][0]['row_sequence']
                     and event['tentative'] is s['pending'][0]['tentative'],'resolution original oldest ROW')
                if op==25 and (final or owner==0):need(states[provider_stage]['busy'] is None or states[provider_stage]['busy']['op']!=27,'final ACCEPT before provider completion')
                if op==25:need(r['position']<len(truth) and r['token']==truth[r['position']],'ACCEPT before target truth')
                else:
                    need(cut is not None and not final and all(p['tentative'] and p['position']>=cut for p in s['pending'])
                         and not any(t['busy'] and t['busy']['op'] not in (26,) for t in states),'ABORT before distributed drain')
            else:
                seed=states[0]['accepted']
                need(owner==provider_stage and seed and seed['id']==r['id'] and r['position']==provider_position+1
                     and event['provider_serial']==r['position'] and event['row_ticket']==seed['row_sequence']
                     and event['accepted_seed_sequence']==seed['accept_sequence']
                     and event['tentative'] is seed['tentative'] and all(v['tentative'] for v in s['pending']),
                     'provider exact locally accepted true pair')
                parent=states[-1]['accepted'];need(parent and parent['id']==r['parent'] and parent['position']+1==r['position'],
                                                   'provider independent final parent')
                need(parent_lease==parent['id'] and states[-1]['busy'] is None and not states[-1]['pending'],
                     'provider final parent lease was overwritten or is in flight')
                rec=parents[parent['id']]
                need(event['parent_record_hex']==rec['record_hex'] and event['parent_record_sha256']==rec['record_sha256']
                     and event['parent_hidden_sha256']==rec['hidden_sha256'] and event['parent_hidden_bytes']==stream_bytes,
                     'provider owned final-record lease')
                event=dict(event,context=dict(sequence=seq,position=r['position'],serial=r['position'],seed=dict(seed),provider_stage=provider_stage,seed_journal_sha256=event.get('seed_journal_sha256'),
                    parent=dict(parent),physical=s['physical'],committed=s['committed'],pending=[v['id'] for v in s['pending']]))
            if op==27 and provider_stage:
                need(s['committed'] in (r['position'],r['position']+1) and s['physical']==s['committed']+len(s['pending']),'remote provider target cursor/seed frontier')
            meta=list(wire.ROW_META.unpack(raw(event['metadata_hex'],224)))
            src=event.get('source') if op==24 else None
            expected=[0x52494e47,1,224,int(event['tentative']),epoch,r['id'],r['parent'],r['position'],r['token'],r['fixture'],owner,int(final),
                      owner-1 if src else -1,src['ticket'] if src else 0,event['row_ticket'] if op==27 and provider_stage else 0,stream_bytes if src else 0,1,
                      bytes.fromhex(request),bytes.fromhex(r['before']),bytes.fromhex(r['after']),bytes.fromhex(src['sha256']) if src else wire.EMPTY_SHA,bytes(16)]
            need(meta==expected,'issued exact native metadata differs')
            if op==27 and provider_stage:
                journal=raw(event['seed_journal_hex'],256)
                need(sha(journal)==event['seed_journal_sha256'],'seed journal raw SHA differs')
                magic,journal_version,size,seed_owner,accepted,physical,committed=struct.unpack('<4IQ2i',journal[:32])
                need((magic,journal_version,size,seed_owner,accepted)==(0x52534331,1,256,0,event['accepted_seed_sequence'])
                     and accepted>event['row_ticket'] and committed==r['position']+1 and committed<=physical<=committed+speculative_depth,'seed journal owned ACCEPT/frontier binding')
                seed_meta=list(expected);seed_meta[10]=0;seed_meta[14]=event['row_ticket']
                need(journal[32:]==wire.ROW_META.pack(*seed_meta),'seed journal original stage0 row differs')
            packet=base.REQUEST.unpack(raw(event['request_hex'],base.REQUEST.size))
            need(packet==(op,r['token'],r['position'],int(r['fixture']>0) if op==27 else r['fixture'],
                          speculative_depth if op==27 else int(event['tentative']) if op==24 else event['row_ticket'],seq,owner,int(final)),
                 'issued raw request differs')
            s['last_sequence']=seq;s['busy']=event
            if op!=27:sent[owner].append(dict(op=op,sequence=seq,row=r['id'],position=r['position'],
                                            tentative=event['tentative'],row_ticket=event['row_ticket']))
            continue
        issued=s['busy'];need(issued is not None and all(event[k]==issued[k] for k in ('stage','sequence','op','row','tentative','row_ticket')),
                             'completion exact outstanding command')
        reply=base.REPLY.unpack(raw(event['reply_hex'],base.REPLY.size))
        need(reply[0]==reply[2]==0 and reply[4]==seq and reply[5:8]==(0 if owner==0 else 1,owner,int(final)),'raw transport reply owner/error')
        if op==27:
            need(seq in captured,'provider completion without capture event')
            b=event['provider'];need(batch_index<len(batches) and b==batches[batch_index],'provider witness/batch chronology');batch_index+=1
            need(b['proposal_hex']==event['metadata_hex'] and b['reply_hex']==event['reply_hex'] and b['proposal_sha256']==sha(bytes.fromhex(b['proposal_hex']))
                 and b['reply_sha256']==sha(bytes.fromhex(b['reply_hex'])),'provider raw witness hashes')
            ctx=issued['context'];parent=ctx['parent'];head=r['fixture']>0;depth=min(speculative_depth,context-r['position']+1) if head else 0
            guesses=b['guesses'];need(len(guesses)==depth and all(type(t)is int and 0<=t<vocab for t in guesses),'actual provider bounded guesses')
            expected=(0x44525032,version,proposal_bytes,2+int(head),epoch,seq,r['id'],r['parent'],parent['accept_sequence'],provider_position+1,
                      r['position'],r['position'],speculative_depth,depth,*(guesses+[-1]*2)[:2],0,1,
                      bytes.fromhex(request),bytes.fromhex(r['after']),bytes.fromhex(issued['parent_hidden_sha256']))
            payload=raw(event['metadata_hex'],proposal_bytes)
            if speculative_depth==3:
                need(payload[192:]==struct.pack('<i',guesses[2] if depth==3 else -1)+bytes(28),'third proposal and reserved bytes')
            need(codec.PROPOSAL.unpack(payload[:192])==expected and reply[3]==proposal_bytes and reply[1]==(guesses[0] if guesses else -1),
                 'raw provider owner/seed/parent/restore/proposal identity')
            for key,value in dict(epoch=epoch,sequence=seq,seed_row=r['id'],parent_row=r['parent'],final_commit=parent['accept_sequence'],
                provider_serial=r['position'],seed_position=r['position'],restored_position=r['position'],available_depth=depth,
                request_sha256=request,seed_prefix_sha256=r['after'],parent_hidden_sha256=issued['parent_hidden_sha256'],restored=True,
                speculative_target_use=True,target_physical=s['physical'],target_committed=s['committed'],pending_target_rows=[p['id'] for p in s['pending']],
                pending_depth=len(s['pending']),accepted_seed_sequence=ctx['seed']['accept_sequence'],original_seed_tentative=ctx['seed']['tentative']).items():
                need(b[key]==value,'decoded provider witness differs: '+key)
            providers.append(ctx);provider_position+=1;available[seq]=b;parent_lease=None
        else:
            ack=event['ack'];need(ack['epoch']==epoch and ack['stage']==owner and ack['sequence']==seq and ack['row_id']==r['id']
                                 and ack['row_ticket']==event['row_ticket'] and ack['sticky_error']==0,'target ACK identity')
            if op==24:
                need(reply[3]==(0 if final else stream_bytes) and reply[1]==(ack['token'] if final and r['fixture'] else -1),'target output/stream extent')
                need(ack['token'] is None if not(final and r['fixture']) else type(ack['token'])is int and 0<=ack['token']<vocab,'target output token')
                expected=list(wire.ROW_META.unpack(bytes.fromhex(issued['metadata_hex'])))
                expected[3]|=2;expected[14]=seq;expected[15]=0 if final else stream_bytes
                expected[20]=wire.EMPTY_SHA if final else bytes.fromhex(ack['stream_sha256'])
                need(wire.ROW_META.unpack(raw(event['metadata_hex'],224))==tuple(expected) and ack['stream_bytes']==expected[15]
                     and (ack['stream_sha256'] is None if final else True) and ack['discarded']==[],'raw target publication witness')
                row=local(event);row['target_output']=ack['token'];s['pending'].append(row);s['physical']+=1
                if not final:publications[(owner,r['id'])]=dict(stage=owner,ticket=seq,sha256=ack['stream_sha256'],bytes=stream_bytes)
            else:
                need(reply[1]==reply[3]==0 and ack['token'] is None and ack['stream_bytes']==0 and ack['stream_sha256'] is None,'resolution stale output')
                discarded=[p['id'] for p in s['pending']] if op==26 else []
                expected=(0x5241434b,version,128,int(op==26 and verify),epoch,r['id'],*(discarded+[0,0])[:2],owner,seq,event['row_ticket'],
                    s['committed'] if op==26 else s['physical'],s['committed'] if op==26 else s['committed']+1,
                    len(discarded),0 if op==26 else len(s['pending'])-1,0,(struct.pack('<Q',discarded[2] if len(discarded)==3 else 0)+bytes(40)) if speculative_depth==3 else bytes(48))
                need(wire.ACK_META.unpack(raw(event['metadata_hex'],128))==expected and ack['discarded']==discarded,'raw resolution/byteverify ACK differs')
                if op==25:
                    row=s['pending'].pop(0);row['accept_sequence']=seq;s['accepted']=row;s['committed']+=1
                    if final:
                        need(record_index<len(records),'missing final-owned record');rec=records[record_index];record_index+=1
                        rb=raw(rec['record_hex'],360)
                        need(rec['schema']=='ownrt.rolling-final-record.v1' and (rec['stage'],rec['sequence'],rec['row'],rec['row_ticket'])==
                             (owner,seq,r['id'],event['row_ticket']) and rec['record_sha256']==sha(rb) and rec['hidden_bytes']==stream_bytes,'final record witness identity')
                        need(codec.FINAL_HEADER.unpack(rb[:24])==(codec.FINAL_MAGIC,1,360,owner,seq),'final record header')
                        expected=list(wire.ROW_META.unpack(bytes.fromhex(issued['metadata_hex'])));expected[14]=event['row_ticket']
                        need(rb[24:248]==wire.ROW_META.pack(*expected),'final immutable record metadata')
                        head=codec.handoff_codec.HEADER.unpack(rb[248:])
                        need(head==(codec.handoff_codec.MAGIC,1,stream_bytes,r['position'],owner,stages,event['row_ticket'],seq,r['token'],
                                    row['target_output'] if r['fixture'] else -1,int(r['fixture']>0),0,rec['hidden_sha256'].encode()),'final hidden handoff identity')
                        parents[r['id']]=rec
                        need(parent_lease is None,'unconsumed final record lease replaced')
                        parent_lease=r['id'] if r['position']<len(inputs)-1 else None
                        if r['fixture']:
                            observed_outputs.append(row['target_output']);position=r['position']+1
                            if position<len(inputs):
                                truth.append(row['target_output'])
                                wrong=[x for x in created.values() if x['position']==position and x['token']!=row['target_output']
                                       and (any(p['id']==x['id'] for t in states for p in t['pending'])
                                            or any(t['busy'] and t['busy']['op']==24 and t['busy']['row']['id']==x['id'] for t in states))]
                                if wrong:
                                    cut=position
                                    observed_miss_depths.update(origin[x['id']]['depth'] for x in wrong)
                            else:cut=len(inputs)
                else:
                    item=dict(sequence=seq,oldest=dict(s['pending'][0]),discarded=[dict(p) for p in s['pending']],
                              provider_position=provider_position,provider_serial=provider_position)
                    all_aborts.append(dict(stage=owner,**item))
                    if owner==provider_stage:aborts.append(item)
                    s['pending']=[];s['physical']=s['committed']
            need((ack['physical'],ack['committed'],ack['pending'])==(s['physical'],s['committed'],len(s['pending'])),'decoded target cursor ACK differs')
        s['busy']=None
    need(all(s['busy'] is None and not s['pending'] and s['physical']==s['committed']==len(inputs) for s in states),
         'rolling terminal owners not fully drained')
    need(observed_outputs==outputs and provider_position==len(inputs)-1 and record_index==len(records) and batch_index==len(batches)
         and parent_lease is None,
         'rolling output/provider/final-record conservation')
    return dict(created={k:dict(v,before=bytes.fromhex(v['before']),after=bytes.fromhex(v['after'])) for k,v in created.items()},
        scheduler_overlap=dict(final_rows_issued_during_provider=overlap_rows,head_bearing_final_rows_issued_during_provider=overlap_head_rows,scope='Scheduler overlap only; not GPU utilization or proven kernel concurrency.'),
        sent=sent,providers=providers,aborts=aborts,all_aborts=all_aborts,states=states,
        actual_proposal_rows=sum(p is not None for p in origin.values()),observed_miss_depths=sorted(observed_miss_depths))
