# Qwen27 Accepted-Prefix GDN Tape Contract

Date: 2026-07-05

Purpose:

- Start the next source-level lane after closing Python serial GDN as too slow.
- Define and verify the exact state contract a native accepted-prefix
  GDN/DeltaNet tape must satisfy before endpoint throughput work.

## Current executable contract

`scripts/check-gdn-spec-recurrent-exact.py` now checks two things:

1. The existing synthetic recurrent-state parity check: serially processing
   speculative rows one token at a time must produce the same SSM states and
   outputs as the reference sequential update.
2. A new accepted-prefix commit prototype covering both:
   - SSM recurrent state;
   - conv rolling-window state.

The contract:

- prefix `0` is the exact base running conv+SSM state before verifier spec
  rows;
- prefix `i` is the exact conv+SSM state after accepting the first `i`
  draft/verifier rows;
- the runner must normalize sampler/raw accepted counts into an accepted
  draft-prefix length in `[0, k]`;
- commit copies exactly one prefix row per request into the running row:
  - reject -> prefix `0`;
  - partial accept `a` -> prefix `a`;
  - full accept -> prefix `k`;
- commit must be GPU-side/fixed-shape in the hot path, not a Python per-layer
  loop.

This contract is intentionally stronger than the old accepted-count packed
path. The synthetic check still verifies that the old packed path does **not**
match the sequential reference (`old_accepted_count_path_equal=false`).

## Validation run

Commands:

```bash
cd /home/steve/llm-optimizations
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-spec-recurrent-exact.py \
  --device xpu:0 --num-reqs 2 --spec-len 3 --heads 2 --dim 8
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-spec-recurrent-exact.py \
  --device xpu:1 --num-reqs 3 --spec-len 4 --heads 2 --dim 8
/home/steve/.venvs/vllm-xpu/bin/python scripts/check-gdn-spec-recurrent-exact.py \
  --device xpu:2 --num-reqs 4 --spec-len 5 --heads 3 --dim 8
```

Results:

| Device | num reqs | spec len | recurrent state | output | accepted-prefix SSM commit | accepted-prefix conv commit | old packed path |
|---|---:|---:|---|---|---|---|---|
| `xpu:0` | 2 | 3 | exact | exact | exact | exact | mismatch as expected |
| `xpu:1` | 3 | 4 | exact | exact | exact | exact | mismatch as expected |
| `xpu:2` | 4 | 5 | exact | exact | exact | exact | mismatch as expected |

All accepted-prefix commit max absolute diffs were `0.0`.

## Why this matters

The current fast draft-INT4 path is quality-invalid around state boundaries,
while ReplaySSM is correct but below the record. Python serial GDN is also
closed: forcing native spec decode off collapses to about `9.7-12.3 tok/s`.

The next implementation should therefore publish fixed prefix rows in the
native GDN/spec path and commit one selected prefix row after sampling. The
script above is the unit-level target before endpoint claims.

## Next source work

1. Add a trace-only native/spec path that exposes prefix `0..k` conv+SSM row
   digests for one request/layer, without changing output behavior.
2. Compare those digests against the synthetic/sequential contract and the
   clean ReplaySSM path for accepted counts `0,1,2,3`.
3. Implement a default-off GPU-side commit prototype once trace parity is
   understood.
4. Only then run repeat64 and strict fresh endpoint gates.

Expected payoff:

- This can plausibly rescue the fast draft-INT4 `70-72 tok/s` family as a
  strict-valid result above the current `65.276 tok/s` record.
- It is not sufficient alone for `100+ tok/s`; that will still require higher
  accepted tokens per target step, a stronger drafter/branch-regenerate path,
  or target-forward reduction.

