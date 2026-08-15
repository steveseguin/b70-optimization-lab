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

The first production-shaped native packed-kernel arm with ReplaySSM off and
the fixed full graph on,
`correctness-recovery-no-replayssm-20260815T175559Z`, is invalid as a benchmark:
it completed compile and graph capture, then failed on the first request with
`UR_RESULT_ERROR_DEVICE_LOST` before producing a benchmark row. Runner exit was
1 and manifest SHA256 is
`988b974d436d4f4e2919b2c1f43059ea245232190eb503a4889b128d05a0223a`.
All four XPUs passed a fresh allocation/readback probe after teardown, so no
reboot was needed. The next arm runs the same native packed kernel eagerly to
separate kernel/state correctness from graph-capture safety.

That eager packed-kernel arm completed at
`correctness-recovery-native-fast-eager-20260815T180325Z` and closes the
kernel-math side of the bisection:

- ReplaySSM, XPU graph capture, Qwen graph capture, forced-communication
  capture, and DDTree were all explicitly disabled;
- the ordinary packed native GDN kernel remained enabled;
- all 128 candidate token IDs exactly match the first 128 tokens of the frozen
  512-token target-only response;
- no comparable target verifier row disagreed across 35 aligned rounds;
- `candidate_is_exact_reference_prefix=true`, cache remained zero, and the
  process exited cleanly;
- `10.496396 tok/s` is diagnostic-only eager throughput, not a promotion
  result;
- post-analysis `SHA256SUMS` SHA256:
  `2c046bf99613f27539fad54e0e34ed334507368e8f6bc3ac83d07a3e946297a5`.

This one-prompt result showed exact eager execution through 128 tokens. The
later frozen 25-prompt validation disproved the broader claim that packed GDN
arithmetic is target-exact: 10–11 long outputs per arm diverged from the
matching target-only control. The one-prompt result remains a valid narrow
canary, not proof of general arithmetic identity.

The next two arms isolated that boundary further:

- `correctness-recovery-replayssm-eager-20260815T181207Z` kept the complete
  native ReplaySSM stage/recurrent/commit transaction but disabled every graph
  layer. It reproduced the same target-verifier error at output token 6:
  row 1 of the second verifier round returned token `21261`, while ordinary
  target-only and the exact packed-eager path require `19214`. The diagnostic
  generated all 128 tokens, was cache-zero, exited cleanly, and measured only
  `1.219868 tok/s`. Its `SHA256SUMS` SHA256 is
  `ece39c7cb4f724a73401367cbb576fd88d45c491d0dcffa48471d778bc8aab62`.
- `correctness-recovery-replayssm-torch-eager-20260815T182007Z` replaced only
  the ReplaySSM recurrent kernel with its PyTorch reference and stopped after
  16 tokens. It produced the identical token-6 verifier error. The shortened
  row intentionally fails the 100-token benchmark window and is not a speed
  result; its manually completed verifier analysis is valid diagnostic
  evidence. Post-analysis `SHA256SUMS` SHA256 is
  `17438f117658ce8262c48c5894a92e0618b2aa592c3926ba092a0f5745672cee`.

Therefore the native ReplaySSM kernel is not independently corrupt and graph
capture is not required to reproduce the failure. The shared ReplaySSM
ring/checkpoint algorithm is numerically different from the exact per-token
packed recurrent path. In particular, ReplaySSM algebraically replays several
accepted updates in FP32 and rounds the checkpoint once, while the target's
packed recurrent path rounds its state at each token. Future strict work must
either make the transaction reproduce those per-token state transitions or
make the exact native packed path graph-safe; old narrow canary passes are not
sufficient evidence that ReplaySSM is target-exact.

