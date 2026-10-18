"""Exercise the patched v4 entry functions and the read-only carry checker."""
import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

import build_templates as T
import teardown_on_error as E
from test_teardown_on_error import Files, module


class ScreenTests(Files):
    def scenario(self, mode, lane='B'):
        here = self.root / 'screen/v4-copy'
        here.mkdir(parents=True)
        (here / 'evidence').mkdir()
        shared = here.parent / 'v3'
        shared.mkdir()
        prior = dict(drained=False, pid=123, boot_id='other-owner', output='other-output')
        (shared / 'teardown-state.json').write_text(json.dumps(prior))
        prior_bytes = (shared / 'teardown-state.json').read_bytes()
        out = here / 'evidence/run'
        lineage = self.root / 'lineage'
        lineage.mkdir()
        events, signals, leases = [], [], []
        child = SimpleNamespace(pid=91000001, returncode=0, poll=lambda: child.returncode,
                                send_signal=signals.append)
        save = self.mods['lane_admission'].atomic_json
        read = lambda path: json.loads(Path(path).read_text())
        original_error = ValueError('post-exit report error')
        fault_present = False

        def journal(*unused):
            return ('Fault response' if fault_present else '', 'cursor')

        def supervise(*args, **kwargs):
            nonlocal fault_present
            run = out / 'run'
            run.mkdir()
            row = read(out / 'window.json')
            teardown = dict(drained=mode != 'undrained', pid=child.pid,
                            boot_id=row['boot_id'], output=str(run))
            if mode == 'wrong-owner':
                teardown['pid'] += 1
            save(run / 'teardown.json', teardown)
            if mode == 'worker-error':
                child.returncode = 1
            if mode == 'new-fault':
                child.returncode = 1
                fault_present = True
            if mode == 'live':
                child.returncode = None
            save(run / 'report-inputs.json', dict(passed=True, lane=lane, placement={},
                 requests=[dict(passed=True, exact_oracle=True)]*12,
                 incident64=dict(passed=True), device_isolation=dict(passed=True)))
            return dict(child_still_running=mode == 'live', returncode=child.returncode)

        def summary(*unused):
            events.append('summary')
            self.assertFalse(self.marker(lane).exists())
            if mode == 'report-error':
                raise original_error
            return dict(passed=True)

        def reserve(lane, **kwargs):
            lease = self.mods['lane_admission'].Reservation(lane, root=self.root / 'coord', **kwargs)
            leases.append(lease)
            return lease

        def prelaunch(*unused):
            if mode == 'admission-refusal':
                raise original_error

        def topology(*unused):
            if mode == 'internal-refusal':
                raise original_error
            return {}

        def popen(*args, **kwargs):
            events.append('launch')
            return child

        def check_fault(text):
            return ['fault'] if 'Fault response' in text else []

        ns = dict(__file__=str(here / 'screen.py'), argparse=argparse, fcntl=fcntl, json=json, os=os,
            Path=Path, signal=SimpleNamespace(SIGINT=2, SIGTERM=15, signal=lambda *args: None),
            subprocess=SimpleNamespace(Popen=popen, STDOUT=-2), time=SimpleNamespace(time_ns=lambda: 123456789),
            Reservation=reserve, atomic_json=save, admission_scope=self.mods['lane_admission'].admission_scope,
            process_identity=lambda pid: None, admit_clients=lambda scope: {}, DEFAULT_DRAIN_ROOT=shared,
            screen_teardown_admit=prelaunch, fault_review=SimpleNamespace(validate=lambda p: ({}, '', '', 'c'),
               fault_lines=check_fault), masked_environment=lambda lane: {}, topology_admit=topology,
            LANES={lane: {} for lane in ('A', 'B')}, cpu_gate=lambda: None, lane_gate=lambda lane: None,
            selected_clients=lambda lane: {}, D=SimpleNamespace(ORACLE=self.root,
               oracle_inputs=lambda: dict(prompts=[dict(prompt_id='incident-retrospective', input_bundle='fake')])),
            HERE=here, ROOT=self.root, M=SimpleNamespace(GIB=1024**3),
            S=SimpleNamespace(supervise=supervise, ldd_preflight=lambda *args: {}, journal=journal,
                              FAULT=re.compile('Fault response')),
            SUPPORT=SimpleNamespace(storage=lambda *args: {}, process_start=lambda pid: 77),
            W=SimpleNamespace(memory_fence=lambda: {}), compare_tokens=None, label=lambda row: row, read=read,
            require=E.require, save=save, sealed=lambda args: dict(placement=dict(supported=True, reason=''),
               binary='/fake', timing='token'), sha=lambda path: '0'*64, summary=summary,
            memory_admit=lambda profile: {}, unit_gate=lambda c: None, unit_conditions=lambda c: {},
            VERSION=E.VERSION, StickyCheck=E.StickyCheck, drained_on_error=E.drained_on_error,
            finish_on_error=E.finish_on_error,
            prove_screen_exit=lambda *args: E.prove_screen_exit(*args, proc=self.proc))
        source = T.screen_sources(T.REFERENCES['screen'])['screen.py']
        tree = ast.parse(source)
        nodes = [node for node in tree.body if
                 isinstance(node, ast.FunctionDef) and node.name in ('parser', 'command', 'screen_main', 'main')
                 or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('WRITES', 'WATCHDOG')
                                                        for t in node.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'patched-screen.py', 'exec'), ns)
        sys.modules['cpu_seal'] = SimpleNamespace(verify=lambda: None)
        original_read = Path.read_text
        def read_text(path, *args, **kwargs):
            if str(path) == '/proc/self/cgroup':
                return '/user@1000.service/screen-test.service'
            return original_read(path, *args, **kwargs)
        argv = ['--lane', lane, '--placement', '1', '--lineage', str(lineage), '--output', str(out),
                '--fault-review', str(self.root / 'review.json'), '--authorized-device-window']
        caught = None
        code = None
        with patch.object(Path, 'read_text', read_text):
            try:
                code = ns['main'](argv)
            except ValueError as error:
                caught = error
        self.assertEqual(signals, [])
        # A parent's failed admission must never rewrite the other owner's drain.
        self.assertEqual((shared / 'teardown-state.json').read_bytes(), prior_bytes)
        return SimpleNamespace(code=code, error=caught, out=out, lease=leases[0],
                               latches=list(shared.glob('fault-*.json')), events=events, original=original_error)

    def test_worker_error_after_confirmed_drain_releases_and_reraises(self):
        result = self.scenario('worker-error')
        self.assertRegex(str(result.error), 'screen failed or interrupted')
        self.assertTrue(result.lease.completed)
        self.assertFalse(self.marker('B').exists())
        self.assertEqual(result.latches, [])
        row = json.loads((result.out / 'window.json').read_text())
        self.assertFalse(row['passed'])
        self.assertEqual(row['teardown_on_error'], E.VERSION)

    def test_post_release_report_error_preserves_original_exception(self):
        result = self.scenario('report-error')
        self.assertIs(result.error, result.original)
        self.assertTrue(result.lease.completed)
        self.assertEqual(result.latches, [])

    def test_new_kernel_fault_never_releases_or_clears_latch(self):
        result = self.scenario('new-fault')
        self.assertEqual(result.code, 1)
        self.assertFalse(result.lease.completed)
        self.assertTrue(self.marker('B').exists())
        self.assertTrue(result.latches)

    def test_live_worker_leaves_marker_and_return_75(self):
        result = self.scenario('live')
        self.assertEqual(result.code, 75)
        self.assertFalse(result.lease.completed)
        self.assertTrue(self.marker('B').exists())

    def test_unconfirmed_drain_still_latches(self):
        result = self.scenario('undrained')
        self.assertEqual(result.code, 1)
        self.assertTrue(self.marker('B').exists())
        self.assertTrue(result.latches)

    def test_lane_a_refusal_before_launch_releases_only_own_marker(self):
        result = self.scenario('admission-refusal', lane='A')
        self.assertIs(result.error, result.original)
        self.assertEqual(result.events, [])
        self.assertTrue(result.lease.completed)
        self.assertFalse(self.marker('A').exists())

    def test_caught_internal_refusal_before_launch_preserves_nonzero(self):
        result = self.scenario('internal-refusal')
        self.assertEqual(result.code, 1)
        self.assertEqual(result.events, [])
        self.assertTrue(result.lease.completed)
        self.assertFalse(self.marker('B').exists())

    def test_normal_screen_still_passes(self):
        result = self.scenario('success')
        self.assertIsNone(result.error)
        self.assertEqual(result.code, 0)
        self.assertTrue(result.lease.completed)
        self.assertEqual(result.latches, [])


