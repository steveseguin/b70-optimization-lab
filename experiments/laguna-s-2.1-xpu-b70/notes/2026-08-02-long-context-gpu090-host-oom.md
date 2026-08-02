# Laguna 32K GPU-utilization 0.90 host-OOM interruption

Date: 2026-08-02 America/Toronto

## Classification

The first model-bearing 32K-capacity candidate run is an infrastructure loss,
not a valid 32K baseline and not a GPU-kernel failure. It used the intended
unchanged source identity, BF16 KV, `max_model_len=32768`, chunk size 8192,
and GPU memory utilization 0.90. The service started and accepted requests,
but the host entered global OOM before the first 1024-token request completed.
The machine was later rebooted while the first 4096-token request was still
blocked.

Sealed evidence:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-long-context-mbt8192-baseline-retry-20260802T170509Z
```

The preserved `bench.json` status is `RUNNING` with three completed rows. It
must never be promoted or summarized as a complete baseline.

## Completed diagnostic rows

All three exact 1024-token prompts returned all 128 requested tokens, reported
zero cached tokens, returned the exact input token array, and passed every
retrieval field. The first row included live JIT/graph-capture work and is not
a steady-state performance datum.

| case | Prometheus prefill tok/s | client TTFT s | conventional decode tok/s | retrieval |
|---|---:|---:|---:|---|
| early | 175.848 | 5.852 | 8.162 | pass |
| middle | 4854.042 | 0.215 | 153.480 | pass |
| late | 5158.627 | 0.202 | 152.315 | pass |

The middle/late rows show that M12/DFlash11 can sustain about 152--153 tok/s
for these live 1K-context prompts. They are useful diagnostic evidence, but
the run experienced host memory pressure and was not compared with the new q1
oracle, so they are not a replacement for the protected short-suite result.

## Failure evidence

The first kernel OOM event was at 13:08:32, during the first request rather
than during the later 4096-token request. Across the following minutes:

- the 8 GiB `/swap.img` had zero or only a few KiB free;
- the kernel repeatedly reported `global_oom` and killed small desktop
  processes rather than the protected model workers;
- four vLLM workers each held roughly 1.2--1.3 GiB resident and 1.6--1.7 GiB
  swapped, in addition to Xe/TTM GPU-backed allocations;
- ordinary page allocation failed in `ttm_pool_alloc_page` while exporting Xe
  GEM memory through DMA-BUF; and
- nominal free RAM was almost entirely unavailable CMA space, leaving the
  node `all_unreclaimable`.

The first 4096-token request was scheduled exactly as one 4096-token prefill,
with only 3.63% KV-cache use. It produced no response before the reboot. Its
result is therefore interrupted/inconclusive; KV capacity was not the limit.

After reboot, all four devices were idle. `xpu-smi diag -d -1 -l 1 -j`
passed environment, libraries, permissions, exclusivity, and light compute on
all four GPUs. Health reporting showed OK frequency and power; this hardware
does not expose determinate memory/temperature health through the installed
XPU-SMI version.

## Next controlled treatment

The 0.90 service reported capacity for 224,081 KV tokens, about 6.84 concurrent
32,768-token requests despite `max_num_seqs=1`. That reservation is unnecessary
for this test. Before any source optimization, the next run changes only GPU
memory utilization to 0.80 and selects the single 4096-early case. This is a
separate capacity identity, not a retry mislabeled as the 0.90 baseline.

The runner now records the requested utilization and selected cases, bounds
each request to 900 seconds, and stops the service if host available memory
drops below 12 GiB or free swap below 4 GiB. A clean 4K diagnostic is required
before the complete 1K--32K sweep resumes.
