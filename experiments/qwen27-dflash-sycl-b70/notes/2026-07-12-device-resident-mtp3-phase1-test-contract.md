# Device-resident MTP3 phase-one test contract

## Purpose

This is the correctness gate for replacing the Qwen MTP3 token/hidden
device-to-host-to-device loop with context-owned backend staging.  Throughput
testing is invalid until every case below passes against the ordinary host
path on the same model, prompt, sampler configuration, and device.

The comparison unit is one complete speculative cycle, not merely one kernel.
The device path may submit all three draft steps before applying `p_min`, but
its externally visible draft, accepted prefix, target memory, and next-cycle
logits must be identical to the host path.

## Required observable contract

The implementation needs a narrow internal test interface.  It must not expose
scheduler-owned graph tensors as if they had stable lifetime.

1. A context-owned staging descriptor must report:
   - capacity, hidden width, token type, hidden type and backend;
   - valid row count and monotonically increasing content generation;
   - a stable allocation identity that changes only when the context-owned
     allocation itself is replaced, not on scheduler reset/rebuild.
2. A synchronized debug readback must copy one staged row into caller-owned
   `token`, `probability`, and `hidden` buffers and reject an invalid row.
   This is test observability, not the production data path.
3. The device-input decode entry point must return a status that distinguishes
   `used_device_input`, `unsupported_backend`, `backend_mismatch`,
   `layout_mismatch`, `invalid_row`, and ordinary decode failure.  Unsupported
   inputs must not silently take the host upload path.
4. A test-only scheduler perturbation must perform the same scheduler reset
   used between ordinary decodes and force one allocation/graph rebuild.  The
   test must be able to confirm that both events occurred.
5. The MTP driver must expose a per-cycle diagnostic record after one final
   synchronization:
   - three raw candidate tokens and probability bit patterns;
   - three raw hidden-row hashes;
   - the early-stop index and visible draft length;
   - accepted count, emitted tokens, draft/target sequence position maxima;
   - whether each step consumed staged device input;
   - scheduler reset/rebuild counters and staging allocation identity.

The minimum practical API shape is therefore equivalent to:

```cpp
struct llama_mtp_stage_info;
struct llama_mtp_cycle_debug;

bool llama_mtp_stage_get_info(ctx, &info);
bool llama_mtp_stage_readback(ctx, row, &token, &probability, hidden, n_hidden);
llama_mtp_decode_status llama_decode_mtp_staged(ctx, metadata, input_row, output_row);
bool llama_mtp_debug_reset_scheduler(ctx, force_rebuild);
bool llama_mtp_cycle_get_debug(spec, seq_id, &debug);
```

Names may differ, but omitting equivalent observability makes the lifetime,
fallback, and early-stop requirements untestable.  Raw backend addresses alone
are not a lifetime contract; use an allocation ID owned by the staging object.

## Test matrix

### 1. Staging lifetime across reset and rebuild

1. Run one host-input MTP step and stage its top-1 token, probability and
   `h_nextn` row.
2. Read back and retain their exact bytes plus allocation ID and content
   generation.
3. Perform an ordinary scheduler reset, then read the same staged row again.
4. Force a scheduler allocation/graph rebuild with a different graph shape,
   then read it a third time.
5. Require byte equality for all three values, unchanged allocation ID,
   unchanged content generation, and incremented reset/rebuild counters.
6. Overwrite that staging row with the next MTP result.  Require unchanged
   allocation ID, incremented content generation, and new bytes.

This catches the unsafe implementation where staging aliases
`llm_graph_result` storage and happens to work until its next allocation.

### 2. Host-input versus device-input bytes

Fork two fresh contexts from the same checkpoint.  For draft steps 0, 1 and 2:

1. Feed `(token, h)` through the existing host `llama_batch` path in context A.
2. Feed the byte-identical staged row through device input in context B.
3. Require the device decode status to be exactly `used_device_input`.
4. Compare candidate-0 token exactly, probability by its 32-bit representation,
   and all `n_embd` hidden floats byte-for-byte after synchronized readback.
5. Compare the next step's logits/candidate tensor as a secondary guard.

Run one negative case each for invalid row, wrong hidden width, host-backed
stage, and cross-device stage.  Each must return its explicit error without a
decode or host upload.

### 3. Early-stop positions

Avoid depending on naturally occurring probabilities.  Add a diagnostic-only
threshold override derived from the three already-computed probability bit
patterns.  Run four cases from the same checkpoint:

