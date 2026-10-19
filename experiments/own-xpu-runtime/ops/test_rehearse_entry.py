"""Real proposal parsing and mocked/native CPU entry, never a service launch."""
import contextlib
import ast
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import launch_env
import rehearse_entry as entry


class RehearsalTest(unittest.TestCase):
    def setUp(self):
        self.queue = entry.lanequeue()
        self.path = Path('/usr/bin/true').resolve()
        self.spec = dict(path=str(self.path), sha256=entry.digest(self.path),
                         args=['--version'], returncode=0, contains='coreutils')
        self.job = dict(name='loader-test-B', lane='B', argv=['/usr/bin/true'],
                        plan=dict(entry_rehearsal=dict(binaries=[self.spec])))

    def test_exact_lanequeue_environment_and_unit_without_service(self):
        calls = []
        def run(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(argv[:2], ['/usr/bin/env', '-i'])
            self.assertNotIn('/usr/bin/systemd-run', argv)
            self.assertIn('LD_LIBRARY_PATH=' + launch_env.library_path(), argv)
            return subprocess.CompletedProcess(argv, 0, 'GNU coreutils', '')
        with patch.object(self.queue, 'command', wraps=self.queue.command) as command:
            result = entry.rehearse(self.job, self.queue, launch_env.library_path(), runner=run)
        self.assertTrue(result['passed'])
        self.assertEqual(result['unit'], 'screen-loader-test-B')
        self.assertFalse(result['service_started'])
        self.assertFalse(result['arm_sequence_tested'])
        command.assert_called_once()
        self.assertEqual(len(calls), 2)

    def test_real_safe_native_version_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            proposal = Path(directory) / 'proposal.txt'
            proposal.write_text(json.dumps(self.job)+'\n')
            output = io.StringIO()
            with patch.object(entry, 'lanequeue', return_value=self.queue), \
                 patch.object(self.queue, 'library_path', return_value=launch_env.library_path()), \
                 patch('sys.argv', ['rehearse_entry.py', str(proposal)]), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(entry.main(), 0)
            self.assertIn('PASS screen-loader-test-B: 1/1', output.getvalue())

    def test_own_parser_refusal_counts_but_generic_error_does_not(self):
        self.spec.pop('args')
        def runner(output, code):
            return lambda argv, **kw: subprocess.CompletedProcess(argv,
                0 if '/usr/bin/ldd' in argv else code,
                '' if '/usr/bin/ldd' in argv else output, '')
        for output, code, expected in [('unknown option --help', 1, True),
                                       ('usage: native OPTIONS', 0, True),
                                       ('failed to open model', 1, False),
                                       ('', 0, False), ('missing libumf.so.1', 127, False)]:
            with self.subTest(output=output):
                result = entry.rehearse(self.job, self.queue, launch_env.library_path(), runner(output, code))
                self.assertEqual(result['passed'], expected)

    def test_packet_override_is_tested_and_missing_lib_blocks_entry(self):
        self.job['argv'] += ['--library-path', '/compiler-only']
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            self.assertIn('/usr/bin/ldd', argv)
            missing = 'LD_LIBRARY_PATH=/compiler-only' in argv
            return subprocess.CompletedProcess(argv, 0, 'libumf.so.1 => not found' if missing else '', '')
        result = entry.rehearse(self.job, self.queue, launch_env.library_path(), runner)
        self.assertFalse(result['passed'])
        self.assertTrue(result['packet_library_override'])
        self.assertEqual(len(calls), 2)

    def test_stale_binary_and_empty_inventory_fail_before_exec(self):
        for specs in ([{**self.spec, 'sha256': '0'*64}], []):
            self.job['plan']['entry_rehearsal']['binaries'] = specs
            with patch.object(entry.entry_sandbox, 'run', side_effect=AssertionError('must not run')) as runner:
                self.assertFalse(entry.rehearse(self.job, self.queue, launch_env.library_path(), runner)['passed'])
                runner.assert_not_called()

    def test_script_coordinator_fails_instead_of_guessing_environment(self):
        self.job.pop('argv')
        self.job['script'] = __file__
        result = entry.rehearse(self.job, self.queue, launch_env.library_path())
        self.assertFalse(result['passed'])

    def test_proposal_error_does_not_leak_secret(self):
        self.job['env_extra'] = {'PASSWORD': 'secret-value'}
        result = entry.rehearse(self.job, self.queue, launch_env.library_path())
        self.assertFalse(result['passed'])
        self.assertNotIn('secret-value', json.dumps(result))

    def test_malformed_declaration_is_a_job_failure(self):
        self.job['plan']['entry_rehearsal'] = []
        result = entry.rehearse(self.job, self.queue, launch_env.library_path())
        self.assertFalse(result['passed'])


class GateIdentityTest(unittest.TestCase):
    STAGE = entry.ROOT / 'experiments/own-xpu-runtime/stage2'

    def scan(self, source, lane='A', name='packet58ai-census-c-smoke-A'):
        return entry.gate_identity(dict(name=name, lane=lane),
                                   {Path('gate.py'): ast.parse(source)})

    def proposal(self, filename):
        path = entry.OPS / 'lane-queue' / filename
        return next(json.loads(line) for line in path.read_text().splitlines()
                    if line.strip() and not line.lstrip().startswith('#'))

    def test_packet58ai_before_fix_refuses_current_name_fixed_gate_passes(self):
        path = self.STAGE / 'packet58ai-miss-census/coordinator_gate.py'
        source = subprocess.check_output(['git', '-c', 'core.packedGitWindowSize=16m',
            '-c', 'core.packedGitLimit=64m', 'show',
            'a032d73a6^:' + str(path.relative_to(entry.ROOT))], cwd=entry.ROOT,
            text=True, stdin=subprocess.DEVNULL)
        job = self.proposal('proposed-p58ai-census-A.txt')
        for text, expected in ((source, False), (path.read_text(), True)):
            result = entry.gate_identity(job, {path: ast.parse(text)})
            self.assertEqual(result['passed'], expected, result)
            if not expected:
                self.assertEqual(result['status'], 'FAIL')
                self.assertEqual(len(result['findings']), 2)
                self.assertTrue(all(r['reason'] == 'foreign job literal' for r in result['findings']))

    def test_packet151_real_readiness_rejects_a_accepts_b(self):
        path = self.STAGE / 'packet151-sibling-cost/v5/readiness.py'
        sources = {path: ast.parse(path.read_text())}
        for lane, status in [('A', 'FAIL'), ('B', 'PASS')]:
            result = entry.gate_identity(dict(name='packet151-sibling-smoke-' + lane, lane=lane), sources)
            self.assertEqual(result['status'], status, result)

    def test_current_fixed_packet_trees_have_no_identity_refusals(self):
        for filename in ('proposed-p58ai-census-A.txt', 'proposed-p151-smoke-B.txt',
                         'proposed-p151-v5-B.txt', 'proposed-p153-smoke-B.txt',
                         'proposed-p154-smoke-B.txt'):
            with self.subTest(proposal=filename):
                job = self.proposal(filename)
                packet, _ = entry.packet_sources(job)
                result = entry.gate_identity(job, entry.gate_sources(packet))
                self.assertTrue(result['passed'], result)
                self.assertGreater(result['files_scanned'], 1)

    def test_exact_jobs_units_service_suffix_and_no_secret_echo(self):
        for literal, passed in [
                ('packet58ai-census-c-smoke-A', True),
                ('packet58ai-census-A', False),
                ('screen-packet58ai-census-c-smoke-A', True),
                ('screen-packet58ai-census-c-smoke-A.service', True),
                ('screen-packet58ai-census-c-smoke-B.service', False),
                ('packet58-onecard-58ad-a.service', False)]:
            with self.subTest(literal=literal):
                result = self.scan(f'assert current == {literal!r}, "secret-error-text"')
                self.assertEqual(result['passed'], passed, result)
                self.assertNotIn('secret-error-text', json.dumps(result))
                self.assertNotIn(literal, json.dumps(result))

    def test_unclassified_literals_warn_and_do_not_refuse(self):
        for source in [
                "message = 'old packet58ai-census-A requires inspection'",
                "unit = 'screen-packet58ai-' + suffix",
                "unit = f'screen-packet58ai-{suffix}'",
                "command = ['--unit=packet58-onecard-58ad-a']",
                "proposal = dict(name='packet58ai-census-A')",
                "require(lane == 'B', 'only when overlapping')",
                "assert lane == 'B' or override"]:
            with self.subTest(source=source):
                result = self.scan(source)
                self.assertEqual(result['status'], 'WARN', result)
                self.assertTrue(result['passed'])
                self.assertTrue(result['warnings'])

    def test_lane_boolean_assertions_guards_and_dispatch(self):
        for source, passed in [
                ("assert lane == 'B' and variant == 'sibling'", False),
                ("assert 'B' == args.lane", False),
                ("assert job['lane'] != 'A'", False),
                ("assert job.get('lane') in ('A', 'B')", True),
                ("assert not (lane == 'A')", False),
                ("if lane != 'B':\n raise ValueError('wrong lane')", False),
                ("if lane == 'A':\n raise ValueError('wrong lane')", False),
                ("if lane == 'B':\n run()\nelse:\n raise ValueError('wrong lane')", False),
                ("if lane == 'B':\n run()", True),
                ("if overlap:\n assert lane == 'B'", True),
                ("for lane in ('A', 'B'):\n assert lane == 'B'", True)]:
            with self.subTest(source=source):
                self.assertEqual(self.scan(source)['passed'], passed)

    def test_unimported_gates_scanned_lineage_and_symlinks_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / 'packet-test'
            packet.mkdir()
            (packet / 'entry.py').write_text('')
            (packet / 'coordinator_gate.py').write_text("assert job == 'packet58ai-census-A'")
            for name in ('lineage', 'lineage-inputs', 'nested/lineage-old'):
                path = packet / name
                path.mkdir(parents=True)
                (path / 'bad.py').write_text('this is invalid Python!')
            outside = root / 'outside'
            outside.mkdir()
            (outside / 'bad.py').write_text('invalid Python!')
            (packet / 'linked').symlink_to(outside, target_is_directory=True)
            (packet / 'linked.py').symlink_to(outside / 'bad.py')
            sources = entry.gate_sources(packet)
            self.assertEqual(len(sources), 2)
            self.assertFalse(entry.gate_identity(dict(name='packet58ai-census-c-smoke-A', lane='A'), sources)['passed'])

    def test_both_modes_and_json_cli_require_identity_check(self):
        base = RehearsalTest()
        base.setUp()
        base.job.update(name='packet999-probe-A', lane='A')
        runner = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, 'GNU coreutils', '')
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / 'packet999-test'
            packet.mkdir()
            script = packet / 'entry.py'
            script.write_text("assert lane == 'B'\n")
            base.job['argv'] = ['/usr/bin/python3', '-B', str(script)]
            proposal = Path(directory) / 'proposal.txt'
            proposal.write_text(json.dumps(base.job))
            for report in (False, True):
                with patch.object(entry, 'rehearse_report', return_value=dict(passed=True)):
                    result = entry.rehearse(base.job, base.queue, launch_env.library_path(), runner, report=report)
                self.assertEqual(result['gate_identity']['status'], 'FAIL', result)
                self.assertFalse(result['passed'])
                self.assertTrue(all(b['passed'] for b in result['binaries']))
                out, err = io.StringIO(), io.StringIO()
                with patch.object(entry, 'rehearse', return_value=result), \
                     patch.object(entry, 'lanequeue', return_value=base.queue), \
                     patch.object(base.queue, 'library_path', return_value=launch_env.library_path()), \
                     patch('sys.argv', ['rehearse_entry.py', str(proposal), '--json', *(['--report'] if report else [])]), \
                     contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(entry.main(), 1)
                self.assertIn('gate_identity', err.getvalue())
                self.assertEqual(json.loads(out.getvalue())['jobs'][0]['gate_identity']['status'], 'FAIL')


