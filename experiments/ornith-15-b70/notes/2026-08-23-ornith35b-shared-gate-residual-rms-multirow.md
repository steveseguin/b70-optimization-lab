# Ornith 1.5 35B: multi-row shared-gate/residual/RMS follow-up

## Decision

Do **not** add a second aggregate flag to the user guide.

Extending the accepted full shared-expert gate → shared multiply → routed add
→ residual add → RMSNorm → weight multiply fusion from one row to 2–32 rows is
output-exact and positive when tested alone, but it is weaker than the already
documented generic multi-row patch. When stacked on that patch its incremental
gain is only **+0.276%**, with overlapping warm-sample ranges. The simpler
generic patch remains the aggregate recommendation.

## Safety and exactness

Ornith 1.5 35B is `qwen35moe`. At four concurrent engine sequences, each token
has an independent scalar shared-expert gate and 2048-element row. The
candidate launches one workgroup per row and preserves all graph-visible FP32
materialization boundaries. It does not reorder routed-expert GEMV arithmetic.

The control and candidate each generated 80 greedy tokens for four sequences
from seed 4242. Complete stdout was byte-identical in both standalone and
stacked tests:

```text
1b50819cab9e15ac7e5219f05e8f76878686ded24b3a99ebde6616dad4b621f1
```

Each candidate executed the full fusion 2,800 times. In the stacked test, the
generic multi-row MoE reduction retained 2,800 hits; the full-chain fusion
replaced 2,800 of the generic patch's 5,600 residual/RMS hits.

## Focused four-sequence measurements

These are directly measured `llama-batched-bench` raw-engine aggregate decode
rates, not HTTP users/sec:

```bash
llama-batched-bench -m "$MODEL" -ngl all -fa on \
  -c 65536 -npp 1024 -ntg 256 -npl 4,4,4 --output-format jsonl
```

Protocol: process-isolated C/B/B/C, discard each process's first cold row, and
retain two warm rows. No value is interpolated or extrapolated.

| comparison | control warm samples | candidate warm samples | mean change |
| --- | --- | --- | ---: |
| standalone vs accepted base | 120.691, 120.649, 120.392, 120.260 | 121.966, 121.982, 121.975, 122.024 | **+1.235%** |
| stacked on generic multi-row patch | 122.989, 123.203, 123.150, 123.516 | 123.625, 123.741, 123.395, 123.457 | **+0.276%** |

The standalone research patch is
`../patches/llamacpp-ornith15-shared-gate-residual-rms-multirow-positive-20260823.patch`.
It is valid but weaker than the generic +2.21% patch.

The stack-only patch is
`../patches/llamacpp-ornith15-shared-gate-residual-rms-multirow-stack-marginal-20260823.patch`.
It applies after the generic patch and is explicitly not recommended.

Machine-readable results and exact raw-artifact names are in
`../data/2026-08-23-ornith35b-shared-gate-residual-rms-multirow-summary.json`.

## Integrity

- Model SHA-256: `ca6ea26329c88b78ffd90a85163be2e746c2fafd1024f56db47e499f117f9a7f`
- Accepted source-diff SHA-256 after restoration:
  `7b9204f8f44608fc5b1858a15498b3cf9bf52b4f02c27c0f91a1807af5b5d15d`
- A zero-row final-control attempt during interrupted process turnover is
  excluded; a clean process retry supplied the retained control-B rows.
