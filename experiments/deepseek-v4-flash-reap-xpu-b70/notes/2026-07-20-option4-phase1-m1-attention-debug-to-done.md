# Option 4 Phase 1 M1 attention debug-to-done

## Numbers first

- **Capture: PASS after 4 retry cycles.** The final packet covers **344/344**
  rank/layer/bucket instances: 4 ranks x 43 layers x both fixed buckets
  (`swa-resident-anchor64` and `compressed-swa-full-anchor512`). It verifies
  **22,232 payloads / 14,134,046,712 bytes** with aggregate instance SHA-256
  `52943218bd882870b2873713749924ad21fec7fe9c2dfe31f08160bd45c9cfc7`
  and packet-manifest SHA-256
  `8528f03231700b062163fafb840a7ff9af87720dad361833838397a44ca06fd1`.
  Six decode kernels compile in pre-arm warmup and **0 compile in the armed
  window**; three post-arm compilations belong to packet flush.
- **Component: PASS.** Both buckets are bitwise exact for all **43/43 layers**;
  all **86/86** layer/bucket raw command-list instances pass; changed input is
  **40/40** and fixed-address replay is **70/70**, including epochs/positions
  **28 and 58**. The measured attention cluster has **14 eager submission
  boundaries versus 1 for M1AttentionBoundaryV1**, with **0 host syncs**.
- **PIECEWISE nesting: PASS in the isolated gate.** Replaying the inner
  executable through the current SYCL queue records into the surrounding
  graph, produces exact **8,192/8,192 output bytes**, causes **no eager break**,
  and adds **0 host syncs** inside the candidate op. Direct raw Level Zero
  append is preserved as a negative because it bypasses surrounding SYCL
  recording.
- **Four-card endpoint: FAIL.** The default-off guarded custom-op seam loads and
  completes PIECEWISE capture without a reported eager break, but the same
  binary control is **22.9140759668 ms/token** and candidate is
  **23.0957300325 ms/token**: **-0.1816540657 ms/token saved**, versus the
  required **+0.50 ms/token**. Candidate output tokens are exact on only
  **9/12 prompts**, so the exact-token gate also fails.
- **Phase 2: NO-GO.** Leave the selector off. M=8 speculative-cycle transfer is
  not qualified by this M=1 nonspeculative result.

## Capture debug loop

The initial armed anchor-64 assertion mixed semantic positions with physical
KV slots. Commit `81f1f426d` binds capture to the canonical physical slot and
`362272965` checks that slot against physical KV geometry. Commit `50b7d88dc`
adds a discard-only pre-arm pass across anchors 64 and 512, compiling all six
decode kernels before capture without contaminating the captured packet.

Four capture/flush cycles were required after those fixes:

1. `m1-attention-boundary-v1-20260720T234300Z` reached 344/344 and zero armed
   JIT, but lacked the immutable RoPE table required for replay. Its JSONL,
   manifests, summary, logs, and checksums remain. The superseded 11 GiB tensor
   payload was deleted to recover disk.
2. The `20260720T235500Z` flush captured RoPE but serialized the same 256 MiB
   table per rank/layer and exhausted disk. The server log and identity remain;
   the incomplete 21 GiB corpus was deleted.
3. `m1-attention-boundary-v1-20260720T235900Z` was structurally complete, but
   component replay proved that a single globally deduplicated C1 table is
   invalid for C4/C128 layers. This is preserved as a negative.
4. Commit `8e2daa67d` keys immutable rotary bindings by compression ratio
   C1/C4/C128. The final packet
   `/mnt/fast-ai/deepseek-v4-corpora/m1-attention-boundary-v1-20260721T001727Z`
   passes all coverage, checksum, and armed-window JIT checks.

The intermediate commits `874a44360` and `c71adbc35` are intentionally kept:
they record the initial immutable binding and the insufficient single-global
deduplication attempt rather than hiding the negative iterations.

## M1AttentionBoundaryV1 component

The replay implementation follows raw-LZ oracle order through rank-local WO_B
without owning the TP reduction: MHC ingress and norm, attention projections,
compressor/state updates, fused QNorm/RoPE/KV insertion, split FP8 QK/LSE/PV,
inverse RoPE/WO_A, and local WO_B. Static-tail score bytes are excluded because
the incumbent sparse kernel deliberately leaves that tail unwritten; every
initialized intermediate and final local output is compared bitwise.

Evidence root:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/option4-m1-attention-component-20260721T0029Z`

The raw V1 trace contains one
`zeCommandListImmediateAppendCommandListsExp` and zero host synchronization
calls. The eager trace contains 14 kernel appends. The nested repair uses
`replay_current_queue(inner.graph_exec)` so the surrounding PIECEWISE graph
records the executable. The direct raw-append nesting probe remains failed and
documented because the Level Zero append bypasses SYCL outer recording.

## Same-binary endpoint gate

Both endpoint arms use vLLM commit
`67044c25d0886f11037671f74da47225ad7297ce`, the same K160 revision, TP4,
PIECEWISE graphs, nonspeculative decoding, one active generation, and the same
public 12-prompt cache-zero suite. The only candidate change is
`VLLM_XPU_V4_OPTION4_M1_ATTENTION_BOUNDARY=1`; its default is `0`.

| Arm | Median tok/s, tokens 1-100 after TTFT | Median ms/token | Cache zero |
| --- | ---: | ---: | --- |
| control | 43.6412972291 | 22.9140759668 | 12/12 |
| candidate | 43.2980468074 | 23.0957300325 | 12/12 |
| saved | - | **-0.1816540657** | - |

The candidate differs from the control at token index 58 for
`incident-retrospective`, 45 for `code-review`, and 4 for `sql-debugging`.
This is a hard exactness failure. A diagnostic control reload is itself exact
on only 7/12 prompts versus the first control, and a same-service candidate
repeat is exact on 9/12; the incumbent temperature-zero endpoint therefore has
an independent nondeterminism problem. That prevents uniquely attributing all
token drift to this boundary, but it does not waive the requested exact-token
gate. Performance independently fails by 0.681654 ms/token relative to the
minimum required saving.

Control evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/option4-m1-attention-endpoint-control-20260721T010000Z`

Candidate evidence:

`/mnt/fast-ai/bench-results/deepseek-v4-flash-xpu/option4-m1-attention-endpoint-candidate-20260721T011200Z`

The live server completed mixed PIECEWISE and decode FULL capture without an
error or reported graph break. The no-host-sync claim is scoped to the isolated
traced nested V1 op; the endpoint server was not run under whole-process PTI.

## Runtime identity and disposition

- Model revision: `7c360e1cd4a5168099dbc54d16d929bf6df04990`.
- XPU kernel source: `5a1e9fa4602f69302dc50ecf85b06b6f86762117`.
- Existing XPU extension SHA-256:
  `d62ea1cf4728250809052c68fdd74983b4f2c0dcaf924624e7a507c8d4c8392f`.
  It was not rebuilt.
- Isolated replay shim SHA-256:
  `431ae9ff183a8070689411cca9a037c20df7bc241ab54562d847d3e4184bd304`.
- No LocalMaxxing submission occurred.
- Postflight stopped the service, closed port 18080, removed every vLLM
  worker/engine, and left all four cards free of inference work.

M=8 changes command geometry, fixed addresses, KV/compressor transitions, and
verifier-cycle ownership. It must receive its own capture, bitwise component
gate, replay qualification, and endpoint A/B; no M=8 transfer claim is made
from this M=1 packet.
