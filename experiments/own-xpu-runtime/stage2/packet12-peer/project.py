#!/usr/bin/env python3
"""Conditional planning arithmetic only; no device, weight or network access."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent

def calculate():
    path = HERE.parent/'packet9-kopt4/receipts-card3-20261011/timing.json'
    raw = path.read_bytes()
    source = json.loads(raw)['projection']['rows']
    baseline = next(r for r in source if r['variant'] == 'experts_split4' and r['gdn_layers'] == 36)
    sequential = (34*baseline['gdn_ms']+baseline['ple_gdn_ms']+baseline['upgraded_gdn_ms']
                  +12*baseline['qsa_ms']+baseline['head_and_final_hc_ms']+baseline['embedding_floor_ms'])
    if abs(sequential-baseline['projected_ms_per_token']) > 1e-9:
        raise ValueError('packet9 projection no longer reconciles')
    scenarios = []
    for parallel_fraction in (1.0, 0.8):
        compute = sequential*(1-parallel_fraction/2)
        for exchanges in (48, 60, 96):
            for round_us in (20.0, 61.8, 200.0):
                exchange_ms = exchanges*round_us/1000
                scenarios.append(dict(parallel_fraction_assumed=parallel_fraction, exchanges=exchanges,
                                      round_us_assumed=round_us, compute_ms=compute, exchange_ms=exchange_ms,
                                      projected_ms=compute+exchange_ms, projected_tok_s=1000/(compute+exchange_ms),
                                      gain=sequential/(compute+exchange_ms)))
    max_hits = sum(math.comb(10,k)*max(k,10-k) for k in range(11))/2**10
    return dict(schema='own-runtime.peer.projection.v1', measured=False,
                source=str(path.relative_to(HERE.parents[3])), source_sha256=hashlib.sha256(raw).hexdigest(),
                checkpoint_layers=48, baseline=baseline, sequential_ms=sequential,
                expected_max_hits_uniform_independent=max_hits,
                two_card_payload_gain_with_HC_replica=2*4951240940/5626671340,
                optimistic_bounce_payload_us_per_round=4*10240/28e9*1e6,
                assumptions=['GEMV-only; not full decode or performance promotion',
                             '80% parallel fraction is a sensitivity choice, not a profile',
                             '61.8 us is an illustrative budget near unrelated XCCL scalar timing; not measured peer latency',
                             '48 exchanges assumes one/layer, 60 is stress count, 96 is two/layer before exact gathers and routing',
                             'D2H and H2D both assumed 28 GB/s for payload floor; small-copy latency unmeasured',
                             'No perfect route balance, halved kernel time or single-card parity has been demonstrated'],
                scenarios=scenarios)

if __name__ == '__main__':
    print(json.dumps(calculate(), indent=2))
