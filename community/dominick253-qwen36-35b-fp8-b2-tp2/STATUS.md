# STATUS — Qwen3.6 35B A3B offline FP8 TP2 on Intel B70

## Classification

| Field | Value |
| --- | --- |
| Evidence level | `community-reported` |
| Patch review status | contributor launcher read and executed on contributor host |
| Tested in reference lab | no |
| Safe to merge as documentation | yes, with the launcher safety warning |
| Eligible for `repro/` or `results/` | no; independent lab reproduction and strict quality gates remain incomplete |

## Provenance

- Contributor: `dominick253`.
- Source PR: [PR #18](https://github.com/steveseguin/b70-optimization-lab/pull/18).
- Contributor branch: `community/qwen36-int4-b2-1gpu`.
- Right-to-submit statement present: yes; the contributor explicitly requested
  this PR update under the repository contribution terms.
- Third-party material: Intel `llm-scaler` image and source, vLLM, PyTorch,
  `llama-benchy`, and Qwen model files. Their upstream licenses apply.
- Model weights are not included.

## Claim

The contributor reports that the digest-pinned Intel B2 image serves the
pre-quantized `Qwen/Qwen3.6-35B-A3B-FP8` checkpoint with TP2 and MTP2 on two
B70 GPUs. Three traffic-isolated sweeps averaged 432.17 aggregate generation
tok/s at concurrency 12 for pp1024/tg256. Four saved MTP outputs totaling
11,024 completion tokens contained no detected `!!!!` corruption.

## Contributor environment

| Field | Value |
| --- | --- |
| GPU model / count / VRAM | 2x Intel `8086:e223`; 34,242,297,856 bytes reported per device |
| GPU BDFs / interconnect | `03:00.0`, `08:00.0`; PCIe width omitted because current probes conflicted |
| OS / kernel | Ubuntu 26.04 LTS / `7.0.0-29-generic` |
| GPU driver | `xe`, srcversion `85B7CA089405934276CBAD3` |
| Container runtime | Docker; exact Docker version not recorded in this packet |
| Image | `intel/llm-scaler-vllm@sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e` |
| vLLM / XPU kernels / torch | `0.21.1.dev0+gad7125a43.d20260802.xpu` / `0.1.8.3.dev0+g3cab97a.d20260802` / `2.11.0+xpu` |
| Model repo and revision | `Qwen/Qwen3.6-35B-A3B-FP8` / `95a723d08a9490559dae23d0cff1d9466213d989` |
| Model artifact | 42 indexed shards present; 37,463,662,160 bytes; `hf cache verify --fail-on-missing-files` passed |
| Quantization | offline FP8 E4M3 block `[128,128]`; FP16 compute; `fp8_e4m3` KV with runtime scale 1.0 |
| Parallelism | TP2, PP1; eager mode |
| Context / batch | max model length 131,072; max sequences 12; max batched tokens 8,192 |
| Cache / speculation | prefix caching off; MTP2 enabled; no preserved acceptance statistic |
| Command and environment | `vllm-qwen36-35b-fp8-b2-tp2.sh` |
| Benchmark | `llama-benchy` commit `e9be344578cec17745066b220798b80a0d2686d3`; pp1024/tg256 exact, depth 0, c1/2/4/8/12, five measured plus one warmup, three sweeps |
| Quality gate | four saved long outputs, 11,024 completion tokens, complete-output repetition scan |
| Logs / JSON | `validation/` in this entry |

## Reference lab environment

Not run in the repository maintainer's reference lab. This contribution must not
be labeled `B70-tested` or `B70-verified` until the maintainer reproduces it.

## What was actually run

1. The Hugging Face cache verified 56 repository files at the pinned revision.
2. The index named 42 weight shards. All 42 existed locally.
3. Docker ran the pinned B2 image on two XPU devices.
4. vLLM logs resolved offline FP8, FP16 compute, TP2, FP8 KV, eager mode,
   131,072 context, 12 sequences, and MTP2.
5. Three complete `llama-benchy` sweeps ran on the same service start.
6. Every sweep passed its coherence test.
7. Every sweep generated exactly 165 successful requests, matching the harness.
8. The kernel fault counter did not increase during any sweep.
9. Four saved MTP responses passed the bounded corruption detector.
10. `validation/verify-evidence.py` recomputed all submitted numeric claims from
    the raw artifacts.

## Findings

1. The simple-collective threshold workaround from Intel issue #550 allowed TP2
   offline-FP8 startup on this contributor host when combined with the recorded
   TCP/direct oneCCL environment. The evidence does not isolate one variable as
   the sole cause.
2. Aggregate generation throughput increased through concurrency 12 in the
   tested pp1024/tg256 range. The three-sweep c12 mean was 432.168608 tok/s, with
   sweep means 434.540574, 434.631195, and 427.334057.
3. Per-request generation throughput decreased as concurrency increased. The
   c12 three-sweep mean was 44.930347 tok/s.
4. Prompt throughput peaked at c8 by the three-sweep mean: 7,069.377248 tok/s.
   The c12 prompt mean was 6,955.946243 tok/s.
5. The four saved current-MTP outputs totaled 11,024 completion tokens and
   contained zero `!!!!` occurrences.
6. The B2 source tag contains the GDN bounds guard from Intel PR #464. Runtime
   evidence did not reproduce the bounded all-`!` failure, but the binary does
   not provide direct source provenance for a one-cause attribution.

## Known issues

- The exact launcher uses broad container privileges, host networking, host IPC,
  and an unauthenticated endpoint. It is preserved as measured evidence, not as
  a generally safe deployment default.
- The launcher force-removes three specific container names before startup.
- FP8 KV logs a scale of 1.0 and warns about possible accuracy loss.
- No native-precision KV control or fixed realistic-suite equivalence test ran.
- Cached-token telemetry was not used as a promotion gate.
- All three benchmark sweeps used one service start. They are repeated workload
  measurements, not three cold model starts.
- Historical boot logs already contained 697 matching `xe` fault lines. The
  benchmark evidence establishes only zero new lines during each sweep.
- No clean three-sweep no-MTP control is included.
- The recipe is text-only and disables image/video inputs.

## Open questions

- Does the maintainer's reference lab reproduce TP2 startup and throughput?
- Does calibrated or native-precision KV change semantic quality or speed?
- Does a reduced-privilege, localhost-only launcher preserve the same result?
- Does a three-cold-start repetition produce the same throughput range?

## Disposition

Keep this as a separate `community/` entry. Do not replace the older dynamic-
FP8 B1 packet or the INT4 packet. Do not promote it to `results/`, `repro/`, or
LocalMaxxing until independent reproduction and the repository's fixed realistic
quality gate pass.
