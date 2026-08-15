# Qwen3.6 27B INT4 TP2 correctness recovery

This lane repairs the failed 2026-08-15 independent validation before doing
any further performance promotion.  The recorded MTP3 endpoint measured a
four-start central median of `98.766 tok/s`, but it failed the stronger current
gate:

- every speculative arm differed from its same-pair target-only control on
  all 25 realistic prompts;
- fresh speculative restarts differed on 19/25 and 21/25 prompts;
- target-only controls were exact across both physical GPU pairs.

No result from this directory is a LocalMaxxing candidate until the repaired
path is exact against a stable target-only reference and repeatable across
fresh starts.

## First diagnostic

`run-verifier-trace.sh standard` starts one fresh copy of the recorded fixed-width-four
MTP3 server and sends only the later holdout arithmetic prompt.  That prompt
first diverged from target-only after six output tokens, so 64 generated tokens
are enough to isolate the failure without tuning on throughput.

The existing default-off verifier trace records, for each speculative round:

- draft token IDs;
- target argmax IDs for all verifier rows;
- accepted-prefix length;
- emitted token IDs and the target-owned bonus ID.

`analyze-verifier-trace.py` aligns those rounds with the emitted response and
the frozen target-only response from the independent validation.  It reports
whether the first mismatch is already present in the target model's first
verifier row (target graph/state problem) or appears only after rejection and
commit bookkeeping.

This is a diagnostic run, not a benchmark.  It uses the benchmark lock, keeps
Muse disabled, refuses an existing output directory, pins the exact historical
source/runtime/model identity, disables smoke and the legacy quality packet,
and hashes all files after server teardown.

`run-verifier-trace.sh zero` uses vLLM's existing synthetic rejection sampler
with acceptance rates `[0, 0, 0]`.  It therefore executes the identical
four-row target verifier but emits only the target-owned first-row token on
every round.  This is the controlled split between accepted-draft transaction
handling and width-four target/state arithmetic.

### Invalid preflight

The first standard attempt created
`correctness-recovery-20260815T163528Z`, then the live harness file was edited
to add the zero-accept mode while Bash was still executing it.  Bash reread the
changed tail and began an unintended second server launch in the same output
directory, overwriting the first server log.  The process group was stopped,
the benchmark lock was released, and Muse remained inactive.  That root is
retained outside Git as harness-failure evidence but is invalid for diagnosis
or performance.  Both measured arms must use the frozen committed harness and
fresh output roots.

## Next gates

1. If the first target verifier row is already wrong, force zero accepted draft
   tokens while retaining the width-four verifier.  Exactness there separates
   width-dependent target math from accepted-state transaction errors.
2. If target rows are correct but emitted tokens diverge, fix rejection/state
   commit accounting and add focused unit tests.
3. Require exact 25-prompt target parity and fresh-start repeatability before
   measuring speed.
4. Only after correctness passes, port relevant current upstream XPU/vLLM
   fixes and optimize against the central-median, cold-prompt standard.