class ReportRehearsalTest(unittest.TestCase):
    PACKET = 'experiments/own-xpu-runtime/stage2/packet142-class-layout'
    FIX = '3d08f0a2289b32e5bb892df60690287c12e4110b'

    def job(self, script):
        return dict(name='report-test-B', lane='B', argv=[
            '/usr/bin/python3', '-B', str(script), '--variant', 'attention-order600',
            '--kind', 'smoke', '--lane', 'B', '--output', '/must-not-write',
            '--authorized-device-window'])

    def historical_copy(self, root, revision):
        # No checkout/worktree and no packet writes. Only source and its small
        # import-time registry, never retained model/device/oracle evidence.
        names = subprocess.check_output(['git', '-c', 'core.packedGitWindowSize=16m', '-c', 'core.packedGitLimit=64m', 'ls-tree', '-r', '--name-only',
            revision, '--', self.PACKET,
            'experiments/own-xpu-runtime/stage1/packet4-prep/driver/window_driver.py'], cwd=entry.ROOT, text=True).splitlines()
        for name in names:
            if not (name.endswith('.py') or name.endswith(('/kernel-registry.json', '/launch-environment.json'))):
                continue
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(subprocess.check_output(['git', '-c', 'core.packedGitWindowSize=16m', '-c', 'core.packedGitLimit=64m', 'show', revision + ':' + name],
                                                       cwd=entry.ROOT))
        return root / self.PACKET / 'v5/bracket_job.py'

    def test_history_before_fix_fails_and_after_fix_passes_both_reports(self):
        for revision, passed in [(self.FIX + '^', False), (self.FIX, True)]:
            with self.subTest(revision=revision), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                script = self.historical_copy(root, revision)
                result = entry.rehearse_report(self.job(script), launch_env.environment(), root)
                self.assertEqual(result['passed'], passed, result)
                self.assertEqual([r['kind'] for r in result['kinds']], ['smoke', 'bracket'])
                if passed:
                    self.assertTrue(all(r['real_entry_main'] for r in result['kinds']), result)
                if not passed:
                    self.assertEqual(result['kinds'][0]['error_type'], 'ImportError', result)
                    self.assertTrue(all(r['collisions'] for r in result['kinds']), result)

    def test_collision_even_when_unused_schema_errors_and_no_model_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.historical_copy(root, self.FIX)
            job = self.job(script)
            top = script.parent.parent / 'unused_collision.py'
            shadow = script.parent / top.name
            top.write_text('VALUE = 1\n')
            shadow.write_text('VALUE = 2\n')
            result = entry.rehearse_report(job, launch_env.environment(), root)
            self.assertFalse(result['passed'])
            self.assertTrue(all(r['report_completed'] for r in result['kinds']), result)
            self.assertEqual(result['kinds'][0]['collisions'][0]['module'], 'unused_collision')
            top.unlink()
            shadow.unlink()
            screen = script.with_name('screen.py')
            source = screen.read_text()
            for statement, error in [
                    ("raise AttributeError('secret-error-text')", 'AttributeError'),
                    ("raise KeyError('secret-error-text')", 'KeyError'),
                    ("open('/mnt/model.safetensors', 'rb')", 'PermissionError'),
                    ("__import__('subprocess').run(['/usr/bin/true'])", 'PermissionError'),
                    ("open('/tmp/opsreview5-forbidden-write', 'w')", 'PermissionError')]:
                with self.subTest(statement=statement):
                    screen.write_text(source.replace('def report_completed(output, record, identity, coordination):',
                        'def report_completed(output, record, identity, coordination):\n    ' + statement))
                    result = entry.rehearse_report(job, launch_env.environment(), root)
                    self.assertFalse(result['passed'], result)
                    self.assertTrue(all(r['error_type'] == error for r in result['kinds']), result)
                    self.assertNotIn('secret-error-text', json.dumps(result))

    def test_report_gate_is_required_in_combined_result(self):
        base = RehearsalTest()
        base.setUp()
        runner = lambda argv, **kw: subprocess.CompletedProcess(argv, 0, 'GNU coreutils', '')
        with patch.object(entry, 'rehearse_report', return_value=dict(passed=False)) as report:
            result = entry.rehearse(base.job, base.queue, launch_env.library_path(), runner, report=True)
        self.assertFalse(result['passed'])
        self.assertTrue(all(b['passed'] for b in result['binaries']))
        report.assert_called_once()

    def test_static_packages_and_off_path_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in ('shared.py', 'v5/shared/__init__.py', 'unused/shared.py'):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('')
            rows = entry.duplicate_modules(root, [str(root), str(root / 'v5')])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['module'], 'shared')
            self.assertEqual(rows[0]['shadow'], str(root / 'v5/shared/__init__.py'))

    def test_unsupported_entry_fails(self):
        result = entry.rehearse_report(dict(argv=['/usr/bin/true']), launch_env.environment())
        self.assertFalse(result['passed'])


