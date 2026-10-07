"""Explicitly annotated semantic development tasks. Never infer a key from prose."""
import copy
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType

SCHEMA = 'semantic-development-task.v1'


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def answer_type(question):
    name = question.get('answer_type')
    require(name in ('int', 'str'), 'question requires explicit int/str answer_type')
    return int if name == 'int' else str


def compile_document(document, annotation, source_sha, *, expected_source_sha=None, reading_conventions=()):
    """Compile one authored document and an independently adjudicated annotation.

    The caller supplies the actual SHA256 of documents.json bytes; load_packet
    computes it directly. No narrative parsing or answer inference occurs here.
    Replay checks annotation consistency only, not independent semantic truth.
    """
    require(isinstance(document, dict) and isinstance(annotation, dict), 'document and annotation required')
    require(isinstance(source_sha, str) and re.fullmatch('[0-9a-f]{64}', source_sha), 'invalid source SHA256')
    require(expected_source_sha is None or source_sha == expected_source_sha, 'source hash mismatch')
    require(annotation.get('source_sha256') == source_sha, 'annotation source hash mismatch')
    require(annotation.get('document_id') == document.get('id') and isinstance(document.get('id'), str),
            'annotation document identity mismatch')
    require(isinstance(reading_conventions, (list, tuple))
            and all(isinstance(rule, str) and rule for rule in reading_conventions), 'reading conventions must be text')
    batches, questions = document.get('batches'), document.get('questions')
    require(isinstance(batches, list) and bool(batches), 'document batches required')
    require(isinstance(questions, list) and bool(questions), 'document questions required')
    refs = annotation.get('batches')
    require(isinstance(refs, list) and len(refs) == len(batches), 'one annotation per batch required')
    qids = []
    for question in questions:
        require(isinstance(question, dict) and set(question) == {'id', 'category', 'answer_type', 'text'}, 'unexpected question fields')
        require(isinstance(question, dict) and isinstance(question.get('id'), str) and question['id'], 'invalid question ID')
        require(question.get('category') in ('current', 'history', 'join'), 'invalid question category')
        require(isinstance(question.get('text'), str) and question['text'], 'question text required')
        answer_type(question)
        qids.append(question['id'])
    answers = annotation.get('answers')
    require(len(qids) == len(set(qids)) and isinstance(answers, dict) and set(qids) == set(answers),
            'annotation answers must cover unique question IDs exactly')
    for question in questions:
        require(type(answers[question['id']]) is answer_type(question), 'annotated answer type mismatch')
    state, all_events, states = {}, [], []
    for n, (batch, ref) in enumerate(zip(batches, refs), 1):
        require(isinstance(batch, dict) and type(batch.get('id')) is int and batch['id'] == n
                and set(batch) == {'id', 'text'} and isinstance(batch.get('text'), str), 'source batch IDs must be contiguous with text')
        require(isinstance(ref, dict) and type(ref.get('batch_id')) is int and ref['batch_id'] == n,
                'annotation batch IDs must match source order')
        events = ref.get('events')
        require(isinstance(events, list), 'annotated events required, including empty lists')
        previous, signatures, compiled = -1, set(), []
        for ordinal, event in enumerate(events):
            require(isinstance(event, dict) and set(event) == {'counter', 'op', 'amount', 'quote'}, 'invalid annotation event fields')
            counter, op, amount, quote = (event[k] for k in ('counter', 'op', 'amount', 'quote'))
            require(isinstance(counter, str) and re.fullmatch('[a-z]+[0-9]{2}', counter), 'unsupported counter name')
            require(op in ('set', 'add', 'sub') and type(amount) is int
                    and (op == 'set' or amount > 0), 'only literal integer set/add/sub supported')
            require(isinstance(quote, str) and bool(quote) and quote in batch['text'], 'annotation quote absent from exact batch text')
            start = batch['text'].find(quote)
            require(start >= previous, 'annotated events are out of source order')
            previous = start
            signature = (counter, op, amount, quote)
            require(signature not in signatures, 'duplicate annotated event; occurrence interface unsupported')
            signatures.add(signature)
            require(op == 'set' or counter in state, 'arithmetic references an uninitialized counter')
            state[counter] = amount if op == 'set' else state[counter] + (amount if op == 'add' else -amount)
            compiled.append({'id': f'{n}:{ordinal}', **copy.deepcopy(event)})
        reference = ref.get('state_after')
        require(isinstance(reference, dict) and all(isinstance(k, str) and type(v) is int for k, v in reference.items()),
                'state_after must contain integer balances')
        require(state == reference, 'annotated event replay disagrees with independently supplied state_after')
        all_events.append(compiled)
        states.append(copy.deepcopy(reference))
    task = {'schema': SCHEMA, 'document_id': document['id'], 'pair_id': document.get('pair_id'),
            'variant': document.get('variant'), 'source_sha256': source_sha,
            'document_sha256': digest(document), 'annotation_sha256': digest(annotation),
            'batches': copy.deepcopy(batches), 'questions': copy.deepcopy(questions),
            'reading_conventions': list(reading_conventions),
            'oracle': {'answers': copy.deepcopy(answers), 'events': all_events, 'after_batch': states},
            'scope': 'Authored semantic development diagnostic; not a speed benchmark or holdout.'}
    task['task_sha256'] = digest(task)
    return task


