# STATUS — mndodd Qwen3.6 27B llama.cpp Intel SYCL fork

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `B70-verified` for the lab's Q8_0 target-only TP1 and TP2 rows; `B70-tested` / support-only for MTP4, DFlash5, and Q8-KV rows |
| Patch review status | read and executed here; the branch-delta inventory, performance-relevant paths, and the complete three-file lab compatibility patch were inspected |
| Tested in reference lab | yes; two ASRock Arc Pro B70 32 GiB cards, plus isolated one-card controls |
| Safe to merge as documentation | yes, with the corrections recorded below |
| Eligible for `repro/` or `results/` | target-only TP2 is eligible; retained in `community/` until a separate maintainer promotion |

## Provenance

- Contributor/source author: [`mndodd`](https://github.com/mndodd).
- Source branch: [`mndodd/llama.cpp:intel-sycl-optimization`](https://github.com/mndodd/llama.cpp/tree/intel-sycl-optimization).
- Tested commit: [`4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126`](https://github.com/mndodd/llama.cpp/commit/4302fb59969a5d8cf9f8e5f55fdd4506d0ed2126).
- Upstream merge base: [`ggml-org/llama.cpp@84e908c625fb60992b4cdef8180fb12fa9b4c4bf`](https://github.com/ggml-org/llama.cpp/commit/84e908c625fb60992b4cdef8180fb12fa9b4c4bf).
- Branch delta at validation: 155 commits, 48 files, 10,395 insertions, and 607 deletions.
- Right-to-submit statement: no separate statement was supplied to this repo. The public fork retains llama.cpp's MIT license; attribution and source links are preserved here.
- Lab-only deltas: [`patches/0001-asrock-lab-lowram-dnnless-tp2.patch`](patches/0001-asrock-lab-lowram-dnnless-tp2.patch).

## Claim

No benchmark claim or raw result was found in the source branch itself. The
operator relayed that another B70 owner had mentioned greater than 50 tok/s.
That hearsay is not attributed to `mndodd` as a documented claim.

The local lab result is separate: target-only Q8_0 TP2 reached
`31.255575 tok/s` in `llama-bench` and `31.338765 tok/s` under the repository's
historical 100-event convention (`31.025377 tok/s` conventional 99-interval
accounting) on the fixed cold endpoint suite. Target-only TP1 reached
`17.497254 tok/s` in `llama-bench` and `17.955800 tok/s` legacy
(`17.776242` conventional) on the matched endpoint suite. A favorable DFlash prompt reached
65.00 tok/s, but the fixed-suite DFlash median was only 38.084045 tok/s
historical (`37.703205` conventional) and is not target-only.

## Contributor Environment

The source branch documents resolved runtime doors and many per-cell findings,
but it does not provide a complete public host/result packet for the relayed
greater-than-50 statement.

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | unknown for any original claimed score |
| OS / kernel | unknown |
| GPU driver / runtime | unknown |
| Engine | llama.cpp fork commit `4302fb599...` |
| Model / revision | branch comments target Qwen3-family Q8_0 and MTP-shaped work; exact original artifact unknown |
| Quantization / KV | exact original configuration unknown |
| Command / benchmark / quality gate | not published in the branch |

## Reference Lab Environment

- Host: AMD EPYC 9015, 15 GiB RAM, 35 GiB swap.
- GPUs: 2x ASRock Arc Pro B70 32 GiB (`8086:e223`, subsystem
  `1849:6025`), `xe` driver, full 32 GiB ReBAR, external links Gen5 x16.
- OS/kernel: Ubuntu 24.04.4 LTS, `7.0.0-28-generic`.
- Intel stack: OMIX `0.3.0-9`, compute runtime `26.22.38646.7-9`.
- Compiler: oneAPI DPC++/C++ 2026.1.0 (`2026.1.0.20260617`).
- Build: Release, BMG-G31 AOT, F16 and Level Zero enabled, host-memory
  fallback disabled, oneDNN/WDC unavailable, SYCL command graphs disabled for
  the validated rows.
- Model identity and binary hashes are in
  [`validation/2026-08-12-asrock-b70-validation.md`](validation/2026-08-12-asrock-b70-validation.md).

## What Was Actually Run Here

1. Target-only Q8_0 TP2, equal tensor split, full-F32 two-card reduction,
   `p512/n128/r5` and the fixed 12-prompt cold endpoint suite.
2. Fresh target-only TP2 logits/perplexity comparison against the accepted
   upstream build.
3. Matched one-card target-only fork/upstream endpoint controls, one-card
   `llama-bench`, and logits/perplexity checks; SG32 was screened separately.
4. One-card MTP4 on the fork and upstream-derived control with the same model, draft,
   service settings, and request contract.
5. One-card DFlash5 and a one-card MTP4 Q8-KV side lane.
6. No successful TP2 DFlash run: draft/meta tensor assignment fails before a
   valid result.

## Findings

1. The fork contains real B70 work, not a flag-only branch. Its Q8 wide-load
   MMVQ, Q8 activation-quantization deduplication, B70 shape routing,
   cross-operation fusions, multi-column verifier work, attention paths, and
   staging fixes are all present in the tested source.
2. The clean target-only TP2 endpoint A/B is `31.338765` versus `29.610651`
   tok/s under the legacy helper convention, a `+5.836%` relative gain. Both
   rows used raw completions, temperature 0, seed 42, identical prompts, and
   produced 12/12 identical complete output hashes.
3. The initial endpoint comparison mixed chat and completions APIs. It is
   superseded by the matched run above and must not be cited.
4. The fork MTP4 row is `+19.463%` over the upstream-derived control under the same TP1
   service/request identity. It is a useful performance result, but the
   retained request did not ask the server for token IDs and did not explicitly
   set temperature in the request; keep it support-only unless a matched
   greedy rerun is completed.
5. Fork MTP4 and fork DFlash5 produced the same 12 complete output hashes under
   their common request contract. This establishes agreement between those two
   speculative routes, not equivalence to a separately configured target-only
   run.
6. The local metadata patch changes three contexts from
   `1,048,576 * 368` bytes each (about 1.078 GiB total) to three 64 MiB
   contexts (192 MiB total). Earlier notes saying two 1 GiB arenas were wrong.
7. The matched target-only TP1 endpoint A/B is `17.955800` versus `17.297038`
   tok/s legacy (`+3.809%`). Forced SG32 looked `+3.65%` in `llama-bench` but
   was only `+0.083%` over the fork default on the fixed endpoint suite, so it
   is diagnostic and remains off by default.
8. Final target-only TP2 screens did not improve the frozen path: root-barrier
   elision was `-0.246%` against its same-build control, the PVC MMVQ phase
   walk was `-2.818%`, and root-local reduction plus peer-copy replication was
   `-1.726%`. Their source edits were reverted and their logs are hashed in
   the validation manifest.

## Known Issues

- `PROVENANCE.md` describes an earlier integration point and contains defaults
  later changed by the branch. Use the tested commit plus the runtime's
  unconditional `SYCL doors` banner, not the prose file alone.
- WDC is not tested here because the build has no oneDNN support. The local
  dummy type declaration only lets the disabled translation unit compile.
- The full fork delta is large. The measured end-to-end gain is not assigned
  to one commit without a controlled ablation.
- TP2 depends on the lab's opt-in two-card exact-F32 all-reduce patch; the
  fork's stock BF16-compressed TP path failed the Q8 quality gate on this host.
- TP2 command-graph capture is not safe in this tensor-split path: the normal
  configuration aborted when a queue wait occurred during graph recording;
  disabling Q8 dedup let prompt evaluation finish but decode then hung.
- Do not use the fork's built-in `GGML_SYCL_PROFILE=1` profiler for TP2. A
  short profiling run returned `UR_RESULT_ERROR_DEVICE_LOST` and reset both
  B70 compute engines. Both devices recovered to `normal`, and later ordinary
  workloads passed.
- No long-context retrieval or sustained-concurrency gate was run for this
  packet.

## Disposition

Keep as a `B70-verified` target-only community result and a `B70-tested`
speculative-workload contribution. The corrected source/build/launch/benchmark
recipes are self-contained here. The graph/no-graph and TP1 follow-up is
closed: graph capture is rejected, SG32 is not promoted, and the graph-off
default fork identity is frozen as the reproducible winner.
