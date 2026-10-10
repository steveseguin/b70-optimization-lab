"""CPU execution of the actual scheduled producer/consumer methods with fake XPU boundaries.

No listener, native import, device discovery or device access. The native callback
uses deterministic CPU tensors. This verifies scheduling and refusals, not GPUs.
"""
import ast
import copy
import hashlib
from pathlib import Path
import threading
import time
from types import SimpleNamespace as NS
import unittest
from unittest import mock

import torch
import stream_contract as contract
import text_prefetch138 as prefetch
import text_residency133 as residency

HERE = Path(__file__).resolve().parent


def actual_runtime_class():
    source = HERE / 'integration.py'
    tree = ast.parse(source.read_text(), str(source))
    wanted = {'_maybe_prefetch_text', 'consume_text_prefetch', '_close_prefetch_window',
              '_encode_workers', 'text', '_check_prefetch_binding', '_text_prefetch_memory', '_text_graph_state'}
    methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in wanted]
    rows = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_tensor_rows')
    cls = ast.ClassDef(name='ActualRuntime', bases=[], keywords=[], body=methods, decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=[rows, cls], type_ignores=[]))
    namespace = dict(copy=copy, threading=threading, time=time, hashlib=hashlib,
                     text_prefetch138=prefetch, contract=contract, GIB=1024 ** 3, Path=Path)
    exec(compile(module, str(source), 'exec'), namespace)
    return namespace['ActualRuntime'], namespace['_tensor_rows']


Runtime, tensor_rows = actual_runtime_class()


class Pipeline:
    def __init__(self):
        self._LOCK = threading.Lock()
        self._STAGES = {'encode': {'workers': [], 'jobs': {}}}
        self.submitted = 0

    def submit(self, stage, index, callback, tag):
        self.submitted += 1
        job = NS(done=threading.Event(), error=None, value=None)
        def run():
            try:
                with torch.inference_mode():
                    job.value = callback()
            except BaseException as error:
                job.error = error
            finally:
                job.done.set()
        worker = threading.Thread(target=run, name='ltx-encode-0')
        self._STAGES[stage]['workers'] = [worker]
        self._STAGES[stage]['jobs'][index] = job
        worker.start()
        return True

    def collect(self, stage, index, tag):
        worker = self._STAGES[stage]['workers'][0]
        worker.join()
        job = self._STAGES[stage]['jobs'].pop(index)
        if job.error:
            raise job.error
        return job.value, dict(queued_ahead=True, stage_seconds=0.01, cpu_seconds=0.001,
                               tag=tag, speculation_miss=False)

    def pending(self, stage):
        return list(self._STAGES[stage]['jobs'])


