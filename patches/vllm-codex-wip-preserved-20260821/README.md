# Preserved uncommitted vLLM WIP (Codex era), 2026-08-21

Two uncommitted files were found in `/home/steve/src/vllm` (HEAD
`44fc8fde09`, the Codex-agent optimization line) when the Q64xK32 endpoint
campaign's sealed identity gate refused a non-empty source diff:

- `vllm/model_executor/layers/vocab_parallel_embedding.py`
- `vllm/v1/worker/gpu_model_runner.py`

This is another agent's work in progress (instrumentation-flavored: json/os
imports and related plumbing), preserved rather than discarded, per the
review-then-restore-clean-tree rule. Decoded patch SHA-256
`66f5823ca1f48545f1adef3731b165bc14975d374ff2899ce91272e94a30a852` — exactly
the diff digest the identity gate reported. The same bytes were also kept in
the tree via `git stash push` (message `codex-wip preserved 20260821`), so it
can be restored either way. Artifact:
`vllm-wip-66f5823c-20260821.diff.gz.b64`.
