# 2026-07-05: normal-MTP partial-reject GDN replay experiment

Context: the separate INT4 draft LM-head path for
`webhie/Qwen3.6-27B-int4-AutoRound` showed a real speed signal
(`~72.8 tok/s` strict fresh diagnostic) but failed repeat/order quality. Trace
comparison against exact draft showed the target verifier tokens are still
chosen by the target model, but after an identical partial-reject row the next
GDN state diverges. The bad row was:

- prior visible output: `blue`;
- partial row output from sampler: `, green`;
- draft row: `, black,`;
- target row: `, green,`;
- next INT4 row produced `, red <eos>` while exact draft produced
  `, red, yellow`.

Interpretation: normal MTP does not use the draft-only rollback/replay path for
partial rejects, so the packed verifier row can leave Qwen3.6 GDN state past
the accepted-prefix boundary.

Patch under test:

- `/home/steve/llm-optimizations/patches/qwen36-27b-autoround-int4-b70/vllm-normal-mtp-partial-reject-gdn-replay-20260705.patch`
- env gate:
  `VLLM_XPU_SPEC_DECODE_REPLAY_NORMAL_PARTIAL_REJECT_GDN_STATE=1`
- paired with existing worker snapshot restore gate:
  `VLLM_XPU_SPEC_DECODE_RESTORE_DRAFT_PARTIAL_REJECT_GDN_STATE=1`

What the patch does:

- on normal-MTP partial reject with `0 < accepted < draft_len`, drop the packed
  verifier row's visible output;
- let the existing worker restore the pre-spec GDN/Mamba state snapshot and skip
  ReplaySSM commit/postprocess for that row;
- roll scheduler accounting back to the visible token boundary;
- force the accepted-prefix plus replacement span through ordinary one-token
  decode before speculative decoding resumes.

Results so far:

- First implementation rolled back `num_tokens_scheduled` but left async
  speculative placeholders and `num_computed_tokens` ahead of the visible
  boundary. It failed quality badly (`blue, red, yellow`, `blue`, and
  `blueuser...` variants). Trace showed `num_computed_tokens` still ahead by
  the stale draft span.
- Boundary fix (`num_computed_tokens <= num_tokens`, clear spec IDs and stale
  placeholders) passed a no-async focused quality isolation:
  exact cases pass, repeat64 pass, baseline match, long-context skipped for
  iteration speed.
  Artifact:
  `data/qwen36-27b-autoround-int4-b70-baselines/quality-qwen27-webhie-draftint4-normalpartialreplay-boundaryfix-noasync-quality-20260705T044759Z.json`.
- Async path is still blocked. AsyncScheduler repopulates placeholder spec IDs
  during forced-single recovery and/or double-counts output placeholders. Two
  async attempts crashed on `assert request.num_output_placeholders >= 0`:
  `qwen27-webhie-draftint4-normalpartialreplay-boundaryfix-quality-20260705T044530Z`
  and
  `qwen27-webhie-draftint4-normalpartialreplay-asyncforcesingle-quality-20260705T045648Z`.
  Trace showed the recovery row was correctly reset to the visible boundary,
  but the following async scheduled step reintroduced packed spec placeholders.

Current in-flight validation:

- strict no-trace candidate:
  `qwen27-webhie-draftint4-normalpartialreplay-noasync-strict-20260705T045838Z`
- result:
  `data/qwen36-27b-autoround-int4-b70-baselines/qwen27-webhie-draftint4-normalpartialreplay-noasync-strict-20260705T045838Z-candidate-summary-20260705T045838Z.json`
- strict fresh gate passed (`cached_tokens=0`), but speed collapsed to
  **28.72 tok/s median** and quality failed repeat32 after the realistic bench:
  `30/32` rows were `blue, green, red`, one was `blue,green,red`, and only one
  row was `blue, green, red, yellow`. Long-context and exact cases passed.

Conclusion: do not promote or submit. The scheduler-level replay hack is a
useful diagnostic because it proved the failure is state-boundary related, but
it is not a viable optimization: it is too slow and still state-fragile after
longer prior requests. The next credible route is a real accepted-prefix
GDN/DeltaNet tape/replay implementation (Hipfire-style) or a stronger drafter
that avoids arbitrary partial-reject state divergence, not more placeholder
accounting tweaks.
