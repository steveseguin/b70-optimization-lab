# Flash-Next TP4 MTP3 active-8K preregistration

Date: 2026-08-28

## Purpose and protection boundary

Classify exactly one missing practical website cell: official Flash-Next FP8,
TP4/EP4, eager text, native MTP3, and 8,192 active prompt tokens. MTP3 is the
next bounded arm because it already has a completed active-2K generic request
and a complete exact-4K pass. MTP1 has two first-request no-output results;
MTP4 has repeated stopped requests and four-card reset windows.

This is one server boot and one p8192/o128 request. No repeat, short battery,
second timing row, cache sweep, or other generation request is authorized. The
arm cannot replace or lower a featured, captured, certified, or prior matrix
speed. Any observed rate is diagnostic until all frozen gates are adjudicated.
The clean MTP2/8K B70 teardown authorizes only this separately preregistered
boot.

## Frozen server and cache identity

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` from
  `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernel checkout
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, staged runtime build
  `2f829747503c77d4814834dffd0840fb1dd9f75a` at
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`;
- TP4/EP4, allgather/reduce-scatter, Triton MoE, BF16 activation, native MTP3,
  eager/graph-off, BLHNC, prefix cache off, async off, one sequence, 64 maximum
  batched tokens, maximum model length 8,448, reasoning parser absent;
- selective UVA placement of the PLE and input embedding, requiring the exact
  12.22-GiB cumulative offload receipt on all four ranks;
- fixed cache exactly 376,569,856 bytes / 32 blocks. Existing block-demand
  evidence predicts 9,654 reported tokens. Require exactly 32 blocks and at
  least 8,320 reported tokens before the request; stop without resizing if the
  admission gate fails;
- campaign `qwen38-flash-next-fp8-tp4-ep4-eager-mtp3-8448-r1`, attempt 1,
  port 19669, state `/tmp/q38-mtp3-8448-supervisor`, and fresh campaign-specific
  run/cache/compile/RPC/evidence paths.

## Frozen request, authority, and comparator

Use `scripts/bench-openai-token-depth-suite.py` SHA-256
`8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`
and fixture SHA-256
`c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`.
The frozen prompt-token hash is
`6baa17bea14f0ecad7e4edf54a05256eafaef1d447a447569fd303371c671741`;
the request-payload hash is
`d2c65090ce71e4db33b834b3de55a82a8c4c2f9485baaf94adb156ee686a0e1b`.
Send temperature 0, top-p 1, seed 1, ignore-EOS, streaming token IDs, no prompt
truncation/cache/special tokens, exactly 8,192 prompt and 128 output tokens.
Require every generic gate, exact 8192/128/8320 usage, zero cached tokens,
length stop, 128 IDs, and the complete 100-event/99-interval window.

The only gating parity authority remains the MTP0 raw receipt SHA-256
`2a8bfbb133ae4cf1b54ee31fd1c632ea8f843b7109fa72baff5b69d357e453aa`
with output-token hash
`0efd150b868d63f11cb4327bec07b02c7778d137142495924139e5221b4cebd3`.
Explicitly disclose that it used vLLM `658965050` and a 192-MiB cache. The
current-source MTP2 raw receipt SHA-256
`409e4e58259085a8bb7253a23951b0e396f52d09555e5146a1c157d97e54a324`,
output hash `d3ce0631eb382e39168ee6bbbf177b0d49fbb27bc6c6466bcf215f16db8d0220`,
and text hash `68c50214e241e6613efdd0b0bbbfea36995d917448b1db527f3dc3fb03cd8b70`
are frozen as a non-gating descriptive comparator only.

Require positive draft, draft-token, accepted-token, and positions 0/1/2
deltas. Require exactly three position deltas whose sum equals the accepted-
token delta. Exact MTP0 parity is separate. A mismatch is a scoped cross-
runtime/cache Grade-D quarantine, not isolated proof that MTP3 caused it.

## Bounds, lifecycle, and adjudication

Keep the existing 300-second engine worker-response gate. The request has a
900-second inner and 910-second outer client bound; the complete lifecycle has
a 2,700-second bound. Preserve every artifact written by the shared harness
plus complete client/server logs; streaming events held only in memory are not
durably checkpointed on interruption.

The persistent managed supervisor must own the exact launcher, server PID and
process group, port, state, and paths. A completed pass or parity quarantine
uses one exact stop sentinel; a failed client uses the distinct failed-request
sentinel. Postflight requires no listener, owned process group, compile path,
or RPC path; exact rediscovery of the four B70 addresses; numeric memory below
256 MiB per card; and a successful bounded kernel-journal capture. Any B70
reset/fatal event blocks later GPU work pending recovery. Corrected-only NVMe
or root-port events are disclosed and block clean-host/deployment wording but
are not relabeled as B70 failures.

Generic plus MTP plus exact MTP0 parity may fill only this capability cell as a
Grade-C research screen. A parity mismatch is Grade D. No-output, timeout,
counter, malformed-receipt, lifecycle, or B70 failure is a bounded Grade-D
stop. In every outcome, observed rate is diagnostic and all existing speeds
remain unchanged.

## Frozen executable identities

- delegated base launcher:
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- MTP3/8K launcher wrapper:
  `fbf4e826b86d644aa5cf5421d86b406f115023cce8b1892a198d6b84de970d3b`;
- one-request client:
  `83e18abc031fccc7f5023258dd656852ca7ef5ec437c9c64e478da74b4a20674`;
- lifecycle supervisor:
  `94292d12f8de643cbe62c114dcf2f906450e7e04c75ffa914ddb18df3cc48ef1`.

These identities are frozen before execution. Any later change requires a new
note, attempt, and paths.

## Attempt 1 result

Attempt 1 passed the exact source/runtime, fresh four-rank, placement, served
identity, health, and capacity gates. The frozen 32-block allocation reported
9,654 tokens, and all four ranks recorded the required 12.22-GiB selective
offload receipt. The sole p8192/o128 request then reached the unchanged
900-second client bound without a completed response receipt or any durably
recorded output token. No second request was sent, no parity or MTP-counter
result exists, and no speed,
quality, or deployment credit is granted.

The failed-request sentinel reached the owned server group. The server drained
request processing, completed API shutdown, left no listener or recorded
process group, removed the compile and RPC paths, and returned all four cards
below 43 MiB. The supervisor retained return code 143 because this was
the explicitly failed path, not a completed classification; that code is
evidence of the deliberate launcher termination, not a teardown failure.
There was no B70-addressed event. The bounded window retained 33 corrected
APEI records / 34 corrected PCIe endpoint sections for local NVMe
`0000:01:00.0`; they block clean-host and deployment wording without proving
the request cause.

The 45-entry evidence manifest verifies and has SHA-256
`1f9dd8dcf27c928d9023d1a6ecc817e054ac0c33e20e6b60c8daa5ebcc76a053`.
This active-8K cell is a Grade-D bounded no-receipt quarantine. Existing MTP3
configured-512 and exact-4K results and every captured speed remain unchanged.
Receipt:
`experiments/qwen38-flash-next-fp8-b70/data/20260828-tp4-mtp3-8448-context-attempt1-bounded-negative.json`.
