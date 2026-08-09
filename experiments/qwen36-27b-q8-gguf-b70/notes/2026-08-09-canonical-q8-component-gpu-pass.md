# Canonical Q8 c2 component GPU pass

Date: 2026-08-09

Status: sealed `COMPONENT_GATE_PASS`; diagnostic-only and not performance
promotable.

## Result

The default-off canonical per-vector Q8 control passed its first real B70 GPU
gate on GPU ordinal 0. The gate used the exact Qwen3.6 recurrent-output weight
shape `[6144,5120]`, two distinct deterministic input vectors, both flat
`[6144,2,1,1]` and recurrent `[6144,1,2,1]` layouts, and both M1-first AB and
batched-first BA bootstrap orders.

All selector-on outputs were bitwise identical to the fresh selector-off M1
references:

- M1 A SHA-256: `ed20dba51d74c4da9163494161a0c87cf87fd3a89722f8342e0ba339210c8db5`;
- M1 B SHA-256: `e43c5f4fdf2afad17bad7c9e57ec8da796a0af1d48faac68839f7631eacd0efb`;
- flat/recurrent AB SHA-256: `794ebb6a44426b653c98a776f0f435dc389247d97ffc2cfbe202be2f17f84ced`;
- flat/recurrent BA SHA-256: `bfee1517ce374a8c1e7dad274faf9e2c96e12162a91c4de67de69aa2d342bc8a`.

Each selector-on process retained the exact route counter tuple
`1/1/1/1/2/4/0`: one flat dispatch, one recurrent dispatch, one suppressed
multi-column route, one suppressed recurrent DMMV route, two reorder-ready
dispatches, four single-column MMVQ calls, and zero violations. The
selector-off process emitted no canonical route marker.

The three worker PIDs were distinct and bound to their records. All workers
and bounded helper processes exited cleanly without timeout, forced kill, or
survivor. Passive fault checks passed after each worker and before the single
postflight device query. GPU memory returned from `43 MiB` to `43 MiB`.

## Identity and sealed evidence

- gate commit: `ca4dc1a8945f8cb0bca1662a493ff8da6b590603`;
- candidate source: `109eee6fc36fcd073996c4c1eac7e22aa4c711da`;
- candidate SYCL source SHA-256:
  `ffcbe9c01b239407d68fdfea6cb982116d7ba4f22132ee671dc22cee09ef811f`;
- runtime manifest SHA-256:
  `1b6c305b7e3fad027e7397168bda23526b72b8a4b59e8c6b2b3788fc7347b4d9`;
- component runner SHA-256:
  `7d6ddb65aa4aa123260fa40bcd5aad0ae0b7ac471dc5cf78234f52fbee4ed5c8`;
- component executable SHA-256:
  `a8fccf34669325d3b328ece931b9dcce5328fb16162a2efd60b595af1f48a668`;
- packet:
  `/mnt/fast-ai/bench-results/qwen36-27b-q8-gguf-b70/component-gates/q8-canonical-mmvq-gpu0-20260809T211129Z`;
- `summary.json` SHA-256:
  `f6a6850141a493c97d727265920f4da62156007581c4e80d30342c1ba8d1a535`;
- 58-entry artifact inventory SHA-256:
  `40944af4f4d0df748b5974b1e23f9ede0697766f23ee73e0b21a49aac7297c80`;
- detached `completion-status.json` SHA-256:
  `99b890551ad7fe910362283a48a31b176950cc9c5097985a5f7dfaaf8dd65b2b`.

An independent audit recomputed every retained output and identity and found
no blocker.

## Boundary and next gate

This result rejects a simple isolated arithmetic, vector-order, or lazy-reorder
bootstrap defect for this covered Q8 projection shape. It does not test the
full model's recurrent state, KV cache, scheduler, natural stopping, forced
tail, or performance.

The next gate is therefore model-level rather than another component variant:
create selector-off and selector-on c1 oracles with the exact hybrid runtime,
then run the preregistered two-wave four-GPU card crossover. Full c2 equality
to the selector-matched c1 oracle is the correctness endpoint. The historical
B71/A96 splits remain baseline landmarks, not success criteria.
