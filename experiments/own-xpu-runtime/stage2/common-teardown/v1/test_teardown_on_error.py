"""CPU-only regression: fake proc/fdinfo, journal and native calls; real locks.

Execute the reference adapter and K2 postprocessing tail, with only the new
patch applied in memory. All writes are confined to each test's temp directory.
"""
import ast
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

import build_templates as T
import teardown_on_error as E


def module(name, source, path):
    result = ModuleType(name)
    result.__file__ = str(path)
    exec(compile(source, str(path), 'exec'), result.__dict__)
    return result


class Clock:
    def __init__(self):
        self.value = 100.

    def now(self):
        return self.value

    def sleep(self, seconds):
        if seconds < 0:
            raise ValueError('negative sleep')
        self.value += seconds


class Files(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='teardown-on-error-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proc = self.root / 'proc'
        self.proc.mkdir()
        self.drain = self.root / 'drain'
        self.drain.mkdir()
        self.clock = Clock()
        self.mods = {}
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(sys.modules))
        for name in ('chain_devices', 'lane_admission', 'drain_gate'):
            path = T.REFERENCES['chain'] / (name + '.py')
            self.mods[name] = module(name, path.read_text(), path)
            sys.modules[name] = self.mods[name]
        self.W = self.adapter()

    def adapter(self, original=False):
        path = T.REFERENCES['chain'] / 'window_adapter.py'
        source = path.read_text() if original else T.chain_sources(path.parent)['window_adapter.py']
        return module('test_adapter', source, path)

    def owner(self, pid=91000001, state='S', fds=True):
        path = self.proc / str(pid)
        (path / 'fdinfo').mkdir(parents=True, exist_ok=True)
        (path / 'stat').write_text(f'{pid} (fake child) ' + ' '.join([state] + ['0']*18 + ['77'] + ['0']*10))
        if fds:
            (path / 'fdinfo/3').write_text('drm-driver: xe\ndrm-pdev: 0000:23:00.0\ndrm-client-id: 9\n')
            (path / 'fd').mkdir(exist_ok=True)
            (path / 'fd/3').symlink_to('/dev/dri/renderD128')
        return path

    def admission(self, *, original=False, check=lambda: None, window='K2'):
        adapter = self.adapter(original) if original else self.W
        admission = adapter.WindowAdmission(window, self.root / 'admission.json',
            root=self.root / 'coord', proc=self.proc, now=self.clock.now,
            topology=lambda lane: {}, drain_root=self.drain, check=check)
        admission.drain.now = self.clock.now
        admission.drain.sleep = self.clock.sleep
        return admission

    def state(self):
        return json.loads((self.drain / 'teardown-state.json').read_text())

    def marker(self, lane='A'):
        return self.root / ('coord/active-lane-' + lane + '.json')

    def locks_released(self, admission):
        for path in (self.drain / 'teardown.lock', self.root / 'coord/lane-A.lock'):
            with path.open('r+') as stream:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertFalse(admission.lease.files)

    def watch(self, admission, *, live=False, fault=False):
        self.owner()
        admission.register(91000001)
        if not live:
            shutil.rmtree(self.proc / '91000001')
        watch = SimpleNamespace(launched=[91000001], cpu_children=[], new_gpu_fault=fault, last=0)
        def postflight():
            self.assertEqual(watch.last, float('-inf'))
            self.assertTrue(self.marker().exists())
            self.assertFalse(self.state()['drained'])
            with (self.drain / 'teardown.lock').open('r+') as stream:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.clock.sleep(5)
        watch.postflight = postflight
        admission.watch = watch
        return watch


