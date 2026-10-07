#!/usr/bin/env python3
"""Portable read-only native audit of the fixed eight-cell historical-state study.

Never runs models, generators, tokenizer subprocesses or GPU operations. Native
reconstruction below is copied from frozen audit_semantic_v1.audit_trial with
explicit historical trace identity and terminal snapshot-write-gap handling.
Snapshot integrity and reference quality remain separate findings.
"""
import argparse
import ast
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3

from audit_semantic_v1 import (answer_score, canonical, digest, local_path, read,
    require, semantic_events, sha, state_metrics, usage_totals)
from audit_sparse_v1 import finite_nonnegative, phase_costs
from audit_history_snapshots import audit as audit_snapshots

HERE = Path(__file__).parent
ENGINE = HERE / 'history_v1'
PROTOCOL = 'historical-state-study-v1'
NATIVE_PROTOCOL = 'historical-state-development-v1'
POLICY = {'context_limit_utf8_bytes':32768,'memory_limit_utf8_bytes':6553,
          'max_ingestion_attempts':3,'max_retrieval':24,'max_answer_calls':32,
          'ingestion_generation':{'enable_thinking':False,'max_tokens':4096},
          'answer_generation':{'enable_thinking':True,'reasoning_effort':'medium','max_tokens':8192}}
CONDITIONS = {'AS':('archive','source-only'),'QH':('quoted','history'),
              'QS':('quoted','source-only'),'AH':('archive','history')}
ORDER = tuple((case,condition) for case,conditions in (
    ('t01-clinic',('AS','QH','QS','AH')),('t02-theatre',('AH','QS','QH','AS')))
    for condition in conditions)
CONTINUATION_RULE={'next_documents':['t03-depot','t04-meals'],
    'requires_complete_auditable_evidence':True,'requires_all_history_trials_exact':True,
    'requires_no_same_arm_current_or_temporal_accuracy_regression':True,
    'improvement_alternatives':['at_least_one_same_arm_temporal_answer_gain',
        'one_arm_exact_in_both_modes_and_history_total_elapsed_at_most_0.9_times_source_only_on_both_documents_with_known_zero_cache'],
    'history_to_source_elapsed_max_ratio':0.9,'automatic_extension':False,
    'scope':'Development continuation only; separately frozen extension, no speed or holdout promotion.'}
SOURCE_SHA256 = {
 'documents.json':'45ae96b4c80dca9a14defddf1bf33ae895e47fed9848101dbdc9ae2cb2be666f',
 'adjudicated.json':'e8bee704ebcdf69635205eefe949884bbb096d724fbb01646e046c836b461b1f',
 'annotations-independent.json':'80411f06139cd5e7f0f39251b6d4f01e1afae31b079a2483aa866457913b93ba',
 'annotations-review.json':'c43123857d93419cc346e509520ba2910265f3173ff67297dd5a1ce493067833',
 'reference-check.json':'08f1c546266ad65095014067eea532ebf3d5bb3168bc8045f7a1ba2a8624c890',
 'verify_references.py':'97d81c5be3e95abd17961f90c46dc703134b44c1e033c252ecf7764bc393d69f',
 'decision.md':'b114ee619aba510d744d30b27d738017f6b0d22d4bb9baaf493a5a70d1647ea2',
 'study-plan.md':'e581c58a0096bdb7aeb9cb674a24e0b092c322272fa0414b52cfce9ee2af03d7'}

def same(actual, expected, message):
    require(canonical(actual)==canonical(expected), message)


