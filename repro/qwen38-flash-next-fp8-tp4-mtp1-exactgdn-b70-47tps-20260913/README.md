# Reproduce the Qwen3.8 Flash-Next lossless-MTP1 line with the exact serial GDN verifier rows in the kernel extension (46.854250 tok/s on four B70s)

> **Certification: `lab-replay`.** This replays the record on a host where the
> lab's vLLM overlay, kernel stage, oneCCL build, model copy, virtual
> environment, and four-card topology already exist. Every identity is pinned
> and every binary is hosted, but the guide is not a portable installer; its
> `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json) lists
> the open gates. The [container route](CONTAINER-STATUS.md) is copied from the
> 37.83 tok/s guide and not adapted (it would also need `_xpu_C` rebuilt).

This is the fastest Flash-Next line the lab has published, and it changes nothing about the
model's arithmetic. The [37.83 tok/s line](../qwen38-flash-next-fp8-tp4-mtp1-qsafused-b70-38tps-20260907/README.md)
verified the one speculative token exactly by running the GDN (gated delta net) verifier rows
one at a time through vLLM's Python serial path: accepted state copied into spec column 0,
row 0 through the single-row decode kernel, column 0 copied into column 1, row 1 through the
decode kernel. A step-timing decomposition put that path at 8.7 ms of the 42.7 ms two-row
verify step, and the cost is in neither its kernels nor its index/copy glue. The kernel
extension already carries an exact mode that does the same per-row decode inside the single
`gdn_attention_spec_decode` op, but the served build hard-gates it to four verifier rows; the
lane's kernel tree head `e421889` (commit `ad25aa9`, "Generalize exact GDN replay to MTP row
count") accepts two. This line rebuilds `_xpu_C.abi3.so` from that tree
([series](../../patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md),
two inert env-gated commits on top for disclosure) and selects the extension's exact mode
(`VLLM_XPU_GDN_SERIAL_SPEC_DECODE=0`, `VLLM_XPU_GDN_NATIVE_SPEC_RECURRENT_SERIAL_EXACT=1`,
`VLLM_XPU_GDN_SPEC_PERSISTENT_SCRATCH=1`, `VLLM_XPU_GDN_NATIVE_SPEC_COMPLETION_BARRIER=1`).
The vLLM overlay (`6d872457`), the MoE kernel and its tuned map, the offload, the placement,
the collective runtime and the model are untouched.

The outputs are **the same authority as the 37.83 tok/s line**: exact-2K `afffd211…` and
exact-4K `1d833e5f…` on every server (a kernel-level probe is bit-identical for the mode, and
three certification servers plus the record server reproduce both pins), the quality profile
byte for byte against the certified battery (seven of seven exact-case outputs identical,
sixteen repeats collapsing to one hash, the long-context needle identical). The two-row
verify step drops from 42.7 to 33.7 ms; every row class gains 23-24%.
LocalMaxxing run: cmtzask41000nlq011f16bpbc.

## Result and identity

| Item | Value |
| --- | --- |
| Headline | **46.854250 tok/s**, median of prompt-class medians over 99 inter-token intervals after TTFT, fixed cold 12-prompt realistic suite sent once (A367, 2026-09-13); the 37.83 line scored 37.825654 on the same suite |
| Exactness | Same authority as the certified 37.83 line: exact-2K `afffd211…` and exact-4K `1d833e5f…` on A364, A365, A366 (battery servers) and A367 (record server); kernel probe bit-identical |
| Quality | 6/7 exact cases with the inherited `code_execution` miss and byte-identical outputs to the certified battery on all seven, 16/16 repeats one hash, exact needle (A364, A365, A366) |
| Model | `Qwen/Qwen3.8-Flash-Next-FP8` revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` (131 shards, 185,563,783,127 bytes; [contract](../qwen38-flash-next-fp8-tp4-mtp3-b70/model-contract.json)) |
| vLLM | fused-QSA overlay `6d8724577dabbee5fa0bbc70c4d927c6174c8d8a` (tree `3e8dfc59…`), unchanged from the 37.83 line ([series](../../patches/qwen38-flash-next-fp8-b70/vllm-qsafused-mtp1-6d872457/README.md)) |
| XPU kernel stage | stage v2: the served `2f829747` stage with `_xpu_C.abi3.so` rebuilt from kernel head `bbae3c59e226c1b0c2a2dca6c51b4465cf36fd26` over `e421889` ([series](../../patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md)); 18 loadable files pinned by [`runtime-stage-gdn-roundstate-v2-loadable.sha256`](../../experiments/qwen38-flash-next-fp8-b70/data/runtime-stage-gdn-roundstate-v2-loadable.sha256) |
| Collective runtime | public oneCCL `4ceafd1` build, `libccl.so.1.0` `43d94d43…`, `kernels.spv` `0d549c35…` ([receipt](../../patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/README.md)) |
| Python runtime | Python 3.12 venv, `torch 2.11.0+xpu`, `triton 3.7.0`, oneAPI 2025.3 compiler runtime |
| Cards | four Intel Arc Pro B70 32 GiB, TP4 + EP4, `ZE_AFFINITY_MASK=0,1,2,3` |
| Configuration | as the 37.83 line (`FULL_DECODE_ONLY` graph, MTP `num_speculative_tokens=1`, max length 4,352, one sequence, 64 batched tokens, KV `376569856` bytes BLHNC, UVA offload 12.25 GiB, never-routed experts host-placed) plus the four exact-mode selectors above |
| Full pins | [`identity.json`](identity.json) |

