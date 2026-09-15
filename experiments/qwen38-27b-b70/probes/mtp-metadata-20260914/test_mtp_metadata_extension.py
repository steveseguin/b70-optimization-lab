"""CPU-only checks that research RPC results are plain JSON; no torch or GPU."""
import ast
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('mtp_transfer_worker_under_test', HERE / 'mtp_transfer_worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class PlainResultTests(unittest.TestCase):
    def test_plain_round_trips_and_refuses_objects(self):
        self.assertEqual(worker.plain({'a': [1, 'x', None, True]}), {'a': [1, 'x', None, True]})
        with self.assertRaises(TypeError):
            worker.plain({'torch_version': object()})

    def test_gate_reports_torch_version_as_text(self):
        tree = ast.parse((HERE / 'mtp_native_metadata_gate.py').read_text())
        values = [v for node in ast.walk(tree) if isinstance(node, ast.Dict)
                  for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant) and k.value == 'torch_version']
        self.assertEqual(len(values), 1)
        call = values[0]
        self.assertTrue(isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'str')

    def test_native_gate_rpc_returns_plain(self):
        tree = ast.parse((HERE / 'mtp_transfer_worker.py').read_text())
        gate = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'mtp_transfer_native_gate')
        returns = [n for n in ast.walk(gate) if isinstance(n, ast.Return)]
        self.assertTrue(returns and all(isinstance(r.value, ast.Call) and getattr(r.value.func, 'id', None) == 'plain' for r in returns))


if __name__ == '__main__':
    unittest.main()
