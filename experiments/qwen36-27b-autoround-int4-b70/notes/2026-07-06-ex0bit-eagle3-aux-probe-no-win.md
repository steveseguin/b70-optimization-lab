# 2026-07-06: Ex0bit EAGLE3/DFlash aux-hidden acceptance probe is a no-win for Qwen27 AutoRound

## Classification

Diagnostic only. No LocalMaxxing submission. No throughput claim.

## Objective

Test whether an existing DFlash/EAGLE3 draft (`Ex0bit/Qwen3.6-27B-PRISM-EAGLE3`)
has enough fresh-prompt accepted-token depth to justify Intel/XPU endpoint
integration and lower-level kernel work for the current Qwen27 INT4 AutoRound
target.

Gate before backend work:

- strong pass: realistic-suite mean accepted prefix clearly above current MTP3
  (`~2.6 generated tokens / verifier step`), ideally `tau >= 4.5`;
- fail: draft acceptance is low on fresh target-owned output, meaning Hipfire /
  DFlash external numbers are not transferable to this target without training
  or adaptation.

## New/reused artifacts

- vLLM aux hidden dump patch snapshot:
  `patches/qwen36-27b-autoround-int4-b70/vllm-qwen27-eagle3-aux-hidden-dump-20260706.patch`
- Dataset builder update:
  `scripts/build-qwen36-eagle-dataset-from-dump.py`
  now emits `qwen36_eagle_sequence_v2` samples with
  `aux_hidden_states [T, 3, hidden]` when dump shards contain aux hidden states.
- New corpus runner:
  `experiments/qwen36-27b-autoround-int4-b70/scripts/run-eagle3-aux-corpus-v2-4gpu.sh`
- New offline acceptance evaluator:
  `scripts/evaluate-qwen27-ex0bit-eagle3-offline.py`

## Corpus

Collected no-spec target-owned generations with aux layers `1,31,60`, one
webhie Qwen27 AutoRound replica per B70:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-eagle3-aux-v2-chat-4gpu-20260706T193559Z
```

Corpus summary:

- 4 GPU shards, 24 prompts per shard, 96 prompts total.
- 160 output tokens per prompt, 15,360 rows total.
- `aux_rows_saved=15360`, `aux_bad_files=0`.
- `continuity_breaks=0`.
- Dataset rows are `qwen36_eagle_sequence_v2` with
  `hidden_state [T,5120]` and `aux_hidden_states [T,3,5120]`.

This is a target-owned fresh output corpus, not a warmed repeated-output or
history-accelerated measurement.

## Offline evaluator

Evaluator implements the local vLLM EAGLE3 forward math:

1. concatenate captured aux layers `[1,31,60]`;
2. apply Ex0bit `fc.weight (5120,15360)`;
3. run the one-layer Llama draft with target embeddings and Ex0bit draft
   weights;
4. apply the Ex0bit draft LM head;
5. for compressed, map draft IDs to target IDs using `target = draft_id + d2t`;
6. greedily compare proposal `t+1` against target-owned
   `sampled_next_token_ids[t+1]`.

This probes draft acceptance only. It is not endpoint speed and not a promoted
result.

## Results

Compressed Ex0bit checkpoint:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-offline-eval-all-20260706T194103Z/compressed-all-summary.json
```

- starts: `14784`
- mean accepted: `0.289908`
- acceptance histogram:
  - `0`: `11176`
  - `1`: `3017`
  - `2`: `510`
  - `3`: `77`
  - `4`: `2`
  - `5`: `2`
- step-1 exact: `3608 / 14784 = 24.40%`
- step-1 top-5: `8488 / 14784 = 57.41%`
- family means ranged roughly `0.2605` to `0.3166`; no family was close to a
  useful speculative depth.

Full-vocab Ex0bit checkpoint spot check:

```text
/mnt/fast-ai/bench-results/qwen36-27b-autoround-int4-b70/eagle-data/qwen27-ex0bit-eagle3-full-offline-eval-20260706T194235Z/full-maxstarts512-summary.json
```

- starts: `512`
- mean accepted: `0.291016`
- acceptance histogram:
  - `0`: `384`
  - `1`: `109`
  - `2`: `17`
  - `3`: `2`
  - `4`: `0`
  - `5`: `0`
- step-1 exact: `25.0%`
- step-1 top-5: `58.98%`

The full-vocab checkpoint matching compressed acceptance shows the failure is
not caused by Ex0bit's compressed `d2t` vocabulary; the draft itself is not
matched to this target/output distribution.

## Decision

Close direct Ex0bit EAGLE3/DFlash import as a no-win for the current
`webhie/Qwen3.6-27B-int4-AutoRound` target.

This does **not** disprove DFlash generally, and it does not disprove Hipfire's
code-prompt result. It only proves that this off-the-shelf PRISM EAGLE3 draft
does not provide useful acceptance on our fresh realistic Qwen27 target stream.

Do not spend endpoint/kernel integration effort on this checkpoint as-is.

## Next credible route

Use the now-working aux corpus infrastructure to train or adapt a
target-matched EAGLE3/DFlash draft:

1. start from Ex0bit full or compressed weights;
2. train on target-owned `qwen36_eagle_sequence_v2` aux samples;
3. evaluate offline acceptance before any endpoint work;
4. only integrate if mean accepted depth approaches or exceeds current MTP3
   and ideally moves toward `tau >= 4.5`.

If training cannot improve offline acceptance materially, return to target-side
kernel work or a different stronger draft source. Do not repeat config-only
DFlash endpoint runs on this checkpoint.
