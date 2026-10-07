#!/usr/bin/env python3
"""Replay supplemental transport bytes; model-visible receipt remains an attestation."""
import json
from pathlib import Path
import evidence
import paged_full

ROOT=Path(__file__).resolve().parent

def audit(root):
    for filename in ('freeze.json','transport-plan.json'):
        for name,sha in evidence.read_json(root/filename)['files_sha256'].items():
            if evidence.digest((root/name).read_bytes())!=sha: raise ValueError('frozen file changed: '+name)
    folder=root/'results/full-paged'; rows=[json.loads(x) for x in (folder/'reads.jsonl').read_text().splitlines()]
    parts=paged_full.pages(root)
    if len(rows)!=len(parts)+2: raise ValueError('missing or extra operation')
    src=evidence.sources(root)
    expected_catalog={'questions':evidence.read_json(root/'questions.json'),'pages':len(parts),
        'sources':[{'id':x['id'],'repository_path':x['repository_path'],'commit':x['commit'],'lines':len(lines)} for x,lines in src.values()],
        'contract':'Same status/answer/explanation/full-line citations contract as question instructions. All source lines must be received before answering.'}
    expected=[('catalog',None,expected_catalog)]+[('page',i,{'page':i,'pages':len(parts),'lines':page}) for i,page in enumerate(parts,1)]
    try:mechanical=evidence.validate_answers(root,evidence.read_json(folder/'answers.json'))
    except (ValueError,KeyError,TypeError) as error:mechanical={'mechanical_pass':False,'error':str(error),'semantic_quality':None}
    expected.append(('submit',None,mechanical))
    for n,(row,(command,page,response)) in enumerate(zip(rows,expected),1):
        data=json.dumps(response,ensure_ascii=False,indent=2).encode()
        if row['sequence']!=n or row['command']!=command or row['page']!=page or row['response']!=response:raise ValueError('operation replay mismatch')
        if row['response_bytes']!=len(data) or row['response_sha256']!=evidence.digest(data) or len(data)>6500:raise ValueError('payload hash/size mismatch')
    if rows[-1]['submission_sha256']!=evidence.digest((folder/'answers.json').read_bytes()):raise ValueError('answer bytes changed')
    actual=[(line['source_id'],line['line'],line['text']) for page in parts for line in page]
    original=[(sid,n,line) for sid,(_,lines) in src.items() for n,line in enumerate(lines,1)]
    if actual!=original:raise ValueError('source coverage mismatch')
    return {'schema':'project-decision-recall.paged-audit.v1','mechanical':mechanical,'source_lines_emitted':len(actual),'every_line_exact_once_ordered':True,'operations':len(rows),'page_count':len(parts),'max_page_payload_bytes':max(r['response_bytes'] for r in rows if r['command']=='page'),'tool_response_bytes':sum(r['response_bytes'] for r in rows),'first_read_to_submit_seconds':rows[-1]['time_unix']-rows[0]['time_unix'],'model_visible_completeness':'Requires separate answerer attestation; emitted logs alone cannot prove perception.','tokens':None,'cached_tokens':None,'inference_cost':None,'peak_memory':None,'semantic_quality':None,'speed_qualification':False}

if __name__=='__main__':print(json.dumps(audit(ROOT),indent=2))