class CheckerTests(Files):
    def setUp(self):
        super().setUp()
        path = T.HERE.parents[4] / 'scripts/check_teardown_on_error.py'
        self.checker = module('test_checker', path.read_text(), path)

    def copy(self, kind):
        destination = self.root / kind
        destination.mkdir()
        render = T.chain_sources if kind == 'chain' else T.screen_sources
        for name, source in render(T.REFERENCES[kind]).items():
            (destination / name).write_text(source)
        (destination / 'teardown_on_error.py').write_bytes((T.HERE / 'teardown_on_error.py').read_bytes())
        return destination

    def test_both_known_integrations_are_carried(self):
        for kind in ('chain', 'screen'):
            with self.subTest(kind=kind):
                self.assertTrue(self.checker.inspect_packet(self.copy(kind))['passed'])

    def test_original_packet_is_not_carried(self):
        for kind in ('chain', 'screen'):
            with self.subTest(kind=kind):
                self.assertFalse(self.checker.inspect_packet(T.REFERENCES[kind])['passed'])

    def test_helper_alone_or_dead_hook_is_not_carried(self):
        packet = self.copy('chain')
        (packet / 'window_adapter.py').write_text('# finish_chain_error is mentioned but never called\n')
        self.assertFalse(self.checker.inspect_packet(packet)['passed'])
        (packet / 'window_adapter.py').unlink()
        self.assertFalse(self.checker.inspect_packet(packet)['passed'])

    def test_changed_helper_or_symlink_is_not_carried(self):
        packet = self.copy('chain')
        helper = packet / 'teardown_on_error.py'
        helper.write_text('# not the checked helper\n')
        self.assertFalse(self.checker.inspect_packet(packet)['passed'])
        helper.unlink()
        helper.symlink_to(T.HERE / 'teardown_on_error.py')
        self.assertFalse(self.checker.inspect_packet(packet)['passed'])


