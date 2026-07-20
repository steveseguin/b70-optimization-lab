# 2026-07-20 Option 4 Phase 1 M1 attention oracle index failure

## Numbers first

- **Verdict: FAIL / STOPPED at Step 1.** Do not claim a Phase 1 component or
  endpoint result.
- Requested packet root:
  `/mnt/fast-ai/deepseek-v4-corpora/m1-attention-boundary-v1-20260720T232130Z`.
  It contains **0 files**, **0/344** required rank/layer/bucket instances,
  **0/43 layers**, and **0/2 buckets**. There is no packet checksum.
- Bucket 1 `SWA-resident`, decode anchor `64`: first armed request returned
  HTTP 500 before any record flushed. Bucket 2
  `compressed+SWA-window-full`, decode anchor `512`: not attempted.
- Component gate: changed input **0/40**; fixed-address replay **0/70**;
  positions 28 and 58 **not run**; per-layer parity **0/43**; eager/V1
  submission-boundary counts **not measured**.
- Endpoint gate: PIECEWISE nesting **not run**; eager break and host sync count
  **not measured**; control/candidate median ms/token **not measured**; output
  token exactness **not run**. The threshold remains `22.381408 ms/token`
  against the `22.881408 ms/token` baseline.
- Phase 2 FFN/MoE boundary: **NO-GO** because the mandatory Phase 1 packet is
  still absent.
- Postflight: the oracle stopped, port 18080 is closed, and all four B70s are
  free for AI work. Card 0 retains only the desktop allocation.

## What the repair proved

The original non-contiguous compressor-cache warmup failure is fixed in vLLM
commit `265f53ddd848e4f1379031c56d3acf797f795994` on `option4-decoder`.
Capture-only bookkeeping now requires an armed eligible forward, the two
unsafe `state_cache.view(total_state_slots, -1)` calls are gone, compressor
rows are gathered according to the real logical first-two-dimension strides,
and zero-sized fixed-binding sentinels retain the original storage.

The focused CPU test creates a non-contiguous cache and checks the gathered
values bitwise against direct scalar row indexing. It also proves an enabled
recorder remains inactive without an armed forward. Result: **2/2 passed**.
Ruff, compileall, and `git diff --check` also passed.

Most importantly, the corrected TP4 service loaded all 46 K160 shards, passed
the four-rank XCCL preflight, completed sparse-MLA dummy warmup, and reached
ready on `127.0.0.1:18080`. This closes the earlier `.view` failure without
changing model weights, arithmetic, XPU kernels, or oneCCL.

## New failed gate

The first armed singleton decode at anchor 64 triggered XPU device assertions
from `ATen/native/xpu/sycl/Indexing.h:622`:

```text
Assertion `index >= -sizes_[i] && index < sizes_[i] && "index out of bounds"`
failed.
```

Rank 0 then died, the executor stopped the remaining ranks, and the API
returned HTTP 500. The failure occurs only after capture is armed; unarmed
warmup completed. This localizes the problem to capture-time execution or
bookkeeping, but the asynchronous device assertion does not identify which
capture gather supplied the invalid index. No speculative diagnosis is
promoted as a cause.

The JIT monitor also reported first-request compilation for six decode
kernels, including QNorm/RoPE insertion and split QK/LSE/PV. This independently
violates the required explicit-warmup/no-lazy-compilation condition. Per the
run instruction, the attempt stopped instead of patching and retrying past the
failed Step 1 gate.

## Preserved identity and evidence

- K160 revision:
  `7c360e1cd4a5168099dbc54d16d929bf6df04990`;
- model manifest SHA-256:
  `08535b4ad7fd94419c7eadb1f6cf7f1de583d64f92a1760c86aa238972904e78`;
- capture vLLM commit:
  `265f53ddd848e4f1379031c56d3acf797f795994`;
- XPU kernel source commit:
  `5a1e9fa4602f69302dc50ecf85b06b6f86762117`;
- oneCCL source commit:
  `48fda4f0e074db005596d6899d5227d3f0316c12`;
- loaded oneCCL binary SHA-256:
  `53de2b6d65265803d64773546c1166ceed4ae43737f0fded776f5847b4b461c9`;
- run root:
  `/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/option4-m1-attention-oracle-20260720T232130Z`;
- `identity.txt` SHA-256:
  `dfe2996294ed7923143ac6dcb8b445cb33e4d5a6adba5dd97a2c5fcd86d5ac56`;
- `preflight.log` SHA-256:
  `8579b52098e76ad3bbaa2150253fc7ccd464d3eda550a068f4412b653005fed0`;
- `server.log` SHA-256:
  `7f0e3049fb4e94b673f83931875439b1a9d95592004069340985d10026283b68`;
- preserved patch:
  `patches/deepseek-v4-flash-xpu-b70/2026-07-20-option4-m1-attention-oracle-index-failure.patch`,
  SHA-256
  `6d30f0ff7d8da9fa8449eb1a3df6ac1dcb69835688b7b1556d717c2fc6f422f9`;
- structured result:
  `experiments/deepseek-v4-flash-reap-xpu-b70/data/option4-m1-attention-phase1-failed-index-20260720.json`.

No XPU shared object was rebuilt. No LocalMaxxing action occurred. No frozen
held-out pack was opened, searched, listed, or modified.
