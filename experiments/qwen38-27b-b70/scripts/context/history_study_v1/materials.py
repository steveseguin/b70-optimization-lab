"""Pinned authored input packet and fixed eight-condition matrix; no generation."""
import json
from pathlib import Path
from engine import HERE, compiler, sha

CASES=('t01-clinic','t02-theatre')
CONDITIONS={'AS':('archive','source-only'),'QH':('quoted','history'),
            'QS':('quoted','source-only'),'AH':('archive','history')}
ORDER=(('t01-clinic','AS'),('t01-clinic','QH'),('t01-clinic','QS'),('t01-clinic','AH'),
       ('t02-theatre','AH'),('t02-theatre','QS'),('t02-theatre','QH'),('t02-theatre','AS'))


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def pins():return json.loads((HERE/'input-pins.json').read_bytes())


def input_bytes():
    lane=HERE.parents[2];result={}
    for row in pins()['files']:
        path=(lane/row['path']).resolve()
        if not path.is_relative_to(lane) or sha(path)!=row['sha256']:
            raise ValueError('frozen study input changed: '+row['path'])
        result[row['copy_path']]=path.read_bytes()
    return result


def cases_from(packet):
    packet=Path(packet).resolve()
    for row in pins()['files']:
        path=(packet/row['copy_path']).resolve()
        if not path.is_relative_to(packet) or sha(path)!=row['sha256']:
            raise ValueError('copied study input hash/path mismatch')
    source=packet/'source'
    tasks={task['document_id']:task for task in compiler().load_packet(source/'documents.json',source/'adjudicated.json')}
    documents={doc['id']:doc for doc in json.loads((source/'documents.json').read_bytes())['documents']}
    if sorted(tasks)[:2]!=list(CASES):raise ValueError('fixed first two document identities changed')
    return {case:{'document':documents[case],'task':tasks[case]} for case in CASES}


def expected_rows(cases):
    result=[]
    for case,condition in ORDER:
        task=cases[case]['task'];arm,mode=CONDITIONS[condition];directory=f'{case}-{condition}'
        result.append({'case_id':case,'condition':condition,'arm':arm,'retrieval_mode':mode,
            'counter_count':8,'initialization_batches':1,'task_sha256':task['task_sha256'],
            'question_sha256':compiler().digest(task['questions']),
            'task_path':f'{case}-task.json','document_path':f'{case}-document.json',
            'result_path':f'{directory}/result.json','native_result_path':f'{directory}/native/result.json'})
    return result
