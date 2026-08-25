# Qwen fa0 persistent graph-cache evidence port: preregistration

Date: 2026-08-25

Status: **patch prepared and statically checked; unbuilt and unrun.**

## Purpose

The historical R5 sentinel proved persistent SYCL graph replay and exact
graph-off/on output parity, but its July dirty binary is not an acceptable
source recipe for the matrix. The clean accepted Qwen source at `fa0f3b25`
preserves the lab optimizations and per-device TP graph design, but lacks the
persistent cache/counters and rejects every `CONCAT` before capture.

The new patch ports only those missing graph-evidence mechanisms. It is not a
performance optimization claim and does not change defaults.

Machine-readable identity and gates are in
[`2026-08-25-qwen36-fa0-graph-cache-port-prereg.json`](../data/2026-08-25-qwen36-fa0-graph-cache-port-prereg.json).
Patch explanation and application checks are in
[`patches/qwen36-27b-mtp-gguf-q4-b70/README.md`](../../../patches/qwen36-27b-mtp-gguf-q4-b70/README.md).

## Frozen first run

After the patch is independently reviewed, built once in a new sibling build,
and the build receipt passes, the first GPU work is one TP1 parent sentinel:

1. same new binary, graph off/cache zero;
2. fresh process, same binary and every other input, graph on/cache eight;
3. exact output-byte parity;
4. graph-off summary with all action counters zero;
5. graph-on summary with no rejection/unsupported/cache-full event, positive
   record/create/direct-hit counts, and `replayed == requested`.

No full depth curve starts before this gate. A passing sentinel authorizes only
a separately preregistered TP1 curve. TP2 and TP4 require their own packets;
the port deliberately retains the base's per-device graph behavior but static
source reasoning is not multi-card evidence.

## Interpretations fixed before execution

- Requested without replay is failure, not partial graph evidence.
- Any compatibility rejection means the tested arm is not graph-on.
- Output mismatch is failure even if throughput rises.
- A slower graph candidate is still a useful measured matrix cell; it never
  lowers or overwrites the protected graph-off frontier.
- A faster sentinel grants no depth, quality, website, or submission claim.
- Cross-build output differences are not attributed to graphs because this
  compiler lane is stable within a build but not necessarily across rebuilds.
- No graph cell may be estimated.

## Static status

The patch touches only `common.hpp` and `ggml-sycl.cpp`, applies cleanly under
`git apply --check` to the exact clean `fa0f3b25` source, and retains the
existing per-device compatibility commentary and behavior. No source tree was
patched, no build was completed, and no GPU process was launched while this
packet was prepared. The parent intentionally stopped an unpatched preliminary
graph configure/build at 33% once its normalized configuration was captured;
that interrupted build is neither an input nor evidence for this patch.
