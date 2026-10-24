# Proposed one-card qualification admission

This is a coordinator plan, not a launch receipt. The runner has been compiled
but never invoked. Root owns fresh admission, any controlled application stop,
and the single launch. The existing runner and binary remain unchanged.

The initial candidate is the card used by `qwen38-27b-fp8`. Historical P195
[K0 admission](../../stage2/packet195-record-bundle-diet/evidence/device-cards01-p195-a/K0-lane-admission.json)
maps `renderD130` to `0000:23:00.0`; this must be re-established from current
sysfs, `/dev/dri/by-path`, device numbers, and the application's actual process
descriptors. Neither a render-node number nor an old logical card ordinal is
a current identity. Stop only that application if root selects it; preserve
the other applications. No automatic restart or retry is part of this plan.

## Identity and isolation evidence

The inherited [backend](../../stage2/packet181-session-swap-v3/one-card/lineage/native/generated/single_device.cpp)
enumerates Level Zero GPU devices visible to SYCL and selects an index in that
list. It creates a driver context, a SYCL context containing the selected
device, and compute/copy/maintenance queues on that device. Its identity string
contains index/name/copy ordinal, **not PCI BDF**. The runner's `--card 0`
therefore means first filtered device, not physical card zero.

The historical [lane mapping](../../stage2/packet181-session-swap-v3/one-card/chain_devices.py)
uses NEO BDF filtering before Level Zero enumeration, PCI ordering, and matching
Level Zero/SYCL selectors. P195's retained admission joins that configuration
to passive BDF/node and process-FD evidence. The proposed exact-BDF filter below
narrows its two-card `0000:2` prefix to one card. This narrower configuration
has not been qualified by this runner. `ZE_AFFINITY_MASK` alone would not prove
that another device was not opened during discovery.

The source proves selected-device queue construction, not absence of temporary
DRM opens by the driver/runtime during enumeration or driver-context creation.
Root must retain a privileged passive inventory and monitor this one child's
PID/start ticks and target/non-target DRM descriptors. Any unexpected device
contact, inventory error, or new fault stops new work. A post-exit empty scan
alone cannot reconstruct transient opens. The frozen runner has no in-process
BDF assertion or pre-kernel parent acknowledgement; that is an explicit limit,
not evidence supplied by its numeric selector. If root requires that stronger
gate, a separately reviewed entry change should require exactly one visible
GPU and compare `pci_address` with the admitted BDF before owner construction.

## Fresh coordinator checks

Before any launch, bind the binary and source/object closure in
[compile-only.json](evidence/compile-only.json), including binary SHA256
`c9588597ab33b4a7812d6c88adbedf3a62d2061472f84f0d211ff1c9aaf5bfa8`.
Retain the current boot ID, complete fault baseline, memory block states,
root free space, MemAvailable, node/BDF/dev_t topology, application PID/start
ticks, and raw privileged holder inventory. The target must be descriptor-empty
after any authorized application stop; daily-process allowlisting never permits
a holder on the target. Other application identities/nodes must remain unchanged.
Preserve queue PAUSE markers, exclude competing experiment units, and retain
coordinator ownership for the whole run. Do not mutate power, memory, swap,
shared caches, or service settings as a side effect of admission.

Use a single unit with `Restart=no`, `SendSIGKILL=no`, `KillMode=process`,
`TimeoutStopSec=infinity`, `UMask=0077`, unlimited address space, nice 0 and
coordinator-approved CPU affinity (historically `0-3,16-19`). The compiler's
4 GiB address-space limit must not propagate to this native process. Do not use
a timeout that forcibly kills the GPU owner. The runner transfers under 1 MiB
and uses bounded synthetic buffers, but runtime/context/JIT resources still
need admission. Device total capacity is not observed free VRAM.

## Proposed child command and closed environment

This example assumes fresh checks confirm BDF `0000:23:00.0`. Change the BDF
only through a new reviewed admission. Root must create a new private control
directory and its `sycl`, `neo`, and `xdg` subdirectories first; the output
directory itself must not exist. `HOME` stays `/home/steve`. Check that neither
the admitted working directory nor HOME contains an unexpected `igdrcl.config`;
do not remove or rewrite any existing configuration.

The exact library tuple is the recorded [launch_env.py](../../stage2/packet181-session-swap-v3/one-card/launch_env.py)
tuple, preserving order and spelling. The qualification link command separately
records compiler runtime/system rpaths in its compile receipt; no inherited
shell library paths or SYCL/ZE options are admitted.

```bash
/usr/bin/env -i \
  HOME=/home/steve PATH=/usr/bin:/bin OMP_NUM_THREADS=2 \
  LD_LIBRARY_PATH=/opt/intel/oneapi/tcm/1.5/lib:/opt/intel/oneapi/umf/1.1/lib:/opt/intel/oneapi/tcm/1.5/env/../lib:/opt/intel/oneapi/tbb/2023.0/env/../lib/intel64/gcc4.8:/opt/intel/oneapi/pti/1.0/lib:/opt/intel/oneapi/mkl/2026.0/lib:/opt/intel/oneapi/dnnl/2026.0/lib:/opt/intel/oneapi/debugger/2026.0/opt/debugger/lib:/opt/intel/oneapi/compiler/2026.0/opt/compiler/lib:/opt/intel/oneapi/compiler/2026.0/lib \
  NEOReadDebugKeys=1 FilterBdfPath=0000:23:00.0 \
  ZE_ENABLE_PCI_ID_DEVICE_ORDER=1 ZE_AFFINITY_MASK=0 \
  ONEAPI_DEVICE_SELECTOR=level_zero:0 \
  SYCL_CACHE_DIR=/tmp/gsq-native-qualification-ADMITTED.control/sycl \
  NEO_CACHE_DIR=/tmp/gsq-native-qualification-ADMITTED.control/neo \
  XDG_CACHE_HOME=/tmp/gsq-native-qualification-ADMITTED.control/xdg \
  /home/steve/llm-optimizations/experiments/own-xpu-runtime/gsq-rco-iq3s/native-qualification/build/1792817788303878245/qualify-native \
  --run --card 0 --output /tmp/gsq-native-qualification-ADMITTED
```

`ADMITTED` is a placeholder for a fresh coordinator-bound run identity, not an
invocation instruction. Private cache locations do not disable or flush shared
caches. Root supplies the unit/monitor around this child command; it is not a
self-contained admission wrapper.

On incident preserve the first error, halt new work and issue at most one
cooperative SIGTERM to the identified child. No replacement launch follows.
Retain ownership while completion is uncertain. Successful cleanup requires
the child's positive backend synchronization and safe owner receipt, process
exit, passive target-descriptor clearance and unchanged fault/application
evidence. The runner deliberately waits for supervision if safe cleanup cannot
be established. This qualification establishes only the bounded format cases;
it cannot establish full-model correctness, fit, MTP behavior or throughput.
