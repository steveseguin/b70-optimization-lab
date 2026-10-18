"""Refresh the class table on CPU; include GDN only after a complete clean receipt."""
import collections
import gzip
import hashlib
import json
import statistics
from pathlib import Path
from byte_model import account, DIRECTORY

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
QSA = P.parent / 'packet107-specialised-layers'
ROOF = 537_000  # read+write bytes/us; decimal 537 GB/s

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate(rows, layer):
    """Sum events within each call; reject missing, duplicate or inconsistent data."""
    if layer == 4:
        assert all(r['mode'] == 'current' for r in rows), 'GDN specialised arm forbidden'
    current = [r for r in rows if r['mode'] == 'current']
    assert len(current) == 100, 'require 50 current iterations per context'
    result = collections.defaultdict(list)
    for context in (128, 4096):
        group = [r for r in current if r['occupied_context'] == context]
        assert len(group) == 50 and {r['iteration'] for r in group} == set(range(50))
        classes = None
        for r in group:
            assert r['layer'] == layer and r['position'] == context - 1
            assert r['warmup'] == (r['iteration'] < 10)
            totals = collections.Counter()
            assert r['submissions'] == len(r['events'])
            assert len({e['id'] for e in r['events']}) == len(r['events'])
            for e in r['events']:
                assert e['end_ns'] > e['start_ns']
                totals[e['class']] += e['end_ns'] - e['start_ns']
            assert dict(totals) == r['classes_ns'] and sum(totals.values()) == r['gpu_ns']
            assert not any(k.startswith('p107.') for k in totals)
            if classes is None:
                classes = set(totals)
            assert classes == set(totals)
            if not r['warmup']:
                for key, ns in totals.items():
                    result[context, key].append(ns / 1000)
    assert all(len(v) == 40 for v in result.values())
    return result

