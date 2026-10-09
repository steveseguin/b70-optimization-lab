# Flash-Next runtime comparison — 2026-10-09 UTC

**The failing image has newer NEO/IGC/Level Zero drivers than the working
host, but older SYCL/UR, Torch and Triton.** The shared image stack is a
credible investigation target, not a proven common cause. The three faults
have different immediate circumstances: loading under memory pressure,
first model forward, and tiny-probe worker teardown. The evidence does not
support calling all three an OOM-teardown or host-USM-free bug.

Try **the host UMD bind overlay first**, in a later admitted single-card
window, because it changes the driver/compiler boundary while retaining the
same probe and Python stack. All twelve locally available alternative image
IDs contain the same NEO/IGC/L0 as the failing image, so none is the requested
host-matched replacement. Remedy B below is an explicitly **unbuilt**
host-UMD image design, with an exact construction command instead of an
invented matching tag or digest.

This review was CPU-only on `steve-b70s`, kernel `7.0.0-39-generic`, xe.
Containers used a shell entrypoint, no network and no devices. Metadata,
ELF dependency/relocation checks, saved evidence, kernel journal and an
existing process's library mappings were read. No GPU initialization,
Torch import, package installation, power/memory setting change, service
operation, or remedy execution occurred. The protected LTX tree, model
storage, run directories and secrets were untouched. The owner's report of
a fault-free LTX day is a useful contrast, not a matched workload control.

## Runtime inventory

Failing image, abbreviated `e444` below:

```text
vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9
Created: 2026-09-21T22:50:18.89466892Z
```

| Layer / package | Image e444 | Host / `/home/steve/.venvs/ltx25-baseline` | Image relative to host |
| --- | --- | --- | --- |
| NEO: `libze-intel-gpu1`, `intel-opencl-icd`, `intel-ocloc` | `26.27.39122.11-0` | `26.18.38308.1-0` | Newer |
| IGC: `intel-igc-core-2`, `intel-igc-opencl-2` | `2.38.2` | `2.34.4` | Newer |
| Level Zero: `libze1`, `libze-dev` | `1.32.0` | `1.28.2-1~24.04~ppa1` | Newer |
| GMM: `libigdgmm12` | `22.10.1-1~24.04~ppa1` | `22.10.0` | Newer package; both real library names end `12.10.0` |
| `dpcpp-cpp-rt`, `intel-cmplr-lib-rt`, `intel-cmplr-lib-ur` | all `2026.0.0` | all `2026.1.0` | Older |
| `intel-cmplr-lic-rt`, `intel-opencl-rt`, `intel-openmp`, `intel-sycl-rt` | all `2026.0.0` | all `2026.1.0` | Older |
| `oneccl`, `oneccl-devel` | `2022.0.0` | `2022.1.1` | Older |
| `intel-pti` | `0.17.0` | `1.0.1` | Older |
| Torch | `2.13.0+xpu` | `2.14.0+xpu` | Older |
| Triton distribution metadata | `triton 3.7.2+xpu` and `triton-xpu 3.7.2` | `triton-xpu 3.8.0` | Older; two image metadata records do not prove two active backends |
| vLLM / XPU kernels | `0.30.0+xpu` / `0.1.14.1` | Not the LTX application path | Different application |
| glibc: `libc6` | `2.39-0ubuntu8.9` | same | Equal |
| `libstdc++6` | `14.2.0-4ubuntu2~24.04.1` | same | Equal; supplies `GLIBCXX_3.4.33` |

Host apt also contains oneAPI compiler runtimes `2025.3.3-30` and
`2026.0.0-947`; these are not the SYCL libraries resolved by the LTX venv.
The old installed `libigc1 1.0.15468.25-2ubuntu0.1` has a separate `.so.1`
ABI and is not its active `.so.2` compiler. LTX's additional metadata is
MKL `2026.1.0`, TBB `2023.1.0`, UMF `1.1.0`, TCM `1.5.0`, torchaudio
`2.11.0+xpu`, torchvision `0.29.0+xpu`. No versions were inferred from a
mutable image tag or Python GPU discovery.

### Actual library resolution, not just package labels

Both Torch builds have `DT_RPATH=$ORIGIN/../../../..:$ORIGIN`.
`ldd libtorch_xpu.so` resolves SYCL, UR loader, oneCCL, PTI and MKL from
`/opt/venv/lib` in the image and the LTX venv's `lib/` on the host. NEO and
Level Zero are dynamically loaded later, so `ldd` on Torch alone cannot
identify their active paths.

