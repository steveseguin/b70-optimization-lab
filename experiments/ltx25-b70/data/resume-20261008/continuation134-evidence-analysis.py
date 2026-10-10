#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only fixed-window receipt analysis; no runtime imports or live requests."""
import hashlib
import json
from pathlib import Path
from statistics import median, mean

ROOT = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913')
HERE = Path(__file__).resolve().parent
RUN = ROOT / ('encoder-server-continuation-stream-133b-frame-dg1-adcone-bo1-pa1-smfp-'
    'two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-dseager-display-ra0-ssfull-gc60-'
    'ssbackground-sdc1-mi-cmtext-shift-textsplit36.completed-20261010T145013Z')
PARENT = ROOT / ('encoder-server-continuation-stream-129-frame-dg0-adcone-bo1-pa1-smfp-'
    'two-way20-28-w1-b1-p1-dxpu2-s256x256-f145-gc60-ssbackground-sdc1-mi')
GIB = 2**30
CARDS = ['xpu:%d' % n for n in range(4)]
FLOORS = dict(zip(CARDS, [8, 8, 2, 9]))
sources = {}

def read(path):
    raw = path.read_bytes()
    sources[str(path)] = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    return json.loads(raw)

def stats(values):
    return dict(n=len(values), median=median(values), mean=mean(values), min=min(values), max=max(values))

def phases(row):
    m = row['memory']
    yield 'before', m['before']['free']
    for stage in m['conditioning']:
        for suffix in ['before', 'after']:
            yield stage['stage'] + '-' + suffix, stage['free_' + suffix]
    yield 'after', m['after']['free']

def memory(rows):
    found = {}
    for row in rows:
        for phase, free in phases(row):
            bucket = found.setdefault(phase, {})
            for card, count in free.items():
                if card not in bucket or count < bucket[card]['bytes']:
                    bucket[card] = dict(bytes=count, gib=count/GIB, run_name=row['run_name'])
    minima = {c: min(v[c]['bytes'] for v in found.values()) for c in CARDS}
    return dict(phases=found, minimum_bytes=minima,
        margin_above_floor_and_band_gib={c: minima[c]/GIB-FLOORS[c]-.75 for c in CARDS})

receipts = [read(RUN / ('receipts/receipt-stream133b-s%08d.json' % i)) for i in range(31)]
decodes = [read(RUN / ('receipts/decode-stream133b-s%08d.json' % i)) for i in range(31)]
qualification = [read(RUN / ('receipts/receipt-stream133b-q%s-c%06d.json' % (mode, i)))
                 for mode in ['eager', 'graph', 'repeat'] for i in range(3)]
qdecodes = [read(RUN / ('receipts/decode-stream133b-q%s-c%06d.json' % (mode, i)))
           for mode in ['eager', 'graph', 'repeat'] for i in range(3)]
verdict = read(RUN / 'stream-qualification-verdict.json')
assert verdict['passed'] is True
parity = []
for i, (r, d) in enumerate(zip(receipts, decodes)):
    pr = read(PARENT / ('receipts/receipt-stream129-s%08d.json' % i))
    pd = read(PARENT / ('receipts/decode-stream129-s%08d.json' % i))
    fields = {k: r['tensors'][k]['sha256'] == pr['tensors'][k]['sha256'] for k in r['tensors']}
    fields.update({k: d['tensors'][k]['sha256'] == pd['tensors'][k]['sha256'] for k in d['tensors']})
    fields['anchor'] = r['anchor_out']['sha256'] == pr['anchor_out']['sha256']
    fields['prompt'] = r['prompt_sha256'] == pr['prompt_sha256']
    fields['cone'] = d['anchor_decode']['equal'] is True
    assert all(fields.values()), (i, fields)
    parity.append(dict(index=i, comparisons=fields))
periods = {kind: [(receipts[i+1][kind]-receipts[i][kind])/1e9 for i in range(7,30)]
           for kind in ['commit_ns']}
periods['submit_ns'] = [(receipts[i+1]['timing_ns']['submit']-receipts[i]['timing_ns']['submit'])/1e9
                        for i in range(7,30)]
buckets = {k: stats([r['timing_s'][k] for r in receipts[7:30]]) for k in
    ['submit_to_sampler_start', 'sampler_a_bucket', 'sampler_b', 'anchor_decode_in_chain',
     'video_done_to_anchor_ready', 'anchor_ready_to_receipt_staged']}
buckets['sampler_a_kernel'] = stats([r['timing_s']['sampler_a_split']['sampler_a'] for r in receipts[7:30]])
decode_buckets = {k: stats([r['timing_s'][k] for r in decodes[7:30]]) for k in
    ['display_decode', 'audio_decode', 'queue_wait', 'anchor_ready_to_go', 'precompute_b',
     'anchor_ready_to_decode_done', 'hash_and_diagnostics']}
