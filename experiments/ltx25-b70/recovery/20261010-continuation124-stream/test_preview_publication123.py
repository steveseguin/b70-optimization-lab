"""CPU regressions for packet123: real appending writer, strict reader and publication.

No HTTP listener, model, GPU, service or live directory is used.
"""
import asyncio
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

import session
import stream_preview as sp


class Publication123(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.final = Path(self.tmp.name) / 'preview_00001_.mp4'

    def appending_read(self, path):
        """Arrange a real writer append between read_regular's two identity checks."""
        append, done = threading.Event(), threading.Event()
        errors = []

        def writer():
            try:
                if not append.wait(3):
                    raise TimeoutError('reader did not start')
                with path.open('ab') as stream:
                    stream.write(b'-final')
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException as error:
                errors.append(error)
            finally:
                done.set()
        thread = threading.Thread(target=writer)
        thread.start()
        fdopen = os.fdopen
        calls = []

        class Reader:
            def __init__(self, *args, **kwargs):
                self.stream = fdopen(*args, **kwargs)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
            def fileno(self):
                return self.stream.fileno()
            def read(self, *args):
                raw = self.stream.read(*args)
                calls.append(True)
                if len(calls) == 1:
                    append.set()
                    if not done.wait(3):
                        raise TimeoutError('writer did not finish')
                return raw
        return thread, append, done, errors, Reader

    def run_appending(self, callback):
        self.final.write_bytes(b'first')
        thread, append, done, errors, reader = self.appending_read(self.final)
        try:
            with mock.patch.object(session.os, 'fdopen', reader):
                return callback()
        finally:
            append.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])

    def test_old_direct_writer_causes_identity_failure(self):
        # The inherited HTTP route's direct read raises: aiohttp turns it into 500.
        with self.assertRaisesRegex(RuntimeError, 'Evidence changed during read'):
            self.run_appending(lambda: session.read_regular(self.final))

    def test_pending_writer_race_retries_once_and_reads_complete_bytes(self):
        waits = []
        async def wait(seconds):
            waits.append(seconds)
        raw = self.run_appending(lambda: asyncio.run(sp.read_preview_record(
            session, self.final, writer_complete=lambda: False, wait=wait)))
        self.assertEqual(raw, b'first-final')
        self.assertEqual(waits, [0.05])

    def test_completed_file_mutation_still_fails_without_wait(self):
        async def wait(seconds):
            self.fail('completed evidence must not be retried')
        with self.assertRaisesRegex(RuntimeError, 'Evidence changed during read'):
            self.run_appending(lambda: asyncio.run(sp.read_preview_record(
                session, self.final, writer_complete=lambda: True, wait=wait)))

    def test_second_identity_failure_is_not_retried(self):
        waits = []
        async def wait(seconds):
            waits.append(seconds)
        with mock.patch.object(session, 'read_regular', side_effect=RuntimeError('Evidence changed during read')) as read:
            with self.assertRaisesRegex(RuntimeError, 'Evidence changed during read'):
                asyncio.run(sp.read_preview_record(session, self.final, writer_complete=lambda: False, wait=wait))
        self.assertEqual(read.call_count, 2)
        self.assertEqual(waits, [0.05])

    def test_linked_file_is_not_retried(self):
        self.final.write_bytes(b'payload')
        os.link(self.final, self.final.with_suffix('.link'))
        async def wait(seconds):
            self.fail('linked evidence must not be retried')
        with self.assertRaisesRegex(RuntimeError, 'Nonregular, linked or oversized evidence'):
            asyncio.run(sp.read_preview_record(session, self.final, writer_complete=lambda: False, wait=wait))

    def test_symlink_is_not_retried(self):
        target = self.final.with_suffix('.target')
        target.write_bytes(b'payload')
        self.final.symlink_to(target)
        async def wait(seconds):
            self.fail('unsafe evidence must not be retried')
        with self.assertRaisesRegex(RuntimeError, 'Unsafe evidence path'):
            asyncio.run(sp.read_preview_record(session, self.final, writer_complete=lambda: False, wait=wait))

    def test_temporary_writer_is_hidden_until_fsync_and_rename(self):
        partial = sp.temporary_name(self.final)
        ready, release = threading.Event(), threading.Event()
        errors = []
        def writer():
            try:
                with partial.open('xb') as stream:
                    stream.write(b'first')
                    stream.flush()
                    ready.set()
                    if not release.wait(3):
                        raise TimeoutError('reader did not release writer')
                    stream.write(b'-final')
                sp.publish_exclusive(partial, self.final)
            except BaseException as error:
                errors.append(error)
        thread = threading.Thread(target=writer)
        thread.start()
        try:
            self.assertTrue(ready.wait(3))
            self.assertFalse(self.final.exists())
            with self.assertRaises(FileNotFoundError):
                session.read_regular(self.final)
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(session.read_regular(self.final), b'first-final')
        self.assertEqual(self.final.stat().st_nlink, 1)
        self.assertFalse(partial.exists())

    def test_rename_publication_is_single_link_before_directory_fsync(self):
        partial = sp.temporary_name(self.final)
        partial.write_bytes(b'complete')
        observed = []
        def at_fsync(directory):
            observed.append(session.read_regular(self.final))
            self.assertEqual(self.final.stat().st_nlink, 1)
            self.assertFalse(partial.exists())
        with mock.patch.object(sp, '_fsync_dir', at_fsync):
            sp.publish_exclusive(partial, self.final)
        self.assertEqual(observed, [b'complete'])

    def test_atomic_json_is_canonical_and_hidden_before_rename(self):
        final = self.final.with_suffix('.json')
        value = {'preview': 'résumé', 'bytes': 8}
        expected = session.canonical(value) + b'\n'
        rename = sp._rename_exclusive
        observed = []
        def at_rename(tmp, destination):
            self.assertFalse(destination.exists())
            self.assertEqual(tmp.parent, destination.parent)
            observed.append(session.read_regular(tmp))
            rename(tmp, destination)
        with mock.patch.object(sp, '_rename_exclusive', at_rename):
            digest = sp.write_record_atomic(session, final, value)
        self.assertEqual(observed, [expected])
        self.assertEqual(session.read_regular(final), expected)
        self.assertEqual(digest, hashlib.sha256(expected).hexdigest())

    def test_atomic_json_refuses_existing_receipt(self):
        final = self.final.with_suffix('.json')
        final.write_bytes(b'original')
        with self.assertRaises(FileExistsError):
            sp.write_record_atomic(session, final, {'changed': True})
        self.assertEqual(session.read_regular(final), b'original')

    def test_empty_preview_never_published(self):
        partial = sp.temporary_name(self.final)
        partial.touch()
        with self.assertRaises(sp.PreviewFailure):
            sp.publish_exclusive(partial, self.final)
        self.assertFalse(self.final.exists())

    def test_runtime_publishes_preview_receipt_atomically_and_retries_only_preview(self):
        source = (Path(__file__).parent / 'integration.py').read_text()
        commit = source[source.index('    def _commit_preview('):source.index('    def _preview_failed(')]
        self.assertIn('stream_preview.write_record_atomic(', commit)
        self.assertNotIn('self.write(', commit)
        route = source[source.index('    def record_route('):source.index("    server.routes.get('/ltx-stream/receipt/")]
        self.assertIn('await stream_preview.read_preview_record(', route)
        self.assertIn("if prefix == 'preview-' else ctx.session.read_regular(path)", route)
        self.assertIn('writer_complete=lambda: ctx.preview.record(name) is not None', route)


if __name__ == '__main__':
    unittest.main()
