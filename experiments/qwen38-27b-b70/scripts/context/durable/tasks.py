#!/usr/bin/env python3
"""Deterministic synthetic pilot tasks. Answer keys never enter model prompts."""
import argparse
import hashlib
import json
import random
from pathlib import Path


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def make_task(seed=7, batches=48, filler_words=320, style='report'):
    if batches < 4 or filler_words < 0 or style not in ('report', 'dispatch'):
        raise ValueError('at least four batches, nonnegative filler, known style required')
    rng = random.Random(seed)
    counters = [f'{name}{i+10}' for i, name in enumerate(['amber','birch','cedar','dune','elm','fern','glen','heath'])]
    state, records, refs, event_refs = {}, [], [], []
    tickets = [f'ticket-{seed}-{i}' for i in range(8)]
    reviews = [f'review-{seed}-{i}' for i in range(8)]
    owners = rng.sample(counters, len(counters))
    seals = []
    filler = ['The clerks sorted the correspondence before the courier arrived.',
              'Rain tapped the windows while the warehouse doors remained shut.',
              'A visitor asked for directions and then returned to the courtyard.',
              'The shift supervisor checked the clock and tidied the empty desk.']
    for batch_id in range(1, batches + 1):
        lines, events = [], []
        names = counters if batch_id == 1 else rng.sample(counters, 3)
        for name in names:
            op = 'set' if batch_id == 1 else rng.choice(['set','add','sub'])
            amount = rng.randint(1, 90)
            if style == 'report':
                quote = {'set':f'The balance of {name} is now {amount}.',
                         'add':f'The balance of {name} increased by {amount}.',
                         'sub':f'The balance of {name} decreased by {amount}.'}[op]
            else:
                quote = {'set':f'{name}: replace the recorded balance with {amount}.',
                         'add':f'{name}: credit {amount} to the recorded balance.',
                         'sub':f'{name}: debit {amount} from the recorded balance.'}[op]
            state[name] = amount if op == 'set' else state[name] + (amount if op == 'add' else -amount)
            events.append({'id':f'{batch_id}:{len(events)}','counter':name,'op':op,'amount':amount,'quote':quote})
            lines.append(quote)
        seal = '-'.join(rng.sample(['copper','willow','silver','orchid','linen','marble','raven','pearl','violet','maple'],3))
        seals.append(seal)
        lines.append(f'The delivery seal for batch {batch_id} was {seal}.')
        if batch_id == 1:
            lines.extend(f'{ticket} belongs to counter {owner}.' for ticket,owner in zip(tickets,owners))
        if batch_id == batches:
            lines.extend(f'{review} concerns {ticket}.' for review,ticket in zip(reviews,tickets))
        # Filler is task input, not cached/generated model content. It carries no ledger updates.
        noise = []
        while len(' '.join(noise).split()) < filler_words:
            noise.append(rng.choice(filler))
        pos = rng.randrange(len(lines)+1)
        lines[pos:pos] = noise
        records.append({'id':batch_id,'text':'\n'.join(lines)})
        refs.append(dict(state));event_refs.append(events)
    questions, answers = [], {}
    for i, name in enumerate(counters):
        qid=f'current-{i}'
        questions.append({'id':qid,'category':'current','question':f'What is the final balance of {name}?'})
        answers[qid]=state[name]
        old_batch=1+(i*(batches-2)//8)
        qid=f'history-{i}'
        questions.append({'id':qid,'category':'history','question':f'What was the delivery seal for batch {old_batch}?'})
        answers[qid]=seals[old_batch-1]
        qid=f'join-{i}'
        questions.append({'id':qid,'category':'join','question':f'What was the balance at the end of batch 2 of the counter associated with {reviews[i]}?'})
        answers[qid]=refs[1][owners[i]]
    task={'schema':'durable-context-task.v1','seed':seed,'style':style,'batches':records,
          'questions':questions,'oracle':{'answers':answers,'after_batch':refs,'events':event_refs},
          'scope':'Synthetic pilot; two authored writing styles, not a general-document benchmark.'}
    task['task_sha256']=hashlib.sha256(encoded(task)).hexdigest()
    return task


def verify(task):
    if not isinstance(task,dict) or task.get('schema')!='durable-context-task.v1':
        raise ValueError('unsupported task object or schema')
    if type(task.get('seed')) is not int or task.get('style') not in ('report','dispatch'):
        raise ValueError('task needs an integer seed and a known style')
    if not isinstance(task.get('task_sha256'),str):
        raise ValueError('task hash missing')
    body={k:v for k,v in task.items() if k!='task_sha256'}
    if hashlib.sha256(encoded(body)).hexdigest()!=task['task_sha256']:
        raise ValueError('task hash mismatch')
    batches=task.get('batches');questions=task.get('questions');oracle=task.get('oracle')
    if not isinstance(batches,list) or not batches:
        raise ValueError('batches must be a nonempty list')
    for number,batch in enumerate(batches,1):
        if (not isinstance(batch,dict) or type(batch.get('id')) is not int
                or batch['id']!=number or not isinstance(batch.get('text'),str)):
            raise ValueError('batch IDs must be contiguous integers starting at 1, with text')
    if not isinstance(questions,list) or not questions or not isinstance(oracle,dict):
        raise ValueError('questions and oracle are required')
    answers=oracle.get('answers');refs=oracle.get('after_batch');event_refs=oracle.get('events')
    if not isinstance(answers,dict):
        raise ValueError('oracle answers must be an object')
    question_ids=[]
    for question in questions:
        if (not isinstance(question,dict) or not isinstance(question.get('id'),str)
                or not question['id'] or question.get('category') not in ('current','history','join')
                or not isinstance(question.get('question'),str) or not question['question']):
            raise ValueError('each question needs an ID, known category and nonempty text')
        question_ids.append(question['id'])
    if len(set(question_ids))!=len(question_ids) or set(question_ids)!=set(answers):
        raise ValueError('question IDs must be unique and exactly match oracle answer keys')
    for question in questions:
        answer=answers[question['id']]
        required_type=str if question['category']=='history' else int
        if type(answer) is not required_type:
            raise ValueError('oracle answer type differs from its question category')
    if (not isinstance(refs,list) or not isinstance(event_refs,list)
            or len(refs)!=len(batches) or len(event_refs)!=len(batches)):
        raise ValueError('one reference state and event list are required for every batch')
    event_ids=set();state={}
    for batch,reference,events in zip(batches,refs,event_refs):
        if (not isinstance(reference,dict) or any(not isinstance(k,str) or not k or type(v) is not int
                                                  for k,v in reference.items())):
            raise ValueError('reference states must map nonempty names to integer balances')
        if not isinstance(events,list):
            raise ValueError('each batch needs a list of events')
        for event in events:
            if not isinstance(event,dict) or set(event)!={'id','counter','op','amount','quote'}:
                raise ValueError('oracle event fields are invalid')
            identifier=event['id'];counter=event['counter'];op=event['op'];amount=event['amount'];quote=event['quote']
            if not isinstance(identifier,str) or not identifier or identifier in event_ids:
                raise ValueError('oracle event IDs must be nonempty and globally unique')
            event_ids.add(identifier)
            if (not isinstance(counter,str) or not counter or op not in ('set','add','sub')
                    or type(amount) is not int or (op in ('add','sub') and amount<=0)
                    or not isinstance(quote,str) or not quote or quote not in batch['text']):
                raise ValueError('oracle event counter, operation, amount or source quote is invalid')
            if op!='set' and counter not in state:
                raise ValueError('oracle arithmetic references an uninitialized counter')
            state[counter]=amount if op=='set' else state[counter]+(amount if op=='add' else -amount)
        if state!=reference:
            raise ValueError('oracle events and after-batch reference state disagree')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seeds',type=int,nargs='+',default=[7])
    p.add_argument('--styles',nargs='+',choices=['report','dispatch'],default=['report','dispatch'])
    p.add_argument('--batches',type=int,default=48)
    p.add_argument('--filler-words',type=int,default=320)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    cases=[]
    for seed in args.seeds:
        for style in args.styles:
            task=make_task(seed,args.batches,args.filler_words,style)
            path=args.out/f'{style}-seed{seed}.json'
            data=json.dumps(task,ensure_ascii=False,indent=2)+'\n'
            if path.exists() and path.read_text()!=data:
                raise SystemExit(f'refusing to overwrite a different task: {path}')
            path.write_text(data)
            cases.append({'path':path.name,'task_sha256':task['task_sha256'],
                          'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest={'schema':'durable-context-suite.v1','cases':cases,'arms':['summary','archive','quoted'],
              'question_counts':{'current':8,'history':8,'join':8},'batches':args.batches,
              'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dest=args.out/'suite.json'
    data=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
    if dest.exists() and dest.read_text()!=data:
        raise SystemExit('refusing to change existing suite manifest')
    dest.write_text(data)
    print(f'Wrote {len(cases)} cases; 24 fixed questions each')

if __name__=='__main__':main()
