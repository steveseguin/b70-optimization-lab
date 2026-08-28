# Flash-Next TP4 MTP4 active-8K preregistration

Date: 2026-08-28

## Objective and scope

Classify the last missing TP4/EP4, eager-text, native-MTP4, active-8K
practical matrix cell. This is one server boot and one p8192/o128 request. It
is not a speed qualification, repeat battery, minimum-cache claim, or
deployment promotion.

MTP4 configured-512 remains a Grade-C research screen at 20.727 tok/s.
Separate active-1K evidence passed exact parity twice but is quarantined by its
frozen teardown rule. Active-2K produced no receipt before its fixed bound and
recorded resets on all four cards during teardown. Exact-4K stopped at 3,904
computed prompt tokens with no durable result. This is therefore the highest
risk remaining practical cell. The immediately preceding MTP1/8K arm completed
and its controlled shutdown passed every cleanup gate with no B70-addressed
event, so a fresh independently audited MTP4 attempt is allowed.

## Frozen server and cache identity

- model `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` from
  `/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8`;
- vLLM `1372c62d975c554f4b465c8299bc5f3295301ceb`, kernel checkout
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, staged runtime build
  `2f829747503c77d4814834dffd0840fb1dd9f75a` at
  `/mnt/usb-models/qwen38-build/runtime-core-moe-negidguard-b70`;
- TP4/EP4, allgather/reduce-scatter, Triton MoE, BF16 activation, native MTP4,
  eager/graph-off, BLHNC, prefix cache off, async off, one sequence, 64 maximum
  batched tokens, maximum model length 8,448, reasoning parser absent;
- selective UVA placement of the PLE and input embedding, requiring the exact
  12.22-GiB cumulative offload receipt on all four ranks;
- fixed cache exactly 423,641,088 bytes / 36 blocks. Require exactly 36 blocks
  and at least 8,320 reported tokens before the request; stop without resizing
  or retrying if live admission misses either gate;
- campaign `qwen38-flash-next-fp8-tp4-ep4-eager-mtp4-8448-r1`, attempt 1,
  port 19671, state `/tmp/q38-mtp4-8448-supervisor`, and fresh
  campaign-specific run/cache/compile/RPC/evidence paths.

The 36-block choice is frozen from prior live admission behavior. MTP4's
29-block boots reported capacities consistent with a 21-block fixed component
plus one block per 832 configured tokens. That predicts 32 blocks at 8,448;
using exactly 32 would expose no allocation margin and put p8192/o128 at about
98.5% of nominal capacity. Thirty-six blocks add only 44.9 MiB, predict 9,504
tokens / 1.125x maximum concurrency, and reduce nominal request occupancy to
about 87.5%. This is headroom, not a performance treatment.

## Frozen request, authority, and mechanism gates

Use `scripts/bench-openai-token-depth-suite.py` SHA-256
`8f162c1ab9fde7e0daffed2c4f0d6ff061ad6076c5de716e36f3d883ab4a1067`
and fixture SHA-256
`c44fccbaf600cc506d8ed0cc7357161057b86abc44469b611be71db97558061d`.
The prompt-token hash is
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
It used vLLM `658965050` and a 192-MiB cache, so any mismatch is a scoped
cross-runtime/cache Grade-D quarantine and not isolated proof that MTP4 caused
it. The current-source MTP2 raw receipt SHA-256
`409e4e58259085a8bb7253a23951b0e396f52d09555e5146a1c157d97e54a324`,
output hash `d3ce0631eb382e39168ee6bbbf177b0d49fbb27bc6c6466bcf215f16db8d0220`,
and text hash
`68c50214e241e6613efdd0b0bbbfea36995d917448b1db527f3dc3fb03cd8b70`
are a frozen non-gating descriptive comparator only.

Require positive draft, draft-token, and accepted-token deltas. Require exactly
four positive accepted-position deltas for positions zero through three, with
their sum equal to the accepted-token delta. Perfect acceptance or a fixed
acceptance ratio is not required.

## Bounds, lifecycle, and adjudication

Keep the existing 300-second engine worker-response gate. The request has a
1,200-second inner and 1,210-second outer client bound; the complete lifecycle
has a 3,000-second bound. Preserve every artifact written by the harness plus
complete client/server logs. Send no second request.

The persistent descendant-aware supervisor owns the exact launcher, server PID
and process group, port, state, and paths. A completed pass or parity
quarantine uses `STOP after completed MTP4 active-8K classification`; a
failed client uses `STOP after failed MTP4 active-8K request`. Postflight
requires no listener, owned process group, compile path, or RPC path; the
supervisor PID/process-group/return-code/stop receipts remain retained as
lifecycle evidence. It also requires exact rediscovery of the four B70
addresses, numeric memory below 256 MiB per card, and a successful bounded
kernel-journal capture. Any
B70 reset/fatal event blocks later GPU work pending recovery. Corrected-only
NVMe or root-port events are disclosed and block clean-host/deployment wording
but are not relabeled as B70 failures.

Generic plus mechanism plus exact MTP0 parity may fill only this capability
cell as a Grade-C research screen. A parity mismatch is Grade D. No-receipt,
timeout, counter, malformed-receipt, lifecycle, or B70 failure is a bounded
Grade-D stop. In every outcome, the observed rate is diagnostic only and all
existing speeds remain unchanged.

## Protected data identities

The run may change only the MTP4/8K practical cell, its derived contract
classification, concise family/site summary, and linked receipt:

- `estimates`: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`;
- `views`: `ead957373435d63c95a1768f3ebf8c629d4b8a1810789289fb6d26fb5f2d2ef4`;
- `featured_results`: `cd1a2c7a041e214385041a0fe8a1bc04e1a9cb61eb1a11364019317cc275e5cf`;
- packet featured metrics:
  `0b0299b1695f9bec672f2d8221908f6afc36c497c54bf8cb2ae6232deaf13ab1`;
- `run_measurements`:
  `0181835266b52796e0e2a127435217a9636de5c8744a90c258724e2b5693bbee`;
- `series_measurements`:
  `15aeda8bb39c6f68ad53652a5ed92f97373b3f7fcd757cadb2a2cfe9cd3a85a2`;
- other coverage views:
  `d1d50f356013eed81d06771366bb0cfdc932235113d8a4e6ff7781a2ad422391`;
- the other 24 practical cells:
  `d7d61e533ec6b748718d16861d15376feb96e7a76f110187716ec2f4ea8da45c`;
- the existing contract rules:
  `a8cde0fa0b8791020418d33d2ce1faae8a21b36542efa60cc60a2c747b379ab5`.

MTP4's retained 20.727 tok/s short-screen result must not be replaced by this
diagnostic context observation.

## Frozen executable identities

- delegated base launcher:
  `62b40c9268a665727ff3946a621e4fcd2db072ed0bd4595dde7a6a006083ccb7`;
- MTP4/8K launcher wrapper:
  `aff9bcb16136d31e2f0948585c1d6d1fc01b0dc6f2153f511458869ee0cc595c`;
- one-request client:
  `0ac27b14cef3e2f2d6f18246189c44dde02e9e77701dd1a01a1cf7952dc05a87`;
- lifecycle supervisor:
  `894b6b76c79a4c526a312e4525a2a346082977509c11c76001ff9ec72bd8421a`.

These identities are frozen before execution. Any later change requires a new
note, attempt, and paths.
