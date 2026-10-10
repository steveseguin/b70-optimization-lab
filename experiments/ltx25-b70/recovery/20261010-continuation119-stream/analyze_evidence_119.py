#!/home/steve/.venvs/ltx25-baseline/bin/python
"""Read-only, standard-library analysis of fixed 118b samples for packet 119.

Run with bin/python -B; emits JSON to stdout. Reads only explicitly named files.
It never imports the runtime, opens devices, contacts endpoints or writes files.
Live manifest/log hashes identify bytes observed, not a permanent file identity.
"""
import datetime
import hashlib
import json
from pathlib import Path
import statistics

BASE = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
REPO = Path('/home/steve/llm-optimizations')
LANE = REPO / 'experiments/ltx25-b70'
RUN_STEM = ('encoder-server-continuation-stream-118b-frame-dg{dg}-adcone-bo1-pa1-smfp-'
            'two-way20-28-w1-b1-p1-dxpu2-s256x256-f121')


def analyze():
    files = {}

    def read(path):
        path = Path(path)
        before = datetime.datetime.now(datetime.timezone.utc).isoformat()
        raw = path.read_bytes()
        files[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                            'read_started_utc': before,
                            'read_finished_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        return raw

    def obj(path):
        return json.loads(read(path))

    result = {
        'schema': 'ltx.continuation119.evidence.v1',
        'methodology': {
            'execution': 'standard library, CPU only, explicit regular-file reads; no runtime import',
            'matched_metric_chunks': list(range(10, 36)),
            'shared_identity_chunks': list(range(37)),
            'period_definition': 'receipt submit[i+1] minus submit[i], i=10..35, seconds',
            'summary': 'median/min/max, no interpolation; paired sample by stream sequence',
            'timestamp_limits': 'host wall timestamps identify boundaries, not device queue submissions',
            'live_file_limits': 'manifest and client.log are captured read-only; may grow after this read',
            'qualification': 'each per-chunk equality is observed; CPU analysis is not new qualification',
        },
        'runs': {}, 'cross_run_identity': {}, 'sources': {},
    }
    paired = {}
    for dg in (0, 1):
        suffix = '.completed-20261010T0156Z' if dg == 0 else ''
        run = BASE / (RUN_STEM.format(dg=dg) + suffix)
        receipts = [obj(run / 'receipts' / ('receipt-stream118b-s%08d.json' % i)) for i in range(37)]
        decodes = [obj(run / 'receipts' / ('decode-stream118b-s%08d.json' % i)) for i in range(37)]
        work = Path('/home/steve/ltx-stream') / ('s118b-live01' if dg == 0 else 's118b-dg1-live01')
        manifest = [json.loads(line) for line in read(work / 'manifest.jsonl').splitlines() if line]
        log = read(work / 'client.log').decode()
        metrics = {}

        def add(key, value):
            metrics.setdefault(key, []).append(value)

        for i in range(10, 36):
            r, d, prev = receipts[i], decodes[i], decodes[i - 1]
            t, pt = r['timing_ns'], prev['timing_ns']
            pc = r['conditioning_sources']['B']['precompute']
            add('period_s', (receipts[i + 1]['timing_ns']['submit'] - t['submit']) / 1e9)
            add('upsample_and_b_prep_s', (t['sampler_b_start'] - t['stage_a_done']) / 1e9)
            for key, value in r['timing_s']['sampler_a_split'].items():
                add(key + '_s', value)
            for snap in r['snapshots']:
                if snap['label'] in ('B-before', 'B-after'):
                    add(snap['label'] + '_snapshot_s', snap['seconds'])
                if snap['label'] in ('A-before', 'A-after') and not snap['dual']:
                    add(snap['label'] + '_nondual_inspector_s', snap['seconds'])
                    for part, seconds in snap['parts_s'].items():
                        add(snap['label'] + '_nondual_' + part + '_s', seconds)
            add('b_node_s', (t['condition_b_done'] - t['condition_b_start']) / 1e9)
            add('b_precompute_s', (pc['timing_ns']['done'] - pc['timing_ns']['start']) / 1e9)
            add('b_encode_s', pc['record']['encode_s'])
            add('b_consumer_wait_s', r['conditioning_sources']['B']['waited_s'])
            add('b_precompute_done_before_b_node_s', (t['condition_b_start'] - pc['timing_ns']['done']) / 1e9)
            add('cone_decode_s', d['anchor_decode']['seconds'])
            add('actual_go_wait_s', d['schedule']['go_wait_s'])
            for key in ('anchor_ready_to_go', 'display_decode', 'precompute_a', 'precompute_b'):
                add(key + '_s', d['timing_s'][key])
            for label, mark in (('a_start', 'sampler_a_start'), ('a_end', 'stage_a_done'),
                                ('b_node', 'condition_b_start'), ('b_sampler', 'sampler_b_start')):
                add('predecessor_display_done_minus_' + label + '_s', (pt['display_done'] - t[mark]) / 1e9)
            add('predecessor_display_start_after_a_start_s', (pt['display_start'] - t['sampler_a_start']) / 1e9)
            add('xpu3_after_free_bytes', r['memory']['after']['free']['xpu:3'])
        summaries = {key: {'n': len(values), 'median': statistics.median(values),
                           'min': min(values), 'max': max(values), 'values': values}
                     for key, values in metrics.items()}
        result['runs']['dg' + str(dg)] = {
            'path': str(run), 'metrics': summaries,
            'observed_manifest_rows': len(manifest),
            'client_log_last_line': log.splitlines()[-1],
            'cone_equal_shared': sum(d['anchor_decode']['equal'] is True for d in decodes),
            'qualification_verdict_sha256': receipts[20]['qualification_verdict_sha256'],
            'server_options': receipts[20]['server_options'],
            'decoder_pool': decodes[20]['decoder'].get('pool'),
            'example': {'current_seq': 21, 'previous_seq': 20,
                        'current_timing_ns': receipts[21]['timing_ns'],
                        'predecessor_decode_timing_ns': decodes[20]['timing_ns']},
        }
        paired[dg] = decodes
    for tensor in ('images', 'waveform'):
        matches = [i for i in range(37) if paired[0][i]['tensors'][tensor]['sha256'] ==
                   paired[1][i]['tensors'][tensor]['sha256']]
        result['cross_run_identity'][tensor] = {'matching_sequences': matches, 'n': 37}
    author = LANE / 'recovery/20261009-continuation118b-stream'
    for name, path, lines, meaning in (
        ('replica_environment', author / 'runtime_packet.py', [353, 602],
         'xpu:2 environment retained; native VAEDecode, zero replicas'),
        ('replica_guard', author / 'session.py', [317, 318],
         'session admission requires decode_replicas == 0'),
        ('vae_device', author / 'native_bindings.py', [144, 149],
         'native VAE pinned xpu:3, output/intermediate CPU'),
        ('display_schedule', author / 'integration.py', [385, 578, 599],
         '3-second sampler-A go bound, B precompute, then display decode'),
        ('upsampler', BASE / 'prepared-continuation-stream-118b/source/comfy_extras/nodes_lt_upsampler.py',
         [45, 47, 51, 56], 'native model placement, execution, result copied to intermediate device'),
    ):
        read(path)
        result['sources'][name] = {'path': str(path), 'lines': lines, 'meaning': meaning}
    result['interpretation'] = {
        'supported': 'dg1 predecessor display completion coincides with successor upsampler return; '
                     'delay occurs before stage-B conditioning, not in its snapshots or precompute wait',
        'unproven': 'queue/CCS-level cause and exact blocking operation require later device evidence',
        'snapshot_timing_limit': 'inspector seconds exclude CandidateSafety pre-inspect synchronization; '
                                 'nondual memory part includes the second synchronization and memory readings; '
                                 'cannot attribute all inspector time to synchronization',
        'replica': 'xpu:2 environment is not an instantiated stream decode replica; changing placement '
                   'requires new residence admission and cross-card exact-output qualification',
        'candidate': 'graph cone plus eager display may preserve eager interleaving; delayed display '
                     'may instead defer waiting onto next cone/FIFO; neither benefit is measured',
    }
    result['files_read'] = files
    return result


if __name__ == '__main__':
    print(json.dumps(analyze(), indent=2, sort_keys=True, ensure_ascii=False))
