"""CPU-only pin admission tests. All mutations are in temporary packets."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lanequeue as q
import pin_guard as guard
from test_lanequeue import QueueTestCase

REAL_PLAN = q.plan_job
REAL_CHECK = q.check_pins


class PinTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.stage = self.root / 'experiments/own-xpu-runtime/stage2'
        self.packet = self.stage / 'packet58x-cache-capacity'
        self.script = self.write(self.packet / 'queue_runner.py', "p.add_argument('--plan')\n")
        self.job = dict(name='packet58x-smoke-A', lane='A',
                        argv=['/usr/bin/python3', '-B', str(self.script)])

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def seal(self, path, target, field='sources', digest=None):
        digest = digest or hashlib.sha256(target.read_bytes()).hexdigest()
        self.write(path, json.dumps({field: {str(target): digest}}))

    def check(self):
        return guard.check_job(self.job, self.root, self.stage)

    def test_today_58x_cross_packet_verifier_refuses_before_plan_invocation(self):
        verifier = self.write(self.stage / 'packet58w-onecard-record/verify_ready.py', 'old verifier')
        self.seal(self.packet / 'build-receipt.json', verifier)
        with patch.object(q, 'ROOT', self.root), patch.object(q, 'STAGE', self.stage), \
             patch.object(q.subprocess, 'run') as invoke:
            with self.assertRaisesRegex(guard.PinRefusal, 'cross-packet mutable pin.*verify_ready.py') as failure:
                REAL_PLAN(self.job, '/unused', invoke)
        invoke.assert_not_called()
        self.assertIs(failure.exception.receipt['device_executed'], False)

    def test_pure_in_tree_packet_passes(self):
        self.seal(self.packet / 'build-receipt.json', self.script)
        self.assertTrue(self.check()['passed'])

    def test_current_hash_mismatch_refuses_even_in_tree(self):
        self.seal(self.packet / 'build-receipt.json', self.script)
        self.script.write_text('modified')
        with self.assertRaisesRegex(guard.PinRefusal, 'hash changed'):
            self.check()

    def test_missing_pin_refuses(self):
        self.seal(self.packet / 'build-receipt.json', self.script)
        self.script.unlink()
        with self.assertRaises(guard.PinRefusal):
            self.check()

    def test_invalid_hash_is_not_silently_ignored(self):
        self.seal(self.packet / 'build-receipt.json', self.script, digest='bad')
        with self.assertRaisesRegex(guard.PinRefusal, 'invalid SHA256'):
            self.check()

    def test_oracle_allowlist_and_hash_check(self):
        oracle = self.write(self.stage / 'packet49-integrate/oracle/arithmetic.json', '{}')
        self.seal(self.packet / 'build-receipt.json', oracle)
        self.assertTrue(self.check()['passed'])
        oracle.write_text('{"changed": true}')
        with self.assertRaisesRegex(guard.PinRefusal, 'hash changed'):
            self.check()

    def test_oracle_binding_targets_include_external_symlink(self):
        oracle = self.write(self.root / 'external-oracle/completion.json', '{}')
        link = self.packet / 'oracle'
        link.symlink_to(oracle.parent, target_is_directory=True)
        self.seal(self.packet / 'oracle-binding.json', link / oracle.name, 'files_sha256')
        self.assertTrue(self.check()['passed'])

    def test_symlink_to_mutable_other_packet_refuses(self):
        external = self.write(self.stage / 'packet58w-onecard-record/verify_ready.py', 'mutable')
        local = self.packet / 'borrowed.py'
        local.symlink_to(external)
        self.seal(self.packet / 'build-receipt.json', local)
        with self.assertRaisesRegex(guard.PinRefusal, 'cross-packet mutable'):
            self.check()

    def test_v4_frozen_wrapper_passes(self):
        wrapper = self.write(self.stage / 'screen/v4-lanes/run.py', 'frozen')
        self.seal(self.packet / 'screen-seal.json', wrapper)
        self.assertTrue(self.check()['passed'])

    def test_parent_build_binary_passes_but_source_in_build_refuses(self):
        binary = self.write(self.stage / 'packet58v-async-cache/build/device/own-rt-iq3', '\x7fELFfixture')
        self.seal(self.packet / 'build-receipt.json', binary)
        self.assertTrue(self.check()['passed'])
        source = self.write(binary.parent / 'main.cpp', 'not frozen')
        self.seal(self.packet / 'build-receipt.json', source)
        with self.assertRaisesRegex(guard.PinRefusal, 'cross-packet mutable'):
            self.check()

    def test_completed_chain_evidence_passes_unfinished_refuses(self):
        folder = self.stage / 'packet58w-onecard-record/evidence/card0-58w-a/WS'
        source = self.write(folder / 'run/receipt.json', '{}')
        window = self.write(folder / 'window.json', json.dumps(dict(
            passed=True, device_executed=True, finished_utc_ns=123, child_still_running=False)))
        self.seal(self.packet / 'ready.json', source, 'screen_sources')
        self.assertTrue(self.check()['passed'])
        window.write_text('{"passed": true}')
        with self.assertRaisesRegex(guard.PinRefusal, 'cross-packet mutable'):
            self.check()

    def test_model_bytes_are_never_opened(self):
        model = self.root / 'models/weights.gguf'
        self.seal(self.packet / 'build-receipt.json', model, digest='f' * 64)
        with patch.object(guard, 'sha256', side_effect=AssertionError('no model reads')):
            result = self.check()
        self.assertEqual(result['model_hashes_deferred'], [str(model)])

    def test_nested_seal_text_list_and_readiness_maps(self):
        local = self.write(self.packet / 'host-admission/derive.py', 'frozen')
        digest = hashlib.sha256(local.read_bytes()).hexdigest()
        self.write(local.parent / 'seal.json', json.dumps({'files': {'derive.py': digest}}))
        self.write(self.packet / 'wrapper-sources', f'{digest}  {local}\n')
        self.seal(self.packet / 'READY-FOR-DEVICE.json', self.script, 'screen_sources')
        self.assertEqual(self.check()['pins'], 2)

    def test_hash_linked_evidence_source_lists_are_followed(self):
        external = self.write(self.stage / 'packet58w-onecard-record/verify_ready.py', 'mutable')
        manifest = self.packet / 'evidence/identity-sources.json'
        self.seal(manifest, external)
        self.seal(self.packet / 'build-receipt.json', manifest, 'gates')
        with self.assertRaisesRegex(guard.PinRefusal, 'verify_ready.py'):
            self.check()

    def test_record_lists_and_nested_file_hashes_are_checked(self):
        digest = hashlib.sha256(self.script.read_bytes()).hexdigest()
        for pins in ([{'path': str(self.script), 'sha256': digest}],
                     {str(self.script): {'sha256': digest, 'size': 25}},
                     {'path': str(self.script), 'sha256': digest}):
            with self.subTest(pins=pins):
                self.write(self.packet / 'seal.json', json.dumps({'files': pins}))
                self.assertTrue(self.check()['passed'])

    def test_extensionless_direct_sources_map_and_conflicting_hashes(self):
        source = self.write(self.packet / 'Makefile', 'frozen')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        self.write(self.packet / 'compiler-sources.json', json.dumps({'Makefile': digest}))
        self.assertTrue(self.check()['passed'])
        self.seal(self.packet / 'build-receipt.json', source, digest='a' * 64)
        with self.assertRaisesRegex(guard.PinRefusal, 'hash changed'):
            self.check()

    def test_completed_evidence_symlink_cannot_allow_mutable_source(self):
        source = self.write(self.stage / 'packet58w-onecard-record/verify_ready.py', 'mutable')
        folder = self.stage / 'packet58w-onecard-record/evidence/card0-a/WS'
        self.write(folder / 'window.json', json.dumps(dict(
            passed=True, device_executed=True, finished_utc_ns=123)))
        link = folder / 'verifier.py'
        link.symlink_to(source)
        self.seal(self.packet / 'ready.json', link, 'screen_sources')
        with self.assertRaisesRegex(guard.PinRefusal, 'cross-packet mutable'):
            self.check()

    def test_null_seal_refuses(self):
        self.write(self.packet / 'screen-seal.json', 'null')
        with self.assertRaisesRegex(guard.PinRefusal, 'object or list'):
            self.check()

    def test_extensionless_binary_in_artifact_map_is_checked(self):
        binary = self.write(self.packet / 'build/device/engine', 'binary')
        self.write(self.packet / 'build-receipt.json', json.dumps(
            {'artifacts': {'build/device/engine': '0' * 64}}))
        with self.assertRaisesRegex(guard.PinRefusal, 'hash changed'):
            self.check()

    def test_plan_command_prints_explicit_refusal_without_packet_writes(self):
        queue = self.root / 'queue'
        queue.mkdir()
        (queue / 'queue-A.txt').write_text(json.dumps(self.job) + '\n')
        external = self.write(self.stage / 'packet58w-onecard-record/verify_ready.py', 'mutable')
        self.seal(self.packet / 'build-receipt.json', external)
        with patch.object(q, 'ROOT', self.root), patch.object(q, 'STAGE', self.stage), \
             patch.object(q, 'cpu_setup'), patch.object(q, 'library_path', return_value='/unused'), \
             patch.object(q.sys, 'argv', ['lanequeue.py', 'plan', '--lane', 'A', '--directory', str(queue)]), \
             patch('sys.stdout', new_callable=io.StringIO) as out:
            self.assertEqual(q.main(), 1)
        self.assertFalse(json.loads(out.getvalue())['refusal_receipt']['launch_attempted'])
        self.assertFalse(list(self.packet.glob('*refusal*')))


class QueuePinTests(QueueTestCase):
    def setup_packet(self):
        packet = q.STAGE / 'packet58x-cache-capacity'
        packet.mkdir(parents=True)
        script = packet / 'queue_runner.py'
        script.write_text('frozen')
        digest = hashlib.sha256(script.read_bytes()).hexdigest()
        q.save(packet / 'build-receipt.json', {'sources': {str(script): digest}})
        job = self.job('packet58x-smoke-A')
        job['argv'] = ['/usr/bin/python3', '-B', str(script)]
        return job, script

    def test_changed_during_preparation_refuses_and_continues_without_launch(self):
        job, script = self.setup_packet()
        self.write([job, self.job('dependent', depends_on=[job['name']]), self.job('independent')])
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        def plan(row, _):
            REAL_CHECK(row)
            if row['name'] == job['name']:
                script.write_text('edited after plan')
            return {'host_required_available_bytes': 0}
        with patch.object(q, 'plan_job', side_effect=plan), patch.object(q, 'check_pins', side_effect=REAL_CHECK):
            self.assertEqual(self.queue.run(), 0)
        self.assertEqual(len(self.backend.runs), 1)
        self.assertEqual([r['outcome'] for r in self.done()],
                         ['REFUSED-PREDEVICE', 'SKIPPED-DEPENDENCY', 'DONE'])
        receipt = json.loads(Path(self.done()[0]['receipt']).read_text())
        self.assertFalse(receipt['launch_attempted'])
        self.assertFalse(self.queue.active.exists())
        self.assertNotIn(('START', {'name': job['name']}), self.events)

    def test_plan_refusal_uses_same_continuation(self):
        job, script = self.setup_packet()
        script.write_text('already changed')
        self.write([job, self.job('independent')])
        self.backend.after = lambda: (self.root / 'STOP-A').touch()
        with patch.object(q, 'plan_job', side_effect=lambda row, _: REAL_CHECK(row)), \
             patch.object(q, 'check_pins', side_effect=REAL_CHECK):
            self.assertEqual(self.queue.run(), 0)
        self.assertEqual(len(self.backend.runs), 1)
        self.assertEqual(self.done()[0]['outcome'], 'REFUSED-PREDEVICE')

    def test_stop_during_hashing_prevents_launch_and_inflight(self):
        job, _ = self.setup_packet()
        self.write([job])
        def check(_):
            (self.root / 'STOP-A').touch()
            return {'passed': True}
        with patch.object(q, 'check_pins', side_effect=check):
            self.assertEqual(self.queue.run(), 0)
        self.assertEqual(self.backend.runs, [])
        self.assertFalse(self.queue.active.exists())


if __name__ == '__main__':
    unittest.main()
