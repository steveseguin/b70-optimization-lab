# dsv41 format fixtures — dequant + packed-dot gates

Bounded gaps #1/#2 from
[../deepseek-v41-capability-table.md](../deepseek-v41-capability-table.md).
CPU-only; no GPU, no model admission, no engine changes.

## Files

- `iq2xxs_tables.h`, `iq2xs_tables.h`, `iq1s_tables.h` — normative format
  tables. Provenance: ggml/llama.cpp `ggml-common.h` @ `7d7f02875` (MIT),
  format design I. Kawrakow (ik_llama.cpp, MIT). Fixture data, not
  engine-shipped code.
- `iq2xxs_decode.hpp`, `q2k_decode.hpp`, `iq2xs_decode.hpp`,
  `iq1s_decode.hpp` — Own Xe independent block decoders, written from the
  format contracts (block sizes 66/84/74/50 bytes per 256 elements).
  `q2_K` additionally has a second fp16 field (`dmin`).
- `iq2xxs_gemv.hpp` — packed row-dot contract: per term
  `t = (db*code)*sign`, then `acc = fmaf(t, x[i], acc)`, natural block/lane
  order, one fp32 accumulator. Device kernels must document any reduction
  reordering against this reference.
- `gguf_locate.hpp`, `test_common.hpp` — shared GGUF tensor locator
  (two-pass: data section starts only after the LAST tensor info) and the
  differential gate body.
- `test_iq2xxs.cpp`, `test_q2k.cpp`, `test_iq2xs.cpp`, `test_iq1s.cpp`,
  `test_gemv_iq2xxs.cpp` — gates vs the reference `dequantize_row_*`
  compiled from the pinned llama.cpp clone (advisory comparison execution).

## Build and run (this host)

```bash
ICPX=/opt/intel/oneapi/compiler/2026.1/bin/icpx
GGML=/home/steve/src/llama.cpp-dsv41-20261108/build-jit/ggml/src/libggml-base.a
$ICPX -O2 -std=gnu++17 -no-pie -fiopenmp -fp-model=precise -ffp-contract=off -o /tmp/test_q2k test_q2k.cpp $GGML
$ICPX -O2 -std=gnu++17 -no-pie -fp-model=precise -ffp-contract=off -o /tmp/test_gemv_iq2xxs test_gemv_iq2xxs.cpp
export LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.1/lib:$LD_LIBRARY_PATH
/tmp/test_q2k   # optional arg: path to any GGUF shard holding the type
```

`-fp-model=precise -ffp-contract=off` is **load-bearing**: icpx -O2
otherwise reassociates the accumulation and the packed-vs-two-phase
comparison wobbles at ulp level depending on surrounding code. The gemv
contract is only defined under deterministic FP codegen; the device kernel
pins its own reduction order instead.
The Intel-compiled reference archive needs `icpx -fiopenmp` at link time
(`_intel_fast_memset`/`__kmpc_*`). Fixtures never link against or modify
the engine.

## Results (2026-11-08, this host, finite-only gates)

```text
test_iq2xxs      OK synthetic x4096 + real x512 bit-exact   FIXTURE_PASS
test_q2k         OK synthetic x4096 + real x512 bit-exact   FIXTURE_PASS q2_K
test_iq2xs       OK synthetic x4096 + real x512 bit-exact   FIXTURE_PASS iq2_xs
test_iq1s        OK synthetic x4096 + real x512 bit-exact   FIXTURE_PASS iq1_s
test_gemv_iq2xxs OK synthetic + real dot bit-exact          FIXTURE_PASS gemv_iq2xxs
```

Real bytes: sha256-verified local UD-IQ2_XXS shard 2 (owner-selected
artifact); tensor located per the `gguf` python package's independent
offset cross-check.

## Gate-hardening lessons (do not regress)

1. **NaN masking**: random synthetic blocks with random fp16 scales produce
   NaN payloads; NaN==NaN bitwise "passes" are meaningless. Synthetic gates
   force finite scales (exp 5, random mantissa) and *reject* any non-finite
   output.
2. **Locator off-by-remaining-infos**: computing the GGUF data start at the
   matched tensor's info position (instead of after all infos) shifted the
   "real" window by 19,616 bytes into garbage that *still passed bit-exact*
   (both decoders read the same wrong bytes). Cross-check real-window
   offsets against an independent parser.
3. **Accumulation reassociation**: per-term products were bit-identical
   while the dot differed — icpx reorders reductions at default fp-model.
   Fixed flags above.

## Additional gated units (same pattern)