Evidence: [A367 realistic suite](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-native-exact-gdn-realistic-suite-v1-result.json),
[promotion attestation](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a367-promotion-attestation.json),
[A364 battery summary](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a364-native-exact-gdn-ple-only-qsa-stable-summary.json),
[A365 fresh-server repeat](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a365-fresh-repeat-deterministic-summary.json),
[A366 third server](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a366-native-exact-gdn-ple-only-qsa-stable-summary.json),
[exact-2K pair summary](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-native-exact-gdn-exact-2k-pair-summary.json),
[kernel probe](../../experiments/qwen38-flash-next-fp8-b70/probes/gdn-spec-round-state-equivalence.py),
run-directory manifests [`evidence/a364-run.sha256`](evidence/a364-run.sha256) and [`evidence/a367-run.sha256`](evidence/a367-run.sha256).
The narrative is in the [result packet](../../results/qwen38-flash-next-fp8-b70/README.md) and the lane notes
(`2026-09-12-a344-a354-the-second-verify-row-is-gdn-glue.md`, `2026-09-12-a361-a363-the-extension-exact-serial-mode-removes-the-tax.md`,
`2026-09-13-a364-native-exact-gdn-certification-result.md`).

## Measured long-context extension (separate diagnostic profile)

A382 and A394 extend the exact-GDN MTP1 line to **33,280 served capacity**, with
KV budget **1,341,530,112 bytes** and the never-hit + max-count-2 host placement.
These are different capacity/placement settings from the A367 realistic headline;
they do not replace its 46.854250 tok/s score. Both historical servers completed
two exact-depth rows at each of 2,048, 8,192, 16,384 and 32,768 input tokens.
Every depth has one output-token hash across all four rows, equal to its A381
control. This is repeat evidence, not a completed long-context quality battery.

| Actual input tokens | Decode median tok/s | TTFT median seconds | Rows / servers |
| --- | --- | --- | --- |
| 8,192 | 42.7035 | 47.6778 | 4 / 2 |
| 16,384 | 45.5645 | 99.4437 | 4 / 2 |
| 32,768 | 44.0520 | 206.1754 | 4 / 2 |

