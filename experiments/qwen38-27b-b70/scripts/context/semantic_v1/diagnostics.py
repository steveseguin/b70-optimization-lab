"""CPU-only scoring/replay of recorded responses. No model transport or launch code."""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from ledger import CanonicalLedger, LedgerError
from tasks import answer_type, digest, load_packet, public_task, require, verify
from answers import INSTRUCTION

ARMS = ('summary', 'archive', 'quoted')


def answer_payload(task):
    public = public_task(task)
    return {'instruction': INSTRUCTION, 'questions': public['questions'],
            'reading_conventions': public['reading_conventions']}


def grade_answers(task, answers):
    verify(task)
    require(isinstance(answers, dict), 'answers must be an object')
    ids = {q['id'] for q in task['questions']}
    groups, typed, invalid_types = {}, {}, []
    for question in task['questions']:
        key = question['id']; actual = answers.get(key)
        if key in answers and actual is not None and type(actual) is not answer_type(question):
            invalid_types.append(key)
        correct = type(actual) is answer_type(question) and actual == task['oracle']['answers'][key]
        for table, label in ((groups, question['category']), (typed, question['answer_type'])):
            row = table.setdefault(label, {'asked': 0, 'correct': 0})
            row['asked'] += 1; row['correct'] += correct
    return {'asked': len(ids), 'correct': sum(r['correct'] for r in groups.values()),
            'valid': not (set(answers) - ids), 'answer_types_valid': not invalid_types,
            'exact_question_coverage': set(answers) == ids, 'invalid_type_ids': invalid_types,
            'missing_ids': sorted(ids - set(answers)), 'unknown_ids': sorted(set(answers) - ids),
            'by_category': groups, 'by_answer_type': typed}


def state_metrics(actual, expected):
    if not isinstance(actual, dict) or any(not isinstance(k, str) or type(v) is not int for k, v in actual.items()):
        return {'valid': False, 'exact': False, 'correct': 0, 'asked': len(expected)}
    keys = set(actual) | set(expected)
    return {'valid': True, 'exact': actual == expected,
            'correct': sum(k in actual and k in expected and actual[k] == expected[k] for k in keys), 'asked': len(keys)}


def event_metrics(actual, expected):
    """Semantic tuple counts plus attributable field errors; no prose inference.

    First match equal semantic tuples. Remaining unique identical source quotes
    identify substitutions. Ambiguous leftovers remain omissions/spurious events.
    Quote validity and transactional acceptance are separate ledger outcomes.
    """
    if not isinstance(actual, list):
        return {'valid_format': False, 'expected': len(expected), 'predicted': None,
                'omitted': len(expected), 'spurious': 0, 'malformed': 1, 'exact_order': False,
                'matched': 0, 'substitutions': 0, 'wrong_fields': {'counter': 0, 'op': 0, 'amount': 0},
                'missed_events': len(expected), 'extra_events': 1,
                'semantic_precision': None, 'semantic_recall': 0 if expected else None, 'semantic_f1': None}
    def well_formed(event):
        return (isinstance(event, dict) and isinstance(event.get('counter'), str)
                and event.get('op') in ('set', 'add', 'sub') and type(event.get('amount')) is int
                and isinstance(event.get('quote'), str))
    def signature(event):
        return tuple(event[k] for k in ('counter', 'op', 'amount'))
    pending = list(range(len(expected))); remaining = []; matched = 0; malformed = 0
    for event in actual:
        if not well_formed(event):
            malformed += 1; continue
        found = next((i for i in pending if signature(expected[i]) == signature(event)), None)
        if found is None:
            remaining.append(event)
        else:
            pending.remove(found); matched += 1
    wrong = {'counter': 0, 'op': 0, 'amount': 0}; substitutions = 0; unpaired = []
    for event in remaining:
        candidates = [i for i in pending if expected[i]['quote'] == event['quote']]
        if len(candidates) == 1 and sum(e['quote'] == event['quote'] for e in remaining) == 1:
            reference = expected[pending.pop(pending.index(candidates[0]))]
            substitutions += 1
            for key in wrong:
                wrong[key] += event[key] != reference[key]
        else:
            unpaired.append(event)
    ordered = (not malformed and [signature(e) for e in actual] == [signature(e) for e in expected])
    precision = matched / len(actual) if actual else (0 if expected else 1)
    recall = matched / len(expected) if expected else 1
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {'valid_format': not malformed, 'expected': len(expected), 'predicted': len(actual),
            'matched': matched, 'omitted': len(pending), 'spurious': len(unpaired), 'malformed': malformed,
            'substitutions': substitutions, 'wrong_fields': wrong,
            'missed_events': len(pending) + substitutions, 'extra_events': len(unpaired) + substitutions + malformed,
            'semantic_precision': precision, 'semantic_recall': recall, 'semantic_f1': f1,
            'exact_order': ordered}


