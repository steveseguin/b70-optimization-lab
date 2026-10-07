#!/usr/bin/env python3
"""Replay source bindings, exact citations and delivered evidence; no semantic oracle."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import evidence

ROOT=Path(__file__).resolve().parent

def audit(root, with_results=False):
    src=evidence.sources(root)
    manifest=evidence.read_json(root/'manifest.json')
    for name, binding in manifest['artifacts'].items():
        if evidence.digest((root/name).read_bytes()) != binding['sha256']: raise ValueError('artifact hash mismatch: '+name)
    for item,_ in src.values():
        original=subprocess.check_output(['git','show',item['commit']+':'+item['repository_path']],cwd=root)
        if original != (root/item['path']).read_bytes():
            raise ValueError('source differs from Git: '+item['id'])
    questions=evidence.read_json(root/'questions.json')['questions']
    refs=evidence.read_json(root/'reference.json')['questions']
    ids=[q['id'] for q in questions]
    if len(ids)!=12 or len(set(ids))!=12 or {q['id'] for q in refs}!=set(ids) or len(refs)!=12:
        raise ValueError('expected 12 unique matching questions')
    unknown=0
    for q in refs:
        if q['status']=='unknown':
            unknown+=1
            if q['reference_answer'] is not None: raise ValueError('unknown gold must be null')
        elif q['status']!='answered' or not isinstance(q['reference_answer'],str):
            raise ValueError('invalid reference answer')
        for criterion in q['criteria']:
            if not criterion['citations']: raise ValueError('unbound reference criterion')
            for c in criterion['citations']:
                if evidence.passage(src,c['source_id'],c['start_line'],c['end_line'])['text']!=c['quote']:
                    raise ValueError('reference quote mismatch')
    if unknown !=2: raise ValueError('expected two source-unknown questions')
    report={'schema':'project-decision-recall.audit.v1','source_files':len(src),
            'source_bytes':sum((root/x['path']).stat().st_size for x,_ in src.values()),
            'questions':12,'unknown_references':unknown,'git_bytes_exact':True,
            'reference_quotes_exact':True,'semantic_reference_quality':'requires independent review',
            'arms':{}}
    if with_results:
        for arm in ('full','search'):
            path=root/'results'/arm
            identity=evidence.read_json(path/'identity.json')
            if identity != {name:evidence.digest((root/name).read_bytes()) for name in ('manifest.json','questions.json','protocol.json','evidence.py')}: raise ValueError('trial identity changed')
            try:
                answers=evidence.read_json(path/'answers.json')
                mechanical=evidence.validate_answers(root,answers)
            except (ValueError, KeyError, TypeError) as error:
                answers={'answers':[]}
                mechanical={'mechanical_pass':False,'error':str(error),'semantic_quality':None}
            rows=[json.loads(line) for line in (path/'reads.jsonl').read_text().splitlines()]
            if not rows or len(rows)>64 or rows[-1]['command']!='submit': raise ValueError('invalid operation count/termination')
            seen={sid:set() for sid in src}; byte_total=0; full_count=0
            for n,row in enumerate(rows,1):
                if row['sequence']!=n: raise ValueError('log sequence mismatch')
                data=json.dumps(row['response'],ensure_ascii=False,indent=2).encode()
                if len(data)!=row['response_bytes'] or evidence.digest(data)!=row['response_sha256']:
                    raise ValueError('log response binding mismatch')
                byte_total+=len(data)
                if row['command']=='full':
                    full_count+=1
                    if arm!='full': raise ValueError('full delivery in search arm')
                    expected=[evidence.passage(src,sid,1,len(lines)) for sid,(_,lines) in src.items()]
                    if row['response']!=expected: raise ValueError('full response differs')
                    for item in expected: seen[item['source_id']].update(range(item['start_line'],item['end_line']+1))
                elif row['command']=='read':
                    if arm!='search': raise ValueError('read in full arm')
                    item=evidence.passage(src,row['source'],row['start'],row['end'])
                    if row['response']!=item: raise ValueError('read response differs')
                    seen[item['source_id']].update(range(item['start_line'],item['end_line']+1))
                elif row['command']=='search':
                    if arm!='search': raise ValueError('search in full arm')
                    pattern=evidence.re.compile(row['query'],evidence.re.I)
                    expected=[{'source_id':sid,'line':i,'text':line} for sid,(_,lines) in src.items() for i,line in enumerate(lines,1) if pattern.search(line)]
                    if row['response']!=expected: raise ValueError('search response differs')
                    for hit in expected: seen[hit['source_id']].add(hit['line'])
                elif row['command']=='catalog':
                    if row['response']['questions'] != evidence.read_json(root/'questions.json'): raise ValueError('catalog questions changed')
                    expected=[{'id':x['id'],'repository_path':x['repository_path'],'commit':x['commit'],'lines':len(lines)} for x,lines in src.values()]
                    if row['response']['sources'] != expected: raise ValueError('catalog sources changed')
                elif row['command']=='submit':
                    if n!=len(rows) or row['response']!=mechanical or row.get('submission_sha256')!=evidence.digest((path/'answers.json').read_bytes()): raise ValueError('submission receipt mismatch')
                elif row['command']!='rejected': raise ValueError('unknown command')
            if arm=='full' and full_count!=1: raise ValueError('expected one full delivery')
            if sum(r['response_bytes'] for r in rows if r['command'] not in ('submit','rejected'))>300000: raise ValueError('byte cap exceeded')
            unseen=[]
            for answer in answers['answers']:
                for c in answer['citations']:
                    if not set(range(c['start_line'],c['end_line']+1))<=seen[c['source_id']]: unseen.append(answer['id'])
            if unseen: raise ValueError('cited undelivered lines: '+str(unseen))
            reference_coverage={q['id']:[all(set(range(c['start_line'],c['end_line']+1))<=seen[c['source_id']] for c in cr['citations']) for cr in q['criteria']] for q in refs}
            report['arms'][arm]={'mechanical':mechanical,'operations':len(rows),
             'operation_counts':{k:sum(r['command']==k for r in rows) for k in sorted({r['command'] for r in rows})},
             'tool_response_bytes':byte_total,'first_read_to_submit_seconds':rows[-1]['time_unix']-rows[0]['time_unix'],
             'unique_source_lines_delivered':sum(map(len,seen.values())),
             'source_lines_total':sum(len(lines) for _,lines in src.values()),
             'all_cited_lines_delivered':True if mechanical.get('citations_exact') else None,'reference_span_coverage':reference_coverage,
             'tokens':None,'cached_tokens':None,'inference_cost':None,'peak_memory':None,
             'semantic_quality':None,'speed_qualification':False}
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--results',action='store_true'); p.add_argument('--out',type=Path)
    args=p.parse_args(); result=audit(ROOT,args.results); text=json.dumps(result,indent=2)+'\n'
    if args.out:
        with args.out.open('x') as out: out.write(text)
    else: print(text,end='')
