"""Replay pending-provider controller commands without treating guesses as truth."""
import hashlib
import struct
from finalize_ring_proof import need


def prefix(before,position,token):
    return hashlib.sha256(b'ownrt.ring-prefix.v1\0'+before+struct.pack('<II',position,token)).digest()


def audit_controller(schedule,inputs,request_sha,stage_count):
    initial=hashlib.sha256(b'ownrt.ring-request.v1\0'+bytes.fromhex(request_sha)+bytes(8)).digest()
    created={};states=[dict(physical=0,committed=0,pending=[],accepted=None,last_sequence=0) for _ in range(stage_count)]
    sent=[[] for _ in states];providers=[];aborts=[];provider_position=0;final_parents={}
    def sequence(state,value):
        need(type(value)is int and value==state['last_sequence']+1,'global owner sequence gap/duplicate')
        state['last_sequence']=value
    for event in schedule:
        kind=event['event']
        if kind=='older-accepted-with-one-pending':
            state=states[0]
            need(len(state['pending'])==1 and state['accepted']['tentative'] is True
                 and (event['position'],event['physical'],event['committed'],event['pending_row'])
                 ==(state['accepted']['position'],state['physical'],state['committed'],state['pending'][0]['id']),
                 'older ACCEPT did not retain one exact younger row')
            continue
        if kind=='provider':
            state=states[0];sequence(state,event['sequence']);seed=state['accepted']
            need(seed is not None and seed['position']==provider_position+1==event['position']
                 and event['serial']==event['position'] and all(not s['pending'] for s in states[1:]),
                 'canonical provider progression or other-stage drain differs')
            pending=[r['id'] for r in state['pending']]
            need(all(r['tentative'] for r in state['pending'])
                 and (event['physical'],event['committed'],event['pending_depth'],list(event['pending_rows']))
                 ==(state['physical'],state['committed'],len(pending),pending), 'provider target suffix identity differs')
            parent=final_parents.get(seed['position']-1)
            need(parent is not None and parent['id']==seed['parent'] and parent['after']==seed['before']
                 and states[-1]['accepted']['id']==parent['id'],'provider parent is not latest actual final commit')
            providers.append(dict(sequence=event['sequence'],position=seed['position'],serial=event['serial'],
                seed=dict(seed),parent=dict(parent),physical=state['physical'],committed=state['committed'],pending=list(pending)))
            provider_position=seed['position'];continue
        if kind=='target-verified-suffix-abort':
            state=states[0];sequence(state,event['abort_sequence']);pending=state['pending']
            need(pending and all(r['tentative'] for r in pending) and event['discarded_rows']==[r['id'] for r in pending],
                 'actual ABORT differs from complete pending suffix')
            oldest=pending[0]
            need(oldest['position']==state['committed']==event['seed_position']+1
                 and event['actual_target_token']==inputs[oldest['position']]!=event['rejected_token']==oldest['token']
                 and provider_position==event['provider_serial'] and event['target_restore_bytecheck_required'] is True,
                 'suffix lacks actual target rejection or newest provider serial')
            need(states[-1]['committed']==oldest['position'] and states[-1]['accepted']['position']==oldest['position']-1,
                 'suffix aborted before final parent commit')
            aborts.append(dict(sequence=event['abort_sequence'],oldest=dict(oldest),discarded=[dict(r) for r in pending],
                               provider_position=provider_position,provider_serial=event['provider_serial']))
            sent[0].append(dict(op=26,sequence=event['abort_sequence'],row=oldest['id'],position=oldest['position']))
            state['physical']=state['committed'];state['pending']=[]
            need(event['physical']==event['committed']==state['committed'],'post-abort physical frontier differs');continue
        need(kind in ('row','accept'),'unknown pending controller event')
        index=event['stage'];need(type(index)is int and 0<=index<stage_count,'controller stage bounds')
        state=states[index];sequence(state,event['sequence'])
        if kind=='row':
            rowid=event['row'];position=event['position'];parentid=event['parent'];token=event['token']
            need(type(event['tentative'])is bool and (index==0 or event['tentative'] is False),'only first stage may hold tentative rows')
            expected_parent=state['pending'][-1] if state['pending'] else state['accepted']
            need(position==state['physical'] and parentid==(0 if expected_parent is None else expected_parent['id']),
                 'ROW physical cursor or full parent differs')
            before=initial if expected_parent is None else expected_parent['after'];after=prefix(before,position,token)
            item=dict(id=rowid,parent=parentid,position=position,token=token,before=before,after=after)
            if rowid in created:need(created[rowid]==item,'issued ROW identity was mutated')
            else:
                need(rowid>max(created,default=0),'global row identity not monotonic');created[rowid]=item
            need(not state['pending'] or event['tentative'] and all(r['tentative'] for r in state['pending']),
                 'verified ROW bypassed unaccepted work')
            local=dict(item,tentative=event['tentative'],row_sequence=event['sequence'],
                       provider_position_at_capture=provider_position,provider_serial_at_capture=provider_position)
            state['pending'].append(local);state['physical']+=1
            need(len(state['pending'])<=(2 if index==0 else 1),'pending capacity exceeded')
            sent[index].append(dict(op=24,sequence=event['sequence'],row=rowid,position=position))
        else:
            need(state['pending'] and event['row']==state['pending'][0]['id'],'ACCEPT did not name oldest issued row')
            local=state['pending'].pop(0)
            need(event['original_tentative'] is local['tentative'] and local['position']==state['committed']
                 and local['token']==inputs[state['committed']],'ACCEPT original flag or confirmed input differs')
            if local['tentative']:
                need(index==0 and states[-1]['committed']==local['position']
                     and states[-1]['accepted']['position']==local['position']-1,
                     'tentative input accepted before actual final parent commit')
            local['accept_sequence']=event['sequence'];state['accepted']=local;state['committed']+=1
            if index==stage_count-1:final_parents[local['position']]=local
            sent[index].append(dict(op=25,sequence=event['sequence'],row=local['id'],position=local['position']))
        need((event['physical'],event['committed'],event['pending'])
             ==(state['physical'],state['committed'],len(state['pending'])),'controller cursor/pending counters differ')
    need(all(not s['pending'] and s['physical']==s['committed']==len(inputs) for s in states),'terminal target not fully drained')
    need(provider_position==len(inputs)-1,'canonical provider steps incomplete')
    return dict(created=created,sent=sent,providers=providers,aborts=aborts,states=states)
