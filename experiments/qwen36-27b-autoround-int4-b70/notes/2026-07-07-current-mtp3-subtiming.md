# 2026-07-07: Current MTP3 Subtiming Check

## Summary

This diagnostic rechecked the current valid Qwen27 ReplaySSM recipe with
decode timing enabled, after the state-digest trace work. It confirms the
headline recipe remains reproducible in the expected range, but it does not
create a new record because quality was skipped and the run was diagnostic.

The important technical result is that the current decode bucket is already a
clean fixed MTP3 graph bucket:

- `num_tokens_unpadded=4`
- `num_tokens_padded=4`
- `max_scheduled_spec_tokens=3`
- `use_spec_decode=true`
- `cudagraph_mode=PIECEWISE`

There is no visible padding waste in this path. The older idea that recurrent
MTP-next dispatch was an eager `~11 ms` bug should stay closed; timing labels
inside the captured proposer path are still partly host/async-attribution
contaminated.

## Run Identity

Label:

```text
qwen27-current-mtp3-subtiming-20260707T042536Z
```

Artifacts:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/diagnostics/qwen27-current-mtp3-subtiming-20260707T042536Z-20260707T042536Z
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-mtp3-subtiming-20260707T042536Z-candidate-summary-20260707T042536Z.json
data/qwen36-27b-autoround-int4-b70-baselines/qwen27-current-mtp3-subtiming-20260707T042536Z-timing-summary.json
```

Strict fresh-response mechanics:

- fixed Qwen realistic suite;
- each prompt once;
- `cached_tokens=0` on every request;
- `return_token_ids=true`;
- quality skipped, so this is not a promotion row.

Throughput:

| metric | value |
|---|---:|
| median tokens 1-100 after TTFT | `68.29651966631667 tok/s` |
| p10 | `62.53167668171678 tok/s` |
| mean | `67.96695475988614 tok/s` |
| median TTFT | `479.6927673742175 ms` |

This is consistent with the current promoted strict best
`68.23626314761921 tok/s` and should be treated as reproducibility support,
not a new LocalMaxxing submission.

## Timing Snapshot

Parsed from `scripts/summarize-xpu-decode-timing-log.py`:

| label | mean total per sampled step |
|---|---:|
| `gpu_model_runner.forward_total` | `21.4729 ms` |
| `gpu_model_runner.model_forward` | `21.4183 ms` |
| `gpu_model_runner.draft_total` | `15.5815 ms` |
| `gpu_model_runner.draft_proposer_call` | `15.2042 ms` |
| `spec_decode.propose.forward_context_next_total` | `13.3841 ms` |
| `spec_decode.propose.model_forward_next` | `13.2900 ms` |
| `gpu_model_runner.sample_total` | `0.4328 ms` |
| `spec_decode.greedy_sample_total` | `0.4278 ms` |

Interpretation caveat: the large draft/proposer labels conflict with the
previous synchronized MTP-forward split, which showed
`spec_decode.propose.model_forward_first/next` below `1 ms`. Treat those large
draft labels as async timing attribution, not as a fresh proof of a slow eager
MTP kernel.

## Decision

Do not reopen:

- MTP-next eager-dispatch debugging;
- wrapper-level LM-head/sampler reductions;
- scheduler-level replacement/bonus suppression sweeps;
- MTP4/MTP5 cache-size config sweeps.

The remaining credible Qwen27 work needs a real mechanism:

1. reduce target-body cost with measured kernel/body changes;
2. improve accepted tokens per target step with a stronger target-matched
   draft source that clears the offline acceptance threshold;
3. build graph-safe GDN/DeltaNet state transactions that make branch or
   target-tail regeneration possible without Python/scheduler replay;
4. only revisit verifier-row reduction if it avoids the already-closed
   replacement/bonus recovery trap.

