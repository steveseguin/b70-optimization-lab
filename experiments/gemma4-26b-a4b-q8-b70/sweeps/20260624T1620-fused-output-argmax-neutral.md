# 2026-06-24 - Gemma 4 26B Q8 MTP fused output argmax

## Hypothesis

The direct-MTP assistant path only consumes sampled token IDs. If the draft
output head can compute `argmax(output_weight * hidden)` directly, it may avoid
materializing full vocab logits and reduce per-draft-step overhead enough to
move the Q8 fresh-response record above the current `98.617 tok/s`.

## Patch

Patch artifact:

- `patches/gemma4-26b-a4b-q8-b70/20260624T1620-llamacpp-gemma4-mtp-fused-output-argmax-neutral-current.patch`

Implementation summary:

- added experimental `GGML_OP_MUL_MAT_ARGMAX`;
- added SYCL backend implementation for Q4_0/Q8_0 output weights and a single
  F32 hidden vector;
- added `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1` to route GemmaAssistant direct
  MTP through the fused op;
- fixed run identity capture so the flag is logged in both server logs and
  `summary.json`.

Default behavior is unchanged unless `LLAMA_GEMMA4_MTP_FUSED_OUTPUT_ARGMAX=1`
is set.

## Valid Runs

Current best valid Q8 fresh-response record for comparison:

- `data/gemma4-q8-gpu0-mtp-n7-directunroll7-qonly-b1024u1024-th8-syclgraph0-full-20260624T144749Z/summary.json`
- canaries: `384/384`
- fresh row0 after-TTFT: `98.61718830251647 tok/s`
- mean after-TTFT: `97.95563472401156 tok/s`
- `cached_tokens=0`

Fused output argmax screen:

- `data/gemma4-q8-gpu0-mtp-n7-fusedoutargmax-screen-20260624T155640Z/summary.json`
- canaries: `64/64`
- fresh row0 after-TTFT: `98.20833028461249 tok/s`
- `cached_tokens=0`
- rejected: below the standing record

Fused output argmax valid profile screen:

- `data/gemma4-q8-gpu0-mtp-n7-fusedoutargmax-profile-valid-20260624T161049Z/summary.json`
- server log: `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-mtp-n7-fusedoutargmax-profile-valid-20260624T161049Z.server.log`
- canaries: `32/32`
- fresh row0 after-TTFT: `97.89601949514567 tok/s`
- `cached_tokens=0`
- identity confirmed: record-stack llama-server, Q4_0 MTP draft, direct
  argmax IDs/unroll 7, q-only attention inputs, fused output argmax enabled

Invalid profile run to ignore:

- `data/gemma4-q8-gpu0-mtp-n7-fusedoutargmax-profile-20260624T160850Z/summary.json`
- measured `25.85456834067283 tok/s`
- invalid for this patch: launched the low-level baseline runner directly,
  defaulted to `/home/steve/src/llama.cpp/build-sycl-b70/bin/llama-server`, and
  did not construct the MTP `EXTRA_LLAMA_ARGS`.

## Profile Comparison

Baseline profile:

- `data/gemma4-q8-gpu0-mtp-n7-profile-baseline-20260624T142134Z/summary.json`
- final profile line: `draft_decode_ms=705.410` over `98` draft decodes
- decode phase: `per_call_ms=7.317`, `process_ubatch_ms=658.836`,
  `post_extract_ms=62.056`, `sampled_extract_ms=56.504`

Fused output argmax profile:

- final profile line: `draft_decode_ms=924.983` over `130` draft decodes
- decode phase: `per_call_ms=7.208`, `process_ubatch_ms=862.898`,
  `post_extract_ms=76.959`, `sampled_extract_ms=71.397`

Normalized per call, this is essentially unchanged:

- baseline draft step: about `7.2 ms/call`;
- fused output draft step: about `7.1 ms/call`, but no throughput gain in the
  end-to-end fresh-response benchmark.

The fused op does not address the dominant `process_ubatch` cost. The remaining
post-extract sampled-ID work is only about `0.55 ms/call`, and the replacement
kernel/reduction does not translate into a record.

## Decision

Rejected / neutral. Keep the patch artifact as a reference, but do not promote
this as a record path.

Next work should avoid output-head-only optimizations and focus on larger
execution-shape changes:

- reduce the assistant draft forward cost itself;
- fuse or batch multiple assistant draft positions in one graph/backend call;
- revisit lower-quality side lanes only as explicitly non-Q8 references;
- avoid warmed/history n-gram claims as headline fresh-response throughput.
