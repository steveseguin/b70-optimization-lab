"""Local-tokenizer CPU wiring checks, executed in an interpreter with tokenizers."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ['TOKENIZERS_PARALLELISM']='false'
from tokenizers import Tokenizer, __version__ as tokenizer_version
from engine import ENGINE, verify_engine


def main():
    request=json.load(sys.stdin);verify_engine()
    tokenizer_path=Path(request['tokenizer']);tokenizer=Tokenizer.from_file(str(tokenizer_path))
    sys.path.insert(0,str(ENGINE))
    import live
    rows=[]
    with tempfile.TemporaryDirectory(prefix='sparse-tokenizer-fit-') as temp:
        for index,item in enumerate(request['trials']):
            task=json.loads(Path(item['task_path']).read_bytes());out=Path(temp)/str(index)
            live.run_trial(task,item['arm'],out,live.StubClient(task))
            calls=[json.loads(line) for line in (out/'calls.jsonl').read_text().splitlines()]
            initial=task['generated_provenance']['initialization_batches'];phases={}
            for call in calls:
                phase='answer' if call['phase']=='answer' else 'initialization' if call['batch_id']<=initial else 'steady'
                row=phases.setdefault(phase,{'calls':0,'max_reference_prompt_bytes':0,'max_reference_response_bytes':0,
                    'max_reference_response_tokens':0,'max_prompt_bytes_with_ascii_memory_allowance':0})
                row['calls']+=1
                row['max_reference_prompt_bytes']=max(row['max_reference_prompt_bytes'],call['prompt_bytes'])
                row['max_reference_response_bytes']=max(row['max_reference_response_bytes'],len(call['response'].encode()))
                tokens=len(tokenizer.encode(call['response'],add_special_tokens=False).ids)
                row['max_reference_response_tokens']=max(row['max_reference_response_tokens'],tokens)
                messages=call['messages'];payload=json.loads(messages[1]['content']);payload['memory']='x'*live.MEMORY_LIMIT
                messages[1]['content']=json.dumps(payload,ensure_ascii=False)
                row['max_prompt_bytes_with_ascii_memory_allowance']=max(row['max_prompt_bytes_with_ascii_memory_allowance'],len(live.encoded(messages)))
            rows.append({'case_id':item['case_id'],'arm':item['arm'],'task_sha256':task['task_sha256'],'phases':phases})
    result={'schema':'sparse-state-budget-receipt.v1','tokenizer_path':str(tokenizer_path.resolve()),
        'tokenizer_sha256':hashlib.sha256(tokenizer_path.read_bytes()).hexdigest(),'tokenizers_version':tokenizer_version,
        'engine_source_sha256':verify_engine()['source_sha256'],'trials':rows,
        'all_reference_prompts_fit':all(p['max_reference_prompt_bytes']<=32768 and p['max_prompt_bytes_with_ascii_memory_allowance']<=32768 for r in rows for p in r['phases'].values()),
        'all_reference_emissions_fit':all(p['max_reference_response_tokens']<=(8192 if phase=='answer' else 4096) for r in rows for phase,p in r['phases'].items()),
        'measurement_kind':'cpu-oracle-wiring-budget-check',
        'scope':'Reference JSON response token counts only; no model timing/accuracy prediction, no proof arbitrary model wording or reasoning fits. ASCII-memory check is not a bound on all escaped strings.'}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=='__main__':main()
