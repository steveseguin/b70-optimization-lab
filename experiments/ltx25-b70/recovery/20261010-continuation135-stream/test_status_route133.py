"""Execute packet133's actual async status handler without a listener or device.

AST extraction removes only its registration decorator. The handler body,
including the advertised feature map and oracle fields, is executed unchanged.
The route has no await; driving its coroutine once avoids creating an event
loop (and the loop's socketpair). No integration/runtime module is imported.
"""
import ast
import copy
import json
from pathlib import Path
import time
from types import SimpleNamespace as NS
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
AUTHOR = (HERE if (HERE/'integration.py').is_file() else
          Path('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261010-continuation135-stream'))


def status_handler(ctx):
    path = AUTHOR/'integration.py'
    source = path.read_text()
    tree = ast.parse(source, str(path))
    routes = [node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)
              and node.name == 'status']
    if len(routes) != 1:
        raise AssertionError('Expected exactly one actual async status route')
    route = copy.deepcopy(routes[0])
    route.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[]))
    namespace = dict(ctx=ctx, time=time, contract=NS(PACKET=135),
                     web=NS(json_response=lambda body, **kwargs: NS(
                         body=json.dumps(body).encode(), status=kwargs.get('status', 200))))
    exec(compile(module, str(path), 'exec'), namespace)
    return namespace['status']


def oracle_sha():
    tree = ast.parse((AUTHOR/'text_residency133.py').read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
                target.id == 'ORACLE_SHA256' for target in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError('The actual helper must declare its oracle identity')


class StatusRoute133(unittest.TestCase):
    def check_mode(self, mode):
        oracle = oracle_sha() if mode == 'split36' else None
        worker = NS(summary=lambda: {})
        timings = []
        ctx = NS(action_busy=False, authority=NS(status=lambda: {'phase': 'stream'}, qid='qid'),
            identity_sha='identity', manifest_sha='manifest', session=NS(PLAN_SHA256='a'*64),
            frames=145, anchor='frame', decoder_graph_flag=1 if mode == 'split36' else 0,
            anchor_decode='cone', bencode_overlap=1, prep_ahead=1, snapshot_mode='fingerprint',
            pool_cap=None, text_residency=mode, display_device='xpu:3',
            display_schedule='eager-display' if mode == 'split36' else 'sampler-a',
            anchor_read_ahead=0, snapshot_schedule='full', fault=lambda: False,
            run=Path('/unused-status-route133'), root=Path('/unused-status-route133'),
            qualified_windows=[64], decoder_graph=None, cone=None, precompute=worker,
            inspector=worker, display_worker='serial', decoder=worker, preview=worker,
            server_options=dict(text_residency=mode, text_oracle_sha256=oracle),
            storage_check=lambda **kwargs: {}, note_status_route=timings.append)
        handler = status_handler(ctx)
        maintenance = NS(snapshot=lambda: {})
        with mock.patch.dict('sys.modules', {'maintenance125': maintenance, 'maintenance128': maintenance}):
            coroutine = handler(NS())
            try:
                coroutine.send(None)
            except StopIteration as done:
                response = done.value
            else:
                self.fail('Status route unexpectedly awaits; fixture must explicitly model the new dependency')
            finally:
                coroutine.close()
        self.assertEqual(response.status, 200)
        status = json.loads(response.body)
        self.assertEqual(status['packet'], 135)
        self.assertEqual(status['text_residency'], mode)
        self.assertIn('text_oracle_sha256', status)
        self.assertEqual(status['text_oracle_sha256'], oracle)
        self.assertEqual(len(timings), 1)
        self.assertIs(status['features'].get('text_residency'), True,
                      'Actual status must advertise the feature required by the packet133 client')

    def test_legacy_status_advertises_residency_and_null_oracle(self):
        self.check_mode('legacy')

    def test_split36_status_advertises_residency_and_pinned_oracle(self):
        self.check_mode('split36')


if __name__ == '__main__':
    unittest.main(verbosity=2)
