# Reference-lab validation - 2026-08-08

## Scope and identity

The reference lab ran the exact contributor model revision and container image on two Intel Arc Pro B70 GPUs:

- model: `Qwen/Qwen3.6-35B-A3B-FP8` at `95a723d08a9490559dae23d0cff1d9466213d989`;
- image: `intel/llm-scaler-vllm@sha256:3f0a8c60fbaf376ec09538f093cba91f171238b99c117445c0bcc6096272ec3e`;
- vLLM: `0.21.1.dev0+gad7125a43.d20260802.xpu`;
- XPU kernels: `0.1.8.3.dev0+g3cab97a.d20260802`;
- TP2, FP16 compute, FP8 E4M3 KV, eager execution, MTP2, 131,072 context, 12 maximum sequences, and 8,192 batched tokens;
- benchmark: llama-benchy commit `e9be344578cec17745066b220798b80a0d2686d3`, pp1024/tg256 exact, concurrency 1/2/4/8/12, one warmup and five measured batches.

Raw artifacts are outside Git under:

`/mnt/fast-ai/llm-optimization-artifacts/community-dominick253/qwen36-35b-fp8-b2-tp2/`

The tested container filesystem and runtime configuration are backed up on the
USB at
`/mnt/usb-models/models/runtime-images/intel-llm-scaler-vllm-b2-3f0a8c60.tar.zst`
(5,157,140,427 bytes; SHA-256
`7ed46ef7f9e26a1b8a3ec5a5bcf57c0994b35b0bd12893d983b6328b3552a0e2`).
Docker 29's containerd image store could export only an index for the original
digest reference, so the archive was materialized with a no-op `FROM` build.
Its architecture, OS, complete image config, and RootFS layer identities were
compared with the exact digest and match, but loading the archive restores the
local tag `community-b2-export:3f0a8c60`, not the registry digest name. Re-pin
the source digest when online.

## Launcher bring-up

The initial reduced-privilege launcher failed before model load. oneCCL
reported pidfd as unsupported, fell back to DRM FD exchange, and failed with
`opendir failed: could not open device directory`. Adding host IPC alone did
not fix it. Adding `CAP_SYS_PTRACE` as well, while retaining Docker's default
seccomp profile, allowed TP2 initialization and model load. This A/B sequence
is consistent with a pidfd permission issue but does not retain a syscall trace
or errno proving the exact denial. The maintained launcher now uses
`--ipc=host` and `--cap-add=SYS_PTRACE`; it still does not use `--privileged`,
host networking, unconfined seccomp, restart persistence, or a non-loopback
publication. It remains a trusted-local-workload launcher because the rootful
container gets every `/dev/dri` node, host IPC, `CAP_SYS_PTRACE`, and a nominal
200 GiB shared-memory allocation.

Failed-start logs are retained in `20260808-reference-lab-a` and `20260808-reference-lab-b`. The successful hardened run is `20260808-reference-lab-c`.

## Throughput result

Both sweeps completed exactly 165 successful requests with no benchmark error.
The operator's post-run scans found no new matching `xe` fault lines, but the
artifact directories retain only empty scan outputs rather than the commands,
journal ranges, and exit statuses needed for a durable no-fault proof.

| Concurrency | Contributor three-sweep mean | Hardened lab run | Contributor-privilege control |
| ---: | ---: | ---: | ---: |
| 1 | 105.228 | 54.865 | 52.613 |
| 2 | 185.767 | 99.417 | 99.052 |
| 4 | 278.716 | 155.423 | 161.965 |
| 8 | 401.022 | 213.680 | 203.047 |
| 12 | 432.169 | 268.866 | 286.003 |

The contributor-privilege control used `--privileged`, host networking, host
IPC, and unconfined seccomp, but bound the endpoint to loopback and disabled
restart persistence. It reached only 66.2% of the reported c12 mean. Container
hardening therefore does not explain the missing throughput. The operator
recorded local kernel `7.0.0-28-generic` versus contributor
`7.0.0-29-generic`, and a matching `xe` driver srcversion, but the host identity
command output is not retained in these raw directories. No causal attribution
is made beyond those observations.

## Functional and bounded quality checks

- A no-thinking arithmetic request returned `323` for `17 * 19`.
- llama-benchy's coherence gate passed in both 165-request sweeps.
- The contributor's long-output checker passed three independent 1,536-token responses with no empty visible output, punctuation collapse, low diversity, or repeated-character failure. The median end-to-end output rate was 49.210 tok/s.
- The operator observed an empty final device scan and both selected GPUs idle
  after teardown; the exact scan command, exit status, and post-run device
  output were not retained in the artifact directories.

These checks establish that the exact model/image/runtime identity is runnable
under the maintainer-reduced B70 container configuration. They do not reproduce
the contributor's exact deployment surface or establish FP8-KV semantic
equivalence to a native-KV teacher.

## Disposition

Raise this packet to `B70-tested`, but keep it in `community/`. The reported 432.17 tok/s c12 claim was not reproduced and must remain contributor-host evidence. Nothing in this run qualifies the packet for `results/`, `repro/`, or LocalMaxxing.