The table takes the conventional median of all four retained rows at each depth;
decode uses the 99-interval rates rounded to 0.001 tok/s in the original summaries.
At 2,048 tokens, first-use rows were 29.294 / 29.328 tok/s and subsequent rows
47.246 / 47.248 tok/s (A382 / A394). They remain separate and are omitted from the
curves because pooling startup with subsequent execution would obscure that split.
TTFT is measured directly; no prefill throughput is inferred. Curves connect only
these measured points and make no claim at unmeasured lengths.

[Aggregate with every source row and source hash](evidence/a382-a394-context-profile.json),
[A382 rows](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a382-32k-context-depth-ladder.json),
[A394 repeat rows](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-tp4-mtp1-a394-32k-context-depth-ladder-fresh-server.json),
[exact prompt fixture](../../data/qwen27-exact-depth/qwen38-flash-next-bcd9f01-exact-depth-v1.json),
[placement](../../experiments/qwen38-flash-next-fp8-b70/data/20260913-q38-expert-host-placement-a315-census-5gib-mc2-per-rank.json).
A frozen long-context client and quality battery at the served capacity remain
uncompleted. Historical row success also does not prove safe teardown.

## Dependency closure

| Component | Identity and link |
| --- | --- |
| Host platform | Ubuntu 24.04, Linux 7.0 xe driver, four B70s on one host; **no tested install path** (open gate) |
| Accelerator toolchain | oneAPI 2025.3 compiler runtime, `torch 2.11.0+xpu`, `triton 3.7.0`; venv contents recorded in [`pip-freeze-observed.txt`](../qwen38-flash-next-fp8-tp4-mtp3-b70/pip-freeze-observed.txt) (observed, not locked) |
| Runtime source | public `76cfe1cd`, the [lossless-MTP1 series](../../patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/README.md) to `1b2a17c1`, the [placement series](../../patches/qwen38-flash-next-fp8-b70/vllm-placement-mtp1-005dc578/README.md) to `005dc578`, the [Triton-HC series](../../patches/qwen38-flash-next-fp8-b70/vllm-hctriton-mtp1-62219122/README.md) to `62219122`, the [fused-QSA series](../../patches/qwen38-flash-next-fp8-b70/vllm-qsafused-mtp1-6d872457/README.md) to `6d872457` |
| Native kernels | stage v2: the hosted `2f829747` stage ([disclosure](../qwen38-flash-next-fp8-tp4-mtp3-b70/RELEASE-NOTES.md)) with `_xpu_C.abi3.so` rebuilt from the [exact-serial-GDN kernel series](../../patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/README.md) (`bbae3c5` over `e421889`); build and assembly scripts `experiments/qwen38-flash-next-fp8-b70/tools/q38-build-xpu-c-gdn-roundstate.sh`, `q38-assemble-gdn-roundstate-stage.sh` |
| Collective runtime | hosted public oneCCL `4ceafd1` build ([receipt](../../patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/README.md)) |
| Model | publisher revision `bcd9f01d`, [contract](../qwen38-flash-next-fp8-tp4-mtp3-b70/model-contract.json) and [`verify-model.py`](../qwen38-flash-next-fp8-tp4-mtp3-b70/verify-model.py) |
| Configuration | the frozen A367 packet (four scripts pinned by [`frozen-a367-packet.sha256`](frozen-a367-packet.sha256)), derived from the certified A306 packet by `experiments/qwen38-flash-next-fp8-b70/tools/rewrite-q38-a306-to-a366-native-exact-gdn-realistic-suite.py`; the certification packets A364/A365/A366 by `rewrite-q38-a305-to-a364-native-exact-gdn-certification.py` |
| Execution | `verify-identity.sh`, `run-record-gate.sh` (below); container route not adapted |
| Verifier pin | the frozen packet pins the exactness verifier by bytes; [`verifier-pin.txt`](verifier-pin.txt) records its SHA-256, git blob and the last lab commit that carries it |
| Last realistic-suite replay | none beyond A367; A382/A394 are separate long-context diagnostics, not record-suite replays; historical replay is not authorized on the current host |
| Validation | frozen client: fixed cold realistic suite once, exactness verifier `verify-moe-m1-w13-n32-selection.py` (`c874852b…`), fresh-response gates; `check-replay-result.py` compares output pins and gates with the record |

