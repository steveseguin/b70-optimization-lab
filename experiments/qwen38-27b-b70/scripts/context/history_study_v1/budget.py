"""Local-tokenizer CPU wiring checks, executed in an interpreter with tokenizers."""
import hashlib
import json
import os
import re
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
    class BudgetClient(live.StubClient):
        """Explicit CPU-only gold wiring: fetch source, fetch history, submit."""
        def __init__(self,task,mode):
            super().__init__(task);self.index=0
            self.actions=[{'action':'fetch','batch_id':b['id']} for b in task['batches']]
            if mode=='history':
                times=sorted({int(n) for q in task['questions'] if q['category']!='current'
                              for n in re.findall(r'batch ([0-9]+)',q['text'])})
                self.actions += [{'action':'state_at','batch_id':n} for n in times]
        def __call__(self,messages,phase,batch_id):
            if phase=='answer' and self.index<len(self.actions):
                reply=self.actions[self.index];self.index+=1;return json.dumps(reply),{}
            return super().__call__(messages,phase,batch_id)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='history-study-tokenizer-fit-') as temp:
        for index,item in enumerate(request['trials']):
            task=json.loads(Path(item['task_path']).read_bytes());out=Path(temp)/str(index)
            live.run_trial(task,item['arm'],out,BudgetClient(task,item['retrieval_mode']),retrieval_mode=item['retrieval_mode'])
            calls=[json.loads(line) for line in (out/'calls.jsonl').read_text().splitlines()]
            initial=item['initialization_batches'];phases={}
            for call in calls:
                phase='answer' if call['phase']=='answer' else 'initialization' if call['batch_id']<=initial else 'steady'
                row=phases.setdefault(phase,{'calls':0,'max_reference_prompt_bytes':0,'max_reference_response_bytes':0,
                    'max_reference_response_tokens':0,'max_response_tokens_with_ascii_memory_allowance':0,'max_prompt_bytes_with_ascii_memory_allowance':0})
                row['calls']+=1
                row['max_reference_prompt_bytes']=max(row['max_reference_prompt_bytes'],call['prompt_bytes'])
                row['max_reference_response_bytes']=max(row['max_reference_response_bytes'],len(call['response'].encode()))
                tokens=len(tokenizer.encode(call['response'],add_special_tokens=False).ids)
                row['max_reference_response_tokens']=max(row['max_reference_response_tokens'],tokens)
                response=json.loads(call['response'])
                if phase!='answer':response['memory']='x'*live.MEMORY_LIMIT
                full_response_tokens=len(tokenizer.encode(json.dumps(response,ensure_ascii=False),add_special_tokens=False).ids)
                row['max_response_tokens_with_ascii_memory_allowance']=max(row['max_response_tokens_with_ascii_memory_allowance'],full_response_tokens)
                messages=call['messages'];payload=json.loads(messages[1]['content']);payload['memory']='x'*live.MEMORY_LIMIT
                messages[1]['content']=json.dumps(payload,ensure_ascii=False)
                row['max_prompt_bytes_with_ascii_memory_allowance']=max(row['max_prompt_bytes_with_ascii_memory_allowance'],len(live.encoded(messages)))
            rows.append({'case_id':item['case_id'],'condition':item['condition'],'arm':item['arm'],'retrieval_mode':item['retrieval_mode'],'task_sha256':task['task_sha256'],'phases':phases})
    result={'schema':'history-study-budget.v1','tokenizer_path':str(tokenizer_path.resolve()),
        'tokenizer_sha256':hashlib.sha256(tokenizer_path.read_bytes()).hexdigest(),'tokenizers_version':tokenizer_version,
        'engine_source_sha256':verify_engine()['source_sha256'],'trials':rows,
        'all_reference_prompts_fit':all(p['max_reference_prompt_bytes']<=32768 and p['max_prompt_bytes_with_ascii_memory_allowance']<=32768 for r in rows for p in r['phases'].values()),
        'all_reference_emissions_fit':all(max(p['max_reference_response_tokens'],p['max_response_tokens_with_ascii_memory_allowance'])<=(8192 if phase=='answer' else 4096) for r in rows for phase,p in r['phases'].items()),
        'measurement_kind':'cpu-oracle-wiring-budget-check',
        'fixture_policy':'Every source batch fetched once; history additionally fetches each distinct requested earlier batch; then gold submission. All calls are CPU stubs.',
        'scope':'Reference JSON response token counts only; no model timing/accuracy prediction, no proof arbitrary model wording or reasoning fits. Full 6553-byte ASCII memory is reserialized into every prompt and ingestion response and the latter is tokenized; this fixture is not a bound on all escaped strings or arbitrary memory text.'}
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=='__main__':main()
