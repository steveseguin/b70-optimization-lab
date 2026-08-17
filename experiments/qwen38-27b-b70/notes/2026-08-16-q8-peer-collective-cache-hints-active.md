# Qwen3.8 27B Q8 TP2 peer-collective cache hints

Date: 2026-08-16

Status: closed as performance-neutral; do not repeat unchanged.

## Hypothesis

The accepted TP2 stack performs 128 already-fused collective boundaries per
generated token.  Its root vec4 reduction kernel reads the second B70's
peer-mapped partial and writes the completed sum back to that peer mapping.
Those one-use transactions should not displace reusable local data from cache.
Intel's compile-time SYCL `annotated_ptr` cache controls can express streaming
or uncached policy on only those peer operations without changing arithmetic,
ownership, launch count, or synchronization.

This is distinct from the closed reordered-Q8 weight cache-policy arm in the
Qwen3.6 pass-2 notebook.  That arm changed high-volume local weight reads;
this arm changes only the cross-device `p1` vec4 read/write in the accepted
root reduction.

## Contract

- accepted Qwen3.8 27B Q8_0 TP2 target-only stack and model identity;
- selector `level_zero:1,0`, `SYCL0/SYCL1`, equal tensor split;
- F16 KV, flash attention, batch 1024 / ubatch 256;
- same binary exposes incumbent, streaming, and uncached peer policies;
- first require a quality-exact smoke and evidence that the treatment door is
  live, then use a position-balanced control/treatment decode bracket;
- promote only a repeatable gain followed by the complete cache-zero fixed
  suite, exact-output hashes, semantic canaries, and long-context needle gate.

The experiment must be stopped and recorded as unsafe if the current boot
shows a Xe reset, hang, timeout, or device-lost event.  This arm does not use or
revive quarantined collective mode 3.

## Implementation and safety gate

The isolated candidate is based on the accepted one-chain Q8 source and adds
only [`GGML_SYCL_COMM_PEER_CACHE`](../patches/q8-peer-collective-cache-hints-20260816.diff):
`0` is the ordinary pointer path, `1` applies streaming L1/L3 hints, and `2`
applies uncached L1/L3 hints. Local `p0`, residual, and `add0` operations are
unchanged. The build used oneAPI 2026.1.1, Release, BMG-G31 AOT, F16 and Level
Zero enabled, graph/DNN/host fallback disabled, and an 8 GiB hard build cap.

Candidate SHA-256 identities:

- incremental patch: `7826ae4e83786dde494ab73258787bdc7a847d75c2f74e1f9ee687b49bef3524`
- `llama-bench`: `9d3fc8515dd819eea9c144e8a7e4323964599ad638f0e93477042617ecd7aa42`
- `llama-server`: `1c8a322942f948c10fba908d5371eb8b0acef31b370dc6958a7ea4e132915526`
- `libggml-sycl.so.0.19.0`: `9c664ec151c269dabf4ddccdf6506aeb910cd5a89f9ba4410ba4aac23f62619e`

Fresh-process `p64/n1/r1` smokes for modes 0, 1, and 2 all reported the
requested door, `VERIFY_MISMATCH=0`, and normal completion. Both B70s remained
normal with no current-boot Xe compute reset, hang, timeout, fault, or
device-lost event. Those one-token timings were not treated as performance
evidence.

## Position-balanced result

The screen used fresh processes in symmetric order `0,1,2,2,1,0`. Every run
used `p64/n256/r3`, the accepted TP2 target-only flags, F16 KV, flash attention,
batch 1024 / ubatch 256, and the same candidate binary.

| Peer-cache mode | Pooled decode tok/s | Delta from same-binary mode 0 |
| --- | ---: | ---: |
| `0`, ordinary pointers | 36.563301 | control |
| `1`, streaming L1/L3 | 36.567361 | +0.011104% |
| `2`, uncached L1/L3 | 36.553346 | -0.027228% |

All six runs reported `VERIFY_MISMATCH=0`; both GPUs remained normal and the
post-run kernel-log audit found no compute fault/reset/hang/timeout/device-loss
event. The structured measurements and all raw-log SHA-256 values are in the
[data record](../data/2026-08-16-q8-peer-collective-cache-hints-neutral.json).

The streaming delta is far below run-to-run resolution and uncached is
slightly negative. The arm is therefore neutral and was not promoted or sent
to a costly endpoint quality suite. The accepted reproduction remains
unchanged.
