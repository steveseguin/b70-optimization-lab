"""CPU-only cross-check for this fixed, controlled-grammar development packet.

This checks authored source lines, not arbitrary prose understanding or model
quality. Run from any directory; emits a JSON receipt without changing inputs.
"""
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    paths = [ROOT / name for name in (
        'documents.json', 'annotations-independent.json', 'annotations-review.json')]
    source, first, second = [json.loads(path.read_bytes()) for path in paths]
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    source_sha = hashes['documents.json']
    rows = []
    references = []
    for annotation in (first, second):
        require(annotation['source_sha256'] == source_sha, 'annotation source hash')
        refs = {doc['document_id']: doc for doc in annotation['documents']}
        require(len(refs) == len(annotation['documents']), 'duplicate reference')
        require(set(refs) == {doc['id'] for doc in source['documents']}, 'document coverage')
        references.append(refs)
    for doc in source['documents']:
        state, owners, reviews, states, owner_states, batches = {}, {}, {}, [], [], []
        for batch in doc['batches']:
            number = batch['id']
            require(number == len(states) + 1, 'batch sequence')
            events = []
            for line in batch['text'].splitlines():
                if line.startswith('The balance of '):
                    match = re.fullmatch(r'The balance of ([a-z]+[0-9]{2}) (is now|increased by|decreased by) (-?\d+)\.', line)
                    require(match is not None, 'unrecognized posting')
                    counter, verb, number_text = match.groups()
                    op = {'is now': 'set', 'increased by': 'add', 'decreased by': 'sub'}[verb]
                    amount = int(number_text)
                    require(op == 'set' or (counter in state and amount > 0), 'uninitialized arithmetic')
                    state[counter] = amount if op == 'set' else state[counter] + (amount if op == 'add' else -amount)
                    events.append(dict(counter=counter, op=op, amount=amount, quote=line))
                elif line.startswith('ticket-'):
                    match = re.fullmatch(r'(ticket-[a-z]+-[a-h]) belongs to counter ([a-z]+[0-9]{2})\.', line)
                    if match:
                        ticket, counter = match.groups()
                        require(ticket not in owners, 'repeated initial ownership')
                    else:
                        match = re.fullmatch(r'(ticket-[a-z]+-[a-h]) was transferred to ([a-z]+[0-9]{2}), effective before this batch ended\.', line)
                        require(match is not None, 'unrecognized ownership posting')
                        ticket, counter = match.groups()
                        require(ticket in owners, 'transfer before assignment')
                    require(counter in state, 'unknown owner')
                    owners[ticket] = (counter, number)
                elif line.startswith('review-'):
                    match = re.fullmatch(r'(review-[a-z]+-[1-8]) concerns (ticket-[a-z]+-[a-h])\.', line)
                    require(match is not None, 'unrecognized review link')
                    review, ticket = match.groups()
                    require(review not in reviews and ticket in owners, 'invalid review')
                    reviews[review] = ticket
            states.append(copy.deepcopy(state))
            owner_states.append(copy.deepcopy(owners))
            batches.append(dict(batch_id=number, events=events, state_after=copy.deepcopy(state)))
        answers, basis, temporal_batches = {}, {}, set()
        different = 0
        for question in doc['questions']:
            qid, text = question['id'], question['text']
            require(qid not in answers and question['answer_type'] == 'int', 'question identity/type')
            if question['category'] in ('current', 'history'):
                match = re.fullmatch(r'What (is|was) the balance of ([a-z]+[0-9]{2}) at the end of batch (\d+)\?', text)
                require(match is not None, 'unrecognized balance question')
                tense, counter, target_text = match.groups()
                target = int(target_text)
                require((tense == 'is') == (question['category'] == 'current'), 'question tense')
                ref = dict(counter=counter, batch_id=target)
            else:
                require(question['category'] == 'join', 'question category')
                match = re.fullmatch(r"Follow (review-[a-z]+-[1-8]) to its ticket\. Using the owner of that ticket at the end of batch (\d+), what was that counter's balance at the end of batch (\d+)\?", text)
                require(match is not None, 'unrecognized ownership question')
                review, target_text, repeated_target = match.groups()
                require(target_text == repeated_target, 'mismatched ownership/balance dates')
                target = int(target_text)
                ticket = reviews[review]
                counter, ownership_batch = owner_states[target - 1][ticket]
                ref = dict(counter=counter, batch_id=target, ownership_source_batch=ownership_batch,
                           review=review, ticket=ticket)
            require(1 <= target <= len(states), 'target range')
            answers[qid] = states[target - 1][counter]
            basis[qid] = ref
            if question['category'] != 'current':
                require(target < len(states), 'historical question at final close')
                temporal_batches.add(target)
                different += answers[qid] != states[-1][counter]
            else:
                require(target == len(states), 'current question before final close')
        for refs in references:
            ref = refs[doc['id']]
            require(ref['source_sha256'] == source_sha, 'document reference source hash')
            require(ref['batches'] == batches, 'events/quotes/states disagree with source replay')
            require(ref['answers'] == answers, 'answers disagree with source replay')
            require(ref['answer_basis'] == basis, 'answer basis disagrees with source replay')
        rows.append(dict(document_id=doc['id'], events=sum(len(b['events']) for b in batches),
                         states=len(states), answers=len(answers),
                         temporal_answers_differing_from_final=different,
                         distinct_historical_batches=sorted(temporal_batches)))
    print(json.dumps(dict(schema='context-temporal-reference-check.v1', input_sha256=hashes,
                         verification_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                         passed=True, disagreements=0, documents=rows,
                         scope='Controlled explicit-line replay plus question/ownership grammar checks. '
                               'Narrative interpretation separately reviewed by assistants; no human '
                               'validation, model-quality result, speed gate or execution admission.',
                         speed_gate=False, holdout_admission=False), indent=2))


if __name__ == '__main__':
    main()