class OnecardReportTest(unittest.TestCase):
    PACKET = Path('experiments/own-xpu-runtime/stage2/packet58ab-onecard-hcfusion')

    def proposal(self, packet='58ab', arm='smoke'):
        path = entry.OPS / 'lane-queue' / f'proposed-p{packet}-{arm}-A.txt'
        return next(json.loads(s) for s in path.read_text().splitlines() if s.startswith('{'))

    def source_copy(self, root, relative=None):
        relative = relative or self.PACKET
        packet = entry.ROOT / relative
        sources = [*packet.glob('*.py'), packet / 'admission.json',
                   packet / 'host-admission/memory_plan.py',
                   packet.parent / 'packet49-integrate/oracle/suite_check.py']
        for source in sources:
            if not source.exists():
                continue
            target = root / source.relative_to(entry.ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        job = self.proposal()
        job['argv'][2] = str(root / relative / 'queue_runner.py')
        return job

    def test_screen_proposals_and_first_view_warmup_policy(self):
        for packet in ('58x', '58ab'):
            for arm in ('smoke', 'v5'):
                with self.subTest(packet=packet, arm=arm):
                    result = entry.rehearse_report(self.proposal(packet, arm), launch_env.environment())
                    self.assertTrue(result['passed'], result)
                    smoke, bracket = result['kinds']
                    self.assertEqual((smoke['request_count'], bracket['request_count']), (12, 60))
                    self.assertTrue(all(r['real_entry_main'] and not r['admission_executed']
                                        and not r['device_executed'] for r in result['kinds']))
                    self.assertTrue(bracket['candidate_beats_all_controls'])
                    self.assertEqual(bracket['comparison_controls'], ['A1', 'A2'])
                    self.assertEqual(bracket['warmup_view']['rate'], 10.)
                    self.assertTrue(bracket['warmup_view']['exact'])

    def test_packet58v_real_import_failure_is_not_hidden(self):
        # Its launch_identity imports today's lanequeue by file without adding
        # lanequeue's directory. The new pin_guard import genuinely fails in
        # the real entry environment; the rehearsal must not repair sys.path.
        result = entry.rehearse_report(self.proposal('58v'), launch_env.environment())
        self.assertFalse(result['passed'], result)
        self.assertTrue(all(r['error_type'] == 'ModuleNotFoundError' for r in result['kinds']), result)
        self.assertTrue(all(r['locations'][-1]['file'] == 'lanequeue.py' for r in result['kinds']), result)

    def test_packet58v_report_schema_with_private_import_path_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied = self.source_copy(root, self.PACKET.parent / 'packet58v-async-cache')
            job = self.proposal('58v')
            job['argv'][2] = copied['argv'][2]
            for name in ('packet56-draft-prefix/p56_head_support.py',
                         'packet56-draft-prefix/suite_metrics.py', 'packet34-replay-bench/window.py'):
                source = entry.ROOT / self.PACKET.parent / name
                target = root / source.relative_to(entry.ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            for name in ('lanequeue.py', 'pin_guard.py'):
                source = entry.OPS / 'lane-queue' / name
                target = root / source.resolve().relative_to(entry.ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
            script = Path(job['argv'][2])
            # Fixture-only repair of the known import failure above, so the
            # older comparison policy itself is covered. Live packet unchanged.
            script.write_text('import sys\nfrom pathlib import Path\nsys.path.append('
                'str(Path(__file__).resolve().parents[2] / "ops/lane-queue"))\n' + script.read_text())
            result = entry.rehearse_report(job, launch_env.environment(), root)
            self.assertTrue(result['passed'], result)
            self.assertFalse(result['kinds'][1]['candidate_beats_all_controls'])
            self.assertIsNone(result['kinds'][1]['warmup_view'])

    def test_packet58z_record_window_reports(self):
        script = entry.ROOT / self.PACKET.parent / 'packet58z-onecard-record/queue_runner.py'
        job = dict(name='packet58z-report-A', lane='A', argv=[
            '/usr/bin/python3', '-B', str(script), '--output-root', '/must-not-write',
            '--view', 'down-tile16'])
        result = entry.rehearse_report(job, launch_env.environment())
        self.assertTrue(result['passed'], result)
        self.assertEqual([r['kind'] for r in result['kinds']], ['WS128x', 'WS128'])
        self.assertTrue(all(r['report_completed'] and r['request_count'] == 12 for r in result['kinds']))

    def test_late_import_collision_fails_on_private_source_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = self.source_copy(root)
            script = Path(job['argv'][2])
            self.assertTrue(entry.rehearse_report(job, launch_env.environment(), root)['passed'])
            shadow = script.parent / 'shadow'
            shadow.mkdir()
            (shadow / 'compare_bracket.py').write_text('VALUE = 1\n')
            script.write_text('import sys\nfrom pathlib import Path\nsys.path.insert(0, '
                              'str(Path(__file__).parent / "shadow"))\n' + script.read_text())
            result = entry.rehearse_report(job, launch_env.environment(), root)
            self.assertFalse(result['passed'], result)
            # Smoke imports compare even though it does not call it.
            self.assertTrue(all(r['error_type'] == 'ImportError' for r in result['kinds']), result)

    def test_unused_collision_and_report_isolation_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = self.source_copy(root)
            script = Path(job['argv'][2])
            shadow = script.parent / 'shadow'
            shadow.mkdir()
            for target in (script.parent, shadow):
                (target / 'unused.py').write_text('VALUE = 1\n')
            source = script.read_text()
            script.write_text('import sys\nfrom pathlib import Path\nsys.path.append('
                              'str(Path(__file__).parent / "shadow"))\n' + source)
            result = entry.rehearse_report(job, launch_env.environment(), root)
            self.assertFalse(result['passed'], result)
            self.assertTrue(all(r['report_completed'] and r['collisions'] for r in result['kinds']), result)
            script.write_text(source)
            driver = script.with_name('suite_driver.py')
            source = driver.read_text()
            for statement, error in [
                    ("raise KeyError('secret-error-text')", 'KeyError'),
                    ("open('/mnt/model.safetensors', 'rb')", 'PermissionError'),
                    ("__import__('subprocess').run(['/usr/bin/true'])", 'PermissionError'),
                    ("open('/tmp/opsreview6-forbidden-write', 'w')", 'PermissionError')]:
                with self.subTest(statement=statement):
                    driver.write_text(source.replace('    views=[];arenas=set();weights=set();signature=None',
                        '    ' + statement + '\n    views=[];arenas=set();weights=set();signature=None'))
                    result = entry.rehearse_report(job, launch_env.environment(), root)
                    self.assertFalse(result['passed'], result)
                    self.assertTrue(all(r['error_type'] == error for r in result['kinds']), result)
                    self.assertNotIn('secret-error-text', json.dumps(result))

    def test_a0_tokens_still_checked_and_window_tail_is_real(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = self.source_copy(root)
            driver = Path(job['argv'][2]).with_name('suite_driver.py')
            source = driver.read_text()
            driver.write_text(source.replace("    result=read(actual/'result.json')",
                "    result=read(actual/'result.json')\n    if actual.parent.name == 'A0': result['tokens'][0] = 999"))
            result = entry.rehearse_report(job, launch_env.environment(), root)
            self.assertTrue(result['kinds'][0]['passed'], result)
            self.assertFalse(result['kinds'][1]['passed'], result)
            self.assertEqual(result['kinds'][1]['error_type'], 'ValueError')
            driver.write_text(source)
            window = driver.with_name('window.py')
            window.write_text(window.read_text().replace("            summary['evidence_label'] = 'screen'",
                "            raise KeyError('secret-error-text')\n            summary['evidence_label'] = 'screen'"))
            result = entry.rehearse_report(job, launch_env.environment(), root)
            self.assertFalse(result['passed'], result)
            self.assertTrue(all(r['error_type'] == 'KeyError' for r in result['kinds']), result)


class PackagingTest(unittest.TestCase):
    STAGE = entry.ROOT / 'experiments/own-xpu-runtime/stage2'

    def blob(self, revision, path):
        return subprocess.check_output(['git', '-c', 'core.packedGitWindowSize=16m',
            '-c', 'core.packedGitLimit=64m', 'show', revision + ':' + str(path.relative_to(entry.ROOT))],
            cwd=entry.ROOT, text=True, stdin=subprocess.DEVNULL)

    def test_packet153_original_deadline_and_fixed_source(self):
        path = self.STAGE / 'packet153-snapshot-host/v5/analyze.py'
        for source, passed in [(self.blob('3813d8dd9^', path), False), (path.read_text(), True)]:
            result = entry.deadline_scan({path: ast.parse(source)}, {'first_request': 60.})
            self.assertEqual(result['passed'], passed, result)
            if not passed:
                self.assertEqual(len(result['findings']), 2)
                self.assertTrue(all(r['data_proof'] for r in result['findings']))

    def test_packet154_original_floor_and_fixed_source(self):
        path = self.STAGE / 'packet154-rank1-split/v5/screen.py'
        for source, passed in [(self.blob('80d3d7434^', path), False), (path.read_text(), True)]:
            result = entry.storage_scan({path: ast.parse(source)})
            self.assertEqual(result['passed'], passed, result)
            self.assertEqual(len(result['admissions']), 2)
            if not passed:
                self.assertTrue(all(r['message_value_mismatch'] for r in result['findings']))
                self.assertTrue(all(not r['passes_25_5gb_plus_writes'] for r in result['findings']))

    def test_packet58ai_floor_is_caught_through_real_entry(self):
        script = self.STAGE / 'packet58ai-miss-census/queue_runner.py'
        packet, sources = entry.packet_sources(dict(argv=['python3', '-B', str(script)]))
        result = entry.storage_scan(sources)
        self.assertTrue(result['passed'], result)
        # The live packet was repaired; keep the old refusal as a pinned
        # regression instead of requiring the live packet to remain broken.
        window = script.with_name('window.py')
        sources[window] = ast.parse(self.blob('60a56785a^', window))
        result = entry.storage_scan(sources)
        self.assertTrue(any(Path(r['file']).name == 'window.py' and r['floor_bytes'] == 30_000_000_000
                            for r in result['findings']), result)
        self.assertFalse(any('lineage' in str(p.relative_to(packet)) for p in sources))

    def test_current_entry_paths_include_report_and_exclude_builds(self):
        for number, name in [(153, 'snapshot-host'), (154, 'rank1-split')]:
            script = self.STAGE / f'packet{number}-{name}/v5/bracket_job.py'
            packet, sources = entry.packet_sources(dict(argv=['python3', '-B', str(script)]))
            if number == 153:
                self.assertIn(script.with_name('analyze.py'), sources)
            self.assertIn(script.with_name('screen.py'), sources)
            self.assertTrue(entry.storage_scan(sources)['passed'])
            self.assertTrue(entry.deadline_scan(sources, {'first_request': 60})['passed'])
            self.assertFalse(any('build' in p.name for p in sources))

    def test_phase_bounds_and_data_proof_never_has_deadline(self):
        source = '''
import time
def first_request():
    require(elapsed_seconds <= 119, 'cold request')
    proc.wait(timeout=119)
    deadline = time.monotonic() + 119
def load_model():
    proc.wait(timeout=599)
def load_ok():
    proc.wait(timeout=600)
def data_proof():
    require(proof['seconds_after_view_start'] <= 9999, 'proof')
def systemctl():
    proc.wait(timeout=10)
'''
        result = entry.deadline_scan({Path('entry.py'): ast.parse(source)},
                                     {'first_request': 60, 'load': 300})
        self.assertEqual(len(result['findings']), 5, result)
        self.assertEqual(len(result['limits']), 6, result)

    def test_storage_constants_arithmetic_and_message_mismatch(self):
        source = '''
FLOOR = 25 * 10**9
def storage(path, writes):
    free = shutil.disk_usage('/').free
    require(free - writes >= FLOOR, '30 GB floor')
'''
        result = entry.storage_scan({Path('entry.py'): ast.parse(source)})
        self.assertFalse(result['passed'])
        self.assertTrue(result['findings'][0]['message_value_mismatch'])
        self.assertTrue(result['findings'][0]['passes_25_5gb_plus_writes'])

    def test_dynamic_data_proof_deadlines_and_saved_phase_maxima(self):
        source = '''
def data_proof():
    assert elapsed_seconds <= configured_limit
    proc.wait(timeout=allowed_seconds)
def first_request():
    deadline = started + 80
'''
        result = entry.deadline_scan({Path('analyze.py'): ast.parse(source)}, {'first_request': 60})
        self.assertEqual(len(result['findings']), 3, result)
        with tempfile.TemporaryDirectory(dir=entry.OPS, prefix='.timing-test-') as directory:
            evidence = Path(directory) / 'timings.json'
            evidence.write_text(json.dumps(dict(load_seconds=200, ranks=[
                dict(load_ms=310000), dict(load=dict(seconds=290)),
                dict(phase='load', duration_seconds=305)], expected_seconds=9000)))
            job = dict(plan=dict(entry_rehearsal=dict(timing_evidence=[str(evidence)])))
            self.assertEqual(entry.measured_phases(job), {'first_request': 60., 'load': 310.})

    def test_unit_storage_floor_and_unreachable_vendor_copy(self):
        result = entry.storage_scan({Path('screen.py'): ast.parse(
            "assert free_gb - writes_gb >= 30, '25 GB floor'\n")})
        self.assertEqual(result['findings'][0]['floor_bytes'], 30_000_000_000)
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / 'packet-fixture'
            packet.mkdir()
            (packet / 'entry.py').write_text("import screen\n")
            (packet / 'screen.py').write_text("assert free >= 25_000_000_000\n")
            vendor = packet / 'lineage-old'
            vendor.mkdir()
            (vendor / 'screen.py').write_text("assert free >= 30_000_000_000\n")
            _, sources = entry.packet_sources(dict(argv=['python3', '-B', str(packet / 'entry.py')]))
            self.assertEqual(len(sources), 2)
            self.assertTrue(entry.storage_scan(sources)['passed'])

    def test_real_storage_helpers_and_import_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'storage.py'
            source = '''import shutil
def storage(output, planned_write_bytes):
    assert shutil.disk_usage('/').free - planned_write_bytes >= FLOOR
    return True
'''
            for floor, status in [('25_000_000_000', 'PASS'), ('30_000_000_000', 'FAIL')]:
                path.write_text(source.replace('FLOOR', floor))
                result = entry.replay_storage([dict(path=str(path), function='storage')], entry.launch_env.environment())
                self.assertEqual(result[0]['status'], status, result)
            path.write_text("open('/mnt/model.safetensors', 'rb')\n" + source.replace('FLOOR', '25_000_000_000'))
            result = entry.replay_storage([dict(path=str(path), function='storage')], entry.launch_env.environment())
            self.assertEqual(result[0]['status'], 'WARN', result)

    def test_both_modes_require_packaging_and_emit_fail_warn(self):
        base = RehearsalTest()
        base.setUp()
        failed = dict(storage_floor=entry.check_result([dict(line=1)]),
                      wall_deadlines=entry.check_result(), preparation_path=dict(
                          status='WARN', message='no preparation-path probe declared'))
        for report_mode in (False, True):
            with patch.object(entry, 'packaging_checks', return_value=failed) as checks, \
                 patch.object(entry, 'rehearse_report', return_value=dict(passed=True)):
                result = entry.rehearse(base.job, base.queue, launch_env.library_path(),
                    runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, 'GNU coreutils', ''), report=report_mode)
                self.assertFalse(result['passed'])
                checks.assert_called_once()
        with tempfile.TemporaryDirectory() as directory:
            proposal = Path(directory) / 'proposal.txt'
            proposal.write_text(json.dumps(base.job))
            for json_mode in (False, True):
                out, err = io.StringIO(), io.StringIO()
                with patch.object(entry, 'rehearse', return_value=dict(result, **failed)), \
                     patch.object(entry, 'lanequeue', return_value=base.queue), \
                     patch.object(base.queue, 'library_path', return_value=launch_env.library_path()), \
                     patch('sys.argv', ['rehearse_entry.py', str(proposal), *(['--json'] if json_mode else [])]), \
                     contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(entry.main(), 1)
                text = err.getvalue() if json_mode else out.getvalue()
                self.assertIn('FAIL screen-loader-test-B: storage_floor', text)
                self.assertIn('WARN screen-loader-test-B: preparation_path: no preparation-path probe declared', text)
                if json_mode:
                    self.assertIn('storage_floor', json.loads(out.getvalue())['jobs'][0])

    def test_packet151_before_fix_warns_without_declared_probe(self):
        relative = Path('experiments/own-xpu-runtime/stage2/packet151-sibling-cost')
        with tempfile.TemporaryDirectory() as directory:
            # Retain the old source tree shape, never copy weights/builds/evidence.
            names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only',
                '5cb2362d9^', '--', str(relative)], cwd=entry.ROOT, text=True,
                stdin=subprocess.DEVNULL).splitlines()
            for name in names:
                if not name.endswith('.py') or any(p.startswith('lineage') for p in Path(name).parts):
                    continue
                target = Path(directory) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(self.blob('5cb2362d9^', entry.ROOT / name))
            script = Path(directory) / relative / 'v5/bracket_job.py'
            job = dict(argv=['python3', '-B', str(script)])
            result = entry.preparation_probe(job, script.parent.parent, launch_env.environment())
            self.assertEqual(result['status'], 'WARN', result)
            self.assertEqual(result['message'], 'no preparation-path probe declared')

    def test_packet151_retained_old_binary_fails_and_fixed_passes(self):
        packet = self.STAGE / 'packet151-sibling-cost'
        if not (packet / 'v5/build/preparation/fixed/fixture').is_file():
            self.skipTest('retained CPU preparation binaries not installed')
        job = json.loads((entry.OPS / 'lane-queue/proposed-p151-smoke-B.txt').read_text())
        spec = entry.declared_preparation(job, packet)
        for mode, passed in [('old', False), ('fixed', True)]:
            binary = packet / f'v5/build/preparation/{mode}/fixture'
            declared = dict(spec, command=[str(binary), *spec['rank_argv'][1:]], sha256=entry.digest(binary))
            with self.subTest(mode=mode), patch.object(entry, 'declared_preparation', return_value=declared):
                result = entry.preparation_probe(job, packet, launch_env.environment())
            self.assertEqual(result['passed'], passed, result)
            self.assertEqual(result['preparation_bypassed'], not passed, result)

    def test_packet151_current_report_uses_real_sibling_analysis(self):
        job = json.loads((entry.OPS / 'lane-queue/proposed-p151-smoke-B.txt').read_text())
        result = entry.rehearse_report(job, launch_env.environment())
        self.assertTrue(result['passed'], result)
        self.assertTrue(all(r['report_completed'] and r['synthetic_evidence'] for r in result['kinds']))

    def test_explicit_preparation_declaration_runs_exact_argv_and_fails_closed(self):
        binary = Path('/usr/bin/true').resolve()
        rank = ['/device/real', '--rank', '0', '--context', '4096']
        spec = dict(command=[str(binary), *rank[1:]], rank_argv=rank,
                    sha256=entry.digest(binary), contains='first-decode-prepared')
        job = dict(plan=dict(entry_rehearsal=dict(prepare_probe=spec)))
        calls = []
        def runner(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(argv[argv.index(str(binary)) + 1:], rank[1:])
            self.assertEqual(kwargs['timeout'], 45)
            return subprocess.CompletedProcess(argv, 0, 'first-decode-prepared', '')
        result = entry.preparation_probe(job, None, launch_env.environment(), runner)
        self.assertTrue(result['passed'], result)
        self.assertEqual(len(calls), 1)
        spec['command'][-1] = '8'
        with self.assertRaises(ValueError):
            entry.preparation_probe(job, None, launch_env.environment(), runner)
        self.assertEqual(len(calls), 1)

    def test_preparation_sandbox_only_grants_declared_metadata(self):
        binary = Path('/usr/bin/cat')
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            scratch = Path(directory).resolve()
            metadata = Path(outside) / 'plan.tsv'
            forbidden = Path(outside) / 'model.bin'
            metadata.write_text('synthetic metadata\n')
            forbidden.write_text('must not be read\n')
            with patch.object(entry.entry_sandbox, 'restrict', side_effect=lambda b:
                              entry.prepare_restrict(Path(b), [metadata], scratch)):
                good = entry.entry_sandbox.run([str(binary), str(metadata)], binary=binary)
                bad = entry.entry_sandbox.run([str(binary), str(forbidden)], binary=binary)
            self.assertEqual(good.returncode, 0)
            self.assertEqual(good.stdout, 'synthetic metadata\n')
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual(bad.stdout, '')


if __name__ == '__main__':
    unittest.main()
