#!/usr/bin/env python3
"""Supplemental complete-source delivery after the original display truncation."""
import argparse
import fcntl
import json
import time
from pathlib import Path
import evidence

ROOT=Path(__file__).resolve().parent

def pages(root):
    result=[]; current=[]
    for sid,(_,lines) in evidence.sources(root).items():
        for n,line in enumerate(lines,1):
            item={'source_id':sid,'line':n,'text':line}
            candidate=current+[item]
            if len(json.dumps(candidate,ensure_ascii=False,indent=2).encode())>5000:
                if not current: raise ValueError('single source line exceeds page budget')
                result.append(current); current=[item]
            else: current=candidate
    if current: result.append(current)
    return result

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['catalog','page','submit']); parser.add_argument('--number',type=int); parser.add_argument('--file',type=Path)
    args=parser.parse_args()
    frozen=evidence.read_json(ROOT/'freeze.json')['files_sha256']
    extra=evidence.read_json(ROOT/'transport-plan.json')['files_sha256']
    for name,sha in {**frozen,**extra}.items():
        if evidence.digest((ROOT/name).read_bytes())!=sha: raise ValueError('frozen input changed: '+name)
    parts=pages(ROOT); folder=ROOT/'results/full-paged'; folder.mkdir(parents=True,exist_ok=True)
    with (folder/'.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        log=folder/'reads.jsonl'; rows=[json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
        if (folder/'answers.json').exists(): raise ValueError('already submitted')
        expected='catalog' if not rows else ('page' if len(rows)<=len(parts) else 'submit')
        if args.command!=expected or (expected=='page' and args.number!=len(rows)):
            raise ValueError('must receive catalog and every page in order before submission')
        if args.command=='catalog':
            result={'questions':evidence.read_json(ROOT/'questions.json'),'pages':len(parts),
                    'sources':[{'id':x['id'],'repository_path':x['repository_path'],'commit':x['commit'],'lines':len(lines)} for x,lines in evidence.sources(ROOT).values()],
                    'contract':'Same status/answer/explanation/full-line citations contract as question instructions. All source lines must be received before answering.'}
        elif args.command=='page': result={'page':args.number,'pages':len(parts),'lines':parts[args.number-1]}
        else:
            with (folder/'answers.json').open('xb') as out: out.write(args.file.read_bytes())
            try: result=evidence.validate_answers(ROOT,evidence.read_json(folder/'answers.json'))
            except (ValueError,KeyError,TypeError) as error: result={'mechanical_pass':False,'error':str(error),'semantic_quality':None}
            (folder/'mechanical.json').write_text(json.dumps(result,indent=2)+'\n')
        text=json.dumps(result,ensure_ascii=False,indent=2)
        if len(text.encode())>6500: raise ValueError('response exceeds display budget')
        row={'sequence':len(rows)+1,'command':args.command,'page':args.number,'time_unix':time.time(),'response_bytes':len(text.encode()),'response_sha256':evidence.digest(text.encode()),'response':result}
        if args.command=='submit':row['submission_sha256']=evidence.digest((folder/'answers.json').read_bytes())
        with log.open('a') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(text)

if __name__=='__main__':main()
