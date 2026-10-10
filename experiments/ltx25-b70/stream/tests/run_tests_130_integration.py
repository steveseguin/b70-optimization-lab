#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Packet130 synthetic HTTP checks. Must run through run_cpu_suites.py."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = (HERE / 'run_tests_118b.py').read_text()
source = source[:source.index('\nfor t in (test_first_launch_121_dg0')]
source = source.replace('default=18194', 'default=18232')
source = source.replace("tag = '118' if '118' in fake else '117'", "tag = '118'")
source = source.replace('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261009-continuation118b-stream',
                        '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-130/resolution/components')
source = source.replace("b'fake-packet-118b-manifest'", "b'fake-packet-130-manifest'")
source = source.replace("fake='fake_comfy118.py'", "fake='fake_comfy130.py'")
source = source.replace("packet='118b'", "packet='130'")
exec(compile(source, str(HERE / 'run_tests_118b.py'), 'exec'))

frozen_fake_145 = None  # a separate legacy fake launch, never lab reference evidence
for frames, aux, display, worker, interval in ((121, 'legacy', 'xpu:3', 'serial', 10), (145, 'legacy', 'xpu:3', 'serial', 10),
                             (145, 'xpu2', 'xpu:3', 'serial', 10), (169, 'xpu2', 'xpu:3', 'serial', 10),
                             (145, 'legacy', 'xpu:2', 'serial', 10), (169, 'legacy', 'xpu:2', 'serial', 10),
                             (145, 'legacy', 'xpu:2', 'parallel', 10), (169, 'legacy', 'xpu:2', 'parallel', 10),
                             (145, 'legacy', 'xpu:3', 'serial', 60), (145, 'xpu2', 'xpu:3', 'serial', 60)):
    label = '%d-%s-%s-%s-%d' % (frames, aux, display[-1], worker, interval)
    e = Env('130-' + label)
    schedule = 'eager-display' if display == 'xpu:2' else 'sampler-a'
    reference_flags = []
    if frames == 145 and aux == 'xpu2':
        assert frozen_fake_145 is not None
        e.refs.write_text(json.dumps(frozen_fake_145))
        reference_flags = ['--reference-hashes', str(e.refs)]
    e.start_fake('--frames', str(frames), '--decoder-graph', '0', '--aux-residency', aux,
                 '--display-device', display, '--display-schedule', schedule, '--display-worker', worker,
                 '--gc-interval-seconds', str(interval),
                 '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02', *reference_flags)
    try:
        cp = e.client('--max-chunks', '3', '--expect-frames', str(frames),
                      '--expect-aux-residency', aux, '--expect-display-device', display,
                      '--expect-display-schedule', schedule, '--expect-display-worker', worker,
                      '--expect-gc-interval-seconds', str(interval))
        rows = e.manifest()
        if frames == 145 and aux == 'legacy' and display == 'xpu:3' and cp.returncode == 0:
            receipts = sorted(e.root.glob('encoder-*/receipts/receipt-stream130-qeager-c*.json'))
            chunks = []
            for path in receipts:
                receipt = json.loads(path.read_text())
                decode = json.loads((path.parent / ('decode-' + receipt['run_name'] + '.json')).read_text())
                chunks.append(dict({key: receipt['tensors'][key]['sha256']
                                    for key in ('video_latent', 'audio_latent', 'stage_a_latent')},
                                   images=decode['tensors']['images']['sha256'],
                                   waveform=decode['tensors']['waveform']['sha256'],
                                   last_frame=decode['last_frame_sha256'],
                                   anchor_file=receipt['anchor_out']['sha256']))
            assert len(chunks) == 3
            frozen_fake_145 = {'schema': 'ltx.stream116.reference-frame-hashes.v1', 'variants': {
                '145/two-way20-28/frame': {'source_packet': 'synthetic130-legacy', 'chunks': chunks}}}
        check('130 ' + label + ' qualifies and streams three chunks', cp.returncode == 0 and len(rows) == 3,
              'rc=%d last=%s' % (cp.returncode, last_log(cp)))
        check('130 ' + label + ' binds residency and names', len(rows) == 3 and all(
              row['run_name'].startswith('stream130-s') and row['server_options']['aux_residency'] == aux and row['server_options']['display_worker'] == worker
              and row['server_options']['gc_interval_seconds'] == interval
              and len(row['server_options']['residency_qualification_id']) == 64 for row in rows))
        check('130 ' + label + ' records exact delivered video length', len(rows) == 3 and all(
              row['frames'] == frames and row['new_frames'] == frames - int(i > 0)
              and row['seconds'] == round((frames - int(i > 0)) / 24, 6) for i, row in enumerate(rows)))
        decodes = [json.loads(path.read_text()) for path in e.root.glob('encoder-*/receipts/decode-*.json')]
        def truthful_worker(record):
            gated = record['kind'] in ('qualify-eager', 'qualify-graph')
            parallel = worker == 'parallel' and not gated
            stamps, timing = record['display_worker_timing'], record['timing_ns']
            return (record['display_worker'] == worker
                    and record['completion_worker'] == ('parallel' if parallel else 'serial')
                    and stamps['gated_inline'] is gated
                    and (timing['anchor_ready'] <= stamps['audio_start_ns'] <= stamps['audio_done_ns']
                         <= stamps['queued_ns'] <= stamps['start_ns'] <= timing['display_start']
                         and stamps['audio_done_ns'] == timing['audio_done']
                         and timing['decode_done'] == max(timing['audio_done'], timing['display_done'])
                         if parallel else stamps['queued_ns'] is None and stamps['start_ns'] is None
                         and stamps['audio_start_ns'] is None and stamps['audio_done_ns'] is None
                         and timing['decode_done'] == timing['audio_done']))
        check('130 ' + label + ' decode controls and worker timestamps bind',
              len(decodes) == 12 and all(truthful_worker(record) for record in decodes))
        cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-aux-residency',
                      'xpu2' if aux == 'legacy' else 'legacy', '--expect-display-worker', worker,
                      '--expect-gc-interval-seconds', str(interval))
        check('130 ' + label + ' refuses mismatched residency expectation', cp.returncode == 8)
        cp = e.client('--skip-qualification', '--max-chunks', '1',
                      '--expect-gc-interval-seconds', str(60 if interval == 10 else 10))
        check('130 ' + label + ' refuses mismatched maintenance expectation', cp.returncode == 8)
    finally:
        e.stop_fake()

