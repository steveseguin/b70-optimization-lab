# Qwen3.8 Flash-Next FP8 A48 twoshots lossless-2K preregistration

Date: 2026-09-01
Status: frozen before full-model launch

A48 is the fresh attempt-48/port-19720 host-guarded successor to A47. The only
enabled inference-selector change is:

```text
CCL_SYCL_ALLREDUCE_LL=twoshots
```

The public graph-safe oneCCL library, device kernel, 4096-byte LL threshold,
TP4/EP4 MTP0 topology, synchronous PLE-only placement, 2,304-token service
cap, size-1 `FULL_DECODE_ONLY` graph, compilation mode NONE, KV budget,
prompts, output authorities, and complete quality battery are retained. The
component prerequisite passed exact CPU-oracle comparison for all 97 ordered
BF16 `[1,2560]` allreduces, 100 changing inputs, and all four ranks in each of
six matched arms. Its three candidate reductions were `7.293496%`,
`6.180802%`, and `4.678938%`.

## Source-head disclosure

A47 pinned vLLM `797769b34b6db5c934609b75dc04cc61ec66e5f9`; the current clean
overlay is `cbc3cb588a7cae8dcc489fb4dfc1a800d19980d9`. The intervening commit
adds opt-in per-phase Triton MoE configuration. A48 pins the newer head and
proves that `VLLM_TUNED_CONFIG_FOLDER` is absent from the live server, so that
path is inactive. This source-head advance is disclosed as behavior-neutral;
the packet does not pretend that the source trees are byte-identical.

## Frozen packet

- derived launcher SHA-256:
  `a3bf49c3aad05f0245bc6ec1c0df19544860a7a2595d256a124af9a752bd108b`;
- launcher SHA-256:
  `7f4366a6358c3a3aed6a1326b68e700519cfc591fcfce2b0ffd3d922118b2eb1`;
- client SHA-256:
  `95a308a36a89414b661080df9945a621db7c9b6ba76e07b73a642d5d597e2a9a`;
- supervisor SHA-256:
  `e0e8a407c8ccbdd2e05146fe76bd7791a37f533ca572a4007266e258e8a0db11`;
- privileged host wrapper SHA-256:
  `1ce70894278f81b6c3c32b21a9696f6098b21970af4649304ab0a3a11e1430b8`;
- A48 runtime verifier SHA-256:
  `a3acec5018c4b1147f8efddb75f6678acee7f9802d4fb11f3c56bc7b2bd74ca8`;
- field-aware rewrite helper SHA-256:
  `f60885a4f13086ee39f7dd8e1d4bd23dfa4c1da72100dc3872d65ee0834f84fd`.

The rewrite helper validates exact source-field occurrence counts and
reproduces the tracked A48 packet byte-for-byte in validation mode. Broad
attempt-name substitution is not used.

Both the privileged wrapper and launcher require `/mnt/usb-models` to resolve
exactly to `/dev/sda2 fuseblk` and `/mnt/fast-ai` to resolve exactly to the
local `/dev/nvme0n1p2 ext4` filesystem before creating benchmark paths. This
prevents an unmounted external-drive directory from silently accepting
evidence on the internal root filesystem.

## Fail-closed interpretation

The runtime verifier accepts a consumed selector only after the process maps
the exact pinned oneCCL and the server log records the exact `twoshots`
selection. Any conflicting selector, collective error, library/kernel drift,
missing size-1 full-graph dispatch, unexpected compilation, host pressure,
swap, ASPM drift, post-policy AER-counter increment, new NVMe link event, or
dirty source fails the arm. Corrected events already accumulated before the
host wrapper applies its policy are recorded as a baseline rather than forcing
another reboot; only a stable counter is admitted.

A valid result still requires recovery, the accepted semantic boundary,
16/16 repeat, all three protected short hashes, the exact cache-zero 2K needle,
and two identical exact-2K authority hashes. Speed is reported only after all
quality gates pass. Any failure preserves the eager `5.515783 tok/s` result
and A44's `20.507849 tok/s` diagnostic median unchanged.

No reboot or one-load-per-boot rule applies. The host may run A48 whenever its
live health, empty evidence paths, source identities, and privileged bounded
host-control gate pass.

The first host-wrapper invocation exited before path creation with status 141.
Under `pipefail`, the successful `grep -q` ASPM checks closed their `lspci`
producers early and converted the resulting SIGPIPE into a wrapper failure.
The wrapper and its generator now capture each complete `lspci` report before
matching it. Generator reproduction, root-only validation, and both real
ASPM-disabled matches pass; no server, checkpoint load, run path, or request
existed during the procedural interruption.
