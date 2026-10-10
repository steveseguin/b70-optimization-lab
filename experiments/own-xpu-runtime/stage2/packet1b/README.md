# Stage 2 packet 1b — Flash-Next CPU reference math

**CPU synthetic gate passed, 2026-10-10; certified device parity UNVERIFIED.**
This independently written reference prepares Stage2's operator census. It is
not a working model runtime, an implementation of vLLM, a certified FP8 MoE
kernel or an authorization for native work. No external runtime is imported,
translated into our implementation, or used as its base. Source was inspected
for mathematical contracts and credited below; only torch CPU arithmetic and
the lab's existing GGUF block-size parser are execution dependencies.

[Reference](reference.py), [37 tests](test_reference.py),
[test receipt](test-receipt.json), [fresh-process receipt](test-receipt-fresh.json),
[source pins](source-evidence.json) and [planning arithmetic](planning-arithmetic.json)
are retained. Receipts pin source/docs/contracts, CPU build, nice/thread
settings, test IDs, failure counts, RSS and eight synthetic output digests.
Both runs must pass; the fresh receipt compares every output digest and test
ID to the first receipt. Same-process repeats are also tested. No claim about
cross-build numerical stability follows from this CPU repeat.

## Geometry and coverage

[Packet1's tensor contract](../packet1/tensor-contract.json) is the authority:
H2560; GDN16 key/48 value heads, K=V128, conv4; QSA24 query/2 KV heads,D256,
indexer4 query/1 key heads,D128, pooling4,budget2048; MoE512 top10, routed and
shared intermediate640; HC4 streams, low-rank320; PLE16 rows of160 at
`model.language_model.layers.1`; MTP separate2560×2560 projections and one
QSA/MoE/HC block. The tests independently check representative header shapes.

Tests execute all arithmetic on real channel dimensions, including a full
GDN/HC/MoE decoder layer and a QSA/HC/MoE MTP block; a separate five-row QSA
fixture crosses a pooling boundary, repeats and splits the causal sequence.
Synthetic weight views have repeated nonzero output rows and full input
width; they are intentionally not representative model weights. Router scores
have512 entries, while **only ten selected expert matrices** are backed by
synthetic weights (top10 tied IDs0–9). That reduced bank bounds CPU memory;
it is not a512-expert payload/dispatch sweep. Missing IDs raise rather than
silently pruning or substituting an expert. Known-score fixtures separately
test512-way non-tied routing and BF16-created ties.

MTP uses the real merge/block/mixer widths but **seven synthetic head rows**,
not a full248,320-row head and not token-level model execution. PLE exercises
full physical row addressing across128 partitions of2,500,012×160 using a
synthetic callback; it never materializes or reads the51.2 GB table. Its hash
multipliers, per-head sizes/offsets are supplied synthetic metadata: the real
280 I64 bytes were header-described, not payload-read, in packet1. There is
no full PLE projection/gating/dilated-convolution module in this packet:
requested lookup/hash math is implemented; PLE injection/casts remain U6.

## Source-derived dependency order and explicit rounding

S2–S6 refer to the certified model overlay commit
`6d8724577dabbee5fa0bbc70c4d927c6174c8d8a`; exact paths, Git blobs and SHA256s
are in [source-evidence.json](source-evidence.json). The `amd/` implementation
is the historical XPU route. The fused QSA pre-indexer is the explicitly
qualified NVIDIA-named source port used by that route, not an inference from
its directory name. Local source checkouts are provenance only; reruns do not
need them. Lab deltas credit their underlying vLLM/XPU-kernel contributors.

| Key | Certified-line evidence | Frozen CPU dependency/cast sequence |
| --- | --- | --- |
| S1 | [Exact serial extension](../../../../patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md), kernel commit `bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26`, `gated_delta_rule.hpp`, `causal_conv1d.hpp`, `spec_decode.hpp`; [packet1 precision evidence](../packet1/README.md#differences-and-boundaries-that-must-survive-implementation) | BF16 projections, width4 chronological conv with FP32 ascending tap accumulation, FP32 SiLU then BF16. Normalize Q/K, scale Q by1/sqrt128, decay old state, dot with K, `(V-prediction)*sigmoid(b)`, outer-product add, dot updated state with Q. Output rounds BF16; **state rounds BF16 after every serial row**, before the next row reads it. State layout[48,V128,K128]. GDN ordinary RMS gain then SiLU(z), BF16 before output projection. |
| S2 | `amd/indexer_qsa.py`, `amd/ops/qsa.py`, `nvidia/ops/qsa_pre_indexer.py`; [QSA port and serial guard](../../../../patches/qwen38-flash-next-fp8-b70/vllm-qsafused-mtp1-6d872457/README.md) | Project BF16 index Q4×128/K128. Q norm→text rotary. Four chronological raw keys sum FP32→divide4→**BF16 pooled boundary**→key norm→rotary at first position. Index score adds ReLU(Q·K) in head order0–3 then /sqrt128. Stable score-descending/logical-index-ascending selection of up to512 complete blocks; expand each selected block in token order and append incomplete tail; pad to2051 with−1. Serial rows preserve causality. Actual attention K/V remain BF16; architectural key pooling is not compressed-precision KV. |
| S3 | `model_executor/models/qwen3_next.py`, `layers/fused_moe/router/fused_topk_router.py`; `amd/model.py` inherits its MoE | FP32 softmax→top10→renormalize selected probabilities. CPU chooses stable descending/lowest-ID ties, accumulates experts in selection order, applies routing weight after down projection. Shared expert computes SiLU(gate)×up→down, sigmoid(shared gate), then adds to routed result. Exact device tie/reduction/quantization order is **U2/U4**, not established by the wrapper. |
| S4 | `amd/hyperconnection.py`, `amd/ops/hc.py`; [HC delta](../../../../patches/qwen38-flash-next-fp8-b70/vllm-hctriton-mtp1-62219122/README.md) | Normalize each H2560 stream separately with gain1+w, BF16 output. Down10240→320 and injection10240→4; divide down by4 before SiLU→BF16; up320→10240→sigmoid, mix normalized streams0–3 in FP32, /4→BF16. Combine `residual + branch*(2*sigmoid(injection/4))`, then BF16. CPU materializes pending combine before next mix; native fused path still needs U5. |
| S5 | `amd/ple_layer.py` and `amd/model.py`; [PLE memory geometry](../../../qwen38-flash-next-fp8-b70/notes/2026-10-08-host-memory-reduction-design.md) | layers.1 only. Bigram then trigram, eight heads each: signed64 wrapping token×multiplier, XOR in ngram order, positive remainder by head size+offset. EOS resets older history. Divide physical ID by2,500,012 for partition/local row. Gather E4M3[160], cast BF16, multiply global BF16 scale in FP32, BF16 output, concatenate16 rows. Exact real hash values and post-lookup injection remain U6. |
| S6 | `amd/mtp.py`, separate `pre_fc_norm_embedding`, `pre_fc_norm_hidden`, `fc_embedding`, `fc_hidden` | Normalize embedding H2560 and flattened HC hidden10240 separately (unit-offset norm); two independent projections. Broadcast projected embedding into four projected hidden streams, BF16 add. One QSA/MoE/HC block; final grouped HC mixer collapses to H2560, shared head produces proposals. Returns multistream hidden too. **Not the27B concatenation merge.** Acceptance, target verification and rollback are not implemented here. |

Every CPU elementary tensor operation is FP32 unless explicitly cast. Norm
uses an adjacent-pair tree with zero padding at odd widths, variance+1e-6,
rsqrt, gain1+w (ordinary gain for GDN output). GDN dot partitions128 keys into
32 lanes of four consecutive values; each lane adds four ascending products,
then that tree. No FMA contraction is assumed. Transcendentals use this pinned
torch CPU build. Linear uses bounded128-output tiles, FP32 CPU matmul and
BF16 output. FP8 weights multiply BF16 block128 scales in FP32 then round to
BF16 **before** that matmul. This is deliberately a mathematical surrogate;
**certified Flash Triton FP8 activation quantization is not implemented**.
No27B W8A16 equivalence claim is imported.

QSA attention splits per-query Q/gate, normalizes Q/K, applies split-half text
RoPE to64 dimensions (BF16 trig table), appends BF16 KV, computes FP32 scores
at1/sqrt256 over selected IDs, max-subtracted softmax and PV, rounds BF16,
applies sigmoid output gate and BF16 projection. CPU PV uses a fixed tree in
selected order, not the certified paged/split-K reduction. Text positions only;
vision/MRoPE channel composition requires separate fixtures.

## UNVERIFIED — required native census

Passing a synthetic test closes **none** of these rows. Save inputs, outputs,
intermediates and before/after states as little-endian dtype/shape/stride/raw
bytes+SHA256 with model/build/kernel/environment/dispatch identities. Prove
instrumentation does not change any of the12 frozen outputs before extracting.
Use the [Stage1 fixture envelope](../../stage1/packet1b/tests/fixture-extraction.schema.json)
as a structural starting point, extending it for Flash operators/EP/HC/PLE;
schema validity alone never proves bytes or numerical identity.

| ID | Unverified boundary | Required fixtures/gate |
| --- | --- | --- |
| U1 | GDN FMA, subgroup tree, transcendental approximations, gate/conv casts and exact serial/checkpoint behavior | All M1/M2/prefill shapes and row states, rounding/cancellation cases, accepted-prefix replay, poisoned padding. Preserve known BF16 inter-row commit; no FP32 substitution. |
| U2 | Flash Triton FP8 expert activation quantization, scale application, K reduction, dequant intermediates, output rounding; BF16 projection library math | All gate/up/down, shared/dense/head shapes, production tiles, scales and M-dependent dispatch; exact image-bound operators. CPU BF16-dequant/FP32-BLAS surrogate is not this arithmetic. |
| U3 | QSA norm/pool tree, rotary cache generation/casts, paged/split-K score/softmax/PV, query gate | Complete group/tail/context/page-boundary cases, ties, long context, serial rows, raw/compressed index keys and full BF16 KV. Current CPU covers text causal math only. |
| U4 | Certified router tie/NaN policy, top10 output order, route-weight placement and EP accumulation/allreduce order | All512 experts reachable, rank-skew/host-miss fixtures, near ties, same/fresh repeats and every served M. Softmax/renormalize is sourced; CPU stable ties and ordered accumulation remain choices. |
| U5 | HC packed down/inject padding, GEMM/reduction/fusion exactness and materialized versus delayed combine | Per-stream norm, low-rank/injection, gated mixes and every rounded combined stream, row-wise selectors and TP4 collective ordering. |
| U6 | Authenticated PLE hash metadata/real row bytes, owner reduction, global-scale widening and exact lookup casts; full PLE projection/gating/conv/injection | Real boundary/EOS/hash-overflow fixtures; every partition covered, physical table offsets, immutable row ownership, history reset and integration before HC; no real payload values supplied here. |
| U7 | MTP norm/project/shared-head device arithmetic, proposal schedule and full transactional semantics | Complete block/full-vocabulary head and multistream states, target-only versus MTP, first-token phantom, accept0/partial/all/EOS, rollback of every state, fresh-process oracle equality. Seven-row synthetic head is screening only. |

## Re-run offline

```bash
nice -n 19 env OMP_NUM_THREADS=2 /home/steve/.venvs/vllm-xpu/bin/python -B experiments/own-xpu-runtime/stage2/packet1b/run_tests.py
```

To deliberately rewrite the first receipt add
`--receipt experiments/own-xpu-runtime/stage2/packet1b/test-receipt.json`.
For a fresh process add
`--compare-receipt experiments/own-xpu-runtime/stage2/packet1b/test-receipt.json`
and `--receipt experiments/own-xpu-runtime/stage2/packet1b/test-receipt-fresh.json`.
The runner refuses any nice value other than19 or OMP thread setting other
than2; pins two torch CPU threads, one interop thread and deterministic CPU
algorithms. The installed torch has an XPU build suffix; no device API is
queried or initialized. `-B` prevents bytecode scratch. Tests use only synthetic
memory and retained repository JSON, never model files, network or device nodes.
The planning calculator reads the lab's Stage1 GGUF type table and packet1
census; its JSON is reproducibly checked, not timed model evidence.

During preparation two test assertions were corrected: BF16 arange512 creates
ties, so the distinct-score fixture now uses representable top scores and a
separate test pins the ties; uniformly scaling an embedding is canceled by
RMSNorm, so MTP sensitivity now changes its direction. Those were fixture
errors, not device observations. Final receipts contain the corrected suite.
No scratch directory was created; no native build, model/server launch,
systemd operation, port8188 access, `/dev/dri` access, weight download or write
under `/mnt/fast-ai` occurred. Next work is the CPU admission packet, followed
by the owner's separately authorized native census under [STAGE2-PLAN](../../STAGE2-PLAN.md).