Raw roots remain under
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/`; each root has a
post-teardown `SHA256SUMS`, source/runtime snapshots, trace, emitted token IDs,
and analyzer output. The invalid live-edited preflight remains excluded.

The persistent-scratch follow-up completed a frozen six-arm, 25-prompt matrix
at `fixed-scratch-validation-20260815T194000Z`. All arms were operationally
valid. The candidate's four-arm central median was **98.639 tok/s**; same-pair
fresh-start repeats were 25/25 and 24/25 exact. However, same-pair target parity
still failed on 10–11 of 25 prompts. The compact result is
[`../../../results/qwen36-27b-autoround-int4-b70/fixed-scratch-validation-20260815.json`](../../../results/qwen36-27b-autoround-int4-b70/fixed-scratch-validation-20260815.json).
Do not promote or submit it.

The preregistered recurring-divergence trace then used the exact
`holdout--concurrency-review` prompt and a fresh same-pair target-only stream:

- packed native eager was exact for all 128 tokens;
- the repaired serial eager path first differed at token 68 (`7499` vs
  target `9575`), in target verifier row 1;
- packed PIECEWISE with persistent scratch differed at the same token and row.

Thus the serial path is not a universal output oracle, while command-graph
execution remains non-exact even after the scratch-lifetime repair. The packed
eager diagnostic measured only `40.725 tok/s` on its first request because
that request included remaining Triton JIT work. The next bounded screen runs
the standard 64-token smoke first, then times the same cache-zero prompt. This
is a startup-prewarm attribution test, not a new performance claim.

That prewarmed packed-eager arm remained exact and cache-zero, but improved
only from `40.725` to `44.489 tok/s`; graph-free execution is therefore not a
viable performance route. The next default-off repair is XPU-kernel commit
`4050008863bf0db6047935f775378ab882265300`: persistent scratch is now keyed by
the immutable per-layer convolution-weight address as well as shape/device.
This prevents the 48 GDN layers from capturing separate command graphs against
one shared workspace. The full multi-target AOT build passed; candidate
`_xpu_C.abi3.so` SHA256 is
`3e38a9edc8d205d2693603748b3af7cdaf6699cb901be8bbf45b3b1076818455`.
Promotion still requires the token-68 PIECEWISE trace and then the complete
frozen matrix; this source-level argument is not treated as proof.

The token-68 layer-private trace failed at the identical verifier row and token
(`7499` vs `9575`). Both ranks logged exactly 48 private scratch allocations,
proving that the feature armed for all GDN layers; the cache-zero run remained
healthy and exited zero. Its manifest SHA256 is
`47061fe1b2b7456072fed5d6c0a87ac2e9f4f695d52f9e3ad5c249a17a0eba02`.
Per-layer scratch does not fix correctness and is retained only as a negative
experiment until reverted.

The next diagnostic, `native-fast-piecewise-no-replay`, retains Torch
compilation, the fixed four-row verifier, native packed GDN, and the same
persistent scratch, but sets
`VLLM_XPU_DISABLE_SPEC_DECODE_CUDAGRAPH_REPLAY=1`. Exact output would isolate
the fault to Level Zero replay; another token-68 failure would move the
boundary up to the compiled verifier itself.

The no-replay arm also failed at token 68 and measured `45.061 tok/s`; its
manifest SHA256 is
`7e227493af9b6727e9bb2ec832c4f697253b9c1d6ec856a05e07f0f371fca6a1`.
Level Zero replay is therefore not required for the divergence.

The next source change is the exact reviewed upstream XPU fix
`aeece10c061b8ef708b1962c175f5600f05c1933`, applied on local `main` as
`3722d8a0fb7cdd3c052fb7b1468b85171c746e1f`. It wraps
`gdn_attention_core_xpu` with `eager_break_during_capture`, keeping GDN outside
breakable command graphs while allowing the surrounding verifier to remain
compiled/captured. This is a current upstream safety behavior, not a local
invention. It must first pass the same token-68 trace; speed is secondary until
then.

That upstream eager-break arm still failed at the identical verifier row and
token (`7499` vs target `9575`). It was otherwise healthy, cache-zero, and
measured `85.641 tok/s`; its manifest SHA256 is
`6eba982d50df4543ae787c55a648684ef199c2c7aee64f33209a38d3aae643b1`.
Moving GDN itself outside breakable command graphs is therefore not sufficient.
The next bounded arm keeps the PIECEWISE runtime and ordinary compiled decode,
but sets `VLLM_XPU_SKIP_COMPILED_SPEC_DECODE=1` so only the speculative target
forward uses the raw model. This tests the compiled-verifier boundary directly;
it is a correctness diagnostic, not a promotion benchmark.

That raw-verifier arm passed the recurring canary completely. All 128 output
tokens match the fresh same-pair target, all 50 aligned verifier rounds agree,
and the former token-68 disagreement is absent; the analyzer classification is
`no_divergence_in_window`. The row was fresh and cache-zero, but measured only
`22.218 tok/s`, so bypassing the entire compiled verifier is an oracle, not a
performance solution. Raw root:
`correctness-recovery-native-fast-piecewise-skip-compiled-20260815T221000Z`;
post-teardown manifest SHA256:
`393d9a4e9b8d9c1bbe7a824cf5f53b8a2df57dd25bda9260403fd7fb457c645c`.
This establishes the compiled speculative target forward as the correctness
boundary. Future work should keep the exact raw result as the oracle while
selectively changing compilation/partitioning, rather than revisiting scratch
or Level Zero replay.

The first Inductor-partition startup at
`correctness-recovery-native-fast-piecewise-partition-20260815T222000Z`
failed closed before serving a request. Enabling the newer partition mode also
enabled the irrelevant MLA RoPE/KV-cache fusion in this mixed local source, but
the XPU pass manager had not imported `MLARoPEKVCacheCatFusionPass`; runner exit
was 5 and no throughput/parity row exists. Manifest SHA256:
`87a7c97abdb7af2aae65b121be7815f598d843451980c5d116f27ab579982693`.
The rerun explicitly disables that MLA-only pass in `pass_config` while leaving
the intended Inductor partition change intact.

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

1. Screen a current partitioning/compile identity while retaining the exact
   packed-GDN transaction. The first candidate is PIECEWISE with
   `use_inductor_graph_partition=true`; it must pass the token-68 oracle before
   any throughput interpretation.
2. If it fails, instrument compiled versus raw hidden states at the first
   divergent verifier round and bisect compile boundaries. Do not retry shared
   scratch, per-layer scratch, Level Zero replay bypass, or the upstream GDN
   eager break; all are already closed negatives.
3. Once a fast arm passes the canary, require exact same-pair parity and
   fresh-start repeatability on the frozen 25-prompt suite before promotion.
4. Only after correctness passes, port the current upstream XPU safety fixes
   and performance changes one focused commit at a time, then optimize against
   the central-median, cache-zero cold-prompt standard.
