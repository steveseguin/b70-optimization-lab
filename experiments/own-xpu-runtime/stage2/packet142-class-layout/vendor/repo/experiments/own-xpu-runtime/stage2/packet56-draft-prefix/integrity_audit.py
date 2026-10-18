#!/usr/bin/env python3
"""Parse packet JSON and verify retained scratch bytes without trusting pass flags."""
import base64,gzip,hashlib,json
from pathlib import Path
from storage import P,digest,verify_archive

def main():
    rows=[];parsed=0;members=0
    for path in sorted(P.glob('*.json')):
        if path.name=='retained-integrity.json':continue
        json.loads(path.read_text());parsed+=1
        rows.append(dict(path=path.name,sha256=digest(path),kind='JSON'))
    for path in sorted((P/'evidence').glob('scratch-*.gz')):
        if path.name.endswith('.jsonl.gz'):
            checked=verify_archive(path)
            with gzip.open(path,'rt') as source:
                next(source);current=None;data=None
                for line in source:
                    row=json.loads(line)
                    if row['kind']=='file':
                        current=row;data=bytearray() if row['retained'] and row['path'].endswith('.json') else None
                    elif row['kind']=='chunk' and data is not None:data.extend(base64.b64decode(row['base64'],validate=True))
                    elif row['kind']=='end' and data is not None:json.loads(data);parsed+=1
            members+=checked['retained_files']
        else:
            checked=dict(retained_files=0,files=0)
            with gzip.open(path,'rt') as source:archive=json.load(source)
            for row in archive:
                checked['files']+=1
                if 'text' in row:
                    raw=row['text'].encode();assert len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],row['path']
                    checked['retained_files']+=1;members+=1
                    if row['path'].endswith('.json'):json.loads(row['text']);parsed+=1
        rows.append(dict(path=str(path.relative_to(P)),sha256=digest(path),kind='scratch archive',**checked))
    result=dict(passed=True,device_executed=False,parsed_json_records=parsed,retained_members_verified=members,
                source_sha256={'integrity_audit.py':digest(P/'integrity_audit.py'),'storage.py':digest(P/'storage.py')},files=rows,
                scope='top-level JSON and completed scratch archive bytes; historical failed/interrupted receipts are parsed, never promoted; current binary/input/quality hashes are independently required by seal.py')
    (P/'retained-integrity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('passed','parsed_json_records','retained_members_verified')}))
if __name__=='__main__':main()
