# DFlash B=6/B=9/B=16 source-width oracle

Date: 2026-07-13 UTC

## Outcome

Existing corrected target-feature artifacts were sufficient for the core
source-BF16 oracle. No new target capture, benchmark-prompt request, protected
llama.cpp change, or GPU3 operation was required.

On 512 common target-owned anchors, endpoint-mixed B=16 increased visible
tokens per speculative step from `2.9980` at B=6 to only `3.2559`. The paired
gain was `+0.2578` accepted drafts (`95%` normal interval `+0.1512` to
`+0.3644`). B=9 reached `3.1543` visible tokens/step.

Width is not semantically invariant: endpoint-mixed B=16 changed at least one
of rows 1..5 on `128/512` anchors, and only `94.26%` of first-five top-1 IDs
matched B=6. However, the resulting `8.6%` visible-token gain is far too small
to justify the already measured native B=16 draft and verifier latency cliffs.
This closes block width as the missing large general acceptance gain.

## Artifact sufficiency

The retained corrected corpus root is:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-dflash-aux-v8-corrected5-v6b-4gpu-20260710T040000Z
```

Its four shards contain 384 `qwen36_eagle_sequence_v2` samples. Each sample has
160 target-owned positions, target continuation IDs, and the corrected five
feature taps with shape `[160,5,5120]` in BF16. Prompt IDs are generated,
disjoint engineering tasks such as `incident-log-triage`; they are not the
fixed benchmark prompts.

These artifacts support source checkpoint replay at any block width that fits
the retained continuation. They do not provide native GGUF decoder inputs or
native draft logits. Therefore they are sufficient for the source-BF16 width
and attention-contract decision, but not same-trace native Q8/F16-KV parity.

The only retained native activation fixture is B=6 and comes from a different
prompt and target runtime:

```text
data/qwen27-q6k-m6-top1-real-fixture-20260713.json
```

It is referenced in the report as unmatched implementation evidence only. No
native B=9/B=16 comparison was fabricated from unlike traces.

## Implementation

`scripts/evaluate-qwen27-dflash-width-oracle.py`:

- samples anchors using B=16 eligibility, then evaluates every width at those
  exact same anchors;
- reuses the established reconstruction and DFlash forward semantics from
  `scripts/train-qwen27-dflash-offline.py`;
- runs source z-lab BF16 draft weights with a BF16 target LM head;
- evaluates upstream `public-noncausal` and repaired `endpoint-mixed`
  causal-SWA/full-noncausal attention;
- records target IDs, first-five predicted IDs, exact-prefix acceptance,
  streamed full-logit deltas, and paired acceptance effects;
- labels output as offline diagnostic, not throughput and not LocalMaxxing
  eligible.

The source feature mapping remains fixed at post-layer `[1,16,31,46,61]`.
No arbitrary layer sweep was performed.

## Exact run identity

Command:

```bash
set +u
source /opt/intel/oneapi/setvars.sh --force
set -u
export ZE_AFFINITY_MASK=0
export ONEAPI_DEVICE_SELECTOR='level_zero:*'
/home/steve/.venvs/vllm-xpu/bin/python \
  scripts/evaluate-qwen27-dflash-width-oracle.py \
  --anchors 512 \
  --device xpu:0 \
  --out data/qwen27-dflash-width-oracle-20260713/source-bf16-512.json
