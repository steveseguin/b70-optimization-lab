# Qwen3.8 Flash-Next FP8 XPU overlay

Exported: 2026-08-26

Apply each directory's numbered patches in order with `git am`. The vLLM
series is based on `76cfe1cd88d30d525eec8be5bff75f8b77471c88`. The kernel
compatibility series is based on
`0fd18a7c08a64d2645bf083cfa5576200b61b02c`. Its first two commits restore
source pieces dropped by earlier local/upstream merge resolution; its third
adds the fused block-FP8 and MXFP4 SiLU-multiply implementation translation
units to the existing basic-kernel build list. It does not replace or remove
the existing Qwen/GDN/MoE performance work in that kernel tree.

## SHA-256

```text
ada51dac31d5be31f5b07396e391a2cbc855f3bf24bb751b4998ae304e544ada  vllm/0001-Merge-02f2b4c15dd987d9436e125aab29604447c77405-into-.patch
50acc32f60d26dc444d2dea1be09d3fa901eff511792cb54ca191ed0c5a65b95  vllm/0002-support-PLE-Offload-for-Qwen3.8-Flash-Next.patch
8bd198c57477e92d7dd6f019998f3769abdf4b1c92dcb53af02293a94895928e  vllm/0003-Support-eager-PLE-offload-transport-on-XPU.patch
69447fec75398b10982c3f5cbea161550591cf2f66b0319a6d1cb085232ce42c  vllm/0004-Enable-Qwen4Exp-model-dispatch-on-XPU.patch
0c63f3e5b3664942a8c66f9a71952adfc2229b7528b2001a0010debb4f329f4c  vllm/0005-Add-Qwen4Exp-XPU-hyperconnection-fallbacks.patch
d2d84153d4e94d7369b474a23bda89a5da564a7ca969125c9f02af432d5ef381  vllm/0006-Enable-Qwen4Exp-QSA-kernels-on-XPU.patch
64c65eb34efff1bb91208de2b2892b2a3467bb736fb3e938ea47856e4981a993  vllm/0007-Fix-PLE-target-device-selection-across-accelerators.patch
7941bbd056f168272a82b91c5b9ea97501e8c2ec674c17eeea38fb192a5c1c6e  vllm/0008-Restore-weight-skip-filters-for-Qwen4Exp.patch
23d25179eb7e287ca8217afac479ec0fe55736cb2e20ff8032e866ffd77b536e  vllm-xpu-kernels/0001-fix-xpu-restore-architecture-probe-bindings.patch
8cfaecdb5c0d1afe61f6eb87d6018346261c1b8eadb58f181aec328c16f70af1  vllm-xpu-kernels/0002-fix-build-restore-local-MoE-prologue-source.patch
e8880c975ad17cbfc8676e65edd82eae96a94aaecf883137bd3c51c124e627a2  vllm-xpu-kernels/0003-fix-build-include-fused-quant-implementations.patch
```

These are source artifacts only. A deployment package must additionally pin
and checksum its native XPU binaries, Python environment, model revision, and
checkpoint tree.
