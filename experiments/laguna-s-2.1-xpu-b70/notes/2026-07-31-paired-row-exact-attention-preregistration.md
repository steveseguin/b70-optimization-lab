# Laguna paired-row exact M12 attention

Date: 2026-07-31 America/Toronto

Status: **rejected at the one-B70 component gate; no vLLM integration or
endpoint run.**

## New mechanism

The exact verifier currently launches one paged-decode workgroup per
`(verifier row, KV head)`.  On TP4, each row has 12 Q heads and 2 KV heads, so
each KV head owns only six real Q rows while the compiled qgroup-16 policy has
ten unused rows.

Pair two consecutive verifier rows and place both six-head GQA groups in one
qgroup-16 tile.  This reduces the exact verifier from 12 to 6 logical decode
batches and lets one K/V load feed both temporal rows.  For each pair, the
earlier row masks the final KV token and uses a sliding-window origin one token
earlier; the later row uses the pair's maximum staircase length.  The QK,
softmax, and PV tile shapes and per-row reduction order remain the incumbent
qgroup-16/page-64 policy.

The first component may explicitly pack Q and unpack O outside its timed core.
That isolates whether the kernel mechanism is exact and large enough before
any vLLM integration.  A later integrated screen must include those costs.

## Candidate

- Kernel base: `99886d783372e621941228250091dc8ebdc1595d`.
- Worktree: `/home/steve/src/laguna-xpu-kernels-paired-attn-20260731`.
- Selector: `VLLM_XPU_LAGUNA_M12_PAIR_ATTN`, literal `0` or `1`, default off.
- Candidate-only physical input: batch 6, 24 Q heads, 2 KV heads, head 128,
  BF16 Q/K/V, page 64, qgroup-16, consecutive staircase pairs.
- Selector-on must fail closed for every other shape, dtype, layout, sequence
  relation, mask, or page policy used by the component.
- Selector-off dispatch and device code remain the promoted path.

## Gates

1. Focused host tests must cover selector parsing, shape rejection, pairing
   and inverse layout, staircase lengths, and both full and sliding masks.
2. Build only the reduced Laguna attention library with pinned oneAPI 2025.3;
   record source commit, DSO SHA-256, `libsycl` SONAME, elapsed time, peak RSS,
   and swaps.
3. On one idle B70, compare the candidate after inverse layout with the
   incumbent 12-batch output for the 52 real-window contexts, full and
   sliding attention, and at least two changing seeds.  Require raw BF16
   equality in every case.
4. Time the attention core with fixed prepacked inputs and caller-owned
   outputs.  Require at least 1.5 ms projected saving across 12 full plus 36
   sliding layers before paying for vLLM integration; this leaves margin for
   pack/unpack work while the 130-tok/s gap is about 1.13 ms/cycle.
5. A component pass authorizes only default-off vLLM integration and an
   all-cost component screen.  Smoke and endpoint gates require a new frozen
   authorization with the unchanged 13/13 teacher, cache-zero, one start,
   146/145 target and 14/13 draft topology, and clean idle.

No weight, target or draft precision, BF16 KV semantic, verifier width, draft
depth, target verification, sampler, acceptance rule, prompt, output length,
or score metric may change.  No reset, driver reload, FLR, reboot, or
privileged recovery is authorized.

## Result (2026-08-01 America/Toronto)

The arithmetic mechanism is exact, but it is not faster.  The final component
compared the incumbent qgroup-8 control with the packed qgroup-16 candidate on
physical B70 rank 1 across all 52 real-window contexts, full and sliding
attention, and two changing seeds:

| Metric | Control | Paired candidate |
| --- | ---: | ---: |
| raw BF16 equality | - | **208/208** |
| full-attention mean | 0.022639569 ms | 0.023645231 ms |
| sliding-attention mean | 0.021955918 ms | 0.021993689 ms |
| projected 12 full + 36 sliding | 1.062087889 ms | 1.075515588 ms |

The projected change is **-0.013427699 ms**: a regression, not the required
`+1.5 ms` saving.  The selector's invalid-literal and selector-on-control-shape
fail-closed checks also passed.  The mapped native library was the candidate
artifact, and stderr contained no missing-policy fallback or runtime failure.

This closes the seam before integration.  Pairing halves logical verifier
batches but changes the incumbent qgroup-8 tile into qgroup-16; the measured
core result shows that this does not reduce effective B70 attention cost.  The
component does not isolate whether tile resource use, scheduling, or another
kernel detail consumes the theoretical K/V reuse, so no stronger causal claim
is made.

## Build and harness chronology

1. Source `079b503c` compiled every heavy kernel object but failed its final
   host object on a one-character guard typo (`is_var_len` instead of
   `is_varlen`).  The failed build took `16:18.23`, peaked at `5,090,744 KiB`,
   and reported zero swaps.  No device work occurred.
2. Source `4ab83266` fixed that typo and produced DSO SHA-256
   `a3d76dccbf541307318db4822debf0a581dbfea5cf4461bf9d9b3e5f592ccdba`.
   The first component invocation then proved the reduced build lacked the
   incumbent qgroup-8 policies.  The control fell back to the PyTorch
   reference, so its `0/208` result and timings are classified strictly as a
   build-policy/harness failure and are not kernel evidence.
3. Final source `8a1b059356eea1d7368ffaa67ac3dafe5543234d` added only the two
   qgroup-8 control policies.  The corrected four-policy incremental build
   took `3:41.50`, peaked at `4,244,008 KiB`, reported zero swaps, and produced
   a 23,440,040-byte DSO with SHA-256
   `29f91afac61ed2447cc5581c7cb0838f452086fd17fa49b1ed1fb2796922f155`.
   It links `libsycl.so.8`; the resolved oneAPI 2025.3 library SHA-256 is
   `18fa367fb7be21f05e718555b50e4d5dec000322cc40e6c48d596b3f2ab4f394`.

Final component artifact:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/components/
laguna-paired-attn-8a1b059-20260801T092049Z
```

Invalid first invocation retained for audit:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/components/
laguna-paired-attn-4ab8326-20260801T091540Z
```

Tracked reproduction artifacts:

- full structured result:
  `data/laguna-paired-attn-component-negative-20260801.json`;
- component gate:
  `tools/gate_laguna_paired_attn.py`;
- source patch:
  `patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-paired-attn-rejected-8a1b059-20260801.patch`;
- source bundle:
  `patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-paired-attn-rejected-8a1b059-20260801.bundle`.

The protected `125.4619731637751 tok/s` conventional record worktrees and
runtime were never modified.  The host returned to strict idle after the
component.  No reboot, reset, driver action, model service, endpoint score, or
LocalMaxxing submission occurred.
