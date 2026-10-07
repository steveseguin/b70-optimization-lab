#!/usr/bin/env python3
"""Offline packet integrity and gold-reference feasibility, never model grading."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
COMMIT = 'a8bbae3119d9ea31d08bd8b7cec74941adabc6ac'
SOURCES = ['worker/README.md', 'worker/PLAN.md', 'docs/recipe-publication-standard.md', 'docs/local-ops.md']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads((HERE / path).read_text())


def validate():
    repo = Path(subprocess.check_output(['git', '-C', str(HERE), 'rev-parse', '--show-toplevel'], text=True).strip())
    compiler_path = HERE.parent / 'compile_citations.py'
    original_path = HERE.parent.parent / 'evaluation-20261007/memory/validate.py'
    compiler = load_module('v2compiler', compiler_path)
    original = load_module('original_citation_validator', original_path)
    manifest = read('manifest.json')
    require(manifest['source_commit'] == COMMIT, 'source commit drift')
    require([s['source_path'] for s in manifest['corpus']] == SOURCES, 'source selection drift')
    paths = [e['path'] for e in manifest['packet_files']]
    inventory = sorted(str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file() and p.name != 'manifest.json')
    require(len(paths) == len(set(paths)) and sorted(paths) == inventory, 'packet inventory drift')
    for entry in manifest['packet_files']:
        path = HERE / entry['path']
        require(not path.is_symlink() and path.resolve().is_relative_to(HERE), 'unsafe inventory path')
        data = path.read_bytes()
        require(len(data) == entry['bytes'] and digest(data) == entry['sha256'], 'file digest drift: ' + entry['path'])
    for entry, path in [(manifest['compiler'], compiler_path), (manifest['original_validator'], original_path)]:
        require(digest(path.read_bytes()) == entry['sha256'], 'external control source drift')
    # Inspect only the old source-path inventory, never its questions or answers.
    prior_manifest = json.loads((original_path.parent / 'manifest.json').read_text())
    prior_sources = {entry['source_path'] for entry in prior_manifest['corpus']}
    require(not prior_sources.intersection(SOURCES), 'corpus source reused from original packet')
    bundle_bytes = (HERE / 'model-input/source-bundle.json').read_bytes()
    bundle = compiler.strict_json(bundle_bytes)
    ids = compiler.validate_bundle(bundle)
    require(ids == [f'V2Q{i:02}' for i in range(1, 11)], 'fresh question count/order drift')
    require(set(bundle['corpus']) == {'S01', 'S02', 'S03', 'S04'}, 'corpus IDs drift')
    total = 0
    for entry in manifest['corpus']:
        source = subprocess.check_output(['git', '-C', str(repo), 'show', COMMIT + ':' + entry['source_path']])
        blob = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', COMMIT + ':' + entry['source_path']], text=True).strip()
        frozen = (HERE / entry['file']).read_bytes()
        require(source == frozen == bundle['corpus'][entry['doc_id']].encode('utf-8'), 'source is not complete exact pinned bytes')
        require(blob == entry['git_blob_oid'] and entry['source_commit'] == COMMIT, 'Git source identity drift')
        require(digest(source) == entry['sha256'] and len(source) == entry['bytes'], 'source digest drift')
        require(len(source.decode().splitlines()) == entry['line_count'], 'source line count drift')
        total += len(source)
    require(total == manifest['source_bytes_total'] == 27018, 'source byte total drift')
    key = read('review-only/answer-key.json')['answers']
    require([a['question_id'] for a in key] == ids, 'rubric question identity drift')
    count = 0
    for answer in key:
        require(len(answer['criteria']) == 3 and answer['disqualifying_errors'], 'rubric must have three criteria and disqualifiers')
        for index, criterion in enumerate(answer['criteria'], 1):
            require(criterion['id'] == answer['question_id'] + f'.C{index}' and criterion['meaning'] and criterion['supporting_references'], 'incomplete rubric criterion')
            for ref in criterion['supporting_references']:
                one = compiler.compile_references({'answers': [{'question_id': 'CONTROL', 'answer': 'structure only', 'citations': [ref]}]}, ['CONTROL'], bundle['corpus'])
                original.check_citation(one['answers'][0]['citations'][0], bundle['corpus'])
            count += 1
    gold_bytes = (HERE / 'review-only/gold-refs.json').read_bytes()
    gold = compiler.strict_json(gold_bytes)
    expected_gold = {'answers': [{'question_id': a['question_id'], 'answer': a['reference_answer'], 'citations': a['citations']} for a in key]}
    require(gold == expected_gold, 'gold reference control diverges from authored rubric')
    require(all(1 <= len(a['citations']) <= 2 for a in gold['answers']), 'gold exceeds protocol citation cap')
    compiled = compiler.compile_references(gold, ids, bundle['corpus'])
    require(compiled == read('review-only/gold-compiled.json'), 'gold compilation drift')
    original.check_responses(compiled, bundle['questions'], bundle['corpus'])
    with tempfile.TemporaryDirectory(prefix='recall-v2-offline-') as tmp:
        target = Path(tmp) / 'compiled'
        receipt = compiler.compile_files(HERE / 'model-input/source-bundle.json', HERE / 'review-only/gold-refs.json', target)
        require((target / 'source-bundle.json').read_bytes() == bundle_bytes and (target / 'raw-refs.json').read_bytes() == gold_bytes, 'raw input preservation drift')
        require(receipt == read('review-only/gold-compilation-receipt.json'), 'gold compilation receipt drift')
    protocol = read('protocol.json')
    require(protocol['model_visible_files'] == ['model-input/instructions.txt', 'model-input/source-bundle.json'], 'model visibility drift')
    require((protocol['input_token_limit'], protocol['context_token_limit'], protocol['output_token_limit'], protocol['outer_deadline_seconds'], protocol['wire_timeout_seconds']) == (28000, 33024, 3072, 420, 420), 'budget drift')
    require(protocol['model_calls'] == 1 and protocol['model_requests_performed'] == 0 and protocol['automatic_retries'] == 0 and protocol['all_questions_one_query'], 'request count drift')
    require(protocol['thinking'] is False and protocol['temperature'] == 0 and protocol['seed'] == 42, 'sampling drift')
    return {'packet_integrity': 'passed', 'source_commit': COMMIT, 'complete_source_files': 4, 'source_bytes': total, 'questions': 10, 'semantic_criteria': count, 'gold_reference_compiler': 'passed', 'unchanged_original_citation_validator': 'passed', 'gold_control_is_authored_not_model_output': True, 'semantic_grading': 'not-performed', 'model_requests': 0, 'model_quality_result': False, 'input_token_admission': 'pending exact rendered request/tokenizer; no token-count claim', 'independent_review': 'pending'}


if __name__ == '__main__':
    print(json.dumps(validate(), indent=2))