def load_packet(packet):
    """Portable verification: pinned source/annotation bytes, independent compilation.

    Tokenizer fit receipts are checked as recorded CPU evidence; live preparation
    separately reruns the tokenizer. No originating-host paths are required here.
    """
    packet=Path(packet).resolve();plan=read(packet/'plan.json')
    require(plan.get('schema')=='history-study-plan.v1' and plan.get('protocol')==PROTOCOL,'wrong history study packet')
    same({k:plan.get(k) for k in POLICY},POLICY,'fixed native policy differs')
    same(plan.get('expected_trials'),8,'fixed trial count differs')
    require(plan.get('speed_gate_passed') is False and plan.get('holdout_admitted') is False,'packet promotion claim')
    require(plan.get('extension_admitted') is False,'packet extension claim')
    same(plan.get('continuation_rule'),CONTINUATION_RULE,'continuation rule differs from prospective decision')
    original_paths={'decision.md':'notes/2026-10-07-context-next-study-decision.md',
                    'study-plan.md':'notes/2026-10-07-history-state-study-plan.md'}
    pins={'schema':'history-study-input-pins.v1','files':[
        {'copy_path':'source/'+name,'path':original_paths.get(name,'data/2026-10-07-temporal-development/'+name),
         'sha256':hashed} for name,hashed in SOURCE_SHA256.items()]}
    same(plan.get('input_pins'),pins,'reference input provenance differs')
    same(plan.get('engine_source_sha256'),ENGINE_SHA256,'frozen history engine identity differs')
    wrapper=plan.get('wrapper_source_sha256')
    require(isinstance(wrapper,dict) and set(wrapper)=={'budget.py','engine.py','materials.py','native_audit.py',
            'snapshot_audit.py','runner.py','pinned-engine.json','input-pins.json','copied-auditors.json'}
            and all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in wrapper.values()),'invalid wrapper inventory')
    for name,expected in SOURCE_SHA256.items():
        require(sha(local_path(packet,'source/'+name))==expected,'frozen reference input differs: '+name)
    require(sha(ENGINE/'tasks.py')==ENGINE_SHA256['tasks.py'],'frozen compiler drift')
    spec=importlib.util.spec_from_file_location('_history_study_audit_compiler',ENGINE/'tasks.py')
    compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)
    compiled={t['document_id']:t for t in compiler.load_packet(packet/'source/documents.json',packet/'source/adjudicated.json')}
    docs={d['id']:d for d in read(packet/'source/documents.json')['documents']}
    same(sorted(compiled),['t01-clinic','t02-theatre','t03-depot','t04-meals'],'authored source coverage differs')
    tasks={case:compiled[case] for case in ('t01-clinic','t02-theatre')}
    expected_rows=[]
    for case,condition in ORDER:
        arm,mode=CONDITIONS[condition];task=tasks[case];folder=case+'-'+condition
        expected_rows.append({'case_id':case,'condition':condition,'arm':arm,'retrieval_mode':mode,
            'counter_count':8,'initialization_batches':1,'task_sha256':task['task_sha256'],
            'question_sha256':digest(task['questions']),'task_path':case+'-task.json',
            'document_path':case+'-document.json','result_path':folder+'/result.json',
            'native_result_path':folder+'/native/result.json'})
    same(plan['trials'],expected_rows,'fixed condition order, questions or paths differ')
    for case,task in tasks.items():
        same(read(packet/(case+'-task.json')),task,'compiled task differs from frozen references')
        same(read(packet/(case+'-document.json')),docs[case],'compiled document differs from source')
    inventory={'source/'+name for name in SOURCE_SHA256}|{'budget-receipt.json'}|{
        case+suffix for case in tasks for suffix in ('-task.json','-document.json')}
    require(set(plan['files_sha256'])==inventory,'packet artifact inventory differs')
    for name,expected in plan['files_sha256'].items():
        require(sha(local_path(packet,name))==expected,'packet artifact hash differs: '+name)
    budget=read(packet/'budget-receipt.json')
    require(budget.get('schema')=='history-study-budget.v1' and budget.get('measurement_kind')=='cpu-oracle-wiring-budget-check',
            'wrong budget receipt kind')
    same(budget['engine_source_sha256'],ENGINE_SHA256,'budget engine identity differs')
    same(budget['wrapper_source_sha256'],wrapper,'budget wrapper identity differs')
    require(isinstance(budget['tokenizer_sha256'],str) and re.fullmatch('[0-9a-f]{64}',budget['tokenizer_sha256']),
            'invalid tokenizer identity')
    require(budget['all_reference_prompts_fit'] is True and budget['all_reference_emissions_fit'] is True,'reference budget did not fit')
    require(len(budget['trials'])==8,'budget matrix incomplete')
    for row,item in zip(budget['trials'],expected_rows):
        keys=('case_id','condition','arm','retrieval_mode','task_sha256')
        same({k:row[k] for k in keys},{k:item[k] for k in keys},'budget row identity differs')
        require(set(row['phases'])=={'initialization','steady','answer'},'budget phase coverage differs')
        for phase,values in row['phases'].items():
            require(all(type(v) is int and v>=0 for v in values.values()),'invalid budget value type')
            expected_calls=1 if phase=='initialization' else 11 if phase=='steady' else 22 if item['retrieval_mode']=='history' else 13
            require(values['calls']==expected_calls and values['max_reference_prompt_bytes']<=32768
                    and values['max_prompt_bytes_with_ascii_memory_allowance']<=32768
                    and values['max_reference_response_tokens']<=(8192 if phase=='answer' else 4096),'budget phase differs or exceeds caps')
    return plan,tasks

ENGINE_SHA256 = {'answers.py': 'bc77826918033f59c29add697a3ae8be2491eb4ed59694040d432ebfb382f0fe', 'diagnostics.py': '6bab40287c483b9cfc41d8c042e88c27989144cb5e36de834747a4eb8b8181d6', 'ledger.py': 'abff2a06690e1f52b4e37479696ba16acb890d630940385ff0d86e13d92c4ef1', 'live.py': 'cf2530192e084eb51101ec69a4f918f787dacea0e5b96fd96be459e390a3215a', 'snapshots.py': '73eeb45e3af863bc8a47b5c4e56f930f57db5955cbb2dcb05b12aa7acf6f0aeb', 'tasks.py': 'e15dd0f9e64521b6b143bc872ea17e1f08b27ef5530932b929f9e46d4ec6433f'}

