"""Adversarial clock, continuity and receipt-integrity checks; no device work."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import analyze as a


def event(i, start, end, *, fixture=10, label='blk.0.hc.a.norm',
          queue='compute', speculative=True, position=80):
    return dict(event=i, start_ns=start, end_ns=end, fixture=fixture,
                position=position, label=label, queue=queue,
                queue_kind='compute' if queue == 'compute' else 'copy',
                speculative=speculative)


class ClockTests(unittest.TestCase):
    def test_copy_clock_never_enters_compute_gap(self):
        left, right = event(1, 100, 200), event(3, 250, 300)
        for start, end in ((1, 1), (10**15, 10**15+10**12)):
            with self.subTest(start=start):
                copy_event = event(2, start, end, queue='copy-auto', label='transfer.upload')
                gaps, missing = a.compute_gaps([right, copy_event, left])
                self.assertEqual(missing, 0)
                self.assertEqual([g['ms'] for g in gaps], [50/1e6])

    def test_missing_event_id_breaks_continuity(self):
        gaps, missing = a.compute_gaps([event(1, 100, 200), event(3, 500, 600)])
        self.assertEqual((gaps, missing), ([], 1))

    def test_fixture_boundary_is_not_idle(self):
        gaps, missing = a.compute_gaps([event(1, 100, 200), event(2, 500, 600, fixture=11)])
        self.assertEqual((gaps, missing), ([], 1))

    def test_nested_compute_intervals_use_union_frontier(self):
        gaps, missing = a.compute_gaps([event(1, 100, 500), event(2, 200, 250),
                                       event(3, 400, 450), event(4, 520, 600)])
        self.assertEqual(missing, 0)
        self.assertEqual([g['ms'] for g in gaps], [0, 0, 20/1e6])

    def test_duplicate_id_refuses(self):
        with self.assertRaisesRegex(AssertionError, 'duplicate event'):
            a.compute_gaps([event(1, 100, 200), event(1, 300, 400)])

    def test_zero_duration_compute_refuses(self):
        with self.assertRaises(AssertionError):
            a.compute_gaps([event(1, 100, 100)])

    def test_gap_after_omission_does_not_keep_old_frontier(self):
        gaps, missing = a.compute_gaps([event(1, 1000, 2000), event(3, 100, 200),
                                       event(4, 250, 300)])
        self.assertEqual(missing, 1)
        self.assertEqual([g['ms'] for g in gaps], [50/1e6])

    def test_draft_overlap_is_clipped_union_not_sum(self):
        self.assertEqual(a.overlap_ns(100, 500, [(10, 200), (150, 300), (400, 600)]), 300)
        self.assertEqual(a.overlap_ns(100, 500, [(1, 99), (500, 600)]), 0)

    def test_semantic_head_position_shift(self):
        for label in ('head.suffix', 'transfer.head.hidden-import', 'wait.head.hidden'):
            with self.subTest(label=label):
                self.assertEqual(a.cycle_position(event(1, 100, 200, label=label)), 81)
        self.assertEqual(a.cycle_position(event(1, 100, 200)), 80)

    def test_snapshot_and_rollback_do_not_become_enqueue_gaps(self):
        for label, category in [('snapshot.capture.flat', 'snapshot_to_speculative_begin'),
                                ('rollback.restore.flat', 'restore_to_correction_begin')]:
            with self.subTest(label=label):
                gaps, missing = a.compute_gaps([event(1, 100, 200, label=label),
                                               event(2, 500, 600, label='begin.0')])
                self.assertEqual(missing, 0)
                self.assertEqual(gaps[0]['kind'], category)

    def test_command_match_uses_rank0_host_clock(self):
        e = dict(end_ns=1_000_010_000)
        local = dict(rank=0, rank_received=1.000009)
        closer_peer = dict(rank=1, rank_received=1.000010)
        self.assertIs(a.command_for_gap(e, [closer_peer, local]), local)
        with self.assertRaisesRegex(AssertionError, 'ambiguous command'):
            a.command_for_gap(e, [dict(rank=0, rank_received=0.1)])


class IntegrityTests(unittest.TestCase):
    def test_mutated_input_and_changed_symlink_refuse(self):
        with tempfile.TemporaryDirectory(prefix='packet134-integrity-') as tmp:
            root = Path(tmp)
            packet = root/'packet134'
            parent = root/'packet124c-record-bundle'
            packet.mkdir()
            parent.mkdir()
            source = root/'source.txt'
            source.write_text('retained receipt\n')
            link = parent/'oracle'
            link.symlink_to('../source.txt')
            a.save(packet/'input-pins.json', dict(files={'source.txt': a.sha(source)},
                parent_symlinks={'oracle': '../source.txt'}))
            with mock.patch.object(a, 'P', packet), mock.patch.object(a, 'ROOT', root):
                a.verify_inputs()
                source.write_text('changed receipt\n')
                with self.assertRaisesRegex(AssertionError, 'input identity changed'):
                    a.verify_inputs()
                source.write_text('retained receipt\n')
                link.unlink()
                link.symlink_to('../different.txt')
                with self.assertRaisesRegex(AssertionError, 'parent links changed'):
                    a.verify_inputs()

    def test_full_receipts_reproduce_saved_result(self):
        self.assertEqual(a.generate(), a.read(a.P/'evidence/attribution.json'))

    def test_missing_correction_receipt_refuses(self):
        original = a.rows
        removed = []

        def omit(path):
            values = original(path)
            if Path(path).name == 'timings.jsonl' and not removed:
                for index, row in enumerate(values):
                    if 10 <= row['fixture'] <= 16 and not row['speculative']:
                        removed.append(row)
                        return values[:index]+values[index+1:]
            return values

        with mock.patch.object(a, 'rows', side_effect=omit):
            with self.assertRaises(AssertionError):
                a.generate()
        self.assertEqual(len(removed), 1)

    def test_claiming_overhead_pass_refuses(self):
        original = a.read

        def wrong(path):
            value = original(path)
            if Path(path) == a.BASE/'evidence/budget.json':
                value = copy.deepcopy(value)
                value['summary']['overhead_bounded'] = True
            return value

        with mock.patch.object(a, 'read', side_effect=wrong):
            with self.assertRaises(AssertionError):
                a.generate()

    def test_imports_do_not_install_resource_limits(self):
        # This is a source contract for the analysis entrypoints only. No native
        # launch limit is changed or tested by importing the frozen runtime.
        import ast
        for name in ('analyze.py', 'test_analysis.py', 'validate.py', 'seal.py'):
            tree = ast.parse((a.P/name).read_text())
            for statement in tree.body:
                if isinstance(statement, ast.If) and '__name__' in ast.unparse(statement.test):
                    continue
                if isinstance(statement, (ast.FunctionDef, ast.ClassDef)):
                    continue
                self.assertNotIn('setrlimit', ast.unparse(statement))


if __name__ == '__main__':
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    unittest.main()
