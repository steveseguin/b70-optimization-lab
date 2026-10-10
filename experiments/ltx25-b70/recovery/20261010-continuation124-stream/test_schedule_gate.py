"""CPU-only corruption tests for saved live schedule receipts; no runtime imports."""
import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import stream_schedule_gate as gate

H = '1' * 64


def fixture(display='sampler-a', ahead=0, schedule='full', mode='fingerprint'):
    r = dict(kind='stream', run_name='stream124-s00000001', prompt_id='prompt1', stream_seq=1,
             committed=True, anchored=True, anchor='frame', seed=2, frames=121, reset=False,
             prompt_sha256=H, qualification_verdict_sha256=H,
             sanity=dict(finite=True, shapes=True, anchor_chain=True),
             server_options=dict(display_schedule=display, anchor_read_ahead=ahead,
                                 snapshot_schedule=schedule, snapshot_mode=mode,
                                 decoder_graph_pool_cap_bytes=1000000000, display_device='xpu:3'),
             anchor_out=dict(sha256=H), levers=dict(anchor_decode='cone'),
             anchor_read_source='verified-read-ahead' if ahead else 'native', snapshots=[])
    for label in ('request-before', 'A-before', 'A-after', 'B-before', 'B-after', 'request-after'):
        r['snapshots'].append(dict(label=label, mode=mode, memory_cards=gate.CARDS.copy(),
                                  synchronized=['xpu:3'] if schedule == 'a-xpu3-sync' and label.startswith('A-')
                                  else gate.CARDS.copy(), dual=False, agree=None, min_margin_bytes=2**30))
    event = dict(source_run_name=r['run_name'], anchor_sha256=H, consumer_run_name='stream124-s00000002',
                 prompt_id='prompt2', sampler_b_start_ns=100)
    d = dict(kind='stream', run_name=r['run_name'], prompt_id='prompt1', stream_seq=1,
             display_device='xpu:3', display_replica=None,
             last_frame_sha256=H, tensors={k: dict(sha256=H) for k in ('images', 'waveform')},
             anchor_decode=dict(mode='cone', equal=True, last_frame_sha256=H, display_last_frame_sha256=H),
             timing_ns=dict(display_start=101), schedule=dict(display_schedule=display, gated=False,
             go_wait_s=.2, display_release=dict(reason='matching-successor-sampler-b-start', waited_s=.8,
                                               event=event)))
    return [r], [d]


