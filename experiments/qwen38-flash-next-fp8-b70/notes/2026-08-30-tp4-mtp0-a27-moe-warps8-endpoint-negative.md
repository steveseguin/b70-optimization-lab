# Qwen3.8 Flash-Next FP8 A27 M4 MoE warps-8 result

Date: 2026-08-30
Status: rejected at endpoint speed and exact-4K repeat gates

A27 was the first and only full Flash-Next load in boot
`4a84e582-68ac-4958-8d08-3815fbe7aaf6`. The 131 local-NVMe shards loaded in at
most 80.25 seconds. All ranks retained the exact 11.92 GiB synchronous PLE
placement, and the server emitted the exact receipt selecting the frozen M4
warps-8 configuration with SHA-256 `f93b5e1d...bf7f`.

Recovery, the inherited accepted 6/7 semantic boundary, 16/16 short repeat,
exact-4K needle, and both cache-zero transport gates passed. The short rows
retained the protected output hash at `5.561458 / 5.473329 / 5.501703 tok/s`,
median `5.501703 tok/s`. That is 0.255% below the protected `5.515783 tok/s`
median. One fast row is insufficient; the treatment receives no endpoint speed
credit.

Exact-4K row 1 matched the retained authority at `5.105157 tok/s`, but row 2
returned a different hash at `5.302356 tok/s`. The final repeat/authority
assertion failed closed. The M4 config therefore cannot be promoted as a
reliable/lossless endpoint optimization.

The key performance learning is that the exact 20.2--21.1% real-weight M4
component improvement did not transfer measurably to the full TP4 target step.
M4 MoE is not a dominant endpoint bottleneck in this configuration, or its
savings are hidden by larger serial/communication work. Do not spend the next
boot on a matched control for a candidate whose median already failed to beat
the frontier. Preserve the component result, profile the full target step, and
continue the separately localized layer-1 GatedDeltaNet reliability work.

Teardown was clean: the listener and model processes disappeared, all four
cards returned to about 43 MiB, and host memory/swap recovered. Four corrected
Samsung-NVMe receive events appeared, one with a nonfatal status bit; there was
no reset, GPU loss, OOM, or freeze. Protected `5.515783 tok/s` target-only and
approximately `20.727 tok/s` MTP4 results remain unchanged.

Structured result:
[`20260830-tp4-mtp0-a27-moe-warps8-endpoint-negative.json`](../data/20260830-tp4-mtp0-a27-moe-warps8-endpoint-negative.json).
