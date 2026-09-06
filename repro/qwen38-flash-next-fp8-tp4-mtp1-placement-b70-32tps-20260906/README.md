# Reproduce the lossless MTP1 Qwen3.8 Flash-Next line with never-routed experts host-placed (31.929 tok/s on four B70s)

> **Certification: `lab-replay`.** This replays the record on a host where the
> lab's vLLM overlay, kernel stage, oneCCL build, model copy, virtual
> environment, and four-card topology already exist. Every identity is pinned
> and every binary is hosted, but the guide is not a portable installer; its
> `missing` entry in [`repro/guide-catalog.json`](../guide-catalog.json) lists
> the open gates. The [container route](CONTAINER-STATUS.md) is written but
> unbuilt and unreplayed (the base image ships torch 2.13; the record needs 2.11).

This is the fastest quality-preserving Flash-Next line the lab has published:
the deterministic full-decode-graph TP4/EP4 server with one publisher MTP
token (every output pin equals the no-speculation line), where the experts a
routing census never selects live in pinned host memory behind a per-expert
offset table in the Triton MoE kernel, so every hot expert stays resident and
only the PLE n-gram table and the input embeddings are read over UVA. It
supersedes the [27.05 tok/s headroom line](../qwen38-flash-next-fp8-tp4-mtp1-lossless-b70-27tps-20260905/README.md).
LocalMaxxing approved it as run
[`cmtq59cy503jvn701kgvg62zt`](https://www.localmaxxing.com/runs/cmtq59cy503jvn701kgvg62zt).

## Result and identity

| Item | Value |
| --- | --- |
| Headline | **31.929484 tok/s**, median of prompt-class medians over 99 inter-token intervals after TTFT, fixed cold 12-prompt realistic suite sent once (A226, 2026-09-06) |
| Exactness | 12/12 outputs bit-identical to the approved MTP0 and MTP1 rows; the A225 battery on a separate server reproduced the exact-2K (`afffd211…`, 33.21/33.22 tok/s) and exact-4K (`c6193cc6…`, 32.48/32.50) authorities, 6/7 quality with the inherited miss, 16/16 repeat, exact needle; the tuned-map selection receipt is part of the battery |
| Model | `Qwen/Qwen3.8-Flash-Next-FP8` revision `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` (131 shards, 185,563,783,127 bytes; [contract](../qwen38-flash-next-fp8-tp4-mtp3-b70/model-contract.json)) |
| vLLM | placement overlay `005dc57895896f770157ea94f68e473e7447139e` (tree `d82fb5f2…`): nine commits over the lossless MTP1 head `1b2a17c1` (55 commits over public `76cfe1cd88d30d525eec8be5bff75f8b77471c88`); package version `0.20.2rc1.dev2+gc51df4300.d20260523.xpu` |
| XPU kernel stage | build head `2f829747503c77d4814834dffd0840fb1dd9f75a`, 18 loadable files pinned by [`runtime-stage.sha256`](../qwen38-flash-next-fp8-tp4-mtp3-b70/runtime-stage.sha256), hosted as GitHub release [`qwen38-flash-next-runtime-2f829747-20260827`](https://github.com/steveseguin/b70-optimization-lab/releases/tag/qwen38-flash-next-runtime-2f829747-20260827) |
| Collective runtime | public oneCCL `4ceafd1` build, `libccl.so.1.0` `43d94d43…`, `kernels.spv` `0d549c35…` ([receipt](../../patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/README.md)) |
| Python runtime | Python 3.12 venv, `torch 2.11.0+xpu`, `triton 3.7.0`, oneAPI 2025.3 compiler runtime |
| Cards | four Intel Arc Pro B70 32 GiB, TP4 + EP4, `ZE_AFFINITY_MASK=0,1,2,3` |
| Configuration | `FULL_DECODE_ONLY` graph (capture sizes 1 and 2), MTP `num_speculative_tokens=1`, max length 4,352, one sequence, 64 batched tokens, KV `376569856` bytes BLHNC, UVA offload `--cpu-offload-gb 12.25` of `ple_embedding.ngram_embedding.weight embed_tokens.weight` (12.22 GiB per rank; every hot routed expert resident), `Q38_EXPERT_HOST_PLACEMENT` = 3.5 GiB per rank of never-routed experts (543-587 per rank) in pinned host memory behind the kernel's per-expert offset table, `VLLM_XPU_MKLDNN_DETERMINISTIC=1`, oneCCL `twoshots` all-reduce, tuned MoE map `moe-m1-w13-n32` (map `a8f1f898…`) |
| Full pins | [`identity.json`](identity.json) |

Evidence: [A226 realistic suite](../../experiments/qwen38-flash-next-fp8-b70/data/20260906-tp4-mtp1-a226-realistic-suite-v1-result.json), [promotion attestation](../../experiments/qwen38-flash-next-fp8-b70/data/20260906-tp4-mtp1-a226-promotion-attestation.json),
[A225 battery summary](../../experiments/qwen38-flash-next-fp8-b70/data/20260906-tp4-mtp1-a225-fresh-repeat-deterministic-summary.json), [A190/A225 exact-2K pair](../../experiments/qwen38-flash-next-fp8-b70/data/20260906-tp4-mtp1-a190-a225-exact-2k-pair-summary.json),
[placement file](../../experiments/qwen38-flash-next-fp8-b70/data/20260906-q38-expert-host-placement-3p5gib-per-rank.json), [LocalMaxxing response](../../data/localmaxxing-responses/qwen38-flash-next-fp8-tp4-mtp1-placement-realistic-20260906.json),
run-directory manifests [`evidence/a225-run.sha256`](evidence/a225-run.sha256) and [`evidence/a226-run.sha256`](evidence/a226-run.sha256).
The narrative is in the [result packet](../../results/qwen38-flash-next-fp8-b70/README.md).

## Dependency closure

| Component | Identity and link |
| --- | --- |
| Host platform | Ubuntu 24.04, Linux 7.0 xe driver, four B70s on one host; **no tested install path** (open gate) |
| Accelerator toolchain | oneAPI 2025.3 compiler runtime, `torch 2.11.0+xpu`, `triton 3.7.0`; venv contents recorded in [`pip-freeze-observed.txt`](../qwen38-flash-next-fp8-tp4-mtp3-b70/pip-freeze-observed.txt) (observed, not an installable hash lock; open gate) |
| Runtime source | public `76cfe1cd`, the [lossless-MTP1 series](../../patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/README.md) to `1b2a17c1`, then the [placement series and bundle](../../patches/qwen38-flash-next-fp8-b70/vllm-placement-mtp1-005dc578/README.md) (`verify-series.sh --apply` re-creates tree `d82fb5f2…`) |
| Native kernels | hosted stage `2f829747` (hybrid build: only `_moe_C` freshly built at that head, [disclosure](../qwen38-flash-next-fp8-tp4-mtp3-b70/RELEASE-NOTES.md)) |
| Collective runtime | hosted public oneCCL `4ceafd1` build ([receipt](../../patches/qwen38-flash-next-fp8-b70/oneccl-4ceafd1-b70-public/README.md)) |
| Model | publisher revision `bcd9f01d`, [contract](../qwen38-flash-next-fp8-tp4-mtp3-b70/model-contract.json) and [`verify-model.py`](../qwen38-flash-next-fp8-tp4-mtp3-b70/verify-model.py) |
| Configuration | the frozen A226 packet (four scripts pinned by [`frozen-a226-packet.sha256`](frozen-a226-packet.sha256)) and the placement file; server line in [`container-serve.sh`](container-serve.sh) |
| Execution | `verify-identity.sh`, `run-record-gate.sh` (below); container route unbuilt |
| Verifier pin | the frozen packet pins the exactness verifier by bytes; [`verifier-pin.txt`](verifier-pin.txt) records its SHA-256, git blob and the last lab commit that carries it, and `verify-identity.sh` names that commit when the file has moved on |
| Last replay | 2026-09-06 15:21, attempt 229 through `run-record-gate.sh` on the originating host: 12/12 outputs identical to the record, every gate equal, 32.181792 tok/s class-balanced ([gate log](evidence/a229-record-gate.log), [run manifest](evidence/a229-record-gate-replay.sha256), [suite result](../../experiments/qwen38-flash-next-fp8-b70/data/20260906-tp4-mtp1-a229-record-gate-replay-realistic-suite-v1-result.json)) |
| Validation | frozen client: fixed cold realistic suite once, exactness verifier `verify-moe-m1-w13-n32-selection.py` (`0bd36f13…`), fresh-response gates; `check-replay-result.py` compares output pins and gates with the record |

## Restore source

```bash
cd /path/to/b70-optimization-lab
REPRO_VLLM_TREE=/path/to/vllm-clone patches/qwen38-flash-next-fp8-b70/vllm-lossless-mtp1-1b2a17c1/verify-series.sh --apply
REPRO_VLLM_TREE=/path/to/vllm-clone patches/qwen38-flash-next-fp8-b70/vllm-placement-mtp1-005dc578/verify-series.sh --apply
git -C /path/to/vllm-clone checkout q38-placement-mtp1-005dc578
```

The kernel stage and the oneCCL build are downloaded from their releases and
checked against the tracked manifests (`runtime-stage.sha256`, `lib.sha256`);
the mtp3 guide's frozen `prepare-runtime.py` installs the stage tar.

## Run

```bash
cd /path/to/b70-optimization-lab
repro/qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/verify-identity.sh
REPRO_ATTEMPT=<unused number above 226> repro/qwen38-flash-next-fp8-tp4-mtp1-placement-b70-32tps-20260906/run-record-gate.sh
```

`verify-identity.sh` checks, without touching the GPUs: the placement overlay
bundle, tag, tree and nine-patch series over the lossless MTP1 head; the checked-out overlay head and a clean tree;
the 18 stage files; both oneCCL hashes; the model config, safetensors index and
shard count; the tuned map, the exactness verifier, the frozen packet and the placement file; and
the Python runtime versions. Defaults are the originating host's paths; each of
`REPRO_VLLM_TREE`, `REPRO_KERNEL_STAGE`, `REPRO_ONECCL_ROOT`,
`REPRO_MODEL_ROOT`, `REPRO_VENV_ROOT` may point at the same verified artifacts
elsewhere, and an absent default stops with the variable's name.

`run-record-gate.sh` derives a fresh attempt from the frozen A226 packet
(`make-replay-attempt.py`: byte-identical apart from attempt number, port and
state names, internal hashes recomputed), runs the packet's own static
validation, launches it through the lab's host-controlled launcher (root:
swap and ASPM reset, page-cache drop, fail-closed preflight on processes,
ports, mounts and free space), waits for `/health`, sends the fixed cold
realistic suite once with the record's flags (the packet's frozen client is the
separate certification battery, A225, and is not re-run), stops the server
through the packet's stop file, and compares `realistic-suite-v1-result.json`
with the record: all 12
prompt and output SHA-256s must match and every gate must equal the record's.
The replay's class-balanced median is printed beside 31.929484 tok/s; speed is
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
- the placement is a census artefact: experts never routed to on the exact-2K
  trajectory and the realistic suite; a workload that routes to a host-placed
  expert pays a PCIe read for that row (outputs stay bit-identical);
- the record is one measurement of one workload class (short/medium
  realistic prompts at 4,352 max length); long-context and concurrency behaviour
  are research, not part of this replay.

Ongoing optimization of this line continues in the
[experiment directory](../../experiments/qwen38-flash-next-fp8-b70/); nothing
there changes this packet until a new record is certified and catalogued.
