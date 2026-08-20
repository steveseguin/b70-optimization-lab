# Qwen3.8 INT4 determinism-pad TP1 causal screen result

Date: 2026-08-20

Status: **positive causal diagnostic; not promotion evidence**

The six fresh-server arms completed in the preregistered order under the same
TP1/MTP5 binary, strict composite stage, b936 outer/AOT cache, model bytes,
suite, request order, and seed. The only treatment variable was
`VLLM_XPU_ONEDNN_INT4_DETERMINISM_PAD=0|1`.

## Result

| Arm | Pad | Structured variant | Token count | Structured output SHA | Legacy median tok/s |
|---|---:|---|---:|---|---:|
| `0-a` | 0 | G | 419 | `74a860ae...` | 81.604 |
| `1-a` | 1 | G | 419 | `74a860ae...` | 81.678 |
| `0-b` | 0 | F2 | 420 | `11a29b06...` | 81.608 |
| `1-b` | 1 | G | 419 | `74a860ae...` | 81.601 |
| `0-c` | 0 | G | 419 | `74a860ae...` | 81.700 |
| `1-c` | 1 | G | 419 | `74a860ae...` | 81.586 |

Pad-off therefore produced two distinct structured-extraction token arrays
(`G/F2/G`), while pad-on was bit-identical in all three arms (`G/G/G`). The
other three prompts were identical across all six arms. This passes the
preregistered causal criterion.

The median of the three arm medians was `81.608 tok/s` off and `81.601 tok/s`
on (`-0.008%`). Treat that as neutral diagnostic timing, not a speed result.

## Engagement and identity gates

All six arms:

- exited zero; passed the fixed smoke and fresh-response benchmark gates;
- dual-view verified all model files immediately before launch;
- resolved the package and native extensions strictly under
  `/home/steve/staged-xpu-commitfix-graphfa-composite-20260820`;
- loaded `_xpu_C` SHA `4dd336013d15...` and graph-safe FA SHA
  `33938cdd2436...`;
- directly loaded two b936 outer artifacts and both AOT artifacts;
- emitted no graph/AOT rebuild or save marker;
- left the compile-cache manifest byte-identical before and after: manifest
  SHA `552ddb98181f...`, tree `02db4496...`, 1,859 entries, 1,588 files,
  197,507,168 bytes.

The branch-warning split was exactly `0/1/0/1/0/1`. The warning uses
`TORCH_WARN_ONCE`: it proves that the pad branch was active, not how often or
for which module it ran. Six first-inference Triton kernels did JIT-compile
in-process in every arm, but they wrote no observed cache artifacts and did
not change the sealed cache tree.

## Claim boundary

This same-binary alternating control met the preregistered criterion and
supports crediting **global in-band oneDNN W4A16 prefill padding** for the
observed six-arm structured-extraction contrast. Three pad-on observations do
not establish lane-wide determinism. The generic operator gate applies to both
the quantized target-backbone prefill and quantized MTP-layer prefill at the
199-token shape, so it does not isolate which side was causal. A future scoped
target-versus-draft gate would be required for that attribution.

This is not yet a full-25, TP2, quality, or promotion result. First add
fail-closed harness checks for pad engagement, direct b991/AOT loads, post-run
cache equality, and token parity. Then run two margin-free TP2 full-25 arms
with the pad enabled, this composite runtime, and the post-recovery
`b99160ae76` cache at
`/mnt/usb-models/llm-runtime/vllm-cache/qwen38-postrecovery-marginfree-mtp5-20260820/torch_compile_cache/b99160ae76`.
Its input manifest SHA is `f3582440de9b...` and tree SHA is `723c1599060f...`.
Require strict self-parity, target-oracle comparison, and the fixed quality
gate before promoting any throughput number.

Structured evidence:
[`../data/2026-08-20-int4-detpad-tp1-causal-screen.json`](../data/2026-08-20-int4-detpad-tp1-causal-screen.json)

Preregistration:
[`2026-08-20-int4-detpad-tp1-causal-screen-preregistration.md`](2026-08-20-int4-detpad-tp1-causal-screen-preregistration.md)

Source/operator proof:
[`2026-08-20-autoround-int4-runtime-nondeterminism-found-and-pad-fix.md`](2026-08-20-autoround-int4-runtime-nondeterminism-found-and-pad-fix.md)
