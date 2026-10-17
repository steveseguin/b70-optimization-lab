# Packet53: production-order expert GEMV

Preparation is CPU-only. The coordinator owns every GPU window; no device
program, oracle, service, health probe or model server is started by this work.
The packet49 oracle unit and packet49c record chain remain untouched. The
existing model record and production engine are unchanged.

Packet52's free-order round failed its120us bar, saving only10.47/10.42us.
Its two expert controls still cost about140us per ordinary M1 layer. Packet53
therefore changes their scheduling while keeping the production arithmetic.
The dense classes are outside this round. The SLM-fill explanation for
packet52's regression remains a hypothesis, not a measured hardware finding.

[Preregistration](../experiments/own-xpu-runtime/stage2/packet53-expert-order/PREREGISTRATION.md)
and [manifest](../experiments/own-xpu-runtime/stage2/packet53-expert-order/manifest.json)
were committed before qualification. Five gate/up candidates and three down
candidates stay fixed:

- Gate/up: persistent global-index and persistent SLM-index decode, each with
  64 workgroups; virtual2 and virtual4 logical-lane mapping with global decode;
  and persistent virtual2 with SLM.
- Down: virtual2 and virtual4, plus persistent virtual2. Its K640 tail keeps
  three steps for logical lanes0–15 and two for16–31.

Each workgroup has256 work-items, eight SG32 subgroups. The fixed64-workgroup
launch is intended as two groups per B70 Xe core. SLM arms stage the full8KiB
codebook once per group. The two32-bit gathers retain the original word
layout; bank conflicts are possible and unmeasured. No per-workgroup fill is
excluded from timing.

Virtualization assigns two or four logical lanes to one physical lane as
separate sums. Every chain retains positions256*t+8*lane, with eight values
in order. Register additions perform the lower levels of the original
adjacent SG32 tree; shuffles perform the remaining levels in the same order.
This is not packet52's changed-order multi-accumulator arithmetic. Weights,
precision and output conversion remain unchanged. Existing packet49 oracles
are retained; no new oracle job is needed or launched.

The production controls are packet48b's accepted expert kernels, used through
the packet51 fixture exactly as packet49c uses them. Both kernel families use
ten distinct changing routes across actual512-expert banks and real compact
format strides. M2 means two independent serial rows. E captures complete
outputs, route statuses and sticky error: gate/up25684 bytes in five buffers,
down51244 bytes in three. Every candidate must match the unchanged production
CPU evaluation and the actual production device capture; a self-consistent
candidate mirror cannot pass by itself.

The decision requires at least30us saved per ordinary M1 layer in **both**
fresh timing owners, using the same per-class selection. All regressions and
M2 results remain in the summary. M2 cannot rescue an M1 failure. This is an
operator screen, not a model-throughput claim or production integration.

## Preparation findings

The first CPU proof failed at check6 because its production tree helper
modified the lane array that later checks reused. A private array copy fixes
the proof. The second cross-compiler attempt found unspecified evaluation
order between two random draws used to make adversarial tree inputs. Both
compilers passed their own checks but produced different fixture hashes;
separate draw statements fix the fixture. Neither correction changes kernel
arithmetic or loosens equality. Rejected sources, original build receipts and
logs are retained under `evidence-cpu/initial-proof-refusal/` and
`evidence-cpu/second-proof-fixture-refusal/` in packet53.

Intel's OpenMP runtime prints a warning when the inherited production host
control requests two threads under OMP_THREAD_LIMIT=1. The wrapper retains
and recognizes that exact warning before the JSON result; the thread cap
stays in place. All builds/tests run serially at nice19 on cores4–15,20–31,
with Python-B. Build/source receipts describe the explicit reuse of verified
historical packet45 support objects; Intel recompiles the new source.

## Coordinator handoff

[WINDOW.md](../experiments/own-xpu-runtime/stage2/packet53-expert-order/WINDOW.md)
contains the script-file commands for E1, E2, T1, T2 and the common selection.
Use physical card0, PCI0000:23:00.0, only after the coordinator releases current
GPU work. The wrappers refuse foreign Xe clients. They require the same
actually reviewed **past UTC** boundary in all four windows, and include the
PF_EXITING-tolerant sensor fixed by packet52 commit `b9745a557`.

