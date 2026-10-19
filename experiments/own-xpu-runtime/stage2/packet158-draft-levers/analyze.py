"""CPU-only source/receipt accounting. Never imports or executes a runtime.

Run with nice19, CPUs8-15,24-31, python3 -B and closed stdin. Optional
--split-summary accepts only a complete real packet157 C/T/C/T/C summary.
All writes stay in this packet; no model payload is opened.
"""
import argparse
import datetime
import hashlib
import json
import resource
import shutil
import statistics
from pathlib import Path

P = Path(__file__).resolve().parent
S = P.parent
ROOT = S.parents[2]
GROUPS = ('input_norm_embedding_mix', 'attention_projections', 'attention',
          'routed_experts', 'shared_expert', 'final_norm', 'head_gemv',
          'argmax_publication')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def group(label):
    label = label.removeprefix('draft.')
    if label == 'logits':
        return 'head_gemv'
    if label == 'argmax' or label.startswith(('begin.', 'commit.')):
        return 'argmax_publication'
    if label.startswith('final.'):
        return 'final_norm'
    if 'shexp' in label or label == 'blk.0.shared_gate':
        return 'shared_expert'
    if any(x in label for x in ('exps', 'route', 'moe', 'ffn', 'hc.f')) or label == 'blk.0.gather':
        return 'routed_experts'
    if label in ('blk.0.qsa.qgate', 'blk.0.qsa.k', 'blk.0.qsa.v', 'blk.0.qsa.iq', 'blk.0.qsa.ik', 'blk.0.attention'):
        return 'attention_projections'
    if label == 'blk.0.attn.combine' or 'qsa' in label:
        return 'attention'
    if label.startswith(('merge.', 'blk.0.hc.a')):
        return 'input_norm_embedding_mix'
    raise ValueError('unclassified ' + label)


