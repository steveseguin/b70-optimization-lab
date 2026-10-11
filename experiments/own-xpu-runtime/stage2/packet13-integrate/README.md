# Packet 13 — performance integration of own-rt-iq3

October 11, 2026. CPU preparation complete; **no device executable was run**.
This extends our [packet 4](../packet4/README.md) in a separate directory,
preserving its source and failed BLAS-order comparison. It targets the separate
Unsloth Flash-Next UD-IQ3_XXS **quantized compressed version**, 48 layers,
512 experts, top 10, unchanged packed weights and full BF16 state/KV.

## What is wired

[main.cpp](main.cpp) retains packet 3's actual model graph: embedding and PLE,
four hyperconnection streams, 36 GDN and 12 QSA layers, routing, shared experts,
final mixer and the full output head. [performance.cpp](performance.cpp) binds
our existing measured kernels through the same Arena/Device owner as packet 4.
There is no imported runtime, server, graph capture, MTP or token reuse.

- Dense matrices use the complete `(grid, rows, columns, bank)` table from
  [rounds 2/3](../packet9-kopt4/dispatch.json): SG32 for the up-shaped winners,
  split4 for the down-shaped winners, and the constant-codebook variants where
  those won. Selection is by the table, not a blanket aspect-ratio rule.
  Unmeasured shapes retain the table's declared SG32 fallback; these are not
  represented as measured winners.
