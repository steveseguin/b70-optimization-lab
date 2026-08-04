# Re-scoped decode targets, and what to run after the reboot

Date: 2026-08-04 America/Toronto

Status: **decisions taken by Steve on 2026-08-04: reboot the host, and re-scope
the 32K target rather than pursue a long-context drafter now.**

## Re-scoped 32K target

The original goal was >150 tok/s at 32,640 tokens with speculation. The measured
blocker is draft acceptance, not speed:

- step time is nearly flat with context: 24.0 ms at 1K, 27.3 ms at 32K
- per-position acceptance collapses 73.3% (1K) -> 53.1% (4K) -> **7.4%** (32K)
- the drafter is six `sliding_attention` layers, window 512, no full-attention
  layer, so its receptive field is ~3,072 tokens against 32,640

150 tok/s at 32K needs 4.09 tokens/step, i.e. **~76.6% per-position
acceptance** -- higher than this drafter achieves at 1K. Two reconfiguration
routes were measured and both fail: widening the window to 4096 makes acceptance
slightly *worse* (0.56% -> 0.47%), and deeper drafts are worth +2.5% because the
chain saturates at the prevailing `p`.

**New 32K target: 50-60 tok/s**, from work that is actually available:

| lever | est. contribution |
| :--- | ---: |
| collective time (measured floor 45.9 us x 112 calls/step = 5.14 ms of 26.5 ms) | ~1.24x |
| M=12 step-time kernel work | to be sized after the host is healthy |

That is ~1.3-1.5x on 39.589, so **50-60 tok/s**. Anything beyond it at 32K needs
a drafter trained for long context, which is deferred rather than abandoned --
drafter substitution is now proven quality-safe (output SHA identical across
arms), so it can be picked up cleanly whenever a candidate exists.

The 1K and no-speculation targets are unchanged:

- **250 @1K** needs 86.1% acceptance, or 1.64x faster steps, or a mix
- **100 no-spec** needs 10 ms/step at M=1 against 75 ms today -- **7.5x**, pure
  kernel work, fully independent of the drafter

## Post-reboot runbook

**1. Confirm the host is healthy before measuring anything.** Stock config, no
allocator flag, no profiler:

```bash
cd /home/steve/llm-optimizations/experiments/laguna-s-2.1-xpu-b70/tools
RUN=/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/postreboot-verify
LAGUNA_LONG_CANDIDATE_PROFILE=q12 \
LAGUNA_LONG_CASE_IDS=laguna-lc-32640-early \
LAGUNA_GPU_UTIL=0.80 \
./run_laguna_long_context_baseline.sh candidate "$RUN"
```

Pass condition: `timing.conventional_99_interval_first_100_tok_s` near **39.589**
and `prefill_tok_s_prometheus` near **7,345**. If it initialises without
`PYTORCH_ALLOC_CONF=expandable_segments:True`, the fragmentation is cleared.

**Do not proceed if this fails.** Nothing measured in the degraded state is
comparable, and no optimisation can be evaluated against a moving baseline.

**2. Consider the GuC firmware upgrade** in the same window: installed 70.44.1,
driver asks for 70.54.0, and the wedges present as `guc_exec_queue_timedout_job`.
It cost several run slots on 2026-08-04.

**3. Re-measure the decode breakdown properly.** The profiler cannot do this on
this stack -- it costs ~6x and inflates count-heavy kernels, which is how the
"collectives are 78% of device time" claim arose. Use standalone component
benchmarks, as `bench_laguna_xccl_allgather.py` does for the collective: no
model, no profiler, two minutes. Size attention and the MoE GEMM at decode
shapes against the 26.5 ms step budget.

**4. Then optimise the largest measured term**, and verify each change by
differential end-to-end timing -- change one thing, measure tok/s -- never by
per-kernel attribution under a profiler.

## Settings that must not leak into measurement runs

| setting | why |
| :--- | :--- |
| `PYTORCH_ALLOC_CONF=expandable_segments:True` | halves prefill, cuts decode 5x |
| torch profiler | ~6x slowdown; use for counts and candidates only |
| `FI_PROVIDER=` (empty) | not the same as unset; oneCCL fails ATL init |
| `LAGUNA_MIN_MEM_AVAILABLE_KB` below ~5 GiB | masks a real guard; the successful 2026-08-02 runs used 5242880 |

## Boundaries

No quantisation change, no caching or speculation setting used to inflate any
number. The 2026-08-02 figures quoted as the pass condition come from that run's
note. The protected `125.4619731637751 tok/s` conventional short-decode record
is untouched.
