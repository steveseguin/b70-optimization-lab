"""Durable answer/retrieval protocol. No oracle or grading access."""
import re
import json
from snapshots import selection

from ledger import LedgerError
from tasks import answer_type

INSTRUCTION = '''Answer the listed questions using your memory and original evidence.
Every reply is one JSON object with one action: "search", "fetch", "state_at", "update", or "submit".
You may include "answers":{"question-id":value} with ANY action; these are saved and can be revised.
Each question declares answer_type: use an integer for "int", a string for "str", or null for an unknown. The category does not determine the type.
Search: {"action":"search","query":"literal text"}. Fetch an exact original batch:
{"action":"fetch","batch_id":2}. Search uses digit boundaries (batch 2 excludes batch 20).
Historical state: {"action":"state_at","batch_id":2,"counters":["amber10"]}.
This returns your own actual accepted state at the END of that batch, not an oracle.
Omit counters for the full state, or select 1..256 unique names (each <=128 UTF-8 bytes;
the list <=4096 UTF-8 bytes). Missing counters are explicitly listed, never assumed zero.
Only one batch per call. Historical retrieval shares the same retrieval and answer-call budgets.
Source fetch/search remains available for ownership, corrections and other narrative details.
Use fetch for original text; use state_at for a saved historical balance. Repeated retrieval returns cached evidence and
still uses an answer call. Update saves answers without ending. To finish use
{"action":"submit","answers":{...}} after every question has a saved value (null allowed).
Partial answers never finish the task. Budget exhaustion does not submit automatically.
All arms have identical access to original batches. Do not invent facts.'''


# Exact frozen semantic answer instruction; captured rather than imported at runtime.
SOURCE_ONLY_INSTRUCTION = '''Answer the listed questions using your memory and original evidence.
Every reply is one JSON object with one action: "search", "fetch", "update", or "submit".
You may include "answers":{"question-id":value} with ANY action; these are saved and can be revised.
Each question declares answer_type: use an integer for "int", a string for "str", or null for an unknown. The category does not determine the type.
Search: {"action":"search","query":"literal text"}. Fetch an exact original batch:
{"action":"fetch","batch_id":2}. Search uses digit boundaries (batch 2 excludes batch 20).
Use fetch when a question names a batch. Repeated retrieval returns cached evidence and
still uses an answer call. Update saves answers without ending. To finish use
{"action":"submit","answers":{...}} after every question has a saved value (null allowed).
Partial answers never finish the task. Budget exhaustion does not submit automatically.
All arms have identical access to original batches. Do not invent facts.'''
RETRIEVAL_MODES = ('source-only', 'history')


def instruction_for(retrieval_mode):
    if retrieval_mode not in RETRIEVAL_MODES:
        raise ValueError('retrieval_mode must be source-only or history')
    return SOURCE_ONLY_INSTRUCTION if retrieval_mode == 'source-only' else INSTRUCTION


def new_session():
    return {'answers': {}, 'calls': 0, 'retrievals': 0, 'cache': {}, 'recent': [],
            'feedback': None, 'completed': False}


def search_pattern(query):
    return re.compile((r'(?<!\d)' if query[0].isdigit() else '') + re.escape(query)
                      + (r'(?!\d)' if query[-1].isdigit() else ''))


def retrieve(store, action, argument):
    if action == 'state_at':
        return store.state_at(argument['batch_id'], argument['counters'])
    if action == 'fetch':
        try:
            hit = store.get(argument)
            return {'batch_id': argument, 'text': hit['text'], 'truncated': False}
        except LedgerError as e:
            return {'error': str(e)}
    pattern = search_pattern(argument)
    hits = [h for h in store.recall(argument) if pattern.search(h['text'])]
    response = {'search': argument, 'matches': [], 'total_matches': len(hits)}
    for hit in hits[:8]:
        pos = pattern.search(hit['text']).start()
        snippet = hit['text'][max(0, pos-100):pos+600].encode()[:800].decode('utf-8', errors='ignore')
        response['matches'].append({'batch_id': hit['batch_id'], 'snippet': snippet})
    return response