- Every MoE block has one gate/up launch across all ten selected experts,
  one down launch, and the measured ordered weighted epilogue: **three expert
  projection/mixture launches**. SiLU, status checks and shared-expert addition
  remain additional nonlinear work. Gate/up wait for routing; down waits for
  the intervening rounded activation. SG32 is the
  [round-4 expert winner](../packet9-kopt4/README.md#device-results--card-3-2026-10-11-045x-utc-boot-13858eef);
  split4 is not imposed on experts.
- [arithmetic.hpp](arithmetic.hpp) is the single selection/reference interface,
  version **`iq3-p13-r234-sg32-split4-bf16-v1`**. It reuses the kernel packets'
  reference trees and decoders, including separate FP32 multiply/add and
  adjacent-pair trees. CPU and native adapters take the same variant decision;
  packet 4's shared `core.hpp` supplies nonlinear reductions and BF16 casts.
  Fast math and contraction stay disabled. Source hashes bind these dependencies.

The [owner's arithmetic decision](../../../../notes/2026-10-11-iq3-arithmetic-authority-decision.md)
requires the oracle to adopt this frozen order. The old BLAS fixture is retained
in packet 4 and is not this packet's gate. Shared math does **not** establish
CPU/SYCL transcendental parity: exact device comparisons and fresh-process
repeats remain necessary. No output difference is silently accepted.

## Memory and placement

One card is a **layer-streaming correctness vehicle**. At each layer, stage
its dense/control tensors first. Read back the computed route IDs, validate
them, and copy the exact packed bytes for all ten selected slots into compact
banks; a separate device route table maps slots to those banks. Preserve the
original expert IDs/probabilities and their order. Gate and up share that route
table and activation; down retains separate activations for each slot. Duplicate
IDs are safe and remain separate slots. Release the layer's weights only after
all its events and hidden-state copies complete. The head is its own final
weight group and is released before the next token. First-layer-only mode may
retain its dense weights, but evicts/reloads selected banks at every new route.

The stage1 packet3-prep **CopyEngine** transfers at most **4 MiB** at a time
through one owned pinned slab per card. Each copy drains before the slab is
reused. Model slices are read-only, at most 4 MiB; no full host expert bank or
expanded weight shadow is built. Embedding and PLE read only requested rows.
This does not drop or control the OS page cache. Host file-cache and driver
memory still need coordinator admission.

[The checked memory plan](memory-plan.json), at context capacity 128:

| Placement | Owned request/workspace | Packed weights | Calculated peak device bytes |
| --- | ---: | ---: | ---: |
| One-card streaming | 352,001,192 | At most 528,476,160; head/final mixer is the largest group | **880,477,352** |
| Resident card 2, layers 0–23 | 312,217,840 | 26,165,134,080 | **26,477,351,920** |
| Resident card 3, layers 24–47 and head | 312,438,856 | 26,464,055,040 | **26,776,493,896** |

Each owner also has a 4,194,304-byte pinned host slab. These are allocation
calculations, **not device fit measurements**; the CLI enforces 30 GiB per
owner and records the actual owned peak. Context is bounded to 1,024 and the
window uses 128 for the frozen 87-token prompt plus seven further inputs.

Two-card `resident` is the existing **sequential 24/24 layer split**, with
ordered host-bounce handoffs. It removes repeated weight streaming and is the
resident speed configuration/control; it does not make both cards compute a
layer together. [TWO-CARD-TP.md](../TWO-CARD-TP.md) explicitly retains this
fallback. Its within-layer TP, peer transport and new reduction gates remain
separate, unmeasured work. This packet does not claim TP speedup or native fit.

## First-token capture and timing

[prepare.py](prepare.py) uses the oracle's frozen tokenizer module and first
`incident-retrospective` prompt. It checks the existing shard admission and
tokenizer header hash, writes the same 87 token IDs, and downloads nothing.
The CLI evaluates every prompt position through all layers, then emits up to
eight greedy token IDs. EOS ends generation normally; the eight-step diagnostic
then records incomplete coverage rather than manufacturing extra tokens.

For each generated step, `stepN/layer-XX.bf16` and `stepN/layers.jsonl` use the
oracle's `[1,4,2560]`, little-endian BF16 fixture format. Step 1 is the last
prompt position; steps 2–8 are its autoregressive continuation. Every step
records all 48 hashes. `timings.jsonl` contains site, layer and input-token
rows with wall ms, GEMV device ms, non-GEMV device ms and copy/readback wall ms.
Two-pass GEMVs include the interval from the first pass to the last, including
their gap. Device timing is **null on CPU**. Layer/token wall times include
eager synchronization, streaming and trace overhead; they are diagnostics,
not a cold-suite throughput headline. The final mixer/head contributes to
token totals, outside the 48 layer rows.

`passed` in a native window means completed diagnostic coverage, clean journal
and safe teardown. `real_model_qualified` stays false. Optional `--oracle`
requires a rebased root with `arithmetic.json`, `input.json`, `result.json`
and `stepN` fixtures. Its version and arithmetic source hashes must match the
build receipt. A fresh repeat compares all hashes and token IDs; a changed
repeat fails the window. The [runbook](WINDOW.md) supplies the exact commands.

## CPU evidence and reproduction

- **13 integration cases**, including six independent exact mini-model checks
  across one/three/eight generated tokens and both placements: 113 buffers and
  3,873 values per check, **23,238 compared values**. Also a fresh-process
  repeat, admission refusals, existing-output preservation and both 1,224-tensor
  plans. [Receipt](cpu-tests.json).
- **75 independent scalar/recursive-tree comparisons** across all 25 production
  shape/grid keys, sign/zero mutations, and rejection of an unknown shape.
  Four owner/event retirement cases, including 5,000 safe retirements.
- **17 mocked window tests**, with no journal or device access: eight-step
  coverage, both card commands, input/binary changes, missing fixtures, early
  EOS, fault and journal-loss latches, unsafe teardown, repeats and rejection
  of the old oracle identity.
- Real layer 0 runs all **87 prompt tokens on CPU**, saving 20,480 BF16 bytes.
  SHA256: `1b7f914b9ef1834a72aea1cb186b74c8dbecddff743fa529fe8e916e1352d82e`.
  [Receipt and retained bytes](evidence/real-layer/receipt.json): comparison
  pending oracle rebase, **not an oracle pass**.
- Host and SYCL compile/link pass. Only host binaries execute; `readelf`
  checks the host binary has no accelerator library dependency.
  [Build receipt](build-receipt.json) binds commands, sources and binaries.

From the repository root, using the installed environment:

```bash
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B \
  experiments/own-xpu-runtime/stage2/packet13-integrate/build.py --real-layer
```

The builder uses two build jobs and removes its own ignored `build/` by
default. `--keep-build` prepares the coordinator's executable and tokenizer
inputs. Existing coordinator windows or fault evidence cause refusal before
cleanup. Never remove those records just to obtain a new run.

[Closeout and remaining gates](CLOSEOUT.md). No device, server, Docker,
systemd, power, host-memory, driver, port 8188 or LTX operation occurred here.
