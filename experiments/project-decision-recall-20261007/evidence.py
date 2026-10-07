#!/usr/bin/env python3
"""Small, logged source reader. Citation validation is separate from meaning review."""
import argparse
import fcntl
import hashlib
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_json(path):
    def unique(pairs):
        value = {}
        for k, v in pairs:
            if k in value:
                raise ValueError('duplicate JSON key: ' + k)
            value[k] = v
        return value
    return json.loads(path.read_text(), object_pairs_hook=unique)

def sources(root):
    manifest = read_json(root / 'manifest.json')
    result = {}
    for item in manifest['sources']:
        path = root / item['path']
        if path.resolve().parent != (root / 'sources').resolve():
            raise ValueError('source path outside corpus')
        data = path.read_bytes()
        if digest(data) != item['sha256']:
            raise ValueError('source hash mismatch: ' + item['id'])
        if item['id'] in result:
            raise ValueError('duplicate source id')
        result[item['id']] = (item, data.decode().splitlines())
    return result

def passage(src, sid, start, end):
    item, lines = src[sid]
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise ValueError('invalid line range')
    return {'source_id': sid, 'start_line': start, 'end_line': end,
            'text': '\n'.join(lines[start - 1:end]),
            'numbered_text': '\n'.join(f'{n}: {lines[n-1]}' for n in range(start, end+1))}

def validate_answers(root, value):
    src = sources(root)
    expected = {q['id'] for q in read_json(root / 'questions.json')['questions']}
    if set(value) != {'answers'} or not isinstance(value['answers'], list):
        raise ValueError('expected answers array only')
    seen = set()
    for answer in value['answers']:
        if set(answer) != {'id','status','answer','explanation','citations'}:
            raise ValueError('incorrect answer fields')
        qid = answer['id']
        if qid not in expected or qid in seen:
            raise ValueError('missing, extra or duplicate answer id')
        seen.add(qid)
        if answer['status'] not in ('answered','unknown'):
            raise ValueError('invalid status')
        if answer['status'] == 'unknown':
            if answer['answer'] is not None:
                raise ValueError('unknown requires null')
        elif not isinstance(answer['answer'], str) or not answer['answer'].strip():
            raise ValueError('answered requires nonempty text')
        if not isinstance(answer['explanation'], str) or not answer['explanation'].strip():
            raise ValueError('explanation required')
        if not isinstance(answer['citations'], list) or not answer['citations']:
            raise ValueError('scope/context citations required even for unknown')
        for citation in answer['citations']:
            if set(citation) != {'source_id','start_line','end_line','quote'}:
                raise ValueError('incorrect citation fields')
            found = passage(src,citation['source_id'],citation['start_line'],citation['end_line'])
            if citation['quote'] != found['text']:
                raise ValueError('quote does not equal complete cited lines')
    if seen != expected:
        raise ValueError('answer set incomplete')
    return {'questions': len(seen), 'citations_exact': True, 'semantic_quality': None}

