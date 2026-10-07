#!/usr/bin/env python3
"""Compile line references into exact quotes; never assess answer meaning."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


SOURCE_SCHEMA = 'lab.cited-recall.sources.v2'
MAX_CITATION_LINES = 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact_fields(value, fields, label):
    require(isinstance(value, dict), label + ' must be an object')
    require(set(value) == set(fields), label + ' has missing or unknown fields')


def valid_text(value, label, nonempty=True):
    require(isinstance(value, str), label + ' must be a string')
    require(not nonempty or bool(value.strip()), label + ' must not be empty')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ValueError(label + ' must contain valid Unicode') from error


def validate_sources(expected_question_ids, corpus):
    require(isinstance(expected_question_ids, list) and expected_question_ids,
            'expected question IDs must be a nonempty list')
    for qid in expected_question_ids:
        valid_text(qid, 'expected question ID')
    require(len(set(expected_question_ids)) == len(expected_question_ids),
            'expected question IDs must be unique')
    require(isinstance(corpus, dict) and corpus, 'corpus must be a nonempty object')
    for doc_id, text in corpus.items():
        valid_text(doc_id, 'corpus document ID')
        valid_text(text, 'corpus document text', nonempty=False)


def compile_references(raw_refs, expected_question_ids, corpus):
    """Pure function: input IDs are opaque keys; no file/network access or repair.

    Line semantics deliberately match the original citation validator:
    str.splitlines(), one-based inclusive ranges, joined with LF. Whitespace
    within lines is preserved. Source line-ending bytes live in the raw bundle.
    """
    validate_sources(expected_question_ids, corpus)
    exact_fields(raw_refs, {'answers'}, 'response')
    answers = raw_refs['answers']
    require(isinstance(answers, list), 'answers must be a list')
    require(len(answers) == len(expected_question_ids), 'missing or extra question answers')
    compiled = []
    for index, answer in enumerate(answers):
        exact_fields(answer, {'question_id', 'answer', 'citations'}, 'answer')
        valid_text(answer['question_id'], 'question ID')
        require(answer['question_id'] == expected_question_ids[index],
                'unknown, duplicate, or out-of-order question ID')
        valid_text(answer['answer'], 'answer text')
        citations = answer['citations']
        require(isinstance(citations, list) and citations, 'citations must be a nonempty list')
        compiled_citations = []
        for citation in citations:
            exact_fields(citation, {'doc_id', 'start_line', 'end_line'}, 'citation')
            doc_id = citation['doc_id']
            valid_text(doc_id, 'citation document ID')
            require(doc_id in corpus, 'unknown citation document')
            start, end = citation['start_line'], citation['end_line']
            require(type(start) is int and type(end) is int, 'citation lines must be strict integers')
            lines = corpus[doc_id].splitlines()
            require(1 <= start <= end <= len(lines), 'citation range is outside document')
            require(end - start + 1 <= MAX_CITATION_LINES, 'citation exceeds 20 lines')
            compiled_citations.append({'doc_id': doc_id, 'start_line': start, 'end_line': end,
                                       'quote': '\n'.join(lines[start - 1:end])})
        compiled.append({'question_id': answer['question_id'], 'answer': answer['answer'],
                         'citations': compiled_citations})
    return {'answers': compiled}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate JSON object key')
        value[key] = item
    return value


def reject_constant(value):
    raise ValueError('non-finite JSON numbers are not allowed')


def strict_json(data):
    return json.loads(data.decode('utf-8'), object_pairs_hook=unique_object,
                      parse_constant=reject_constant)


def validate_bundle(bundle):
    exact_fields(bundle, {'schema', 'questions', 'corpus'}, 'source bundle')
    require(bundle['schema'] == SOURCE_SCHEMA, 'unknown source bundle schema')
    questions = bundle['questions']
    require(isinstance(questions, list) and questions, 'questions must be a nonempty list')
    for question in questions:
        exact_fields(question, {'id', 'prompt'}, 'question')
        valid_text(question['id'], 'question ID')
        valid_text(question['prompt'], 'question prompt')
    expected = [question['id'] for question in questions]
    validate_sources(expected, bundle['corpus'])
    return expected


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def pretty_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')


def compile_files(source_bundle, raw_refs, output_directory):
    """Trusted caller paths only; create a new directory and never overwrite.

    Validate before creating output. If an output write fails, retain that
    incomplete directory for inspection; later invocations must use a new one.
    """
    bundle_bytes = Path(source_bundle).read_bytes()
    raw_bytes = Path(raw_refs).read_bytes()
    bundle = strict_json(bundle_bytes)
    expected = validate_bundle(bundle)
    compiled = compile_references(strict_json(raw_bytes), expected, bundle['corpus'])
    compiled_bytes = pretty_bytes(compiled)
    receipt = {
        'schema': 'lab.cited-recall.compilation.v2',
        'mechanical_validation': 'passed',
        'semantic_grading': 'not-performed',
        'citation_relevance': 'not-checked',
        'model_quality_result': False,
        'raw_refs_sha256': sha256(raw_bytes),
        'source_bundle_sha256': sha256(bundle_bytes),
        'questions_sha256': sha256(canonical_bytes(bundle['questions'])),
        'corpus_sha256': sha256(canonical_bytes(bundle['corpus'])),
        'compiler_sha256': sha256(Path(__file__).read_bytes()),
        'compiled_sha256': sha256(compiled_bytes),
        'expected_question_ids': expected,
        'documents': {key: {'utf8_sha256': sha256(text.encode('utf-8')),
                            'line_count': len(text.splitlines())}
                      for key, text in sorted(bundle['corpus'].items())},
        'hash_encoding': 'Component hashes use UTF-8 JSON, sorted keys, compact separators, unescaped Unicode; raw file hashes use original bytes.',
        'line_semantics': 'Python str.splitlines(); one-based inclusive ranges; quote joined with LF.',
    }
    output = Path(output_directory)
    output.mkdir(exist_ok=False)
    for name, data in [('raw-refs.json', raw_bytes), ('source-bundle.json', bundle_bytes),
                       ('compiled.json', compiled_bytes), ('receipt.json', pretty_bytes(receipt))]:
        with (output / name).open('xb') as stream:
            stream.write(data)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-bundle', type=Path, required=True)
    parser.add_argument('--raw-refs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt = compile_files(args.source_bundle, args.raw_refs, args.out)
    except (ValueError, OSError) as error:
        print(json.dumps({'status': 'refused', 'error': str(error),
                          'semantic_grading': 'not-performed'}), file=sys.stderr)
        return 2
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
