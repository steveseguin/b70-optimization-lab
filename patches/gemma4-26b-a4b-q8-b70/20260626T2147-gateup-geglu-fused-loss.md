# 2026-06-26T21:47Z Q8 Gate/Up GEGLU Fused Op - Loss

## Patch

Default-off source experiment in
`/home/steve/src/llama.cpp-gemma-record-stack`, enabled by:

```bash
LLAMA_GEMMA4_MOE_GATEUP_GEGLU=1
```

Implementation summary:

- add backend-only `GGML_OP_MOE_Q8_0_GATEUP_GEGLU`;
- add `ggml_moe_q8_0_gateup_geglu(ctx, gate_up_exps, cur, ids, gate_up_scales)`;
- in the Gemma4 Q8 small-batch MoE graph, replace the current
  `MUL_MAT_ID(gate_up) -> split gate/up -> GEGLU` sequence with one SYCL op
  under strict guards;
- quantize the current hidden row to Q8_1 once, then dot the selected Q8_0
  gate/up expert rows and emit F32 GEGLU output shaped
  `[n_ff, n_expert_used, n_tokens]`;
- leave the down projection and final weighted sum on the existing validated
  route-cache path.

The source patch built successfully with:

```bash
cd /home/steve/src/llama.cpp-gemma-record-stack
source /opt/intel/oneapi/setvars.sh --force >/tmp/oneapi-setvars-gemma-build.log 2>&1
cmake --build build-sycl-b70-aot-bmg-g31 -j --target llama-server
```

Harness capture was added so the env key appears in both the server log and
`summary.json`:

- `scripts/run-gemma4-26b-first-baseline.sh`;
- `scripts/run-gemma4-26b-llamacpp-replica.sh`.

## Result

Run:
`data/gemma4-q8-gpu2-gateup-geglu-screen-20260626T214732Z/summary.json`

Config: current promoted Gemma 4 26B A4B Q8 record recipe plus:

```bash
LLAMA_GEMMA4_MOE_GATEUP_GEGLU=1
LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1
```

Validity:

- canary: `32/32` repeats, `128` rows, pass;
- benchmark cached tokens: `[0, 0]`;
- row0 is fresh-response eligible;
- quality lane: Q8 target/verifier, Q4_0 MTP draft only.

Performance:

- fresh row0 after TTFT: `84.21460316143335 tok/s`;
- support mean after TTFT: `84.22833614279985 tok/s`;
- current valid record: `103.51547512013657 tok/s`;
- delta from record: about `-18.6%`.

## Decision

Reject. Do not promote. Do not submit to LocalMaxxing.

The prototype is correctness-clean in the screen, but it is a large throughput
loss. The current `LLAMA_SYCL_MUL_MAT_ID_ROUTE_CACHE=1` path for gate/up is
substantially better than this naive fused dot+GEGLU implementation. The fused
op reduces graph/node count but loses the tuned `MUL_MAT_ID` math path and does
not address the down projection or LM-head work enough to compensate.

Keep the env-gated source patch as a research artifact only. Do not make it part
of the promoted Gemma recipe. Future fused-MoE work should either fuse a much
larger single-output MoE region or optimize the existing route-cache `MUL_MAT_ID`
path directly rather than replacing it with this small fused gate/up op.
