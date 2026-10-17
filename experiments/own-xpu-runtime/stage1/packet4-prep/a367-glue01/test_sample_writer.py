"""CPU-only sample persistence checks; no runtime imports or device access."""
from contextlib import contextmanager
import json
from pathlib import Path
import tempfile
import threading
import unittest

from sample_writer import SampleWriter


class SamplePersistence(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='a367-local-samples-')
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'samples.jsonl'

    def test_blocked_writer_does_not_delay_samples_and_drains_final_row(self):
        entered, release, sampled = threading.Event(), threading.Event(), threading.Event()

        @contextmanager
        def blocked_open(path):
            with path.open('x', encoding='utf-8') as real:
                class BlockedStream:
                    def write(self, value):
                        entered.set()
                        release.wait()
                        return real.write(value)

                    def flush(self):
                        real.flush()
                yield BlockedStream()

        writer = SampleWriter(self.path, open_file=blocked_open)
        rows = [{'phase': 'baseline', 'monotonic': 0}]
        writer.start()
        writer.enqueue(rows[0])
        producer = None
        try:
            self.assertTrue(entered.wait(2), 'writer did not reach blocked write')

            def take_samples():
                for i in range(1, 1001):
                    row = {'phase': 'sampling', 'monotonic': i * .5}
                    rows.append(row)
                    writer.enqueue(row)
                final = {'phase': 'shutdown', 'monotonic': 500.5}
                rows.append(final)
                writer.enqueue(final)
                sampled.set()

            producer = threading.Thread(target=take_samples, daemon=True)
            producer.start()
            self.assertTrue(sampled.wait(2), 'sample production waited for blocked file I/O')
            self.assertFalse(release.is_set())
            self.assertEqual(writer.written_rows, 0)
        finally:
            release.set()
            if producer is not None:
                producer.join(2)
            writer.finish()
        self.assertEqual(self.path.read_text(), ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
        self.assertEqual(writer.written_rows, len(rows))
        self.assertEqual(json.loads(self.path.read_text().splitlines()[-1]), rows[-1])

    def test_empty_file_and_idempotent_finish(self):
        writer = SampleWriter(self.path)
        writer.start()
        writer.finish()
        writer.finish()
        self.assertEqual(self.path.read_bytes(), b'')
        with self.assertRaisesRegex(RuntimeError, 'already finished'):
            writer.enqueue({})

    def test_file_errors_are_reported_after_join(self):
        def fail_open(path):
            raise OSError('test full local disk')
        writer = SampleWriter(self.path, open_file=fail_open)
        writer.start()
        writer.enqueue({'phase': 'baseline'})
        with self.assertRaisesRegex(RuntimeError, 'test full local disk'):
            writer.finish()
        self.assertIsInstance(writer.failure, OSError)
        self.assertFalse(writer.thread.is_alive())

    def test_serialization_failure_is_reported(self):
        writer = SampleWriter(self.path)
        writer.start()
        writer.enqueue({'monotonic': float('nan')})
        with self.assertRaisesRegex(RuntimeError, 'local sample writer failed'):
            writer.finish()
        self.assertEqual(writer.written_rows, 0)


if __name__ == '__main__':
    unittest.main()
