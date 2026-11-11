# dsv41_step_budget.py: time against floor for one DeepSeek V4.1 Flash step

What it does: it reads the engine's `OWN_GPROF=2` profiles (one per card), the GGUF headers of the model and an
unprofiled run. For every kernel type it models the bytes each launch must read under the engine's six-card
slicing, and prints launches, us per launch, ms per step, bytes, the floor and the gap. It then sums the time by
role and by category, per card and for the slowest card, ranks the top recoverable items, and lists the structural
levers that move the floor itself. It also builds a prompt-block ledger and a "floor by block size" table.

It runs on the CPU only, with the standard library only. It reads the GGUF headers and never the tensor data.

```bash
cd experiments/own-xpu-runtime/engine/tools/perf
python3 -I dsv41_step_budget.py                       # b1 defaults: /home/steve/dsv41-work/runs/b1
python3 -I dsv41_step_budget.py --runs DIR --md out.md --json out.json
python3 -I dsv41_step_budget.py --bw 600 --xchg-sync-us 2.0 --distinct 70   # other floors / assumptions
python3 -I dsv41_step_budget.py --xwait xw.txt        # + who waits for whom (needs dsv41_xwait.patch)
```

## Inputs

| input | how it is made |
| --- | --- |
| `RUNS/dec_c{0..5}.log` | answer steps: `OWN_GPROF=2 OWN_GPROF_DECODE=1 OWN_GPROF_CARD=c`, prompt 1, about 48 tokens |
| `RUNS/pre_c{0..5}.log` | prompt read: `OWN_GPROF=2 OWN_GPROF_CARD=c` with **at least 2 answer tokens**. With 1 token, `own_run_v41` runs no answer step and prints no profile. When these logs have no kernel table, `--pre-fallback` is used (default: the e80 3K profiles of cards 0, 2, 4 and 5). |
| `RUNS/plain.log` | an unprofiled run; its tok/s gives the real step time |
| `--model` | the GGUF directory (shapes and quant types) |
| `--xwait FILE` | the output of `OWN_XWAIT=FILE` from the patched engine (`dsv41_xwait.patch`) |

## Model of the engine (round-18 defaults, `backend_sycl_v41.hpp`)

- Rows per card (`tp_setup`, equal weights, 16-row units). Expert and shared gate/up rows: 384 per card. Output-b,
  expert-down and shared-down rows: 848 or 864. Vocabulary rows: about 21,550. Engram rows: 5 x 5120 split.
- Heads: one-token steps keep whole groups of 8 heads (8, 8, 16, 8, 8, 16 per card, `hl[0]`). Prompt blocks of
  16 or more tokens split them 12, 12, 12, 12, 8, 8 (`hl[2]`).
- Every card reads these in full (replicated): q_a + kv, the router rows (F32 stored as 16-bit halves), the
  stream-mix rows `hc_*_fn` (24 x 20480 F32, read by `HcDotsRows`), the compressor and the indexer k.
- Bytes per row are `pk41::packed_row_bytes`. Q2_K expert rows are unpacked GGUF rows.
- The tool rebuilds the launch sequence of `tp_card_step` (engram after layer 0, the six phases per layer, then the
  head) and checks the launch counts it predicts against each profile. A mismatch, or a kernel name the model does
  not know, is listed at the end of the answer-step section.
- Prompt kernels are classified by name. Their bytes are the same tensors per block, with `--distinct` experts per
  (block, layer). Without measurements, uniform picks of 96 from 384 give about 85.

## Floors (all are parameters)

- Weights and activations: bytes / `--bw` (550 GB/s). The output head runs at 572 GB/s, so 550 is slightly
  conservative.
- Exchanges: `--xchg-sync-us` (2.5 us, one PCIe flag round trip) + bytes / `--link-gbs` (25 GB/s).
- Prompt blocks: max(bytes / bw, multiply-adds / `--macs`). The default is 5.7 T/s, the card's FMA peak.
- "Standalone floor": the same, but each launch costs at least `--launch-us` (2.2 us, an empty kernel). This shows
  what is reachable without fusing launches.

A floor is a structural ideal, not a prediction. The gaps column says where the time goes. Whether a lever is worth
its hours is decided with the strategy note's value check.

## Caveats

- Each card is profiled in its own run, and profiling adds 1.2 to 2.5 ms per step. The exchange times therefore
  come from six different runs, and none of them shows the real critical path. "gaps, real" is
  `real step - kernel sum`. It assumes kernel durations are the same with and without profiling.
- Attention bytes use the context of the profiled run (`--ctx`). At long context the attention and the index grow,
  and the ledger should be re-made from long-document profiles.