def verify(task):
    require(isinstance(task, dict) and task.get('schema') == SCHEMA, 'unsupported semantic task')
    require(task.get('task_sha256') == digest({k: v for k, v in task.items() if k != 'task_sha256'}), 'task hash mismatch')
    require(len(task['oracle']['events']) == len(task['batches']) == len(task['oracle']['after_batch']),
            'one event/state reference per source batch required')
    # Revalidate the annotation contract, without attempting to interpret prose.
    document = {'id': task['document_id'], 'pair_id': task['pair_id'], 'variant': task['variant'],
                'batches': task['batches'], 'questions': task['questions']}
    annotation = {'document_id': task['document_id'], 'source_sha256': task['source_sha256'],
                  'answers': task['oracle']['answers'], 'batches': [
                      {'batch_id': n, 'state_after': state,
                       'events': [{k: v for k, v in event.items() if k != 'id'} for event in events]}
                      for n, (state, events) in enumerate(zip(task['oracle']['after_batch'], task['oracle']['events']), 1)]}
    compile_document(document, annotation, task['source_sha256'], reading_conventions=task['reading_conventions'])


def public_task(task):
    """Allowlisted deep copy for prompts: never include references, answers or hashes."""
    verify(task)
    return {'document_id': task['document_id'], 'batches': copy.deepcopy(task['batches']),
            'questions': copy.deepcopy(task['questions']), 'reading_conventions': list(task['reading_conventions'])}


def reference_view(task):
    """Read-only copy for host-side scoring; never put this object in a prompt."""
    verify(task)
    def freeze(value):
        if isinstance(value, dict):
            return MappingProxyType({k: freeze(v) for k, v in value.items()})
        if isinstance(value, list):
            return tuple(freeze(v) for v in value)
        return value
    return freeze(task['oracle'])


def load_packet(documents_path, adjudicated_path):
    data = Path(documents_path).read_bytes()
    packet = json.loads(data)
    adjudicated_path = Path(adjudicated_path).resolve()
    adjudicated_bytes = adjudicated_path.read_bytes()
    annotations = json.loads(adjudicated_bytes)
    source_sha = hashlib.sha256(data).hexdigest()
    require(annotations.get('schema') == 'context-semantic-adjudicated.v1', 'adjudicated annotations required')
    require(annotations.get('source_sha256') == source_sha, 'packet source hash mismatch')
    sources = annotations.get('annotation_sources')
    require(isinstance(sources, list) and len(sources) >= 2, 'two independent annotation sources required')
    seen = set()
    for source in sources:
        require(isinstance(source, dict) and isinstance(source.get('path'), str)
                and isinstance(source.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', source['sha256']),
                'annotation source requires relative path and SHA256')
        relative = Path(source['path'])
        path = (adjudicated_path.parent / relative).resolve()
        require(not relative.is_absolute() and path.is_relative_to(adjudicated_path.parent)
                and path not in seen and path != adjudicated_path, 'annotation source path escapes or duplicates packet')
        require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256'],
                'annotation source hash mismatch')
        seen.add(path)
    docs, refs = packet.get('documents'), annotations.get('documents')
    require(isinstance(docs, list) and isinstance(refs, list), 'document and annotation lists required')
    ids = [d['id'] for d in docs]; ref_ids = [r['document_id'] for r in refs]
    require(len(ids) == len(set(ids)) and len(ref_ids) == len(set(ref_ids)) and set(ids) == set(ref_ids),
            'exactly one annotation per document required')
    by_id = {r['document_id']: r for r in refs}
    tasks = []
    for document in docs:
        task = compile_document(document, by_id[document['id']], source_sha,
                                reading_conventions=packet.get('reading_conventions', []))
        task['adjudication_sha256'] = hashlib.sha256(adjudicated_bytes).hexdigest()
        task['annotation_sources'] = copy.deepcopy(sources)
        task['task_sha256'] = digest({k:v for k,v in task.items() if k != 'task_sha256'})
        tasks.append(task)
    return tasks
