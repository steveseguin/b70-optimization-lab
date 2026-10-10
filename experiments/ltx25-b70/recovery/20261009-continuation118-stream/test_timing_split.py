"""CPU tests (packet118): the timing split (measurement only, always on).

1. stream_receipts.submit_split: the named sub-buckets of submit -> sampler A from the timing marks, the snapshot
   records and the node starts; the tiling buckets plus `other` add up to submit_to_sampler_start exactly; absent
   marks give None and move their time into `other`; the stage-A snapshot parts are inside condition_a_tail.
2. stream_receipts.turnaround_split: the predecessor's receipt -> this submit, with `other` closing the sum.
3. validate_measurements refuses malformed server options, snapshot records, splits and turnaround blocks.
4. The authority's healthy() keeps counting calls and time (and the plan-digest share) without changing a check,
   and the chain records each commit's time for the successor's turnaround.
5. The executor timing wrapper records entry/exit around the guarded execute_async, refuses to install twice or
   without the guard, and passes results and exceptions through unchanged.
6. The admission middleware and the receipt route record their marks (source structure).
"""
import ast
import asyncio
import json
import unittest
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stream_receipts as rec  # noqa: E402
import stream_contract as c  # noqa: E402
import test_session as ts  # noqa: E402

MS = 10 ** 6


def marks():
    """A frame-anchored stream chunk's marks (ns), 1 ms apart in the runtime's order."""
    t = {k: None for k in rec.TIMING_KEYS}
    order = ['submit', 'precheck_done', 'queued', 'executor_entry', 'execution_start', 'request_snapshot_start',
             'request_snapshot_done', 'before_request_done', 'stream_text_start', 'anchor_start', 'condition_a_start',
             'condition_a_lookup_done', 'condition_a_done', 'concat_a_start', 'sampler_a_start']
    for i, key in enumerate(order):
        t[key] = (i + 1) * 10 * MS
    t['admission_received'] = 5 * MS
    return t


def snaps(t):
    a0 = t['condition_a_lookup_done'] + 1 * MS
    return [{'label': 'request-before', 'mode': 'fingerprint', 'dual': False, 'agree': None,
             'start_ns': t['request_snapshot_start'] + MS, 'end_ns': t['request_snapshot_done'] - MS},
            {'label': 'A-before', 'mode': 'fingerprint', 'dual': False, 'agree': None, 'start_ns': a0,
             'end_ns': a0 + 2 * MS},
            {'label': 'A-after', 'mode': 'fingerprint', 'dual': False, 'agree': None, 'start_ns': a0 + 5 * MS,
             'end_ns': a0 + 7 * MS}]


class SubmitSplit(unittest.TestCase):
    def test_buckets_and_the_sum(self):
        t = marks()
        nodes = {'stream_text': t['stream_text_start'], 'stream_anchor': t['anchor_start'], '420': 1,
                 '344': t['sampler_a_start']}
        split = rec.submit_split(t, snaps(t), nodes)
        self.assertEqual(set(split), {k for k, _, _ in rec.SUBMIT_SPLIT} | {'other', 'total'})
        self.assertEqual(split['total'], 0.14)
        self.assertEqual(split['precheck'], 0.01)
        self.assertEqual(split['request_before_snapshot'], 0.01)
        self.assertEqual(split['executor_to_first_node'], 0.01)          # before_request_done -> stream_text
        self.assertEqual(split['first_node_to_condition_a'], 0.02)       # text window/reuse + anchor read
        self.assertEqual(split['stage_a_before_snapshot'], 0.002)
        self.assertEqual(split['stage_a_consume'], 0.003)
        self.assertEqual(split['stage_a_after_snapshot'], 0.002)
        self.assertEqual(split['dispatch_to_sampler_a'], 0.02)
        tiles = sum(split[k] for k in rec.SUBMIT_TILES)
        self.assertAlmostEqual(tiles + split['other'], split['total'], places=9)
        self.assertAlmostEqual(split['other'], 0.0, places=9)
        inner = split['stage_a_before_snapshot'] + split['stage_a_consume'] + split['stage_a_after_snapshot']
        self.assertLessEqual(inner, split['condition_a_tail'])

    def test_missing_marks_move_into_other(self):
        t = marks()
        for key in ('queued', 'executor_entry', 'condition_a_start', 'condition_a_lookup_done', 'condition_a_done'):
            t[key] = None                                   # no HTTP path; an unanchored chunk
        split = rec.submit_split(t, [], {})
        self.assertIsNone(split['comfy_validate_queue'])
        self.assertIsNone(split['stage_a_before_snapshot'])
        self.assertIsNone(split['first_node'] if 'first_node' in split else None)
        tiles = sum(split[k] for k in rec.SUBMIT_TILES if split[k] is not None)
        self.assertAlmostEqual(tiles + split['other'], split['total'], places=9)
        self.assertIsNone(rec.submit_split({k: None for k in rec.TIMING_KEYS})['total'])

    def test_first_node_ignores_nodes_outside_the_window(self):
        t = marks()
        split = rec.submit_split(t, [], {'early': t['submit'] - 1, 'late': t['sampler_a_start'] + 1,
                                         'x': t['before_request_done'] + 3 * MS})
        self.assertEqual(split['executor_to_first_node'], 0.003)