for outcome in ('healthy', 'fault', 'unavailable'):
    e = Env('130-preview-500-' + outcome)
    e.start_fake('--frames', '145', '--decoder-graph', '0', '--preview-route-error', outcome,
                 '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02')
    try:
        cp = e.client('--max-chunks', '3', '--expect-frames', '145', '--expect-aux-residency', 'legacy')
        state = json.loads((e.work / 'client-state.json').read_text())
        stopped = state.get('last_stop', {})
        snapshot = stopped.get('server_status', {})
        check('130 preview500 ' + outcome + ' preserves original exit7',
              cp.returncode == 7 and stopped.get('code') == 7 and 'HTTP 500' in stopped.get('reason', ''))
        check('130 preview500 ' + outcome + ' writes and logs one bounded observation',
              snapshot.get('request_count') == 1 and snapshot.get('timeout_seconds') == 2.0
              and cp.stdout.count('exit-7 server status') == 1)
        expected = (snapshot.get('available') and not snapshot['status'].get('fault')
                    and snapshot['status'].get('halted') is None) if outcome == 'healthy' else (
                    snapshot.get('available') and bool(snapshot['status'].get('fault'))) if outcome == 'fault' else (
                    not snapshot.get('available') and snapshot.get('http_status') == 503)
        check('130 preview500 ' + outcome + ' status distinguishes the cause', bool(expected))
        check('130 preview500 ' + outcome + ' delivers no incomplete preview', not e.manifest())
    finally:
        e.stop_fake()

for gib in (3, 8):
    e = Env('130-allowance-%d' % gib)
    e.start_fake('--frames', '121', '--decoder-graph', '0', '--run-write-allowance-gib', str(gib),
                 '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02')
    try:
        cp = e.client('--max-chunks', '2', '--expect-run-write-allowance-gib', str(gib))
        rows = e.manifest()
        check('130 %d GiB option qualifies, streams and binds receipts' % gib,
              cp.returncode == 0 and len(rows) == 2 and all(
                  r['server_options']['run_write_allowance_bytes'] == gib * 2**30 for r in rows), last_log(cp))
        cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-run-write-allowance-gib', '4')
        check('130 %d GiB expectation mismatch stops before a request' % gib, cp.returncode == 8)
    finally:
        e.stop_fake()
e = Env('130-storage-409')
e.start_fake('--frames', '121', '--decoder-graph', '0', '--storage-refused',
             '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02')
try:
    cp = e.client('--max-chunks', '1')
    check('130 HTTP409 storage refusal preserves client exit15', cp.returncode == 15, last_log(cp))
    check('130 storage refusal delivers no chunk', not e.manifest())
finally:
    e.stop_fake()

