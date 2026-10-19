"""Optimistic certification-work lower bounds on real head rows and hidden states.

The true final maximum is donated before any row is read. This is deliberately
more favorable than a realizable running maximum, and cannot certify a speedup.
It can reject a proposed saving ceiling. All positions/schemes fixed in PLAN.md.
"""
import csv
import gzip
import io
import json
import resource
import time

from audit import P, guard
import prepare


def rounded_upper(value):
    # FP64 -> FP32 upward -> BF16 RNE, all monotone. One extra float32 ulp is
    # conservative even when the first cast was already upward or exact.
    return prepare.bf(np.nextafter(value.astype(np.float32), np.float32(np.inf)))


def main():
    guard()
    global np
    import numpy as np
    prepare.np = np
    started = time.monotonic()
    positions = json.loads((P/'evidence/positions.json').read_text())
    preparation = json.loads((P/'evidence/preparation.json').read_text())
    raw = gzip.decompress((P/'evidence/hidden.bf16.gz').read_bytes())
    assert prepare.sha(raw) == preparation['hidden_sha256']
    x = prepare.unpack(raw).reshape(-1, 2560).astype(np.float64)
    assert len(x) == len(positions) == 385
    max_logit = np.array([r['max_logit'] for r in positions])
    sizes = np.array([80128 if r['head'] == 'draft' else 248320 for r in positions])
    xnorm = np.linalg.norm(x, axis=1)
    x256 = np.linalg.norm(x.reshape(-1, 10, 256), axis=2)
    x16 = np.linalg.norm(x.reshape(-1, 160, 16), axis=2)
    schemes = ['row_cs', 'block256_cs', 'quant16_cs', 'partial256', 'quant16_partial256']
    reads = {s: np.zeros(len(x), np.int64) for s in schemes}
    touches = {s: np.zeros(len(x), np.int64) for s in schemes}
    # Track target shards separately; global row average must not hide an
    # expensive prefix/cheap suffix imbalance.
    partitions = {p: {s: np.zeros(len(x), np.int64) for s in schemes}
                  for p in ('prefix202240', 'suffix46080')}
    wstore = prepare.Weights()
    norm_sha = __import__('hashlib').sha256()
    start = 0
    while start < 248320:
        guard()
        count = min(1024, 248320-start, 202240-start if start < 202240 else 248320-start,
                    80128-start if start < 80128 else 248320-start)
        w = wstore.rows('output.weight', start, count).astype(np.float64)
        assert np.isfinite(w).all()
        wn = np.linalg.norm(w, axis=1)
        norm_sha.update(wn.tobytes())
        w256 = np.linalg.norm(w.reshape(count, 10, 256), axis=2)
        w16 = np.linalg.norm(w.reshape(count, 160, 16), axis=2)
        cs = wn[:, None]*xnorm
        # Strongly inside finite normal range for these particular states.
        assert cs.max() < 1e30 and np.isfinite(x).all()
        u = 2.0**-24
        error = (86*u/(1-86*u))*cs + 5151*2.0**-149/(1-86*u)
        error += 1e-10*np.maximum(cs, 1)  # outward FP64 norm/dot envelope
        b256 = w256@x256.T
        b16 = w16@x16.T
        valid = start < sizes
        part = 'prefix202240' if start < 202240 else 'suffix46080'
        for name, bound in [('row_cs', cs), ('block256_cs', b256), ('quant16_cs', b16)]:
            required = (rounded_upper(bound+error) >= max_logit) & valid
            n = required.sum(axis=0)
            touches[name] += n
            reads[name] += n*2560
            partitions[part][name] += n*2560
        live = {
            'partial256': (rounded_upper(b256+error) >= max_logit) & valid,
            'quant16_partial256': (rounded_upper(b16+error) >= max_logit) & valid,
        }
        for name in live:
            touches[name] += live[name].sum(axis=0)
        dot = np.zeros_like(cs)
        remain256, remain16 = b256.copy(), b16.copy()
        for block in range(10):
            for name in live:
                n = live[name].sum(axis=0)*256
                reads[name] += n
                partitions[part][name] += n
            lo, hi = block*256, (block+1)*256
            dot += w[:, lo:hi]@x[:, lo:hi].T
            remain256 -= w256[:, block: block+1]*x256[:, block]
            remain16 -= w16[:, block*16:(block+1)*16]@x16[:, block*16:(block+1)*16].T
            for name, remainder in [('partial256', remain256), ('quant16_partial256', remain16)]:
                upper = rounded_upper(dot+np.maximum(remainder, 0)+error)
                live[name] &= upper >= max_logit
        start += count
        if start % 16384 == 0 or start == 248320:
            print(json.dumps(dict(rows=start, seconds=time.monotonic()-started)), flush=True)
    output = []
    for j, r in enumerate(positions):
        for scheme in schemes:
            output.append(dict(index=j, head=r['head'], corpus=r['corpus'], prompt=r['prompt'],
                               scheme=scheme, rows=int(sizes[j]),
                               touched_row_fraction=float(touches[scheme][j]/sizes[j]),
                               read_equivalent_fraction=float(reads[scheme][j]/(sizes[j]*2560)),
                               target_prefix_read_fraction=float(partitions['prefix202240'][scheme][j]/(202240*2560)) if r['head']=='target' else None,
                               target_suffix_read_fraction=float(partitions['suffix46080'][scheme][j]/(46080*2560)) if r['head']=='target' else None))
    f = io.StringIO()
    writer = csv.DictWriter(f, fieldnames=list(output[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(output)
    (P/'evidence/fractions.csv').write_text(f.getvalue())
    summaries = []
    for corpus in sorted({r['corpus'] for r in output}):
        for scheme in schemes:
            rows = [r for r in output if r['corpus']==corpus and r['scheme']==scheme]
            vals = np.array([r['read_equivalent_fraction'] for r in rows])
            summaries.append(dict(corpus=corpus, head=rows[0]['head'], scheme=scheme, positions=len(rows),
                                  mean=float(vals.mean()), minimum=float(vals.min()), median=float(np.median(vals)),
                                  maximum=float(vals.max()), mean_touched=float(np.mean([r['touched_row_fraction'] for r in rows]))))
    result = dict(schema='packet161.optimistic-read-lower-bound.v1',
                  description='Real weights/states, donated exact final maximum; optimistic required work, not implemented early-exit timings.',
                  summaries=summaries, all_weights_sha256=prepare.sha(json.dumps(wstore.reads, sort_keys=True).encode()),
                  row_norms_sha256=norm_sha.hexdigest(), weight_reads=wstore.reads,
                  seconds=time.monotonic()-started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  device_executed=False, complete_requested_coverage=False,
                  missing='Exact draft states across all 12 prompts and independent corpus; no independent draft fraction measured.')
    (P/'evidence/analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(summaries=summaries, peak_rss_kib=result['peak_rss_kib'])), flush=True)


if __name__ == '__main__':
    main()