## Restore source

```bash
cd /path/to/b70-optimization-lab
REPRO_VLLM_TREE=/path/to/vllm-clone patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/verify-series.sh --apply
REPRO_VLLM_TREE=/path/to/vllm-clone patches/qwen38-flash-next-fp8-b70/vllm-placement-mtp1-005dc578/verify-series.sh --apply
REPRO_VLLM_TREE=/path/to/vllm-clone patches/qwen38-flash-next-fp8-b70/vllm-hctriton-mtp1-62219122/verify-series.sh --apply
REPRO_VLLM_TREE=/path/to/vllm-clone patches/qwen38-flash-next-fp8-b70/vllm-qsafused-mtp1-6d872457/verify-series.sh --apply
git -C /path/to/vllm-clone checkout q38-qsafused-mtp1-6d872457
REPRO_KERNEL_TREE=/path/to/vllm-xpu-kernels-clone patches/qwen38-flash-next-fp8-b70/xpu-kernels-gdn-exact-serial-bbae3c5/verify-series.sh --apply
```

The served kernel stage and the oneCCL build are downloaded from their releases and checked
against the tracked manifests; stage v2 is the served stage with `_xpu_C.abi3.so` replaced by
the build of kernel head `bbae3c5` (the build script above records every CMake option; the
resulting file is pinned by the v2 manifest, and a rebuild is gated within-binary by the
certification battery, not by byte identity with the lab's build).

## Historical replay and current operating limits

The frozen A367 scripts and identity pins remain historical reproduction evidence.
`run-record-gate.sh` invokes a host-controlled wrapper that changes swap, ASPM and
page-cache state and starts/stops a server. **Do not run that path on the current
host.** The user's current constraints prohibit those changes, repeated server
restarts, automatic retries, reboots and driver resets. Waiting between launches
does not make that historical path authorized or establish safety.

No compliant launch/replay is certified by this packet. A future client may reuse
an already running, identity-verified endpoint; a failed request must halt new
requests and preserve evidence, without cycling the server. Any needed graceful
shutdown is a single incident action. The historical A394 completion did not
establish clean shutdown: teardown returned 143 and cached GPU receipts do not
prove current device health. See the [recovery](../../notes/2026-09-13-a394-freeze-recovery.md)
and [teardown audit](../../notes/2026-09-13-a394-teardown-audit.md).

`verify-identity.sh` checks the source, binary, model and packet identities without
GPU work. Its defaults refer to the originating host; verification alone does not
authorize the historical wrapper. The frozen scripts and recorded hashes have not
been rewritten to disguise their historical operating policy.

## What is not certified

- no clean-host install: the venv, oneAPI runtime, xe driver and model copy are assumed;
- non-originating-host replay: none yet;
- container route: copied from the 37.83 guide, not adapted, unbuilt;
- the kernel stage is a hybrid: `_xpu_C` rebuilt at `bbae3c5` on top of a hosted `2f829747`
  stage whose other components were built at various earlier heads (see the mtp3 guide's
  release notes); the rebuilt `_xpu_C` links `libmqa_logits_kernels_xe_2.so`, the only NEEDED
  difference against the served binary; the oneCCL binary is pinned by bytes;
- the served build's own exact mode is unreachable at two rows (four-row gate), so this line
  cannot be reproduced on the served `_xpu_C`; the rebuild is part of the identity;
- the placement is a census artefact: experts never routed to on the exact-2K trajectory and
  the realistic suite; a workload that routes to a host-placed expert pays a UVA read.
