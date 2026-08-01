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
| neutral SIMD32 dequant MAD | `46a88e09d96fe06871c87a23de534fb47f1e039b` | `7557817d0e8c564be74f2cd7717e0195c1cb3911` | `fdf90dbd88fcdf6f507df2fd5123fc15f0de46c35daa43d69918911a19b68549` | `38933d1eb3561fcddf6c00cea5d6c7d629bddc518b6593a0e67e17856047f496` |
| provisional exact decode GRF128 | `46a88e09d96fe06871c87a23de534fb47f1e039b` | `e4163f93574326b2772742e0f51372a5a3777aa5` | `f4a4cfa61d47526d02586822f8c00a6e983062737df79e4e141675ae91bc32c0` | `e21141feecf16de832ca841b0046c8ea523113795498c392ddc91c08833a5596` |
| exact decode mainloop specialization | `e4163f93574326b2772742e0f51372a5a3777aa5` | `ec507e8b0b1bb7ca36adb81565e29c781fbc0cc2` | `540235f285cc84457c30b74d1ddb322ca9355e1fd7a0c44a1f4df70a22936d26` | `8cf6b505bbb3f96f9c75c30cee46576af9972dc896dabc0dca0aaaf34e237c15` |
| confirmed transposed decode scales | `e4163f93574326b2772742e0f51372a5a3777aa5` | `8dd94f2307db3b830fe07f212c4b36f719652a5c` | `87337d0244f3f81a4b7d2a8b669d3e01610a8eff133bce04696bdb06559bd075` | `0c23d0c5a8bf358d9e20b095fe4b771273e01992468aa3b805207b04c7a44809` |
| rejected transposed-scale prefetch removal | `8dd94f2307db3b830fe07f212c4b36f719652a5c` | `32aa4a4057414163411d0388af10d896da1df442` | `a1bf0a9ba567306ff57eb420e732df5eb26037aa88cf5396dba2351f0922634a` | `cbf4f4994fee46df8c4c7f2cbd84fb54a54425908cbee6961836868fc43ec126` |
| rejected transposed-scale-only distance 3 | `8dd94f2307db3b830fe07f212c4b36f719652a5c` | `588ce4e636e7ad7561aec533bda85e2eaf35cdac` | `078ce5bde9f38262c93e1377e9e2ec9236d09672d7017cf22c9dd27027a3fed0` | `a7be5434b720c5a301e33f0a6894a8796b6f7cf10fa8b9c422b4b5c299fa6c3b` |
| confirmed exact M12 QKNorm/RoPE kernel | `8dd94f2307db3b830fe07f212c4b36f719652a5c` | `69e8ad9119a9cc70c3906b82be6254dd0160f00e` | `36b6991b32172618ad444cd533ca6c32e2938401cc0cee869f760ece52423e59` | `670883c59fb2f45c73919a42623431fd9376bcc1e1e6e5b80e6785b4905c1f1d` |
| confirmed M12 QKNorm/RoPE vLLM selector | `34b43849fc7c8ff8633f223469cc2a0d525c256e` | `58608c6361f1a958a7e933bed0be8c88c35aa26e` | `c73b88bfea5029920b0764889d734b7a9b9e53aab3b4af5e8bb77f17922e982f` | `b5f13674bc32058d22e5fe44ed90a4d4eac3f3abdb9849b9f34019aeca263d48` |

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

The full-pair SIMD32 dequant-MAD candidate is also a static negative. BMG
finalizes the widened vISA operation into the same `M0`/`M16` native SIMD16
halves, leaving 376 total instructions and 156 moves unchanged. No production
build or GPU run occurred. See the
[negative result](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-dequant-mad-simd32-negative.md).

The decode-GRF128 candidate is a valid first endpoint leg, not yet a promoted
record. Its separately named 128-GRF kernel is reachable only for the exact
Laguna width-12 target-MoE decode shape and leaves draft, prefill, and selector-
off behavior at 256 GRFs. It passed 6/6 raw-BF16 component comparisons and the
full 13/13 cold endpoint gate at `121.299321` historical / `120.086328`
conventional tok/s. Because the `+0.22%` first-leg margin is smaller than host
noise, one same-identity confirmation is required before promotion. See the
[first result note](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-decode-grf128-first-endpoint-result.md).

The exact-decode specialization is a static pass, not an endpoint result. It
retains only the live group-32 vectorized mainloop in a new named kernel and
shrinks matched production BMG ISA from 6,174 to 674 instructions while
preserving 128 GRFs, eight EU threads, and the exact 32-mul/16-shift/16-bfn/
2-DPAS arithmetic body. See the
[static pass](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-exact-decode-mainloop-specialization-static-pass.md).

The transposed-scale bundle is the current confirmed exact BF16-KV record
source. It includes the exact mainloop specialization, the retained malformed
prefetch negative, its corrected `[1,SG_N]` block-prefetch geometry, and the
guarded model integration. The immutable BF16 scale tables are cloned from
`[expert,N,K/32]` to `[expert,K/32,N]` only for exact width-12 target decode.
Two independent exact cold starts measured `121.383776672` and
`122.828558121 tok/s` conventionally. See the
[confirmed record](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-transposed-decode-scales-confirmed-record.md).

The transposed-scale prefetch-removal snapshot is a component negative, not a
record source. It remained raw-BF16 exact 6/6 but slowed the summed real W13+W2
component from 0.50334 ms to 0.73220335 ms (`0.687432x`). Its patch is
`0001-laguna-skip-prefetch-for-contiguous-transposed-scale.patch`; see the
[preregistered negative result](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-transposed-scale-prefetch-preregistration.md).

The transposed-scale-only distance-3 snapshot is another exact component
negative. It leaves packed-weight prefetch at six while moving only contiguous
scale prefetch to three. Under the stabilized 200-warmup/15-sample protocol it
was 6/6 exact but `0.997847x` the record component. Its patch is
`0001-laguna-prefetch-transposed-scales-closer-to-use.patch`; see the
[component result](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-transposed-scale-distance3-preregistration.md).

The M12 QKNorm/RoPE kernel and selector snapshots form the current confirmed
exact BF16-KV record source. They preserve the incumbent BF16 reduction and
rounding boundaries while reducing Q/K RMSNorm plus NeoX RoPE from three
device kernels to one per target attention layer. Two cold exact endpoint legs
measured `124.442780113` and `124.642412721 tok/s` conventionally. See the
[confirmed record](../../experiments/laguna-s-2.1-xpu-b70/notes/2026-07-31-qknorm-rope-m12-confirmed-record.md).
