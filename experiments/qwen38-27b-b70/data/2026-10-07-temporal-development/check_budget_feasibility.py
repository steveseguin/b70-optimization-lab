#!/usr/bin/env python3
"""CPU-only reference and retrieval-budget checks; never instantiate HTTPClient.

Run with an interpreter providing the local `tokenizers` package. Each engine
runs in its own interpreter so the frozen modules' bare imports cannot collide.
References are explicit oracle fixtures, not model responses or quality evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE_SHA256 = '45ae96b4c80dca9a14defddf1bf33ae895e47fed9848101dbdc9ae2cb2be666f'
DEFAULT_TOKENIZER = Path('/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_pins(engine):
    return {p.name:sha(p) for p in sorted(engine.glob('*.py')) if not p.name.startswith('test_')}


def worker(args):
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    from tokenizers import Tokenizer, __version__ as tokenizer_version
    engine = HERE.parents[1]/'scripts/context'/args.worker
    before = source_pins(engine)
    sys.path.insert(0, str(engine))
    import live
    from tasks import load_packet
    source = json.loads(args.source.read_bytes())
    adjudication_sha = sha(args.adjudicated)
    tasks = {task['document_id']:task for task in load_packet(args.source,args.adjudicated)}
    assert sha(args.source) == SOURCE_SHA256
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    tokenizer_sha = sha(args.tokenizer)
    modes = ('source-only',) if args.worker == 'semantic_v1' else ('source-only','history')
    rows = []
    for document in source['documents']:
        task = tasks[document['id']]
        # These times come from public questions, not private answer bases.
        closes = sorted({int(value) for question in document['questions'] if question['category']!='current'
                         for value in re.findall(r'end of batch ([0-9]+)',question['text'])})
        assert closes and all(1 <= close < len(document['batches']) for close in closes)
        for arm in ('archive','quoted'):
            for mode in modes:
                for memory_bytes in (0, live.MEMORY_LIMIT):
                    schedule = [{'action':'fetch','batch_id':batch['id']} for batch in document['batches']]
                    if mode == 'history':
                        schedule += [{'action':'state_at','batch_id':close} for close in closes]
                    # A fixture-only client follows a predetermined public-evidence
                    # schedule and eventually emits the known reference answers.
                    class RetrievalFixture(live.StubClient):
                        kind = 'stub'
                        def __init__(self, task):
                            super().__init__(task)
                            self.answer_index = 0
                        def __call__(self, messages, phase, batch_id):
                            if phase != 'answer':
                                response = json.loads(super().__call__(messages,phase,batch_id)[0])
                                response['memory'] = 'x'*memory_bytes
                            else:
                                response = (schedule[self.answer_index] if self.answer_index < len(schedule)
                                            else {'action':'submit','answers':self.task['oracle']['answers']})
                                self.answer_index += 1
                            return json.dumps(response,ensure_ascii=False), {}
                    with tempfile.TemporaryDirectory(prefix='temporal-budget-fixture-') as temporary:
                        out = Path(temporary)/'native'
                        kwargs = {'retrieval_mode':mode} if args.worker == 'history_v1' else {}
                        result = live.run_trial(task,arm,out,RetrievalFixture(task),**kwargs)
                        calls = [json.loads(line) for line in (out/'calls.jsonl').read_text().splitlines()]
                        assert result['measurement_kind']=='stub' and result['protocol_complete']
                        assert result['answer_protocol']['retrievals']==len(schedule)
                        assert result['answer_protocol']['calls']==len(schedule)+1
                        assert len(schedule)<=live.MAX_RETRIEVAL and len(schedule)+1<=live.MAX_ANSWER_CALLS
                        phases={};evictions=[];answer_index=0
                        for call in calls:
                            phase = 'answer' if call['phase']=='answer' else 'ingestion'
                            payload = json.loads(call['messages'][1]['content'])
                            # The fixture has private keys; the engine's public
                            # payload must not transmit that task/reference object.
                            assert not ({'oracle','after_batch','answers','answer_basis','score',
                                         'annotation_sha256','checkpoint_metrics'} & set(payload))
                            expected_keys = ({'instruction','reading_conventions','questions','saved_answers',
                                              'remaining_retrievals','remaining_answer_calls_including_this',
                                              'previous_feedback','state','memory','retrieved'} if phase=='answer' else
                                             {'instruction','reading_conventions','batch_id','text','memory','previous_error','state'})
                            assert set(payload)==expected_keys
                            assert ('questions' in payload)==(phase=='answer')
                            if phase=='answer':assert payload['questions']==document['questions']
                            assert call['prompt_bytes']==len(live.encoded(call['messages']))<=live.LIMIT
                            tokens = len(tokenizer.encode(call['response'],add_special_tokens=False).ids)
                            cap = live.ANSWER_GENERATION['max_tokens'] if phase=='answer' else live.INGESTION_GENERATION['max_tokens']
                            assert tokens<=cap
                            record=phases.setdefault(phase,{'calls':0,'max_serialized_prompt_bytes':0,
                                'max_reference_response_bytes':0,'max_reference_response_tokens':0,
                                'max_serialized_messages_tokens_without_chat_template':0,
                                'max_retained_evidence_items':0})
                            record['calls']+=1
                            for key,value in {'max_serialized_prompt_bytes':call['prompt_bytes'],
                                'max_reference_response_bytes':len(call['response'].encode()),
                                'max_reference_response_tokens':tokens,
                                'max_serialized_messages_tokens_without_chat_template':len(tokenizer.encode(live.encoded(call['messages']).decode(),add_special_tokens=False).ids),
                                'max_retained_evidence_items':len(payload.get('retrieved',[]))}.items():
                                record[key]=max(record[key],value)
                            if phase=='answer':
                                expected=min(answer_index,len(schedule));retained=len(payload['retrieved'])
                                if retained<expected or payload['memory']!='x'*memory_bytes:
                                    evictions.append({'answer_call':answer_index+1,'successful_cached_items':expected,
                                                      'retained_items':retained,'memory_retained_bytes':len(payload['memory'].encode())})
                                answer_index+=1
                        rows.append({'document_id':document['id'],'engine':args.worker,'engine_protocol':live.PROTOCOL,
                            'arm':arm,'retrieval_mode':mode,'fixture_memory_bytes':memory_bytes,'task_sha256':task['task_sha256'],
                            'source_fetches':len(document['batches']),
                            'historical_state_batches':closes if mode=='history' else [],
                            'successful_distinct_retrievals':len(schedule),'answer_calls_including_submit':len(schedule)+1,
                            'remaining_retrievals':live.MAX_RETRIEVAL-len(schedule),
                            'remaining_answer_calls':live.MAX_ANSWER_CALLS-len(schedule)-1,
                            'phases':phases,'evidence_or_memory_eviction_calls':evictions,
                            'fixture_completed':True,'all_reference_emissions_fit':True,'all_actual_serialized_prompts_fit':True})
    assert source_pins(engine)==before and sha(args.source)==SOURCE_SHA256
    assert sha(args.tokenizer)==tokenizer_sha and sha(args.adjudicated)==adjudication_sha
    assert {task['document_id']:task['task_sha256'] for task in load_packet(args.source,args.adjudicated)}=={key:task['task_sha256'] for key,task in tasks.items()}
    return {'engine':args.worker,'engine_source_sha256':before,'tokenizer_sha256':tokenizer_sha,
            'checked_policy':{'context_limit_utf8_bytes':live.LIMIT,'memory_limit_utf8_bytes':live.MEMORY_LIMIT,
                              'max_successful_retrievals':live.MAX_RETRIEVAL,'max_answer_calls':live.MAX_ANSWER_CALLS,
                              'max_ingestion_attempts':live.MAX_INGESTION_ATTEMPTS,
                              'ingestion_generation':live.INGESTION_GENERATION,'answer_generation':live.ANSWER_GENERATION},
            'public_payload_allowlist_checks_passed':True,
            'tokenizers_version':tokenizer_version,'rows':rows}


def run_owned_worker(arguments):
    process=subprocess.Popen(arguments,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                             env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1'))
    try:
        output,error=process.communicate(timeout=180)
        if process.returncode:raise RuntimeError(error[-3000:])
        return json.loads(output)
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=HERE/'documents.json')
    parser.add_argument('--adjudicated',type=Path,default=HERE/'adjudicated.json')
    parser.add_argument('--tokenizer',type=Path,default=DEFAULT_TOKENIZER)
    parser.add_argument('--out',type=Path,default=HERE/'budget-feasibility.json')
    parser.add_argument('--worker',choices=('semantic_v1','history_v1'))
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args),ensure_ascii=False));return
    pins={'source_sha256':sha(args.source),'adjudication_sha256':sha(args.adjudicated),
          'script_sha256':sha(__file__),'tokenizer_sha256':sha(args.tokenizer)}
    assert pins['source_sha256']==SOURCE_SHA256
    results=[run_owned_worker([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',engine,
               '--source',str(args.source.resolve()),'--adjudicated',str(args.adjudicated.resolve()),
               '--tokenizer',str(args.tokenizer.resolve())]) for engine in ('semantic_v1','history_v1')]
    assert pins=={'source_sha256':sha(args.source),'adjudication_sha256':sha(args.adjudicated),
                  'script_sha256':sha(__file__),'tokenizer_sha256':sha(args.tokenizer)}
    receipt={'schema':'temporal-budget-feasibility.v1','measurement_kind':'cpu-oracle-fixture-budget-check',**pins,
        'adjudicated_file':args.adjudicated.name,
        'task_compilation':'Frozen tasks.load_packet validates the adjudicated source packet and annotation file hashes; no live manifest or execution admission is created','tokenizer_path':str(args.tokenizer.resolve()),
        'interpreter':sys.executable,'engines':results,'fixture_trials':sum(len(result['rows']) for result in results),
        'all_reference_emissions_fit':True,'all_actual_serialized_prompts_fit':True,
        'model_quality_measured':False,'live_study_admitted':False,'speed_gate_passed':False,'holdout_admitted':False,
        'limits':['Explicit oracle fixture outputs are used only for CPU wiring and response-size measurements; no HTTP/model call occurs.',
                  'Serialized prompt bytes are the engines actual enforced format. Token counts of serialized messages exclude the model chat template and are not native API usage.',
                  'Reference answer tokens exclude model reasoning; the unchanged 8192-token answer allowance combines reasoning and visible output.',
                  'The 6553-byte memory fixture is repeated ASCII x, not a bound on arbitrary escaped strings or model response tokenization.',
                  'The scripted schedule fetches all 12 sources and, in history mode, all 9 distinct earlier closes. A model must still resolve ownership at the requested time and use the retrieved evidence correctly.',
                  'Evidence eviction is reported explicitly. Feasibility of this schedule is not proof that a model will choose it or complete within the same budgets.']}
    args.out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'out':str(args.out),'fixture_trials':receipt['fixture_trials'],
        'max_prompt_bytes':max(row['phases'][phase]['max_serialized_prompt_bytes'] for result in results for row in result['rows'] for phase in row['phases']),
        'trials_with_eviction':sum(bool(row['evidence_or_memory_eviction_calls']) for result in results for row in result['rows'])},indent=2))


if __name__=='__main__':main()
