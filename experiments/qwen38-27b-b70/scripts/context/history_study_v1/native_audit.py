#!/usr/bin/env python3
"""Read-only audit of native semantic evidence; missing measurements stay unknown."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

ARMS = ('summary', 'archive', 'quoted')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def local_path(root, name):
    require(isinstance(name, str), 'artifact path must be text')
    path = (root / name).resolve()
    require(not Path(name).is_absolute() and path.is_relative_to(root.resolve()), 'artifact escapes output')
    return path


def count(value):
    return type(value) is int and value >= 0


def usage_totals(calls):
    values = {key: [] for key in ('cached_tokens', 'prompt_tokens', 'completion_tokens', 'reasoning_tokens')}
    for call in calls:
        usage = call.get('usage')
        usage = usage if isinstance(usage, dict) else {}
        prompt = usage.get('prompt_tokens')
        completion = usage.get('completion_tokens')
        details = usage.get('prompt_tokens_details')
        cached = details.get('cached_tokens') if isinstance(details, dict) else None
        details = usage.get('completion_tokens_details')
        reasoning = details.get('reasoning_tokens') if isinstance(details, dict) else None
        values['prompt_tokens'].append(prompt if count(prompt) else None)
        values['completion_tokens'].append(completion if count(completion) else None)
        values['cached_tokens'].append(cached if count(cached) and count(prompt) and cached <= prompt else None)
        values['reasoning_tokens'].append(reasoning if count(reasoning) and count(completion) and reasoning <= completion else None)
        metadata = call.get('model_response')
        if isinstance(metadata, dict) and 'usage' in metadata:
            require(call.get('usage') == metadata['usage'], 'call usage differs from retained response metadata')
    totals = {key: sum(items) if items and all(v is not None for v in items) else None
              for key, items in values.items()}
    totals['usage_known_calls'] = {key: sum(v is not None for v in items) for key, items in values.items()}
    totals['cold_cache_known'] = bool(calls) and totals['cached_tokens'] == 0
    return totals


def state_metrics(actual, expected):
    if not isinstance(actual, dict) or any(not isinstance(k, str) or type(v) is not int for k, v in actual.items()):
        return {'valid': False, 'exact': False, 'correct': 0, 'asked': len(expected)}
    keys = set(actual) | set(expected)
    return {'valid': True, 'exact': actual == expected,
            'correct': sum(k in actual and k in expected and actual[k] == expected[k] for k in keys),
            'asked': len(keys)}


def answer_score(task, answers):
    require(isinstance(answers, dict), 'answers must be an object')
    ids = {q['id'] for q in task['questions']}
    groups, types, invalid = {}, {}, []
    for q in task['questions']:
        actual = answers.get(q['id'])
        expected_type = int if q['answer_type'] == 'int' else str
        if q['id'] in answers and actual is not None and type(actual) is not expected_type:
            invalid.append(q['id'])
        correct = type(actual) is expected_type and actual == task['oracle']['answers'][q['id']]
        for table, key in ((groups, q['category']), (types, q['answer_type'])):
            row = table.setdefault(key, {'asked': 0, 'correct': 0})
            row['asked'] += 1
            row['correct'] += correct
    return {'asked': len(ids), 'correct': sum(r['correct'] for r in groups.values()),
            'valid': not (set(answers) - ids), 'answer_types_valid': not invalid,
            'exact_question_coverage': set(answers) == ids, 'invalid_type_ids': invalid,
            'missing_ids': sorted(ids - set(answers)), 'unknown_ids': sorted(set(answers) - ids),
            'by_category': groups, 'by_answer_type': types}


def semantic_events(actual, expected):
    """Count semantic tuples independently; quotes never decide tuple equality."""
    gold = [(e['counter'], e['op'], e['amount']) for e in expected]
    if not isinstance(actual, list):
        return {'valid_format': False, 'expected': len(gold), 'predicted': None, 'matched': 0,
                'missed_events': len(gold), 'extra_events': 1, 'malformed': 1, 'exact_order': False}
    tuples, malformed = [], 0
    for event in actual:
        if (not isinstance(event, dict) or not isinstance(event.get('counter'), str)
                or event.get('op') not in ('set', 'add', 'sub') or type(event.get('amount')) is not int
                or not isinstance(event.get('quote'), str)):
            malformed += 1
        else:
            tuples.append((event['counter'], event['op'], event['amount']))
    matched = sum((Counter(tuples) & Counter(gold)).values())
    return {'valid_format': malformed == 0, 'expected': len(gold), 'predicted': len(actual),
            'matched': matched, 'missed_events': len(gold)-matched,
            'extra_events': len(actual)-matched, 'malformed': malformed,
            'exact_order': malformed == 0 and tuples == gold}


def audit_trial(directory, result, task, item, plan):
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
        require(set(receipts) == {r['batch_id'] for r in rows if r['accepted']}, 'receipt/accepted batch mismatch')
        require(set(by_batch) <= set(receipts), 'events lack receipt')
    else:
        require(not events and not receipts and not final_sql, 'nonquoted arm unexpectedly mutated ledger')
    observed, checkpoints, call_index, event_attempts = {}, [], 0, []
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
        if row['accepted']:
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
    require(checkpoint['processed_batches'] == processed and checkpoint['state'] == observed, 'checkpoint artifact differs from reconstructed state')
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