def evaluate_trace(task, arm, batches, answers, *, refusals=()):
    """Replay explicit recorded per-batch attempts, preserving refusals and omissions.

    batches=[{batch_id:int, attempts:[response_object,...]}]. Each response is the
    original arm JSON: quoted events, archive state, or summary memory. No retry
    is generated; all attempts must already exist in the supplied trace.
    """
    verify(task); require(arm in ARMS, 'unknown diagnostic arm')
    require(isinstance(batches, list) and len(batches) == len(task['batches']), 'complete source batch trace required')
    recorded_refusals = copy.deepcopy(list(refusals))
    trace_sha256 = digest({'document_id': task['document_id'], 'arm': arm,
                          'batches': batches, 'answers': answers, 'refusals': recorded_refusals})
    rows = []; rejected = copy.deepcopy(recorded_refusals); observed_state = {}; ingestion_complete = True
    with tempfile.TemporaryDirectory(prefix='semantic-replay-') as temp:
        with CanonicalLedger(Path(temp)/'ledger.sqlite') as store:
            for source, trace, expected, reference in zip(task['batches'], batches, task['oracle']['events'], task['oracle']['after_batch']):
                n = source['id']
                require(isinstance(trace, dict) and type(trace.get('batch_id')) is int and trace['batch_id'] == n,
                        'trace batch order mismatch')
                attempts = trace.get('attempts')
                require(isinstance(attempts, list) and bool(attempts), 'each batch needs recorded attempts')
                store.deliver(n, source['text'])
                attempts_report, accepted, metrics = [], False, None
                for index, response in enumerate(attempts):
                    require(not accepted, 'trace contains another attempt after successful batch application')
                    entry = {'attempt': index + 1}
                    if arm == 'quoted':
                        events = response.get('events') if isinstance(response, dict) else None
                        entry['events'] = event_metrics(events, expected)
                        try:
                            require(isinstance(events, list), 'events must be a list')
                            require(all(isinstance(event, dict) and event.get('op') in ('set', 'add', 'sub')
                                        for event in events), 'semantic events support only set/add/sub')
                            changes = [{'id': f'{n}:{i}', **{k:v for k,v in event.items() if k != 'id'}}
                                       for i, event in enumerate(events)]
                            receipt = store.apply(n, changes)
                            entry['receipt'] = receipt; observed_state = store.metadata()['state']; accepted = True
                        except (ValueError, TypeError, AttributeError, LedgerError) as error:
                            rejected.append({'batch_id': n, 'attempt': index+1, 'error': str(error)})
                            entry['refused'] = str(error)
                    elif arm == 'archive':
                        candidate = response.get('state') if isinstance(response, dict) else None
                        metrics = state_metrics(candidate, reference)
                        accepted = metrics['valid']
                        if accepted: observed_state = copy.deepcopy(candidate)
                        else: rejected.append({'batch_id': n, 'attempt': index+1, 'error': 'invalid state object'})
                    else:
                        accepted = isinstance(response, dict) and isinstance(response.get('memory'), str)
                        if not accepted: rejected.append({'batch_id': n, 'attempt': index+1, 'error': 'invalid summary object'})
                    entry['accepted'] = accepted; attempts_report.append(entry)
                ingestion_complete &= accepted
                rows.append({'batch_id': n, 'attempts': attempts_report, 'accepted': accepted,
                             'state': state_metrics(observed_state, reference) if arm != 'summary' else None})
    score = grade_answers(task, answers)
    final_answer_complete = score['valid'] and score['exact_question_coverage'] and score['answer_types_valid']
    return {'schema': 'semantic-development-diagnostic.v1', 'document_id': task['document_id'],
            'pair_id': task['pair_id'], 'variant': task['variant'], 'arm': arm,
            'task_sha256': task['task_sha256'], 'trace_sha256': trace_sha256,
            'measurement_kind': 'cpu-recorded-response-replay',
            'ingestion_complete': ingestion_complete, 'final_answer_complete': final_answer_complete,
            'protocol_complete': ingestion_complete and final_answer_complete,
            'score': score, 'batches': rows, 'refusals': rejected,
            'all_checkpoint_states_exact': (all(r['state']['exact'] for r in rows) if arm != 'summary' else None),
            'final_state_exact': rows[-1]['state']['exact'] if arm != 'summary' else None,
            'scope': 'Development diagnostic only; no model calls, speed claim or holdout admission.'}


def compare_pairs(results):
    """Require both versions for every supplied arm/pair; never drop a failed row."""
    grouped = {}
    for result in results:
        key = (result['pair_id'], result['arm'])
        pair = grouped.setdefault(key, {})
        require(result['variant'] in ('stress', 'control') and result['variant'] not in pair, 'duplicate or invalid pair member')
        pair[result['variant']] = result
    output = []
    for (pair_id, arm), pair in sorted(grouped.items()):
        require(set(pair) == {'stress', 'control'}, 'incomplete stress/control pair')
        output.append({'pair_id': pair_id, 'arm': arm, 'stress': pair['stress'], 'control': pair['control']})
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--documents', type=Path, required=True)
    parser.add_argument('--annotations', type=Path, required=True)
    parser.add_argument('--trace', type=Path, required=True)
    args = parser.parse_args()
    tasks = {t['document_id']: t for t in load_packet(args.documents, args.annotations)}
    trace = json.loads(args.trace.read_bytes())
    result = evaluate_trace(tasks[trace['document_id']], trace['arm'], trace['batches'], trace['answers'],
                            refusals=trace.get('refusals', []))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
