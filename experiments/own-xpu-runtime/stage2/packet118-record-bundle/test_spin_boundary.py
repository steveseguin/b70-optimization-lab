"""Pure CPU regression checks for exit_mm and spin provenance boundaries."""
import json
from pathlib import Path
import unittest

import p56_head_support as support


class ExitMemoryTests(unittest.TestCase):
    def test_pf_exiting_is_required_for_live_task_without_rss(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            root = proc / '123'
            task = root / 'task/123'
            task.mkdir(parents=True)
            (task / 'children').write_text('124')
            (root / 'status').write_text('State:\tS (sleeping)\nRssAnon:\t12 kB\n')
            child = proc / '124'
            child.mkdir()
            (child / 'status').write_text('State:\tR (running)\n')
            # Field 9, after a comm containing spaces and parentheses.
            (child / 'stat').write_text('124 (native (worker)) R 1 1 1 0 0 4\n')
            result = support.process_tree_anon(123, proc)
            self.assertEqual(result['anonymous_bytes'], 12 * 1024)
            self.assertTrue(result['root_seen'])
            (child / 'stat').write_text('124 (native (worker)) R 1 1 1 0 0 0\n')
            with self.assertRaisesRegex(ValueError, 'missing/malformed RssAnon'):
                support.process_tree_anon(123, proc)
            (child / 'status').write_text('State:\tZ (zombie)\n')
            self.assertEqual(support.process_tree_anon(123, proc)['anonymous_bytes'], 12 * 1024)


if __name__ == '__main__':
    unittest.main()
