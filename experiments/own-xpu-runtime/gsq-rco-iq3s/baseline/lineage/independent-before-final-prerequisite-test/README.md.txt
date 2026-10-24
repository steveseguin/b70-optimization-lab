# Fixed resident target/MTP baseline

This preparation preregisters all twelve prompts from the frozen P195 cap-128 corpus, in their original order, with unchanged input token arrays. Ten tokenizer metadata hashes match between the old and new model. Old-model output oracles and record claims are not used.

One admitted rank pair remains resident throughout. Two distinct five-token synthetic warmups, selected by the exact frozen P195 `select_warmup` function, each request eight outputs and are excluded. Neither warmup occurs as a contiguous span in any benchmark prompt. They initialize both target-only and MTP paths; they do not establish that every later shape or acceptance path is free of first-use cost.

Each of the twelve 60–90-token prompts receives two fresh requests capped at 128 outputs. Even-index prompts run target-only then MTP; odd-index prompts reverse that order. The original full RESET runs before **every** request, including both warmups. No prompt/KV reuse is allowed. Both arms must match every emitted token and complete final target-state hashes. Any mismatch stops new requests and delegates cooperative cleanup/retained ownership to the frozen serving adapter.

All early-EOS cases remain in the evidence and summary. Reports include per-request prompt wall time, completion timestamps, N−1 decode intervals, MTP guesses/hits/misses, both first-arm order groups, and every prompt's raw result. No short or low-acceptance case is dropped. A single resident run with initialized kernels and short prompts is not a cold-start, long-context, general-quality, or old-model record measurement. The first smoke test's target-first JIT time is not a fair performance baseline.

## Scope and budget

`suite.py` provides a plan-only CLI and a coordinator-only `qualification(plan, admit, check, launch_hook)` API. The root coordinator still owns boot/fault, physical ownership, RAM, queue, signal and final-drain admission. This layer starts no services and performs no automatic retry or pruning.

The outer suite explicitly owns the 26-request cap and expanded storage forecast. It reuses the frozen adapter's Transport, NativeController, RESET, state hashing and failure cleanup; it does not call the adapter's two-request comparison helper or silently relabel that helper's original budget. Both builds and the actual native binary remain unchanged. Admission requires the independently passed first real-model 32-token/state proof, clean owner/drain evidence, and the exact same binary SHA256.

The lifetime is bounded to 7,200 seconds, with at most 3,088 emitted tokens (24×128 measured plus 2×8 warmup). The external evidence forecast is 27×231,442,500 bytes plus 64 MiB metadata, or 6,316,056,364 bytes (the initial blank state dumped by the first RESET plus 26 request states). Root cache forecast remains 128 MiB above a 27 GB free-space floor; external evidence retains a 2 GiB floor. These are monitored forecasts, not hard filesystem quotas. Remaining-request storage admission is rechecked before every request. No raw evidence is deleted.

Full traces and state evidence remain on the external evidence filesystem. The API returns a compact terminal join with the complete external result path and SHA256, avoiding a second large trace copy in the coordinator's bounded terminal receipt.

Eight CPU tests exercise the actual suite orchestration with mocked owners, original corpus/source checks, full RESET ordering, balanced requests, excluded warmups, early EOS, timestamp validation, token/state mismatch halt, and retained-error propagation. They do not execute a model, native owner, device or service. Root must review and admit an actual plan before running this suite.
