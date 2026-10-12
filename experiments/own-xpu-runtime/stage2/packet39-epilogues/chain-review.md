# Independent chain review

Reviewed the actual recorded W2C plan census as well as Builder and packet29 transforms.
No device program was run. The saved plan exists in an ignored read-only build directory; its identity and full logical class census are retained below.

- Plan SHA256: `ecf7f44ca61912f22a48e26b5038abf61b8894f8632047e7f72b77aa7794ee96`
- Declared logical sites: 1777
- Census entries: 1777

| Class | Logical sites per token |
| --- | --- |
| `argmax` | 1 |
| `attention` | 48 |
| `attn.combine` | 48 |
| `begin.0` | 1 |
| `begin.1` | 1 |
| `commit.0` | 1 |
| `commit.final` | 1 |
| `embedding` | 1 |
| `expsact` | 48 |
| `expsdown` | 48 |
| `expsdown.check` | 48 |
| `expsgate` | 48 |
| `expsgate.check` | 48 |
| `expsup.check` | 48 |
| `ffn.combine` | 48 |
| `final.act` | 1 |
| `final.gate` | 1 |
| `final.low` | 1 |
| `final.mix` | 1 |
| `final.norm` | 1 |
| `gdn.a` | 36 |
| `gdn.b` | 36 |
| `gdn.conv` | 36 |
| `gdn.gated` | 36 |
| `gdn.qkv` | 36 |
| `gdn.recurrence` | 36 |
| `gdn.z` | 36 |
| `handoff` | 1 |
| `handoff.result` | 1 |
| `hc.a.act` | 48 |
| `hc.a.gate` | 48 |
| `hc.a.inject` | 48 |
| `hc.a.low` | 48 |
| `hc.a.mix` | 48 |
| `hc.a.norm` | 48 |
| `hc.f.act` | 48 |
| `hc.f.gate` | 48 |
| `hc.f.inject` | 48 |
| `hc.f.low` | 48 |
| `hc.f.mix` | 48 |
| `hc.f.norm` | 48 |
| `logits` | 1 |
| `moe` | 48 |
| `ple.add` | 1 |
| `ple.cn` | 1 |
| `ple.conv` | 1 |
| `ple.gated` | 1 |
| `ple.hash` | 1 |
| `ple.key` | 1 |
| `ple.kn` | 1 |
| `ple.lookup` | 1 |
| `ple.qn` | 1 |
| `ple.value` | 1 |
| `qsa.attention` | 12 |
| `qsa.ik` | 12 |
| `qsa.iq` | 12 |
| `qsa.k` | 12 |
| `qsa.pool` | 12 |
| `qsa.prepare` | 12 |
| `qsa.qgate` | 12 |
| `qsa.select` | 12 |
| `qsa.v` | 12 |
| `route` | 48 |
| `router` | 48 |
| `shared_gate` | 48 |
| `shexpact` | 48 |
| `shexpdown` | 48 |
| `shexpgate` | 48 |
| `shexpup` | 48 |
| `streams` | 1 |

## Findings

1. Gate/up is already one paired issue followed by two checks, then activation. Count three tiny launches removed, not a second gate/up launch.
2. `moe` is one logical plan site but the implementation submits mixture then final blend. Timing reports 96 groups/token. Only the final blend belongs in shared-down; do not remove the mixture reduction.
3. `hc_mix` is a four-row ordered sum. Each row subgroup owns only one term; a direct single-row epilogue is invalid.
4. GDN gated norm is one measured launch, not two. Moving z after a new statistics stage can preserve arithmetic but saves zero launches against this baseline.
5. The final HC low activation occurs once outside the 48 layers, so its extra removable launch must be counted explicitly.
6. Existing `small.hc` and `small.ffn` grouping changes issue order, and must be disabled or composed explicitly with new epilogues.
7. Actual plan metadata lists active/error for GEMVs, but matrix binding discards them. GEMV output/status stores are unconditional; fused epilogues must not accidentally inherit unconditional execution.
8. A failed route suppresses the complete downstream activation. Per-slot local suppression is insufficient. Existing nonzero sticky codes must survive unchanged.

## Real-model gate feasibility

Read-only host objects and admitted model input descriptors are present in packet29 build. `host_gate.py` compiles a copied main under packet39/build and links unchanged host-only objects. `host_overlay.inc` runs new scalar epilogues immediately after each materialized GEMV row buffer and turns superseded logical issue sites into no-ops; shared scalar and the unchanged mixture are issued earlier. This is a full-model changed-chain check, not a native fused subgroup proof. The remaining plan labels retain the existing layer-fixture write hooks. Dynamic dependencies are checked to exclude accelerator libraries before execution. Compile and link both disable fast math and contraction.

The host overlay covers `final.low -> final.act`: packet29 `dispatch.hpp:39`
returns non-`blk.*` labels unchanged. The prefill loop explicitly omits
`final.*`, logits and argmax, so the overlay logs 564 skipped logical sites per
prefill token and 565 per token-producing pass. This diagnostic includes 48
relocated `shared_gate` sites and logical `moe` sites; it is **not** a count of
GPU launches removed or a performance estimate. Final HC activation contributes
one of the 97 HC activation groups per decoded token.

The final altered-plan host gate passed **8/8 tokens and 384/384 layer files**
against the arithmetic-v2 oracle (`real-eight.json`). It ran the seven initial
fusion kinds including convolution and final HC activation, with unchanged host
GEMV bodies and the fused scalar row helpers. The later status-only
`expert_checks` fallback is covered by the separate fixture gates. The host
gate does not execute SYCL kernels or provide device timing evidence.

Raw runtime receipt and stdout/stderr are retained losslessly in
`evidence/host-real-eight-runtime.json.gz` and
`evidence/host-real-eight.log.gz`; hashes bind their uncompressed bytes.
Temporary model outputs, repeated mini directories, copied compilation source
and object files were deleted after verification. The ignored host executable,
its dispatch and RoPE fixture remain under `build/host-gate/` for review;
`host_gate.py --build-only` regenerates the copied source and object.