| Fixture | Gates | Result |
| --- | --- | --- |
| `test_hc_sinkhorn.cpp` (+ `hc_sinkhorn.hpp`, `data/hc_sinkhorn/`, `gen_hc_ref.py`) | HC split+Sinkhorn-20, real blk.0 hc_attn scale/base | f64 1.1e-16, f32 1.4e-7 |
| `test_route_gate.cpp` (+ `route_gate.hpp`, `data/route/`, `gen_route_ref.py`) | sqrtsoftplus top-6, bias-select, norm x1.5, engineered tie row | f64 1.4e-16, sets exact |
| `test_ops_misc.cpp` (+ `ops_misc.hpp`, `data/ops/`, `gen_ops_ref.py`) | SwiGLU clamp 10; engram gate; YaRN table + fwd/inverse rotation | f64 <= 1.1e-14 (rope exact 0.0) |
| `test_engram_hash.cpp` (+ `engram_hash.hpp`, `data/engram/`, `gen_engram_ref.py`) | prime chain re-derivation + 24,576 hash ids | bit-exact (int) |
| `test_engram_gather.cpp` (+ `q5k_decode.hpp`) | Q5_K decode differential + 8-row gather from the real 135.2 GB shard-6 table at hash ids | bit-exact |
| `test_attn.cpp` (+ `attn_ops.hpp`, `data/attn/`, `gen_attn_ref.py`) | sparse-attn core (sink, -1 skip, zero-row); compressor pool+RMSNorm; indexer score/topk/candidates; window ring idxs | f64 <= 8.9e-16; ints exact |

Torch reference generators run with the host `~/.venvs/vllm-xpu` python
(torch 2.11, CPU) plus the throwaway `/tmp/ggufcheck` venv's `gguf` on
PYTHONPATH; regenerate dumps into `data/` only when the pinned reference
revision changes.

| `test_mxfp4` | MXFP4 (39) decode | bit-exact synthetic + real dspark expert bytes |

| `test_engine_types` | engine `iq3::decode` Q2_K/IQ2_XXS/IQ2_XS/IQ1_S/MXFP4 | bit-exact vs reference (three-way with per-type fixtures) |
| `test_directory_v41` | `geometry_v41_from_directory` on real shard directory (`data/dsv41-directory.tsv`, regenerate with `dump_directory.py`) | derives exact admitted geometry; tamper rejected |

| `test_plan_v41` | `plan_v41.hpp` decode-step builder vs real directory | all tensors consumed (indexer wk/k_norm residue on non-kv-source layers documented); op census matches reference (80 hc_mixes, 40 sparse_attn, 4 compress, 8 index, 2 engram, 3 MTP captures); shared-cache references verified |

| `test_ops_v41` | engine host kernels (`ops_v41.hpp`) vs fixture impls | sparse_attn/route/swiglu/window/rope/gemv_grouped bit-exact or EXACT; engram/hc within 1-2 bf16 ulp |

## Boundaries and next

- Remaining format gap: IQ4_NL_4_4 (dspark spare only — defer until the
  dspark path is scheduled). IQ2_S decode exists in the engine
  (packet62/math.hpp) and needs the same differential gate when its kernel
  campaign starts.
- gemv contract is defined and gated for IQ2_XXS; the SYCL device kernel
  (32-lane strided, tree32 per `kernels/api.hpp`) is the next campaign step.
- Operator gaps from the capability table (HC Sinkhorn-20, HCA/CSA, route
  logits+sigmoid top-16, engram hash/gather, output LoRA) each follow the
  same pattern: independent CPU implementation + differential gate vs
  reference semantics from the official `model.py`.

## CPU reference runner (corrected 2026-11-09)

`cpu_run_v41.cpp`: full reference forward (f32, OpenMP, weight-stationary
prefill) over the real UD-IQ2_XXS backbone mmap'd from NVMe plus the Q5_K
engram table (shard 6), engram prep tables generated by the official
`engram.py` code path against the real tokenizer (compressed vocab 99092,
asserted).

**The 2026-11-08 "validated" label was wrong.** Four matching greedy tokens
hid four structural errors (FFN pre-mix threading, transposed `comb` in
`hc_post`, compressed-row visibility in the prompt pass, layers 37-39 treated
as ratio 0). They were found and fixed on 2026-11-09 against official
`model.py` and per-layer llama.cpp tensor dumps; see
[the bring-up note](../../../notes/2026-11-09-dsv41-device-load-host-memory.md).

Current standing against llama.cpp 7d7f02875 (CPU build, same GGUF bytes),
prompt 1 ("Say hello in one sentence.", 36 chat-template tokens):

- every layer checked in isolation from llama.cpp's own input: no tensor over
  4 % (per-token median) on any of the 40 layers or the head;
