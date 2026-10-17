#!/usr/bin/env python3
"""Small CPU-only admission and complete-grid summary tests; no native launch."""
import json
from pathlib import Path
import tempfile
import unittest
import summarize
import window

class Tests(unittest.TestCase):
    def test_selected_card_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            info = root / '42/fdinfo/8'
            info.parent.mkdir(parents=True)
            info.write_text('drm-driver: xe\ndrm-pdev: 0000:23:00.0\n')
            self.assertEqual(len(window.selected_clients(2, root)['other_card_clients']), 1)
            info.write_text('drm-driver: xe\ndrm-pdev: 0000:43:00.0\n')
            with self.assertRaises(ValueError): window.selected_clients(2, root)
            self.assertEqual(len(window.selected_clients(3, root)['other_card_clients']), 1)
            info.write_text('drm-driver: xe\n')
            with self.assertRaises(ValueError): window.selected_clients(3, root)

    def test_memory_fence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for n in range(53, 58):
                path = root / ('memory' + str(n)) / 'state'
                path.parent.mkdir()
                path.write_text('offline\n')
            self.assertEqual(len(window.memory_fence(root)), 5)
            path.write_text('online\n')
            with self.assertRaises(ValueError): window.memory_fence(root)

    def test_complete_grid_and_negative_overlap(self):
        rows = []
        for slab in (1971200, 2329600):
            for batch in range(4, 11):
                for shape in ('contiguous_batch', 'slab_commands'):
                    for iteration in range(-3, 30):
                        for mode, wall, copy, comp in [('copy', 10000, 8000, 0), ('compute', 20000, 0, 18000), ('concurrent', 32000, 12000, 19000)]:
                            rows.append(dict(slab_bytes=slab, batch=batch, copy_shape=shape,
                                iteration=iteration, warmup=iteration<0, mode=mode,
                                wall_ns=wall, copy_device_envelope_ns=copy, compute_event_ns=comp,
                                route_to_resident_ns=wall, payload_verified=True))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'receipt.json').write_text(json.dumps(dict(passed=True,safe_to_exit=True,rows=len(rows))))
            (root / 'metadata.json').write_text('{}')
            path = root / 'iterations.jsonl'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            summary = summarize.summarize(root)
            self.assertEqual(len(summary['rows']), 28)
            self.assertEqual(summary['rows'][0]['effective_overlap_fraction'], -0.2)
            self.assertEqual(summary['rows'][0]['envelope_overlap_lower_bound_us'], 0)
            rows[1] = rows[0]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaises(ValueError): summarize.summarize(root)

if __name__ == '__main__':
    unittest.main()
