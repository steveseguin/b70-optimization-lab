"""Fixed seed-83 synthetic sparse-state documents and honestly programmatic keys."""
import hashlib
import json
import random
import re

from engine import compiler

SEED=83
COUNTS=(8,128)
CHUNK=16
STEADY=16
FILLER='The clerks sorted the routine records before the courier arrived.'
RULES=['Read batches in increasing order. Every stated balance posting takes effect immediately.',
       'A question naming an end-of-batch time asks for the state after all postings in that batch.',
       'Ticket ownership does not change unless the source explicitly says it changes.']


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def replay_source(document):
    """Independent controlled-grammar source reader, not reuse of generated events."""
    pattern=re.compile(r'The balance of ([a-z]+[0-9]{2}) (is now|increased by|decreased by) (-?[0-9]+)\.')
    state={};states=[];events=[]
    for batch in document['batches']:
        updates=[]
        for line in batch['text'].splitlines():
            match=pattern.fullmatch(line)
            if not match:continue
            name,verb,amount=match.groups();amount=int(amount)
            if verb=='is now':state[name]=amount;op='set'
            elif verb=='increased by':state[name]=state[name]+amount;op='add'
            else:state[name]=state[name]-amount;op='sub'
            updates.append({'counter':name,'op':op,'amount':amount,'quote':line})
        states.append(dict(state));events.append(updates)
    return states,events


def make_case(count):
    if count not in COUNTS:raise ValueError('only fixed 8/128-counter cases are preregistered')
    rng=random.Random(SEED)
    names=[f'unit{chr(97+i//26)}{chr(97+i%26)}10' for i in range(count)]
    reserve=names[-1];active=names[:-1];state={};batches=[];annotations=[];touched=set()
    initial=(count+CHUNK-1)//CHUNK
    filler=' '.join((FILLER.split()*32)[:320])
    def batch(updates):
        n=len(batches)+1;lines=[];events=[]
        for name,op,amount in updates:
            verb={'set':'is now','add':'increased by','sub':'decreased by'}[op]
            quote=f'The balance of {name} {verb} {amount}.'
            lines.append(quote);events.append({'counter':name,'op':op,'amount':amount,'quote':quote})
            if op=='set':state[name]=amount
            else:state[name]+=amount if op=='add' else -amount
        lines.append(filler)
        batches.append({'id':n,'text':'\n'.join(lines)})
        annotations.append({'batch_id':n,'events':events,'state_after':dict(state)})
    for start in range(0,count,CHUNK):batch([(name,'set',rng.randint(100,199)) for name in names[start:start+CHUNK]])
    for step in range(STEADY):
        targets=([active[(step*3+j)%len(active)] for j in range(3)] if step<3 else rng.sample(active,3))
        touched.update(targets)
        batch([(name,rng.choice(('set','add','sub')),rng.randint(1,90)) for name in targets])
    subjects=sorted(touched)[:7]+[reserve]
    assert len(subjects)==8 and reserve not in touched
    owners=list(subjects);rng.shuffle(owners)
    tickets=[f'ticket-n{count}-{i}' for i in range(8)]
    reviews=[f'review-n{count}-{i}' for i in range(8)]
    batches[0]['text']+='\n'+'\n'.join(f'{ticket} belongs to counter {owner}.' for ticket,owner in zip(tickets,owners))
    batches[-1]['text']+='\n'+'\n'.join(f'{review} concerns {ticket}.' for review,ticket in zip(reviews,tickets))
    questions=[];answers={}
    for i,name in enumerate(subjects):
        q=f'current-{i}';questions.append({'id':q,'category':'current','answer_type':'int',
            'text':f'What is the balance of {name} at the end of batch {len(batches)}?'})
        answers[q]=state[name]
        historical=initial+1+(i*15//7)
        q=f'history-{i}';questions.append({'id':q,'category':'history','answer_type':'int',
            'text':f'What was the balance of {name} at the end of batch {historical}?'})
        answers[q]=annotations[historical-1]['state_after'][name]
        at=initial+1+((i*5+2)%16)
        q=f'join-{i}';questions.append({'id':q,'category':'join','answer_type':'int',
            'text':f'Follow {reviews[i]} to its ticket and owner. What was that owner counter\'s balance at the end of batch {at}?'})
        answers[q]=annotations[at-1]['state_after'][owners[i]]
    doc={'id':f'sparse-n{count}-seed83','pair_id':f'sparse-n{count}','variant':'generated',
         'batches':batches,'questions':questions}
    independent_states,independent_events=replay_source(doc)
    if independent_states!=[r['state_after'] for r in annotations] or independent_events!=[r['events'] for r in annotations]:
        raise ValueError('source replay disagrees with generator reference')
    # Independently parse emitted ownership/review text and requested question
    # names/times. Do not reuse the generator's owners or descriptor arrays.
    source_owners={};source_reviews={}
    for source in batches:
        for line in source['text'].splitlines():
            match=re.fullmatch(r'(\S+) belongs to counter ([a-z]+[0-9]{2})\.',line)
            if match:source_owners[match[1]]=match[2]
            match=re.fullmatch(r'(\S+) concerns (\S+)\.',line)
            if match:source_reviews[match[1]]=match[2]
    independent_answers={}
    for question in questions:
        match=re.fullmatch(r'What (?:is|was) the balance of ([a-z]+[0-9]{2}) at the end of batch ([0-9]+)\?',question['text'])
        if match:name,at=match[1],int(match[2])
        else:
            match=re.fullmatch(r"Follow (\S+) to its ticket and owner\. What was that owner counter's balance at the end of batch ([0-9]+)\?",question['text'])
            if not match:raise ValueError('independent reader cannot interpret question')
            name=source_owners[source_reviews[match[1]]];at=int(match[2])
        independent_answers[question['id']]=independent_states[at-1][name]
    if independent_answers!=answers:raise ValueError('independent answer replay mismatch')
    source_sha=hashlib.sha256(encoded(doc)).hexdigest()
    annotation={'document_id':doc['id'],'source_sha256':source_sha,'batches':annotations,'answers':answers}
    module=compiler();task=module.compile_document(doc,annotation,source_sha,reading_conventions=RULES)
    provenance={'kind':'programmatically-generated','generator_seed':SEED,'counter_count':count,
        'initialization_batches':initial,'initialization_chunk_max':CHUNK,'steady_batches':STEADY,
        'updates_per_steady_batch':3,'untouched_counter':reserve,
        'validation':'Separate controlled-grammar source replay checks states/events/answers; not independent human or assistant annotation.'}
    task['scope']='Generated sparse-state development diagnostic; no authored-annotation or speed claim.'
    task['generated_provenance']=provenance
    task['task_sha256']=module.digest({k:v for k,v in task.items() if k!='task_sha256'})
    module.verify(task)
    return {'document':doc,'task':task,'metadata':provenance}