for scan in ('request', 'background'):
    e = Env('130-storage-scan-' + scan)
    e.start_fake('--frames', '145', '--decoder-graph', '0', '--storage-scan-mode', scan,
                 '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02')
    try:
        cp = e.client('--max-chunks', '3', '--expect-storage-scan-mode', scan)
        rows = e.manifest()
        check('130 storage ' + scan + ' qualifies and binds all receipts',
              cp.returncode == 0 and len(rows) == 3 and all(
                  row['server_options']['storage_scan_mode'] == scan for row in rows), last_log(cp))
        cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-storage-scan-mode',
                      'background' if scan == 'request' else 'request')
        check('130 storage ' + scan + ' expectation mismatch fails before requests', cp.returncode == 8)
    finally:
        e.stop_fake()

for cache in (0, 1):
    e = Env('130-snapshot-digest-cache-' + str(cache))
    e.start_fake('--frames', '145', '--decoder-graph', '0', '--snapshot-digest-cache', str(cache),
                 '--display-schedule', 'sampler-a', '--snapshot-mode', 'fingerprint',
                 '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02')
    try:
        cp = e.client('--max-chunks', '3', '--expect-snapshot-digest-cache', str(cache))
        rows = e.manifest()
        check('130 cache%d qualifies and binds all delivered receipts' % cache,
              cp.returncode == 0 and len(rows) == 3 and all(
                  row['server_options']['snapshot_digest_cache'] == cache for row in rows), last_log(cp))
        cp = e.client('--skip-qualification', '--max-chunks', '1', '--expect-snapshot-digest-cache', str(1-cache))
        check('130 cache%d expectation mismatch fails before requests' % cache, cp.returncode == 8)
    finally:
        e.stop_fake()

for mode in ('parent', 'idle'):
    for frames, worker, display, schedule in ((145, 'serial', 'xpu:3', 'sampler-a'),
                                             (169, 'parallel', 'xpu:2', 'eager-display')):
        label = '%s-%d-%s' % (mode, frames, worker)
        e = Env('130-maintenance-' + label)
        e.start_fake('--frames', str(frames), '--decoder-graph', '0', '--maintenance-mode', mode,
                     '--display-worker', worker, '--display-device', display,
                     '--display-schedule', schedule, '--snapshot-mode', 'fingerprint',
                     '--decode-delay', '0.02', '--audio-delay', '0.02', '--preview-delay', '0.02')
        try:
            cp = e.client('--max-chunks', '3', '--expect-maintenance-mode', mode,
                          '--expect-display-worker', worker)
            rows = e.manifest()
            check('130 ' + label + ' qualifies and binds delivered receipts',
                  cp.returncode == 0 and len(rows) == 3 and all(
                      row['server_options']['maintenance_mode'] == mode for row in rows), last_log(cp))
            records = [json.loads(path.read_text()) for pattern in ('decode-*.json', 'preview-*.json')
                       for path in e.root.glob('encoder-*/receipts/' + pattern)]
            check('130 ' + label + ' binds all decode and preview options',
                  len(records) == 24 and all(record['server_options']['maintenance_mode'] == mode
                                            for record in records))
            cp = e.client('--skip-qualification', '--max-chunks', '1',
                          '--expect-maintenance-mode', 'idle' if mode == 'parent' else 'parent',
                          '--expect-display-worker', worker)
            check('130 ' + label + ' mismatch refuses before requests', cp.returncode == 8)
        finally:
            e.stop_fake()


for mode in ('off', 'before-admission'):
    e = Env('130-allocator-' + mode)
    e.start_fake('--frames','169','--decoder-graph','0','--display-allocator-release',mode,
                 '--display-worker','parallel','--display-device','xpu:2',
                 '--display-schedule','eager-display','--snapshot-mode','fingerprint',
                 '--decode-delay','0.02','--audio-delay','0.02','--preview-delay','0.02')
    try:
        cp=e.client('--max-chunks','3','--expect-display-allocator-release',mode,
                    '--expect-display-worker','parallel')
        rows=e.manifest()
        check('130 allocator '+mode+' qualifies and binds every delivered receipt',
              cp.returncode==0 and len(rows)==3 and all(
                  row['server_options']['display_allocator_release']==mode for row in rows),last_log(cp))
        records=[json.loads(path.read_text()) for pattern in ('decode-*.json','preview-*.json')
                 for path in e.root.glob('encoder-*/receipts/'+pattern)]
        check('130 allocator '+mode+' binds all decode and preview identities',
              len(records)==24 and all(record['server_options']['display_allocator_release']==mode for record in records))
        cp=e.client('--skip-qualification','--max-chunks','1','--expect-display-worker','parallel',
                    '--expect-display-allocator-release','off' if mode=='before-admission' else 'before-admission')
        check('130 allocator '+mode+' mismatch refuses before requests',cp.returncode==8)
    finally:
        e.stop_fake()

bad = [r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS)-len(bad), len(RESULTS), TMP))
raise SystemExit(1 if bad else 0)
