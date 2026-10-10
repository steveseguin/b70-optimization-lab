#!/usr/bin/env python3
"""Packet122 fake HTTP qualification/stream binding; safe wrapper required."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = (HERE / 'run_tests_118b.py').read_text()
source = source[:source.index('\nfor t in (test_first_launch_121_dg0')]
source = source.replace('default=18194', 'default=18199')
source = source.replace("tag = '118' if '118' in fake else '117'", "tag = '118'")
source = source.replace('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261009-continuation118b-stream',
                        '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-122/resolution/components')
source = source.replace("b'fake-packet-118b-manifest'", "b'fake-packet-122-manifest'")
source = source.replace("fake='fake_comfy118.py'", "fake='fake_comfy122.py'")
source = source.replace("packet='118b'", "packet='122'")
exec(compile(source, str(HERE / 'run_tests_118b.py'), 'exec'))

for frames in (121, 145):
    for label, extra, expected in (
        ('replica', ['--display-device', 'xpu:2', '--display-schedule', 'eager-display', '--pool-cap', '1.0'],
         {'display_schedule': 'eager-display', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:2'}),
        ('replica-budget', ['--display-device', 'xpu:2', '--display-schedule', 'eager-display', '--pool-cap', '1.0',
                            '--display-transient-gib', '6'],
         {'display_schedule': 'eager-display', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:2',
          'display_replica_transient_budget_bytes': 6 * 2**30}),
        ('off', ['--decoder-graph', '0'], {'display_schedule': 'sampler-a', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:3'}),
        ('eager-display', ['--display-schedule', 'eager-display', '--pool-cap', '1.0'],
         {'display_schedule': 'eager-display', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full', 'display_device': 'xpu:3'}),
        ('delayed', ['--display-schedule', 'sampler-b', '--anchor-read-ahead', '1', '--snapshot-schedule', 'a-xpu3-sync'],
         {'display_schedule': 'sampler-b', 'anchor_read_ahead': 1, 'snapshot_schedule': 'a-xpu3-sync', 'display_device': 'xpu:3'}),
    ):
        e = Env('122-f%d-' % frames + label)
        e.start_fake('--frames', str(frames), '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02', *extra)
        try:
            flags = [item for key, value in expected.items() if key != 'display_replica_transient_budget_bytes'
                     for item in ('--expect-' + key.replace('_', '-'), str(value))]
            if label == 'replica-budget':
                flags += ['--expect-display-transient-gib', '6']
            cp = e.client('--max-chunks', '3', '--expect-frames', str(frames), *flags)
            rows = e.manifest()
            check('122 f%d ' % frames + label + ' qualifies and streams three chunks', cp.returncode == 0 and len(rows) == 3,
                  'rc=%d last=%s' % (cp.returncode, last_log(cp)))
            check('122 f%d ' % frames + label + ' records exact server options and names', len(rows) == 3 and all(
                row['run_name'].startswith('stream122-s') and all(row['server_options'][k] == v for k, v in expected.items())
                and len(row['snapshots']['synchronized']) == len(row['snapshots']['labels'])
                and all(cards == ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'] for cards in row['snapshots']['memory_cards'])
                and 'anchor_read_source' in row
                for row in rows))
            check('122 f%d ' % frames + label + ' exact manifest delivery geometry', len(rows) == 3 and all(
                row['frames'] == frames and row['new_frames'] == (frames if i == 0 else frames - 1)
                and row.get('skip_first_frames', 0) == (0 if i == 0 else 1)
                and row['seconds'] == round((frames if i == 0 else frames - 1) / 24, 6)
                for i, row in enumerate(rows)))
            if label == 'replica-budget':
                for value in (None, '7'):
                    budget_flags = [] if value is None else ['--expect-display-transient-gib', value]
                    cp = e.client('--skip-qualification', '--max-chunks', '1', *budget_flags)
                    check('122 f%d explicit budget missing/wrong expectation %r refuses' % (frames, value),
                          cp.returncode == 8, 'rc=%d' % cp.returncode)
            for flag, value in (('--expect-display-device', 'xpu:2' if expected['display_device'] == 'xpu:3' else 'xpu:3'), ('--expect-display-schedule', 'sampler-b' if expected['display_schedule'] == 'eager-display' else 'eager-display'), ('--expect-anchor-read-ahead', str(1-expected['anchor_read_ahead'])),
                                ('--expect-snapshot-schedule', 'full' if label == 'delayed' else 'a-xpu3-sync')):
                cp = e.client('--skip-qualification', '--max-chunks', '1', flag, value)
                check('122 f%d ' % frames + label + ' wrong ' + flag + ' refused', cp.returncode == 8, 'rc=%d' % cp.returncode)
        finally:
            e.stop_fake()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS)-len(bad), len(RESULTS), TMP))
raise SystemExit(1 if bad else 0)