| Library | Image file / expected dynamic resolution | Host file, confirmed loaded in existing LTX PID 223465 |
| --- | --- | --- |
| NEO Level Zero | `/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.39122` | `/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38308` |
| L0 loader | `/usr/lib/x86_64-linux-gnu/libze_loader.so.1.32.0` | `/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.2` |
| L0 tracing | image package `1.32.0` | `/usr/lib/x86_64-linux-gnu/libze_tracing_layer.so.1.28.2` |
| IGC | `/usr/local/lib/libigc.so.2.38.2+1782393643` | `/usr/local/lib/libigc.so.2.34.4+1778234987` |
| IGDFCL | `/usr/local/lib/libigdfcl.so.2.38.2+1782393643` | `/usr/local/lib/libigdfcl.so.2.34.4+1778234987` |
| GMM | `/usr/lib/x86_64-linux-gnu/libigdgmm.so.12.10.0` | same path, different package/bytes |
| SYCL | `/opt/venv/lib/libsycl.so.9.0.0` | venv `/lib/libsycl.so.9` |
| UR adapters | `/opt/venv/lib/libur_adapter_level_zero{,_v2}.so.0.12.0` | venv `/lib/libur_adapter_level_zero{,_v2}.so.0` |

The host paths above came from **read-only `/proc/223465/maps`**, not a new
GPU process. Both UR adapters were mapped; their presence alone does not
identify which adapter handled each operation. No competing NEO or L0-loader
copies were found in either venv. The image's OpenCL NEO is
`/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so`; its IGA is
`/usr/local/lib/libiga64.so.2.38.2+1782393643`. The image's baked
`LD_LIBRARY_PATH` is `/opt/ucx/lib:/opt/venv/lib:/usr/local/lib`; it does not
bake the NEO or ZE flags. The pip `intel-opencl-rt` runtime is distinct from
the apt GPU OpenCL ICD.

Reproducible CPU inventory commands (metadata and ELF inspection only):

```bash
image=vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9
docker image ls --digests --no-trunc
docker run --rm --pull=never --network=none --entrypoint /bin/bash "$image" -c '
  dpkg -l | grep -iE "level-zero|opencl|igc|compute|intel|libze|libigdgmm|libc6:|libstdc"
  /opt/venv/bin/python -m pip list 2>/dev/null | grep -iE "intel|dpcpp|oneccl|pti|torch|triton|vllm"
  ls /opt/venv/lib/python3*/site-packages | grep -i intel
  readlink -f /usr/lib/x86_64-linux-gnu/libze_loader.so.1
  ldd /opt/venv/lib/python3*/site-packages/torch/lib/libtorch_xpu.so
  ldd /opt/venv/lib/libur_adapter_level_zero.so.0
  ldd /usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1
'
dpkg -l | grep -iE 'level-zero|opencl|igc|compute|intel|libze|libigdgmm|libc6:|libstdc'
/home/steve/.venvs/ltx25-baseline/bin/python -m pip list 2>/dev/null |
  grep -iE 'intel|dpcpp|oneccl|pti|torch|triton'
ldd /home/steve/.venvs/ltx25-baseline/lib/python3.12/site-packages/torch/lib/libtorch_xpu.so
ldd /home/steve/.venvs/ltx25-baseline/lib/libur_adapter_level_zero.so.0
ldd /usr/lib/x86_64-linux-gnu/libze_loader.so.1
```

`pip list` reads installed distribution metadata; no `torch` or `torch.xpu`
module is imported. No inspection container had a device mapping.

## Fault chronology: three incidents, different triggers

All times below are UTC. Saved log timestamps ending `-04:00` are converted,
not treated as UTC. The attempt-7 analysis requested as `notes/...` is actually
[the lane note](2026-10-08-attempt7-gpu-fault-analysis.md).

The saved Screen 1 `kernel-oom-and-fault-window.log` contains only
`-- No entries --`; its `kernel-latest.log` does not contain the incident.
For this review the retained kernel journal was read directly, without sudo,
using boot `1019201097004915ac6c980d6b74afa0`. Attempt 7's saved fault window
agrees with that journal. The probe is on boot
`4aafe57ba54f4bfdb4ed9f1cbb8830c7`.

| Incident | First fault diagnostic | First response / reset | State before fault |
| --- | --- | --- | --- |
| Screen 1, Oct 8 | 14:04:34.983054, card 43, BCS, VA `0x00008005848aa000`, ASID 920, access 1, level 2 | **`-EBUSY`**, 14:04:34.984196; BCS reset 14:04:34.984598 | Loading; no preceding OOM kill or recorded stop. This is not a first-`-ENOENT` incident. |
| Attempt 7, Oct 8 | 21:11:18.369060, card 47, CCS, VA `0x00000000f4725000`, ASID 1164, access 1, level 3 | `-ENOENT`, 21:11:18.371641; CCS CAT errors/reset follow across all four cards | Initial 64-token dummy/profile forward after weight loading; controller SIGINT follows first fault by **0.7444 s**. |
| Tiny probe, Oct 9 | 01:39:27.868140, card 23, BCS, VA `0x0000d556a74c0000`, ASID 8, access 0, level 4 | `-ENOENT`, 01:39:27.868476; BCS reset 01:39:27.868648 | Gather byte comparison passed; GPU worker returns/releases locals/exits while CPU parent retains receipt. |

### Every kernel line in the preceding ten seconds