class WorkerDrainTests(Files):
    def test_worker_uses_parent_boundary_and_sticky_fault_classifier(self):
        source = T.screen_sources(T.REFERENCES['screen'])['tp2_worker.py']
        tree = ast.parse(source)
        run = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        start = next(i for i, node in enumerate(run.body) if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'teardown_cursor' for t in node.targets))
        end = next(i for i in range(start, len(run.body)) if isinstance(run.body[i], ast.Try))
        reads, classified = [], []
        lines = ['', 'CAT error', '']
        def journal(cursor):
            reads.append(cursor)
            return lines.pop(0), 'later-cursor'
        def faults(text):
            classified.append(text)
            return bool(text)
        ns = dict(output=self.root / 'worker', read=lambda p: {'coordinator_fault_review': {'cursor': 'parent-boundary'}},
                  require=E.require, StickyCheck=E.StickyCheck, S=SimpleNamespace(journal=journal),
                  fault_review=SimpleNamespace(fault_lines=faults), identity={'lane': 'A'},
                  pipeline=SimpleNamespace(Transport=type('FakeTransport', (), {})))
        exec(compile(ast.Module(body=run.body[start:end], type_ignores=[]), 'worker-fault-boundary.py', 'exec'), ns)
        ns['transport'].teardown_check()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'new GPU fault'):
                ns['transport'].teardown_check()
        self.assertEqual(reads, ['parent-boundary', 'parent-boundary'])
        self.assertEqual(classified, ['', 'CAT error'])

    def scenario(self, mode):
        sources = T.screen_sources(T.REFERENCES['screen'])
        output = self.root / 'worker'
        output.mkdir()
        ns = dict(fcntl=fcntl, Path=Path, os=os,
                  time=SimpleNamespace(monotonic=self.clock.now, sleep=self.clock.sleep),
                  DEFAULT_DRAIN_ROOT=self.drain, require=E.require,
                  save=self.mods['lane_admission'].atomic_json,
                  read=lambda path: json.loads(Path(path).read_text()),
                  finish_on_error=E.finish_on_error)
        tree = ast.parse(sources['conditions.py'])
        node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Teardown')
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'patched-conditions.py', 'exec'), ns)
        ns.update(prove_transport_exit=lambda t: E.prove_transport_exit(t, proc=self.proc),
                  selected_clients=lambda lane: self.mods['chain_devices'].admit_clients('lane-' + lane, self.proc))
        tree = ast.parse(sources['tp2_worker.py'])
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'drain')
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'patched-worker.py', 'exec'), ns)
        self.owner()
        error = ValueError('post-exit Python receipt failure')
        child = SimpleNamespace(pid=91000001, poll=lambda: None if mode == 'live' else 0)
        checks, stops = [], []
        def check():
            checks.append('journal')
            if mode == 'fault':
                raise ValueError('new Fault response')
        def close(success):
            if mode != 'live' and (self.proc / '91000001').exists():
                shutil.rmtree(self.proc / '91000001')
            if mode != 'success':
                raise error
        transport = SimpleNamespace(children=[child], retained=[], close=close, stop=stops.append,
                                    teardown_check=E.StickyCheck(check), teardown_lane='A')
        if mode == 'success':
            ns['drain'](transport, output, True)
        else:
            with self.assertRaises(ValueError) as caught:
                ns['drain'](transport, output, True)
            self.assertIs(caught.exception, error)
        return output, ns, transport

    def test_worker_post_exit_exception_still_records_drained(self):
        output, _, _ = self.scenario('error')
        self.assertTrue(self.state()['drained'])
        self.assertTrue(json.loads((output / 'teardown.json').read_text())['drained'])

    def test_worker_live_rank_stays_undrained(self):
        self.scenario('live')
        self.assertFalse(self.state()['drained'])

    def test_worker_new_fault_stays_undrained(self):
        self.scenario('fault')
        self.assertFalse(self.state()['drained'])

    def test_worker_success_uses_same_writer(self):
        self.scenario('success')
        self.assertTrue(self.state()['drained'])
