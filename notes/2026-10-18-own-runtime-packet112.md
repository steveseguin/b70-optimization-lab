# Packet112: exact route selection

October 18, CPU-only preparation under the two-hour brief. Pull refused the
unrelated dirty orchestration files; fetch confirmed HEAD == origin/main at
`e9458351c21b0e4fe6988511bbadc4a1a2b4d913`. Work is confined to a new packet,
this note, and a new proposed queue file. No device, service, live queue, existing
packet, host setting, or other owner's process is changed.

## Finding

The current record-line selection in packet103 has `route=fast`. It dispatches
packet78's `p78route::Kernel`, inherited by packet97. Packet107 and packet110
also select `route-fast`: their **18.750 µs measurement already measures the
fast route**, not the older four-launch all-pairs route. All four copies of
`p78_route.hpp` have identical bytes. The measured layers are synthetic full
shape diagnostics; the roofline is not a standalone model benchmark.

The input is 512 BF16 router logits in the current target path (FP32 is also
supported), selecting ten experts. One WG512, sixteen SG32, performs:

1. Active/sticky-error admission. Thirty-two lanes scan sixteen consecutive
   logits each, reject any NaN/Inf, and write ordered local maxima.
2. Lane zero scans those 32 maxima in order. All lanes run the unchanged
   deterministic FP32 exp. Each group of sixteen reduces with the original
   adjacent pair tree; lane zero reduces the 32 resulting sums with the
   unchanged padded subtree. Each probability is rounded by FP32 division.
3. A full 512-entry bitonic sort: 45 compare/exchange rounds, 35 inside
   subgroups and ten through local storage. Each cross-subgroup round needs
   two workgroup barriers. Comparisons use normalized probabilities, then
   the **lowest original expert index** on ties, including ties created by
   exp/division rounding.
4. Ten lanes write the selected IDs, FP32 weights and two ten-by-three U32
   route descriptor arrays (expert, zero, width 640 or 2560). The original
   selected-weight subtree and normalization run on lane zero.

There are 27 workgroup barriers, serial max/denominator/tail work, and only
one workgroup on the whole card. There are sticky-error atomic loads/stores,
but **no atomic ranking or floating-point accumulation**. This is a plausible
latency mechanism for a roughly 7 KB operation, not a measured causal breakdown
of the 18.75 µs. The entire route costs roughly 0.45 ms across 24 layers per
half; saving half would budget about 0.225 ms/half, approximately 1.46% on hits
using the brief's conversion. This is opportunity arithmetic, not a speed claim.

## Candidate and exactness argument

[p112_route.hpp](../experiments/own-xpu-runtime/stage2/packet112-route-select/p112_route.hpp)
keeps the full arithmetic prefix, output writer, selected-weight normalization,
guards and ABI. It changes selection only. Each SG32 sorts its 32 values and
retains sixteen. Four rounds merge neighboring sorted top-16 lists with a
32-entry bitonic merge, retaining sixteen each time. A discarded element has
at least sixteen better keys in its own list, so cannot enter the global ten.
The finite probability/index comparator is a strict total order. No approximate
selection, raw-logit ranking, data-dependent truncation or changed FP32 tree.

The selection has 35 subgroup compare/exchange rounds on the final subgroup's
path and seven workgroup barriers, reducing the kernel total from 27 to 14.
The proposal tests whether those thirteen fewer barriers are worth at least
half the current route time. It does not assume that they are.

Production admits no NaN/Inf input row: error becomes one and every public
output remains untouched. On these rejected rows, scratch slots 0–31 have
unspecified partial writes because the unchanged concurrent validation exits
after observing another lane's error. The gate compares all output and guard
bytes, error, and scratch from slot 32 onward; it does not claim deterministic
bytes for production's own unspecified partial maxima. All scratch bytes are
compared for finite, inactive and prefailed rows. The CPU sequential mirrors
also compare all scratch bytes on nonfinite rows.

## Inputs and preregistered gate

Packet100b saved selected route descriptors, **not logits**, so its IDs cannot
reconstruct this kernel's inputs. A CPU-only copy of packet107's harness runs
the unchanged prefix up to routing in ordinary GDN layer 4 and QSA layer 3,
eight reset seeds per layer, occupied context 128. It saves sixteen exact BF16
router rows as losslessly widened FP32. These are **synthetic layer harness
inputs**, not actual model-capture rows. Provenance, commands, dependencies,
input hashes and layer/seed metadata are retained.

Each process checks 2,048 cases against unchanged route-fast, including 512
NaN/Inf cases covering every expert position, forced ties, signed zeros,
adjacent FP32 values, underflow, extreme finite logits, inactive and sticky
error rows, both input scalar types, and both two/four-output ABIs. Every
output byte is checked; nothing uses a tolerance.

Timing uses all sixteen unchanged harness rows in their original BF16 input
type and U32/F32 output ABI, eight kernel warmups followed by 64 AB/BA pairs
per row. Setup, copies and comparisons are outside the event interval; each
event retains its start/end and wall time. Warmups compile/initialize kernels,
not a model prompt or response cache. Two separate coordinator processes
must each pass the complete byte gate and have candidate median **<=0.5 times
production** overall, in both orders, and in both layer strata. A missing,
inexact, drifted or slow process cannot qualify. The kernel is an operator
diagnostic only; a passing micro is not a model speed or quality claim.

Only a qualified micro can open runtime integration. That would copy the fixed
packet103 sources after p103x lands, add `route_select=production|p112`, run
GNU/Intel byte and relevant startup/host-reference gates, seal the views, and
propose a v5 one-load native lane-B bracket. It is forbidden to integrate
while either process is unmeasured or fails the kill gate.

## CPU milestone

The micro builds under GNU, Intel host and Intel SYCL without executing a
device. Both host compilers pass two fresh 2,048-case processes with identical
output identities. The first device compile exposed the old owner header
alongside packet97's copied owner API; a generated local SYCL-operation header
now uses the same parent API override as the normal build. Its original
failure log is retained. No arithmetic or frozen source was changed.

The new proposal is
[proposed-p112-micro-B.txt](../experiments/own-xpu-runtime/ops/lane-queue/proposed-p112-micro-B.txt).
It contains two independent fresh owners, each expected to take about **60
seconds**, with a **1,200-second watchdog** and no retries. The inherited lane
reservation, fault review, card isolation, graceful stop, drain and release
checks remain. CPU memory caps apply only inside CPU CLI entrypoints; importing
the device wrapper or helpers imposes none. Device equality and speed are pending.

## Shipped milestone

Commit `f7d5ea2c3` pushed the compiled micro and both planned proposals. The
retained build is **10,284,057 bytes**, below 200 MB. All four final CPU
processes produced
`b49f59ab0cfd98cf51cddc7610efec21e6c2fbe349ec7c39937dc23819b0d36f`.
Eleven qualification/import-safety tests and both direct/temporary queue
plans pass. [CPU preparation closeout](../experiments/own-xpu-runtime/stage2/packet112-route-select/CPU-PREPARATION-CLOSEOUT.md)
links the evidence and remaining gates.

The p103x launch-limit fix landed independently in `932df6642` while this
micro was being prepared. No device receipts have arrived, so no runtime
dimension, model startup campaign or v5 bracket is opened prematurely.
The next action is the coordinator-owned micro; its two-process kill gate
decides whether integration is allowed.