def process(session, reply, questions, store, max_retrieval=24, *, retrieval_mode='history'):
    """Merge valid partial answers first, then execute one unambiguous action."""
    instruction_for(retrieval_mode)  # Configuration errors are not model refusals.
    errors = []
    types = {q['id']: answer_type(q) for q in questions}
    if not isinstance(reply, dict):
        session['feedback'] = 'error: reply must be a JSON object'
        return None
    if 'answers' in reply:
        if not isinstance(reply['answers'], dict):
            errors.append('answers must be an object')
        else:
            for key, value in reply['answers'].items():
                if key not in types:
                    errors.append('unknown question ID: ' + str(key)[:80])
                    continue
                expected = types[key]
                if value is not None and (type(value) is not expected or
                        (isinstance(value, str) and len(value.encode()) > 256) or
                        (type(value) is int and len(str(value)) > 64)):
                    errors.append('invalid value type or size for ' + key)
                    continue
                session['answers'][key] = value
    # Legacy mixed answers+search is a retrieval, never an implicit submission.
    action = reply.get('action')
    searches = [k for k in ('query', 'search') if k in reply]
    batches = [k for k in ('batch_id', 'batch') if k in reply]
    if action is None:
        action = 'search' if searches else 'fetch' if batches else 'update' if 'answers' in reply else None
    allowed = {'action', 'answers', 'query', 'search', 'batch_id', 'batch', 'counters'}
    if set(reply) - allowed:
        errors.append('unexpected fields; use one action')
    if (action not in ('search', 'fetch', 'state_at', 'update', 'submit') or len(searches) > 1 or len(batches) > 1
            or (searches and batches) or (action != 'search' and searches)
            or (action not in ('fetch', 'state_at') and batches)
            or ('counters' in reply and action != 'state_at')
            or (action == 'state_at' and ('batch' in reply or 'batch_id' not in reply))):
        errors.append('ambiguous or invalid action; choose exactly one action')
    if action == 'state_at' and retrieval_mode == 'source-only':
        errors.append('state_at is unavailable in source-only mode; use search or fetch')
    response = None
    if not errors and action in ('search', 'fetch', 'state_at'):
        argument = reply[searches[0]] if searches else reply[batches[0]] if batches else None
        valid = (isinstance(argument, str) and bool(argument.strip()) and len(argument.encode()) <= 256
                 if action == 'search' else type(argument) is int and argument > 0)
        if action == 'state_at' and valid:
            try:
                if 'counters' in reply and reply['counters'] is None:
                    raise ValueError('omit counters for the full state; null is not a selection')
                chosen = selection(argument, reply.get('counters'))
                argument = {'batch_id':argument, 'counters':chosen}
            except ValueError as error:
                errors.append(str(error));valid=False
        if not valid:
            errors.append('search needs nonempty query (at most 256 bytes); fetch needs positive integer batch_id')
        else:
            key = f'{action}:' + (json.dumps(argument,sort_keys=True,separators=(',',':'))
                                      if action == 'state_at' else str(argument))
            repeated = key in session['cache']
            if repeated:
                response = session['cache'][key]
            elif session['retrievals'] >= max_retrieval:
                errors.append('retrieval budget exhausted; update or submit saved answers, using null for unknowns')
            else:
                response = retrieve(store, action, argument)
                if 'error' not in response:
                    session['retrievals'] += 1
                    session['cache'][key] = response
            if response is not None and 'error' in response:
                errors.append(response['error'])
            elif response is not None:
                session['recent'] = [k for k in session['recent'] if k != key] + [key]
                session['feedback'] = ('Repeated retrieval: cached evidence restored; choose a different query or exact batch next.'
                                       if repeated else 'Evidence retrieved. Save answers as you establish them.')
    elif not errors and action == 'submit':
        missing = [q['id'] for q in questions if q['id'] not in session['answers']]
        if missing:
            errors.append('submission incomplete; provide values or null for: ' + ', '.join(missing))
        else:
            session['completed'] = True
            session['feedback'] = 'Submitted.'
    elif not errors:
        session['feedback'] = 'Answers saved; continue retrieval or explicitly submit when complete.'
    if errors:
        session['feedback'] = ('error: ' + '; '.join(errors)).encode()[:1200].decode('utf-8', errors='ignore')
    return response
