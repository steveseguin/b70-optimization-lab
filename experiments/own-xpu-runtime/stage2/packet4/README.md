# Packet 4 — one IQ3 executable

**CPU mini-model exact; real first-layer oracle gate FAILS. SYCL compile/link
passes; no device execution occurred.** This is original lab integration for
**Qwen3.8 Flash-Next UD-IQ3_XXS (Unsloth), quantized compressed version**, pinned
to the existing three-shard admission. It is not the FP8 model or a qualified
inference result. [Build receipt](build-receipt.json), [CPU tests](cpu-tests.json),
[real-layer comparison](evidence/real-layer/comparison.json), [device window](WINDOW.md).

`own-rt-iq3` is a C++20 CLI, built from the same sources with or without
`OWN_RT_HOST_ONLY`. It uses packet 2's read-only GGUF loader, packet 3's ordered
step and directory checks, and the stage 1 Device/Arena resource owner. It
accepts `--cards 1|2`, physical starting `--card`, token IDs from `--input`,
`--tokens`, and `--first-layer`. The Python helper reuses the CPU oracle's
Qwen35 regex/BPE tokenizer and authenticated GGUF vocabulary/merges. It writes
token IDs and raw vocabulary bytes; C++ prints generated IDs and joined text.
Prompts are already rendered by the oracle's frozen template. Arbitrary raw
user text needs that same template before tokenization; no chat server exists.

## What runs

Two cards use packet 3's **layer split**, with all 512 experts for layers 0–23
on the first owner and layers 24–47 on the second. This is not tensor-parallel
splitting of each expert. Exact packed residency is 26,165,134,080 and
26,464,055,040 bytes; all 1,224 census tensors have one physical weight owner
or host lookup backing. One card streams a layer at a time for the full model;
its first-layer test keeps that layer resident. No expert is pruned.

Each allocation uses the owner's census categories: weights, recurrent state,
full BF16 KV, scratch and pinned staging. The program caps requested device
allocations at 30 GiB/card; coordinator admission must separately establish
available memory and driver overhead. Copy slabs are 4 MiB/card and compound
operator scratch is 256 MiB/card. Upload progress is flushed after each chunk.
There is no expanded FP32 weight shadow. Real CPU mode evaluates only layer 0,
reading dense/expert rows in bounded tiles and only the ten selected experts.

The native dense and routed GEMVs call packet 2's kernels unchanged. The
`iq3::step_operator` extension in [kernels.cpp](kernels.cpp) lowers the remaining
packet 3 sites through that same Device/Arena/event API. Routing, stable top-10
selection, route descriptors, expert-input gather and sampling execute inside
device kernels. The original lab equations from packet 3 were adapted into
[core.hpp](core.hpp), using bounded scratch instead of heap containers. These
are serial bring-up kernels, **not performance-qualified kernels**.

Embedding and PLE lookup IDs are read back between segments; only the requested
packed rows are read and decoded, then uploaded. Cross-card handoffs use the
bounded host slabs. Every operation drains before the next segment. This is
**segmented eager execution, not whole-step capture**, peer-copy qualification,
or a host callback hidden inside a capture claim. The initial context bound
is 1,024 tokens, with BF16 K/V and state; MTP is absent.

Real GDN keeps the GGUF's `[3,16,D]` value-head order and uses `head % 16` for
its associated key. This is equivalent in layout to the oracle's explicit
unpermute/permute. The synthetic mini-model retains packet 3's head layout.
Packed GGUF controls and gains are consumed directly, without adding exporter
transforms again. GEMV reductions retain packet 2's 32 strided logical lanes.
The CPU oracle instead uses its pinned M1 BLAS arithmetic; matching its outputs
is an independent, strict gate, not something the loader or build establishes.

## Measured CPU evidence

The two-layer mini-model includes GDN, QSA, PLE, HC, routed/shared experts and a
full head. Its 113 buffers / 3,873 values agree bit-for-bit with packet 3's
independent Python reference, including greedy decoding, BF16 state and fresh
processes. One- and two-owner tests exercise explicit handoffs. Plan tests
check all real tensors, types/extents via the loader, and exact per-card census
sums. Receipt schema, rejection cases, five fake-child window guards, and four
event-retirement owner tests are included. No accelerator library is linked
to the host binary.

The real CPU check processed all **87 tokens** of `incident-retrospective`,
through **layer 0 only**, then wrote the last prompt position in the oracle's
`step1/layer-00.bf16` and `layers.jsonl` format: `[1,4,2560]`, BF16 little-endian.
It read 7,999,195,436 payload bytes across that complete prompt, with a maximum
individual read of 163,840 bytes. No other layer's payload was read.

- Actual: `4ff9760afe22c621ac750811071311a04fc47cdf25b1e46c145f7a538c4de587`
- Oracle: `6da649699aa3e71e052a7691ad8e9aa133b0e5d131d2062e37f45e8b946a84f4`
- **2,293 / 10,240 BF16 values differ.** Both 20,480-byte arrays are retained.

The mismatch is unresolved. Different GEMV and scalar transcendental arithmetic
are known identity differences, not a proven explanation of every difference.
The full-model/8-token quality gate is **not passed**. No speed or real generated
answer is claimed. `real_check.py` uses the sibling fixture when present; if
absent, it computes the packet1b-derived GGUF first-layer reference in its own
CPU process. It never substitutes a synthetic hash for the real model.

The first attempt stopped cleanly after 36 prompt tokens at the owner's old
4,096-event smoke limit. The integration adds `retire_completed_events()` for
fully drained eager segments. It refuses pending work and graph leases, retires
old handles, and preserves allocations/queue/context. Its implementation is
local to packet 4; the shared owner header adds only its declaration. No smoke
limit was removed and no busy resource is released. See [closeout](CLOSEOUT.md).

## Build and reproduce, CPU only

No installation, downloads or GPU commands are needed:

```bash
P=experiments/own-xpu-runtime/stage2/packet4
nice -n 19 ionice -c 3 env OMP_NUM_THREADS=2 \
  /home/steve/.venvs/vllm-xpu/bin/python -B "$P/build.py" --real-layer
```

This compiles host and SYCL targets with at most two jobs, executes only host
binaries, runs tests, and deletes its ignored `build/` scratch. `--real-layer`
repeats the bounded real-layer read and records the strict comparison, including
failure. Omit it to rerun only synthetic/plan/ownership/window tests. The build
receipt's `passed` means compilation and those CPU integration checks; it does
not override the real comparison. Add `--keep-build` when the coordinator is
preparing a device window. It preserves binaries and prepared inputs but still
runs **no GPU code**. [WINDOW.md](WINDOW.md) contains the subsequent commands.

Run directories contain `plan.json`, `progress.jsonl`, `census.json`,
`step1/layers.jsonl`, raw hidden fixtures and `receipt.json`. Failed comparisons
exit nonzero after safe teardown. A submission fault poisons the request and
never retries. SIGTERM requests cooperative drain; an undrained/error owner is
retained for its supervisor rather than abandoned. These are one-shot request
processes: failed request state is never reused, so no rollback/capture/replay
qualification is claimed.
