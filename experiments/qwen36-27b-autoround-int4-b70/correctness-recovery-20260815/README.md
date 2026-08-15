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

## Completed bisections

The frozen one-prompt diagnostic now establishes all of the following:

- corrected ordinary target-only (`correctness-recovery-target-only-20260815T170154Z`)
  exactly matches the frozen 128-token target reference; the target oracle is
  stable;
- standard MTP3 first differs at generated token 6. The target verifier itself
  returns token `21261` for that position while ordinary target-only returns
  `19214`;
- synthetic zero acceptance, graph-replay bypass, and compiled-verifier bypass
  all retain the same first wrong target row, ruling out rejection accounting,
  XPU graph replay, and Torch compilation as the primary cause;
- disabling ReplaySSM also retains the same first wrong target row. It measured
  only `11.618 tok/s` on this single diagnostic prompt, so it is both incorrect
  and substantially slower. This is not a promotable throughput result.

The current boundary is therefore the packed GDN/recurrent-state execution,
below ReplaySSM and graph capture. The next arm uses the sequential native GDN
implementation while retaining the four-row verifier.

Raw roots remain under
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/`; each root has a
post-teardown `SHA256SUMS`, source/runtime snapshots, trace, emitted token IDs,
and analyzer output. The invalid live-edited preflight remains excluded.

Two post-consolidation startup roots are also invalid measurements and retained
only as merge-repair evidence:

- `correctness-recovery-native-serial-20260815T171713Z` failed model inspection
  because the preserved GDN class used its pre-upstream-rename symbol;
- `correctness-recovery-native-serial-20260815T171915Z` progressed farther but
  failed worker initialization because the preserved tree-attention backend was
  not restored to the newer backend enum.

Neither root contains a benchmark row. The diagnostic runner now fails closed
when the historical candidate wrapper exits zero without exactly one valid
cold benchmark row.

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
