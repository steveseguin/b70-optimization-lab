# Qwen3.8 AutoRound: missing GDN/batch-invariance factorial arm

Date: 2026-08-18

Status: source-verified diagnostic; not a performance or correctness result

## Why this arm is required

The incoming optimization ladder compared:

- serial-exact GDN on plus global `VLLM_BATCH_INVARIANT=1`: `91.926 tok/s`,
  25/25 self-deterministic; and
- serial-exact GDN off plus global batch invariance off: `98.222/98.717 tok/s`,
  only 12/25 self-deterministic.

That is a useful bound, but two coupled variables changed. The attempted
serial-off/batch-invariant-on arm aborted in the backend selector because GDN
advertises batch-invariance support only when serial-exact mode is enabled.
Consequently, current evidence cannot assign the `+6.3 tok/s` or the divergence
specifically to GDN, global batch-invariant linear/norm policies, or their
interaction. A completion barrier rules out a simple missing queue dependency;
it does not resolve this confounder or prove a particular reduction is causal.

## Diagnostic patch

[`../patches/vllm-qwen38-gdn-batch-invariant-factorial-diagnostic-20260818.patch`](../patches/vllm-qwen38-gdn-batch-invariant-factorial-diagnostic-20260818.patch)
adds one explicit environment override to vLLM base
`44fc8fde09fc311d3099dab10366b672d9142ea4` (patch SHA256
`f13b652df61afa67791ac12799fa6f4169e3ff07d61daa0bc8f7ba322b1844c5`):

```text
VLLM_XPU_GDN_BATCH_INVARIANT_DIAGNOSTIC=1
```

It changes no kernel arithmetic. It only permits the otherwise-rejected
factorial cell. The default remains fail-closed.

## Exact arm

Use the accepted MTP3 source/runtime and keep all baseline flags except:

```bash
VALIDATION_BATCH_INVARIANT=1 \
VALIDATION_QWEN_GEMMA_RMSNORM_BATCH_INVARIANT=1 \
VALIDATION_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=0 \
VLLM_XPU_GDN_BATCH_INVARIANT_DIAGNOSTIC=1
```

Keep the deterministic greedy margin and all oneDNN completion/input-dependency
controls enabled. Run A and B on the full cold 25-prompt suite; report all-25
and selection-12 separately and compare complete token arrays.

Interpretation:

- 25/25 determinism near the fast rate means the GDN selector guard was too
  conservative for this exact path; quality and target parity still must pass.
- The same 12/25 failure strongly implicates the packed GDN path.
- A different failure set establishes an interaction and requires narrower
  operator/state oracles before changing a production kernel.

This arm cannot be promoted even if fast. It deliberately overrides an
unsupported-backend guard and exists only to identify the next implementation
target.