Each E owner has60 full comparisons. Each T owner has10080 records/events,
including10 excluded warmups and200 measured pairs for each M value. Plan
E2–5min and T6–12min per window, plus coordinator gaps. These are conservative
allocations: packet52 actually took about34s E and30s T; packet53 device time
is unknown. The watchdog is2880s, four times the12min upper planning estimate,
with the native cooperative deadline at2820s. Undrained owners are retained
for the coordinator; no hard kill or automatic restart is introduced.

## Final CPU results

GNU host, Intel host and SYCL compile-only builds passed. Four fresh proof
runs (two per host compiler) each passed **8,432,381 checks**, covering
**2,250 sampled rows**, with identical receipts and output hash
`783b1e8984a63584d406fd10ff06ba92a53a2e973cc9e9757dd97f507613a2e6`.
Each proof took about 0.53–0.58 seconds. Two fresh complete-shape host runs
each passed all **60 M1/M2 comparisons**, taking about 6.47 seconds each.
A standalone AddressSanitizer/UBSan proof passed the same check count/hash
without an error in 5.22 seconds. All **17** coordinator/parser tests passed.

The build peaked at **67,184,847 bytes**. Cleanup removed **6,976,241 bytes**
of this packet's regenerable compiler scratch, leaving **60,208,606 bytes**,
well below the 1 GB limit. All six bench/proof binaries and the baseline
relink proofs remain. The packet49c reserve and every other packet's build
were untouched.

Evidence: [CPU gates](../experiments/own-xpu-runtime/stage2/packet53-expert-order/cpu-gates.json),
[Python gates](../experiments/own-xpu-runtime/stage2/packet53-expert-order/python-gates.json),
[seal](../experiments/own-xpu-runtime/stage2/packet53-expert-order/seal.json),
[independent review](../experiments/own-xpu-runtime/stage2/packet53-expert-order/REVIEW.md),
[preparation closeout](../experiments/own-xpu-runtime/stage2/packet53-expert-order/CPU-PREPARATION-CLOSEOUT.md).
Device byte identity and speed remain pending at handoff.

## Device results — October 17, 09:15–09:19 UTC

The coordinator ran E1/E2 and T1/T2 on physical card 0. Both fresh byte
checks passed all 60 comparisons against production and the unchanged CPU
evaluation. The original sealed four-window chain was revalidated before this
documentation update; [compact receipts](../experiments/own-xpu-runtime/stage2/packet53-expert-order/evidence-copy/inventory.json) preserve original bytes.

| Class | Common selection | T1 saved | T2 saved |
| --- | --- | ---: | ---: |
| Expert gate/up | virtual4-global | 14.792 µs | 15.000 µs |
| Expert down | virtual4-global | 7.291 µs | 7.291 µs |
| Ordinary M=1 layer total | | 22.083 µs | 22.291 µs |

The registered 30 µs bar failed: `expert_order_proceeds=false`. No engine
integration or model speed claim follows. Gate/up fell from about 82.9 to
68.0 µs and down from 57.6 to 50.3 µs. V2 saved only about 0.5 and 1.1 µs.
Persistent gate/up global, SLM and virtual2-SLM lost about 138, 215 and
218 µs; persistent virtual2 down lost about 26 µs. Those persistent arms
are closed. Full M2 and per-owner results remain in the
[summary](../experiments/own-xpu-runtime/stage2/packet53-expert-order/evidence-copy/p53-a-summary.json).

V4 improved over V2, warranting a separate V8/V16 screen; this does not
establish that larger V will win. The roughly 19/17 µs weight-only floors
at an assumed 550 GB/s are estimates, not measured performance. Packet53b
also tests HC low/gate and the small FFN, with a combined 35 µs bar.

The source, binaries and original seal remain unchanged. The allowed
DO-NOT-REPEAT update changes a documentation hash in the historical seal;
the original device receipts retain their original seal identity. Do not
re-seal this closed device result or launch more windows under it.
