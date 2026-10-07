# One fresh references-only recall trial

Status: completed structurally; clean shutdown and all-four-card postflight passed.
Independent review found 12/30 complete criteria: the semantic gate failed.
See [closeout](CLOSEOUT.md); exact original evidence remains under `results/`. This is a usefulness diagnostic, not model,
package, benchmark or unattended-agent qualification. The earlier ten-question
failure remains unchanged and is not rerun or repaired.

The test asks ten new questions against four complete documents at source commit
`a8bbae3119d9ea31d08bd8b7cec74941adabc6ac`, preserved by pushed tag
`lab-source/cited-recall-v2-20261007` across main rebases. Its thirty semantic criteria are
frozen separately from model inputs. Themes can overlap earlier operations
questions; corpus and question changes prevent a controlled causal comparison.

The proposed improvement is concise answers plus line references. The compiler
copies quotes exactly; it cannot choose evidence, repair an answer, or grade
meaning. All ten complete answers, natural stop, complete token IDs, zero cached
input tokens and valid line references are required before independent semantic
review. No retries, partial scoring of unfinished JSON, answer repair, tools or
external lookup. Original citation validator is an unchanged crosscheck.

## Fixed request and runtime

- One recall request, temperature 0, top_p 1, seed 42, thinking disabled.
- 10,135 input tokens from local pinned tokenizer; server must agree exactly.
- 28,000 input admission cap; 3,072 output cap; 33,024 total context.
- 420 seconds total network deadline and wire timeout. One supervisor with
  1,200-second lifetime; at least 480 seconds must remain before recall.
- Same installed R276 digest and unchanged official Qwen3.8-27B-FP8 revision
  as the prior small-cache diagnostic. TP2, cards 0/1, FP16 activation and full
  FP16 KV, explicit 2 GiB KV per rank, eager, no MTP or prefix caching.
- Eight identical finite marker/repeat boundary requests precede recall;
  they are runtime checks, not a general arithmetic or output-equivalence gate.
- All previous health, locks, container ownership, RAM exclusions, host64GiB
  staging admission and root50GiB reserve guards remain. No host settings change.
- Cold model source remains preserved; verified temporary RAM restore supplies
  the runtime. EX400U must be unmounted before any GPU operation.
- One graceful SIGINT on completion/error/deadline. No restart, retry, hard kill,
  driver reset or reboot. New faults halt requests. All four cards are checked
  after healthy shutdown. Only the temporary model copy may then be released.

`trial-protocol.json` binds the exact source, profile, messages, runner, compiler,
validator, shared wire parser and supervisor. `tokenization.json` records CPU
preparation. `model-restore/` preserves full cold-copy and RAM verification.
The fresh mounted-source receipt is checked again by the supervisor, followed
by another complete publisher hash verification before the first GPU probe.

Run the frozen server once with output at
`/home/steve/worker-cited-recall-v2-20261007/server`, then `check_boundaries.py`
with sibling `boundaries/`, then `run_recall.py`. The harness always creates
`server/STOP` on completion or failure and persists raw inputs, SSE, response,
metrics, compiled citations and hashes under sibling `recall/`.
Independent semantic grading follows only after completion. No serving copy
or public package will be promoted on structural correctness alone.
