# Gemma 4 26B Q8: verifier next-target audit

Date: 2026-06-29.

Purpose: preserve the parallel code-audit conclusions for the next non-duplicate
Gemma optimization target after the `115.8466634928202 tok/s` full512 record.

No source edits were made for this audit.

## Validity Anchor

Only fixed realistic cold-suite runs with `cached_tokens=0` count as headline
throughput. Current one-B70 Q8 target/verifier record remains:

- `115.8466634928202 tok/s` median generated-token throughput for tokens
  1-100 after TTFT;
- `data/gemma4-q8-gpu1-selecteddown-bf16retest-control-full512-20260629T051323Z/summary.json`;
- LocalMaxxing ID `cmqyrpox4021dqk01co5o4fcw`.

## Closed Verifier Lanes

Do not repeat these as-is:

- backend sampled-ID plumbing:
  `LLAMA_SPEC_VERIFY_BACKEND_ARGMAX_IDS=1` and
  `LLAMA_SPEC_VERIFY_BULK_SAMPLED_IDS=1` are already in the record stack and
  avoid full verifier-logit host reads;
- verifier LM-head argmax shortcuts: fused output argmax, raw/softcap argmax,
  reorder-ncols compact argmax, regular-Q8 MMVQ top1 epilogue and partial
  reductions were neutral or negative;
- simple no-bonus verifier rows: saving the fourth row loses the bonus-token
  pipeline and reprocesses work;
- staged target decode / split bonus: `2+2` and `2+1+1` schedules saved rows
  but paid too much extra decode/scheduler cost;
- late-head bonus and prefix2 tail-head `SPEC_HEAD`: correct but slower because
  they add a second graph boundary/copy/sync path;
- small host/terminal tweaks: EOG clipping, skip-stateless accept, duplicate
  `h_nextn` copy removal, and target-to-draft handoff were valid/diagnostic
  but not record levers.

## Code Anchors

- verifier row construction:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/tools/server/server-context.cpp:546`;
- `spec_i_batch` population:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/tools/server/server-context.cpp:566`;
- speculative sample/accept:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/tools/server/server-context.cpp:4303`;
- backend sampled-row copy:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/llama-context.cpp:1902`;
- backend sampled-token read in speculative sampling:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/common/sampling.cpp:774`;
- Gemma4 fused verifier output argmax:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/models/gemma4.cpp:657`;
- fallback LM-head logits:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/src/models/gemma4.cpp:696`;
- draft candidates are host-side in `server_slot::spec_draft`:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/tools/server/server-context.cpp:217`;
- direct-MTP unroll publishes sampled IDs host-side:
  `/home/steve/src/llama.cpp-gemma-record-repro-c926/common/speculative.cpp:1794`.

## Recommended Non-Duplicate Shapes

1. **Row-adaptive verifier output inside the existing target decode boundary.**
   Preserve the current bonus-token pipeline, avoid a second `SPEC_HEAD` graph
   launch, and only skip expensive verifier LM-head rows when the decision is
   known before building that same target decode. If a design computes the bonus
   row unconditionally or adds another graph boundary, it duplicates lanes
   already closed.

2. **Post-argmax verifier payload / prefix compare.** Candidate IDs are
   host-side today, so a first implementation can upload the tiny draft-candidate
   vector and compare it with existing sampled argmax IDs in a compact graph or
   backend payload. This will not remove LM-head work, but may reduce host
   looping/sampler transitions and can validate row alignment before attempting
   a deeper candidate-vs-max LM-head design.

3. **True candidate-vs-max LM-head shortcut.** This is only worthwhile if it
   avoids materializing verifier logits or reduces LM-head work while preserving
   exact target-model verification. Previous top1 epilogue attempts lost because
   custom max-reduction work was slower than regular matmul plus compact argmax,
   so do not build another version unless it reuses the fast existing matmul path
   or removes rows.

## Risks To Guard

- sampler state updates must remain correct after any compact accept path;
- row alignment through `inp_out_ids` and `spec_i_batch` must remain exact;
- bonus-row mode differs across normal, late-head, prefix2, and staged MTP3
  paths;
- suppress-token/output-scale guards disable monotonic-argmax shortcuts;
- draft candidate IDs are not currently resident in the target graph as a
  persistent device tensor.
