# Qwen3.8 Flash-Next FP8 XPU overlay

Exported: 2026-08-26

## Certified source reconstruction

The certified TP4/MTP3 runtime-stage source is reconstructed by the additive
series in `vllm-xpu-kernels-certified-2f829747/`. Start from public fork commit
`0fd18a7c08a64d2645bf083cfa5576200b61b02c`, apply its seven patches in
numbered order, and require resulting Git tree
`d8c4318a0f0d71c3c36867253ad92b377906fec9`. That is the exact tree at
`2f829747503c77d4814834dffd0840fb1dd9f75a`, the build head for the kernel
stage loaded by the certified Qwen3.8 Flash-Next TP4/MTP3 result.

The older loose `vllm-xpu-kernels/` directory is retained as historical
evidence, but it is **superseded and incomplete as a reconstruction series**.
It omits certified commits `c694d2f2`, `49002d71`, and `7cf21677`; its `0003`
also has malformed patch context and does not apply to the declared base.
Its later exact-GDN patch represents checkout `ad25aa9f`, which was not loaded
by the certified MTP3 runtime stage. Do not combine that loose directory with
the certified seven-patch series.

Run `verify-certified-source-series.py` with local vLLM and
vLLM-XPU-kernels repositories before publishing or building from these source
artifacts. The verifier uses fresh temporary clones, applies only the declared
production sequences, and asserts both exact output tree hashes.

The production vLLM series is based on
`76cfe1cd88d30d525eec8be5bff75f8b77471c88` and applies patches
`0001` through `0010`, `0012`, and `0014` through `0018` in that order.
Patches `0011` and `0013` are opt-in diagnostic research artifacts and must
not be applied to a performance or production tree. The historical loose
kernel artifacts are based on
`0fd18a7c08a64d2645bf083cfa5576200b61b02c`. Its first two commits restore
source pieces dropped by earlier local/upstream merge resolution; its third
adds the fused block-FP8 and MXFP4 SiLU-multiply implementation translation
units to the existing basic-kernel build list. It does not replace or remove
the existing Qwen/GDN/MoE performance work in that kernel tree. Its fourth
filters padding sentinels during MoE alignment. Its fifth changes only the
exact speculative GDN proof path from a fixed four-row bound to the positive
runtime row count; target-only execution is unchanged.

## Historical loose-artifact SHA-256

```text
ada51dac31d5be31f5b07396e391a2cbc855f3bf24bb751b4998ae304e544ada  vllm/0001-Merge-02f2b4c15dd987d9436e125aab29604447c77405-into-.patch
50acc32f60d26dc444d2dea1be09d3fa901eff511792cb54ca191ed0c5a65b95  vllm/0002-support-PLE-Offload-for-Qwen3.8-Flash-Next.patch
8bd198c57477e92d7dd6f019998f3769abdf4b1c92dcb53af02293a94895928e  vllm/0003-Support-eager-PLE-offload-transport-on-XPU.patch
69447fec75398b10982c3f5cbea161550591cf2f66b0319a6d1cb085232ce42c  vllm/0004-Enable-Qwen4Exp-model-dispatch-on-XPU.patch
0c63f3e5b3664942a8c66f9a71952adfc2229b7528b2001a0010debb4f329f4c  vllm/0005-Add-Qwen4Exp-XPU-hyperconnection-fallbacks.patch
d2d84153d4e94d7369b474a23bda89a5da564a7ca969125c9f02af432d5ef381  vllm/0006-Enable-Qwen4Exp-QSA-kernels-on-XPU.patch
64c65eb34efff1bb91208de2b2892b2a3467bb736fb3e938ea47856e4981a993  vllm/0007-Fix-PLE-target-device-selection-across-accelerators.patch
7941bbd056f168272a82b91c5b9ea97501e8c2ec674c17eeea38fb192a5c1c6e  vllm/0008-Restore-weight-skip-filters-for-Qwen4Exp.patch
fd1dd94b54e5b41812d9cefdc3c05bdbab5c0a4d684c04aedd85cd6fe9973c49  vllm/0009-Port-QSA-compressed-cache-to-tokens-per-state.patch
fa0d3e4ff71d51f5c5e0e318934c9a5d6aa33f68426cd0f50203073ead2bbbbd  vllm/0010-Avoid-copying-uninitialized-PLE-weights-during-offlo.patch
175c877972ac665a25b2fd75c5a07e520c233ee8c3b6a2c6ecf5575c117b3d03  vllm/0011-Add-opt-in-XPU-MoE-phase-sync-trace.patch
37cbc03515c77cc64da7a80689865c2fde4bb96dd78f8d67491b346af0e5f190  vllm/0012-Allow-selective-UVA-offload-of-Qwen4Exp-embeddings.patch
564fc8ff102e91c23be5aceca0e5d43fb84e3d486978340d142503c75fa651fb  vllm/0013-Capture-routed-MoE-replay-inputs-on-demand.patch
fb7063c15743b306b218a6159f94935325bfcfd8c6db61200fa4e1cb196906f9  vllm/0014-Normalize-QSA-caches-from-logical-layout.patch
4e7ce685db32a88695ab4a3d4f05bf468a34974a23e24d3772c37a4582b45956  vllm/0015-Support-legacy-XPU-GDN-ABI-for-target-decode.patch
e9d2ed0234695954ea8c1bdb0edb1b18cc00c0be8c1bfb8e7d021abb0e80795e  vllm/0016-Fail-closed-on-XPU-GDN-schema-mismatches.patch
cdd9631a9480ab333fb4340812adf856ad65e22b0c4da1b1a8ef91bb04d7fa3c  vllm/0017-Port-Qwen4Exp-MTP-tests-to-tokens-per-state-cache-AP.patch
7d5328a5d5175fdd0c97ac83b9cb826e8e3dce5d30c755a26c4f732000f41937  vllm/0018-Route-legacy-XPU-GDN-speculative-decode.patch
23d25179eb7e287ca8217afac479ec0fe55736cb2e20ff8032e866ffd77b536e  vllm-xpu-kernels/0001-fix-xpu-restore-architecture-probe-bindings.patch
8cfaecdb5c0d1afe61f6eb87d6018346261c1b8eadb58f181aec328c16f70af1  vllm-xpu-kernels/0002-fix-build-restore-local-MoE-prologue-source.patch
e8880c975ad17cbfc8676e65edd82eae96a94aaecf883137bd3c51c124e627a2  vllm-xpu-kernels/0003-fix-build-include-fused-quant-implementations.patch
ecc1cb5c84b148e96755b0b834408ae5ffaf9e497d2c1eb7d46735b4cf850a88  vllm-xpu-kernels/0004-fix-moe-ignore-padding-sentinels-during-alignment.patch
7cbadf00a334404507ea730ea8281db203d4de7613785b599aa7f9800d523a46  vllm-xpu-kernels/0005-Generalize-exact-GDN-replay-to-MTP-row-count.patch
```

These are source artifacts only. A deployment package must additionally pin
and checksum its native XPU binaries, Python environment, model revision, and
checkpoint tree.

The exact 18-file hybrid runtime stage is pinned by
`../../experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-padding-guard-loadable.sha256`.
Package it with `../../scripts/package-qwen38-runtime-stage.py`; the tool rejects
missing or extra `.py`/`.so` runtime files and Python cache artifacts, verifies
every file hash, writes a deterministic uncompressed tar plus fixed-size parts,
re-extracts and verifies the package, and emits a portable JSON receipt. Use
`--stage`, `--archive`, and optionally `--receipt`, `--split-bytes`, and
`--verification-dir`; output paths must not already exist.
