#!/usr/bin/env python3
"""Synthetic offline controls only; never replay the original ten questions."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compile_citations import (SOURCE_SCHEMA, canonical_bytes, compile_files,
                               compile_references, strict_json, validate_bundle)

HERE = Path(__file__).resolve().parent
ORIGINAL_VALIDATOR = HERE.parent / 'evaluation-20261007/memory/validate.py'


def fixtures():
    bundle = {
        'schema': SOURCE_SCHEMA,
        'questions': [
            {'id': 'FRESH_A', 'prompt': 'What exact indented label is preserved?'},
            {'id': 'FRESH_B', 'prompt': 'What count was approved in this synthetic note?'},
        ],
        'corpus': {'SYNTH_A': 'Header\n\n  retained indentation\n\tcafé 雪\nlast\n',
                   'SYNTH_B': 'Approved count: 17.\n'},
    }
    refs = {'answers': [
        {'question_id': 'FRESH_A', 'answer': 'The indented label includes café 雪.',
         'citations': [{'doc_id': 'SYNTH_A', 'start_line': 2, 'end_line': 4}]},
        {'question_id': 'FRESH_B', 'answer': 'The approved count is 17.',
         'citations': [{'doc_id': 'SYNTH_B', 'start_line': 1, 'end_line': 1}]},
    ]}
    return bundle, refs


class CompilerTests(unittest.TestCase):
    def setUp(self):
        self.bundle, self.refs = fixtures()
        self.ids = [q['id'] for q in self.bundle['questions']]

    def compile(self, refs=None, bundle=None):
        bundle = self.bundle if bundle is None else bundle
        return compile_references(self.refs if refs is None else refs,
                                  [q['id'] for q in bundle['questions']], bundle['corpus'])

    def test_exact_quotes_preserve_blank_lines_indentation_and_unicode(self):
        before = copy.deepcopy((self.refs, self.bundle))
        result = self.compile()
        self.assertEqual(result['answers'][0]['citations'][0]['quote'],
                         '\n  retained indentation\n\tcafé 雪')
        self.assertEqual(result['answers'][1]['citations'][0]['quote'], 'Approved count: 17.')
        self.assertEqual((self.refs, self.bundle), before)
        self.assertEqual(result, self.compile())

    def test_original_validator_accepts_fresh_compiled_fixture_and_false_claim(self):
        before = ORIGINAL_VALIDATOR.read_bytes()
        spec = importlib.util.spec_from_file_location('unchanged_memory_validator', ORIGINAL_VALIDATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.check_responses(self.compile(), self.bundle['questions'], self.bundle['corpus'])
        false_refs = copy.deepcopy(self.refs)
        false_refs['answers'][1]['answer'] = 'The approved count is 999, not 17.'
        false_result = self.compile(false_refs)
        # A contradicted answer still passes BOTH mechanical checkers. Neither
        # copying quotes nor exact-quote validation establishes semantic support.
        module.check_responses(false_result, self.bundle['questions'], self.bundle['corpus'])
        self.assertEqual(false_result['answers'][1]['answer'], 'The approved count is 999, not 17.')
        self.assertEqual(ORIGINAL_VALIDATOR.read_bytes(), before)

    def test_missing_duplicate_unknown_and_out_of_order_questions_are_rejected(self):
        cases = []
        missing = copy.deepcopy(self.refs); missing['answers'].pop(); cases.append(missing)
        duplicate = copy.deepcopy(self.refs); duplicate['answers'][1] = copy.deepcopy(duplicate['answers'][0]); cases.append(duplicate)
        unknown = copy.deepcopy(self.refs); unknown['answers'][0]['question_id'] = 'UNSEEN'; cases.append(unknown)
        reordered = copy.deepcopy(self.refs); reordered['answers'].reverse(); cases.append(reordered)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.compile(value)

    def test_unknown_document_ids_are_never_treated_as_paths_or_urls(self):
        for doc_id in ('MISSING', '/etc/passwd', '../../outside', 'https://example.invalid/doc'):
            bad = copy.deepcopy(self.refs); bad['answers'][0]['citations'][0]['doc_id'] = doc_id
            with self.subTest(doc_id=doc_id), self.assertRaises(ValueError):
                self.compile(bad)

    def test_invalid_ranges_and_noninteger_bool_values_are_rejected(self):
        for start, end in [(0, 1), (-1, 1), (4, 3), (1, 6), (True, 2), (1, False),
                           (1.0, 2), (1, 2.0), ('1', 2), (None, 2), (1, float('inf'))]:
            bad = copy.deepcopy(self.refs)
            bad['answers'][0]['citations'][0].update(start_line=start, end_line=end)
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.compile(bad)

    def test_twenty_line_limit_is_inclusive(self):
        self.bundle['corpus']['SYNTH_A'] = '\n'.join(str(i) for i in range(30))
        self.refs['answers'][0]['citations'][0].update(start_line=1, end_line=20)
        self.assertEqual(len(self.compile()['answers'][0]['citations'][0]['quote'].splitlines()), 20)
        self.refs['answers'][0]['citations'][0]['end_line'] = 21
        with self.assertRaises(ValueError): self.compile()

    def test_empty_and_malformed_answers_or_citations_are_rejected(self):
        for field, value in [('answer', ''), ('answer', ' \t\n'), ('answer', None),
                             ('answer', 17), ('citations', []), ('citations', {}),
                             ('citations', [None]), ('question_id', [])]:
            bad = copy.deepcopy(self.refs); bad['answers'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.compile(bad)

    def test_extra_quote_and_unknown_fields_at_every_level_are_rejected(self):
        for target in ('root', 'answer', 'citation'):
            bad = copy.deepcopy(self.refs)
            obj = bad if target == 'root' else bad['answers'][0]
            if target == 'citation': obj = obj['citations'][0]
            obj['quote' if target == 'citation' else 'unexpected'] = 'do not repair this'
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.compile(bad)
        # Even a model-supplied quote that already matches is refused.
        bad = copy.deepcopy(self.refs)
        bad['answers'][1]['citations'][0]['quote'] = 'Approved count: 17.'
        with self.assertRaises(ValueError): self.compile(bad)

    def test_malformed_top_level_and_trusted_sources_are_rejected(self):
        for value in (None, [], {'answers': {}}, {}, {'answers': [None, None]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compile_references(value, self.ids, self.bundle['corpus'])
        for ids, corpus in [([], self.bundle['corpus']), (['A', 'A'], self.bundle['corpus']),
                            ([None], self.bundle['corpus']), (['A'], {}), (['A'], {'D': None})]:
            with self.subTest(ids=ids, corpus=corpus), self.assertRaises(ValueError):
                compile_references(self.refs, ids, corpus)
        for field, value in [('schema', 'wrong'), ('questions', []), ('corpus', [])]:
            bad = copy.deepcopy(self.bundle); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): validate_bundle(bad)
        bad = copy.deepcopy(self.bundle); bad['questions'][0]['answer_key'] = 'secret'
        with self.assertRaises(ValueError): validate_bundle(bad)

    def test_json_parser_rejects_syntax_duplicate_keys_nonfinite_and_invalid_utf8(self):
        for raw in (b'{', b'{"answers":[],"answers":[]}', b'{"x":NaN}', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError): strict_json(raw)

    def test_line_endings_match_original_validator_without_trimming_contents(self):
        self.bundle['corpus']['SYNTH_A'] = 'head\r\n\r\n  indent\r\n\tUnicode 雪\r\n'
        self.assertEqual(self.compile()['answers'][0]['citations'][0]['quote'], '\n  indent\n\tUnicode 雪')

    def test_cli_preserves_bytes_hashes_inputs_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='cited-recall-v2-control-') as directory:
            root = Path(directory)
            bundle = root / 'input-bundle.json'; raw = root / 'input-refs.json'; output = root / 'compiled'
            bundle_bytes = (' \r\n' + json.dumps(self.bundle, ensure_ascii=False, indent=3) + '\r\n').encode()
            raw_bytes = ('\t' + json.dumps(self.refs, ensure_ascii=False, indent=1) + ' \n').encode()
            bundle.write_bytes(bundle_bytes); raw.write_bytes(raw_bytes)
            command = [sys.executable, '-B', str(HERE / 'compile_citations.py'),
                       '--source-bundle', str(bundle), '--raw-refs', str(raw), '--out', str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads((output / 'receipt.json').read_text())
            self.assertEqual((output / 'raw-refs.json').read_bytes(), raw_bytes)
            self.assertEqual((output / 'source-bundle.json').read_bytes(), bundle_bytes)
            self.assertEqual(raw.read_bytes(), raw_bytes); self.assertEqual(bundle.read_bytes(), bundle_bytes)
            for field, data in [('raw_refs_sha256', raw_bytes), ('source_bundle_sha256', bundle_bytes),
                                ('questions_sha256', canonical_bytes(self.bundle['questions'])),
                                ('corpus_sha256', canonical_bytes(self.bundle['corpus'])),
                                ('compiler_sha256', (HERE / 'compile_citations.py').read_bytes()),
                                ('compiled_sha256', (output / 'compiled.json').read_bytes())]:
                self.assertEqual(receipt[field], hashlib.sha256(data).hexdigest())
            self.assertFalse(receipt['model_quality_result'])
            self.assertEqual(receipt['semantic_grading'], 'not-performed')
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            second = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(second.returncode, 2)
            self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, before)

    def test_rejected_refs_create_no_output_and_preserve_original_bytes(self):
        with tempfile.TemporaryDirectory(prefix='cited-recall-v2-refusal-') as directory:
            root = Path(directory); bundle = root / 'bundle.json'; raw = root / 'refs.json'
            bundle.write_text(json.dumps(self.bundle))
            raw_bytes = b'{"answers": [], "repair_me": true}\n'; raw.write_bytes(raw_bytes)
            with self.assertRaises(ValueError): compile_files(bundle, raw, root / 'output')
            self.assertFalse((root / 'output').exists())
            self.assertEqual(raw.read_bytes(), raw_bytes)


if __name__ == '__main__':
    unittest.main()
