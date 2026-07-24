# Laguna M8 actual-model gate: target-hidden evidence abort

Date: 2026-07-24 America/Toronto

Status: sealed instrumentation abort during the first incumbent-eager M=8
target-verification forward. One fresh offline request was dispatched, but no
generation completed or returned from `LLM.generate`. This is not a quality or
performance result.

## Frozen identity

- approved record: LocalMaxxing `cmrx6p5dv001bo4017hb7sixz` at
  `33.89498511171744 tok/s`;
- v3 gate tooling:
  `7f0f190d48b47224dcc7e692dbd74de5c568e64e`;
- v3 preregistration:
  `d63a99951`;
- reviewed full-stack vLLM:
  `61e483e80a9bb0c4eaf8c6fb31f3165668cbe71c`;
- frozen kernel descendant:
  `4772f727590c51b72add79350b913d098cf67872`;
- sealed run root:
  `/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/laguna-m8-actual-offline-7f0f190d4-20260724T163134Z`.

The retained identity, logs, and arm-idle reports have SHA-256 digests:

```text
5fbf2c6cec0a4aca785b29f2f57b0e137d7bf946bc1d65854a92b367ef29dd5b  identity.txt
8e45e34fa7e55058c18ab2450c83d2e5032c10432a713770952a069369b5c189  incumbent-eager/stdout.log
bdfe5e76434a76e7b9f35b1edcb094de49eed0dbd19f3359f503dab783a24be7  incumbent-eager/stderr.log
9ecebaf332ce695fef8cfcbe70f5033f3cd61347dd05c997c8c2e4b6dfe56f82  incumbent-eager/pre-idle.json
d962025993c5fe8b1c8de6829faf51aab2a7ba3abbe31f9081a4d69371d14eb9  incumbent-eager/post-idle.json
```

The root and all three `m8p3-{a,b,c}` RPC bases are owner-readable and
non-writable and will never be reused.

## What happened

The full model-content verification, global idle check, and incumbent pre-arm
idle check passed. Arm A then proved the corrected approved identity:
`enforce_eager=True`, no caller-supplied compilation config, XPU graph disabled,
TP4/EP4 XCCL initialized, all 15 target shards and the one DFlash shard loaded
from internal ext4, and the first exact speculative-attention `q=8` launch ran.

The first target-verification event reached all 48 attention layers on all four
ranks. Each rank retained 195 manifest events ending at
`attention_47_output`, for 780 event records and 768 raw tensor binaries across
the arm. The logical event was target ordinal 1, generation epoch 34, positions
33-40, with one row of seven draft candidates.

The evidence hook then failed before the target-hidden and logits boundaries:

```text
RuntimeError: Laguna M8 evidence expected target hidden states as a tensor
```

The hook incorrectly assumed that the Laguna target returned a bare tensor.
For the frozen DFlash configuration, target forward intentionally returns
`(final_hidden_states, aux_hidden_states)`. Normal runner postprocessing
immediately unpacks that tuple and feeds `final_hidden_states` to logits. This
was therefore an evidence-recorder type error, not a model execution,
exactness, or graph result.

The single `LLM.generate` call raised `EngineDeadError`. No `driver.json`,
`analysis.json`, completed generation, returned token sequence, throughput, or
candidate result exists. B and C did not run. Partial internal scheduler state
(`num_computed_tokens=33`, `num_output_tokens=1`, seven scheduled draft IDs)
does not constitute a returned generation.

All four workers logged shutdown `done`; the post-worker inventory is empty and
the strict post-arm XPU observer passed on devices 0-3. The shared-memory
resource tracker emitted one cleanup warning, retained in stderr as a caveat,
but no worker or XPU context remained. The sealed artifact and active model
paths are on `/dev/nvme0n1p2` ext4 under `/mnt/fast-ai`; no external USB path
was used.

## Decision

Classify this root as
`instrumentation_abort_during_first_m8_target_forward_before_logits_or_completed_generation`.
It says nothing about A/B/C raw parity or performance.

The continuation must extract tuple element zero only under the already frozen
Laguna+DFlash evidence contract, require the exact structured output and M=8
geometry, leave the tuple untouched for normal DFlash postprocessing, and
remain absent from evidence-off execution. Unit tests and independent source
review must precede a new vLLM commit. Any rerun requires a new main-repo
binding commit, fresh `m8p4-{a,b,c}` RPC paths, and a fourth preregistration.

The approved LocalMaxxing record remains unchanged.