class Turnaround(unittest.TestCase):
    def test_split_and_sum(self):
        m = {'receipt_staged': 100 * MS, 'commit': 104 * MS, 'commit_written': 105 * MS, 'first_served': 150 * MS,
             'admission_received': 170 * MS, 'submit': 171 * MS}
        split = rec.turnaround_split(m)
        self.assertEqual((split['receipt_staged_to_commit'], split['commit_write'], split['commit_to_first_served'],
                          split['served_to_admission'], split['admission_parse'], split['total']),
                         (0.004, 0.001, 0.045, 0.02, 0.001, 0.071))
        self.assertAlmostEqual(split['other'], 0.0, places=9)
        m['first_served'] = None                           # polled before commit? not served: other closes the sum
        split = rec.turnaround_split(m)
        self.assertIsNone(split['commit_to_first_served'])
        self.assertAlmostEqual(split['other'], 0.065, places=9)


class Validation(unittest.TestCase):
    def receipt(self):
        t = marks()
        return {'server_options': {'snapshot_mode': 'fingerprint', 'decoder_graph_pool_cap_bytes': None},
                'snapshots': [dict(s, label=l) for s, l in zip(snaps(t) * 2, ['request-before', 'A-before', 'A-after',
                                                                              'B-before', 'B-after', 'request-after'])],
                'timing_s': {'submit_split': rec.submit_split(t)}, 'node_starts_ns': {'344': 1},
                'authority_checks': {'healthy_calls': 3, 'healthy_s': 0.01}, 'turnaround': None}

    def test_valid_and_invalid(self):
        rec.validate_measurements(self.receipt())
        bad = []
        r = self.receipt(); r['server_options']['snapshot_mode'] = 'quick'; bad.append(r)
        r = self.receipt(); r['server_options']['decoder_graph_pool_cap_bytes'] = 1.5; bad.append(r)
        r = self.receipt(); r['snapshots'][0]['mode'] = 'walk'; bad.append(r)               # differs from the launch
        r = self.receipt(); r['snapshots'] = r['snapshots'][1:]; bad.append(r)               # no request-before
        r = self.receipt(); r['snapshots'][2]['dual'] = True; bad.append(r)                  # dual without agree
        r = self.receipt(); r['snapshots'][2]['agree'] = False; bad.append(r)
        r = self.receipt(); r['snapshots'][1], r['snapshots'][2] = r['snapshots'][2], r['snapshots'][1]; bad.append(r)
        r = self.receipt(); r['timing_s']['submit_split'].pop('other'); bad.append(r)
        r = self.receipt(); r['node_starts_ns'] = {'344': 'x'}; bad.append(r)
        r = self.receipt(); r['authority_checks'] = {}; bad.append(r)
        r = self.receipt(); r['turnaround'] = {'split': {}}; bad.append(r)
        for r in bad:
            with self.assertRaises(ValueError):
                rec.validate_measurements(r)


