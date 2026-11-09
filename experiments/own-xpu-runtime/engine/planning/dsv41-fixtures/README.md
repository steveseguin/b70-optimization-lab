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