class ChainTests(Files):
    def test_post_exit_error_drains_releases_and_reraises_identical_error(self):
        admission = self.admission()
        error = ValueError('selection must name exactly route/recurrence/hc')
        with self.assertRaises(ValueError) as caught:
            with admission:
                self.watch(admission)
                raise error
        self.assertIs(caught.exception, error)
        self.assertTrue(self.state()['drained'])
        self.assertEqual(self.state()['completed_monotonic'], 105)
        self.assertFalse(self.marker().exists())
        row = json.loads(admission.evidence.read_text())
        self.assertFalse(row['passed'])
        self.assertEqual(row['teardown_on_error'], E.VERSION)
        self.locks_released(admission)

    def test_live_child_with_or_without_render_fds_leaves_undrained(self):
        for fds in (True, False):
            with self.subTest(fds=fds):
                admission = self.admission()
                with self.assertRaisesRegex(ValueError, 'original'):
                    with admission:
                        self.watch(admission, live=True)
                        if not fds:
                            shutil.rmtree(self.proc / '91000001/fd')
                            (self.proc / '91000001/fdinfo/3').unlink()
                        raise ValueError('original')
                self.assertFalse(self.state()['drained'])
                self.assertTrue(self.marker().exists())
                self.locks_released(admission)
                # Reset only this test's scratch, never a live marker.
                shutil.rmtree(self.root / 'coord')
                shutil.rmtree(self.proc / '91000001')
                (self.drain / 'teardown-state.json').unlink()

    def test_seen_fault_stays_undrained_even_with_empty_proc(self):
        admission = self.admission()
        with self.assertRaisesRegex(ValueError, 'original'):
            with admission:
                self.watch(admission, fault=True)
                raise ValueError('original')
        self.assertFalse(self.state()['drained'])
        self.assertTrue(self.marker().exists())

    def test_new_fault_in_postflight_stays_undrained(self):
        admission = self.admission()
        def fault():
            admission.watch.new_gpu_fault = True
            raise ValueError('new Fault response')
        with self.assertRaisesRegex(ValueError, 'original'):
            with admission:
                self.watch(admission).postflight = fault
                raise ValueError('original')
        self.assertFalse(self.state()['drained'])
        self.assertTrue(self.marker().exists())

    def test_foreign_client_or_missing_isolation_refuses_completion(self):
        admission = self.admission()
        with self.assertRaisesRegex(ValueError, 'original'):
            with admission:
                self.watch(admission)
                self.owner(91000002)
                raise ValueError('original')
        self.assertFalse(self.state()['drained'])
        self.assertTrue(self.marker().exists())

    def test_missing_ready_proof_is_not_bypassed(self):
        admission = self.admission(window='W0p')
        with self.assertRaisesRegex(ValueError, 'original'):
            with admission:
                self.watch(admission)
                raise ValueError('original')
        self.assertFalse(self.state()['drained'])
        self.assertTrue(self.marker().exists())

    def test_launch_registry_mismatch_refuses(self):
        admission = self.admission()
        with self.assertRaisesRegex(ValueError, 'original'):
            with admission:
                self.watch(admission).launched.append(91000002)
                raise ValueError('original')
        self.assertFalse(self.state()['drained'])

    def test_live_cpu_child_refuses(self):
        admission = self.admission()
        with self.assertRaisesRegex(ValueError, 'original'):
            with admission:
                self.watch(admission).cpu_children = [SimpleNamespace(pid=91000002, poll=lambda: None)]
                raise ValueError('original')
        self.assertFalse(self.state()['drained'])

    def test_success_still_uses_same_teardown_and_passes(self):
        admission = self.admission()
        with admission:
            self.watch(admission)
            admission.complete()
        self.assertTrue(self.state()['drained'])
        self.assertTrue(json.loads(admission.evidence.read_text())['passed'])
        self.assertFalse(self.marker().exists())

    def test_failed_receipt_is_never_accepted_by_verifier(self):
        admission = self.admission()
        with self.assertRaisesRegex(ValueError, 'original'):
            with admission:
                self.watch(admission)
                raise ValueError('original')
        with self.assertRaisesRegex(ValueError, 'missing completed lane admission'):
            self.W.verify_receipt(dict(passed=False, window='K2'))

    def test_next_permit_keeps_sixty_second_cooldown(self):
        admission = self.admission()
        with self.assertRaises(ValueError):
            with admission:
                self.watch(admission)
                raise ValueError('original')
        permit = self.mods['drain_gate'].DrainPermit(self.root / 'next', root=self.drain,
                   now=self.clock.now, sleep=self.clock.sleep)
        with permit:
            self.assertGreaterEqual(self.clock.now(), 165)
            permit.complete()

    def test_nonzero_adapter_return_cleans_but_remains_nonzero(self):
        admission = self.admission()
        def main(*, admission):
            self.watch(admission)
            return 7
        with patch.object(self.W, 'WindowAdmission', return_value=admission):
            code = self.W.run_window(main, wait_check=lambda: None,
                argv=['--window', 'K2', '--output', str(self.root / 'nonzero'),
                      '--card', '0', '--authorized-device-window'])
        self.assertEqual(code, 7)
        self.assertTrue(self.state()['drained'])
        self.assertFalse(self.marker().exists())
        self.assertFalse(json.loads(admission.evidence.read_text())['passed'])

    def test_foreign_marker_token_is_never_removed(self):
        admission = self.admission()
        other = {'token': 'some-other-owner'}
        with self.assertRaisesRegex(ValueError, 'original'):
            with admission:
                self.watch(admission)
                self.marker().write_text(json.dumps(other))
                raise ValueError('original')
        self.assertEqual(json.loads(self.marker().read_text()), other)
        self.assertFalse(admission.lease.completed)

    def test_admission_refusal_never_overwrites_prior_teardown(self):
        admission = self.admission()
        prior = dict(boot_id=admission.drain.boot, drained=False, pid=42, output='previous')
        path = self.drain / 'teardown-state.json'
        path.write_text(json.dumps(prior))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'previous shared drain incomplete'):
            with admission:
                self.fail('refused admission must not enter')
        self.assertEqual(path.read_bytes(), before)


