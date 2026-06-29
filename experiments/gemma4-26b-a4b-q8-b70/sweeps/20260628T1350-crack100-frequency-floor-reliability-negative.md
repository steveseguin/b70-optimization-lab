# 2026-06-28 crack-100 reliability: GPU frequency floor negative

## Question

Can a higher B70 GPU frequency floor make the current strict Gemma 4 26B A4B
Q8 lane reliably crack `100 tok/s` on the realistic fresh-response gate?

## Baseline / current promoted record

Promoted strict record:

- `data/gemma4-q8-gpu1-strict-vdr2-f16p021-bulksampled-confirm-B-n3-nmin2-p00475-ub1024-full512-20260628T052158Z/summary.json`
- median tokens 1-100 after TTFT: `98.34046474459183 tok/s`
- p10: `85.97937679810455`
- mean: `95.95288855186745`
- full512 median after TTFT: `91.17386231553596`
- valid: fixed realistic suite, each prompt once, `cached_tokens=0`, canary pass.

The strongest single strict `>100` observation before this check was:

- `data/gemma4-q8-gpu0-strict-vdr2-f16p021-bulksampled-unroll6-n3-nmin2-p00475-ub1024-full512-20260628T062352Z/summary.json`
- median tokens 1-100 after TTFT: `101.076`
- p10: `93.129`
- full512 median after TTFT: `92.421`

This row is valid, but was not promoted as a reliable headline because repeats
did not hold `>100`.

## Experiment

Set the B70 frequency range to a higher floor (`2400,2800`) and rerun the
current strict identity / nearest best identity under the full realistic gate.
The expectation was that avoiding low-frequency residency might push the
already-close 98-101 tok/s family over 100 consistently.

## Results

| run | median 1-100 | p10 1-100 | mean 1-100 | full512 median | validity |
| --- | ---: | ---: | ---: | ---: | --- |
| `gemma4-q8-gpu0-freq2400-current-full512-20260628T1330Z` | `100.224` | `89.255` | `99.493` | `91.920` | valid, canary pass |
| `gemma4-q8-gpu0-freq2400-confirmA-full512-20260628T1340Z` | `96.052` | `86.601` | `96.953` | `92.294` | valid, canary pass |
| `gemma4-q8-gpu1-freq2400-confirmB-full512-20260628T1340Z` | `93.510` | `88.046` | `95.373` | `90.846` | valid, canary pass |
| `gemma4-q8-gpu2-freq2400-confirmC-full512-20260628T1340Z` | `92.856` | `84.449` | `92.852` | `90.376` | valid, canary pass |
| `gemma4-q8-gpu3-freq2400-confirmD-full512-20260628T1340Z` | `94.440` | `85.858` | `94.640` | `90.486` | valid, canary pass |
| `gemma4-q8-gpu0-freq2400-aff-u6-confirmE-full512-20260628T1350Z` | `97.054` | `86.850` | `97.311` | `92.648` | valid, canary pass |

The first GPU0 run did crack `100`, but the follow-up confirmations regressed
to the low/mid-90s. The exact best-identity rerun with CPU affinity and direct
argmax unroll also landed below the promoted record.

The GPUs were restored to the default `400,2800` frequency range after the
test. Do not assume the 2400 floor is active for future runs.

## Decision

Negative / not reliable.

The frequency floor can produce a lucky strict `>100` sample, but it does not
make the result reproducible enough to promote or submit. Treat `100.224` the
same way as the earlier `101.076` row: a valid high observation, not a reliable
record.

## Implication

The current family is genuinely close to `100`, but more clock/frequency
testing is low ROI. Reliable `>100` likely needs one of:

- reduced exact target/verifier cost, especially LM-head or verifier MoE rows;
- higher fresh-request MTP acceptance on the hard realistic prompts without
  history/repetition tricks;
- a real source-level scheduling/kernel improvement that lowers variance on
  the slow prompt subset.

Avoid repeating unchanged p-min/unroll/ubatch/frequency sweeps unless a new
profile or code change gives a concrete reason.
