#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""Packet131 synthetic HTTP checks; cooperative CPU-only run_cpu_suites.py required."""
from pathlib import Path
import os

HERE = Path(__file__).resolve().parent
source = (HERE / 'run_tests_118b.py').read_text()
source = source[:source.index('\nfor t in (test_first_launch_121_dg0')]
source = source.replace('default=18194', 'default=18234')
source = source.replace("tag = '118' if '118' in fake else '117'", "tag = '118'")
source = source.replace('/home/steve/llm-optimizations/experiments/ltx25-b70/recovery/20261009-continuation118b-stream',
                        '/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-131/resolution/components')
source = source.replace("b'fake-packet-118b-manifest'", "b'fake-packet-131-manifest'")
source = source.replace("fake='fake_comfy118.py'", "fake='fake_comfy131.py'")
source = source.replace("packet='118b'", "packet='131'")
exec(compile(source, str(HERE / 'run_tests_118b.py'), 'exec'))

# Offline validation must consume the receipt option, never the server launcher environment.
os.environ.pop('LTX_CONE_GRAPH_MEMORY', None)
check('131 offline qualification runs without server cone environment', 'LTX_CONE_GRAPH_MEMORY' not in os.environ)

for mode, dg, display, schedule, interval, cache, maintenance in (
    ('off', 0, 'xpu:3', 'sampler-a', 10, 0, 'parent'),
    ('off', 0, 'xpu:3', 'sampler-a', 60, 1, 'idle'),
    ('replica-release', 1, 'xpu:2', 'eager-display', 10, 0, 'parent'),
    ('replica-release', 1, 'xpu:2', 'eager-display', 60, 1, 'idle'),
):
    label='%s-%d-%d-%s' % (mode, interval, cache, maintenance)
    e = Env('131-' + label)
    e.start_fake('--frames','145','--decoder-graph',str(dg),'--cone-graph-memory',mode,
                 '--display-device',display,'--display-schedule',schedule,'--display-worker','serial',
                 '--gc-interval-seconds',str(interval),'--snapshot-digest-cache',str(cache),
                 '--maintenance-mode',maintenance,'--storage-scan-mode','background',
                 '--decode-delay','0.02','--audio-delay','0.02','--preview-delay','0.02')
    try:
        flags=['--expected-cone-graph-memory',mode,'--expect-gc-interval-seconds',str(interval),
               '--expect-snapshot-digest-cache',str(cache),'--expect-maintenance-mode',maintenance,
               '--expect-storage-scan-mode','background']
        cp=e.client('--max-chunks','3',*flags)
        if cp.returncode:
            print(cp.stdout + cp.stderr, flush=True)
        rows=e.manifest()
        check('131 '+label+' qualifies and streams three chunks',cp.returncode==0 and len(rows)==3,last_log(cp))
        check('131 '+label+' binds cone option in every delivered receipt',len(rows)==3 and all(
              row['run_name'].startswith('stream131-s') and row['server_options']['cone_graph_memory']==mode
              and row['server_options']['display_allocator_release']=='off' for row in rows))
        decodes=[json.loads(p.read_text()) for p in e.root.glob('encoder-*/receipts/decode-*.json')]
        previews=[json.loads(p.read_text()) for p in e.root.glob('encoder-*/receipts/preview-*.json')]
        check('131 '+label+' binds all decode and preview identities',len(decodes)==12 and len(previews)==12 and all(
              record['server_options']['cone_graph_memory']==mode for record in decodes+previews))
        check('131 '+label+' carries admission precisely on cone paths',len(decodes)==12 and all(
              (record.get('cone_graph_memory_admission') is not None) ==
              (mode=='replica-release' and record['kind']!='qualify-eager') for record in decodes))
        check('131 '+label+' retains control-card and replica routes',len(decodes)==12 and all(
              record['display_device']==('xpu:3' if record['kind']=='qualify-eager' else display) for record in decodes))
        flags[1]='off' if mode=='replica-release' else 'replica-release'
        cp=e.client('--skip-qualification','--max-chunks','1',*flags)
        check('131 '+label+' refuses expectation mismatch before requests',cp.returncode==8,last_log(cp))
    finally:
        e.stop_fake()

bad=[r for r in RESULTS if not r[1]]
print('\n%d/%d passed; work in %s' % (len(RESULTS)-len(bad),len(RESULTS),TMP))
raise SystemExit(1 if bad else 0)
