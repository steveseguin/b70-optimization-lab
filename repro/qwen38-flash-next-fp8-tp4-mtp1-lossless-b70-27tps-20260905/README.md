# Reproduce the lossless MTP1 Qwen3.8 Flash-Next line (27.048 tok/s on four B70s)

> **Certification: `lab-replay`.** This replays the record on a host where the
> lab's vLLM overlay, kernel stage, oneCCL build, model copy, virtual
> environment, and four-card topology already exist. Every identity is pinned
> and every binary is hosted, but the guide is not a portable installer; its
> `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json) lists
> the open gates. The [container route](CONTAINER-STATUS.md) is written but
> unbuilt and unreplayed.

This is the fastest quality-preserving Flash-Next line the lab has published:
the deterministic full-decode-graph TP4/EP4 server with one publisher MTP
token, where every output pin equals the no-speculation line (lossless), and
the September 5 VRAM-headroom fix that ended the GPU driver paging expert
weights. LocalMaxxing approved it as run
[`cmtp5u0ip02eln701lntsl2ns`](https://www.localmaxxing.com/runs/cmtp5u0ip02eln701lntsl2ns).

## Result and identity

| Item | Value |
| --- | --- |
| Headline | **27.048435 tok/s**, median of prompt-class medians over 99 inter-token intervals after TTFT, fixed cold 12-prompt realistic suite sent once (A189, 2026-09-05) |
| Exactness | 12/12 outputs bit-identical to the MTP0 line; fresh-server repeat A190 reproduced the exact-2K (`afffd211…`) and exact-4K (`c6193cc6…`) authorities and the short suite; quality 6/7 direct-answer, 25/25 official-thinking profile unchanged |
| Model | `Qwen/Qwen3.8-Flash-Next-FP8` revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` (131 shards, 185,563,783,127 bytes; [contract](../qwen38-flash-next-fp8-tp4-mtp3-b70/model-contract.json)) |
| vLLM | overlay `1b2a17c1e7c41985d6a5e0eb324ada4775c25e60` (tree `1cb86e07…`), 55 commits over public `vllm-project/vllm` `76cfe1cd88d30d525eec8be5bff75f8b77471c88`; package version `0.20.2rc1.dev2+gc51df4300.d20260523.xpu` |
| XPU kernel stage | build head `2f829747503c77d4814834dffd0840fb1dd9f75a`, 18 loadable files pinned by [`runtime-stage.sha256`](../qwen38-flash-next-fp8-tp4-mtp3-b70/runtime-stage.sha256), hosted as GitHub release [`qwen38-flash-next-runtime-2f829747-20260827`](https://github.com/steveseguin/b70-optimization-lab/releases/tag/qwen38-flash-next-runtime-2f829747-20260827) |
| Collective runtime | public oneCCL `4ceafd1` build, `libccl.so.1.0` `43d94d43…`, `kernels.spv` `0d549c35…` ([receipt](../../patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/README.md)) |
| Python runtime | Python 3.12 venv, `torch 2.11.0+xpu`, `triton 3.7.0`, oneAPI 2025.3 compiler runtime |
| Cards | four Intel Arc Pro B70 32 GiB, TP4 + EP4, `ZE_AFFINITY_MASK=0,1,2,3` |
| Configuration | `FULL_DECODE_ONLY` graph (capture sizes 1 and 2), MTP `num_speculative_tokens=1`, max length 4,352, one sequence, 64 batched tokens, KV `376569856` bytes BLHNC, UVA offload `--cpu-offload-gb 13.4` of `ple_embedding.ngram_embedding.weight embed_tokens.weight mlp.experts` (13.78 GiB per rank), `VLLM_XPU_MKLDNN_DETERMINISTIC=1`, oneCCL `twoshots` all-reduce, tuned MoE map `moe-m1-w13-n32` (map `a8f1f898…`) |
| Full pins | [`identity.json`](identity.json) |

Evidence: [A189 realistic suite](../../experiments/qwen38-flash-next-fp8-b70/data/20260905-tp4-mtp1-a189-realistic-suite-v1-result.json)
(SHA-256 `6939a129…`), [promotion attestation](../../experiments/qwen38-flash-next-fp8-b70/data/20260905-tp4-mtp1-a189-promotion-attestation.json),
[A190 fresh-server summary](../../experiments/qwen38-flash-next-fp8-b70/data/20260905-tp4-mtp1-a190-fresh-repeat-deterministic-summary.json),
[LocalMaxxing response](../../data/localmaxxing-responses/qwen38-flash-next-fp8-tp4-mtp1-headroom-realistic-20260905.json),
run-directory manifests [`evidence/a189-run.sha256`](evidence/a189-run.sha256) and [`evidence/a190-run.sha256`](evidence/a190-run.sha256).
The narrative is in the [result packet](../../results/qwen38-flash-next-fp8-b70/README.md).

## Dependency closure

| Component | Identity and link |
| --- | --- |
| Host platform | Ubuntu 24.04, Linux 7.0 xe driver, four B70s on one host; **no tested install path** (open gate) |
| Accelerator toolchain | oneAPI 2025.3 compiler runtime, `torch 2.11.0+xpu`, `triton 3.7.0`; venv contents recorded in [`pip-freeze-observed.txt`](../qwen38-flash-next-fp8-tp4-mtp3-b70/pip-freeze-observed.txt) (observed, not an installable hash lock; open gate) |
| Runtime source | public `76cfe1cd` plus the in-repository [overlay series and bundle](../../patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/README.md) (`verify-series.sh --apply` re-creates tree `1cb86e07…`) |
| Native kernels | hosted stage `2f829747` (hybrid build: only `_moe_C` freshly built at that head, [disclosure](../qwen38-flash-next-fp8-tp4-mtp3-b70/RELEASE-NOTES.md)) |
| Collective runtime | hosted public oneCCL `4ceafd1` build ([receipt](../../patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/README.md)) |
| Model | publisher revision `bcd9f01d`, [contract](../qwen38-flash-next-fp8-tp4-mtp3-b70/model-contract.json) and [`verify-model.py`](../qwen38-flash-next-fp8-tp4-mtp3-b70/verify-model.py) |
| Configuration | the frozen A189 packet (four scripts pinned by [`frozen-a189-packet.sha256`](frozen-a189-packet.sha256)); server line in [`container-serve.sh`](container-serve.sh) |
| Execution | `verify-identity.sh`, `run-record-gate.sh` (below); container route unbuilt |
| Validation | frozen client: fixed cold realistic suite once, exactness verifier `verify-moe-m1-w13-n32-selection.py` (`0bd36f13…`), fresh-response gates; `check-replay-result.py` compares output pins and gates with the record |

## Restore source

```bash
cd /path/to/b70-optimization-lab
REPRO_VLLM_TREE=/path/to/vllm-clone patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/verify-series.sh --apply
git -C /path/to/vllm-clone checkout q38-lossless-mtp1-1b2a17c1
```

The kernel stage and the oneCCL build are downloaded from their releases and
checked against the tracked manifests (`runtime-stage.sha256`, `lib.sha256`);
the mtp3 guide's frozen `prepare-runtime.py` installs the stage tar.

## Run

```bash
cd /path/to/b70-optimization-lab
repro/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/verify-identity.sh
REPRO_ATTEMPT=<unused number above 189> repro/qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/run-record-gate.sh
```

`verify-identity.sh` checks, without touching the GPUs: the overlay bundle,
tag, tree and 55-patch series; the checked-out overlay head and a clean tree;
the 18 stage files; both oneCCL hashes; the model config, safetensors index and
shard count; the tuned map, the exactness verifier, and the frozen packet; and
the Python runtime versions. Defaults are the originating host's paths; each of
`REPRO_VLLM_TREE`, `REPRO_KERNEL_STAGE`, `REPRO_ONECCL_ROOT`,
`REPRO_MODEL_ROOT`, `REPRO_VENV_ROOT` may point at the same verified artifacts
elsewhere, and an absent default stops with the variable's name.

`run-record-gate.sh` derives a fresh attempt from the frozen A189 packet
(`make-replay-attempt.py`: byte-identical apart from attempt number, port and
state names, internal hashes recomputed), runs the packet's own static
validation, launches it through the lab's host-controlled launcher (root:
swap and ASPM reset, page-cache drop, fail-closed preflight on processes,
ports, mounts and free space), waits for `/health`, runs the frozen client
once, and compares `realistic-suite-v1-result.json` with the record: all 12
prompt and output SHA-256s must match and every gate must equal the record's.
The replay's class-balanced median is printed beside 27.048435 tok/s; speed is
reported, not gated, because an exact replay that is slower is still exact.
A full pass takes about 25 minutes (9-12 minutes of model load from the lab's
USB copy, graph capture, the suite).

Stop: the packet's supervisor tears the server down at the end of the client
run and writes `/tmp/q38-mtp1-ple-only-a<N>.rc`; check that no `Worker_TP`
process or listener on the packet port remains.

## What is not certified

- no clean-host install: the venv, oneAPI runtime, xe driver and model copy
  are assumed; `pip-freeze-observed.txt` is a receipt, not a hash lock;
- non-originating-host replay: none yet; the host-controlled launcher assumes
  the lab's mounts and swap layout;
- container route: written, unbuilt, unreplayed ([status](CONTAINER-STATUS.md));
- the kernel stage is a hybrid build (only `_moe_C` rebuilt at `2f829747`), and
  the oneCCL binary is pinned by bytes, not by a reproducible build;
- the record is one measurement of one workload class (short/medium
  realistic prompts at 4,352 max length); long-context and concurrency behaviour
  are research, not part of this replay.

Ongoing optimization of this line continues in the
[experiment directory](../../experiments/qwen38-flash-next-fp8-b70/); nothing
there changes this packet until a new record is certified and catalogued.