def ingest(base, name, layer):
    native = base / 'native'
    window_path = base / 'window.json'
    receipt_path = native / 'receipt.json'
    timing_path = native / 'iterations.jsonl'
    snapshot = P / 'evidence' / ('timing-' + name + '.jsonl.gz')
    if not timing_path.exists():
        window_path = P / 'evidence' / (name + '-window.json')
        receipt_path = P / 'evidence' / (name + '-receipt.json')
    window = json.loads(window_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    assert window['passed'] and window['drained'] and window['device_executed']
    assert receipt['passed'] and receipt['safe_to_exit'] and receipt['device_executed']
    assert receipt['timing_pair_checks'] == 100 and receipt['checks'] == (644 if layer == 3 else 572)
    assert receipt['route_set_counts'] == {str(layer): 4}
    assert receipt['arithmetic'] == 'iq3-p49-split32-v1'
    for key in ('dispatch-speed6.json', 'selection.json'):
        assert sha(base.parent.parent / key) == sha(P / key), 'measurement selection/dispatch mismatch'
    data = timing_path.read_bytes() if timing_path.exists() else gzip.decompress(snapshot.read_bytes())
    result = validate([json.loads(s) for s in data.splitlines()], layer)
    snapshot = P / 'evidence' / ('timing-' + name + '.jsonl.gz')
    if snapshot.exists():
        assert gzip.decompress(snapshot.read_bytes()) == data
    else:
        snapshot.write_bytes(gzip.compress(data, mtime=0))
    for src, suffix in ((window_path, 'window'), (receipt_path, 'receipt')):
        dest = P / 'evidence' / (name + '-' + suffix + '.json')
        if dest.exists():
            assert dest.read_bytes() == src.read_bytes()
        else:
            dest.write_bytes(src.read_bytes())
    return result, dict(name=name, source=str((native / 'iterations.jsonl').relative_to(ROOT)),
                        sha256=hashlib.sha256(data).hexdigest(), snapshot=str(snapshot.relative_to(P)),
                        window_sha256=sha(window_path), receipt_sha256=sha(receipt_path))

def main():
    from build_engine import limits
    limits()
    sources = []; grouped = collections.defaultdict(list); owners = collections.Counter()
    for name, base, layer in [('qsa-B-1', QSA / 'evidence/micro-B-1', 3),
                               ('qsa-B-2', QSA / 'evidence/micro-B-2', 3)]:
        data, pin = ingest(base, name, layer); sources.append(pin); owners[layer] += 1
        for (context, key), values in data.items():
            grouped[layer, context, key].append(statistics.median(values))
    pending = []
    for base in sorted((P / 'evidence').glob('micro-B-*')):
        if not (base / 'window.json').exists():
            pending.append(str(base.relative_to(P))); continue
        window = json.loads((base / 'window.json').read_text())
        if not window.get('passed'):
            pending.append(str(base.relative_to(P))); continue
        data, pin = ingest(base, 'gdn-' + base.name, 4); sources.append(pin); owners[4] += 1
        for (context, key), values in data.items():
            grouped[4, context, key].append(statistics.median(values))
    rows = []
    for (layer, context, key), medians in sorted(grouped.items()):
        b = account(layer, key, context - 1)
        us = statistics.median(medians); total = b['read_bytes'] + b['write_bytes']; floor = total / ROOF
        occ = 6 if layer == 3 else 18
        rows.append(dict(layer=layer, kind='QSA' if layer == 3 else 'GDN', context=context, site=key,
                         measured_us=us, owner_medians_us=medians, owners=len(medians), samples_per_owner=40,
                         occurrences_per_half=occ, floor_us=floor, effective_GBs=total / us / 1000,
                         roof_ratio=total / us / ROOF, above_floor_us=us-floor,
                         headroom_ms_per_half=max(0, us-floor) * occ / 1000, **b))
    # Read every available negative index, including other lane files, and pin them.
    negatives = sorted(
        ROOT / line for line in __import__('subprocess').check_output(
            ['rg', '--files', '--hidden', '-g', 'DO-NOT-REPEAT.md', '-g', '!**/.git/**'], cwd=ROOT, text=True).splitlines())
    closed = ROOT / 'experiments/own-xpu-runtime/ops/screen-cleanup/closed.json'
    audit = dict(closed_sha256=sha(closed), files={str(f.relative_to(ROOT)):sha(f) for f in negatives})
    (P / 'evidence/exclusions.json').write_text(json.dumps(audit, indent=2)+'\n')
    result = dict(schema='packet110.roofline.v1', roofline_GBs=537, device_executed_by_analysis=False,
                  timing_definition='median of per-process medians of complete class event sums; 40 measured calls/context/owner',
                  byte_definition='source-derived useful global-byte floor, not measured DRAM traffic',
                  sources=sources, directory_sha256=sha(DIRECTORY), byte_model_sha256=sha(P/'byte_model.py'),
                  gdn_status='measured' if owners[4] else 'pending coordinator', pending=pending, rows=rows)
    (P / 'roofline.json').write_text(json.dumps(result, indent=2)+'\n')
    lines = ['# Packet110: fresh per-class GPU roofline', '',
      'Packet107 current QSA, two fresh processes; packet110 current GDN if its clean coordinator receipt is present. '
      'Only occupied contexts 128 and 4096 are measured. All numbers below are synthetic complete-layer diagnostics.', '',
      '**Useful-byte throughput is not measured DRAM bandwidth.** The source model counts distinct useful weight fields and '
      'input/state bytes, plus global intermediate reads/writes. Cached duplicate loads, instruction fetch, lookup tables, '
      'cache-line overfetch and hardware transactions are not measured. The 537 GB/s copy reference uses total read+write bytes. '
      'The difference above this memory-only floor is an opportunity budget, not an attainable speedup.', '',
      'For each iteration, sum all events for a class before taking its median. Take each process median over exactly 40 '
      'post-warm-up calls, then the median of process medians. The JSON retains each process separately. '
      '`attention`, `qsa.attention`, `qsa.ik` and `moe` contain multiple events; `small.ffn.q6` includes router/shared gate/up/router. '
      'Do not interpret it as a standalone router measurement.', '',
      'Formulas: GB/s = (read B + write B) / µs / 1000; ratio = GB/s / 537; floor µs = bytes / 537000; '
      'above-floor µs = measured µs − floor; headroom ms/half = max(0, above-floor µs) × occurrences / 1000.', '',
      'Occurrences are 6 QSA and 18 GDN layers per half. This is representative-layer scaling, **not a measured half time**. '
      'Layer0 has different formats, and PLE, head, draft, rollback, host gaps and inter-card transfers are excluded. '
      'No QSA time is multiplied by 24 or substituted for a GDN time. Packet107 selection retains production expert-down; '
      'later down-tile16/composite measurements have a different identity.', '',
      'GDN status: **'+result['gdn_status']+'**. '+('One GDN process is attribution only; it cannot support a speed verdict.' if owners[4] else
      'Run the proposed coordinator job, then rerun `roofline.py`; it fills both GDN tables and recomputes ranking without a GPU call.'), '',
      '[Machine-readable rows and input hashes](roofline.json); [byte formulas](byte_model.py); '
      '[source derivation](BYTE-MODEL.md); [excluded-arm inventory](evidence/exclusions.json).', '']
    for layer, kind in ((3,'QSA'),(4,'GDN')):
        for context in (128,4096):
            lines += [f'## {kind}, occupied context {context}', '']
            subset = [r for r in rows if r['layer']==layer and r['context']==context]
            if not subset:
                lines += ['Not measured. No historical or QSA timing substituted.', '']; continue
            lines += ['| Class | Read B/call | Write B/call | µs/call | GB/s | /537 | Floor µs | Above floor µs | × layers | Headroom ms/half |',
                      '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
            for r in sorted(subset,key=lambda r:-r['headroom_ms_per_half']):
                lines.append(f"| {r['site']} | {r['read_bytes']:,} | {r['write_bytes']:,} | {r['measured_us']:.3f} | {r['effective_GBs']:.2f} | {r['roof_ratio']:.3f} | {r['floor_us']:.3f} | {r['above_floor_us']:.3f} | {r['occurrences_per_half']} | {r['headroom_ms_per_half']:.4f} |")
            lines.append('')
    review = json.loads((P/'lever-review.json').read_text())
    if audit == review['closure_inputs']:
        lines += rank(rows, bool(owners[4]))
    else:
        lines += ['## Ranking needs a fresh closure review', '', 'Closure inputs changed since the pinned review. The timing/byte table is refreshed, but no stale lever ranking is emitted. Review the changed negative files before updating lever-review.json.']
    (P / 'ROOFLINE.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(rows=len(rows), owners=dict(owners), gdn_status=result['gdn_status'])))

def rank(rows, have_gdn):
    # Feasibility is an explicit judgement weight, not a measured probability.
    candidates = [
        ('Exact gate/up tile16 with existing half-cache (packet104b)', ['expsgate'], .65,
         'Separate open coordinator-authorized gate/up arm. Preserve E1, each chain and BF16 boundary. The 0.892953 operator ratio is only a feasibility clue; the original 15% gate failed and only its explicit screen override permits this arm.'),
        ('Exact shared-down/mixture/combine and activation epilogues (packet109)', ['shexpdown','moe','ffn.combine','shexpact','expsact'], .50,
         'Prepared complete-tuple epilogues keep rounded intermediates and production NaN behavior. Class headroom is a ceiling; the route body remains unchanged and its 18+ us is deliberately not credited.'),
        ('Pruned top10 selection network after unchanged normalized route probabilities', ['route'], .40,
         'New mechanism proposal: retain maximum/exp/denominator trees, compare rounded probabilities with ID ties, prune comparisons that cannot affect sorted top10. Distinct from production full bitonic sort and closed all-pairs/geometry arms. Needs a sorting-network proof and exact device gate; no code is implemented here.')]
    ranked=[]
    for name, sites, feasibility, why in candidates:
        relevant=[r for r in rows if r['context']==128 and r['site'] in sites]
        qsa=sum(r['headroom_ms_per_half'] for r in relevant if r['kind']=='QSA')
        gdn=sum(r['headroom_ms_per_half'] for r in relevant if r['kind']=='GDN')
        ranked.append((qsa+gdn,name,sites,feasibility,why,qsa,gdn))
    ranked.sort(key=lambda x:-(x[0]*x[3]))
    out=['## Three open exact levers, ranked for the next brief', '',
         'Rank on the 128-token budget. Feasibility weights are engineering judgements, not measured probabilities or expected gains. '
         'The score is headroom × feasibility; 4096-token results remain separate. '+
         ('GDN contributes its fresh representative-layer ×18 budget.' if have_gdn else 'Only the observed QSA ×6 contribution is ranked; the GDN ×18 contribution is pending. This ordering is provisional.'), '',
         '| Rank | Lever | QSA ms/half | GDN ms/half | Available headroom | Feasibility | Score ms/half |',
         '| ---: | --- | ---: | ---: | ---: | ---: | ---: |']
    for i,(total,name,sites,f,why,q,g) in enumerate(ranked,1):
        gs=f'{g:.4f}' if have_gdn else 'pending'
        out.append(f'| {i} | {name} | {q:.4f} | {gs} | {total:.4f} | {f:.2f} | {total*f:.4f} |')
    for _,name,sites,f,why,q,g in ranked:
        out += ['', f'**{name}.** {why}']
    out += ['', 'Exclusions: packet107 QSA sharing/GDN head-preparation, packet108 draft load8, packet104 non-gate tile arms, '
            'packet95/99/102 expert lookup/prefetch/batching, H1 HC cache, packet94 norm-consumer fusion, '
            'packet74 packed-dense and packet53b/67 HC geometry remain closed. Route-fast, rec-both-plus and E1 are already in '
            'this measurement. Down-tile16 is already banked in newer compositions; its old-control headroom is not a new lever. '
            'Q-gate has fresh excess, but its expanded Q6 read floor consumes most of the call; it does not displace these three '
            'without a distinct mechanism. No closed arm is reopened by this table.', '',
            'No lever was implemented or qualified here. The coordinator briefs the winner after checking the latest closure state.']
    return out

if __name__ == '__main__':
    main()