Querying **all** kernel entries, without a fault-only filter, gives **zero
entries** in each half-open interval below (first diagnostic excluded):

- Screen 1: `[2026-10-08 14:04:24.983054, 14:04:34.983054)`.
- Attempt 7: `[2026-10-08 21:11:08.369060, 21:11:18.369060)`.
- Probe: `[2026-10-09 01:39:17.868140, 01:39:27.868140)`.

If “first fault” means the response line instead of its diagnostic, the
following are **all** additional lines preceding that response. Each block
is one multiline journal entry. No allocation-free, exit, OOM-kill or
container-stop entry is interposed.

```text
2026-10-08T14:04:34.983054+00:00 steve-b70s kernel: xe 0000:43:00.0: [drm] Tile0: GT0:
    ASID: 920
    Faulted Address: 0x00008005848aa000
    FaultType: 0
    AccessType: 1
    FaultLevel: 2
    EngineClass: 3 bcs
    EngineInstance: 0

2026-10-08T21:11:18.369060+00:00 steve-b70s kernel: xe 0000:47:00.0: [drm] Tile0: GT0:
    ASID: 1164
    Faulted Address: 0x00000000f4725000
    FaultType: 0
    AccessType: 1
    FaultLevel: 3
    EngineClass: 5 ccs
    EngineInstance: 0

2026-10-09T01:39:27.868140+00:00 steve-b70s kernel: xe 0000:23:00.0: [drm] Tile0: GT0:
    ASID: 8
    Faulted Address: 0x0000d556a74c0000
    FaultType: 0
    AccessType: 0
    FaultLevel: 4
    EngineClass: 3 bcs
    EngineInstance: 0
```

Reproduce the unrestricted windows (a fractional `--until` just before the
first diagnostic will print `-- No entries --`):

```bash
journalctl -k --boot=1019201097004915ac6c980d6b74afa0 \
  --since '2026-10-08 14:04:24.983054 UTC' \
  --until '2026-10-08 14:04:34.984196 UTC' --utc -o short-iso-precise --no-pager
journalctl -k --boot=1019201097004915ac6c980d6b74afa0 \
  --since '2026-10-08 21:11:08.369060 UTC' \
  --until '2026-10-08 21:11:18.371641 UTC' --utc -o short-iso-precise --no-pager
journalctl -k --boot=4aafe57ba54f4bfdb4ed9f1cbb8830c7 \
  --since '2026-10-09 01:39:17.868140 UTC' \
  --until '2026-10-09 01:39:27.868476 UTC' --utc -o short-iso-precise --no-pager
```

**Screen 1 ordering:** repeated `-EBUSY` follows the BCS fault through
14:04:43.257147. `docker invoked oom-killer` is logged at
14:04:44.976882, first kernel kill at 14:04:45.026078 (`python3`, PID 755946),
Docker CLI kill at 14:04:45.546343 (PID 756872), and the model worker kill at
14:04:51.878504 (`VLLM::Worker_TP`, PID 757710). The systemd unit records its
main-process kill at 14:04:44.983113, also after the GPU fault. Thus memory
pressure can be a contributor, but the OOM kill cannot explain the initial
fault as teardown. The saved graceful-stop receipt has no timestamp; it
cannot establish a pre-fault stop. No USM-free trace exists.

**Attempt 7 ordering:** the journal has no pre-fault free/exit/OOM/stop line.
The saved `graceful-stop.json` monotonic time 367710.872428586 minus the first
kernel entry's monotonic 367710.128027 gives the 0.7444 s delay above. The
container exits at 21:13:16.461307608, code 1, `OOMKilled=false`.
The recovery snapshot's `GFP_ATOMIC order:9` allocation failure follows the
faults, not vice versa. No allocation-lifetime tracing was enabled, so lack
of a kernel free message does **not** prove that every USM mapping stayed live.

**Probe correction:** the earlier [slab note](2026-10-09-slab-probe-result.md)
interprets `bytes_equal_waiting_postflight` as a still-live GPU process idling.
The hash-matched [source](../reopen-20261008/probe/single_rank_slab_probe.py)
(SHA256 `4bd8d426d6964f113d7b2f3c46cc67b11de081c29f83bdc38b86c6818c80183d`)
shows otherwise: `run_device()` saves that stage then returns, dropping local
owners; the GPU child calls `os._exit(0)`. The CPU parent calls `waitpid()`
**before** setting `postflight_requested_unix`. The
[receipt](../reopen-20261008/runs/probe-indirect-20261009/receipt.json) records
`worker_wait_status=0`, no forwarded signals, and that timestamp as
`1791509967.8684642` = 01:39:27.868464 UTC. Worker exit was therefore observed
by the time of the first `-ENOENT` journal timestamp, while the parent/container
could remain alive. The first diagnostic is 324 microseconds earlier than
that receipt time. Journal collection and user-space timestamps cannot order
the initiating GPU access against exit that precisely.

