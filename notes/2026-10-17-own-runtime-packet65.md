# Packet65 — routed expert occupancy, October 17, 2026

CPU preparation is complete; device quality and the requested **30% class
latency reduction remain unmeasured**. No GPU, service, model payload, sudo,
power setting, host-memory setting or reboot was used. The coordinator owns
all device windows. Production stays selected until matching device evidence
passes the gate.

Packet: [packet65-expert-occupancy](../experiments/own-xpu-runtime/stage2/packet65-expert-occupancy/README.md).
It copies packet64’s sources and reuses its unchanged compiled objects where
possible. Packet64, packet61x, `screen/v3-packet64` and
`screen/v3-packet64-lanes` were not edited. All CPU work ran at nice19 on
cores 8–15,24–31 with Python `-B`; compiler jobs were serial within each build,
and the largest measured build child RSS was 726,620 KiB. Build size at receipt
was 162,166,188 logical bytes including retained offline compilation scratch.

## Diagnosis and decision

The production call is `p49d::expert`, not the older kernel suggested by the
inherited dispatch label. Gate/up already uses V8 split streams; down uses V16.
Each already processes all ten selected experts in one launch, 200 workgroups
of 256 work-items, eight SG32 per workgroup. Both launches schedule 1,600
subgroups. Useful packed weight bytes are 10,496,000 for gate/up and 9,216,000
for down. Actual resident occupancy and outstanding memory requests are not
known from CPU work. A 32-core calculation is explicitly conditional and
counts total scheduled work, not simultaneous occupancy.

The new choices are `wg64`, `wg128`, `prefetch64`, and `wide64`, alongside
`production`. They preserve the packet49 logical lane sums, adjacent reduction
tree, BF16 stores, route/status/error behavior, model weights and BF16 KV.
`wide64` shares raw code/scale loads among adjacent chains without buffering
extra decoded float arrays. The CPU fixture also compares raw FP32 sums so a
BF16-rounded coincidence cannot hide reassociation.

Offline BMG-G31 compilation of the actual checked expert translation unit
reports **128 configured GRFs and no spills for all ten kernels**. `wide64`
reduces static load instructions from 79 to 51 for gate/up and 103 to 79 for
down; overall instructions fall from 2,469 to 1,993 and 3,368 to 2,955.
Those counts are mechanism evidence, not projected speedups. Screen it first.
The prefetch arm retains earlier loads but the compiler waits on them before
current arithmetic, and its instruction counts rise; preserve this uncertainty.

Gate/up are already combined. Down needs activated results across workgroups,
so a naïve fused launch has no legal global barrier. Activation fusion alone
has too little scope to meet the class bar. Previously failed persistent/SLM,
free-order and V16 gate/up arms stay closed.

[Full source diagnosis and assembly evidence](../experiments/own-xpu-runtime/stage2/packet65-expert-occupancy/OCCUPANCY.md).

## Lean gates

- GNU 13.3 and Intel 2026.0 host compilers each pass two fresh CPU processes.
  Each checks **72 actual production/candidate cases, 110,592 raw FP32 chains
  and 3,456 trees**. Full 640/2,560-row production geometry uses ten selected
  experts; extra padded, invalid/partial route, inactive/error, NaN, infinity,
  subnormal and signed-zero cases pass without tolerance.
- All expected/candidate streams across compilers and repeats have 561,856
  bytes and SHA256
  `a32abd7c067fa57b926230521022b16321c9ea4dc0de5e320335d4166528af87`.
- The complete host engine matches packet64’s 96 retained target fixtures and
  24 tokens for every selection, and enabling attribution preserves those
  bytes. This mini integration check supplements the production-width expert
  checks; it is not full-model device parity.
- The actual native selection parser passes 14 acceptance/refusal cases.
- Five candidate views share one binary, with separate selection/placement and
  CPU seals. The copied screen wrapper preserves the v3 packet64 protocol and
  adds whole-host campaign admission; frozen queued wrappers are unchanged.