| Case | Threshold construction | Expected visible result |
|---|---|---|
| stop 0 | greater than step-0 probability | empty draft |
| stop 1 | pass step 0, fail step 1 | token 0 only |
| stop 2 | pass steps 0-1, fail step 2 | tokens 0-1 |
| no stop | lower than every probability | all three tokens |

When adjacent probabilities make a single scalar threshold unable to select a
particular position, the test-only override must accept a three-element
per-step pass mask.  Do not search prompts until the desired ordering appears.

For every case compare host and device paths on raw candidates, visible draft,
stop index and next-cycle input.  The device path must show three submitted
steps even when the visible draft stops earlier.

### 4. KV rollback and full acceptance

For accepted counts `0, 1, 2, 3`, restore host and device paths from identical
target and draft checkpoints, execute one complete cycle, commit that accepted
count, then decode one identical continuation token.

Require:

- identical emitted token sequence and target candidate-0;
- identical target and draft `llama_memory_seq_pos_max()` values;
- byte-identical continuation logits (or an explicitly justified numerical
  tolerance if a backend operation itself is nondeterministic);
- identical next-cycle candidate tokens/probability bits/hidden hashes;
- rejection (`0`) removes every speculative KV entry;
- partial acceptance retains exactly the accepted prefix;
- full acceptance retains all three accepted entries without re-evaluating or
  duplicating a position.

The continuation comparison is the authoritative state test.  Position maxima
alone cannot detect a wrong recurrent snapshot or wrong KV contents at a valid
position.

### 5. Reset/rebuild inside a complete cycle

Repeat tests 3 and 4 while forcing a scheduler rebuild after draft step 0 and
again after step 1.  This is separate from test 1: it proves later steps consume
the context-owned staged bytes, not stale scheduler storage.

## Promotion gates

- All cases pass with the device path default-off.
- The negative-path statuses prove no silent host fallback.
- Deterministic 128-token generation matches the host implementation exactly.
- The strict realistic suite passes with `cached_tokens=0` before any speed is
  reported.
- Diagnostic records confirm one final host materialization per MTP3 cycle,
  not one synchronization per draft step.

## Current blockers to executable coverage

The current tree exposes synchronized host accessors only.  It has no stable
staging descriptor/readback, no explicit device-input decode status, no forced
scheduler-rebuild hook, and no complete-cycle diagnostic record.  Consequently
the existing recurrent rollback test can validate checkpoint restoration but
cannot prove device staging lifetime or distinguish a silent host bounce.

The first executable test should be added as a separate
`tests/test-mtp-device-staging.cpp` once the staging and device-input symbols
land.  It should be model-gated like `test-recurrent-state-rollback.cpp` and
should skip models without an MTP head rather than weakening its assertions.

## First executable results

`tests/test-mtp-device-staging.cpp` is now present and links in the JIT SYCL
build. Its first Qwen runs found two concrete integration failures:

1. The production MTP backend sampler chain contains `top_k` only. It exposes
   ten candidate IDs but no probability tensor (`candidates=10`, `probs=0`),
   while staging requires both. Consequently the first staging slot remains
   invalid. Adding a probability-producing sampler to the test makes staging
   populate, but the production chain still needs the same semantic fix.
2. Once populated, arming slot 0 as the next input aborts with
   `MTP token device input requires non-host backend buffers`. The persistent
   source tensor is device-backed, but the scheduler-owned token graph input is
   still host-backed. The device-input graph must explicitly allocate token and
   hidden destinations on the staging device (or bypass the token input through
   a device-resident embedding path) before D2D consumption is possible.

These are implementation failures, not test limitations. Lifetime, rebuild,
and host/device-output equality assertions remain pending until the device
input reaches graph execution.

### Corrected phase-one result

The focused failures drove two corrections: top-k-only staging now treats
probability as optional, and the Qwen35/Qwen35MoE MTP graph pins its token and
hidden inputs to the actual SYCL compute backend instead of `SYCL_Host`.

The real Qwen3.6 27B Q4_0 test on one B70 then passed with exit code zero:

```text
main : staging bytes and lifetime validated
```

This run proves:

- exact candidate-token and `h_nextn` bytes between staged and host output;
- a device-fed next step matches an independent host-fed context even when the
  ordinary host token and hidden fields are deliberately poisoned;
- staging tensor identity and bytes survive an M=1 to M=2 scheduler graph
  rebuild;
- invalid steps, unstaged input arming, disable, and re-enable invalidate or
  reject content as specified.

Probability/early-stop coverage remains deliberately pending: phase one is
guarded to `p_min == 0`, so the production top-k-only chain does not materialize
a probability tensor. The complete accepted-count/KV rollback matrix also
remains required before the device-unrolled driver can be promoted beyond its
current fixed-three-step scope.
