"""Exact frozen report83 replication and fresh dispatch97 sparse-state case."""
import hashlib
import json
import random
import re
from pathlib import Path

from engine import HERE, compiler, sha

SEEDS=(83,97)
COUNT=128
CHUNK=16
STEADY=16
FILLER='The clerks sorted the routine records before the courier arrived.'
RULES=['Read batches in increasing order. Every stated balance posting takes effect immediately.',
       'A question naming an end-of-batch time asks for the state after all postings in that batch.',
       'Ticket ownership does not change unless the source explicitly says it changes.']


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def replay_source(document):
    """Independent controlled-grammar source reader, not reuse of generated events."""
    patterns=[(re.compile(r'Dispatch recorded ([a-z]+[0-9]{2}) at a balance of (-?[0-9]+)\.'),'set'),
              (re.compile(r'A credit of ([0-9]+) was posted to ([a-z]+[0-9]{2})\.'),'add'),
              (re.compile(r'Dispatch posted a debit of ([0-9]+) against ([a-z]+[0-9]{2})\.'),'sub')]
    state={};states=[];events=[]
    for batch in document['batches']:
        updates=[]
        for line in batch['text'].splitlines():
            recognized=False
            for pattern,op in patterns:
                match=pattern.fullmatch(line)
                if not match:continue
                name,amount=(match[1],int(match[2])) if op=='set' else (match[2],int(match[1]))
                if op=='set':state[name]=amount
                else:state[name]+=amount if op=='add' else -amount
                updates.append({'counter':name,'op':op,'amount':amount,'quote':line})
                recognized=True
                break
            if recognized:continue
            if (line==' '.join((FILLER.split()*32)[:320])
                    or re.fullmatch(r'\S+ belongs to counter [a-z]+[0-9]{2}\.',line)
                    or re.fullmatch(r'\S+ concerns \S+\.',line)):continue
            raise ValueError('unrecognized source line: '+line[:160])
        states.append(dict(state));events.append(updates)
    return states,events


def make_case(seed):
    if type(seed) is not int or seed not in SEEDS:raise ValueError('only fixed report83/dispatch97 cases are preregistered')
    if seed==83:return original_case()
    count=COUNT
    rng=random.Random(seed)
    names=[f'unit{chr(97+i//26)}{chr(97+i%26)}10' for i in range(count)]
    reserve=names[-1];active=names[:-1];state={};batches=[];annotations=[];touched=set()
    initial=(count+CHUNK-1)//CHUNK
    filler=' '.join((FILLER.split()*32)[:320])
    def batch(updates):
        n=len(batches)+1;lines=[];events=[]
        for name,op,amount in updates:
            quote=({'set':f'Dispatch recorded {name} at a balance of {amount}.',
                    'add':f'A credit of {amount} was posted to {name}.',
                    'sub':f'Dispatch posted a debit of {amount} against {name}.'})[op]
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
    doc={'id':f'sparse-n{count}-seed{seed}-dispatch','pair_id':f'sparse-n{count}','variant':'generated',
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
            if match:
                if match[1] in source_owners:raise ValueError('duplicate source owner')
                source_owners[match[1]]=match[2]
            match=re.fullmatch(r'(\S+) concerns (\S+)\.',line)
            if match:
                if match[1] in source_reviews:raise ValueError('duplicate source review')
                source_reviews[match[1]]=match[2]
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
    provenance={'kind':'programmatically-generated','generator_seed':seed,'style':'dispatch','counter_count':count,
        'initialization_batches':initial,'initialization_chunk_max':CHUNK,'steady_batches':STEADY,
        'updates_per_steady_batch':3,'untouched_counter':reserve,
        'validation':'Separate controlled-grammar source replay checks states/events/answers; not independent human or assistant annotation.'}
    task['scope']='Generated sparse-state replication diagnostic; no authored-annotation or speed claim.'
    task['generated_provenance']=provenance
    task['task_sha256']=module.digest({k:v for k,v in task.items() if k!='task_sha256'})
    module.verify(task)
    return {'document':doc,'task':task,'metadata':provenance}


def original_case():
    pins=json.loads((HERE/'original-source.json').read_bytes())
    packet=HERE.parents[2]/pins['packet_relative_to_experiment']
    for name,digest in pins['files_sha256'].items():
        if sha(packet/name)!=digest:raise ValueError('original frozen report task/document changed')
    rawdoc=(packet/'sparse-n128-seed83-document.json').read_bytes()
    rawtask=(packet/'sparse-n128-seed83-task.json').read_bytes()
    document=json.loads(rawdoc);task=json.loads(rawtask);compiler().verify(task)
    return {'document':document,'task':task,'metadata':task['generated_provenance'],
            'document_bytes':rawdoc,'task_bytes':rawtask}


def historical_coverage(case):
    """Describe fixed question coverage; never select new questions from this metric."""
    document=case['document'];task=case['task'];owners={};reviews={}
    for batch in document['batches']:
        for line in batch['text'].splitlines():
            match=re.fullmatch(r'(\S+) belongs to counter ([a-z]+[0-9]{2})\.',line)
            if match:owners[match[1]]=match[2]
            match=re.fullmatch(r'(\S+) concerns (\S+)\.',line)
            if match:reviews[match[1]]=match[2]
    rows=[];categories={category:{'asked':0,'differs_from_final':0} for category in ('history','join')}
    for question in document['questions']:
        category=question['category']
        if category=='current':continue
        if category=='history':
            match=re.fullmatch(r'What was the balance of ([a-z]+[0-9]{2}) at the end of batch ([0-9]+)\?',question['text'])
            name=match[1];at=int(match[2])
        else:
            match=re.fullmatch(r"Follow (\S+) to its ticket and owner\. What was that owner counter's balance at the end of batch ([0-9]+)\?",question['text'])
            name=owners[reviews[match[1]]];at=int(match[2])
        value=task['oracle']['after_batch'][at-1][name];final=task['oracle']['after_batch'][-1][name]
        if value!=task['oracle']['answers'][question['id']]:raise ValueError('question coverage source/reference mismatch')
        differs=value!=final;categories[category]['asked']+=1;categories[category]['differs_from_final']+=differs
        rows.append({'id':question['id'],'category':category,'counter':name,'batch_id':at,
                     'value':value,'final_value':final,'differs_from_final':differs})
    return {'historical_questions':len(rows),'differs_from_final':sum(r['differs_from_final'] for r in rows),
            'categories':categories,'questions':rows}
