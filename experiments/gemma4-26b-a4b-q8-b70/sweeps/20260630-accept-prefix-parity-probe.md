# Gemma 4 26B Q8: Accept-Prefix Parity Probe

Date: 2026-06-30

## Purpose

Validate the exact accept-prefix invariant needed before attempting a real
backend accept-prefix verifier LM-head op. This is a parity/diagnostic patch,
not a throughput optimization and not a LocalMaxxing candidate.

The proposed future op would avoid computing later verifier/bonus output rows
unless earlier target top-1 rows matched the draft prefix. Before implementing
that in the backend, the server-side sampled-row semantics need to be proven
equivalent to the current sampler accept path.

## Source Patch

Source snapshot:

- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260630-acceptprefix-parity-source.patch`
- `patches/gemma4-26b-a4b-q8-b70/source-snapshots/20260630-acceptprefix-parity-source.diffstat`

Previous source snapshot to diff mentally against:

- `patches/gemma4-26b-a4b-q8-b70/20260630-after-perlayer-postnorm-fusion-source.patch`

Main new helper:

- `tools/server/server-context.cpp`: `verify_spec_accept_prefix_parity(...)`
- Runtime flag: `LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY=1`

The helper is default-off and fail-fast. When enabled on the normal full-bonus
path, it reconstructs the accepted token vector from backend sampled rows:

1. read sampled verifier rows `0..n_draft`;
2. append target sampled IDs until the first draft mismatch;
3. append the bonus row only when all draft rows matched;
4. compare that derived vector against `common_sampler_sample_and_accept_n(...)`.

The initial helper was too strict (`n_draft == 3`) and failed valid short-tail
steps (`n_draft=2`, `i_batch=3`). The validated helper accepts any full-bonus
shape with `n_draft > 0`, `spec_draft.size() == n_draft`, consecutive verifier
rows, and `spec_i_batch.size() == n_draft + 1`.

Harness metadata now records/passes the flag in:

- `repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh`
- `scripts/run-gemma4-26b-first-baseline.sh`
- `scripts/run-gemma4-26b-llamacpp-replica.sh`
- `scripts/build_gemma4_realistic_localmaxxing_payload.py`

## Validation

Built:

```bash
cd /home/steve/src/llama.cpp-gemma-record-repro-c926
set +u
source /opt/intel/oneapi/setvars.sh --force >/dev/null
set -u
cmake --build build-sycl-b70-aot-bmg-g31-q8reorder-vdr2 --target llama-server -j 8
```

The build succeeds. The UI asset step still prints the known local Node
`EBADENGINE` warning, then reuses the existing stamped UI assets and continues.

### Failed Attempts Kept For Reference

`gemma4-q8-gpu0-acceptprefix-parity-strict128-20260630T042402Z`

- Canary: 512/512 passed.
- Realistic suite: invalid/incomplete because the old helper rejected valid
  short-tail verifier steps and interrupted some rows.
- Error: `accept-prefix parity requires MTP3 full-bonus verifier rows, got
  n_draft=2 draft=2 i_batch=3`.

`gemma4-q8-gpu0-acceptprefix-parity-full512-20260630T042642Z`

- Same stale/too-strict binary issue; invalid because rows hit the same
  `n_draft=2` short-tail rejection.

### Passing Run

`gemma4-q8-gpu0-acceptprefix-parity-full512-v2-20260630T043728Z`

Command shape:

```bash
cd /home/steve/qwen36-results-main
LLAMA_SPEC_VERIFY_ACCEPT_PREFIX_PARITY=1 \
GPU_INDEX=0 PORT=18480 FLASH_ATTN=on CTX_SIZE=32768 GGML_SYCL_ENABLE_VMM=1 \
MAX_TOKENS=512 CANARY_REPEATS=32 \
LABEL=gemma4-q8-gpu0-acceptprefix-parity-full512-v2-20260630T043728Z \
repro/gemma4-26b-a4b-q8-b70/run-vdr2-selecteddown-record.sh
```

Evidence:

- `data/gemma4-q8-gpu0-acceptprefix-parity-full512-v2-20260630T043728Z/summary.json`
- `data/gemma4-q8-gpu0-acceptprefix-parity-full512-v2-20260630T043728Z/realistic-suite.json`
- `data/gemma4-q8-gpu0-acceptprefix-parity-full512-v2-20260630T043728Z/chat-canary.json`
- server log: `/mnt/fast-ai/bench-results/gemma4-26b-a4b-q8/servers/gemma4-q8-gpu0-acceptprefix-parity-full512-v2-20260630T043728Z.server.log`

Result:

- `bench_rc=0`
- canary: 128/128 rows passed
- realistic final gate: passed
- `cached_tokens=0` for all 12 prompts
- median tokens 1-100 after TTFT: `117.60357286123875 tok/s`
- p10: `104.05553056029459 tok/s`
- mean: `117.26191569638787 tok/s`
- full512 after-TTFT median: `112.95266056446746 tok/s`
- wall full512 median: `108.53028475372003 tok/s`
- median TTFT: `178.42455202480778 ms`
- server log parity/exception matches: 0

## Decision

Closed as a useful parity proof and design input. Do not submit; it is below
the active `123.67689864739785 tok/s` record and intentionally does no real
work reduction.

The result proves the current sampled-row output is sufficient to derive the
same accepted-token vector as the existing sampler path for the full-bonus MTP
verifier shape, including short-tail `n_draft < 3` steps.

Next meaningful short-decode work is not another config screen. It is a real
backend accept-prefix verifier op or another profile-backed verifier/MoE
boundary reduction:

- keep the current one target decode boundary;
- preserve the bonus-token pipeline;
- avoid serial host/head launches;
- compute later verifier rows only when earlier rows matched, or otherwise
  reduce the expensive verifier graph boundary.
