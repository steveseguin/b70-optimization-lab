import functools
import importlib.util
from pathlib import Path
import sys
import queue
import threading
import types
import unittest

HERE = Path(__file__).resolve().parent
def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
O = load('tested_observer', 'runtime_observer.py')
S = load('tested_observer_session', 'session.py')


def owner(class_name, method, **extra):
    namespace = {'__file__': 'actual/custom_node/__init__.py', **extra}
    exec('class ' + class_name + ':\n    def ' + method + '(self): pass\n', namespace)
    cls = namespace[class_name]
    namespace['NODE_CLASS_MAPPINGS'] = {class_name: cls}
    return cls, namespace


class ObserverControls(unittest.TestCase):
    def setUp(self):
        self.old = sys.modules.get('ltx_resolution_session')
        sys.modules['ltx_resolution_session'] = S

    def tearDown(self):
        if self.old is None:
            sys.modules.pop('ltx_resolution_session', None)
        else:
            sys.modules['ltx_resolution_session'] = self.old

    def test_uses_registered_owner_through_actual_decorator(self):
        cls, state = owner('LTXPipelineDecode', 'apply', _REPLICA_SETS={'replica': {}})
        original = cls.apply
        @functools.wraps(original)
        def wrapped(*args, **kwargs):
            return original(*args, **kwargs)
        cls.apply = wrapped
        self.assertIs(O.node_globals({'LTXPipelineDecode': cls}, 'LTXPipelineDecode', 'apply'), state)

    def test_registered_class_cannot_point_at_another_module_owner(self):
        cls, state = owner('LTXPipelineDecode', 'apply')
        state['NODE_CLASS_MAPPINGS']['LTXPipelineDecode'] = object()
        with self.assertRaisesRegex(RuntimeError, 'defining module'):
            O.node_globals({'LTXPipelineDecode': cls}, 'LTXPipelineDecode', 'apply')

    def test_actual_routes_and_node_installation_both_prevent_native_claim(self):
        graph, gs = owner('LTXGraphCaptureGate', '_apply', _installed=None)
        writer = types.SimpleNamespace(queue=queue.Queue())
        decode, ds = owner('LTXPipelineDecode', 'apply', _REPLICA_SETS={'replica': {}},
                           _WRITER=writer, SAVE_FAILURES=[])
        registry = {'LTXGraphCaptureGate': graph, 'LTXPipelineDecode': decode}
        prompt_queue = types.SimpleNamespace(get_current_queue=lambda: ([], []))
        pipeline = types.SimpleNamespace(_LOCK=threading.Lock(), _RUNNING=[0], _STAGES={})
        capture = types.SimpleNamespace(_ROUTES=[], CAPTURES_FROZEN=[False], LOADS_FROZEN=[False])
        lean = types.SimpleNamespace(_MEMO_INSTALLED={}, _SENTRY_INSTALLED={})
        def snapshot():
            return O.observe(registry, prompt_queue, pipeline, capture, lean)
        self.assertEqual(snapshot()['sampler_routes'], 0)
        capture._ROUTES.append(object())
        self.assertEqual(snapshot()['sampler_routes'], 1)
        capture._ROUTES.clear()
        gs['_installed'] = (None, {0: object(), 1: object()})
        self.assertEqual(snapshot()['sampler_routes'], 2)
        ds['_REPLICA_SETS']['replica']['video'] = object()
        lean._MEMO_INSTALLED[1] = object()
        self.assertEqual(snapshot()['decode_replicas'], 1)
        self.assertEqual(snapshot()['lean_state'], 1)
        writer.queue.put('unfinished-preview')
        self.assertEqual(snapshot()['preview_pending'], 1)
        ds['SAVE_FAILURES'].append({'error': 'preview failure'})
        self.assertTrue(snapshot()['fault'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
