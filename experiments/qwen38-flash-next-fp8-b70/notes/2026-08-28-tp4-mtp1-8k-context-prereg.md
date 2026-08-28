# Flash-Next TP4 MTP1 active-8K preregistration

Date: 2026-08-28

## Objective and scope

Classify the remaining TP4/EP4, eager-text, native-MTP1, active-8K practical
matrix cell without changing any existing result. This is one server boot and
one p8192/o128 request. It is not a speed qualification, repeat battery,
minimum-cache claim, or deployment promotion.

MTP1 configured-512 and exact-4K are already Grade-C research screens at
9.372 and 8.904 tok/s. Separate active-1K and active-2K arms passed admission
but returned no completed output before their fixed bounds; the 2K teardown
also recorded all-card resets. The subsequent recovery qualification, MTP2/8K,
and MTP3/8K arms left the exact four-card topology discoverable and idle with
no B70-addressed event in the last window. This new arm therefore requires a
fresh four-rank preflight and changes no prior interpretation.

## Frozen server and cache identity

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` from
  `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernel checkout
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, staged runtime build
  `2f829747503c77d4814834dffd0840fb1dd9f75a` at
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`;
- TP4/EP4, allgather/reduce-scatter, Triton MoE, BF16 activation, native MTP1,
  eager/graph-off, BLHNC, prefix cache off, async off, one sequence, 64 maximum
  batched tokens, maximum model length 8,448, reasoning parser absent;
- selective UVA placement of the PLE and input embedding, requiring the exact
  12.22-GiB cumulative offload receipt on all four ranks;
- fixed cache exactly 376,569,856 bytes / 32 blocks. Require exactly 32 blocks
  and at least 8,320 reported tokens before the request; stop without resizing
  if the live admission gate fails;
- campaign `qwen38-flash-next-fp8-tp4-ep4-eager-mtp1-8448-r1`, attempt 1,
  port 19670, state `/tmp/q38-mtp1-8448-supervisor`, and fresh campaign-specific
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

Require positive draft, draft-token, accepted-token, and position-zero deltas.
Require exactly one position delta equal to the accepted-token delta. Exact
MTP0 parity is separate. A mismatch is a scoped cross-runtime/cache Grade-D
quarantine, not isolated proof that MTP1 caused it.

## Bounds, lifecycle, and adjudication

Keep the existing 300-second engine worker-response gate. The request has a
1,200-second inner and 1,210-second outer client bound; the complete lifecycle
has a 3,000-second bound. The larger request bound is frozen before launch to
avoid repeating MTP3/8K's 900-second no-receipt boundary; it is not evidence
that MTP1 will complete. Preserve every artifact written by the shared harness
plus complete client/server logs.

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
Grade-C research screen. A parity mismatch is Grade D. No-receipt, timeout,
counter, malformed-receipt, lifecycle, or B70 failure is a bounded Grade-D
stop. In every outcome, observed rate is diagnostic and all existing speeds
remain unchanged.

## Frozen executable identities

- delegated base launcher:
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- MTP1/8K launcher wrapper:
  `b121ee84312dd0d8525f440bd37f70f3a347eb5c4f8609379e27ee33615c6f16`;
- one-request client:
  `b03a8c3b72f6e5b21562471aaeff01583a9663ab83626139a48e36e9958c7d0b`;
- lifecycle supervisor:
  `da65bfae43847b571070477333edb0614d58350f15dd3bb1a442489b191796e6`.

These identities are frozen before execution. Any later change requires a new
note, attempt, and paths.