def _run(args):
    root = args.root.resolve()
    src = sources(root)
    trial = root / 'results' / args.arm
    trial.mkdir(parents=True, exist_ok=True)
    log_path = trial / 'reads.jsonl'
    rows = [json.loads(x) for x in log_path.read_text().splitlines()] if log_path.exists() else []
    if (trial / 'answers.json').exists():
        raise ValueError('trial already submitted')
    if len(rows) >= 64:
        raise ValueError('64 operation limit reached')
    if args.command == 'catalog':
        result = {'sources':[{'id':x['id'],'repository_path':x['repository_path'],'commit':x['commit'],'lines':len(lines)} for x,lines in src.values()],
                  'questions':read_json(root / 'questions.json'),
                  'answer_contract':{'answers':[{'id':'question id','status':'answered|unknown','answer':'text or null for unknown','explanation':'reasoning and corpus scope','citations':[{'source_id':'id','start_line':1,'end_line':2,'quote':'exact complete lines joined with newline'}]}]}}
    elif args.command == 'full':
        if args.arm != 'full' or any(x['command'] == 'full' for x in rows):
            raise ValueError('full is available once to full arm only')
        result = [passage(src,sid,1,len(lines)) for sid,(_,lines) in src.items()]
    elif args.command == 'search':
        if args.arm != 'search':
            raise ValueError('search arm only')
        # Ordinary case-insensitive regex line search, deterministic source order.
        pattern = re.compile(args.query, re.I)
        result = [{'source_id':sid,'line':n,'text':line} for sid,(_,lines) in src.items()
                  for n,line in enumerate(lines,1) if pattern.search(line)]
    elif args.command == 'read':
        if args.arm != 'search':
            raise ValueError('search arm only')
        result = passage(src,args.source,args.start,args.end)
    else:
        # Preserve a first submission even when mechanical validation fails.
        raw = args.file.read_bytes()
        with (trial / 'answers.json').open('xb') as first:
            first.write(raw)
        try:
            result = validate_answers(root, read_json(trial / 'answers.json'))
        except (ValueError, KeyError, TypeError) as error:
            result = {'mechanical_pass':False,'error':str(error),'semantic_quality':None}
        (trial / 'mechanical.json').write_text(json.dumps(result,indent=2)+'\n')
    encoded = json.dumps(result,ensure_ascii=False,indent=2)
    # Full text includes numbered + unnumbered copies for auditable exact quoting.
    delivered = len(encoded.encode())
    prior = sum(x['response_bytes'] for x in rows if x['command'] != 'rejected')
    if args.command != 'submit' and prior + delivered > 300000:
        raise ValueError('300000 returned-byte limit exceeded')
    row = {'sequence':len(rows)+1,'command':args.command,'query':args.query,
           'source':args.source,'start':args.start,'end':args.end,
           'time_unix':time.time(),'response_bytes':delivered,'response_sha256':digest(encoded.encode()),'response':result}
    if args.command == 'submit':
        row['submission_sha256'] = digest((trial/'answers.json').read_bytes())
    with log_path.open('a') as file:
        file.write(json.dumps(row,ensure_ascii=False)+'\n')
    print(encoded)

def run(args):
    root = args.root.resolve()
    trial = root / 'results' / args.arm
    trial.mkdir(parents=True, exist_ok=True)
    with (trial / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        identity = {name: digest((root/name).read_bytes()) for name in
                    ('manifest.json', 'questions.json', 'protocol.json', 'evidence.py')}
        identity_path = trial / 'identity.json'
        if identity_path.exists():
            if read_json(identity_path) != identity:
                raise ValueError('trial input identity changed')
        else:
            with identity_path.open('x') as file:
                file.write(json.dumps(identity, indent=2)+'\n')
        log_path = trial / 'reads.jsonl'
        prior = [json.loads(line) for line in log_path.read_text().splitlines()] if log_path.exists() else []
        if len(prior) >= 64 or (trial/'answers.json').exists():
            raise ValueError('trial closed or operation limit reached')
        try:
            _run(args)
        except (ValueError, KeyError, TypeError, re.error, OSError) as error:
            # Rejections consume an operation and remain visible in the evidence.
            result = {'error': str(error)}
            encoded = json.dumps(result, ensure_ascii=False, indent=2)
            row = {'sequence':len(prior)+1, 'command':'rejected',
                   'attempted_command':args.command, 'query':args.query,
                   'source':args.source, 'start':args.start, 'end':args.end,
                   'time_unix':time.time(), 'response_bytes':len(encoded.encode()),
                   'response_sha256':digest(encoded.encode()), 'response':result}
            with log_path.open('a') as file:
                file.write(json.dumps(row, ensure_ascii=False)+'\n')
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--arm',choices=['full','search'],required=True)
    parser.add_argument('command',choices=['catalog','full','search','read','submit'])
    parser.add_argument('--query')
    parser.add_argument('--source')
    parser.add_argument('--start',type=int)
    parser.add_argument('--end',type=int)
    parser.add_argument('--file',type=Path)
    run(parser.parse_args())

if __name__ == '__main__':
    main()
