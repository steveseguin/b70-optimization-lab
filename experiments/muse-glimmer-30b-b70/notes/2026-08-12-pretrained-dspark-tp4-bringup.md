# Pretrained DSpark TP4 bring-up and confidence sweep

Date: 2026-08-12

## Intent

Test the public, already-trained Muse Glimmer DSpark assistant as an acceptance-side complement to the exact SYCL kernel stack. No drafter training was performed.

## Fixed benchmark identity

- verifier: Muse Glimmer 30B BF16, TP4 on devices `0,1,2,3`;
- single request, `parallel=1`, greedy, prompt cache disabled;
- 256 generated tokens for prose, code, and JSON;
- arithmetic mean of the three per-request decode rates;
- exact kernel flags: primitive cache, binding cache, and BF16 subgraph conversion cache enabled; oneMKL/direct experiments and SYCL graphs disabled;
- expected output hashes: prose `914f754747d0edaa`, code `cf2b2c4fd9e36fe5`, JSON `4f813a9706abc163`.

## Artifact and source identity

- published checkpoint: `DaoCloud/Muse-Glimmer-30B-DSpark` at immutable revision `0609ed2c925f68ab4aed36ed485797767d13b0e4`;
- converted BF16 GGUF: `/mnt/usb-models/Muse-Glimmer-30B-DSpark/Muse-Glimmer-30B-DSpark-BF16.gguf`;
- GGUF SHA-256: `a0d4cd570b4d514f451a43df50429e152d1591232a00a67d4e2234b462bf75dc`;
- converter source commit: `563600474` (`convert_hf_to_gguf: support Muse Glimmer DSpark`);
- exact kernel base source commit: `9e019d206`.

## TP4 compatibility work

The first server attempt failed because `markov_w2.weight` was mirrored. Its result was therefore a mirrored full-vocabulary bias that could not be added to the verifier's axis-0-sharded logits. The correct layout is axis 1 for the `[rank, vocab]` matrix, producing an axis-0-sharded bias.

The next failure was the dependent `ARGMAX` in the Markov chain. Each device held only a vocabulary shard, so a local argmax was not a global token ID. The correctness-first implementation segments the meta graph after each sharded argmax, computes a global last-maximum index, and mirrors that small result before the next `GET_ROWS` node. The current generic fallback gathers the sharded F32 logits to the host. It is functionally correct but is explicitly a prototype; the performance follow-up is a device-side maxloc collective over tiny value/index pairs.

Bring-up also exposed an independent bug in the exact BF16 conversion cache: a recycled activation address could represent different shapes inside one DSpark subgraph. The cache key now includes pointer, element count, and source type. The old pointer-only key asserted on a shape collision.

## Results

The adjacent DFlash control was `40.343 / 62.652 / 69.794`, mean `57.596` t/s. It drafted/accepted `1150/173`, `760/201`, and `672/207`.

| DSpark confidence | Prose | Code | JSON | Mean t/s | Verdict |
|---:|---:|---:|---:|---:|---|
| 0.00 | 41.204 | 68.241 | 71.038 | 60.161 | best; +4.45% vs adjacent DFlash |
| 0.10 | 40.267 | 68.396 | 70.231 | 59.631 | exact, slower than 0.00 |
| 0.20 | 40.540 | 66.449 | 68.620 | 58.536 | exact, slower |
| 0.30 | 40.238 | 67.317 | 66.987 | 58.181 | exact, slower |
| 0.40 | 38.161 | 65.501 | 66.438 | 56.700 | exact, below control |
| 0.50 | 37.624 | 62.852 | 62.376 | 54.284 | exact, rejected |

At confidence 0.00, DSpark drafted/accepted `1236/168`, `723/203`, and `733/204`. All three output hashes matched the fixed reference. Confidence truncation increased the displayed acceptance percentage but reduced accepted-token yield and throughput; keep `p_min=0` for this checkpoint and workload.

## Durable evidence

- DFlash control and original startup failure: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dspark-dflash-ab-20260812.jsonl`, SHA-256 `5eea499b0ff46f76f9883280acc16e5b819f132ad5d1cbf19a43a8b2e3e47a44`;
- TP retry history and successful 0.00 row: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dspark-p0-retry-20260812.jsonl`, SHA-256 `bd5437671fe7db0354b8684780aa083b256c83284535a0fd1ab822a7bf5e6743`;
- confidence sweep: `/mnt/fast-ai/bench-results/muse-glimmer-30b/sweeps/dspark-confidence-20260812.jsonl`, SHA-256 `156064a651a00afaa9fbb1583851da0fecafd5e6658d18c05b90a7006ddcf470`;
- tracked sweep configurations sit beside this note under `sweeps/`;
- production was restored after the sweep and passed the full code and vision health canaries in `data/muse-health-20260812-dspark-confidence-restore.json`.

## Decision and next action

Keep the pretrained DSpark path and confidence 0.00 as a verified positive experiment, but do not present 60.161 t/s as close to the century goal. Implement the asynchronous SYCL maxloc collective to remove the host synchronization prototype, measure that delta, then combine only exact gains with the remaining target-side kernel/structural work.
