# Gemma 4 26B Q8 Candidate-Proof Profile

Date: 2026-07-01

Status: diagnostic captured, not a promoted performance result.

## Purpose

Measure whether the current MTP verifier path has enough exact candidate-match
structure to justify deeper LM-head work, such as candidate-vs-max proof,
accept-prefix verifier output rows, or a bonus-preserving row-adaptive verifier
graph. This is a host-side profile only; it does not change the promoted record
recipe or the LocalMaxxing headline.

## Workspace And Patch Trail

Active repo workspace:

```text
/home/steve/llm-optimizations
```

Active source checkout:

```text
/home/steve/src/llama.cpp-gemma-record-repro-c926
```

Patch artifacts:

- pre-edit source snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-candidate-proof-profile-preedit-source.patch`
- abandoned sampler-level attempt:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-candidate-proof-profile-sampling-abandoned-source.patch`
- final server-context diagnostic snapshot:
  `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260701-candidate-proof-profile-server-source.patch`

The sampler-level hook was abandoned because it did not sit at the right
acceptance boundary. The final diagnostic is anchored in
`tools/server/server-context.cpp`, in the default full-bonus MTP verifier path
after `common_sampler_sample_and_accept_n(...)` and before
`finish_speculative_accept(...)`.

## Build Environment Finding

The first build attempt failed at link/direct-run time with unresolved
Intel/SYCL/OpenMP runtime symbols and direct binary startup failed with
`libsvml.so` missing. This was a build environment issue, not a source syntax
issue: the oneAPI runtime environment was not sourced.

Working build/run form:

```bash
source /opt/intel/oneapi/setvars.sh --force
cmake --build /home/steve/src/llama.cpp-gemma-record-repro-c926/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

With the oneAPI environment sourced, `llama-server --version` reports llama.cpp
`c926ad098` built with IntelLLVM `2026.0.0`.

## Diagnostic Run

Run label:

```text
gemma4-q8-gpu0-candidate-proof-profile-smoke-20260701T204644Z
```

Command shape:

```bash
cd /home/steve/llm-optimizations
LLAMA_SPEC_VERIFY_CANDIDATE_PROOF_PROFILE=1 \
GPU_INDEX=0 PORT=18421 \
LABEL=gemma4-q8-gpu0-candidate-proof-profile-smoke-20260701T204644Z \
CANARY_REPEATS=16 MAX_TOKENS=64 REALISTIC_GATE=1 \
CTX_SIZE=32768 FLASH_ATTN=on GGML_SYCL_ENABLE_VMM=1 \
bash repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Evidence:

- summary:
  `data/gemma4-q8-gpu0-candidate-proof-profile-smoke-20260701T204644Z/summary.json`
- canary:
  `data/gemma4-q8-gpu0-candidate-proof-profile-smoke-20260701T204644Z/chat-canary.json`
- server stdout:
  `data/gemma4-q8-gpu0-candidate-proof-profile-smoke-20260701T204644Z/server.stdout.log`
- full server log:
  `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-candidate-proof-profile-smoke-20260701T204644Z.server.log`

Validity:

- fixed realistic cold suite: passed
- canary: 16 repeats / 64 rows, pass all
- `cached_tokens=0`: true for every measured request
- `MAX_TOKENS=64`: compact diagnostic only, not a full512 record claim
- median generated-token throughput field: `123.5397541201026 tok/s`
  across the compact run
- p10: `99.90946864628641 tok/s`
- mean: `120.71908291397222 tok/s`
- median TTFT: `178.57741698389873 ms`

Do not submit this to LocalMaxxing. It is not the promoted full512 gate.

## Candidate-Proof Counters

Final cumulative server line:

```text
server spec candidate proof: steps=452 verifier_rows=1802 draft_rows=1350 draft_match_rows=1102 match_pct=81.630 full_draft_matches=277 full_pct=61.283 bonus_rows_needed=277 full_accept_with_bonus=277 missing_sampled_rows=0 nonconsecutive_steps=0 first_mismatch_counts=(0:72, 1:48, 2:59, 3:273)
```

Interpretation:

- The sampled verifier rows are available and consecutive in this path:
  `missing_sampled_rows=0`, `nonconsecutive_steps=0`.
- Candidate draft rows match the sampled target token on `1102/1350` rows
  (`81.630%`), so there is real candidate-proof structure.
- Full draft matches occur on `277/452` steps (`61.283%`). Those are exactly
  the steps where the bonus row remains useful; a no-bonus design leaves too
  much throughput on the floor, matching earlier negative results.
- First-mismatch distribution is not trivial:
  `0:72`, `1:48`, `2:59`, `3:273`. A draft-candidate-only shortcut still
  needs an exact fallback for early mismatches, and cannot be promoted unless
  the target top token is still correctly determined.

## Decision

This diagnostic supports only a deeper exact verifier design. It does not
support another simple config screen or host-side sampler shortcut.

Promising but nontrivial follow-ups:

- an in-graph accept-prefix LM-head path that computes only the required output
  rows while preserving the bonus pipeline;
- candidate-vs-max proof only if the fallback still returns the exact target
  top token without paying the current full-row cost on most steps;
- verifier graph/MoE boundary reduction, since target/verifier work remains the
  dominant cost in the record profile.

Closed or deprioritized by this and earlier diagnostics:

- no-bonus row skipping;
- staged MTP3 split-bonus;
- late-head bonus as currently implemented;
- host-side candidate proof that avoids target top-token computation;
- more p_min / UBATCH / simple row-shape config roulette.
