# Laguna exact M12 mapped gather/scale/add fusion preregistration

Date: 2026-08-01 America/Toronto

Status: preregistered before source change, build, or device execution.

## Premise and distinction

The promoted exact BF16-KV record is `125.4619731637751 tok/s` conventionally
at a `32.326922 ms` speculative cycle. The M12 target MoE tail still launches
the generic mapped `moe_gather` kernel and then the exact M12 shared
elementwise kernel. The first accumulates ten routed BF16 rows in slot order
with FP32 weights and stores BF16. The second reloads that BF16 value,
multiplies by exactly `2.5`, stores BF16, adds the BF16 shared expert value,
and stores BF16 again.

The candidate performs those operations in one workgroup per token. It loads
the existing `unpermuted_row_to_permuted_row` map, retains slot order and the
generic `-1` remote-row skip, performs the same FP32 accumulation, and uses
the already audited helper for the routed-BF16, scaled-BF16, and final-BF16
boundaries. It removes the intermediate routed tensor traffic and one XPU
submission per target layer without changing a value or rounding point.

This is materially distinct from the unmeasured 2026-07-24 M8 canonical-row
candidate. That kernel assumed 80 route-parallel rows in token/slot order and
accepted no permutation map. The current M12 grouped GEMM emits 120 rows in
expert-grouped order, so the new candidate must consume the real map and is
valid only for `[12,10]`, `[120,3072]`, BF16/FP32, scaling factor 2.5.

The old M8 Phase-A run stopped before importing its candidate because its
strict-idle parser expected the wrong `xpu-smi` JSON schema. It is neither
positive nor negative performance evidence and is not being retried.

## Candidate and gates

1. Start from protected kernel source
   `99886d783372e621941228250091dc8ebdc1595d`. Add a separately named M12
   mapped gather/scale/add op and a default-off exact-record dispatch. Selector
   off must preserve the promoted source path.
2. Static/source tests must require exact shapes and dtypes, one device,
   contiguity, non-overlap, 16-byte alignment, `num_local_experts == 64`, the
   real `[12,10]` permutation map, slot traversal 0..9, `-1` skip, and the
   shared audited three-BF16-boundary helper.
3. A one-B70 changed-input component compares generic `moe_gather` followed by
   `laguna_m12_scale_add` against the fused kernel from one DSO. Require at
   least 6/6 raw-BF16 equality, no input mutation, and identical map/weight/
   routed/shared inputs. Use 200 warmups and 15x40 timing.
4. Require at least `1.10x` component speedup and an extrapolated 48-layer
   saving of at least `0.30 ms/cycle`. Stop and preserve below either gate.
5. A component pass authorizes only vLLM integration plus focused CPU/source
   tests and a four-rank cache-zero topology smoke. The smoke must retain
   target 146/145, draft 14/13, normal acceptance, exact target-q1 output,
   and clean teardown.
6. Only a passed smoke authorizes one cold frozen 13-prompt endpoint leg. The
   first valid result stands; a record must be confirmed under the complete
   benchmark identity before promotion or LocalMaxxing submission.

This candidate is an incremental launch/traffic fusion and is not projected
alone to reach 130 tok/s. It may compose with an independent larger win.

No model, checkpoint value, INT4 weight, BF16 scale, BF16 KV, speculative
width/depth, verification, sampling, prompt, teacher, cache policy, metric,
retry, warm generation, graph-capture window, or scoring window may change.
No reboot, reset, FLR, driver reload, or privileged recovery is authorized.
