#!/usr/bin/env python3
"""Packet119 fake HTTP qualification/stream binding; safe wrapper required."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = (HERE / 'run_tests_118b.py').read_text()
source = source[:source.index('\nfor t in (test_first_launch_121_dg0')]
source = source.replace('default=18194', 'default=18196')
source = source.replace("tag = '118' if '118' in fake else '117'", "tag = '118'")
source = source.replace('20261009-continuation118b-stream', '20261010-continuation119-stream')
source = source.replace("b'fake-packet-118b-manifest'", "b'fake-packet-119-manifest'")
source = source.replace("fake='fake_comfy118.py'", "fake='fake_comfy119.py'")
source = source.replace("packet='118b'", "packet='119'")
exec(compile(source, str(HERE / 'run_tests_118b.py'), 'exec'))

for label, extra, expected in (
    ('off', ['--decoder-graph', '0'], {'display_schedule': 'sampler-a', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full'}),
    ('eager-display', ['--display-schedule', 'eager-display', '--pool-cap', '1.0'],
     {'display_schedule': 'eager-display', 'anchor_read_ahead': 0, 'snapshot_schedule': 'full'}),
    ('delayed', ['--display-schedule', 'sampler-b', '--anchor-read-ahead', '1', '--snapshot-schedule', 'a-xpu3-sync'],
     {'display_schedule': 'sampler-b', 'anchor_read_ahead': 1, 'snapshot_schedule': 'a-xpu3-sync'}),
):
    e = Env('119-' + label)
    e.start_fake('--frames', '121', '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02', *extra)
    try:
        flags = [item for key, value in expected.items() for item in ('--expect-' + key.replace('_', '-'), str(value))]
        cp = e.client('--max-chunks', '3', '--expect-frames', '121', *flags)
        rows = e.manifest()
        check('119 ' + label + ' qualifies and streams three chunks', cp.returncode == 0 and len(rows) == 3,
              'rc=%d last=%s' % (cp.returncode, last_log(cp)))
        check('119 ' + label + ' records exact server options and names', len(rows) == 3 and all(
            row['run_name'].startswith('stream119-s') and all(row['server_options'][k] == v for k, v in expected.items())
            and len(row['snapshots']['synchronized']) == len(row['snapshots']['labels'])
            and all(cards == ['xpu:0', 'xpu:1', 'xpu:2', 'xpu:3'] for cards in row['snapshots']['memory_cards'])
            and 'anchor_read_source' in row
            for row in rows))
        for flag, value in (('--expect-display-schedule', 'sampler-b' if label == 'eager-display' else 'eager-display'), ('--expect-anchor-read-ahead', str(1-expected['anchor_read_ahead'])),
                            ('--expect-snapshot-schedule', 'full' if label == 'delayed' else 'a-xpu3-sync')):
            cp = e.client('--skip-qualification', '--max-chunks', '1', flag, value)
            check('119 ' + label + ' wrong ' + flag + ' refused', cp.returncode == 8, 'rc=%d' % cp.returncode)
    finally:
        e.stop_fake()
bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS)-len(bad), len(RESULTS), TMP))
raise SystemExit(1 if bad else 0)