```

Identity:

- draft: `/mnt/fast-ai/llm-cache/hf/manual/z-lab--Qwen3.6-27B-DFlash`;
- draft weights: BF16;
- target embedding and BF16 LM head: webhie Qwen3.6-27B int4 AutoRound,
  snapshot `f5750c90b3776db658594df5fe8051098226dd8e`;
- widths: B=6, B=9, B=16, meaning 5, 8, and 15 predicted rows;
- attention: public non-causal and endpoint-mixed;
- common anchors: 512;
- anchor-set SHA-256:
  `b69e6c17146fbe341f5c42d6094bbf194d5e7e16a36f9a845c0f51d8523b5497`;
- seed: `20260713`;
- max context: 160;
- device: B70 GPU0;
- DFlash forwards: 3072;
- diagnostic elapsed wall: `47.7316 s`;
- result SHA-256:
  `de661122089cbeca52bdf19784d6b248fe028dc34f1af1a4f3f292322e5f3fd2`.

## Acceptance result

| source attention | block | accepted drafts | visible tokens/step | full block accepted |
|---|---:|---:|---:|---:|
| public non-causal | 6 | 1.9668 | 2.9668 | 12.30% |
| public non-causal | 9 | 2.1133 | 3.1133 | 3.12% |
| public non-causal | 16 | 2.1582 | 3.1582 | 0.20% |
| endpoint-mixed | 6 | 1.9980 | 2.9980 | 13.28% |
| endpoint-mixed | 9 | 2.1543 | 3.1543 | 3.52% |
| endpoint-mixed | 16 | 2.2559 | 3.2559 | 0.39% |

Paired endpoint-mixed effects relative to B=6:

| comparison | mean accepted gain | 95% normal interval | improved / worsened anchors | first-five ID changed anchors |
|---|---:|---:|---:|---:|
| B=9 vs B=6 | +0.1562 | +0.0940 to +0.2185 | 46 / 10 | 114 / 512 |
| B=16 vs B=6 | +0.2578 | +0.1512 to +0.3644 | 46 / 10 | 128 / 512 |

The identical improved/worsened counts do not imply identical anchors or
prefix sizes; B=16 adds a longer accepted tail on some already improved
anchors.

For endpoint-mixed B=6 versus B=16, 635,699,200 first-five logit values were
compared. Mean absolute delta was `0.12650`, RMS delta `0.19749`, and maximum
absolute delta `7.3125`. Top-1 agreement by row was:

```text
row 1  99.02%
row 2  97.46%
row 3  96.48%
row 4  94.73%
row 5  83.59%
```

This directly confirms the expected bidirectional width effect while bounding
its useful acceptance impact.

## Attention-contract result

Endpoint-mixed versus public non-causal changed mean visible tokens by:

- B=6: `+0.0312`, interval `-0.0038` to `+0.0663`;
- B=9: `+0.0410`, interval `-0.0096` to `+0.0916`;
- B=16: `+0.0977`, interval `+0.0168` to `+0.1785`.

The full logits and IDs differ, especially in later B=16 rows, but the
acceptance effect is much smaller than the `0.5`-token gap that would justify
treating attention semantics as the missing general strict-acceptance win.

## Repeat stability

An independent 128-anchor run used the same seed and therefore overlaps the
first 128 sampled anchors of the 512-anchor run. Across six mode/width cells,
first-five IDs differed on 18 of 768 anchor-cell comparisons and accepted
prefix differed on 2 of 768. This is small XPU BF16 near-tie variability, not
bitwise determinism. It did not change the width decision. Both reports retain
the exact per-anchor IDs so future majority-repeat logic can audit the near
ties rather than hiding them.

## Decision and next action

Do not move the general lane from B=6 to B=16 for acceptance alone. Earlier
native timing measured B=6 target verify/draft medians of `58.189/10.515 ms`,
versus `138.877/69.085 ms` at B=16. The source oracle finds only `8.6%` more
visible tokens, while those prompt-specific native components increase by much
larger factors. B=9 is also not rescued by its `5.2%` visible-token gain.

Native source-parity capture is now lower priority. It would require a guarded
same-trace native injection/capture path for B=9 and B=16, and the protected
llama.cpp build/server was active on GPU3. Because the source checkpoint itself
does not show a large general B=16 gain, disturbing that lane to capture wider
native blocks would not be justified now.

Continue optimizing the B=6 native complete cycle: packed Xe2 target verifier,
five-layer draft projection fusion, device-resident top-1/handoff, and replay.
A routed wider block remains reasonable only for a workload family that proves
both substantially higher acceptance and favorable complete-cycle economics.