Current device binary SHA256:
`8de8ec649cf378715cc6b59e358675a90c33ba2d104aa62a2d8100d41d0cf277`.

## Coordinator screen and integration bar

[Exact commands](../experiments/own-xpu-runtime/stage2/packet65-expert-occupancy/WINDOW.md)
run a preregistered, sequential campaign: unprofiled control/candidate screens
first, then two fresh attributed control/candidate pairs in AB/BA order.
Every screen uses the incident64 check plus all twelve 128-token prompts,
with packet49 token checks and request resets. No failed screen is retried.

The timing harness runs **inside the real target layer composition**, all
48 layers, sampling fixed decode fixtures 9–16. It sums actual GPU event
intervals within each complete target half, takes the median across fixtures,
sums rank medians, then balances prompt classes. Cancelled partial halves and
draft events cannot become a fast complete class sample. It never subtracts
timestamps across cards. Component timings remain available separately.

The primary class is packet57’s full `moe_experts`: router, route, gate/up,
activation, down, mixture and FFN combine. It must use **at most 70% of the
control time in each of two fresh matched pairs**, with neither rank regressing.
The approximately 0.192 ms parent class cannot be replaced by only the
approximately 0.129 ms gate/up-plus-down sum. The analyzer requires matched
configuration, prompts, outputs, composition and packet49 oracle evidence.

The campaign reserves the whole host through the existing cooperative lane
protocol, also holds both legacy screen locks, and checks foreign Xe clients.
No campaign or device screen ran during this preparation. A passing class
screen is still diagnostic: a full fresh quality/record chain is needed before
integrating a winner or publishing a model speed. The 512-token final gate is
not claimed by a 128-token screen.

## Quick lane token screens prepared on CPU

The first decision now takes six fresh screens per lane, with both card pairs
available for work at once. Lane A runs production, wide64, wg64, wg128,
prefetch64, production; lane B reverses the four candidates. Each takes only
its own lane lease and legacy lock, keeps the same 13 exact requests and
packet49 authority, and leaves the shared memory, device isolation, fault,
graceful drain and teardown-spacing checks in place. There are five 90-second
gaps per lane. The 3,600-second watchdog exceeds four times the expected screen
time. Roughly 30 minutes per lane is an estimate; admission and shared drains
can add time.

The frozen lane wrappers could not directly admit packet65 placement 1 and
only allowed lane B live entry. Packet65's selections bind its original wrapper
sources, so those files also remain byte-for-byte unchanged. The additional
[`screen/quick/`](../experiments/own-xpu-runtime/stage2/packet65-expert-occupancy/screen/quick/README.md)
copy has its own wrapper seal and reuses the original seals. No selection or
binary was rebuilt or resealed. The whole-host class campaign remains available
for a winner after this cheap end-to-end token-rate decision.

CPU checks passed: original and new wrapper seal verification, all twelve
`--plan` jobs, mocked six-screen runs on both lanes with five 90-second gaps,
stop-on-failure, cooperative lease overlap and hold/refusal checks, device
isolation, full incident64 plus twelve-request worker flow, and class/token
accounting. No CPU model, GPU, service or device window ran. Work stayed on the
helper cores at nice19, Python `-B`, with stdin closed; scripts use small bounded
metadata, receipts and streamed binary hashes, below the 8 GB budget. This task did not edit any frozen tree or existing selection file. A concurrent
coordinator reseal changed packet64 files while this task ran; those changes
are left with their owner and excluded from this commit. Seal verification
used 23,596 KiB peak RSS.

[Coordinator commands and job files](../experiments/own-xpu-runtime/stage2/packet65-expert-occupancy/screen/quick/README.md#coordinator-commands),
[CPU validation](../experiments/own-xpu-runtime/stage2/packet65-expert-occupancy/screen/quick/validation.json).
The helper reports class-balanced tok/s against the mean of the two production
screens on the same lane and independently checks all 13 token streams. These
are diagnostic 128-token screens. No device quality or speed result is claimed;
the coordinator's launch is next, followed by the class gate for a winner.
