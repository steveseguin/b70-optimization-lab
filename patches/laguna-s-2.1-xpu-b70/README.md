# Laguna S 2.1 published-convention 102.971 tok/s source snapshots

These files preserve the exact local vLLM and vLLM XPU-kernel source used by
the approved four-B70 Laguna result (`101.942 tok/s` under conventional
interval accounting). The original experiment branches point at
upstream project remotes and are not assumed to be publicly pushable.

| Component | Public upstream base | Record commit | Bundle SHA-256 | Combined patch SHA-256 |
| --- | --- | --- | --- | --- |
| vLLM | `1d354c694eedf241b836319dba497345a5aa1167` | `e596ef1543466ae1a05e5bb8091f58872e2b18ba` | `56bb463925cf53ba20db81c980264fd2a993d1e76f15731ac5676674fa0b9126` | `23fc7766c1985c6237fcab12dae62096f759511dbc7c5dc7f9828fe93d4c6d6d` |
| vLLM XPU kernels | `11f42aa47ff51924b3d9527cfc2bfef5fd2d98e5` | `6f9dd3c3a7b1b677a992ca4f431a968408f9c816` | `7aeec0b55e7b40f26d993ddf6dfb978ec267da1ae1e89d9f54c6db4d80022ed3` | `0eb4337547160394ff4ebaa66782dd936fbad3fffeceb85af08832f6d99dbd69` |
| supplemental attention-runtime XPU source | `11f42aa47ff51924b3d9527cfc2bfef5fd2d98e5` | `906190641d708b8028018c5dde653e265c835348` | `8c53de764a0c903a5e627a1c7a54a9c3bb21b500479a644b86af4c83e948149e` | `0420ac1a6db050d7a695dcfa60e8dcec2286b72b1660509862587aa537a05e0d` |

The `.bundle` files preserve the original commit graph after the listed public
prerequisite. The `.patch` files are review-friendly binary-safe combined tree
diffs from that base to the record commit. Both bundle prerequisites are
contained in the corresponding upstream `origin/main`.

Restore vLLM from an upstream clone:

```bash
git fetch origin
git fetch /path/to/b70-optimization-lab/patches/laguna-s-2.1-xpu-b70/vllm-laguna-width12-dflash-fp8-102tps-record-20260726.bundle \
  experiment/laguna-width12-stack-clean-20260726:refs/heads/laguna-record
git checkout e596ef1543466ae1a05e5bb8091f58872e2b18ba
```

Restore the XPU kernels from an upstream clone:

```bash
git fetch origin
git fetch /path/to/b70-optimization-lab/patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-width12-102tps-record-20260726.bundle \
  experiment/laguna-width12-router-clean-20260726:refs/heads/laguna-record
git checkout 6f9dd3c3a7b1b677a992ca4f431a968408f9c816
```

Restore the supplemental attention-runtime source:

```bash
git fetch /path/to/b70-optimization-lab/patches/laguna-s-2.1-xpu-b70/vllm-xpu-kernels-laguna-attention-runtime-906190641-20260726.bundle \
  experiment/laguna-s-2.1-fwht-20260721:refs/heads/laguna-attention-runtime
git checkout 906190641d708b8028018c5dde653e265c835348
```

The supplemental bundle closes an important provenance gap. The measured
`_vllm_fa2_C.abi3.so` and `libattn_kernels_xe_2.so` were built from
`906190641`, while the final router/workspace source tree was `6f9dd3c3a`.
The measured `_C`, `_xpu_C`, grouped-GEMM/helper DSOs byte-match the earlier
`4772f727590c51b72add79350b913d098cf67872` build, and
`xpumem_allocator` came from
`18a44f440ca3ac2006d5ba19cd12ccca0a0c9982`. Both earlier commits are
contained by the main kernel bundle. The standalone repro restores all of
these worktrees, pins every native hash, and checks the actual loaded paths.

Validation performed before promotion:

- both bundles pass `git bundle verify` in repositories containing their
  public prerequisites;
- both combined patches pass `git apply --check --reverse` at their exact
  record commits;
- bundle heads equal the record commits in the table;
- all six file SHA-256 values were recomputed from the tracked snapshots.
- the supplemental bundle and patch pass the same bundle-head, prerequisite,
  hash, and reverse-apply checks.

Result and reproduction entry points:

- [qualified result packet](../../results/laguna-s-2.1-int4-b70/README.md);
- [structured record](../../data/laguna-s-2.1-width12-dflash-fp8-record-20260726.json);
- [standalone repro](../../repro/laguna-s-2.1-int4-b70-102tps-20260726/README.md);
- [metric correction](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-26-throughput-window-accounting-correction.md).

## Post-record experimental snapshots

The following snapshots are retained for review and exact reproduction but are
not promoted record sources:

| Experiment | Base | Commit | Patch SHA-256 | Bundle SHA-256 |
| --- | --- | --- | --- | --- |
| width-12 target inline gathers | `34b43849fc7c8ff8633f223469cc2a0d525c256e` | `ce2f3dfc02bce59095d8654d299c52b05c72d423` | `e9af21c63f399ccace945077cf1fbef883f4e8cfbe3ec9cd412dc3233eae070e` | `231d391d4526e7816ba69e80d211aefb0df663699846d5211e50c659c1ee9ea7` |
| rejected in-place dequant MAD | `46a88e09d96fe06871c87a23de534fb47f1e039b` | `7df9806e9eb12fb8e880c7ba0c6b4a104ef73832` | `ef639c3cc2a05fa4db870301fa3f732cf4ae031c2b16509d658d46c6c886e632` | `735d958c6c5d47e49d5184bcb30cc166033b69f94c38b5081d5f42d727e0ade2` |

The inline-gather candidate was preregistered in
[the 2026-07-31 experiment note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-target-inline-gathers-preregistration.md).
Its bundle ref is
`experiment/laguna-target-inline-gathers-20260731`; its review patch is
`0001-xpu-inline-exact-Laguna-target-gathers.patch`. The first non-scored
request failed its exact q=1 prefix/cache gate, so it remains default-off and
must not be rerun or promoted. See the
[negative result](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-target-inline-gathers-negative.md).

The in-place dequant-MAD candidate is a static negative. Its matched BMG
decode-policy probe grew from 376 to 408 instructions by adding 32 moves, so
the preregistered process stopped before component or endpoint execution. Its
bundle ref is `experiment/laguna-mad-inplace-20260731`; see the
[negative result](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-dequant-mad-inplace-negative.md).