class AuthorityCounters(unittest.TestCase):
    def test_healthy_counts_and_commit_marks(self):
        h = ts.Harness(frames=49)
        try:
            before = h.a.health_snapshot()
            h.a.healthy()
            h.a.healthy()
            after = h.a.health_snapshot()
            self.assertEqual(after['calls'] - before['calls'], 2)
            self.assertGreater(after['plan_digest_seconds'], before['plan_digest_seconds'])
            self.assertGreaterEqual(after['seconds'], after['plan_digest_seconds'])
            h.a.plan['schema'] = 'changed'                    # the check itself is unchanged
            with self.assertRaises(RuntimeError):
                h.a.healthy()
            h.a.plan['schema'] = 'ltx.stream118.plan.v1'
            self.assertEqual(h.a.status()['server_options'], {})
        finally:
            h.close()

    def test_commit_marks_in_the_chain(self):
        h = ts.Harness(frames=49, anchor='frame')
        try:
            for g in c.setup_graphs():
                h.submit(g['graph'])
            for p in c.qualification_params(49, 0, 'two-way', 'frame')[:3]:      # the eager chain
                h.submit(c.build_chunk_graph(p))
            chain = h.a.chains['qeager']
            self.assertIsInstance(chain['commit_ns'], int)
            self.assertLessEqual(chain['commit_ns'], chain['commit_written_ns'])
        finally:
            h.close()


class ExecutorTiming(unittest.TestCase):
    def test_wrapper_records_and_passes_through(self):
        import integration

        class Executor:
            _resolution_guard_installed = True

            async def execute_async(self, prompt, prompt_id, extra_data=None, execute_outputs=None):
                if prompt == 'boom':
                    raise RuntimeError('boom')
                return ('done', prompt_id)

        ctx = type('Ctx', (), {'exec_marks': {}})()
        receipt = integration.install_executor_timing(Executor, ctx)
        self.assertEqual(receipt['behavior'], 'timestamps only')
        out = asyncio.run(Executor().execute_async('p', 'pid-1'))
        self.assertEqual(out, ('done', 'pid-1'))
        m = ctx.exec_marks['pid-1']
        self.assertTrue(type(m['entry']) is int and type(m['exit']) is int and m['entry'] <= m['exit'])
        with self.assertRaises(RuntimeError):
            asyncio.run(Executor().execute_async('boom', 'pid-2'))
        self.assertIsInstance(ctx.exec_marks['pid-2']['exit'], int)
        with self.assertRaises(RuntimeError):
            integration.install_executor_timing(Executor, ctx)          # twice

        class Bare:
            async def execute_async(self, *a):
                return None
        with self.assertRaises(RuntimeError):
            integration.install_executor_timing(Bare, ctx)              # without the resolution guard


