import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from memory_watchdog import (AVAILABLE_FLOOR, PRESSURE_LIMIT, MemoryWatchdog,
                             process_identity, sample_memory, trip_reason)


class WatchdogTests(unittest.TestCase):
    def test_thresholds_and_next_allocation(self):
        sample = {'accounted_pressure_bytes': PRESSURE_LIMIT-1,
                  'mem_available_bytes': AVAILABLE_FLOOR+1}
        self.assertIsNone(trip_reason(sample))
        self.assertIn('80 GB', trip_reason(sample, 1))
        sample['accounted_pressure_bytes'] = 0
        self.assertIn('32 GiB', trip_reason(sample, 1))
        with self.assertRaises(ValueError):
            trip_reason(sample, -1)

    def test_meminfo_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'meminfo'
            p.write_text('MemTotal: 100 kB\nMemAvailable: 60 kB\nCached: 30 kB\n')
            sample = sample_memory(p)
            self.assertEqual(sample['accounted_pressure_bytes'], 40*1024)
            self.assertEqual(sample['mem_available_bytes'], 60*1024)
            p.write_text('MemTotal: 100 kB\n')
            with self.assertRaises(KeyError): sample_memory(p)

    def test_trip_once_and_receipt(self):
        stops = []
        with tempfile.TemporaryDirectory() as tmp:
            w = MemoryWatchdog(tmp, stops.append, lambda: {
                'accounted_pressure_bytes': PRESSURE_LIMIT, 'mem_available_bytes': 40*2**30})
            w.check(); w.check()
            self.assertEqual(len(stops), 1)
            event = json.loads((Path(tmp)/'memory-watchdog-event.json').read_text())
            self.assertEqual(event['interval_seconds'], .25)
            self.assertGreater(event['controller']['starttime_ticks'], 0)
            self.assertEqual(len((Path(tmp)/'host-memory-samples.jsonl').read_text().splitlines()), 2)

    def test_read_failure_stops_once(self):
        def fail(): raise PermissionError('fixture')
        stops = []
        with tempfile.TemporaryDirectory() as tmp:
            w = MemoryWatchdog(tmp, stops.append, fail)
            w.check(); w.check()
            self.assertEqual(stops, ['host memory observation unavailable'])

    def test_receipt_failure_still_requests_stop(self):
        stops = []
        with tempfile.TemporaryDirectory() as tmp:
            w = MemoryWatchdog(tmp, stops.append, lambda: {
                'accounted_pressure_bytes': 0, 'mem_available_bytes': 40*2**30})
            with patch.object(Path, 'open', side_effect=OSError('disk full')):
                with self.assertRaises(OSError): w.check()
            self.assertEqual(stops, ['host memory receipt unavailable'])
            self.assertTrue(w.tripped.is_set())

    def test_thread_samples_and_stops(self):
        import threading
        called = threading.Event()
        with tempfile.TemporaryDirectory() as tmp:
            w = MemoryWatchdog(tmp, lambda why: called.set(), lambda: {
                'accounted_pressure_bytes': PRESSURE_LIMIT, 'mem_available_bytes': 40*2**30})
            w.start()
            self.assertTrue(called.wait(1))
            w.close()
            self.assertFalse(w.thread.is_alive())

if __name__ == '__main__': unittest.main()
