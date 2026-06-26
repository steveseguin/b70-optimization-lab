# 2026-06-24T2243 - Target Fused Argmax And Softcap Verifier Argmax

Goal: reduce target/verifier output overhead in the current fresh-response
Gemma 4 26B A4B Q8 lane without reducing target quality and without relying on
repeated-output/history acceleration.

Current valid record for comparison:

- `gemma4-q8-gpu1-rowargmax-safer-immediatecl1-full-20260624T193222Z`
- Q8 target + Q4_0 MTP draft, `n=7`, direct-unroll7, q-only assistant attention
  inputs, verifier row-argmax IDs, deferred target `h_nextn`,
  `UR_L0_USE_IMMEDIATE_COMMANDLISTS=1`
- fresh row-0: **101.60238982389097 tok/s** after TTFT,
  **88.50781195831634 tok/s** wall, `cached_tokens=0`
- canary: **1536/1536**

Validity rule: headline throughput below is first fresh p512/o512-style row
only. Repeated benchmark rows are support data, not fresh-response headline
claims.

## Target Fused Argmax Guard

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/20260624T2243Z-llamacpp-gemma4-target-fused-argmax-supported-guard-current.patch`

Intent: make the target fused-output-argmax path safe to enable only when the
output tensor type and shape support it. This was hygiene for experiments around
the existing `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX` path, not a default record
change.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | Decision |
| --- | --- | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-control-postfusedguard-screen-20260624T224213Z` | control after guard patch | 16/16 | 101.306809 | 88.315865 | valid control, below record |
| `gemma4-q8-gpu1-fusedtargetguard-screen-20260624T224213Z` | `LLAMA_SPEC_VERIFY_FUSED_OUTPUT_ARGMAX=1` with guard | 16/16 | 89.366338 | 79.041690 | reject; much slower |

Decision: keep the guard as default-safe source hygiene if the broader patch
stack is retained, but reject the fused target flag for this model/config. It
does not improve fresh response throughput.

## Softcap-Aware Verifier Argmax

Patch artifacts:

- crashing first draft:
  `patches/gemma4-26b-a4b-q8-b70/20260624T2255Z-llamacpp-gemma4-spec-verify-softcap-argmax-current.patch`
- zero-output guard revision:
  `patches/gemma4-26b-a4b-q8-b70/20260624T2310Z-llamacpp-gemma4-spec-verify-softcap-argmax-zero-output-guard-current.patch`

Intent: after the normal `result_output` LM-head matmul, replace the verifier
post-processing chain

```text
scale -> tanh -> scale -> ggml_argmax
```

with a single `GGML_OP_ARGMAX_SOFTCAP` returning sampled verifier token IDs.
The op is gated by `LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX=1`, applies
`softcap * tanh(raw / softcap)` during the argmax scan, and is disabled when
suppress-token bias is present.

The first draft built successfully but crashed on the first canary:

- run: `gemma4-q8-gpu1-softcapargmax-screen-20260624T230624Z`
- failure:
  `/home/steve/src/llama.cpp-gemma-record-stack/src/llama-context.cpp:1821:
  GGML_ASSERT(ggml_nelements(tensor) >= 1) failed`
- cause: the model graph could publish a zero-length sampled-row tensor during
  a zero-output/prefill graph. The generic `build_sampling()` path already
  avoids this with an `n_outputs == 0 || logits->ne[1] == 0` guard.

The zero-output guard revision added `n_outputs > 0` before publishing sampled
row tensors for both the existing fused verifier path and the new softcap
verifier path. It fixed the crash:

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-control-softcapop-screen-20260624T230624Z` | control after softcap-op source stack | 32/32 | 101.263619 | 88.361491 | 0.738269 | valid control, below record |
| `gemma4-q8-gpu1-softcapargmax-zeroguard-screen-20260624T231009Z` | `LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX=1`, zero-output guard | 32/32 | 101.302474 | 88.316983 | 0.743129 | valid but neutral; below record |

Decision: reject as a promoted speed path for now. The crash fix is useful, and
the source stays default-off, but the softcap argmax flag does not beat the
current fresh-response record. Do not submit to LocalMaxxing.

Runner hygiene: `scripts/run-gemma4-26b-first-baseline.sh` now records
`LLAMA_SPEC_VERIFY_SOFTCAP_ARGMAX` in `launcher_identity` for future runs.

## Follow-Up Implication

The current row profile remains dominated by target verifier/output work and
MTP draft overhead, but this specific post-softcap argmax fusion does not move
enough time to matter. Next candidates should focus on larger row-profile
components: draft-side cost, verifier/output matmul placement, or reducing
target-side copied/logit materialization without changing Q8 target
verification.

## Multi-Token `MUL_MAT_ID` No-Reorder Control

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/20260624T2330Z-llamacpp-sycl-mulmatid-multitoken-no-reorder-current.patch`

Intent: the broad `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` path had already
been shown valid but much slower (`~76 tok/s`) than the current `101.60 tok/s`
fresh record. This control added a default-off diagnostic switch,
`LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NO_REORDER=1`, to force the non-reordered
kernel branch inside the multi-token fused `MUL_MAT_ID` path and determine
whether the slowdown came from the reordered layout branch.

| Run | Change | Canary | Fresh row0 tok/s | Wall tok/s | TTFT s | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-mulmatid-multitoken-noreorder-screen-20260624T233811Z` | `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_FAST=1` + `LLAMA_SYCL_MUL_MAT_ID_MULTI_TOKEN_NO_REORDER=1` | 32/32 | 76.035561 | 68.578333 | 0.732224 | reject; still in the known bad multi-token fast-path band |

Fresh validity: one p512/o512-style benchmark row, `cached_tokens=0`, no
headline use of repeats or history-accelerated continuation.

Decision: the reordered branch was not the cause of the multi-token
`MUL_MAT_ID` regression. Do not promote and do not submit to LocalMaxxing. The
useful retained artifact is the patch snapshot and the result tying this branch
off, so future work should not re-test broad multi-token `MUL_MAT_ID` by merely
toggling reorder behavior.
