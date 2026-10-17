"""CPU control-plane tests: no devices, model reads, journal reads or launches."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import a367_glue01 as c


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='a367-glue01-admission-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.claims = self.root / 'claims'
        self.claims.mkdir()
        reg, seal = self.root / 'reg.json', self.root / 'seal.json'
        reg.write_text('{"test": "preregistration"}\n')
        seal.write_text('{"test": "seal"}\n')
        for mock in (patch.object(c, 'REG', reg), patch.object(c, 'SEAL', seal),
                     patch.object(c, 'claim_directory', return_value=self.claims, create=True),
                     patch.object(c.w.socket, 'gethostname', return_value='steve-b70s')):
            mock.start()
            self.addCleanup(mock.stop)

    def fixture(self, arm='control'):
        now = float(int(time.time()))
        stamp = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(now - 1))
        health = dict(schema='ltx.four-card-health.v1', passed=True, boot_id='test-boot',
                      kernel=Path('/proc/sys/kernel/osrelease').read_text().strip(),
                      start_utc=stamp, end_utc=stamp, device_count=4,
                      cards=[dict(device=f'xpu:{r}', **{'pass': True}) for r in range(4)],
                      journal_fault_lines_during_probe=[], fault_lines_earlier_this_boot=0)
        health_path = self.root / f'{arm}-health.json'
        c.w.write(health_path, health)
        campaign = self.root / 'campaign.json'
        plan = dict(preregistration_sha256=c.w.sha(c.REG), seal_sha256=c.w.sha(c.SEAL),
                    arms={a: str(self.root / (a + '-output')) for a in c.ARMS})
        c.w.write(campaign, plan)
        output = Path(plan['arms'][arm])
        owner = dict(schema='own-xpu-runtime.packet4.owner-window.v1', authorized=True,
                     boot_id='test-boot', host='steve-b70s',
                     preregistration_sha256=c.w.sha(c.w.PREREG),
                     health_path=str(health_path), health_sha256=c.w.sha(health_path),
                     output=str(output), halt_resolved=True,
                     pci_ids=['0000:23:00.0', '0000:27:00.0', '0000:43:00.0', '0000:47:00.0'],
                     firmware='cpu-test-only', issued_unix=now - 10, expires_unix=now + 3500,
                     previous_teardown_completed_unix=now - 307,
                     purpose='a367-glue01-screen', glue_arm=arm,
                     glue_preregistration_sha256=c.w.sha(c.REG), glue_seal_sha256=c.w.sha(c.SEAL),
                     campaign_path=str(campaign), campaign_sha256=c.w.sha(campaign))
        owner['glue_memory_exception'] = dict(approved=True, approved_by='owner',
            minimum_mem_available_kib=114_840_824, owner_approval_text=c.glue_approval_text())
        if arm == 'candidate':
            control = Path(plan['arms']['control'])
            control.mkdir(exist_ok=True)
            identity = dict(arm='control', seal_sha256=c.w.sha(c.SEAL),
                            preregistration_sha256=c.w.sha(c.REG), campaign_sha256=c.w.sha(campaign))
            stop = dict(completed_unix=now - 307)
            c.w.write(control / 'identity.json', identity)
            c.w.write(control / 'stop.json', stop)
            c.w.write(control / 'owner-window.json', {'health_sha256': 'earlier-control-health'})
            c.w.write(control / 'glue01-run.json', dict(passed=True, mock=False, clean_exit=True,
                gap_complete=True, all_owners_gone=True,
                identity_sha256=c.w.sha(control / 'identity.json'), stop_sha256=c.w.sha(control / 'stop.json')))
            c.w.write(self.claims / 'control.claimed.json', dict(arm='control',
                output=str(control), campaign_sha256=c.w.sha(campaign)))
        return owner, health, now, output

    def admit(self, fixture, *, available=114_840_824, rows=None, faults=None):
        owner, health, now, output = fixture
        with patch('compare.check_arm', return_value={'passed': True}) as checked:
            result = c.verify_admission(owner, health, 'test-boot', now, output,
                rows or [], faults or [], available, arm=owner['glue_arm'], kernel_log='')
        return result, checked

    def mutate_file(self, path, **updates):
        record = c.w.read(path)
        record.update(updates)
        c.w.write(path, record)

    def test_control_complete_admission_at_exact_floor(self):
        result, check = self.admit(self.fixture())
        self.assertIsNone(result['resolved_fault'])
        check.assert_not_called()

    def test_execute_without_receipts_cannot_launch(self):
        for arm in c.ARMS:
            with self.subTest(arm=arm), patch.object(c.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(ValueError, 'owner/health/payload'):
                    c.main(['--execute', '--output', str(self.root / 'unused'), '--arm', arm])
                launch.assert_not_called()
                self.assertFalse((self.root / 'unused').exists())

    def test_candidate_requires_checked_control(self):
        fixture = self.fixture('candidate')
        _, checked = self.admit(fixture)
        checked.assert_called_once_with(self.root / 'control-output', 'control')

    def test_unapproved_floor_defaults_to_refusal(self):
        fixture = self.fixture()
        del fixture[0]['glue_memory_exception']
        with self.assertRaisesRegex(ValueError, 'default refuses'):
            self.admit(fixture)

    def test_memory_exception_exact_fields_and_approval(self):
        variants = ({'approved': False}, {'approved_by': 'agent'},
                    {'minimum_mem_available_kib': 114_840_823},
                    {'minimum_mem_available_kib': 114_840_824.0},
                    {'owner_approval_text': 'approve everything'}, {'blanket_waiver': True})
        for changes in variants:
            with self.subTest(changes=changes):
                fixture = self.fixture()
                fixture[0]['glue_memory_exception'].update(changes)
                with self.assertRaises(ValueError):
                    self.admit(fixture)

    def test_one_kib_under_start_floor_refuses(self):
        with self.assertRaisesRegex(ValueError, 'floor'):
            self.admit(self.fixture(), available=114_840_823)

    def test_approval_sentence_binds_both_arms_and_current_hashes(self):
        sentence = c.glue_approval_text()
        for literal in ('A367 glue01 row-copy screen', 'one control then one candidate',
                        '114840824 KiB', '12000000 KiB', c.w.sha(c.REG), c.w.sha(c.SEAL)):
            self.assertIn(literal, sentence)
        fixture = self.fixture()
        c.SEAL.write_text('{"test": "new seal"}\n')
        fixture[0]['glue_seal_sha256'] = c.w.sha(c.SEAL)
        with self.assertRaisesRegex(ValueError, 'exact approval'):
            self.admit(fixture)

    def test_owner_prereg_seal_scope_bindings(self):
        for key in ('purpose', 'glue_preregistration_sha256', 'glue_seal_sha256',
                    'preregistration_sha256', 'boot_id', 'host', 'health_sha256'):
            with self.subTest(key=key):
                fixture = self.fixture()
                fixture[0][key] = 'wrong'
                with self.assertRaises(ValueError):
                    self.admit(fixture)

    def test_expired_or_future_owner_refuses(self):
        for key, delta in (('expires_unix', -1), ('issued_unix', 1)):
            fixture = self.fixture()
            fixture[0][key] = fixture[2] + delta
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.admit(fixture)

    def test_unapproved_owner_and_unresolved_halt_refuse(self):
        for key in ('authorized', 'halt_resolved'):
            fixture = self.fixture()
            fixture[0][key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.admit(fixture)

    def test_other_arm_cannot_use_control_owner(self):
        fixture = self.fixture()
        with self.assertRaisesRegex(ValueError, 'arm binding'):
            c.verify_admission(*fixture[:2], 'test-boot', fixture[2], fixture[3],
                               [], [], 114_840_824, arm='candidate', kernel_log='')

    def test_fixture_revision_is_not_approval(self):
        fixture = self.fixture()
        fixture[0]['admission_revision_sha256'] = 'old fixture'
        with self.assertRaisesRegex(ValueError, 'fixture revision'):
            self.admit(fixture)

    def test_output_reuse_and_process_conflicts_refuse(self):
        fixture = self.fixture()
        fixture[3].mkdir()
        with self.assertRaisesRegex(ValueError, 'output exists'):
            self.admit(fixture)
        fixture[3].rmdir()
        for name in ('ltx-stream', 'VLLM::Worker_TP0', 'ComfyUI'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'process running'):
                self.admit(fixture, rows=[(999, name, name)])

    def test_every_arm_requires_full_305s_gap(self):
        for arm in c.ARMS:
            fixture = self.fixture(arm)
            fixture[0]['previous_teardown_completed_unix'] = fixture[2] - 304
            with self.subTest(arm=arm), self.assertRaisesRegex(ValueError, '305-second'):
                self.admit(fixture)

    def test_failed_or_stale_health_refuses(self):
        for mutation in ({'passed': False}, {'end_utc': '2000-01-01 00:00:00 UTC'},
                         {'device_count': 3}, {'fault_lines_earlier_this_boot': 1}):
            fixture = self.fixture()
            fixture[1].update(mutation)
            c.w.write(fixture[0]['health_path'], fixture[1])
            fixture[0]['health_sha256'] = c.w.sha(fixture[0]['health_path'])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.admit(fixture)

    def test_candidate_health_must_start_after_control_gap(self):
        fixture = self.fixture('candidate')
        fixture[1]['start_utc'] = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(fixture[2] - 4))
        c.w.write(fixture[0]['health_path'], fixture[1])
        fixture[0]['health_sha256'] = c.w.sha(fixture[0]['health_path'])
        with self.assertRaisesRegex(ValueError, 'health|gap'):
            self.admit(fixture)

    def test_candidate_cannot_reuse_control_health_receipt(self):
        fixture = self.fixture('candidate')
        c.w.write(self.root / 'control-output/owner-window.json',
                  {'health_sha256': fixture[0]['health_sha256']})
        with self.assertRaisesRegex(ValueError, 'new health'):
            self.admit(fixture)

    def test_campaign_hash_and_identity(self):
        for mutation in ({'preregistration_sha256': 'wrong'}, {'seal_sha256': 'wrong'},
                         {'arms': {'control': '/same', 'candidate': '/same'}},
                         {'arms': {'control': '/control'}}):
            fixture = self.fixture()
            self.mutate_file(fixture[0]['campaign_path'], **mutation)
            fixture[0]['campaign_sha256'] = c.w.sha(fixture[0]['campaign_path'])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.admit(fixture)

    def test_campaign_payload_hash_drift(self):
        fixture = self.fixture()
        self.mutate_file(fixture[0]['campaign_path'], extra='unbound')
        with self.assertRaisesRegex(ValueError, 'campaign pin'):
            self.admit(fixture)

    def test_campaign_output_binding(self):
        fixture = self.fixture()
        plan = c.w.read(fixture[0]['campaign_path'])
        plan['arms']['control'] = str(self.root / 'different')
        c.w.write(fixture[0]['campaign_path'], plan)
        fixture[0]['campaign_sha256'] = c.w.sha(fixture[0]['campaign_path'])
        with self.assertRaisesRegex(ValueError, 'output binding'):
            self.admit(fixture)

    def test_claim_consumed_exactly_once(self):
        owner = self.fixture()[0]
        c.claim_arm(owner, 'control')
        self.assertTrue((self.claims / 'control.claimed.json').is_file())
        with self.assertRaisesRegex(ValueError, 'consumed|retry'):
            c.claim_arm(owner, 'control')

    def test_global_claim_not_bypassed_by_new_campaign_path(self):
        owner = self.fixture()[0]
        c.claim_arm(owner, 'control')
        other = self.root / 'new-coordinator'
        other.mkdir()
        other_campaign = other / 'campaign.json'
        other_campaign.write_bytes(Path(owner['campaign_path']).read_bytes())
        owner['campaign_path'] = str(other_campaign)
        owner['campaign_sha256'] = c.w.sha(other_campaign)
        with self.assertRaisesRegex(ValueError, 'consumed|retry'):
            c.claim_arm(owner, 'control')

    def test_candidate_failed_control_never_admits(self):
        mutations = ({'passed': False}, {'mock': True}, {'clean_exit': False},
                     {'gap_complete': False}, {'all_owners_gone': False},
                     {'identity_sha256': 'wrong'}, {'stop_sha256': 'wrong'})
        for mutation in mutations:
            fixture = self.fixture('candidate')
            self.mutate_file(self.root / 'control-output/glue01-run.json', **mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.admit(fixture)

    def test_candidate_control_identity_binding(self):
        for mutation in ({'arm': 'candidate'}, {'seal_sha256': 'wrong'},
                         {'preregistration_sha256': 'wrong'}, {'campaign_sha256': 'wrong'}):
            fixture = self.fixture('candidate')
            identity = self.root / 'control-output/identity.json'
            self.mutate_file(identity, **mutation)
            self.mutate_file(self.root / 'control-output/glue01-run.json', identity_sha256=c.w.sha(identity))
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.admit(fixture)

    def test_candidate_control_checker_failure_blocks(self):
        fixture = self.fixture('candidate')
        with patch('compare.check_arm', side_effect=ValueError('control quality failed')):
            with self.assertRaisesRegex(ValueError, 'control quality failed'):
                c.verify_campaign(fixture[0], 'candidate')

    def test_candidate_stop_receipt_binds_gap(self):
        fixture = self.fixture('candidate')
        fixture[0]['previous_teardown_completed_unix'] -= 1
        with self.assertRaisesRegex(ValueError, 'gap binding'):
            self.admit(fixture)

    def test_live_memory_reserve_is_independent_of_admission_floor(self):
        self.assertEqual(c.LIVE_FLOOR_KIB, 12_000_000)
        rows = [dict(monotonic=i / 2, phase='baseline' if i == 0 else 'loading',
                     mem_total_bytes=130_000_000 * 1024,
                     mem_available_bytes=(12_000_000 - i) * 1024) for i in range(2)]
        with self.assertRaisesRegex(ValueError, 'live reserve'):
            c.summarize(rows)


class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = c.HERE.parent / 'a367-replay/a367_replay.py'
        spec = importlib.util.spec_from_file_location('glue01_control_replay_reference', path)
        cls.replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.replay)

    def test_control_command_and_environment_exact_replay(self):
        output = Path('/cpu-only/unique-output')
        self.assertEqual(c.command_and_environment(output, 'control'),
                         self.replay.command_and_environment(output))

    def test_candidate_only_sanctioned_command_environment_changes(self):
        output = Path('/cpu-only/unique-output')
        control_command, control_env = c.command_and_environment(output, 'control')
        command, env = c.command_and_environment(output, 'candidate')
        self.assertEqual([i for i, (a, b) in enumerate(zip(command, control_command)) if a != b], [2])
        self.assertEqual(len(command), len(control_command))
        self.assertEqual(command[2], str(c.HERE / 'glue_entry.py'))
        changes = {key for key in control_env.keys() | env.keys() if control_env.get(key) != env.get(key)}
        self.assertEqual(changes, {'PACKET4_SOURCE', 'PYTHONPATH', 'Q38_M2_GLUE_ROW_COPY',
                                   'A367_GLUE_OPERATOR_RECEIPTS'})
        self.assertEqual(env['Q38_M2_GLUE_ROW_COPY'], '1')
        self.assertEqual(env['A367_GLUE_OPERATOR_RECEIPTS'], str(output / 'operator'))
        self.assertEqual(env['PACKET4_SOURCE'], str(c.paths('candidate')['source']))
        expected_pythonpath = str(c.HERE) + ':' + control_env['PYTHONPATH'].replace(
            str(c.paths('control')['source']), str(c.paths('candidate')['source']))
        self.assertEqual(env['PYTHONPATH'], expected_pythonpath)

    def test_source_preregistration_control_unchanged_candidate_one_delta(self):
        prereg = c.w.read(c.w.PREREG)
        frozen = copy.deepcopy(prereg)
        self.assertEqual(c.source_preregistration(prereg, 'control'), prereg)
        candidate = c.source_preregistration(prereg, 'candidate')
        from operator_gate import RELATIVE, CLEAN_SHA, CANDIDATE_SHA
        self.assertEqual(prereg['source_pins'][RELATIVE], CLEAN_SHA)
        self.assertEqual(candidate['source_pins'][RELATIVE], CANDIDATE_SHA)
        candidate['source_pins'][RELATIVE] = CLEAN_SHA
        self.assertEqual(candidate, prereg)
        self.assertEqual(prereg, frozen)

    def test_source_export_refuses_extra_changes_or_wrong_base(self):
        prereg = c.w.read(c.w.PREREG)
        export = c.w.read(c.HERE / 'source-export.json')
        original_read = c.w.read
        for extra in (True, False):
            bad = copy.deepcopy(export)
            if extra:
                bad['changed_files']['another.py'] = dict(before='old', after='new')
            else:
                next(iter(bad['changed_files'].values()))['before'] = 'wrong'
            with self.subTest(extra=extra), patch.object(c.w, 'read',
                    side_effect=lambda p: bad if Path(p) == c.HERE / 'source-export.json' else original_read(p)):
                with self.assertRaises(ValueError):
                    c.source_preregistration(prereg, 'candidate')

    def test_whole_export_manifest_check_binds_both_trees(self):
        import build_export
        export = c.w.read(c.HERE / 'source-export.json')
        candidate = export['candidate_files']
        clean = copy.deepcopy(candidate)
        clean[build_export.CHANGED] = {'sha256': export['changed_files'][build_export.CHANGED]['before']}
        with patch.object(build_export, 'manifest', side_effect=lambda root:
                          candidate if root == build_export.CANDIDATE else clean):
            self.assertTrue(c.verify_export()['passed'])
        for bad_tree in ('candidate', 'clean'):
            altered = copy.deepcopy(candidate if bad_tree == 'candidate' else clean)
            altered['unexpected.py'] = {'sha256': 'drift'}
            with self.subTest(tree=bad_tree), patch.object(build_export, 'manifest',
                    side_effect=lambda root: (altered if bad_tree == 'candidate' else candidate)
                    if root == build_export.CANDIDATE else (altered if bad_tree == 'clean' else clean)):
                with self.assertRaisesRegex(ValueError, bad_tree + ' export changed'):
                    c.verify_export()


if __name__ == '__main__':
    unittest.main()