class GateTests(unittest.TestCase):
    def reject(self, rows, decodes, part):
        result = gate.check(rows, decodes)
        self.assertFalse(result['passed'])
        self.assertTrue(any(part in reason for reason in result['failures']), result)

    def test_default_passes_no_speed_claim(self):
        result = gate.check(*fixture())
        self.assertTrue(result['passed'], result)
        self.assertFalse(result['performance_qualified'])

    def test_empty_rejected(self):
        self.reject([], [], 'No live')

    def test_qualification_does_not_count_as_live(self):
        r, d = fixture(); r[0]['kind'] = 'qualify-graph'
        self.reject(r, d, 'No live')

    def test_missing_options(self):
        r, d = fixture(); del r[0]['server_options']
        self.reject(r, d, 'Missing server options')

    def test_invalid_option(self):
        r, d = fixture(); r[0]['server_options']['display_schedule'] = 'unknown'
        self.reject(r, d, 'Invalid display')

    def test_bool_ahead_rejected(self):
        r, d = fixture(); r[0]['server_options']['anchor_read_ahead'] = True
        self.reject(r, d, 'Invalid anchor')

    def test_option_mismatch_between_receipts(self):
        r, d = fixture(); other = copy.deepcopy(r[0]); other.update(run_name='other', stream_seq=2)
        other['server_options']['display_schedule'] = 'sampler-b'; r.append(other)
        self.reject(r, d, 'Server options differ')

    def test_uncommitted(self):
        r, d = fixture(); r[0]['committed'] = False
        self.reject(r, d, 'Uncommitted')

    def test_missing_qualification(self):
        r, d = fixture(); del r[0]['qualification_verdict_sha256']
        self.reject(r, d, 'qualification verdict')

    def test_cone_mismatch(self):
        r, d = fixture(); d[0]['anchor_decode']['equal'] = False
        self.reject(r, d, 'byte check')

    def test_cone_claim_true_with_wrong_hash(self):
        r, d = fixture(); d[0]['anchor_decode']['display_last_frame_sha256'] = '2' * 64
        self.reject(r, d, 'byte check')

    def test_decode_prompt_binding(self):
        r, d = fixture(); d[0]['prompt_id'] = 'foreign'
        self.reject(r, d, 'Decode identity')

    def test_b_release_passes(self):
        result = gate.check(*fixture(display='sampler-b'))
        self.assertTrue(result['passed'], result)

    def test_b_release_wrong_source(self):
        r, d = fixture(display='sampler-b'); d[0]['schedule']['display_release']['event']['source_run_name'] = 'foreign'
        self.reject(r, d, 'matching successor')

    def test_b_release_wrong_anchor(self):
        r, d = fixture(display='sampler-b'); d[0]['schedule']['display_release']['event']['anchor_sha256'] = '2' * 64
        self.reject(r, d, 'matching successor')

    def test_b_release_display_before_event(self):
        r, d = fixture(display='sampler-b'); d[0]['timing_ns']['display_start'] = 99
        self.reject(r, d, 'matching successor')

    def test_combined_wait_bound(self):
        r, d = fixture(display='sampler-b'); d[0]['schedule']['display_release']['waited_s'] = 2.81
        self.reject(r, d, '3 seconds')

    def test_nan_wait_rejected(self):
        r, d = fixture(display='sampler-b'); d[0]['schedule']['go_wait_s'] = float('nan')
        self.reject(r, d, '3 seconds')

    def test_bound_fallback_reported_and_refused(self):
        r, d = fixture(display='sampler-b'); d[0]['schedule']['display_release']['reason'] = 'bound'
        result = gate.check(r, d)
        self.assertFalse(result['passed'])
        self.assertEqual(result['bounded_fallbacks'], [r[0]['run_name']])

    def test_gated_bypass_on_live_refused(self):
        r, d = fixture(display='sampler-b'); d[0]['schedule']['display_release']['reason'] = 'gated-no-wait'
        self.reject(r, d, 'live display release')

    def test_all_card_memory_required(self):
        r, d = fixture(); r[0]['snapshots'][1]['memory_cards'] = ['xpu:3']
        self.reject(r, d, 'all-card readings')

    def test_full_mode_cannot_reduce(self):
        r, d = fixture(); r[0]['snapshots'][1]['synchronized'] = ['xpu:3']
        self.reject(r, d, 'forbidden reduced')

    def test_reduced_a_allowed(self):
        result = gate.check(*fixture(schedule='a-xpu3-sync'))
        self.assertTrue(result['passed'], result)

    def test_reduced_b_refused(self):
        r, d = fixture(schedule='a-xpu3-sync'); r[0]['snapshots'][3]['synchronized'] = ['xpu:3']
        self.reject(r, d, 'forbidden reduced')

    def test_reduced_dual_refused(self):
        r, d = fixture(schedule='a-xpu3-sync'); r[0]['snapshots'][1].update(dual=True, agree=True)
        self.reject(r, d, 'forbidden reduced')

    def test_every_twentieth_cannot_reduce(self):
        r, d = fixture(schedule='a-xpu3-sync'); r[0]['stream_seq'] = d[0]['stream_seq'] = 20
        self.reject(r, d, 'forbidden reduced')

    def test_walk_cannot_reduce(self):
        self.reject(*fixture(schedule='a-xpu3-sync', mode='walk'), 'fingerprint mode')

    def test_near_floor_requires_dual(self):
        r, d = fixture(); r[0]['snapshots'][0]['min_margin_bytes'] = 2**29
        self.reject(r, d, 'required dual')

    def test_near_floor_policy_sticky(self):
        r, d = fixture()
        r[0]['snapshots'][0].update(min_margin_bytes=2**29, dual=True, agree=True)
        self.reject(r, d, 'required dual')

    def test_near_floor_all_dual_passes(self):
        r, d = fixture(schedule='a-xpu3-sync')
        for snap in r[0]['snapshots']:
            snap.update(min_margin_bytes=2**29, dual=True, agree=True, synchronized=gate.CARDS.copy())
        self.assertTrue(gate.check(r, d)['passed'])

    def test_missing_snapshots(self):
        r, d = fixture(); r[0]['snapshots'] = []
        self.reject(r, d, 'Snapshot labels')

    def test_read_ahead_hit_required(self):
        r, d = fixture(ahead=1); r[0]['anchor_read_source'] = 'native-miss'
        self.reject(r, d, 'no verified live hit')

    def test_read_ahead_hit_reported(self):
        result = gate.check(*fixture(ahead=1))
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['read_ahead_hits'], 1)

    def test_read_ahead_off_native_only(self):
        r, d = fixture(); r[0]['anchor_read_source'] = 'verified-read-ahead'
        self.reject(r, d, 'option off')

    def test_control_exact(self):
        r, d = fixture()
        result = gate.check(r, d, copy.deepcopy(r), copy.deepcopy(d))
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['control_compared_chunks'], 1)

    def test_control_bytes_differ(self):
        r, d = fixture(); cd = copy.deepcopy(d); cd[0]['tensors']['waveform']['sha256'] = '2' * 64
        result = gate.check(r, d, copy.deepcopy(r), cd)
        self.assertFalse(result['passed'])

    def test_control_prompt_differs(self):
        r, d = fixture(); cr = copy.deepcopy(r); cr[0]['prompt_sha256'] = '2' * 64
        self.assertFalse(gate.check(r, d, cr, d)['passed'])

    def test_control_missing_refused(self):
        r, d = fixture()
        self.assertFalse(gate.check(r, d, [], [])['passed'])

    def test_read_run_parses_worker_options_without_checker_local_state(self):
        for worker in ('serial', 'parallel'):
            r, d = fixture()
            r[0]['server_options']['display_worker'] = worker
            with tempfile.TemporaryDirectory(prefix='ltx124-read-run-', dir='/dev/shm') as temp:
                folder = Path(temp) / 'receipts'; folder.mkdir()
                for prefix, value in (('receipt', r[0]), ('decode', d[0])):
                    (folder / (prefix + '-' + r[0]['run_name'] + '.json')).write_text(json.dumps(value))
                hashes = {}
                self.assertEqual(gate.read_run(temp, 1, 1, hashes), (r, d))
                self.assertEqual(len(hashes), 2)

    def test_cli_reads_files_and_hashes(self):
        r, d = fixture()
        with tempfile.TemporaryDirectory(prefix='ltx120-gate-', dir='/dev/shm') as temp:
            folder = Path(temp) / 'receipts'; folder.mkdir()
            for prefix, value in (('receipt', r[0]), ('decode', d[0])):
                (folder / (prefix + '-' + r[0]['run_name'] + '.json')).write_text(json.dumps(value))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = gate.main(['--run', temp, '--first', '1', '--last', '1'])
            result = json.loads(output.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(len(result['files_sha256']), 2)


if __name__ == '__main__':
    unittest.main()
