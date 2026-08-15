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
- the first attempted no-ReplaySSM arm measured `11.618 tok/s`, but a later
  wrapper audit proved that the promoted launcher overwrote the requested
  `VLLM_XPU_GDN_REPLAYSSM_SPEC=0` value. Its log preallocated all 48 ReplaySSM
  rings. Retain the run as harness evidence, not as a ReplaySSM bisection or a
  promotable throughput result.

The current boundary is the target verifier's packed GDN/recurrent-state
execution, but ReplaySSM itself is not yet ruled out. The corrected next arm
uses the sequential native GDN implementation with ReplaySSM and XPU graph
capture both explicitly disabled while retaining the four-row verifier.

That corrected arm completed at
`correctness-recovery-native-serial-20260815T173738Z`. It is valid as a
one-prompt diagnostic, but not as a performance result:

- the server ran with ReplaySSM and every XPU graph mode explicitly disabled;
- the first four-row verifier was exact and accepted all three draft tokens;
- the next verifier's row 0 repeated token `369`, while ordinary target-only
  required token `28253`;
- first candidate/reference divergence was output index 5;
- the diagnostic rate was only `2.996662 tok/s`, as expected for the
  deliberately serial path;
- the post-teardown manifest SHA256 is
  `c7734b9656bfa24e2adf1ca7f8d282dfefd05529d5825fbe62c81f457ac58ec7`.

This rules out the parallel native recurrent kernel as the sole cause. The
serial implementation publishes per-row speculative state but, unlike the
native packed kernel contract, does not promote the previously accepted state
into the running column before the next speculative row. The exact accepted
count and block-table metadata are the next evidence gate; do not substitute
the already-rejected global prefix-count or plus-one variants.

The bounded metadata rerun
`correctness-recovery-native-serial-20260815T174802Z` confirmed the missing
edge. Rank 0 recorded three GDN cache groups per forward, with block columns
`[1,2,3,4]`, `[5,6,7,8]`, and `[9,10,11,12]`. The first verifier received
`num_accepted_tokens=1`; the second received `4`, after the first round had
accepted all three drafts and emitted its bonus. Therefore the second forward
must promote source column `4 - 1 = 3` into running column 0 before processing
row 0. The trace reproduced the same output-index-5 failure; its post-teardown
manifest SHA256 is
`1c4c3d622f73cb714c1d1566b0999be0cc62c1495deb9caad4a508a24c8fe64b`.

The serial repair is vLLM commit `8c27a1e68`: before processing a serial
speculative row, gather state column `num_accepted_tokens - 1` and promote it
to the running column, matching the native packed-kernel contract. The matched
post-fix run is
`correctness-recovery-native-serial-20260815T175207Z`:

- all 128 candidate token IDs exactly match the first 128 tokens of the frozen
  512-token target-only response;
- no comparable target verifier row disagreed across 35 aligned rounds;
- `candidate_is_exact_reference_prefix=true` and classification is
  `no_divergence_in_window`;
- cache remained zero and the run exited cleanly;
- `4.108457 tok/s` is diagnostic-only serial throughput;
- post-analysis manifest SHA256:
  `9c951722f3b4173c58356a1bf56723d994666eec7a5f87d7bfc423ba154c1237`.

The analyzer now treats a shorter exact candidate as a reference prefix rather
than a false divergence at the candidate's EOF. Its regression check retains
the original index-5 failure classification for the unpatched run and reports
no divergence for the repaired run.

Raw roots remain under
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/`; each root has a
post-teardown `SHA256SUMS`, source/runtime snapshots, trace, emitted token IDs,
and analyzer output. The invalid live-edited preflight remains excluded.

Five post-consolidation startup roots are also invalid measurements and retained
only as merge-repair evidence:

- `correctness-recovery-native-serial-20260815T171713Z` failed model inspection
  because the preserved GDN class used its pre-upstream-rename symbol;
- `correctness-recovery-native-serial-20260815T171915Z` progressed farther but
  failed worker initialization because the preserved tree-attention backend was
  not restored to the newer backend enum;
- `correctness-recovery-native-serial-20260815T172210Z` reached the Mamba cache
  selector, then failed because the preserved Qwen GDN layer still returned the
  old string backend name instead of the newer `MambaAttentionBackendEnum`;
- `correctness-recovery-native-serial-20260815T172613Z` completed target graph
  compilation, then failed graph-capture setup because the preserved XPU
  communicator did not expose the newer coordinator's disabled `ca_comm`
  contract;
- `correctness-recovery-native-serial-20260815T173200Z` reached XPU graph
  capture, where the eager serial oracle correctly refused an event wait. This
  exposed the wrapper override bug: native serial and no-ReplaySSM diagnostics
  must bypass command-graph capture instead of inheriting the promoted record
  wrapper's forced graph settings.

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
