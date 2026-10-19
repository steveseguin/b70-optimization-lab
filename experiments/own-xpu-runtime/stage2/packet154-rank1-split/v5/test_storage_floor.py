"""CPU regression for both screen admission sites and their storage helpers."""
import ast
import json
import types
import unittest
from unittest.mock import patch

import screen
from common import HERE, module


class StorageFloor(unittest.TestCase):
    def test_packet_write_budgets_and_boundaries(self):
        # Execute the actual two admission expressions without entering a device job.
        tree = ast.parse((HERE / 'screen.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'require'
                 and len(node.args) == 2 and isinstance(node.args[1], ast.Constant)
                 and node.args[1].value == 'bracket would breach 25 GB free-storage floor']
        self.assertEqual(len(calls), 2)
        storage = module('p154c_storage', HERE.parent / 'storage.py')
        for kind, expected in [('smoke', 145_000_000), ('bracket', 725_000_000)]:
            config = json.loads((HERE / 'configs' / ('split-' + kind + '.json')).read_text())
            planned = screen.WRITES['tp2'] * len(config['views'])
            self.assertEqual(planned, expected)
            self.assertLessEqual(planned, 3 * 243_000_000)
            for free, passes in [(29_700_000_000, True),
                                 (25_000_000_000 + planned, True),
                                 (25_000_000_000 + planned - 1, False)]:
                with self.subTest(kind=kind, free=free):
                    def admit():
                        with patch.object(screen.shutil, 'disk_usage',
                                          return_value=types.SimpleNamespace(free=free)):
                            row = screen.SUPPORT.storage(HERE / 'evidence', planned)
                            self.assertEqual(row['min_free_bytes'], 25_000_000_000)
                        return storage.budget(free, 100_000_000, planned, 0)
                    if passes:
                        admit()
                    else:
                        with self.assertRaises((ValueError, RuntimeError)):
                            admit()
                        with self.assertRaises(RuntimeError):
                            storage.budget(free, 100_000_000, planned, 0)
                    for call in calls:
                        with patch.object(screen.shutil, 'disk_usage',
                                          return_value=types.SimpleNamespace(free=free)):
                            code = compile(ast.Expression(call), 'screen.py', 'eval')
                            env = dict(shutil=screen.shutil, require=screen.require,
                                       planned_writes=planned)
                            if passes:
                                eval(code, env)
                            else:
                                with self.assertRaises(ValueError):
                                    eval(code, env)


if __name__ == '__main__':
    unittest.main()
