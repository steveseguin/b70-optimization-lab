# Replicated attention is implemented, correct, and does not fit on a B70

Date: 2026-08-05 America/Toronto

Status: **built, mechanism verified, and blocked on device memory. The blocker
is quantified rather than estimated: it needs roughly 3 GiB per rank more than
this hardware has at the required 32,768-token context.**

## What it is

The only lever this campaign has found that moves the decode step is the
**count of four-rank collective rendezvous**, worth **-21.7%** at q12 and
saturating at half. The 96 all-gathers are 48 attention O projections, 1 dense
MLP down and 47 MoE final combines, and only the attention half can be removed
exactly: give every rank all the heads and the output projection produces the
full hidden vector with no collective.

`VLLM_XPU_LAGUNA_REPLICATED_ATTENTION`, default off. The implementation is
small because `QKVParallelLinear`, `RowParallelLinear` and
`ColumnParallelLinear` already accept `disable_tp`, and `RowParallelLinear`'s
reduce path is guarded by `tp_size > 1`, so the collective disappears without
touching the collective module.

## The mechanism is verified

Two independent confirmations from the runs:

- **KV per token quadrupled exactly as predicted.** The server reported
  **32,867 tokens in 2.92 GiB = 90.9 KiB/token**, against the baseline's
  ~26 KiB/token. That is every rank holding all 8 KV heads instead of 2.
- **The topology expectation is right.** The audited target topology becomes
  **98 graphs / 97 eager breaks**, derived by subtracting the 48 boundaries the
  selector retires, and the runner's per-rank audit was updated to match.

One bug found and fixed along the way: the selector was inert on the first
attempt, because `attention_prefix` is rebound to `prefix` a few lines above
the gate, so `attention_prefix is None` was False for every target layer. The
run that exposed it reproduced the baseline exactly -- 146/145 topology,
unchanged KV -- which is what a correctly-inert flag should do.

## Why it does not fit

Per rank, on a 31.9 GiB B70, at the suite's required 32,768-token context:

| quantity | baseline | replicated |
| :--- | ---: | ---: |
| attention weights | 0.98 GiB | 3.94 GiB |
| KV per token | ~26 KiB | **90.9 KiB** |
| KV for one 32,768 sequence | ~0.83 GiB | **~2.89 GiB** |

The whole memory envelope was searched, and every setting fails for a different
reason:

| utilisation | KV | outcome |
| :--- | :--- | :--- |
| 0.97 | auto | rejected at startup: asks 29.39 GiB, 29.1 GiB free |
| 0.93 | auto | KV took 2.92 GiB / 32,867 tokens, then **graph capture OOM, 496 MiB short** |
| 0.82 | auto | **no memory for cache blocks**: weights consumed the budget |
| 0.95 | pinned 2.887 GiB | rejected: vLLM requires **at least 2.89 GiB** for one max-length request |
| 0.95 | pinned 2.933 GiB | **KV fits at 33,232 tokens**, then rank 2 dies during init |

Each attempt cleared the previous obstacle and hit the next. The final
configuration allocates the KV cache successfully and still cannot complete
initialisation, because weights plus 4x KV plus cudagraph capture exceeds the
device.

`--kv-cache-memory-bytes` was added to the harness (default unset) to stop vLLM
sizing KV to fill whatever the budget leaves; it moved the failure but did not
remove it.

Reducing `max_model_len` to 16,384 would halve the KV requirement and is enough
to fit, but **the v1 long-context suite requires `LAGUNA_MAX_MODEL_LEN=32768`**,
so no scored measurement can be taken that way.

## The honest verdict

**Replicated attention is not deployable on this hardware.** It is not a
correctness problem, not a contract problem, and not a kernel problem -- it is
about 3 GiB per rank short. It would fit on a 40 GiB device, or at a context
below ~16K, or with a model whose attention is not GQA-8.

The projected gain was in any case smaller than the diagnostic suggested. The
gather-skip arm removed collectives without adding work; replicated attention
removes 48 collectives but makes every rank compute **all 48 query heads
instead of 12**, roughly +2.7 ms per step against the -5.6 ms saved. The
expected net was nearer -11% (about 180 tok/s) than the -21.7% upper bound
(about 207).

So the campaign's one validated lever is, on this hardware, **unavailable**,
and the short-context target has no remaining identified path through the
collectives. What remains is the **~20.2 ms floor**, of which ~13 ms is still
unattributed.

## Disposition

The selector stays, default off, with its topology derivation and harness
wiring, because the implementation is correct and the blocker is hardware. It
must not be enabled on this machine.

## Boundaries

q12, depth 11, width 12, TP4, EP4, 32,768 max model length, `max_num_seqs=1`,
warm host, GPUs verified clear between attempts. Memory figures are read from
the servers' own reports; the "does not fit" conclusion is from five failed
initialisations across the utilisation range, not from arithmetic. No
quantisation change -- reducing KV precision would make it fit and is
explicitly not proposed. The protected `125.4619731637751 tok/s` conventional
short-decode record is untouched.
