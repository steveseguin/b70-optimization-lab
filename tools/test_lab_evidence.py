"""Independent synthetic CPU controls for pinned-source reading/review packs."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
with patch.object(sys, 'path', [str(TOOLS), *sys.path]):
    SPEC = importlib.util.spec_from_file_location('evidence_under_test', TOOLS / 'lab_evidence.py')
    E = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(E)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / 'repo'; self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.name', 'Synthetic fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        long = ['# Long source'] + [f'ordinary line {i}: ' + 'preserved source ' * 4 for i in range(170)]
        long[100] = 'zirconiumlong unique original evidence'
        self.raw = {
            'AGENTS.md': ('# Policies\n' + ''.join(f'Rule {i}\n' for i in range(220))).encode(),
            'AGENT_HANDOFF.md': b'# Handoff\nRead the recorded state and complete applicable policies.\n',
            'CURRENT.md': ('# Current snapshot\n' + ''.join(f'Recorded state line {i}\n' for i in range(220))).encode(),
            'notes/short.md': b'# Small evidence\n\nzirconiumshort original claim.\n',
            'notes/other.md': b'# Other document\nThis is a distinct source blob.\n',
            'notes/long.md': ('\n'.join(long) + '\n').encode(),
            'docs/exact.md': '# UTF-8\r\n\tRésumé — preserved\r\nEOF without newline'.encode(),
            'docs/fences.md': b'# Real heading\n```python\n# Not a heading\n```\n  ~~~~\n## Also code\n  ~~~~\n## Child heading\nend\n',
            'notes/empty.md': b'',
            'experiments/example/evaluation/README.md': b'# Never retrieve synthetic answer key\n',
            'SUDOPASSWORD.txt': b'synthetic fixture only\n',
            '.config/token': b'synthetic fixture only\n',
        }
        for path, raw in self.raw.items():
            target = self.repo / path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
        (self.repo / 'notes/link.md').symlink_to('/nonexistent/synthetic-secret')
        self.commit_all()
        self.index = self.root / 'index.sqlite'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE)

    def commit_all(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'synthetic fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()

    def build(self):
        # Only storage availability is synthetic; Git, SQLite and byte checks are real.
        with patch.object(E.nav.os, 'statvfs', return_value=types.SimpleNamespace(f_bavail=100 * 1024**3, f_frsize=1)):
            E.nav.build(self.repo, self.commit, self.index)

    def read(self, path='notes/short.md', **kwargs):
        return E.read_source(self.index, self.repo, path, **kwargs)

    def review(self, query='zirconiumshort', name='review.json', **kwargs):
        out = self.root / name
        summary = E.review(self.index, self.repo, query, out, **kwargs)
        result = json.loads(out.read_bytes())
        self.assertEqual(summary['sha256'], hashlib.sha256(out.read_bytes()).hexdigest())
        return result

    def assert_coverage(self, doc):
        seen = set()
        for part in doc['excerpts'] + doc['omitted_ranges']:
            lines = set(range(part['start_line'], part['end_line'] + 1))
            self.assertFalse(seen & lines)
            seen |= lines
        self.assertEqual(seen, set(range(1, doc['line_count'] + 1)))

    def test_dirty_worktree_reads_pinned_bytes_and_real_tree_identity(self):
        self.build()
        (self.repo / 'notes/short.md').write_text('Uncommitted contradictory claim')
        (self.repo / 'notes/untracked.md').write_text('Never index ambient bytes')
        result = self.read()
        self.assertEqual(result['excerpts'][0]['text'].encode(), self.raw['notes/short.md'])
        identity = result['repository']
        self.assertTrue(identity['worktree_dirty'])
        self.assertTrue(identity['index_at_head'])
        self.assertEqual(identity['git_tree_oid'], self.git('rev-parse', self.commit + '^{tree}').decode().strip())
        self.assertIsNotNone(datetime.datetime.fromisoformat(identity['observed_at_utc']).tzinfo)
        self.assertFalse(identity['live_host_state_verified'])

    def test_stale_head_refused_until_explicit_override(self):
        self.build(); original = self.commit
        (self.repo / 'notes/short.md').write_text('New committed evidence')
        self.commit_all()
        with self.assertRaisesRegex(ValueError, 'HEAD'):
            self.read()
        with self.assertRaisesRegex(ValueError, 'HEAD'):
            self.review()
        self.assertFalse((self.root / 'review.json').exists())
        result = self.read(allow_stale=True)
        self.assertEqual(result['document']['commit'], original)
        self.assertEqual(result['excerpts'][0]['text'].encode(), self.raw['notes/short.md'])
        self.assertTrue(result['repository']['stale_use_explicit'])
        self.assertFalse(result['repository']['index_at_head'])

    def test_forged_index_commit_cannot_rebind_an_old_real_blob(self):
        self.build()
        (self.repo / 'notes/short.md').write_text('Different actual Git tree content')
        self.commit_all()
        with sqlite3.connect(self.index) as db:
            db.execute('UPDATE metadata SET value=? WHERE key=?', (json.dumps(self.commit), 'commit'))
        with self.assertRaisesRegex(ValueError, 'Git tree'):
            self.read()

    def test_coherent_path_blob_and_text_swap_rejected_by_git_mapping(self):
        self.build()
        with sqlite3.connect(self.index) as db:
            row = db.execute('SELECT blob,sha256,bytes,text FROM documents WHERE path=?', ('notes/short.md',)).fetchone()
            db.execute('UPDATE documents SET blob=?,sha256=?,bytes=?,text=? WHERE path=?', (*row, 'notes/other.md'))
        with self.assertRaisesRegex(ValueError, 'Git tree'):
            self.read('notes/other.md')

    def test_exact_utf8_crlf_and_unterminated_eof_with_byte_budget(self):
        self.build(); raw = self.raw['docs/exact.md']
        full = self.read('docs/exact.md', max_bytes=len(raw))
        self.assertEqual(full['excerpts'][0]['text'].encode(), raw)
        self.assertEqual(full['excerpts'][0]['text_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(full['excerpts'][0]['text_bytes'], len(raw))
        self.assertTrue(full['full_document_included'])
        part = self.read('docs/exact.md', start=2, end=2)['excerpts'][0]
        self.assertEqual(part['text'], '\tRésumé — preserved\r\n')
        self.assertTrue(part['continues_before']); self.assertTrue(part['continues_after'])
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.read('docs/exact.md', max_bytes=len(raw) - 1)
        review = self.review('Résumé', prefix='docs/', name='unicode-review.json')
        self.assertEqual(review['documents'][0]['excerpts'][0]['text'].encode(), raw)

    def test_fenced_headings_are_not_outline_or_section_authority(self):
        self.build()
        result = self.read('docs/fences.md', start=9, end=9)
        self.assertEqual([(x['line'], x['title']) for x in result['outline']], [(1, 'Real heading'), (8, 'Child heading')])
        self.assertEqual([x['title'] for x in result['excerpts'][0]['section_heading_path']], ['Real heading', 'Child heading'])

    def test_whole_document_admitted_at_exact_text_budget(self):
        self.build(); raw = self.raw['notes/short.md']
        result = self.review(source_bytes=len(raw), authority_bytes=0)
        doc = result['documents'][0]
        self.assertTrue(doc['full_document_included'])
        self.assertEqual(doc['excerpts'][0]['text'].encode(), raw)
        self.assertEqual(result['budget']['source_used'], len(raw))
        self.assertFalse(result['obligations_complete']); self.assertFalse(result['authority_complete'])
        self.assert_coverage(doc)

    def test_snippet_fallback_and_omissions_cover_entire_long_source(self):
        self.build()
        hit = E.nav.search(self.index, 'zirconiumlong', limit=1)['hits'][0]
        lines = self.raw['notes/long.md'].decode().splitlines(keepends=True)
        expected = ''.join(lines[hit['start_line'] - 1:hit['end_line']]).encode()
        self.assertLess(len(expected), len(self.raw['notes/long.md']))
        result = self.review('zirconiumlong', limit=1, source_bytes=len(expected), authority_bytes=0)
        doc = result['documents'][0]
        self.assertFalse(doc['full_document_included'])
        self.assertEqual(doc['excerpts'][0]['text'].encode(), expected)
        self.assertTrue(doc['omission_reason'])
        self.assertEqual(result['budget']['source_used'], len(expected))
        self.assert_coverage(doc)

    def test_authorities_full_policy_and_handoff_current_preview_separate_budget(self):
        self.build()
        result = self.review(source_bytes=0)
        authorities = {d['path']: d for d in result['authority_context']}
        for path in ('AGENTS.md', 'AGENT_HANDOFF.md'):
            self.assertTrue(authorities[path]['full_document_included'])
            self.assertEqual(authorities[path]['excerpts'][0]['text'].encode(), self.raw[path])
        current = authorities['CURRENT.md']
        self.assertEqual(current['excerpts'][0]['end_line'], 200)
        self.assertFalse(current['full_document_included'])
        self.assertEqual(current['omitted_ranges'], [{'start_line': 201, 'end_line': 221}])
        self.assertFalse(result['authority_complete'])
        self.assertEqual(result['budget']['source_used'], 0)
        self.assertGreater(result['budget']['authority_used'], 0)
        for doc in authorities.values(): self.assert_coverage(doc)

    def test_missing_authorities_and_no_hits_never_claim_completeness(self):
        for path in ('AGENTS.md', 'AGENT_HANDOFF.md'): (self.repo / path).unlink()
        self.commit_all(); self.build()
        result = self.review('unfindableevidenceword')
        self.assertEqual(result['status'], 'no_match')
        self.assertEqual(result['documents'], []); self.assertEqual(result['returned_top_k'], 0)
        self.assertFalse(result['authority_complete']); self.assertFalse(result['obligations_complete'])
        self.assertFalse(result['live_state_verified'])
        self.assertEqual(result['semantic_grading'], 'not-performed')
        missing = [d['path'] for d in result['authority_context'] if d.get('status') == 'not-indexed']
        self.assertEqual(missing, ['AGENTS.md', 'AGENT_HANDOFF.md'])

    def test_bad_ranges_and_noninteger_budgets_are_rejected(self):
        self.build()
        for start, end in [(0, 1), (3, 2), (1, 999), (True, 2), (1, False)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.read(start=start, end=end)
        for budget in (-1, True, 1.5, '100', None, 4 * 1024**2 + 1):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                self.read(max_bytes=budget)

    def test_nonregular_secret_and_excluded_sources_are_refused(self):
        self.build()
        for path in ('SUDOPASSWORD.txt', '.config/token', 'experiments/example/evaluation/README.md', '../notes/short.md', str(self.repo / 'notes/short.md')):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.read(path)
        # A forged coherent index row still cannot make a Git symlink regular.
        target = self.git('show', self.commit + ':notes/link.md')
        oid = self.git('rev-parse', self.commit + ':notes/link.md').decode().strip()
        with sqlite3.connect(self.index) as db:
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)', ('notes/link.md', oid, E.nav.sha(target), len(target), 'link', 'dated-research-note', target.decode()))
        with self.assertRaisesRegex(ValueError, 'regular file'):
            self.read('notes/link.md')

    def test_zero_budgets_explicit_omissions_and_empty_source(self):
        self.build()
        result = self.review(source_bytes=0, authority_bytes=0)
        self.assertEqual(result['budget']['source_used'], 0)
        self.assertEqual(result['budget']['authority_used'], 0)
        for doc in result['documents'] + result['authority_context']:
            self.assertEqual(doc['excerpts'], [])
            self.assertFalse(doc['full_document_included'])
            self.assert_coverage(doc)
        self.assertTrue(self.read('notes/empty.md', max_bytes=0)['full_document_included'])
        outline = self.read(max_bytes=0, outline_only=True)
        self.assertEqual(outline['excerpts'], []); self.assertTrue(outline['outline'])
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.read(max_bytes=0)

    def test_output_overwrite_and_duplicate_explicit_selection_refused(self):
        self.build()
        out = self.root / 'review.json'; out.write_bytes(b'preserve existing review')
        with self.assertRaises(FileExistsError):
            E.review(self.index, self.repo, 'zirconiumshort', out)
        self.assertEqual(out.read_bytes(), b'preserve existing review')
        new = self.root / 'duplicate.json'
        with self.assertRaisesRegex(ValueError, 'unique'):
            E.review(self.index, self.repo, 'zirconiumshort', new, include=['notes/short.md'] * 2)
        self.assertFalse(new.exists())

    def test_serialized_cap_applies_to_outline_and_refuses_review_before_write(self):
        self.build()
        out = self.root / 'oversized-review.json'
        with patch.object(E, 'MAX_OUTPUT_BYTES', 64):
            with self.assertRaisesRegex(ValueError, 'serialized output bound'):
                self.read(max_bytes=0, outline_only=True)
            with self.assertRaisesRegex(ValueError, 'serialized output bound'):
                E.review(self.index, self.repo, 'zirconiumshort', out,
                         source_bytes=0, authority_bytes=0)
        self.assertFalse(out.exists())

    def test_serialized_cap_counts_utf8_and_final_newline_at_exact_boundary(self):
        value = {'text': 'é'}
        exact_bytes = len('{\n  "text": "é"\n}\n'.encode('utf-8'))
        with patch.object(E, 'MAX_OUTPUT_BYTES', exact_bytes):
            E.check_output(value)
        # Without the final newline this would fit; the emitted JSON must not.
        with patch.object(E, 'MAX_OUTPUT_BYTES', exact_bytes - 1):
            with self.assertRaisesRegex(ValueError, 'serialized output bound'):
                E.check_output(value)


if __name__ == '__main__':
    unittest.main()
