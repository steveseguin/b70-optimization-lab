# Packet 46: specialized layers and one-card CPU prerequisites

Work started at 02:01 UTC on October 17, 2026 on `steve-b70s`, from `main`
after `git pull --rebase` reported up to date. The owner's brief prohibits
builds and sustained CPU work until **02:55 UTC** while the four-card FP8
comparison runs. Preparation uses nice 19, cores 4–15 and 20–31, and Python
without bytecode writes. No device use, model payload reads beyond existing
fixtures, service actions or host-setting changes are authorized here.

Source design: [roadmap](2026-10-17-own-runtime-iq3-speed-roadmap.md),
[one-card plan](../experiments/own-xpu-runtime/ONE-CARD-DESIGN.md).
Packet45 and the protected A367/driver sources remain untouched.
All new code lives in
[`packet46-specialized`](../experiments/own-xpu-runtime/stage2/packet46-specialized/).

## Preregistered work

One ordinary GDN layer and one QSA layer, M=1 decode with 4K occupied context,
compare the current packet45 kernels to compile-time-specialized compositions.
Require every retained intermediate and state byte to agree on changing inputs
and fresh processes. Preserve FP32 rounding, reduction trees, BF16 stores and
state update order. Descriptor-interpreting fused kernels remain closed.
The integration bar is **at least 80 microseconds saved per layer**, measured
with GPU event durations by class. A lower launch count or faster host wall
time alone cannot pass. The coordinator alone runs the card-0 windows.

The CPU expert implementation must match the selected P39/P28 arithmetic using
only existing fixture generation. This Threadripper PRO exposes AVX2 and no
AVX-512 flags. Sustained CPU throughput and fresh-process CPU exactness results
will be recorded after the time boundary. Route-ID and phase diagnostics are
default-off and excluded from speed claims.

## Cache refinement

The metadata-only [budget](../experiments/own-xpu-runtime/stage2/packet46-specialized/CACHE-BUDGET.md)
corrects PLE history to the census's 184,320 bytes and accounts for aligned
slots and metadata. The 18 GB cache holds 9,082 experts; the total design leaves
681 MB beyond the unchanged physical reserve. This is not a device admission.
The hypothetical uniform route scenario requires 35.9268 GB/s and 18,157
expert evaluations/s at 60 target positions/s. Its hit rate is unmeasured.
Three metadata unit tests passed in 0.011 seconds before the build boundary;
no compiler, device binary or sustained test ran.

## Results and handoff

The default-off route/phase adapter and its strict JSONL validator are written
in `packet46-specialized/diagnostics/`. An offline cache report separates
accepted-token popularity from all executed work, including rejected work,
and labels partial layer coverage. Five Python schema/report test groups pass
in 0.002 seconds. C++ compilation and the two fresh mock processes are still
pending the 02:55 UTC boundary. This adapter is not installed in packet45.

Implementation, CPU tests, throughput measurements, independent review and
final seal are pending. Device correctness, device speed and one-card fit
remain unmeasured by this task. The device coordinator retains ownership.