- forced along llama.cpp's first nine tokens: same top token at 8 of 9
  positions, the ninth a near tie (0.38 vs -0.22 logits);
- the runner's prompt pass and step-by-step pass agree exactly.

This is agreement within llama.cpp's arithmetic noise (its CPU backend
quantizes activations to 8 bits inside quantized matmuls), not bit identity.
Evidence: `../../../data/dsv41-bringup-20261109/`.

Build/run (`ids.txt` = chat-template token ids, one per line):

```bash
$ICPX -O3 -fiopenmp -std=c++20 -DOWN_RT_HOST_ONLY -I src -I planning/dsv41-fixtures \
  -o /tmp/cpu_run_v41 planning/dsv41-fixtures/cpu_run_v41.cpp
LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/latest/lib OMP_NUM_THREADS=16 \
  /tmp/cpu_run_v41 ids.txt N out.txt 4096 [engram.gguf] [forced_ids.txt] [state_dump.bin]
```

Environment: `OWN_TRACE=path` (+`OWN_TRACE_STEPS`) decode-step trace for the
device gate; `OWN_PDUMP=path` prompt-pass tensors under llama.cpp's names;
`OWN_LLAMA_INJECT=path` teacher-force each layer from llama.cpp
(`tools/dsv41_llama_inject.py`); `OWN_HC_LEGACY=1` / `OWN_COMB_LEGACY=1`
restore two of the old errors for A/B only; `OWN_KV_BF16=1` stores KV rows
as BF16 like the engine; `OWN_CONTRACT=1` sums in the device executor's
order (build with `-fp-model=precise -ffp-contract=off`).

## Device runner (2026-11-09)

`own_run_v41.cpp` + `src/stage2/packet3/backend/backend_sycl_v41.hpp`: the
model on the cards. `OWN_PROMPT=ids.txt own_run_v41 - N out.txt` reads a
prompt (token ids) and writes the answer with no CPU reference involved;
`own_run_v41 state.bin N out.txt` continues from the reference's state dump
for the trace gate. Usage and environment are in the file header. Loader rules (one SYCL context per card, free-memory check,
bounded upload) exist because the first version froze this 15 GiB host four
times; do not relax them. Gate: `tools/dsv41_trace_diff.py ref.trc dev.trc`.
Whole model on six cards since 2026-11-09 17:07 EST (165 GB in 20 s, 9.0
tok/s since 18:10). Activations are f32 by default (`-DOWN41_ACT_BF16` for the first,
BF16-activation build); KV rows are BF16. With f32 activations all 40 greedy
tokens of prompt 1 equal the reference run with `OWN_KV_BF16=1`.

## SYCL probe (2026-11-09)

`sycl_probe_gemv.cpp`: device gemv over real IQ1_S/IQ2_XXS tensor slices on
Arc Pro B70. Device enumeration requires `libumf.so.1` on the loader path
(oneAPI 2026.1 setvars gap: `LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib`).
Six devices visible (six single-tile cards x 31.9 GiB; an earlier note here said twelve tiles). Naive one-row-per-item
kernel: correct vs host (max rel err accumulation-order noise), 6.6 GB/s —
latency-bound baseline only; production kernels need coalesced block loads
(cf. packet10 expanded-split4 winners on the SC117 lane).

## Device gates (2026-11-09) — ALL PASS on Arc Pro B70

`src/stage2/packet3/kernels/sycl_v41.hpp`: SYCL kernels for the full v41
decode op set (gemv lane_dot/tree32 SG32, rope pairs, swiglu, prob_scale,
moe_combine, hc_pre/post/mean/mix+sinkhorn, window_append, sparse_attn,
compress_pool, indexer score+topk, engram_gate, gemv_grouped). Mul/add paths
bit-exact vs the ops41 host anchors; exp/sigmoid paths within +-1 bf16 ulp.
Gate: `planning/dsv41-fixtures/test_ops_v41_device.cpp` (19 checks):

```bash
$ICPX -fsycl -O2 -std=c++20 -fp-model=precise -ffp-contract=off \
  -I planning/dsv41-fixtures -I src \
  planning/dsv41-fixtures/test_ops_v41_device.cpp -o /tmp/test_ops41_dev
LD_LIBRARY_PATH=/opt/intel/oneapi/umf/latest/lib:/opt/intel/oneapi/compiler/latest/lib \
  ONEAPI_DEVICE_SELECTOR=level_zero:0 /tmp/test_ops41_dev
```

Gotcha recorded: this B70 rejects non-uniform work-groups; pad global ranges
to a multiple of the group size and guard inside the kernel.