class ReviewTimingRegression(unittest.TestCase):
    def test_queued_late_write_is_refreshed_without_mutating_frozen_copy(self):
        shared = {'admission_received': 1, 'precheck_done': 2, 'queued': None}
        timing = {}
        rec.refresh_admission_timing(timing, shared)
        self.assertIsNone(timing['queued'])
        shared['queued'] = 10                    # handler returns after executor entry
        rec.refresh_admission_timing(timing, shared)
        self.assertEqual(timing['queued'], 10)
        shared['queued'] = 11
        self.assertEqual(timing['queued'], 10)   # receipt owns a value snapshot, not a live dict
        rec.refresh_admission_timing(timing, {})
        self.assertTrue(all(v is None for v in timing.values()))

    def test_negative_queue_interval_is_not_clamped(self):
        timing = marks()
        timing['queued'] = timing['executor_entry'] + MS
        split = rec.submit_split(timing)
        self.assertEqual(split['queue_to_executor'], -0.001)
        self.assertAlmostEqual(sum(split[k] for k in rec.SUBMIT_TILES if split[k] is not None) +
                               split['other'], split['total'])

    def test_response_ready_before_fsync_preserves_negative_interval(self):
        split = rec.turnaround_split({'commit_written': 20 * MS, 'first_served': 19 * MS})
        self.assertEqual(split['commit_to_first_served'], -0.001)
        self.assertIsNone(split['total'])
        self.assertIsNone(split['other'])

    def route_fixture(self):
        # Compile only the nested route factory: no server, HTTP socket or runtime installation.
        tree = ast.parse((HERE / 'integration.py').read_text())
        factory = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'record_route')
        path = mock.MagicMock()
        path.__truediv__.return_value = path
        path.is_file.return_value = True
        ctx = SimpleNamespace(run=path, receipt_served={}, receipt_polls={},
                              session=SimpleNamespace(read_regular=mock.Mock(return_value=b'{}')))
        response = SimpleNamespace(status=200)
        web = SimpleNamespace(Response=mock.Mock(return_value=response))
        clock = mock.Mock(side_effect=[100, 200])
        env = {'ctx': ctx, 'web': web, 'time': SimpleNamespace(time_ns=clock),
               'RUN_NAME_RE': SimpleNamespace(fullmatch=lambda name: True),
               '_bound': lambda *args: None,
               'refuse': lambda code, message, status: SimpleNamespace(status=status)}
        exec(compile(ast.Module(body=[factory], type_ignores=[]), '<receipt-route-only>', 'exec'), env)
        return env['record_route']('receipt-'), ctx, web, clock, response

    def test_first_served_is_first_successful_response_construction(self):
        route, ctx, web, clock, response = self.route_fixture()
        request = SimpleNamespace(match_info={'run_name': 'chunk'})
        def construct(**kwargs):
            self.assertEqual(ctx.receipt_served, {})
            self.assertEqual(kwargs['body'], b'{}')
            return response
        web.Response.side_effect = construct
        self.assertIs(asyncio.run(route(request)), response)
        self.assertEqual(ctx.receipt_served, {'chunk': 100})
        web.Response.side_effect = None
        asyncio.run(route(request))
        self.assertEqual(ctx.receipt_served, {'chunk': 100})
        self.assertEqual(ctx.run.is_file.call_count, 2)     # one stat per route call

    def test_missing_or_failed_receipt_response_is_not_served(self):
        route, ctx, web, clock, _ = self.route_fixture()
        request = SimpleNamespace(match_info={'run_name': 'chunk'})
        ctx.run.is_file.return_value = False
        self.assertEqual(asyncio.run(route(request)).status, 404)
        self.assertEqual(ctx.receipt_polls, {'chunk': 1})
        self.assertEqual(ctx.receipt_served, {})
        ctx.run.is_file.return_value = True
        ctx.session.read_regular.side_effect = OSError('read failed')
        with self.assertRaises(OSError):
            asyncio.run(route(request))
        self.assertEqual(ctx.receipt_served, {})
        ctx.session.read_regular.side_effect = None
        web.Response.side_effect = RuntimeError('response failed')
        with self.assertRaises(RuntimeError):
            asyncio.run(route(request))
        self.assertEqual(ctx.receipt_served, {})
        clock.assert_not_called()


class Structure(unittest.TestCase):
    def test_middleware_and_route_marks(self):
        tree = ast.parse((HERE / 'integration.py').read_text())
        fn = {n.name: ast.unparse(n) for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        admission = fn['admission']
        self.assertLess(admission.index('received = time.time_ns()'), admission.index('await request.json()'))
        self.assertLess(admission.index("'precheck_done': time.time_ns()"), admission.index('await handler(request)'))
        self.assertLess(admission.index('await handler(request)'), admission.index("marks['queued'] = time.time_ns()"))
        self.assertLess(fn['route'].index('response = web.Response'),
                        fn['route'].index('ctx.receipt_served.setdefault(name, time.time_ns())'))
        self.assertIn("self.current['admission_marks'] = self.admission_marks.pop(prompt_id, {})",
                      fn['before_request'])
        self.assertIn('stream_receipts.refresh_admission_timing', fn['_after_chunk'])
        self.assertIn('install_executor_timing(execution.PromptExecutor, _CTX)', fn['install'])
        self.assertIn('ctx.note_status_route(time.perf_counter() - started)', fn['status'])
        # measurement only: the before_request marks wrap the unchanged before_request call
        before = fn['before_request']
        self.assertLess(before.index("timing['request_snapshot_start'] = time.time_ns()"),
                        before.index("before = self.adapter.before_request(row['name'])"))


if __name__ == '__main__':
    unittest.main()