class ScheduledPrefetch138(unittest.TestCase):
    def setUp(self):
        self.scenes = prefetch.load_schedule(HERE / 'prefetch-scenes138.json')
        self.runtime = rt = Runtime()
        rt.text_prefetch = 'scheduled'
        rt.prefetch_lock = threading.RLock()
        rt.prefetch_entry = None
        rt.prefetch_serial = 0
        rt.prefetch_allowed = True
        rt.prefetch_scenes = self.scenes
        rt.text_cache = None
        rt.text_reuse = 1
        rt.session = NS(require=prefetch.require)
        rt.fault = lambda: False
        rt.bindings = NS(check_native=lambda: None)
        rt.prefetch_functions = []
        rt._check_prefetch_binding = lambda: None
        rt._text_graph_state = lambda: ((0, ((123, ('graph64',)),)),)
        rt._text_prefetch_memory = lambda: {'xpu:2': 4 * 1024 ** 3, 'xpu:3': 12 * 1024 ** 3}
        self.publications = []
        rt.write = lambda path, value: self.publications.append((path, copy.deepcopy(value)))
        self.pipeline = Pipeline()
        self.infos = {}
        window = NS(_tls=threading.local())
        window.precheck = lambda *args: {'window': 64}
        window.info_for = lambda key: self.infos[key]
        self.bad_tls = False
        self.calls = []
        def encoding(clip, text, tag, index):
            window._tls.window = 64
            window._tls.no_capture = True
            self.calls.append((text, threading.current_thread().name, torch.is_inference_mode_enabled()))
            self.infos[tag, index] = {'window': 64, 'captured_graphs': 0, 'clip_index': index}
            window._tls.window = 64 if self.bad_tls else None
            window._tls.no_capture = False
            return (self.value(text),)
        window.encode = encoding
        native = lambda clip, text, consume_observations, encode_fn: encode_fn()[0]
        rt.adapter = NS(clip=object(), window=window, pipeline=self.pipeline,
            text_pipeline={'native_encode': native, '_job_tag': lambda mode, text: hashlib.sha256((mode+'\n'+text).encode()).hexdigest()})
        rt.authority = NS(lock=threading.RLock(), active=None,
            qualification_params=contract.qualification_params(145, 1, anchor='frame', decoder_graph=1,
                anchor_decode='cone', bencode_overlap=1, prep_ahead=1))
        rt.active_row = lambda name: rt.authority.active if name == rt.authority.active['name'] else prefetch.require(False, 'wrong active')
        prompts = [row['prompt'] for row in self.scenes] + list(contract.QUALIFICATION_PROMPTS)
        rt.text_oracle = {'prompts': {contract.text_sha256(p): {'tensors': tensor_rows(torch, self.value(p))} for p in prompts}}
        self.capture = mock.patch.dict('sys.modules', {'ltx_graph_capture': NS(pipelined_enabled=lambda: False)})
        self.capture.start()
        self.addCleanup(self.capture.stop)

    def value(self, prompt):
        return [[torch.tensor([list(hashlib.sha256(prompt.encode()).digest())], dtype=torch.float32), {'pooled_output': None}]]

    def activate(self, params):
        rt = self.runtime
        name = contract.run_name(params)
        chain = 'stream' if params['kind'] == 'stream' else params['scene_id']
        rt.authority.active = {'params': params, 'name': name, 'chain': chain}
        rt.current = {'name': name, 'text': {'completed': True}}
        return name

    def qualification(self, kind='qualify-graph'):
        rows = [copy.deepcopy(p) for p in self.runtime.authority.qualification_params if p['kind'] == kind]
        self.activate(rows[0])
        self.runtime._maybe_prefetch_text({'kind': kind, 'chunk_index': 0, 'stream_seq': -1})
        return rows

    def consume(self, params):
        rt = self.runtime
        name = self.activate(params)
        rt.current['text'] = None
        result = rt.consume_text_prefetch(rt.adapter.clip, params['prompt'], 'pipeline-window',
                                         contract.clip_index(params), name)
        if result is not None:
            rt.text(name, params['prompt'], result[0])
        return result

    def stream(self, position=3):
        params = contract.stream_params(145, position, self.scenes[position//4]['prompt'], 700+position,
            'a'*64 if position else '', 'kitten', int(position > 0), anchor='frame', decoder_graph=1,
            anchor_decode='cone', bencode_overlap=1, prep_ahead=1)
        params.update(schedule_position=position, schedule_sha256=prefetch.SCHEDULE_SHA256)
        self.activate(params)
        return params

    def test_graph_chain_cut_uses_actual_producer_consumer_and_text_gate(self):
        rows = self.qualification()
        result = self.consume(rows[2])
        self.assertIsNotNone(result)
        self.assertEqual(self.calls, [(rows[2]['prompt'], 'ltx-encode-0', True)])
        self.assertTrue(self.runtime.current['text']['scheduled_prefetch']['consumed'])
        self.assertEqual(tensor_rows(torch, result[0]), self.runtime.text_oracle['prompts'][contract.text_sha256(rows[2]['prompt'])]['tensors'])
        self.assertIsNone(self.runtime.prefetch_entry)
        self.assertFalse(self.pipeline.pending('encode'))

    def test_repeat_chain_cut_uses_actual_producer_consumer(self):
        rows = self.qualification('qualify-repeat')
        self.assertIsNotNone(self.consume(rows[2]))

    def test_stream_prediction_uses_active_last_scene_chunk_not_decode_job(self):
        params = self.stream()
        self.runtime._maybe_prefetch_text({'kind': 'stream', 'chunk_index': 2, 'stream_seq': 2})
        target = dict(params, **prefetch.prediction(params, self.scenes), reuse_text=0)
        self.assertIsNotNone(self.consume(target))
        self.assertEqual(self.calls[0][0], self.scenes[1]['prompt'])

    def test_cycling_prediction_wraps(self):
        params = self.stream(39)
        self.assertEqual(prefetch.prediction(params, self.scenes)['schedule_position'], 0)

    def test_each_slot_has_only_declared_last_chunk_prediction(self):
        for slot in range(40):
            params = self.stream(slot)
            self.assertEqual(prefetch.prediction(params, self.scenes) is not None, slot % 4 == 3)

    def test_missing_schedule_falls_back(self):
        params = self.stream()
        params.pop('schedule_sha256')
        self.assertIsNone(prefetch.prediction(params, self.scenes))

    def test_changed_schedule_hash_falls_back(self):
        params = self.stream()
        params['schedule_sha256'] = 'b'*64
        self.assertIsNone(prefetch.prediction(params, self.scenes))

    def test_different_actual_prompt_discards(self):
        rows = self.qualification()
        params = dict(rows[2], prompt=rows[0]['prompt'])
        self.assertIsNone(self.consume(params))
        self.assertIsNone(self.runtime.prefetch_entry)

    def test_reset_discards(self):
        rows = self.qualification()
        self.assertIsNone(self.consume(dict(rows[2], reset=1)))

    def test_wrong_chain_discards(self):
        rows = self.qualification()
        self.assertIsNone(self.consume(dict(rows[2], kind='qualify-repeat', scene_id='other-chain')))

    def test_mutated_buffer_refuses(self):
        rows = self.qualification()
        with torch.inference_mode():
            self.runtime.prefetch_entry['value'][0][0].add_(1)
        with self.assertRaisesRegex(RuntimeError, 'mutated'):
            self.consume(rows[2])

    def test_wrong_parent_hash_refuses_production(self):
        self.runtime.text_oracle['prompts'][contract.text_sha256(contract.QUALIFICATION_PROMPTS[2])]['tensors'][0]['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            self.qualification()
        self.assertIsNone(self.runtime.prefetch_entry)

    def test_window_state_leak_refuses(self):
        self.bad_tls = True
        with self.assertRaisesRegex(RuntimeError, 'fresh encoder state'):
            self.qualification()

    def test_changed_graph_owners_refuse(self):
        calls = iter([((0, ((123, ('graph64',)),)),), ((0, ((124, ('graph64',)),)),)])
        self.runtime._text_graph_state = lambda: next(calls)
        with self.assertRaisesRegex(RuntimeError, 'signatures or owners'):
            self.qualification()

    def test_memory_failure_prevents_any_encode(self):
        self.runtime._text_prefetch_memory = lambda: prefetch.require(False, 'memory floor')
        with self.assertRaisesRegex(RuntimeError, 'memory floor'):
            self.qualification()
        self.assertEqual(self.pipeline.submitted, 0)

    def test_closed_window_prevents_submit(self):
        self.runtime._close_prefetch_window()
        self.qualification()
        self.assertEqual(self.pipeline.submitted, 0)

    def test_stale_current_name_prevents_submit(self):
        params = self.stream()
        self.runtime.current['name'] = 'wrong'
        self.runtime._maybe_prefetch_text({'kind': 'stream', 'chunk_index': 2, 'stream_seq': 2})
        self.assertEqual(self.pipeline.submitted, 0)

    def test_no_fresh_encode_for_eager_control(self):
        self.qualification('qualify-eager')
        self.assertEqual(self.pipeline.submitted, 0)

    def test_single_slot_prevents_duplicate_encode(self):
        self.qualification()
        self.qualification()
        self.assertEqual(self.pipeline.submitted, 1)

    def test_off_path_has_no_work(self):
        self.runtime.text_prefetch = 'off'
        rows = self.qualification()
        self.assertIsNone(self.consume(rows[2]))
        self.assertEqual(self.pipeline.submitted, 0)

    def test_evidence_checks_floor_and_boolean_types(self):
        rows = self.qualification()
        self.consume(rows[2])
        evidence = self.runtime.current['text']['scheduled_prefetch']
        for key, value in [('tls_clear', 1), ('consumed', 1), ('buffer_bytes', True), ('oracle_sha256', '0'*64)]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                prefetch.validate_evidence(dict(evidence, **{key: value}))
        bad = copy.deepcopy(evidence)
        bad['memory_before']['xpu:3'] = 9*1024**3
        with self.assertRaises(RuntimeError):
            prefetch.validate_evidence(bad)

    def test_schedule_hash_change_refuses_loading(self):
        with mock.patch.object(Path, 'read_bytes', return_value=b'{}'):
            with self.assertRaisesRegex(RuntimeError, 'table changed'):
                prefetch.load_schedule(HERE/'prefetch-scenes138.json')

    def test_graph_owner_same_signature_replacement_is_detected(self):
        tensor = torch.zeros([2])
        entry = NS(graph=object(), output=tensor, flat=[tensor])
        shadow = NS(index=0, entries_by_thread={123: {'same-signature': entry}})
        self.runtime.adapter.window._graph_layers = lambda clip: (None, None, [shadow])
        before = Runtime._text_graph_state(self.runtime)
        entry.graph = object()
        self.assertNotEqual(before, Runtime._text_graph_state(self.runtime))

    def test_graph_static_storage_replacement_is_detected(self):
        tensor = torch.zeros([2])
        entry = NS(graph=object(), output=tensor, flat=[tensor])
        shadow = NS(index=0, entries_by_thread={123: {'same-signature': entry}})
        self.runtime.adapter.window._graph_layers = lambda clip: (None, None, [shadow])
        before = Runtime._text_graph_state(self.runtime)
        entry.flat = [torch.zeros([2])]
        self.assertNotEqual(before, Runtime._text_graph_state(self.runtime))

    def test_runtime_callback_identity_is_bound(self):
        rt = self.runtime
        rt.prefetch_constants = (prefetch.SCHEMA, prefetch.SCHEDULE_SHA256,
            prefetch.MAX_BUFFER_BYTES, prefetch.BOUND_SECONDS, prefetch.CHOICES)
        rt.prefetch_consumer = rt.consume_text_prefetch
        rt.prefetch_consumer_function = rt.prefetch_consumer.__func__
        rt.prefetch_consumer_code = rt.prefetch_consumer_function.__code__
        with mock.patch.object(prefetch, '_CONSUMER', rt.prefetch_consumer):
            Runtime._check_prefetch_binding(rt)
        with mock.patch.object(prefetch, '_CONSUMER', lambda *args: None):
            with self.assertRaisesRegex(RuntimeError, 'ownership changed'):
                Runtime._check_prefetch_binding(rt)

    def test_runtime_constants_are_bound(self):
        rt = self.runtime
        rt.prefetch_constants = (prefetch.SCHEMA, prefetch.SCHEDULE_SHA256,
            prefetch.MAX_BUFFER_BYTES, prefetch.BOUND_SECONDS, prefetch.CHOICES)
        rt.prefetch_consumer = rt.consume_text_prefetch
        rt.prefetch_consumer_function = rt.prefetch_consumer.__func__
        rt.prefetch_consumer_code = rt.prefetch_consumer_function.__code__
        with mock.patch.object(prefetch, '_CONSUMER', rt.prefetch_consumer), mock.patch.object(prefetch, 'MAX_BUFFER_BYTES', 1):
            with self.assertRaisesRegex(RuntimeError, 'ownership changed'):
                Runtime._check_prefetch_binding(rt)


if __name__ == '__main__':
    unittest.main()