class ReplayTests(Files):
    def replay(self, *, original=False, fault=False):
        """Run the actual K2 post-fixture branch and exception tail; no launch."""
        reference = T.REFERENCES['chain'] / 'window.py'
        source = reference.read_text() if original else T.chain_sources(reference.parent)['window.py']
        tree = ast.parse(source)
        watch_node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Watch')
        main_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        start = next(i for i, node in enumerate(main_node.body)
                     if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'watch' for t in node.targets))
        if not original:
            start -= 1  # failure=None
        main_node.body = main_node.body[start:]
        admission = self.admission(original=original)
        out = self.root / 'K2'
        out.mkdir()
        (self.root / 'build').mkdir()
        error = ValueError('selection must name exactly route/recurrence/hc')
        journal_reads = []
        def journal(cursor=None):
            journal_reads.append(cursor)
            return ('Fault response' if fault and cursor else '', 'cursor')
        def fixtures(a, output, env, watch):
            self.owner()
            watch.mark_launched(91000001)
            shutil.rmtree(self.proc / '91000001')
            save(output / 'children.json', dict(pids=[91000001]))
            (output / 'run0').mkdir()
            save(output / 'run0/receipt.json', dict(passed=True))
            return {}
        def fail(*args, **kwargs):
            raise error
        def attempt(label, call, errors):
            try:
                call()
            except Exception as exc:
                errors.append(str(exc))
        save = self.mods['lane_admission'].atomic_json
        env = dict(Path=Path, time=SimpleNamespace(monotonic=self.clock.now, sleep=self.clock.sleep),
            json=json, re=re, journal=journal, FAULT=re.compile('Fault response'), save=save, B=self.root / 'build',
            signal=SimpleNamespace(SIGINT=2, SIGTERM=15, signal=lambda *args: None),
            a=SimpleNamespace(window='K2', diagnostic_unsealed=False), out=out, boot='test-boot', seconds=100,
            record=dict(passed=False), native_env={}, build={}, identity={}, run_fixtures=fixtures,
            sequential_teardown=lambda row: True, summarize=lambda *args: dict(passed=True), require=E.require,
            pp=SimpleNamespace(failure_attempt=attempt), live_owner_pids=lambda watch: [], compress_evidence=lambda *args: None)
        sys.modules['p49_dispatch'] = SimpleNamespace(pin_production_dispatch=fail)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[watch_node, main_node], type_ignores=[])),
                     str(reference), 'exec'), env)
        if original:
            with admission:
                self.assertEqual(env['main'](admission=admission), 1)
        else:
            with self.assertRaises(ValueError) as caught:
                with admission:
                    env['main'](admission=admission)
            self.assertIs(caught.exception, error)
        row = json.loads((out / 'window.json').read_text())
        self.assertFalse(row['passed'])
        self.assertEqual(row['error'], str(error))
        return admission, journal_reads

    def test_original_k2_reproduces_stale_drain_and_marker(self):
        self.replay(original=True)
        self.assertFalse(self.state()['drained'])
        self.assertTrue(self.marker().exists())

    def test_patched_k2_replays_real_python_error_and_releases(self):
        admission, reads = self.replay()
        self.assertTrue(self.state()['drained'])
        self.assertFalse(self.marker().exists())
        self.assertGreater(len(reads), 1)
        self.assertGreaterEqual(self.clock.now(), 105)
        self.locks_released(admission)

    def test_patched_k2_new_kernel_fault_keeps_latch_and_marker(self):
        self.replay(fault=True)
        self.assertFalse(self.state()['drained'])
        self.assertTrue(self.marker().exists())
        self.assertTrue((self.root / 'build/FAULT.json').exists())