def audit_native(directory, result, task, item, plan, *, snapshot_write_gaps=()):
    gaps = {row["batch_id"] for row in snapshot_write_gaps}
    require(not gaps or (result["failure_kind"] == "infrastructure" and result["status"] == "failed"
                        and gaps == {result["batches"][-1]["batch_id"]}), "invalid snapshot failure gap")
    require(result['document_id'] == item['document_id'] and result['arm'] == item['arm'], 'trial identity differs from plan')
    require(result['task_sha256'] == item['task_sha256'] == task['task_sha256'], 'task hash mismatch')
    require(result['source_sha256'] == task['source_sha256'] and
            result['adjudication_sha256'] == task.get('adjudication_sha256'), 'source/adjudication mismatch')
    for key in ('measurement_kind', 'protocol', 'source_code_sha256', 'server_identity', 'answer_generation',
                'ingestion_generation', 'context_limit_utf8_bytes', 'memory_limit_utf8_bytes',
                'max_ingestion_attempts', 'max_retrieval', 'max_answer_calls'):
        require(result[key] == plan[key], 'trial/plan mismatch: ' + key)
    identity = read(directory / 'identity.json')
    require(all(key in result and result[key] == value for key, value in identity.items()), 'identity artifact mismatch')
    require(set(identity) >= {'document_id', 'arm', 'task_sha256', 'measurement_kind', 'source_code_sha256'}, 'identity incomplete')
    required = {'calls.jsonl', 'trace.json', 'checkpoint.json', 'answer-session.json'}
    artifacts = result.get('artifacts')
    require(isinstance(artifacts, dict) and set(artifacts) >= required, 'native artifact bindings missing')
    for name in ('refusals.jsonl', 'retrieval.jsonl'):
        require((directory / name).exists() == (name in artifacts), 'optional artifact binding mismatch: ' + name)
    for name, binding in artifacts.items():
        require(binding['path'] == name, 'artifact identity mismatch')
        path = local_path(directory, binding['path'])
        require(path.is_file() and sha(path) == binding['sha256'], 'artifact hash mismatch: ' + name)
    calls = [json.loads(line) for line in (directory / 'calls.jsonl').read_text().splitlines()]
    require(result['calls'] == len(calls), 'call count mismatch')
    for call in calls:
        metadata = call.get('model_response')
        if not isinstance(metadata, dict):
            continue
        if 'generation' in metadata:
            policy = plan['answer_generation'] if call['phase'] == 'answer' else plan['ingestion_generation']
            require(metadata['generation'] == policy, 'recorded generation differs from frozen policy')
        message = metadata.get('response_message')
        if isinstance(message, dict) and 'response' in call:
            content = message.get('content')
            require(call['response'] == ('' if content is None else content), 'call response differs from retained message')
        if isinstance(metadata.get('raw_response_text'), str) and not metadata.get('raw_response_truncated'):
            try:
                envelope = json.loads(metadata['raw_response_text'])
            except ValueError:
                require('error' in call, 'successful call has malformed retained envelope')
            else:
                if isinstance(message, dict):
                    require(envelope['choices'][0]['message'] == message and
                            envelope['choices'][0]['finish_reason'] == metadata['finish_reason'] and
                            envelope.get('usage', {}) == metadata.get('usage'), 'HTTP envelope/metadata mismatch')
    refusal_path = directory / 'refusals.jsonl'
    recorded_refusals = [json.loads(line) for line in refusal_path.read_text().splitlines()] if refusal_path.exists() else []
    require(recorded_refusals == result['refusals'], 'refusal log mismatch')
    usage = usage_totals(calls)
    require(result['cache_usage'] == {'complete': bool(calls) and usage['cached_tokens'] is not None,
            'cached_tokens': usage['cached_tokens'], 'calls': len(calls)}, 'cache usage mismatch')
    require(result['cold_cache_known'] == usage['cold_cache_known'], 'cold-cache flag mismatch')
    trace = read(directory / 'trace.json')
    require(trace.get('schema') == 'history-live-attempt-trace.v1' and trace['batches'] == result['batches'], 'native trace mismatch')
    session = read(directory / 'answer-session.json')
    require(session == result['answer_protocol'] and session['answers'] == result['answers'], 'answer session mismatch')
    score = answer_score(task, result['answers'])
    require(result['score'] == score, 'answer score mismatch')
    final_complete = bool(session['completed'] and score['valid'] and score['answer_types_valid'] and score['exact_question_coverage'])
    require(result['final_answer_complete'] == final_complete, 'answer completion mismatch')
    rows = trace['batches']
    require([r['batch_id'] for r in rows] == list(range(1, len(rows)+1)) and len(rows) <= len(task['batches']), 'trace batch sequence mismatch')
    require(all(r['accepted'] for r in rows[:-1]), 'trace continues after an unaccepted batch')
    processed = sum(r['accepted'] is True for r in rows)
    require(processed == result['processed_batches'], 'processed batch count mismatch')
    ingestion_complete = processed == len(task['batches'])
    require(result['ingestion_complete'] == ingestion_complete and result['checkpoint_metrics_complete'] == ingestion_complete, 'ingestion completion mismatch')
    complete = ingestion_complete and final_complete and result['failure'] is None
    require(result['protocol_complete'] == complete and result['status'] == ('completed' if complete else 'failed'), 'trial completion/status mismatch')
    require((complete and result['failure_kind'] is None) or
            (not complete and isinstance(result['failure'], str) and result['failure_kind'] in ('model_or_protocol','infrastructure')),
            'failure classification mismatch')
    # Existing SQLite only: no opening CanonicalLedger and no schema migration.
    with sqlite3.connect((directory / 'canonical.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as conn:
        deliveries = list(conn.execute('SELECT batch_id,text,sha256 FROM deliveries ORDER BY batch_id'))
        events = list(conn.execute('SELECT batch_id,ordinal,payload FROM events ORDER BY batch_id,ordinal'))
        receipts = {r[0]: r[1:] for r in conn.execute('SELECT batch_id,delivery_sha256,events_sha256,events_applied,state_sha256 FROM receipts')}
        final_sql = {k: None if v is None else int(v) for k,v in conn.execute('SELECT counter,value FROM current_state')}
    require([n for n,_,_ in deliveries] == list(range(1, len(deliveries)+1)) and len(deliveries) <= len(task['batches']), 'delivery sequence mismatch')
    for n,text,hashed in deliveries:
        require(text == task['batches'][n-1]['text'] and hashlib.sha256(text.encode()).hexdigest() == hashed, 'delivered source mismatch')
    require(len(deliveries) == len(rows), 'delivery/trace coverage mismatch')
    delivery_complete = len(deliveries) == len(task['batches'])
    require(not complete or delivery_complete, 'completed trial lacks complete source delivery')
    by_batch = {}
    for n,ordinal,payload in events:
        by_batch.setdefault(n, []).append((ordinal, json.loads(payload)))
    if result['arm'] == 'quoted':
        require(set(receipts) == ({r['batch_id'] for r in rows if r['accepted']} | gaps), 'receipt/accepted batch mismatch')
        require(set(by_batch) <= set(receipts), 'events lack receipt')
    else:
        require(not events and not receipts and not final_sql, 'nonquoted arm unexpectedly mutated ledger')
    observed, checkpoint_observed, checkpoints, call_index, event_attempts = {}, {}, [], 0, []
    accepted_events = {'batches': 0, 'expected': 0, 'predicted': 0, 'matched': 0,
                       'missed_events': 0, 'extra_events': 0, 'malformed': 0}
    accepted_event_orders = []
    for row in rows:
        n = row['batch_id']; attempts = row['attempts']
        require(0 < len(attempts) <= plan['max_ingestion_attempts'], 'invalid ingestion attempt count')
        require([a['attempt'] for a in attempts] == list(range(1,len(attempts)+1)), 'attempt sequence mismatch')
        require(not any(a.get('accepted') for a in attempts[:-1]) and bool(attempts[-1].get('accepted')) == row['accepted'], 'attempt acceptance mismatch')
        for attempt in attempts:
            call = calls[call_index] if call_index < len(calls) else None
            if call is not None and call['phase'] == result['arm'] and call['batch_id'] == n:
                call_index += 1
                try:
                    parsed = json.loads(call['response'])
                except (KeyError, ValueError, TypeError):
                    parsed = None
                if 'response' in attempt:
                    require(isinstance(parsed, dict) and parsed == attempt['response'], 'attempt differs from recorded model response')
                else:
                    require(not isinstance(parsed, dict), 'parsed response missing from attempt')
            else:
                require(attempt is attempts[-1] and row is rows[-1] and not row['accepted'] and result['status'] == 'failed', 'ingestion attempt lacks recorded call')
            if result['arm'] == 'quoted':
                response = attempt.get('response')
                if isinstance(response, dict):
                    metrics = semantic_events(response.get('events'), task['oracle']['events'][n-1])
                    require(isinstance(attempt.get('events'), dict) and
                            all(attempt['events'].get(k) == v for k,v in metrics.items()),
                            'native event metrics differ from independent tuple matching')
                    if attempt.get('accepted'):
                        accepted_events['batches'] += 1
                        for key in accepted_events:
                            if key != 'batches': accepted_events[key] += metrics[key]
                        accepted_event_orders.append(metrics['exact_order'])
                else:
                    # Transport failures and unparsed responses supply no event
                    # list to score. Keep the attempted batch visible as unknown.
                    metrics = {k:None for k in ('valid_format','predicted','matched','missed_events',
                                                'extra_events','malformed','exact_order')}
                    metrics['expected'] = len(task['oracle']['events'][n-1])
                    require('events' not in attempt, 'event metric exists without a parsed response')
                event_attempts.append({'batch_id':n, 'attempt':attempt['attempt'],
                                       'accepted':bool(attempt.get('accepted')),
                                       'response_parsed':isinstance(response,dict), **metrics})
        if row['accepted'] or n in gaps:
            reply = attempts[-1]['response']
            if result['arm'] == 'archive':
                observed = reply['state']
            elif result['arm'] == 'quoted':
                stored = by_batch.get(n, [])
                require([i for i,_ in stored] == list(range(len(stored))), 'event ordinal mismatch')
                normalized = [{**e, 'id': f'{n}:{i}', 'quote': ' '.join(e['quote'].split())}
                              for i,e in enumerate(reply['events'])]
                require([e for _,e in stored] == normalized, 'SQLite events differ from accepted response')
                for event in normalized:
                    name, op, amount = event['counter'], event['op'], event['amount']
                    require(op in ('set','add','sub') and type(amount) is int, 'invalid applied semantic operation')
                    require(event['quote'] in ' '.join(task['batches'][n-1]['text'].split()), 'applied quote absent from source')
                    require(op == 'set' or name in observed, 'uninitialized replay counter')
                    observed[name] = amount if op == 'set' else observed[name] + (amount if op == 'add' else -amount)
                receipt = receipts[n]
                require(receipt == (deliveries[n-1][2], digest(normalized), len(normalized), digest(observed)), 'SQLite receipt mismatch')
        if row['accepted']:
            checkpoint_observed = dict(observed)
        if result['arm'] != 'summary':
            metrics = state_metrics(observed, task['oracle']['after_batch'][n-1])
            require(row['observed_state'] == observed and row['state'] == metrics, 'checkpoint metrics differ from reconstructed state')
            checkpoints.append(metrics)
        else:
            require(row['state'] is None and row['observed_state'] is None, 'summary internal state must remain unknown')
    if result['arm'] == 'quoted':
        require(final_sql == observed, 'final SQLite state mismatch')
    answer_calls = calls[call_index:]
    require(all(c['phase'] == 'answer' and c['batch_id'] is None for c in answer_calls), 'unexpected call sequence')
    require(len(answer_calls) <= session['calls'] <= plan['max_answer_calls'] and session['calls'] - len(answer_calls) <= 1, 'answer call budget/count mismatch')
    require(not answer_calls or ingestion_complete, 'answer calls before completed ingestion')
    require(not complete or (session['calls'] == len(answer_calls) and answer_calls), 'completed trial lacks recorded answer call')
    # Valid partial answers merge before action validation in the frozen protocol.
    # Reconstruct that saved evidence independently of result/session summaries.
    saved = {}
    question_types = {q['id']: int if q['answer_type'] == 'int' else str for q in task['questions']}
    def valid_answer(key, value):
        return key in question_types and (value is None or
            (type(value) is question_types[key] and
             (not isinstance(value, str) or len(value.encode()) <= 256) and
             (type(value) is not int or len(str(value)) <= 64)))
    for call in answer_calls:
        try:
            reply = json.loads(call.get('response', ''))
        except (ValueError, TypeError):
            continue
        if isinstance(reply, dict) and isinstance(reply.get('answers'), dict):
            saved.update({key:value for key,value in reply['answers'].items() if valid_answer(key,value)})
    require(saved == result['answers'], 'saved answers differ from original response evidence')
    if complete:
        submitted = json.loads(answer_calls[-1]['response'])
        require(isinstance(submitted, dict) and submitted.get('action') == 'submit'
                and not (set(submitted) - {'action','answers'})
                and ('answers' not in submitted or (isinstance(submitted['answers'],dict)
                    and all(valid_answer(k,v) for k,v in submitted['answers'].items()))),
                'completed trial lacks valid explicit submission')
    checkpoint = read(directory / 'checkpoint.json')
    require(checkpoint['processed_batches'] == processed and checkpoint['state'] == checkpoint_observed, 'checkpoint artifact differs from reconstructed state')
    exact = all(r['exact'] for r in checkpoints) if ingestion_complete and result['arm'] != 'summary' else None
    final_exact = checkpoints[-1]['exact'] if ingestion_complete and result['arm'] != 'summary' else None
    require(result['all_checkpoint_states_exact'] == exact and result['final_state_exact'] == final_exact, 'aggregate checkpoint metric mismatch')
    return {'document_id': item['document_id'], 'arm': item['arm'], 'status': result['status'],
            'measurement_kind': result['measurement_kind'], 'correct': score['correct'], 'asked': score['asked'],
            'failure': result.get('failure'), 'calls': len(calls), **usage,
            'delivered_batches': len(deliveries), 'delivered_text_exact': True, 'source_delivery_complete': delivery_complete,
            'checkpoints_checked': len(checkpoints), 'checkpoints_exact': sum(r['exact'] for r in checkpoints),
            'event_attempts':event_attempts,
            'accepted_events':accepted_events if result['arm']=='quoted' else None,
            'all_accepted_events_exact':all(accepted_event_orders) if accepted_event_orders else None,
            'refusals': len(result['refusals']), 'result_sha256': sha(directory / 'result.json'),
            'calls_sha256': sha(directory / 'calls.jsonl')}


def action_counts(calls, session, retrievals, failure=None):
    requested = {name:0 for name in ('search','fetch','state_at','update','submit','invalid')}
    distinct = {name:0 for name in ('search','fetch','state_at')}
    successful = dict(distinct); errors=0
    answer_calls=[c for c in calls if c['phase']=='answer']
    for call in answer_calls:
        try: reply=json.loads(call.get('response',''))
        except (TypeError,ValueError): reply=None
        action=reply.get('action') if isinstance(reply,dict) else None
        if isinstance(reply,dict) and action is None:
            action=('search' if any(k in reply for k in ('query','search')) else
                    'fetch' if any(k in reply for k in ('batch_id','batch')) else
                    'update' if 'answers' in reply else None)
        requested[action if isinstance(action,str) and action in requested else 'invalid']+=1
    for key in session['cache']:
        action=key.split(':',1)[0]
        require(action in distinct,'unknown cached action')
        distinct[action]+=1
    for response in retrievals:
        if 'error' in response: errors+=1;continue
        action=('state_at' if response.get('action')=='state_at' else 'search' if 'search' in response
                else 'fetch' if 'batch_id' in response and 'text' in response else None)
        require(action in successful,'unknown retrieval response')
        successful[action]+=1
    require(all(successful[k]>=distinct[k] for k in distinct),'cache lacks corresponding retrieval response')
    same(session['retrievals'],sum(distinct.values()),'distinct retrieval accounting differs')
    require(sum(distinct.values())<=24 and type(session['calls']) is int and session['calls']<=32,
            'answer/retrieval budget exceeded')
    return {'requested_actions':requested,'successful_distinct_retrievals':distinct,
            'successful_retrieval_responses':successful,
            'repeated_retrieval_responses':{k:successful[k]-distinct[k] for k in distinct},
            'retrieval_error_responses':errors,'answer_calls_logged':len(answer_calls),
            'answer_call_slots_used':session['calls'],'answer_call_exhausted':failure=='answer protocol budget exhausted'}


def validate_prompts(calls,task,mode):
    """Check public input boundaries and the frozen mode instruction directly."""
    constants={}
    for filename in ('answers.py','live.py'):
        require(sha(ENGINE/filename)==ENGINE_SHA256[filename],'history engine source drift')
        for node in ast.parse((ENGINE/filename).read_text()).body:
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Name) and target.id in ('INSTRUCTION','SOURCE_ONLY_INSTRUCTION','SYSTEM'):
                        constants[target.id]=ast.literal_eval(node.value)
    for call in calls:
        messages=call['messages']
        require(len(messages)==2 and messages[0]=={'role':'system','content':constants['SYSTEM']}
                and set(messages[1])=={'role','content'} and messages[1]['role']=='user','model message envelope differs')
        require(type(call['prompt_bytes']) is int and call['prompt_bytes']==len(canonical(messages))
                and call['prompt_bytes']<=32768,'prompt size differs from fixed budget')
        payload=json.loads(messages[1]['content'])
        same(payload['reading_conventions'],task['reading_conventions'],'reading conventions changed')
        if call['phase']=='answer':
            require(set(payload)=={'instruction','reading_conventions','questions','saved_answers',
                    'remaining_retrievals','remaining_answer_calls_including_this','previous_feedback',
                    'state','memory','retrieved'},'unexpected answer input fields')
            same(payload['questions'],task['questions'],'answer question set differs')
            same(payload['instruction'],constants['INSTRUCTION' if mode=='history' else 'SOURCE_ONLY_INSTRUCTION'],
                 'answer mode instruction differs')
        else:
            require(set(payload)=={'instruction','reading_conventions','batch_id','text','memory','previous_error','state'},
                    'unexpected ingestion fields, including possible question/oracle exposure')
            n=call['batch_id'];same(payload['text'],task['batches'][n-1]['text'],'ingestion source differs')
        metadata=call.get('model_response')
        if isinstance(metadata,dict) and 'generation' in metadata:
            same(metadata['generation'],POLICY['answer_generation' if call['phase']=='answer' else 'ingestion_generation'],
                 'raw generation policy differs')


def continuation(rows,kind,infrastructure_abort=False):
    """Frozen prospective signal only; never admits or launches the extension."""
    expected=set(ORDER)
    require(len({(r['case_id'],r['condition']) for r in rows})==len(rows),'duplicate continuation cells')
    cells={(r['case_id'],r['condition']):r for r in rows}
    evidence=(set(cells)==expected and not infrastructure_abort and
              all(r.get('status') in ('completed','failed') and r.get('integrity_passed') is True for r in rows))
    history_exact=evidence and all(cells[case,c]['quality_passed'] is True
                                  for case in ('t01-clinic','t02-theatre') for c in ('AH','QH'))
    no_regression=evidence;gain=False;costs={'archive':False,'quoted':False}
    if evidence:
        for case in ('t01-clinic','t02-theatre'):
            for arm,prefix in (('archive','A'),('quoted','Q')):
                source=cells[case,prefix+'S']['answer_categories'];history=cells[case,prefix+'H']['answer_categories']
                s_current=source['current']['correct'];h_current=history['current']['correct']
                s_temporal=sum(source[k]['correct'] for k in ('history','join'))
                h_temporal=sum(history[k]['correct'] for k in ('history','join'))
                no_regression &= h_current>=s_current and h_temporal>=s_temporal
                gain |= h_temporal>s_temporal
        for arm,prefix in (('archive','A'),('quoted','Q')):
            eligible=True
            for case in ('t01-clinic','t02-theatre'):
                source,history=cells[case,prefix+'S'],cells[case,prefix+'H']
                eligible &= (all(row.get('quality_passed') is True and row.get('cold_cost_interpretation') is True
                                 for row in (source,history)) and
                             finite_nonnegative(source.get('total_trial_wall_seconds')) and
                             finite_nonnegative(history.get('total_trial_wall_seconds')) and
                             source['total_trial_wall_seconds']>0 and
                             history['total_trial_wall_seconds']<=.9*source['total_trial_wall_seconds'])
            costs[arm]=bool(eligible)
    signal=kind=='model' and evidence and history_exact and no_regression and (gain or any(costs.values()))
    return {'evidence_complete':bool(evidence),'history_all_exact':bool(history_exact),
            'no_accuracy_regression':bool(no_regression),'temporal_answer_gain':bool(gain),
            'cost_signal_by_arm':costs,'continuation_signal':bool(signal),
            'extension_admitted':False,'speed_gate_passed':False,'holdout_admitted':False}


def audit_result(directory,task,item,plan,kind,identity):
    directory=Path(directory).resolve();native=read(directory/'result.json')
    require(native.get('schema')=='history-live-trial.v1' and native.get('protocol')==NATIVE_PROTOCOL
            and native.get('resumed') is False and native.get('retrieval_mode')==item['retrieval_mode']
            and native.get('case_id')==item['case_id'] and native.get('document_id')==item['case_id'],
            'native history mode, schema or identity differs')
    same({k:native.get(k) for k in POLICY},POLICY,'native fixed policy differs')
    calls=[json.loads(line) for line in (directory/'calls.jsonl').read_text().splitlines()]
    validate_prompts(calls,task,item['retrieval_mode'])
    snapshots=audit_snapshots(directory,task)
    inner={**POLICY,'protocol':NATIVE_PROTOCOL,'measurement_kind':kind,
           'source_code_sha256':plan['engine_source_sha256'],'server_identity':identity}
    # Core identity is unconditional, including infrastructure-failed evidence.
    same({k:native.get(k) for k in inner},inner,'native runtime/measurement identity differs')
    for key in ('task_sha256','source_sha256','adjudication_sha256'):
        same(native.get(key),task.get(key),'native source/reference identity differs: '+key)
    audited=None;errors=[]
    if not snapshots['integrity_passed']:
        errors.append('snapshot integrity: '+str(snapshots['issues']))
    try:
        audited=audit_native(directory,native,task,
            {'document_id':item['case_id'],'arm':item['arm'],'task_sha256':item['task_sha256']},inner,
            snapshot_write_gaps=snapshots['snapshot_write_gaps'])
    except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as error:
        errors.append('native audit: '+str(error))
    require(not errors or native.get('failure_kind')=='infrastructure','native evidence integrity failed: '+str(errors))
    reference=bool(not errors and audited and audited['status']=='completed' and
        audited['correct']==audited['asked']==24 and audited['source_delivery_complete'] and
        audited['checkpoints_checked']==audited['checkpoints_exact']==12 and snapshots['complete_snapshot_evidence'] and
        (item['arm']=='archive' or audited['all_accepted_events_exact'] is True and audited['accepted_events']['batches']==12))
    score=answer_score(task,native['answers']);same(native['score'],score,'native score differs')
    costs=phase_costs(calls,1)
    retrieval_path=directory/'retrieval.jsonl'
    retrievals=[json.loads(line) for line in retrieval_path.read_text().splitlines()] if retrieval_path.exists() else []
    actions=action_counts(calls,native['answer_protocol'],retrievals,native.get('failure'))
    if item['retrieval_mode']=='source-only':
        require(actions['successful_retrieval_responses']['state_at']==0,'source-only mode returned forbidden state_at')
    wall=native['wall_seconds'];require(finite_nonnegative(wall),'invalid native elapsed time')
    overhead=wall-costs['total']['client_call_seconds'];require(overhead>=-1e-6,'elapsed time below summed call cost')
    return {'status':native['status'],'failure_kind':native['failure_kind'],'integrity_passed':not errors,
            'reference_checks_passed':reference,'quality_passed':kind=='model' and reference,
            'cold_cost_interpretation':kind=='model' and costs['total']['cache_complete'] and costs['total']['cached_tokens']==0,
            'answer_categories':score['by_category'],'score':score,'phase_costs':costs,'action_counts':actions,
            'total_trial_wall_seconds':wall,'non_call_overhead_seconds':overhead,
            'native_audit':audited,'snapshot_audit':snapshots,'audit_errors':errors,
            'native_sha256':sha(directory/'result.json'),'calls_sha256':sha(directory/'calls.jsonl')}


def audit(output,packet):
    output,packet=Path(output).resolve(),Path(packet).resolve();plan,tasks=load_packet(packet)
    root=output/'diagnostic' if (output/'diagnostic').is_dir() else output
    same(read(root/'plan.json'),plan,'output plan differs from frozen packet')
    summary=read(root/'summary.json');kind=summary['measurement_kind'];identity=summary['server_identity']
    require(summary.get('schema')=='history-study-summary.v1' and summary.get('protocol')==PROTOCOL,
            'summary identity differs')
    require(kind in ('model','stub'),'invalid measurement kind')
    if kind=='stub':require(identity is None,'stub claims model identity')
    else:
        require(isinstance(identity,dict) and set(identity)=={'endpoint','model','launch_sha256'}
                and all(isinstance(v,str) and v for v in identity.values())
                and re.fullmatch('[0-9a-f]{64}',identity['launch_sha256']),'model lacks bound server identity')
    same(summary['expected_trials'],8,'summary trial count differs')
    same(summary['engine_source_sha256'],ENGINE_SHA256,'summary engine differs')
    same(summary['continuation_rule'],CONTINUATION_RULE,'summary continuation rule differs')
    require(summary.get('continuation_evaluated') is False and summary.get('extension_admitted') is False
            and summary.get('speed_gate_passed') is False and summary.get('holdout_admitted') is False,
            'wrapper claims extension or promotion')
    require(type(summary['infrastructure_abort']) is bool,'invalid infrastructure flag')
    require(isinstance(summary['trials'],list) and len(summary['trials'])==8,'summary omits planned conditions')
    rows=[];observed=[];missing=False;terminal_infrastructure=False
    expected_paths={local_path(root,item[key]) for item in plan['trials'] for key in ('result_path','native_result_path')}
    actual_paths={p.resolve() for pattern in ('*/result.json','*/native/result.json') for p in root.glob(pattern)}
    require(actual_paths<=expected_paths,'unplanned trial result exists')
    for item,claimed in zip(plan['trials'],summary['trials']):
        same({k:claimed.get(k) for k in item},item,'summary condition/order differs')
        outer_path=local_path(root,item['result_path']);native_path=local_path(root,item['native_result_path'])
        base={**item,'quality_passed':False,'reference_checks_passed':None,'integrity_passed':False,
              'cold_cost_interpretation':False}
        if not outer_path.exists():
            missing=True;status='incomplete' if outer_path.parent.exists() else 'unstarted'
            require(claimed.get('status')==status,'summary missing-trial status differs')
            row={**base,'status':status,'reason':claimed.get('unstarted_reason')}
            if native_path.exists():
                partial=audit_result(native_path.parent,tasks[item['case_id']],item,plan,kind,identity)
                row.update(partial,native_status=partial['status'],status='incomplete',quality_passed=False)
            rows.append(row);continue
        require(not missing and not terminal_infrastructure,'later trial ran after missing/infrastructure-failed earlier trial')
        outer=read(outer_path);task=tasks[item['case_id']]
        require(outer.get('schema')=='history-study-trial.v1' and outer.get('protocol')==PROTOCOL,'outer trial schema differs')
        same({k:outer.get(k) for k in item},item,'outer condition/task identity differs')
        require(native_path.is_file() and sha(native_path)==outer.get('native_sha256'),'native result hash binding differs')
        native=read(native_path)
        for key,expected in (('measurement_kind',kind),('server_identity',identity),('engine_source_sha256',ENGINE_SHA256),
                ('wrapper_source_sha256',plan['wrapper_source_sha256']),('source_sha256',task['source_sha256']),
                ('adjudication_sha256',task['adjudication_sha256']),('annotation_sources',task['annotation_sources']),
                ('native_artifacts',native['artifacts'])):
            same(outer.get(key),expected,'outer provenance differs: '+key)
        require(outer.get('extension_admitted') is False and outer.get('speed_gate_passed') is False
                and outer.get('holdout_admitted') is False,'outer promotion claim')
        row={**item,**audit_result(native_path.parent,task,item,plan,kind,identity),'outer_sha256':sha(outer_path)}
        require(outer.get('audit_error') is None or
                (summary['infrastructure_abort'] is True and isinstance(outer['audit_error'],str)),
                'unretained outer audit failure')
        for key in ('status','score','phase_costs','action_counts','total_trial_wall_seconds','non_call_overhead_seconds',
                    'reference_checks_passed','quality_passed','cold_cost_interpretation'):
            same(outer.get(key),row[key],'outer reconstructed metric differs: '+key)
        if outer.get('audit_error') is None:
            require(set(outer['native_auxiliary'])=={'canonical.sqlite','identity.json'},'native auxiliary inventory differs')
            for name,record in outer['native_auxiliary'].items():
                require(record['path']==name and sha(local_path(native_path.parent,name))==record['sha256'],
                        'native auxiliary hash differs')
            same(outer['native_audit'],row['native_audit'],'outer native audit differs')
            same({k:v for k,v in outer['snapshot_audit'].items() if k!='directory'},
                 {k:v for k,v in row['snapshot_audit'].items() if k!='directory'},'outer snapshot audit differs')
        else:
            row['client_audit_error']=outer['audit_error'];row['integrity_passed']=False
        same(claimed.get('status'),row['status'],'summary native status differs')
        same(claimed.get('quality_passed'),row['quality_passed'],'summary quality differs')
        terminal_infrastructure=native.get('failure_kind')=='infrastructure' or outer.get('audit_error') is not None
        require(not terminal_infrastructure or summary['infrastructure_abort'],'infrastructure failure missing from summary')
        observed.append(row);rows.append(row)
    for key,expected in (('observed_trials',len(observed)),('completed_trials',sum(r['status']=='completed' for r in observed)),
                         ('failed_trials',sum(r['status']=='failed' for r in observed))):
        same(summary.get(key),expected,'summary count differs: '+key)
    same(summary.get('unstarted_trials'),[r for r in summary['trials'] if r['status']=='unstarted'],'unstarted manifest differs')
    status='failed' if summary['infrastructure_abort'] else 'completed' if len(observed)==8 else 'running'
    same(summary.get('status'),status,'summary lifecycle differs')
    return {'schema':'history-study-native-audit.v1','output':str(output),'measurement_kind':kind,
            'packet_plan_sha256':sha(packet/'plan.json'),'planned_trials':8,
            **{status+'_trials':sum(r['status']==status for r in rows) for status in ('completed','failed','incomplete','unstarted')},
            'infrastructure_abort':summary['infrastructure_abort'],'trials':rows,
            'continuation':continuation(rows,kind,summary['infrastructure_abort']),
            'extension_admitted':False,'speed_gate_passed':False,'holdout_admitted':False,
            'scope':'Fixed authored temporal development comparison. Actual-state integrity and reference quality audited separately; no automatic extension or general performance claim.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--packet',type=Path,default=HERE.parents[1]/'data/2026-10-07-history-study')
    args=parser.parse_args();print(json.dumps(audit(args.out,args.packet),ensure_ascii=False,indent=2))
