# Shared-gate component Torch XPU UUID binding abort

Date: 2026-07-23 EDT / 2026-07-24 UTC

## Classification

- Outcome: rank-0 runtime-binding tooling abort; no component measurement.
- Authorization packet:
  `data/laguna-s-2.1-shared-gate-m8-component-authorization-20260724T023300Z.json`
- Authorization commit: `bcfb15849a1785f2daeeff653ba462d32dc01e9a`
- Tools commit: `56c36d5cf95a50aedfc4c32ccb4374457f4b6145`
- Artifact root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-gate-m8-component-56c36d5cf-20260724T023300Z`
- Runner diagnostic: `runtime XPU UUID is malformed`.
- Failure classification:
  `runtime_or_infrastructure`, with the conservative
  `tensor_work_started=true` checkpoint already sealed.
- Runtime work performed: Torch XPU initialization and one scalar device probe.
- Not reached: runtime binding checkpoint, constructor-scope proof, dispatch
  proof, all 128 pre-exactness epochs, timing, and all 32 post-exactness epochs.
- Cards 1 through 3: not started.
- Campaign terminal:
  `campaign_failed_stop_before_analyzer`, with all downstream authorization
  fields false.
- Counters, model generation, endpoint work, network access, reboot, and
  submission: not started.

This authorization and artifact root are terminal and must not be reused.

## Preserved evidence

- `campaign-start-checkpoint.json`:
  `1f74a391fb85e232e121c68a4ac218ae8d5ed0c12da2763fca412414333ae09a`
- `card0/pre-tensor-identity-checkpoint.json`:
  `386559fab4081bd50a05e6f035d8f70d74b0e4a848f21566747779b15e3087ff`
- `card0/tensor-work-started-checkpoint.json`:
  `ecbb5c6dc2a6f5801b9c97d109648b256b1cbcca8f8c0c9ba1be8d37d10cf010`
- `card0/component-result.json`:
  `eb661c45a24fe23b8afca44da84117468bbc6db2f056c357b9875b2b91538ed3`
- `rank-0-terminal.json`:
  `11a7a86edeb65cd40a4e32cef1ae36c5b15978f5c1c0be840ab5534d2568cf81`
- `campaign-terminal.json`:
  `4543d4b6dfa9e3f7ba34dc096919cf61a7e744b6b01e042569cc10a725da3ffa`

## Root cause and correction

The installed Torch is `2.12.0+xpu` at Git revision
`7661cd9c6b841b62b7f411aa52ec51f05457263b`. Its official
`torch/csrc/xpu/Module.cpp` binds `DeviceProp.uuid` as a custom `_XPUuuid`
object. That object exposes the 16 values through a `.bytes` property and a
formatted `__str__`; it is not itself accepted by Python's `bytes()` function.
The component runner incorrectly handled only strings and directly byte-
convertible values.

The correction reads the official wrapper's `.bytes` property, requires
exactly 16 bytes, constructs an RFC UUID from those bytes, and still requires
the resulting UUID to equal the packet's physical card UUID exactly. CPU-only
tests emulate the installed wrapper, reject wrong length, and reject a
well-formed but different UUID. The source reference is:

`https://github.com/pytorch/pytorch/blob/7661cd9c6b841b62b7f411aa52ec51f05457263b/torch/csrc/xpu/Module.cpp`

After full regression and independent review, use a new tools commit,
authorization packet, and NVMe campaign root.