This is a **teardown-associated** BCS fault, consistent with a mapping/event/
internal-buffer lifetime problem. It is not proof that a particular host-USM
free caused it: there is no free trace, `os._exit` skips normal interpreter
shutdown, and the recorded VA matches none of the application's recorded
buffers. The gather's byte pass establishes the small indirect read; it
neither certifies the full MoE kernel nor establishes a universal residency
failure. Attempt 7 is an active-forward fault; Screen 1 is a loading/pressure
fault. All share the image stack, not a demonstrated common free operation.

## Upstream and local source review

The image UMD is **newer**, not older: NEO 26.27.39122.11 / IGC 2.38.2 / Level Zero loader 1.32.0 versus host NEO 26.18.38308.1 / IGC 2.34.4 / loader 1.28.2. Intel's release manifests explicitly associate those NEO versions with those IGC and loader revisions. Image NEO was released 2026-07-21; host NEO 2026-05-12. The 26.27 release's corrected validation notes name Battlemage testing on kernel 7.1.0-rc5, not this host's 7.0.0-39. That is a support/test-coverage difference, not proof that 7.0 is incompatible. The SYCL/UR wheel ordering goes the other way (image 2026.0.0, host 2026.1.0), so “newer image runtime” must not collapse all layers into one version.

Sources: [NEO 26.27 release](https://github.com/intel/compute-runtime/releases/tag/26.27.39122.11), [NEO 26.18 release](https://github.com/intel/compute-runtime/releases/tag/26.18.38308.1).

### Closest known reports and their limits

| Evidence | Relation to these incidents | What it does not establish |
| --- | --- | --- |
| [compute-runtime #948, September 4 comment](https://github.com/intel/compute-runtime/issues/948#issuecomment-5536265115): same NEO 26.27.39122.11, single B60, OpenVINO/OpenCL; allocation log matches CCS and BCS fault VAs to driver-owned `SEMAPHORE_BUFFER` allocations. | Strong lead for the 0xd556… address class: inspect runtime direct-submission ring/semaphore lifetime and residency. | Different application/card. The reporter labels eviction/residency diagnosis unconfirmed. No allocation log yet identifies tonight's exact buffer. |
| [#948, September 24 comment](https://github.com/intel/compute-runtime/issues/948#issuecomment-5816792046): a healthy busy-process kill generated BCS ENOENT/EINVAL with fault VA `0xd556a74c0000`. | Exactly tonight's numeric VA; supports checking child exit/teardown before assigning the fault to gather arithmetic. | Address equality across processes is not buffer identity or proof of a host-USM-free bug. Their incident VA differed; their idle-kill control did not fault. |
| [#953](https://github.com/intel/compute-runtime/issues/953), especially [Intel's defer-backing diagnosis](https://github.com/intel/compute-runtime/issues/953#issuecomment-4991177897). | Known 26.09+ multi-GPU device-USM host-memory mirroring regression; disabling defer backing was proposed and confirmed by the reporter. This is relevant to the 14:04 memory-pressure arm. | Does not explain a small one-card probe without memory pressure, nor prove that host-USM free preceded a fault. |
| [#973](https://github.com/intel/compute-runtime/issues/973). | Demonstrates an allocation can remain cached after a failed bind evicts it: per-dispatch private surfaces on immediate command lists need re-declaration as resident. | Arc A770, private scratch, repeated dispatch after failed VM_BIND, silent corruption. Not an exact first-indirect-access/CAT or teardown match; host 26.18 is affected too. |
| [#865 resolution](https://github.com/intel/compute-runtime/issues/865#issuecomment-3768096655). | A nonblocking host-to-SVM copy crash was resolved by removing a conflicting old GMM library. Relevant to complete dependency closure and avoiding mixed UMDs. | Tiger Lake/OpenCL and mismatched GMM, not this B70 fault. No evidence that the current image's GMM is itself mismatched. |

#946 is superseded by #948, not a resolved fix: [reporter refiling comment](https://github.com/intel/compute-runtime/issues/946#issuecomment-4885840180).

No reviewed upstream release note or issue proves an exact “USM host free causes BCS ENOENT” or “first indirect pinned-host access causes CCS CAT” defect for this stack. These are leads, not confirmed matches. In particular, the byte-correct gather establishes correctness for that tiny launch; it does not clear every production gather shape or every asynchronous runtime operation.

### Flags: what they change, and what they cannot prove

- `NEOReadDebugKeys=1` enables reading debug keys in Linux release builds. It is the gate that lets `EnableDeferBacking=0` take effect; it is not itself a memory placement policy. It also permits any other inherited debug keys, so a proposed controlled comparison should preserve only explicitly recorded keys. [Pinned NEO FAQ](https://github.com/intel/compute-runtime/blob/26.27.39122.11/documentation/FAQ.md#how-can-i-enable-reading-debug-environment-variables-on-linux-release-builds).
- At image tag 26.27, `EnableDeferBacking` is defined as xe backing control, default -1 (enabled), 0 disabled, 1 enabled. **Defer backing is not deferred freeing.** Disabling it changes GEM allocation backing; it does not establish a synchronization guarantee at `zeMemFree`, Python destructor, or process exit. [Pinned debug variable source](https://github.com/intel/compute-runtime/blob/26.27.39122.11/shared/source/debug_settings/debug_variables_base.inl#L569).
- The #953 discussion first called the debug workaround safe, then [retracted that production advice](https://github.com/intel/compute-runtime/issues/953#issuecomment-5164715227). Intel later [reported a fix in 26.35.39758.10](https://github.com/intel/compute-runtime/issues/953#issuecomment-5713654169); one B70 reporter confirmed it, while another B60/Linux-7.0 reporter still saw host OOM, which Intel classified as a separate issue. That is no basis to silently drop the lab's measured `EnableDeferBacking=0` setting or declare a runtime upgrade cures these faults.
- `ZE_FLAT_DEVICE_HIERARCHY=FLAT` changes device hierarchy/enumeration. The image's pinned source reads it directly with `EnvironmentVariableReader`, independently of `NEOReadDebugKeys`; it is not a USM lifetime or synchronization fix. Changing it alongside the UMD would confound the comparison and may change device ordinals. [Pinned implementation](https://github.com/intel/compute-runtime/blob/26.27.39122.11/shared/source/execution_environment/execution_environment.cpp#L337), [Intel SYCL environment documentation](https://github.com/intel/llvm/blob/sycl/sycl/doc/EnvironmentVariables.md).

Local evidence read without opening the protected LTX tree: `docs/host-stability-and-fault-diagnosis.md` lines 413 onward documents the two-card host's separate 26.27 external-host-pointer upload fault and allocation-log attribution; lines 433 onward records the four-card host's memory mirroring and clean results with the same defer-backing flags. The flags therefore are not unique to failing Flash-Next workloads. Screen 1's saved launch has neither debug/backing override; attempt 7 and the tiny probe have both. All three explicitly select `ZE_FLAT_DEVICE_HIERARCHY=FLAT`. Thus the debug pair is not a setting common to all three failures, and FLAT has no demonstrated causal role. The upload incident is analogous evidence for runtime-created host mappings, not confirmation of tonight's allocation type.

Verdict: the image stack plus xe memory mapping/lifetime path is a credible common *investigation target*. There is no controlled UMD-only A/B yet, so “container NEO regression is the common cause” remains unproved. Application workload, PyTorch allocator, Triton, SYCL/UR, process lifetime, and memory pressure differ from LTX. Same cards/kernel and a fault-free LTX day strengthen a software-path hypothesis but do not isolate the layer.

## Dependency closure and ABI preflight

NEO L0 and OpenCL depend on GMM plus standard C/C++ libraries. IGC depends on zlib/zstd plus standard C/C++ libraries. IGDFCL also needs **`libopencl-clang2.so.16`**, unlike image IGC's `.so.17`; this difference must be included. IGA has standard C/C++ dependencies. L0 loader/tracing/validation use standard C/C++ libraries. No direct libdrm dependency appeared in this closure.

Executed CPU-only ABI preflight: twelve host libraries were mounted read-only under `/opt/host-umd` into the failing image, with `--network=none`, explicit `/bin/bash` entrypoint, no devices. `LD_LIBRARY_PATH=/opt/host-umd ldd -v -r` on every file returned no missing libraries, missing symbol versions or undefined symbols. The inspection used temporary files only; the closure and repeatable commands are retained below. This checked loader relocations only, not GPU functionality. Image and host libc6/libstdc++ package versions are exactly equal. Host NEO/loader require at most GLIBC 2.38 / GLIBCXX 3.4.32; IGC at most GLIBC2.38 / GLIBCXX3.4.31; image supplies glibc2.39 / GLIBCXX3.4.33.

## Remedy A: host UMD bind overlay — design, not executed

Mount onto the image's resolved real files, preserving all its existing aliases and preventing RPATH or absolute driver discovery from bypassing the override. The original image's file names remain visible inside the container even though their bytes come from older host packages: record mounts and source hashes rather than believing those filenames. Include optional tracing/validation layers because LTX actually loads tracing. Keep the image's libc, libstdc++, SYCL, UR, torch and oneCCL unchanged so the first trial tests the UMD boundary only.

```bash
image=vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9
host_umd_mounts=()
while IFS='|' read -r source target; do
  host_umd_mounts+=(--mount "type=bind,src=$source,dst=$target,readonly")
done <<'MOUNTS'
/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38308|/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.39122
/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so|/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so
/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.2|/usr/lib/x86_64-linux-gnu/libze_loader.so.1.32.0
/usr/lib/x86_64-linux-gnu/libze_tracing_layer.so.1.28.2|/usr/lib/x86_64-linux-gnu/libze_tracing_layer.so.1.32.0
/usr/lib/x86_64-linux-gnu/libze_validation_layer.so.1.28.2|/usr/lib/x86_64-linux-gnu/libze_validation_layer.so.1.32.0
/usr/lib/x86_64-linux-gnu/libigdgmm.so.12.10.0|/usr/lib/x86_64-linux-gnu/libigdgmm.so.12.10.0
/usr/local/lib/libigc.so.2.34.4+1778234987|/usr/local/lib/libigc.so.2.38.2+1782393643
/usr/local/lib/libigdfcl.so.2.34.4+1778234987|/usr/local/lib/libigdfcl.so.2.38.2+1782393643
/usr/local/lib/libiga64.so.2.34.4+1778234987|/usr/local/lib/libiga64.so.2.38.2+1782393643
/usr/local/lib/libopencl-clang2.so.16|/usr/local/lib/libopencl-clang2.so.16
/usr/lib/x86_64-linux-gnu/libz.so.1.3|/usr/lib/x86_64-linux-gnu/libz.so.1.3
/usr/lib/x86_64-linux-gnu/libzstd.so.1.5.5|/usr/lib/x86_64-linux-gnu/libzstd.so.1.5.5
MOUNTS
# First repeat static relocation checks in precisely the proposed layout.
# This command remains CPU-only and cannot test GPU correctness.
docker run --rm --pull=never --network=none --entrypoint /bin/bash \
  "${host_umd_mounts[@]}" "$image" -c '
    set -eu
    export LD_LIBRARY_PATH=/usr/local/lib:/opt/ucx/lib:/opt/venv/lib
    for f in /usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1 \
      /usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so \
      /usr/lib/x86_64-linux-gnu/libze_loader.so.1 \
      /usr/lib/x86_64-linux-gnu/libze_tracing_layer.so.1 \
      /usr/lib/x86_64-linux-gnu/libze_validation_layer.so.1 \
      /usr/lib/x86_64-linux-gnu/libigdgmm.so.12 \
      /usr/local/lib/libigc.so.2 /usr/local/lib/libigdfcl.so.2 \
      /usr/local/lib/libiga64.so.2 /usr/local/lib/libopencl-clang2.so.16 \
      /usr/lib/x86_64-linux-gnu/libz.so.1 /usr/lib/x86_64-linux-gnu/libzstd.so.1; do
      report=$(ldd -v -r "$f" 2>&1) || { printf "%s\n" "$report"; exit 1; }
      printf "%s\n" "$report"
      if printf "%s\n" "$report" | grep -Eq "not found|undefined symbol"; then
        exit 1
      fi
    done
  '
```

Only a later authorized, preregistered GPU campaign should add these mount arguments to the unchanged bounded probe launcher. No GPU launch is part of this task. Preserve `EnableDeferBacking`, `NEOReadDebugKeys` and `ZE_FLAT_DEVICE_HIERARCHY` between control/candidate initially; changing these together with UMD would confound causality.

Risks: ABI relocation success is necessary but does not prove driver feature compatibility with image SYCL/UR or the workload; older UMD may lack extensions assumed by newer clients. Host package upgrades would change bind sources, so pin hashes immediately before a future trial. The image's package metadata will describe original bytes, so retain this overlay manifest. This is a reversible, container-local rollback; no host libraries are changed. It still cannot eliminate a kernel/driver or application allocation-lifetime bug.

## Closure SHA256 recorded at inspection

| Host real file | SHA256 |
|---|---|
| `/usr/lib/x86_64-linux-gnu/libze_validation_layer.so.1.28.2` | `50115b6679a89f4dfee36384fd7667a7f22f5e8d094d412da4fd86304397973c` |
| `/usr/lib/x86_64-linux-gnu/libze_tracing_layer.so.1.28.2` | `ed9405ce2cd588f7ca78a777865de6d6e3d0d4776fd70b89c6e5ca4826fba59e` |
| `/usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1.15.38308` | `26fa68779adb03b200a8c3001cf81e59fc9a3d63e0f38627ec0005ffce574e7a` |
| `/usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so` | `0cfd5ba1211615558b2f8f3912451889949c0a75245a1f3fd5ee6dbf9fd338bf` |
| `/usr/lib/x86_64-linux-gnu/libze_loader.so.1.28.2` | `0fe232b18985ae078dd546b57bc6d11bacf1030834c0544f7e3feb53ed71c1d0` |
| `/usr/lib/x86_64-linux-gnu/libigdgmm.so.12.10.0` | `41892701dc8de4a9086653e1599c533f40e8e28baf435df27cab70ec2d0b9526` |
| `/usr/local/lib/libigc.so.2.34.4+1778234987` | `5dbf0da8af02783b7770b9294485a034ce9756cf6bcdbed95d9a3b6d10f0674a` |
| `/usr/local/lib/libigdfcl.so.2.34.4+1778234987` | `f9b9db2bc681f44040f3c29fbd17de5ec1bb82dd92921a8022b992b0e02e50e5` |
| `/usr/local/lib/libiga64.so.2.34.4+1778234987` | `79adaf47e87ff5c6df0608b74fa71019e83f2c049b439e9ec59acca5d3457215` |
| `/usr/local/lib/libopencl-clang2.so.16` | `bff108c0dc259768a574372e1d33e3101543da4f2453a47f4296152aa314519d` |
| `/usr/lib/x86_64-linux-gnu/libz.so.1.3` | `86200da370f20476a2507e9097a789b5ef97269b4ca8d5e164ad82dab9d99892` |
| `/usr/lib/x86_64-linux-gnu/libzstd.so.1.5.5` | `0a2128bc10841fb29e76d08d945864dfb0b6a66da5df6df5d8299197439e54bb` |

## Remedy B: alternative image — local candidates rejected; derived image unbuilt

All **13 unique local vLLM image IDs** were inspected without devices. Every
one has NEO `26.27.39122.11`, IGC `2.38.2`, L0 loader `1.32.0`, Torch
`2.13.0+xpu`, DPC++/SYCL/UR `2026.0.0`, PTI `0.17.0`, oneCCL `2022.0.0`.
The twelve alternatives have GMM `22.10.0`, glibc `2.39-0ubuntu8.8`,
Triton-XPU `3.7.2`, and vLLM `0.27.2rc1.dev77+gac7509e2b.xpu`.
They would change application code and possibly lab patches while keeping
the suspected UMD. They are **not a host-runtime remedy**.

| Local repository/tag (`neural-download/vllm-openai-xpu` unless shown) | Immutable local ID / listed digest (SHA256) |
| --- | --- |
| `vllm/vllm-openai-xpu`, failing | `e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9` |
| `vllm/vllm-openai-xpu`, older base | `f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f` |
| `qwen38-int4-r276-dynsd-catchup` | `2546382461a4016ff7ea26ee264be922fc8825f580b9100ae1f53ad8988b5a8b` |
| `qwen38-int4-r276-dynsd-fullgraph` | `bd3fa3af93b1463633c55e22b5ac3087bc9f67e710c1286a8c596a82a019bdba` |
| `qwen38-int4-r276-dynamic-mamba-alloc` | `679f176c5be8c634343190c30cdb3e9ccb64b0bb9e807009e78a5c5bd734bd6a` |
| `qwen38-int4-gdn-spec-group-sync-free-r276` | `521eb277c0733f8c2ce47aea1bb98ed576c6f1ad63bf5baf22d38fc07abf54ad` (local ID only; no RepoDigest) |
| `qwen38-fp8-mtp1-fixed-k-w8a16-r139` | `cbe09ce2f8b82133d213fcde9a0bb3c33ce16d23f8dbab354d9d22276945885b` |
| `qwen38-fp8-mtp1-draft-only-int4-r62` | `982f3fb6fbe7fdc6c38c856eb2b599fe21647eb6585acd71edafb23664e9f6a7` |
| `qwen38-fp8-mtp1-r55c-public-binaries` | `1d1dd0a2a6b55310aded558478da0ed31b539e9eaf0a9eb39daebf913a22aaf6` |
| `qwen38-fp8-mtp1-serial-attention-r49` | `59bd6b2bcb1b77ecb37d07e0bd9d5da9547de3e45c6456d7608be02971eab7ec` |
| `qwen38-fp8-mtp1-rms-serial-r31` | `a485e20ac89823f514a885e123d9de2a429955120f41f57a02f7d2a0b4a307e0` |
| `qwen38-fp8-collective-work-wait-r15` | `d677dc4b24988f1381c6ede7df82dcda467351ea9a67a3dcb17412af53996719` |
| `f01e-kernel-1e90-r13` | `88b612e8ac736e610601e8264e0ee0718595ae723d9f64d56baa664e29fa606d` |

For example, substituting this exact alternative in the inventory command
reproduces the same UMD finding; it is an inspection command, not a launch:

```bash
docker run --rm --pull=never --network=none --entrypoint /bin/bash \
  vllm/vllm-openai-xpu@sha256:f01e24f6c7ff01f1e0662234255a1372297d1dbd89d003cf13c8fad3eab1ba4f \
  -c 'dpkg-query -W libze-intel-gpu1 intel-igc-core-2 libze1 libigdgmm12'
```

No uninspected remote tag is claimed to match. A newer 26.35-based public
image, if obtained later, would be another independently qualified candidate;
it would not reproduce the host UMD. No image pull or build was performed.

**Concrete alternative design:** build a lab image from `e444` containing
exactly the hash-pinned host closure used by remedy A. This is an image with
the **host UMD**, not the entire LTX Python runtime. Keep vLLM/Torch/UR fixed
for this first comparison. The following is a design only, **not executed**.
It reuses `host_umd_mounts` and `image` from remedy A, writes an isolated build
context under `/tmp`, installs no host packages, runs no GPU command, and
produces an immutable local image ID. There is no honest digest to provide
until it has been built.

```bash
# DESIGN ONLY. Run the definitions from remedy A first; do not run a GPU job.
umd_context=$(mktemp -d /tmp/flashnext-host-umd-image.XXXXXX)
mkdir -p "$umd_context/rootfs"
for ((i=1; i<${#host_umd_mounts[@]}; i+=2)); do
  mount_spec=${host_umd_mounts[i]}
  source=${mount_spec#type=bind,src=}
  source=${source%%,dst=*}
  target=${mount_spec#*,dst=}
  target=${target%,readonly}
  mkdir -p "$umd_context/rootfs$(dirname "$target")"
  cp --dereference -- "$source" "$umd_context/rootfs$target"
  sha256sum "$source" >> "$umd_context/source-sha256.txt"
  printf '%s|%s\n' "$source" "$target" >> "$umd_context/mount-map.txt"
done
# Compare source-sha256.txt to the twelve pins in this note BEFORE building.
cat > "$umd_context/Dockerfile" <<'DOCKERFILE'
FROM vllm/vllm-openai-xpu@sha256:e4446310b1d30015e8fdc1a0a2ef1669ac6bef857cbe772487571ed5c1a926a9
COPY rootfs/ /
COPY source-sha256.txt mount-map.txt /opt/flashnext-host-umd-evidence/
ENV LD_LIBRARY_PATH=/usr/local/lib:/opt/ucx/lib:/opt/venv/lib
LABEL org.neural-download.experiment="flashnext-host-umd-26.18-candidate-unqualified"
DOCKERFILE
docker build --pull=false --network=none \
  --iidfile "$umd_context/image-id.txt" \
  -t neural-download/vllm-openai-xpu:flashnext-host-umd-26.18-candidate \
  "$umd_context"
umd_candidate=$(cat "$umd_context/image-id.txt")
docker run --rm --pull=never --network=none --entrypoint /bin/bash \
  "$umd_candidate" -c '
    set -eu
    export LD_LIBRARY_PATH=/usr/local/lib:/opt/ucx/lib:/opt/venv/lib
    for f in /usr/lib/x86_64-linux-gnu/libze_intel_gpu.so.1 \
      /usr/lib/x86_64-linux-gnu/intel-opencl/libigdrcl.so \
      /usr/lib/x86_64-linux-gnu/libze_loader.so.1 \
      /usr/lib/x86_64-linux-gnu/libze_tracing_layer.so.1 \
      /usr/lib/x86_64-linux-gnu/libze_validation_layer.so.1 \
      /usr/lib/x86_64-linux-gnu/libigdgmm.so.12 \
      /usr/local/lib/libigc.so.2 /usr/local/lib/libigdfcl.so.2 \
      /usr/local/lib/libiga64.so.2 /usr/local/lib/libopencl-clang2.so.16 \
      /usr/lib/x86_64-linux-gnu/libz.so.1 /usr/lib/x86_64-linux-gnu/libzstd.so.1; do
      report=$(ldd -v -r "$f" 2>&1) || { printf "%s\n" "$report"; exit 1; }
      printf "%s\n" "$report"
      if printf "%s\n" "$report" | grep -Eq "not found|undefined symbol"; then
        exit 1
      fi
    done
    cat /opt/flashnext-host-umd-evidence/source-sha256.txt
  '
```

Risk is the same older-driver/newer-client feature boundary as remedy A.
Freezing the bytes eliminates bind-source drift and improves repeatability,
but the image's original dpkg metadata and filenames still describe the
replaced files; retain the explicit overlay manifest. This is a local
experimental image, not a publishable recipe or validated runtime. A
package-managed rebuild could follow successful isolation; upgrading Torch,
Triton and all Intel wheels to the LTX versions at the same time would test
too many changes and may break the compiled vLLM extension ABI.

### Which to try first, and what the future test must decide

**A first; B only after its bytes are worth preserving.** A avoids a build
and most directly answers whether the host UMD changes the observed failure.
Neither design has been run on a GPU. Use the existing bounded single-card
probe and fault watcher only in a later owner-admitted idle-card window;
LTX currently owns the four cards. Retain the model-free gather, exact
allocator aliases, `NEOReadDebugKeys=1`, `EnableDeferBacking=0`, `FLAT`,
single launch, hashes, and stop-on-first-fault behavior. Insert A's mount
arguments and `LD_LIBRARY_PATH` into that future launch, or replace its image
with B's recorded immutable ID. Do not reuse the old receipt directory or
an old health receipt.

Before interpreting the next result, make the existing worker-exit boundary
explicit in the preregistration: the present test uses `os._exit`, so it
tests abrupt process resource release as well as gather correctness. A later
separate lifecycle test could record the before-return, after-free and
before-exit times and distinguish normal SYCL shutdown from `_exit`; changing
that behavior simultaneously with the UMD would spoil the first comparison.
A clean single probe is screening evidence, not a proof of stability or a
license for a four-card model load. Full correctness and fresh-process
repeats are still needed before adopting any runtime, because changing IGC
can also change generated arithmetic.
