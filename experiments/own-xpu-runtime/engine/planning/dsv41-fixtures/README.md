# dsv41 format fixtures — IQ2_XXS decode

Bounded gap #2 from
[../deepseek-v41-capability-table.md](../deepseek-v41-capability-table.md).
CPU-only; no GPU, no model admission, no engine changes.

## Files

- `iq2xxs_tables.h` — normative format tables (256-entry codebook, 128-entry
  sign table, 8-entry sign mask). Provenance: ggml/llama.cpp `ggml-common.h`
  @ `7d7f02875` (MIT), format design I. Kawrakow (ik_llama.cpp, MIT).
  Fixture data, not engine-shipped code.
- `iq2xxs_decode.hpp` — Own Xe independent block decoder
  (`dsv41::dequantize_iq2_xxs`), written from the format contract:
  66-byte blocks / 256 elements; fp16 super-scale; per 32-element group an
  8-bit codebook index and 7-bit sign index per 8-element sub-block, 4-bit
  sub-scale in the high word.
- `test_iq2xxs.cpp` — differential gate vs the reference
  `dequantize_row_iq2_xxs` compiled from the pinned llama.cpp clone
  (advisory comparison execution, per the objective's reference rules).

## Build and run (this host)

```bash
icpx -O2 -std=gnu++17 -no-pie -fiopenmp -o /tmp/test_iq2xxs test_iq2xxs.cpp \
  /home/steve/src/llama.cpp-dsv41-20261108/build-jit/ggml/src/libggml-base.a
export LD_LIBRARY_PATH=/opt/intel/oneapi/compiler/2026.1/lib:$LD_LIBRARY_PATH
/tmp/test_iq2xxs   # optional arg: path to any GGUF shard containing IQ2_XXS
```

The reference archive was Intel-compiled; `g++` linking fails on
`_intel_fast_memset`/`__kmpc_*`. The fixture never links against or modifies
the engine.

## Result (2026-11-08, this host)

```text
OK   synthetic x4096: 4096 blocks, 1048576 values bit-exact
real tensor: blk.2.ffn_down_exps.weight (4529848320 elems)
OK   real gguf x512: 512 blocks, 131072 values bit-exact
FIXTURE_PASS
```

Real bytes came from the sha256-verified local
`UD-IQ2_XXS/…-00002-of-00006.gguf` (owner-selected artifact).

## Boundaries and next

- Decode correctness only. The packed `gemv_row` fixture (dot without full
  expansion, fixed reduction order) is the follow-on task and the entry to
  the IQ2_XXS device-kernel campaign (scoreboard IQ2_S = 9% of roofline).
- Remaining missing formats from the capability table: IQ1_S, IQ2_XS, Q2_K
  (backbone), IQ4_NL_4_4 (dspark). Same fixture pattern applies: extract
  normative tables, independent decode, differential gate on real bytes.
