"""Durable answer/retrieval protocol. No oracle or grading access."""
import re

from ledger import LedgerError

INSTRUCTION = '''Answer the listed questions using your memory and original evidence.
Every reply is one JSON object with one action: "search", "fetch", "update", or "submit".
You may include "answers":{"question-id":value} with ANY action; these are saved and can be revised.
Use integers for current/join answers, strings for history, or null for an unknown.
Search: {"action":"search","query":"literal text"}. Fetch an exact original batch:
{"action":"fetch","batch_id":2}. Search uses digit boundaries (batch 2 excludes batch 20).
Use fetch when a question names a batch. Repeated retrieval returns cached evidence and
still uses an answer call. Update saves answers without ending. To finish use
{"action":"submit","answers":{...}} after every question has a saved value (null allowed).
Partial answers never finish the task. Budget exhaustion does not submit automatically.
All arms have identical access to original batches. Do not invent facts.'''


def new_session():
    return {'answers': {}, 'calls': 0, 'retrievals': 0, 'cache': {}, 'recent': [],
            'feedback': None, 'completed': False}


def search_pattern(query):
    return re.compile((r'(?<!\d)' if query[0].isdigit() else '') + re.escape(query)
                      + (r'(?!\d)' if query[-1].isdigit() else ''))


def retrieve(store, action, argument):
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


def process(session, reply, questions, store, max_retrieval=24):
    """Merge valid partial answers first, then execute one unambiguous action."""
    errors = []
    categories = {q['id']: q['category'] for q in questions}
    if not isinstance(reply, dict):
        session['feedback'] = 'error: reply must be a JSON object'
        return None
    if 'answers' in reply:
        if not isinstance(reply['answers'], dict):
            errors.append('answers must be an object')
        else:
            for key, value in reply['answers'].items():
                if key not in categories:
                    errors.append('unknown question ID: ' + str(key)[:80])
                    continue
                expected = str if categories[key] == 'history' else int
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
    allowed = {'action', 'answers', 'query', 'search', 'batch_id', 'batch'}
    if set(reply) - allowed:
        errors.append('unexpected fields; use one action')
    if (action not in ('search', 'fetch', 'update', 'submit') or len(searches) > 1 or len(batches) > 1
            or (searches and batches) or (action != 'search' and searches)
            or (action != 'fetch' and batches)):
        errors.append('ambiguous or invalid action; choose exactly one action')
    response = None
    if not errors and action in ('search', 'fetch'):
        argument = reply[searches[0]] if searches else reply[batches[0]] if batches else None
        valid = (isinstance(argument, str) and bool(argument.strip()) and len(argument.encode()) <= 256
                 if action == 'search' else type(argument) is int and argument > 0)
        if not valid:
            errors.append('search needs nonempty query (at most 256 bytes); fetch needs positive integer batch_id')
        else:
            key = f'{action}:{argument}'
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
