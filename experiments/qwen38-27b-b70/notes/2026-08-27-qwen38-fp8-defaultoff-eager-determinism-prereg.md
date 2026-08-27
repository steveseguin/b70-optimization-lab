# Qwen3.8 FP8 default-off eager determinism preregistration

## Trigger and question

The block-W8A16 target-only TP2 profile remained nondeterministic with XPU
Graph disabled: two strict eager fresh servers matched only 10/12 complete
outputs. Graph capture is therefore not required. The next bounded variable is
the default-off block-W8A16 dispatch itself.

Does the unmodified official FP8 linear path reproduce 12/12 complete outputs
across two eager fresh servers when every other serving and benchmark control
is unchanged?

## Frozen control

- same official FP8 model revision, exact `f01e-kernel-1e90-w8a16-r122`
  image, two B70s, TP2, FP16 KV, target-only/MTP0, direct P2P, 1,024-token
  capacity, one sequence, and 1,024 max batched tokens;
- eager execution with both XPU graph switches off;
- `VLLM_XPU_FP8_BLOCK_W8A16=0`, so the overlay integration remains installed
  but its dispatch is inactive;
- two fresh containers and empty non-prompt cache directories;
- the same full 12-prompt/six-class/512-cap/cache-zero suite and post-suite
  canaries.

The launcher is the parameterized
[`run-w8a16-eager-server.sh`](../../../repro/qwen38-27b-fp8-vllm-tp2-asrock-b70/run-w8a16-eager-server.sh);
the server log must show no W8A16 selection and `enforce_eager=True`.

## Decision

Require 12/12 complete token-array equality across the two default-off eager
servers. If it passes while W8A16 eager remains 10/12, W8A16 is the bounded
causal treatment for this output-instability surface and cannot headline until
fixed. If it also fails, W8A16 is not required and the next diagnosis belongs
to the official FP8 TP2 target/runtime path. Do not weaken complete-output
equality or promote either speed merely because objective canaries pass.