snapshots = [s for r in receipts for s in r['snapshots']]
assert all(s['agree'] is True for s in snapshots if s['dual'])
mem = memory(receipts)
growth = qdecodes[3]['decoder']['pool']['growth_bytes']
assert growth == 3806330880
old = read(HERE / 'continuation124-evidence.json')
deltas = {c: (old['runs']['145_aux']['minimum_free_gib'][c] -
              old['runs']['169_aux']['minimum_free_gib'][c]) for c in CARDS}
base = min(d['xpu3_free_before_decode'] for d in qdecodes[:3])
tail_base = min(free['xpu:3'] for row in qualification[:3] for _, free in phases(row))
reserve = (6704*GIB+999)//1000  # Round the scaled5GiB allowance upward to6.704GiB.
display = 13*GIB//2
common = {c: mem['minimum_bytes'][c]/GIB-deltas[c]-FLOORS[c]-.75 for c in CARDS[:3]}
replica = 834267746/GIB
arms = {}
for arm in ['a', 'b', 'c']:
    margins = dict(common)
    if arm == 'b':
        margins['xpu:2'] -= replica + display/GIB
    margins['xpu:3'] = base/GIB-9-.75-(reserve/GIB if arm != 'c' else 0)-(display/GIB if arm != 'b' else 0)
    arms[arm] = dict(margins_above_floor_and_band_gib=margins,
        admitted_for_cpu_preparation=all(x >= 0 for x in margins.values()))
    if arm == 'b':
        arms[arm]['card3_qualification_margin_if_full_original_display_overlaps_gib'] = margins['xpu:3']-display/GIB
arms['a'].update(period_forecast_s=[6.25,6.70], ratio_forecast=[6.25/7,6.7/7])
arms['b'].update(period_forecast_s=[6.0,6.5], ratio_forecast=[6/7,6.5/7])
arms['c'].update(period_forecast_s=[6.5,6.95], ratio_forecast=[6.5/7,6.95/7])
assert not arms['a']['admitted_for_cpu_preparation'] and not arms['b']['admitted_for_cpu_preparation']
assert arms['c']['admitted_for_cpu_preparation']
out = dict(schema='ltx.continuation134.evidence.v1', run=str(RUN), parent_run=str(PARENT),
    boundaries=dict(memory_and_parity='stream chunks0..30 inclusive, plus separate nine qualification rows',
                    periods='23 differences: chunk7→8 through29→30; commit and submit measured separately',
                    buckets='chunks7..29 inclusive; bucket medians are not additive'),
    coordinator_early=dict(period_s=5.213, n=23, ratio=5.213/6, source='owner brief; original interval selection unspecified'),
    qualification=dict(passed=True, verdict_sha256=sources[str(RUN/'stream-qualification-verdict.json')]['sha256']),
    periods={k: dict(stats(v), values=v) for k,v in periods.items()}, buckets=buckets, decode_buckets=decode_buckets,
    parity=parity, stream_memory=mem, qualification_memory=memory(qualification),
    snapshots=dict(count=len(snapshots), dual=sum(s['dual'] for s in snapshots),
        all_dual_agree=True, minimum_margin_bytes=min(s['min_margin_bytes'] for s in snapshots),
        minimum_margin_card='xpu:0', minimum_margin_phase='B-before/B-after'),
    capture=dict(growth_bytes=growth, growth_gib=growth/GIB, old_estimate_gib=3430940672/GIB*361/256,
                 admission=qdecodes[3]['cone_graph_memory_admission']),
    census=dict(floors_gib=FLOORS, screening_gib=.75, dg0_predecode_admission_baseline_bytes=base,
        dg0_all_phase_minimum_bytes=tail_base,
        c_double_conservative_margin_gib=tail_base/GIB-display/GIB-9-.75,
        baseline_sources=[d['run_name'] for d in qdecodes[:3]],
        full_169_graph_reserve_bytes=reserve, full_169_display_reserve_bytes=display,
        observed_145_to_169_losses_gib=deltas, replica_weights_gib=replica, arms=arms,
        limitations=['Physical samples and extrapolated reserves are not isolated peak bounds.',
                    'No saving from allocator release or inactive graph storage is credited.',
                    'Adding only the display reserve increment to a sampled145 tail undercharges the full reserve.',
                    'Full original card3 display qualification remains charged for the replica arm.']),
    sources=sources)
target=HERE/'continuation134-evidence.json'
with target.open('x') as stream:
    json.dump(out,stream,indent=2,sort_keys=True);stream.write('\n')
print(json.dumps(dict(output=str(target), sources=len(sources), arms=arms, period={k:median(v) for k,v in periods.items()}),indent=2))
