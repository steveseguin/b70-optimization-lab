# Qwen3.8 official FP8 TP2 W8A16 + MTP1 result

The publisher-supplied MTP head is useful on this profile. With the lab's
default-off block-W8A16 dispatch, official MTP1 raises fresh-response
single-user decode from `35.011369` to **`61.699580 tok/s`** (`+76.23%`). The
selected 512-token scheduler profile peaks at **`1,091.642460 tok/s`** with 64
simultaneous short-context HTTP requests, the median of three measured
repeats. That clears the campaign's 875 and 1,000 tok/s aggregate targets.

This does not replace the target-only/MTP0 aggregate profile. MTP0 remains
`3.32%` faster at its own c128 optimum (`1,112.570323 tok/s`). The useful
deployment split is therefore explicit:

- MTP1 for interactive and moderate-concurrency service: `61.70 tok/s` for
  one user and `1,091.64 tok/s` aggregate at c64;
- MTP0 for the highest measured aggregate throughput: `1,112.57 tok/s` at
  c128.

These figures must not be combined into one unnamed row. The MTP1 service is
limited to 256 total tokens, uses `max_num_batched_tokens=512`, and has no 32K
measurement.

## Runtime fix required for concurrent MTP

The older pinned XPU kernel package is safe for synchronized c8 but crashes as
soon as continuous batching mixes speculative decode rows with newly arriving
prefill rows. The retained c16 failure is:

> causal_conv1d does not support spec-decode and non-spec (prefill + decode)
> tokens in the same invocation

The selected image pins XPU kernels at
`1e90ffa672ba02f17a909da11838a4c55b199783`, which includes upstream commits
`40541752f4f7fdef3cab471038c775e3f8d42838` and
`1d5b4f5e5ddd8da96ea23c76d7e7421b00083fdb`. Those commits split the GDN
speculative and non-speculative paths and add the mixed-batch correction. This
is an upstream Intel/vLLM-XPU contribution and is credited as such; the lab's
work here is the integration, W8A16 combination, workload localization, and
validation on two B70s.

## Validation boundary

- sequential semantic suite: 7/7 exact cases;
- repeat stability: 8/8;
- c64 concurrent semantic canary: 512/512, with no cached prompts;
- complete token IDs and cross-task isolation: passed;
- greedy token identity remains batch-shape-dependent, as in the MTP0 service;
- both GPUs remained normal after the campaign.

The exact structured result is
[`2026-08-26-qwen38-fp8-block-w8a16-mtp1-tp2-summary.json`](../data/2026-08-26-qwen38-fp8-block-w8a16-mtp1-tp2-summary.json).
The raw directory retains the rejected old-kernel crash, container/image
receipts, single-user receipts, scheduler screens, output-audited ladders, and
quality results. Nothing in this result is interpolated or extrapolated.
