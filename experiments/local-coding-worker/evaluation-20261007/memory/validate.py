#!/usr/bin/env python3
"""Validate packet provenance and citation structure; never grade answer meaning."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
SOURCE_COMMIT = '76f3ebd23f3f9b378e6088678967addd0b617951'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def packet_path(relative):
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts, 'unsafe packet path')
    resolved = (HERE / path).resolve()
    require(resolved.is_relative_to(HERE), 'packet path escapes packet directory')
    return resolved


def check_citation(citation, documents):
    require(isinstance(citation, dict), 'citation must be an object')
    doc_id = citation.get('doc_id')
    require(doc_id in documents, 'unknown citation document')
    start, end = citation.get('start_line'), citation.get('end_line')
    lines = documents[doc_id].splitlines()
    require(type(start) is int and type(end) is int, 'citation lines must be integers')
    require(1 <= start <= end <= len(lines), 'citation range is outside document')
    require(end - start < 20, 'citation must be focused: at most 20 lines')
    expected = '\n'.join(lines[start - 1:end])
    require(citation.get('quote') == expected, 'citation quote does not match exact frozen lines')


def check_responses(responses, questions, documents):
    require(isinstance(responses, dict) and isinstance(responses.get('answers'), list),
            'responses must contain an answers list')
    expected = {q['id'] for q in questions}
    found = set()
    for answer in responses['answers']:
        require(isinstance(answer, dict), 'answer must be an object')
        qid = answer.get('question_id')
        require(qid in expected and qid not in found, 'unknown or duplicate question ID')
        found.add(qid)
        require(isinstance(answer.get('answer'), str) and answer['answer'].strip(), 'empty answer')
        citations = answer.get('citations')
        require(isinstance(citations, list) and citations, 'answer needs citations')
        for citation in citations:
            check_citation(citation, documents)
    require(found == expected, 'missing question answers')


def self_test():
    docs = {'D01': 'first\nsecond\nthird\n'}
    questions = [{'id': 'Q01'}]
    valid = {'answers': [{'question_id': 'Q01', 'answer': 'An unsupported claim can be syntactically valid.',
                         'citations': [{'doc_id': 'D01', 'start_line': 1, 'end_line': 2,
                                        'quote': 'first\nsecond'}]}]}
    check_responses(valid, questions, docs)
    mutations = [
        lambda x: x['answers'][0]['citations'][0].update(doc_id='D99'),
        lambda x: x['answers'][0]['citations'][0].update(start_line=0),
        lambda x: x['answers'][0]['citations'][0].update(end_line=4),
        lambda x: x['answers'][0]['citations'][0].update(start_line=3, end_line=2),
        lambda x: x['answers'][0]['citations'][0].update(start_line=True),
        lambda x: x['answers'][0]['citations'][0].update(quote='invented'),
        lambda x: x['answers'][0].update(question_id='Q99'),
        lambda x: x['answers'][0].update(answer=''),
        lambda x: x['answers'][0].update(citations=[]),
        lambda x: x['answers'].append(copy.deepcopy(x['answers'][0])),
        lambda x: x.update(answers=[]),
    ]
    for index, mutate in enumerate(mutations):
        bad = copy.deepcopy(valid)
        mutate(bad)
        try:
            check_responses(bad, questions, docs)
        except ValueError:
            continue
        raise ValueError(f'self-test mutation {index} was not rejected')
    return {'valid_structure_case': 1, 'rejected_bad_structure_cases': len(mutations),
            'semantic_correctness_intentionally_not_inferred': True}


def validate_packet():
    manifest = json.loads((HERE / 'manifest.json').read_text())
    require(manifest['source_commit'] == SOURCE_COMMIT, 'unexpected source commit')
    require(manifest['status'] == 'unrun-packet-not-heldout-model-quality-evidence', 'status drift')
    require(len(manifest['corpus']) == 5, 'expected five corpus documents')
    expected_files = {'questions.json', 'answer-key.json', 'protocol.json', 'validate.py',
                      *[f'corpus/D{i:02}.txt' for i in range(1, 6)]}
    paths = [entry['path'] for entry in manifest['packet_files']]
    require(len(paths) == len(expected_files) and set(paths) == expected_files,
            'packet file inventory is incomplete or duplicated')
    for entry in manifest['packet_files']:
        content = packet_path(entry['path']).read_bytes()
        require(hashlib.sha256(content).hexdigest() == entry['sha256'], 'packet hash mismatch: ' + entry['path'])
    repo = Path(subprocess.check_output(['git', '-C', str(HERE), 'rev-parse', '--show-toplevel'], text=True).strip())
    documents = {}
    for entry in manifest['corpus']:
        require(entry['id'] not in documents, 'duplicate document ID')
        frozen = packet_path(entry['file']).read_bytes()
        require(hashlib.sha256(frozen).hexdigest() == entry['sha256'], 'corpus hash mismatch')
        require(entry['source_commit'] == SOURCE_COMMIT, 'mixed source commits')
        source = subprocess.check_output(['git', '-C', str(repo), 'show',
                                          SOURCE_COMMIT + ':' + entry['source_path']])
        require(source == frozen, 'corpus differs from frozen Git source: ' + entry['id'])
        blob = subprocess.check_output(['git', '-C', str(repo), 'rev-parse',
                                        SOURCE_COMMIT + ':' + entry['source_path']], text=True).strip()
        require(blob == entry['git_blob_oid'], 'source blob identity mismatch')
        text = frozen.decode('utf-8')
        require(len(text.splitlines()) == entry['line_count'], 'line count mismatch')
        documents[entry['id']] = text
    require(set(documents) == {f'D{i:02}' for i in range(1, 6)}, 'unexpected document IDs')
    questions = json.loads((HERE / 'questions.json').read_text())['questions']
    key = json.loads((HERE / 'answer-key.json').read_text())['answers']
    ids = [q['id'] for q in questions]
    require(len(ids) == 10 and len(set(ids)) == 10, 'expected ten unique questions')
    require(set(ids) == {answer['question_id'] for answer in key} and len(key) == 10,
            'answer key does not match question IDs')
    require(all(q.get('prompt') for q in questions), 'empty question')
    criteria_count = 0
    for answer in key:
        require(answer['required_claims'] and answer['disqualifying_errors'], 'missing semantic rubric')
        for criterion in answer['required_claims']:
            criteria_count += 1
            require(criterion['meaning'] and criterion['evidence'], 'unsupported rubric criterion')
            for citation in criterion['evidence']:
                check_citation(citation, documents)
    protocol = json.loads((HERE / 'protocol.json').read_text())
    exposure = set(protocol['model_visible_files'])
    require(exposure == {'questions.json', *[e['file'] for e in manifest['corpus']]},
            'model-visible file list must expose only questions and corpus')
    require(protocol['semantic_grading'] == 'human-or-independent-review-required', 'semantic grading drift')
    require(protocol['model_calls_performed'] == 0, 'unrun packet claims model calls')
    return questions, documents, criteria_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--responses', type=Path, help='optional answer JSON; checks structure/citations only')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    try:
        questions, documents, criteria_count = validate_packet()
        result = {'packet_integrity': 'passed', 'source_commit': SOURCE_COMMIT,
                  'questions': len(questions), 'documents': len(documents),
                  'rubric_criteria_checked': criteria_count,
                  'semantic_grade': 'not-performed', 'model_quality_result': False}
        if args.responses:
            check_responses(json.loads(args.responses.read_text()), questions, documents)
            result['answer_structure_and_exact_quote_validation'] = 'passed'
            result['note'] = 'Valid citations may be irrelevant or contradicted by the answer. Human semantic review remains mandatory.'
        if args.self_test:
            result['self_test'] = self_test()
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'packet_integrity': 'failed', 'error': str(exc),
                          'semantic_grade': 'not-performed', 'model_quality_result': False}, indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
