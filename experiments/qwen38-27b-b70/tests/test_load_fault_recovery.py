"""CPU check of the load-fault recogniser against the saved kernel records of 2026-10-04."""
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('lfr', HERE / 'scripts/load_fault_recovery.py')
lfr = importlib.util.module_from_spec(spec); spec.loader.exec_module(lfr)
SAVED = HERE / 'data/2026-10-04-fp8-multiuser/three-mtp5-s4-fault/kernel-fault-records-full.txt'
KILL = ('xe 0000:e3:00.0: [drm] Tile0: GT0: \n\tASID: 312\n\tFaulted Address: 0x00008156aa4c7000\n\tFaultType: 0\n'
        '\tAccessType: 0\n\tFaultLevel: 4\n\tEngineClass: 3 bcs\n\tEngineInstance: 0\n')


class RecoveryTest(unittest.TestCase):
    def test_saved_incident_is_the_known_fault(self):
        records = lfr.parse_records(SAVED.read_text())
        self.assertEqual(len(records), 27)
        self.assertTrue(lfr.is_known_load_fault(records))
        self.assertEqual(lfr.decide(False, records, 36, 36)[0], 'recover')

    def test_halts(self):
        records = lfr.parse_records(SAVED.read_text())
        self.assertEqual(lfr.decide(True, records, 36, 36)[0], 'halt')    # fault while serving
        self.assertEqual(lfr.decide(False, records, 36, 40)[0], 'halt')   # an earlier fault on this boot
        self.assertEqual(lfr.decide(False, [], 3, 3)[0], 'halt')          # fault lines but no page-fault record
        kill = lfr.parse_records(KILL)
        self.assertEqual(len(kill), 1)
        self.assertFalse(lfr.is_known_load_fault(kill))                   # the kill-time class is another address
        self.assertEqual(lfr.decide(False, records + kill, 37, 37)[0], 'halt')


if __name__ == '__main__':
    unittest.main()
