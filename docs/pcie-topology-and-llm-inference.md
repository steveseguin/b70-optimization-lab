# PCIe Topology And Local-LLM Inference

PCIe generation and lane width matter, but not equally for every inference
setup. A narrow link can be nearly invisible after a single GPU has loaded a
model entirely into VRAM, yet become the dominant bottleneck when weights, KV
cache, or tensor-parallel collectives cross the host fabric every token.

This guide separates specification limits, measurements from this lab, and
untested expectations. It is not a claim that PCIe Gen3 or x1 links are always
fast enough.

## Capacity At A Glance

Approximate payload capacity per direction, before transaction-layer and
software overhead:

| Link | Approximate GB/s per direction | Practical reading |
| --- | ---: | --- |
| PCIe 3.0 x1 | 0.985 | Mining-riser class; highly restrictive for transfers and collectives |
| PCIe 3.0 x4 | 3.94 | Similar headline scale to Thunderbolt 4 PCIe tunnelling, but not equivalent |
| PCIe 3.0 x8 | 7.88 | Intermediate native link; test the resident workload and any TP collectives |
| PCIe 3.0 x16 | 15.75 | The reduced-link state tested in the Qwen TP2 experiment below |
| PCIe 4.0 x4 | 7.88 | Same encoding-capacity figure as PCIe 3.0 x8 |
| PCIe 4.0 x8 | 15.75 | Same encoding-capacity figure as PCIe 3.0 x16 |
| PCIe 4.0 x16 | 31.51 | Normal live state of the current B70 reference host |
| PCIe 5.0 x16 | 63.02 | Twice the PCIe 4.0 x16 encoding capacity |
| Thunderbolt 4 | 32 Gbit/s PCIe data requirement | About 4 GB/s before tunnelling overhead; Intel cites storage up to 3,000 MB/s |

PCIe 3.0 uses 8.0 GT/s and 128b/130b encoding. PCIe 4.0 and 5.0 retain that
encoding at 16.0 and 32.0 GT/s. The table is calculated from those rates and is
not a benchmark. PCI-SIG's own PCIe 3.0 table rounds one lane to about 1 GB/s
per direction and x16 to about 32 GB/s aggregated across both directions.

Thunderbolt is a tunneled, shared transport rather than a native lane count.
Thunderbolt 4 certification includes 40 Gbit/s link operation and a 32 Gbit/s
PCIe data requirement, but cable, controller, protocol, display, USB traffic,
and enclosure design reduce application throughput. Do not label a
Thunderbolt connection "PCIe 3.0 x4" merely because the headline numbers are
similar.

Primary specification references:

