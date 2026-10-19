"""Packet171: recompute one-card host-boundary numbers from packet58as v5 evidence.

CPU only; reads the retained packet58as/58aq per-token streams (no model reads).
Usage: nice -n 19 python3 -B measure_58as_host.py > measured.json </dev/null
"""
import glob, hashlib, json, os, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
S2 = ROOT / 'experiments/own-xpu-runtime/stage2'
AS = S2 / 'packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/run/run'
AQ = S2 / 'packet58aq-onecard-split/screen/evidence/card0-58aq-split-a/resident/WSCREEN/run/run'
AS_VIEWS = ['A0', 'B0', 'A1', 'B1', 'A2']  # A = 1 ms poll parent, B = spin (58as)


def digest(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def tokens(root, view):
    rows = [json.loads(l) for f in sorted(glob.glob(f'{root}/{view}/*/timings.jsonl')) for l in open(f)]
    return [r for r in rows if r.get('kind') == 'generated_token' and r['generated_index'] >= 2]


def other(r):
    return r['wall_ms'] - r['prepare_ms'] - r['enqueue_loop_ms'] - r['wait_ms'] - r['transfer_wall_ms']


def per_token(root, view):
    t = tokens(root, view)
    m = lambda k: round(st.mean(r[k] for r in t), 4)
    md = lambda xs: round(st.median(xs), 4)
    slow = [r for r in t if r['transfer_wall_ms'] > 1.0]
    fast = [r for r in t if r['transfer_wall_ms'] <= 1.0]
    sm = lambda rs, k: round(st.mean(r[k] for r in rs), 4)
    # Within each request: does a slow token-boundary readback follow a token whose
    # pre-enqueue host span ("other") was high (fill-submission position)?
    same = [0, 0]; nxt = [0, 0]
    for f in glob.glob(f'{root}/{view}/*/timings.jsonl'):
        rr = [json.loads(l) for l in open(f)]
        rr = [r for r in rr if r.get('kind') == 'generated_token' and r['generated_index'] >= 2]
        for i, r in enumerate(rr):
            if other(r) > 1.8:
                same[0] += 1; same[1] += r['transfer_wall_ms'] > 1
                if i + 1 < len(rr):
                    nxt[0] += 1; nxt[1] += rr[i + 1]['transfer_wall_ms'] > 1
    return dict(
        tokens=len(t), wall_ms=m('wall_ms'), median_wall_ms=md([r['wall_ms'] for r in t]),
        prepare_ms=m('prepare_ms'), enqueue_loop_ms=m('enqueue_loop_ms'), wait_ms=m('wait_ms'),
        transfer_wall_ms=m('transfer_wall_ms'), median_transfer_wall_ms=md([r['transfer_wall_ms'] for r in t]),
        other_ms=round(st.mean(other(r) for r in t), 4), median_other_ms=md([other(r) for r in t]),
        host_waits=m('host_waits'), kernel_submissions=m('kernel_submissions'),
        voluntary_context_switches=m('thread_voluntary_context_switches'),
        copy_counts=t[0]['copy_counts'],
        slow_readback_fraction=round(len(slow) / len(t), 4),
        slow_tokens=dict(wall_ms=sm(slow, 'wall_ms'), wait_ms=sm(slow, 'wait_ms'), transfer_wall_ms=sm(slow, 'transfer_wall_ms'),
                         other_ms=round(st.mean(other(r) for r in slow), 4)),
        fast_tokens=dict(wall_ms=sm(fast, 'wall_ms'), wait_ms=sm(fast, 'wait_ms'), transfer_wall_ms=sm(fast, 'transfer_wall_ms'),
                         other_ms=round(st.mean(other(r) for r in fast), 4)),
        p_slow_readback_given_same_token_high_other=round(same[1] / max(same[0], 1), 4),
        p_slow_readback_given_previous_token_high_other=round(nxt[1] / max(nxt[0], 1), 4),
    )


def publication(cache_log, views):
    rows = [json.loads(l) for l in open(cache_log)]
    n = len(rows) // len(views)
    assert n * len(views) == len(rows), 'equal positions per view'
    out = {}
    for i, v in enumerate(views):
        s = rows[i * n:(i + 1) * n]
        d = [q['publication_host_ms_total'] - p['publication_host_ms_total'] for p, q in zip(s, s[1:])]
        u = [q['publication_uploads_total'] - p['publication_uploads_total'] for p, q in zip(s, s[1:])]
        fb = [q['fill_bytes_total'] - p['fill_bytes_total'] for p, q in zip(s, s[1:])]
        filling = [x for x in fb if x > 0]
        out[v] = dict(positions=len(d), publication_host_ms_per_position=round(st.mean(d), 4),
                      publications_per_position=round(sum(u) / len(u), 4),
                      fill_positions_fraction=round(len(filling) / len(fb), 4),
                      fill_mb_per_filling_position=round(st.mean(filling) / 1e6, 2) if filling else 0)
    return out


def main():
    views = {v: per_token(AS, v) for v in AS_VIEWS}
    pub = publication(AS / 'cache.jsonl', AS_VIEWS)
    aq = json.loads((AQ.parent / 'summary.json').read_text())['segments']['A0']
    inputs = [dict(name=Path(p).name, parent_relpath=str(Path(p).relative_to(ROOT)), parent_digest=digest(p))
              for p in [AS / 'cache.jsonl', AS.parent / 'summary.json', AQ.parent / 'summary.json',
                        S2 / 'packet58as-onecard-spinwait/screen/evidence/card0-58as-v5-a/resident/WSCREEN/summary.json']]
    b = [views['B0'], views['B1']]
    spin_pub = st.mean(pub[v]['publication_host_ms_per_position'] for v in ('B0', 'B1'))
    construction_submission = aq['construction_ms'] + aq['submission_ms']
    derived = dict(
        spin_publication_total_ms_per_token=round(spin_pub, 4),
        poll_era_publication_drain_ms_per_token_58aq=round(aq['drain_ms'], 4),
        construction_plus_submission_ms_58aq=round(construction_submission, 4),
        spin_publication_drain_ms_per_token_upper=round(max(spin_pub - construction_submission, 0.0), 4),
        spin_readback_excess_ms_per_token=round(st.mean(x['transfer_wall_ms'] for x in b) - st.mean(x['fast_tokens']['transfer_wall_ms'] for x in b), 4),
        spin_slow_token_wait_excess_ms_per_token=round(st.mean(x['slow_readback_fraction'] * (x['slow_tokens']['wait_ms'] - x['fast_tokens']['wait_ms']) for x in b), 4),
        spin_wall_ms_per_token=round(st.mean(x['wall_ms'] for x in b), 4),
        spin_sleep_cycle_us_estimate=round(1000 * st.mean(x['wait_ms'] / x['voluntary_context_switches'] for x in b), 1),
    )
    json.dump(dict(schema='packet171.onecard-host-measure.v1', device_executed=False, model_reads=False,
                   views=views, publication=pub, derived=derived, inputs=inputs), sys.stdout, indent=1)
    sys.stdout.write('\n')


if __name__ == '__main__':
    main()
