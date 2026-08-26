# Current-f01e AutoRound TP4/MTP4 eager F16 quality recovery R1

State: **preregistered draft; not launched**.

The prior TP4/MTP4 expansion ended at 32K with a runtime-fatal XPU GDN
speculative-shape assertion after streaming 126 tokens that exactly matched
the target prefix. The engine died before the quality battery, so the missing
quality receipt is not an observed model-quality mismatch. The 2K result also
already diverged from TP4/MTP0 at token 90. This recovery therefore does not
request 2K or 32K.

One fresh TP4/MTP4 eager/F16 server runs exactly four requests in order: 4K,
8K, 16K, and 24K. The 4K, 16K, and 24K responses must pass exact-depth,
128-token TP4/MTP0 parity, cache-zero, and isolated finite positive conserved
acceptance. The 8K request is reproduction-only: it must reproduce the
quarantined TP4/MTP4 parent candidate with 97/124 acceptance and the same
token-99 divergence. Reproduction cannot make 8K measured or publishable.

Only after all four requests pass their intended gates does the same server run
the full quality suite against the completed same-topology TP4/MTP0 baseline.
`pass_all`, `baseline_match_all`, seven exact cases, eight deterministic
repeats, the long-context needle, and explicit cache zero on all 16 usage
records are mandatory.

A complete global pass may freeze only 4K, 16K, and 24K for explicit human
Grade C publication. It does not authorize automatic publication. The prior 2K
and 8K quarantines remain, 32K remains a runtime-fatal incomplete diagnostic,
and x=0 remains missing. No diagnostic speed, existing 8K value, graph route,
headline, protected value, LocalMaxxing result, or descendant configuration
may be replaced.

The only mechanism change from the TP4/MTP0 baseline is native embedded MTP4:
`qwen3_next_mtp`, four speculative tokens, resolved at startup as `mtp`.
Identity stays on the official f01e image and exact AutoRound revision, TP4 on
`ZE_AFFINITY_MASK=0,1,2,3`, memory utilization 0.60, graph off, F16/auto KV,
one sequence, and a fresh ext4 rank-isolated cache. Startup, requests, and
cleanup are bounded; EXIT/INT/TERM and all-render-node cleanup remain strict.

Static check:

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-r1.sh --check
```

Execution command (not run during packet preparation):

```bash
experiments/qwen38-27b-b70/scripts/run-20260826-qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-r1.sh \
  --execute \
  --ack 'RUN qwen38-official-f01e-autoround-tp4-mtp4-f16-eager-quality-recovery-20260826-r1'
```
