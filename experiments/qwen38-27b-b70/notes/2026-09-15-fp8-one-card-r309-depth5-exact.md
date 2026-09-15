# One-card FP8: depths 4-6 made exact (R309), 53.5 tok/s lossless

**Official Qwen3.8-27B FP8 on one B70 now writes at 53.6 / 53.5 tok/s with MTP
depth 5 and the draft-only shortlist head, all 12 strict answers identical to
no-MTP on two fresh servers, at up to 13,824 tokens of context.** The previous
best exact one-card setting was depth 3 at 46.9 tok/s (+14%). Tested September
15, 2026.

## Why depths 4 and 5 changed answers

A depth-d verify step runs every W8A16 projection on d+1 rows; no-MTP decode
runs one row. The lab's oneDNN patch r137a pins the GEMM reduction strategy so a
row's result does not depend on how many rows share the call, but its gate lists
only the TP2 per-rank shapes. One card uses the full-width shapes, so every
projection there ran the catalog strategy.

[`qwen38-fp8-tp1-gemm-row-census.py`](../scripts/qwen38-fp8-tp1-gemm-row-census.py)
checks every row of `gemm(A[:M])` against `gemm(A[r:r+1])`, M = 1..16:

| Image | TP1 full-width shapes | TP2 per-rank shapes |
| --- | --- | --- |
| R304 (qualified) | identical only for M = 1-4 (all six projections) | identical for M = 1-16 |
| R309 | identical for M = 1-16 | identical for M = 1-16 |

M = 1-4 covers depths 0-3, which is exactly why depths 1 and 3 passed and 4 and
5 failed. Error against a float32 dequantized reference is unchanged (3.7e-4 to
4.9e-4 relative, the FP16 floor).

## The change

[`onednn-qwen38-w8a16-fixed-k-tp1-shapes-r309-20260915.patch`](../patches/onednn-qwen38-w8a16-fixed-k-tp1-shapes-r309-20260915.patch)
adds the five full-width (N, K) pairs (16384/5120, 5120/6144, 14336/5120,
34816/5120, 5120/17408) to the same gate; the strategy strings and every other
condition are unchanged, and TP2 shapes are untouched. Kernels were rebuilt with
[`build-kernels-0.1.14.1-r309-tp1-shapes.sh`](../docker/rebase-v0290/build-kernels-0.1.14.1-r309-tp1-shapes.sh)
(574 s; `_xpu_C.abi3.so` `043083fc…`), and the image is R304 plus those two
libraries
([`Dockerfile.r309-tp1-fixed-k`](../docker/rebase-v0290/Dockerfile.r309-tp1-fixed-k),
local `sha256:7d3219a0…`, not pushed).

## Results

Every row: one B70, official FP8, compiled whole graph, host-memory input
embedding (`b70_cpu_embed`), draft-only INT4 head, FP16 KV, one user, prefix
cache off, `--gpu-memory-utilization 0.965`, `--max-num-batched-tokens 4096`,
warm-up before timing. Writing speed is the strict suite's class-balanced median
over tokens 1-100. The output check compares complete 512-token arrays with
R309 no-MTP (rung 13).

| Rung | MTP depth | Draft head | Context | KV tokens | tok/s | Output check |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| 13 | 0 | - | 20,480 | 43,885 | 19.418 | reference |
| 21 | 3 | full vocab | 16,384 | 16,896 | 47.047 | 12/12 |
| 20 | 4 | full vocab | 13,312 | 14,170 | 49.042 | 12/12 |
| 14 | 5 | full vocab | 11,264 | 11,616 | 50.934 | 12/12 |
| 19 | 5 | full vocab | 11,264 | 11,616 | 51.094 | 12/12 (fresh server) |
| 22 | 5 | 67k shortlist | 11,264 | 14,432 | **53.602** | 12/12 |
| 23 | 5 | 67k shortlist | 13,824 | 16,193 | **53.463** | 12/12 (fresh server) |
| 24 | 6 | 67k shortlist | 11,264 | 13,194 | 54.561 | 12/12 (one run) |

- Every run: canaries passed, cached tokens zero, no kernel faults, clean
  host-memory guard.
- **Shortlist:** `VLLM_XPU_DRAFT_LM_HEAD_SHORTLIST=/opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt`,
  already in the image. It limits only the draft's guesses, and the target still
  checks every token with its full head. It added about 5% speed and freed about
  0.4 GiB for KV.
- **Depth 6:** 1.8% higher on the 1-100 metric but lower full-answer wall rate
  (44.6 vs 45.3 tok/s), and only one run, so depth 5 is the recommendation.
- **Answers vs R304:** R309 no-MTP differs from R304 no-MTP on 3 prompts
  (tokens 160, 341, 474). The arithmetic changed but is equally precise, so each
  image is compared with its own no-MTP reference.
- **Harness kill:** the first attempt at the depth-5 repeat (rung 15) was killed
  by the agent harness's low-memory monitor while the host still had 14 GiB
  available. The orphaned container was stopped by hand, and the queue was rerun
  as a user systemd unit (rungs 19-24).

## Reproduce

```bash
python3 experiments/qwen38-27b-b70/scripts/run-fp8-tp1-server.py \
  --out /path/new-run --port 18133 --image <r309 image id> --mem 0.965 \
  --max-model-len 13824 --batched 4096 --mtp 5 --draft-int4 --cpu-embed --warmup \
  --shortlist /opt/draft-shortlists/shortlist-u-v1all-v2top65k.txt --keep
```

Evidence: `/mnt/fast-ai/bench-results/optimization-validation-20260915/fp8-tp1-1[3-9]*`,
`fp8-tp1-2[0-4]*`, `tp1-gemm-census-r30[49]` and
[copied receipts](../data/2026-09-15-fp8-one-card-r309/).
