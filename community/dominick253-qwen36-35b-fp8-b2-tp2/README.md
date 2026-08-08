# Qwen3.6 35B A3B offline FP8 on two Intel Arc B70s

> **Community-reported result from `dominick253`.** This packet records a
> contributor-host run. The repository maintainer has not reproduced it in the
> reference lab. Read [STATUS.md](STATUS.md) before using the launcher.

This entry serves `Qwen/Qwen3.6-35B-A3B-FP8` with Intel's digest-pinned
`llm-scaler` vLLM B2 image. It uses two B70 GPUs, tensor parallelism 2, E4M3 FP8
KV cache, and MTP with two speculative tokens.

The key operational finding is narrow: Intel's simple-collective threshold
workaround from [llm-scaler issue #550](https://github.com/intel/llm-scaler/issues/550#issuecomment-5187718030)
allowed this offline-FP8 TP2 service to start on this contributor host. Earlier
launches without the complete transport configuration failed during profile
initialization with Level Zero device-loss and IPC errors. This is a verified
workaround on this host. It is not a proof that one variable or one transport
path was the sole cause.

## Evidence status

- Evidence level: `community-reported`.
- Three clean benchmark sweeps completed on 2026-08-06.
- Each sweep had exactly 165 expected successful requests and no extra request.
- The kernel fault counter did not increase during any clean sweep.
- Four saved MTP responses contained 11,024 completion tokens.
- The saved long outputs contained zero `!!!!` occurrences.
- The result is diagnostic service evidence, not a promoted repository record.

Run the local evidence auditor:

```bash
cd validation
python3 verify-evidence.py
```

It recomputes raw means, ranges, hashes, request counters, fault deltas, long-
output token counts, and repeated-punctuation checks.

## Exact identity

| Field | Value |
| --- | --- |
| Contributor | `dominick253` |
| GPU | 2x Intel device `8086:e223`, 34,242,297,856 bytes each |
| GPU BDFs | `03:00.0`, `08:00.0` |
| OS | Ubuntu 26.04 LTS |
| Kernel | `7.0.0-29-generic` |
| Driver | `xe`, srcversion `85B7CA089405934276CBAD3` |
| Image | `intel/llm-scaler-vllm@sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e` |
| vLLM | `0.21.1.dev0+gad7125a43.d20260802.xpu` |
| vLLM XPU kernels | `0.1.8.3.dev0+g3cab97a.d20260802` |
| custom ESIMD kernels | `0.1.0` |
| PyTorch | `2.11.0+xpu` |
| Model | `Qwen/Qwen3.6-35B-A3B-FP8` |
| Model revision | `95a723d08a9490559dae23d0cff1d9466213d989` |
| Weight shards | 42 present, 37,463,662,160 bytes total |
| Weight format | FP8 E4M3, dynamic activations, block size `[128,128]` |
| Compute dtype | FP16 |
| KV cache | `fp8_e4m3`; runtime log reports scale `1.0` |
| Tensor parallelism | 2 |
| Pipeline parallelism | 1 |
| MTP | enabled, two speculative tokens |
| Context limit | 131,072 tokens |
| Maximum sequences | 12 |
| Maximum batched tokens | 8,192 |
| Block size | 64 |
| Prefix caching | disabled |
| Graph mode | eager; XPU graph disabled |
| Modalities | text only in this recipe |
| Served name | `qwen36-35b-fp8` |
| Port | `8001` with host networking |

The local Hugging Face cache passed:

```text
hf cache verify Qwen/Qwen3.6-35B-A3B-FP8 --fail-on-missing-files
repo_id=Qwen/Qwen3.6-35B-A3B-FP8 repo_type=model checked=56
```

The API startup log independently reports the same revision, TP2, FP16 compute,
FP8 KV, 131,072-token limit, maximum 12 sequences, eager mode, and MTP2.
Docker inspection reports the same image digest and command.

## Start

The checked-in script is the exact contributor-host launcher:

```bash
bash vllm-qwen36-35b-fp8-b2-tp2.sh
```

Before use, inspect and change the host-specific `MODEL_REPO` path. The script
requires the selected revision to contain `config.json`, the safetensors index,
and every indexed shard before it creates a container.

> **Safety warning:** this exact launcher uses `--privileged`, host networking,
> host IPC, and `seccomp=unconfined`. It publishes an unauthenticated vLLM API on
> host port 8001. It also force-removes three named stale containers. Review and
> isolate it before use. These settings are preserved as measured identity, not
> recommended as a general deployment policy.

## TP2 transport workaround

The exact environment is:

```text
ZE_AFFINITY_MASK=0,1
CCL_ATL_TRANSPORT=ofi
FI_PROVIDER=tcp
FI_TCP_IFACE=lo
CCL_TOPO_P2P_ACCESS=0
CCL_ZE_IPC_EXCHANGE=pidfd
CCL_SEND=direct
CCL_RECV=direct
CCL_SYCL_ALLREDUCE_SIMPLE_THRESHOLD=4294967296
CCL_SYCL_REDUCE_SCATTER_SIMPLE_THRESHOLD=4294967296
CCL_SYCL_ALLGATHERV_SIMPLE_THRESHOLD=4294967296
CCL_SYCL_ALLTOALL_TMP_BUF=1
```

Intel suggested the four simple-collective variables for TP2 in issue #550.
The issue's reporter verified them on a two-B60 host without supported P2P. This
contributor then used the same thresholds with the listed TCP/direct transport
settings on two B70s. The offline-FP8 TP2 service reached health and completed
the evidence below.

This result does not establish that the two hosts have identical PCIe topology.
Current PCIe width probes on this host were inconsistent, so no width claim is
included.

## Clean triple benchmark

Tool identity:

```text
llama-benchy 0.4.1.dev1+ge9be34457
commit e9be344578cec17745066b220798b80a0d2686d3
```

Workload for every row:

- 1,024 prompt tokens;
- exactly 256 generated tokens;
- depth 0;
- prefix caching disabled;
- one warmup batch and five measured batches per concurrency;
- concurrency 1, 2, 4, 8, and 12;
- three complete sweeps;
- API-latency mode;
- coherence test passed before each sweep.

The table reports the mean of the three sweep means. Parentheses show the range
of complete sweep means.

| Concurrency | Prompt tok/s | Aggregate generation tok/s | Per-request generation tok/s | TTFR ms |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 5,257.02 (5,161.25–5,307.54) | 105.23 (103.63–107.19) | 105.23 (103.63–107.19) | 196.20 |
| 2 | 5,936.96 (5,824.81–6,018.25) | 185.77 (182.36–190.31) | 96.00 (93.88–97.59) | 314.66 |
| 4 | 6,647.52 (6,504.66–6,889.87) | 278.72 (269.62–285.31) | 74.55 (74.07–75.47) | 549.88 |
| 8 | 7,069.38 (6,928.32–7,170.50) | 401.02 (385.79–416.64) | 53.92 (53.73–54.27) | 1,050.66 |
| 12 | 6,955.95 (6,880.67–7,009.46) | **432.17** (427.33–434.63) | 44.93 (44.86–45.05) | 1,341.49 |

The clean peak in this tested range is 432.17 aggregate generation tok/s at
concurrency 12. It is not a single-request decode claim.

### Traffic isolation

The benchmark wrapper reads vLLM's successful-request counter before and after
each sweep. Its expected count is:

```text
2 tokenizer warmups + 1 coherence request
+ (1 warmup + 5 measured batches) * (1 + 2 + 4 + 8 + 12)
= 165 successful requests
```

Each sweep recorded exactly 165. The three counter intervals were 125→290,
290→455, and 455→620. This excludes the user traffic that contaminated the
superseded preliminary benchmark.

The historical boot fault count was 697 before and after each sweep. The
verified claim is only a zero delta during these sweeps. It does not classify
or attribute the earlier 697 events.

## Long-output gate

The current MTP2 service produced four saved responses:

| Artifact | Completion tokens | Result |
| --- | ---: | --- |
| `long-mtp-3x4096.json`, response 1 | 2,986 | pass, normal stop |
| `long-mtp-3x4096.json`, response 2 | 4,096 | pass, length stop |
| `long-mtp-3x4096.json`, response 3 | 2,406 | pass, normal stop |
| `final-mtp-1536.json`, response 1 | 1,536 | pass, length stop |
| **Total** | **11,024** | zero detector failures |

The validator checks complete saved content for empty output, short output,
`!!!!`, punctuation collapse, long identical-character runs, and low token
diversity. The four raw responses contain zero `!!!!` occurrences. This is a
bounded corruption test. It does not prove all future prompts are immune.

## GDN corruption fix context

Intel [llm-scaler PR #464](https://github.com/intel/llm-scaler/pull/464)
fixed an out-of-bounds XE2 GDN kernel write linked to intermittent all-`!`
generation on Qwen3.6 FP8 TP2. PR #464 merged on 2026-06-09. The
`vllm-0.21.0-b2` source tag at `f19b3294e63d49f1cfb90a1b6f5e3716237df5a9`
contains the `v_head_id >= num_v_heads` guard in its XPU-kernel patch.

The digest-pinned B2 service completed the bounded long-output and concurrency
tests without reproducing all-`!` output. The container does not ship inspectable
native source for a direct binary-to-source proof. Therefore, this packet does
not claim that PR #464 alone explains every prior corrupt output on this host.

## Evidence files

- `validation/VERIFICATION.md`: claim-by-claim evidence matrix.
- `validation/benchmark-clean-r1.json` through `r3.json`: raw benchmark output.
- `validation/benchmark-clean-r1-monitor.json` through `r3-monitor.json`: raw
  100 ms traffic and fault monitors.
- `validation/benchmark-clean-r1.txt` through `r3.txt`: CLI logs.
- `validation/benchmark-triple-summary.json`: independently recomputed summary.
- `validation/long-mtp-3x4096.json`: three complete saved MTP outputs.
- `validation/final-mtp-1536.json`: final saved MTP output.
- `validation/quality-manifest.json`: output hashes and detector counts.
- `validation/validate-long-output.py`: long-output harness.
- `validation/run-clean-benchmark.py`: contamination-rejecting benchmark wrapper.
- `validation/verify-evidence.py`: offline evidence auditor.

## Known limitations

- This is contributor-host evidence, not an independent reference-lab replay.
- FP8 KV uses runtime scale 1.0. No native-KV quality comparison was run.
- No fixed realistic-suite cache-zero telemetry gate was completed.
- The three benchmark sweeps used the same live service start.
- Eager mode was used. No graph-mode comparison was run.
- The recipe disables image and video inputs.
- MTP acceptance statistics were not preserved, so none are claimed.
- No no-MTP comparison is published here. Earlier no-MTP measurements were not
  repeated under the clean three-sweep traffic gate.
- The launcher retains broad container privileges and host networking.