class HelperTests(Files):
    def test_zombie_reused_pid_and_render_fd_cannot_prove_reaped(self):
        for state in ('S', 'Z', 'X'):
            with self.subTest(state=state):
                self.owner(state=state)
                with self.assertRaises(ValueError):
                    E.require_reaped([91000001], self.proc)
                shutil.rmtree(self.proc / '91000001')
        E.require_reaped([91000001], self.proc)

    def test_permission_error_is_not_absence(self):
        with patch.object(Path, 'lstat', side_effect=PermissionError('hidden')):
            with self.assertRaises(PermissionError):
                E.require_reaped([91000001], self.proc)

    def test_consumed_check_failure_is_sticky(self):
        calls = []
        def check():
            calls.append(1)
            if len(calls) == 1:
                raise ValueError('new kernel fault')
        sticky = E.StickyCheck(check)
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'new kernel fault'):
                sticky()
        self.assertEqual(calls, [1])

    def test_cleanup_failure_does_not_mask_original(self):
        error = KeyError('original')
        def denied():
            raise OSError('cannot confirm drain')
        with self.assertRaises(KeyError) as caught:
            with E.drained_on_error(prove=denied, complete=lambda: self.fail('unsafe completion')):
                raise error
        self.assertIs(caught.exception, error)
        self.assertIn('cannot confirm drain', error.__notes__[0])

    def test_baseexception_still_reraises_after_cleanup(self):
        calls = []
        error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt) as caught:
            with E.drained_on_error(prove=lambda: calls.append('proof'), complete=lambda: calls.append('complete')):
                raise error
        self.assertIs(caught.exception, error)
        self.assertEqual(calls, ['proof', 'complete'])

    def test_screen_proof_binds_worker_boot_output_and_drain(self):
        row = dict(pid=91000001, process_start_ticks=77, device_executed=True, boot_id='boot',
                   child_still_running=False)
        child = SimpleNamespace(pid=91000001, poll=lambda: 1)
        teardown = dict(pid=child.pid, boot_id='boot', output=str(self.root / 'run'), drained=True)
        E.prove_screen_exit(row, child, teardown, self.root, proc=self.proc)
        for change in ({'drained': False}, {'gate_refused': True}, {'pid': 91000002},
                       {'boot_id': 'other'}, {'output': 'other'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                E.prove_screen_exit(row, child, dict(teardown, **change), self.root, proc=self.proc)


class TemplateTests(unittest.TestCase):
    def test_manifest_and_patches_match_rendered_sources(self):
        manifest = json.loads((T.HERE / 'templates.json').read_text())
        self.assertEqual(manifest['helper_sha256'], hashlib.sha256((T.HERE / 'teardown_on_error.py').read_bytes()).hexdigest())
        for kind, render in (('chain', T.chain_sources), ('screen', T.screen_sources)):
            import difflib
            diffs = []
            for name, changed in render(T.REFERENCES[kind]).items():
                original = (T.REFERENCES[kind] / name).read_bytes()
                item = manifest['integrations'][kind]['files'][name]
                self.assertEqual(hashlib.sha256(original).hexdigest(), item['before_sha256'])
                self.assertEqual(hashlib.sha256(changed.encode()).hexdigest(), item['after_sha256'])
                diffs.extend(difflib.unified_diff(original.decode().splitlines(True), changed.splitlines(True),
                             fromfile='a/' + name, tofile='b/' + name))
                compile(changed, name, 'exec')
            self.assertEqual(''.join('\n' if line == ' \n' else line for line in diffs),
                             (T.HERE / (kind + '-integration.patch')).read_text())


if __name__ == '__main__':
    unittest.main()