- [PCI-SIG PCIe 3.0 FAQ](https://pcisig.com/faq?field_category_value%5B%5D=pci_express_3.0)
- [PCI-SIG link-generation overview](https://pcisig.com/sites/default/files/files/PCI-SIG%20Cabling%20Webinar_FINAL.pdf)
- [Intel Thunderbolt 4 announcement and requirements](https://download.intel.com/newsroom/archive/2025/en-us-2020-07-08-introducing-thunderbolt-4-universal-cable-connectivity-for-everyone.pdf)

## Why The Same Link Can Matter A Lot Or Very Little

GPU VRAM bandwidth and host-link bandwidth are different resources. Once a
model and its KV cache remain on one GPU, each decode step can reuse weights
from VRAM without streaming them over PCIe. Request tokens and returned token
IDs are tiny. In that shape, link width may mostly affect model loading and
occasional synchronization.

The link becomes more important when the runtime repeatedly moves large data:

| Workload shape | Expected link sensitivity | Why |
| --- | --- | --- |
| One GPU, model and KV fully resident | Low to moderate | Steady decode is mostly on-card; loading and host synchronization still cross PCIe |
| Several independent one-GPU replicas | Low to moderate after load | Requests are independent; no per-layer inter-GPU collective is required |
| Tensor parallel / row split | Moderate to very high | Ranks exchange activations or partial results repeatedly during each token |
| Pipeline parallel | Moderate, topology-dependent | Stage-boundary activations cross devices; bubbles and latency can dominate |
| CPU or NVMe weight offload | Very high | Weight traffic repeatedly crosses the host link |
| Host-paged or offloaded KV cache | Very high at long context | Attention fetch/update traffic can become link-bound |
| Training or fine-tuning | High | Gradients, optimizer state, and collectives create much more traffic than resident inference |
| Model loading | High until another source bottlenecks | Storage and host memory feed VRAM over PCIe |

This is why a mining board can be useful for independent, fully resident jobs
yet poor for tensor parallelism or offload. It is also why two physically x16
slots are not enough evidence: the firmware may configure x8/x8, a lower slot
may be chipset-attached, several slots may share one uplink, or an x16-shaped
mining riser may electrically expose only x1.

## What This Lab Measured

### Qwen3.6 35B FP8, TP2: Gen3 x16 Was Not The Bottleneck

The reference lab reproduced a community Qwen3.6 35B FP8 B2 deployment on two
B70s, then ran a controlled Gen4 x16 / Gen3 x16 / Gen4 x16 sequence with the
same model revision, restored container filesystem/config identity, TP2/MTP2
configuration, GPU pair, and pp1024/tg256 benchmark shape.

| Link state | c1 generation tok/s | c12 generation tok/s |
| --- | ---: | ---: |
| Gen4 controls | 53.205-58.081 | 263.630-285.708 |
| Gen3 observations | 54.482-58.331 | 266.054-274.437 |

The Gen3 values stayed inside the Gen4 control envelope. A separate 256
MiB-per-rank XCCL all-reduce did change from 4.590 GB/s at Gen3 to 5.565 GB/s
at Gen4, so the link treatment affected effective bulk-fabric performance even
though decode did not follow it.

The A1/A2 model controls drifted by 7-8%, so this experiment does not resolve a
small PCIe effect. It does rule out the roughly 35-50% loss required to explain
the contributor/reference-lab throughput gap. The full evidence and caveats
are in the
[community validation note](../community/dominick253-qwen36-35b-fp8-b2-tp2/validation/2026-08-08-pcie-link-sensitivity.md).

This result applies to Gen3 x16, not Gen3 x1, Thunderbolt, every TP2 model, or
every B70 runtime.

### MiniMax TP4: A Different Shape Showed More Fabric Sensitivity

A separate cross-host MiniMax TP4 observation measured a 256 MiB all-reduce at
27.88 GB/s on an older PCIe 5.0 reference and 13.79 GB/s on the current PCIe
4.0 host. The closer decode comparison was 89.314 versus 83.17-83.79 output
tok/s. That was not a link-only A/B on one host, so it is correlation rather
than proof, but it demonstrates the important pattern: a 2x collective change
does not imply a 2x token-rate change, and TP4 can be more fabric-sensitive
than the Qwen TP2 shape above.

## Guidance By Build Type

### Older PCIe 3.0 Boards

PCIe 3.0 x16 is a reasonable candidate for resident inference. The Qwen TP2
test above found no material decode penalty, but users should still measure
their own engine and parallelism. Check whether installing two cards changes
the slots to x8/x8, and whether the lower slot connects through the chipset.

For a single resident model, prioritize VRAM capacity, backend support, and
correct negotiated width before replacing an otherwise useful Gen3 board. For
TP, offload, or training, include a collective/transfer calibration and an
end-to-end benchmark before deciding.

### Thunderbolt 4 And External GPU Enclosures

Treat Thunderbolt 4 as an experimental approximately 3 GB/s application-class
path, not as a transparent desktop x16 slot. Enclosure firmware, power,
cooling, hot-plug behavior, IOMMU/DMA policy, Resizable BAR support, and Linux
xe compatibility all need validation. This lab has not validated a B70 over
Thunderbolt.

The most promising use is one external GPU running a model that fits fully in
its VRAM. CPU/NVMe offload and multi-GPU tensor parallelism across a shared
Thunderbolt controller are high-risk shapes. Multiple ports on one system may
also share a controller or upstream link.

### Mining Boards And x1 Risers

PCIe 3.0 x1 provides only about 0.985 GB/s per direction before transaction
overhead; Gen2 x1 is about 0.5 GB/s. Confirm the negotiated generation because
many mining-oriented paths default lower.

Potentially viable:

- independent one-GPU inference replicas after each model is fully loaded;
- embarrassingly parallel batch jobs with small inputs and outputs;
- capacity experiments where throughput is secondary.

Likely poor:

- tensor parallelism or row-split inference;
- CPU/NVMe weight offload;
- host-paged KV cache;
- frequent model swapping;
- training or fine-tuning with synchronization.

This lab has not tested B70 inference over x1. Power delivery, firmware address
space, Above-4G Decoding, Resizable BAR, IOMMU grouping, cooling, and shared
chipset uplinks may block the setup before bandwidth is measurable.

## Inspect The Real Topology

Do not trust slot shape or one surprising endpoint line. Start with the device
identity and full PCI tree:

```bash
xpu-smi discovery -j
lspci -D -nn
lspci -t
```

The repository includes a read-only helper that discovers DRM devices or
accepts explicit full-domain BDFs and prints every PCI component in each sysfs
ancestry with its live and maximum link state:

```bash
scripts/report-pcie-topology.sh
scripts/report-pcie-topology.sh 0000:23:00.0 0000:27:00.0
```

For a selected GPU BDF, inspect every PCI component in its sysfs ancestry:

```bash
GPU_BDF=0000:23:00.0
realpath "/sys/bus/pci/devices/${GPU_BDF}" | tr / '\n' | rg '^0000:'
```

Then read the live and maximum link state for the relevant root, bridge, and
endpoint BDFs:

```bash
for BDF in 0000:20:01.1 0000:21:00.0 0000:23:00.0; do
  printf '%s current=%s x%s max=%s x%s\n' \
    "$BDF" \
    "$(cat "/sys/bus/pci/devices/${BDF}/current_link_speed")" \
    "$(cat "/sys/bus/pci/devices/${BDF}/current_link_width")" \
    "$(cat "/sys/bus/pci/devices/${BDF}/max_link_speed")" \
    "$(cat "/sys/bus/pci/devices/${BDF}/max_link_width")"
done
```

Replace the example BDFs with the ancestry from the machine being inspected.
On the current B70 host, an internal endpoint/bridge path can display Gen1 x1
while the external root-facing link is actually Gen4 x16. Check the tree and
both ends of the external link before classifying the card.

## Measure Rather Than Extrapolate

Use this ladder when link bandwidth is a suspected bottleneck:

1. Freeze model, runtime, GPU assignment, prompt/output shape, concurrency,
   graph mode, and cache state.
2. Record the full topology, negotiated speed/width, AER counters, and device
   identity.
3. Run a telemetry-free A1 benchmark from a fresh service.
4. Change link speed in firmware/BIOS with the model stopped, then reboot.
   Live raw PCI configuration writes can lose devices and are not a general
   recipe.
5. Verify both ends of every changed link and run a bounded device check.
6. Run B from a fresh service, then restore and run fresh A2.
7. Separately measure an adjacent H2D transfer and the exact-shape collective
   used by the model. Label payload rate separately from physical wire rate.
8. Accept a causal result only if A2 returns inside the preregistered control
   tolerance. Otherwise report a range and the drift.

Some telemetry tools perturb tightly synchronized workloads. In this lab,
XPU-SMI's PCIe Read/Write metrics returned zero for every live sample, so they
were rejected as evidence. Preserve official benchmark runs without polling
and use a separate shadow run to qualify any observer effect.

## Bottom Line

- Do not replace a functional Gen3 x16 board solely because Gen4 has twice the
  theoretical capacity; test the actual resident-inference workload first.
- Do not infer that Gen3 x1 or Thunderbolt will behave like Gen3 x16.
- Single-GPU resident inference and independent replicas are the best
  candidates for narrow links.
- Tensor parallelism, offload, host-paged KV, training, and shared chipset
  paths need direct bandwidth and end-to-end validation.
- Report generation, width, topology, and parallelism with every multi-GPU
  result. "Two GPUs" is not a complete hardware identity.
