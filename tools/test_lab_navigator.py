"""CPU-only source integrity, retrieval and evidence export controls."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('navigator', Path(__file__).with_name('lab_navigator.py'))
N = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(N)


class NavigatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.repo = self.root / 'repo'; self.repo.mkdir()
        self.git('init', '-q'); self.git('config', 'user.email', 'fixture@example.invalid'); self.git('config', 'user.name', 'Fixture')
        sources = {'CURRENT.md': '# Current state\n\nNo server is running.\n\n## Historical\nOld server ran yesterday.\n',
                   'notes/negative.md': '# Crystal transport failure\n\n  Failure preserved.\n\nDo not repeat zirconium reset.\n',
                   'notes/empty.md': '', 'docs/newline.md': '# Unicode\r\n\tRésumé — preserved\r\n',
                   'experiments/example/evaluation/README.md': '# Secret answer key\nThe answer is 91.\n',
                   'experiments/example/results/answer.md': '# Answer fixture\nNever index this.\n',
                   'results/example/README.md': '# Qualified document\nThis title is not proof of current qualification.\n'}
        for path, data in sources.items():
            p = self.repo / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data.encode())
        (self.repo / 'notes/link.md').symlink_to('/not/a/readable/secret')
        self.git('add', '.'); self.git('commit', '-qm', 'fixture'); self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        self.index = self.root / 'index.sqlite'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE)

    def build(self):
        stats = types.SimpleNamespace(f_bavail=100 * 1024**3, f_frsize=1)
        with patch.object(N.os, 'statvfs', return_value=stats):
            return N.build(self.repo, self.commit, self.index)

    def test_pinned_blobs_ignore_ambient_edits_and_keys(self):
        (self.repo / 'notes/negative.md').write_text('Ambient falsehood only')
        (self.repo / 'notes/untracked.md').write_text('Another ambient falsehood')
        receipt = self.build(); db, meta = N.open_index(self.index)
        try:
            paths = {r[0] for r in db.execute('SELECT path FROM documents')}
            self.assertNotIn('notes/link.md', paths)
            self.assertNotIn('notes/untracked.md', paths)
            self.assertFalse(any('evaluation' in p or '/results/' in p for p in paths))
            self.assertTrue(any(x['path'] == 'notes/link.md' for x in meta['excluded']))
        finally: db.close()
        hits = N.search(self.index, 'zirconium')['hits']
        self.assertEqual(hits[0]['path'], 'notes/negative.md')
        self.assertIn('  Failure preserved.', hits[0]['text'])
        self.assertEqual(receipt['commit'], self.commit)

    def test_exact_pack_and_no_overwrite(self):
        self.build(); out = self.root / 'pack.json'; N.pack(self.index, 'zirconium', out)
        p = json.loads(out.read_text()); h = p['hits'][0]
        raw = self.git('show', self.commit + ':' + h['path'])
        self.assertEqual(h['text'], '\n'.join(raw.decode().splitlines()[h['start_line'] - 1:h['end_line']]))
        self.assertEqual(h['document_sha256'], N.sha(raw))
        self.assertEqual(h['passage_sha256'], N.sha(h['text'].encode()))
        with self.assertRaises(FileExistsError): N.pack(self.index, 'zirconium', out)

    def test_no_hits_never_invents_answer_or_pack(self):
        self.build(); out = self.root / 'missing.json'
        self.assertEqual(N.search(self.index, 'unfindabletoken')['hits'], [])
        with self.assertRaisesRegex(ValueError, 'No evidence'): N.pack(self.index, 'unfindabletoken', out)
        self.assertFalse(out.exists())

    def test_query_syntax_is_literal_and_prefix_is_bound(self):
        self.build()
        self.assertEqual(N.search(self.index, 'zirconium OR -- "', prefix='docs/')['hits'], [])
        with self.assertRaises(ValueError): N.search(self.index, 'zirconium', prefix='../')
        with self.assertRaises(ValueError): N.search(self.index, 'the and')

    def test_readonly_index_and_incomplete_index_rejected(self):
        self.build(); db, _ = N.open_index(self.index)
        try:
            with self.assertRaises(sqlite3.OperationalError): db.execute('DELETE FROM documents')
        finally: db.close()
        bad = self.root / 'bad.sqlite'; sqlite3.connect(bad).close()
        with self.assertRaises(sqlite3.Error): N.open_index(bad)

    def test_tampered_passage_refused_in_pack(self):
        self.build(); db = sqlite3.connect(self.index)
        db.execute("UPDATE passages SET text='false' WHERE path='notes/negative.md'"); db.commit(); db.close()
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            N.pack(self.index, 'zirconium', self.root / 'bad.json')

    def test_coherent_text_and_sha_tamper_cannot_retain_git_identity(self):
        self.build(); db = sqlite3.connect(self.index)
        raw = '# Crystal transport failure\n\nFalse source text.\n'
        digest = N.sha(raw.encode())
        db.execute("UPDATE documents SET text=?,sha256=? WHERE path='notes/negative.md'", (raw, digest))
        excerpt = '\n'.join(raw.splitlines())
        db.execute("UPDATE passages SET text=?,sha256=?,start_line=1,end_line=3 WHERE path='notes/negative.md'", (excerpt, N.sha(excerpt.encode())))
        db.commit(); db.close()
        with self.assertRaisesRegex(ValueError, 'Git blob binding mismatch'):
            N.pack(self.index, 'zirconium', self.root / 'false.json')
        self.assertFalse((self.root / 'false.json').exists())

    def test_policy_excludes_case_insensitive_evaluation_paths(self):
        for name in ['experiments/x/Review-Only/README.md', 'docs/Answers-Key.md',
                     'experiments/x/HOLDOUT/report.md', 'experiments/x/data/readme.md',
                     'worker/tasks/task.json', '.config/token', 'experiments/x/results/report.md']:
            self.assertFalse(N.eligible(name), name)
        self.assertTrue(N.eligible('results/example/README.md'))

    def test_chunks_cover_all_lines_and_respect_bound(self):
        text = '# First\n' + '\n'.join(f'line {i}' for i in range(200)) + '\n# Last\n\tfinal'
        seen = set()
        for first, last, heading, excerpt in N.chunks(text):
            seen.update(range(first, last + 1)); self.assertLessEqual(last - first + 1, 80)
            self.assertEqual(excerpt, '\n'.join(text.splitlines()[first - 1:last]))
        self.assertEqual(seen, set(range(1, len(text.splitlines()) + 1)))
        self.assertEqual(list(N.chunks('')), [])

    def test_unicode_crlf_preserved_and_qualification_not_inferred(self):
        self.build(); out = self.root / 'unicode.json'; N.pack(self.index, 'Résumé', out)
        self.assertIn('\tRésumé — preserved', json.loads(out.read_text())['hits'][0]['text'])
        db, meta = N.open_index(self.index)
        try: self.assertIs(meta['qualification_inferred'], False)
        finally: db.close()

    def test_low_space_refuses_before_index_creation(self):
        stats = types.SimpleNamespace(f_bavail=50 * 1024**3, f_frsize=1)
        with patch.object(N.os, 'statvfs', return_value=stats), self.assertRaisesRegex(ValueError, 'reserve'):
            N.build(self.repo, self.commit, self.index)
        self.assertFalse(self.index.exists())

    def test_existing_index_is_never_overwritten(self):
        self.index.write_text('keep')
        with self.assertRaises(ValueError): self.build()
        self.assertEqual(self.index.read_text(), 'keep')


if __name__ == '__main__': unittest.main()