def bytes_at(context, census):
    # Packet122's unique useful-field model, with position-dependent QSA rows.
    rows = json.loads(json.dumps(census['contexts']['128']))
    selected = 4 * min(context // 4, 512) + context % 4
    rows['draft.blk.0.qsa.select']['activation_state_read_bytes'] = 512 * 2 + (context // 4) * 128 * 2
    rows['draft.blk.0.qsa.attention']['activation_state_read_bytes'] = 6144 * 4 + selected * 2048 + (selected + 1) * 4
    # Pool writes only on the fourth token. Packet122 measured multiples of4.
    if context % 4:
        row = rows['draft.blk.0.qsa.pool']
        row['weight_bytes'] = 0
        row['activation_state_read_bytes'] = 512 * 2 + 128 * 2
        row['write_bytes'] = 512 * 4 + 128 * 2
    result = dict.fromkeys(GROUPS, 0)
    for label, row in rows.items():
        result[group(label)] += sum(row[k] for k in ('weight_bytes', 'activation_state_read_bytes', 'write_bytes'))
    # Two 4-byte publication copies are included by packet157, not packet122.
    return result


def dot_work():
    h, low, mid, top, prefix = 2560, 320, 640, 10, 80128
    hc = 2 * (low * 4*h + 4*h * low)
    return {
        'input_norm_embedding_mix': 2*5*h*h + hc + 2*4*4*h,
        'attention_projections': 2*h*(12288+512+512+512+128+6144),
        'routed_experts': 2*top*3*mid*h + 2*512*h + hc + 2*4*4*h,
        'shared_expert': 2*3*mid*h + 2*h,
        'final_norm': hc,
        'head_gemv': 2*prefix*h,
        'argmax_publication': 0,
    }


def main():
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    ap = argparse.ArgumentParser()
    ap.add_argument('--split-summary', type=Path)
    args = ap.parse_args()
    assert shutil.disk_usage(P).free >= 27_000_000_000, 'CPU preparation below27GB floor'
    sources = {}

    def read(path):
        sources[str(path.relative_to(ROOT))] = sha(path)
        return json.loads(path.read_text())

    census = read(S/'packet122-draft-budget/roofline.json')
    historical = []
    for process in (1, 2):
        base = S/f'packet122-draft-budget/evidence/micro-B-{process}'
        window = read(base/'window.json')
        assert all(window.get(k) is True for k in ('passed', 'device_executed', 'drained', 'lease_released'))
        path = base/'native/iterations.jsonl'
        sources[str(path.relative_to(ROOT))] = sha(path)
        assert window['native_artifacts']['iterations.jsonl'] == sha(path)
        data = [json.loads(line) for line in path.open()]
        for context in (128, 4096):
            rows = [r for r in data if r['context'] == context and not r['warmup']]
            assert len(rows) == 40 and {r['iteration'] for r in rows} == set(range(10, 50))
            values = {g: [] for g in GROUPS}
            for row in rows:
                assert sum(row['classes_ns'].values()) == row['gpu_ns']
                assert set(row['classes_ns']) == set(census['contexts'][str(context)])
                sums = dict.fromkeys(GROUPS, 0.)
                for label, ns in row['classes_ns'].items():
                    sums[group(label)] += ns/1e6
                for g, ms in sums.items():
                    values[g].append(ms)
            counts = bytes_at(context, census)
            historical.append(dict(process=process, context=context, repeats=40,
                rows=[dict(group=g, useful_bytes=counts[g], memory_reference_ms=counts[g]/537e6,
                           measured_ms=statistics.mean(values[g]),
                           gap_ms=statistics.mean(values[g])-counts[g]/537e6) for g in GROUPS]))

    current = None
    if args.split_summary:
        path = args.split_summary.resolve()
        assert path.is_relative_to(S/'packet157-draft-decomp/v5/evidence')
        full = read(path)
        assert full['passed'] and full['all_13_exact'] and full['draft_proposals_identical']
        d = full['draft_decomposition']
        assert d['device_evidence'] and [v['choice'] for v in d['views']] == ['control','candidate','control','candidate','control']
        requests = [r for v in d['views'] if v['choice']=='candidate' for r in v['requests']]
        assert len(requests)==24 and all(r['cycles'] for r in requests)
        current = []
        for g in GROUPS:
            # Match packet157's equal-view/equal-prompt, then equal-cycle means.
            bs = statistics.mean(statistics.mean(bytes_at(c['position'], census)[g] for c in r['cycles']) for r in requests)
            if g == 'argmax_publication':
                bs += 16  # two 4-byte reads+writes
            ms = statistics.mean(r['groups'][g]['device_ms'] for r in requests)
            host = statistics.mean(r['groups'][g]['host_issue_ms'] for r in requests)
            current.append(dict(group=g, useful_bytes=bs, memory_reference_ms=bs/537e6,
                                measured_ms=ms, gap_ms=ms-bs/537e6, host_issue_ms=host))

    selected = current or [dict(group=g,
        useful_bytes=historical[0]['rows'][i]['useful_bytes'],
        memory_reference_ms=historical[0]['rows'][i]['memory_reference_ms'],
        measured_ms=statistics.mean(h['rows'][i]['measured_ms'] for h in historical if h['context']==128),
        gap_ms=statistics.mean(h['rows'][i]['gap_ms'] for h in historical if h['context']==128)) for i,g in enumerate(GROUPS)]
    selected.sort(key=lambda r:r['gap_ms'], reverse=True)
    result = dict(schema='packet158.draft-roofline.v1', design_only=True, device_executed=False,
        generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), bandwidth_GB_s=537,
        measurement_scope='packet157 complete bracket' if current else 'packet122 cyclic replay;128 occupied tokens;two processes',
        historical=historical, packet157=current, ranked=selected, leading_dot_flops=dot_work(),
        warning='Useful-byte reference, not measured DRAM traffic or attainable savings. Negative gaps retained. Host and device times overlap.',
        sources=sources)
    (P/'roofline.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Per-draft byte reference and measured gaps','',
        'Scope: '+result['measurement_scope']+'. This is diagnostic evidence, not a speed result.', '',
        '| Rank | Group | Useful bytes | /537 GB/s ms | Measured ms | Signed gap ms |',
        '| ---: | --- | ---: | ---: | ---: | ---: |']
    for n,r in enumerate(selected,1):
        lines.append(f"| {n} | {r['group']} | {r['useful_bytes']:,.1f} | {r['memory_reference_ms']:.6f} | {r['measured_ms']:.6f} | {r['gap_ms']:+.6f} |")
    lines += ['', 'Host issue: packet154 control median **1.571 ms/cycle**, not a ninth additive GPU kernel; no GPU roofline/gap applies. See [source map and arithmetic](SOURCE-MAP.md).', '',
        'The head reads 3,200 useful bytes per row but retains a 3,380-byte storage stride. Its negative signed gap is evidence that a copy-bandwidth reference is not a hard latency floor. Do not promote a negative gap to a speedup.', '',
        'The useful-byte model omits repeated cache-served reads, scratch traffic, metadata/control traffic and instruction costs. In particular hidden projection has four independent input vectors; 13,107,200 unique weight bytes correspond to 52,428,800 logical weight-byte loads before cache/compiler reuse. The attention byte model is a K/V union, not the repeated loads by 24 query heads. No compute ceiling is borrowed from a different precision.', '',
        'All group times are means of complete per-step event sums; class medians are never added. The two historical processes each contribute 40 non-warmup replays. They are cyclic-input operator diagnostics, not cold prompt results. Source hashes and individual process rows are in [roofline.json](roofline.json).', '',
        '## Historical context sensitivity', '',
        '| Group | 128-token time ms (P1 / P2) | 128-token gap ms (P1 / P2) | 4096-token time ms (P1 / P2) | 4096-token gap ms (P1 / P2) |',
        '| --- | ---: | ---: | ---: | ---: |']
    for i,g in enumerate(GROUPS):
        h128=[h['rows'][i] for h in historical if h['context']==128]
        h4096=[h['rows'][i] for h in historical if h['context']==4096]
        fmt=lambda rows,key:' / '.join(f"{r[key]:.6f}" for r in rows)
        lines.append(f"| {g} | {fmt(h128,'measured_ms')} | {fmt(h128,'gap_ms')} | {fmt(h4096,'measured_ms')} | {fmt(h4096,'gap_ms')} |")
    lines += ['', 'These are the two measured context points. No interpolation or extrapolation is a measurement. Live packet157 positions, when available, price analytical bytes only; their time must come from their own events.', '']
    (P/'ROOFLINE.md').write_text('\n'.join(lines))
    print(json.dumps(dict(scope=result['measurement_scope'],top_two=[r['group'] for r in selected[:2]],source_count=len(sources))))


if __name__ == '__main__':
    main()
