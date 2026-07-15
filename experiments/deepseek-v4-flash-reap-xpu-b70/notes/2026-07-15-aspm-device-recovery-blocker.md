# ASPM probe and three-device recovery blocker

## Outcome

A reversible PCIe ASPM performance-policy probe did not reach timing. After
changing `/sys/module/pcie_aspm/parameters/policy` from `default` to
`performance`, the four-rank oneCCL control stalled during communicator setup.
The probe was terminated, left no worker process, and the ASPM policy was
restored to `default`.

After restoration, GPUs at `0000:27:00.0`, `0000:43:00.0`, and
`0000:47:00.0` remained PCI-enumerated and bound to `xe`, but reported
`power/runtime_status=error`. Only `0000:23:00.0` remained discoverable through
`xpu-smi`. No model server or other GPU workload is running.

## Fabric observation

The external links are not lane-starved. Each B70 card's upstream link is PCIe
Gen4 x16 (`16 GT/s x16`). The apparent `2.5 GT/s x1` endpoint is the card's
internal Intel bridge/VF-facing link, not the host slot link. The host is using
two pairs of root complexes, and the normal rank order already gives the
minimum two cross-complex edges for a four-rank ring.

## Recovery attempted

The following safe local recovery steps did not restore the three cards:

1. restore ASPM policy to `default`;
2. set the affected root, upstream, downstream, and GPU PCI functions'
   `power/control` to `on`;
3. issue per-function FLR through each GPU's sysfs `reset` file;
4. unbind/rebind `xe` for `0000:27:00.0`;
5. issue an upstream bus reset through `0000:25:00.0` and retry the bind.

Kernel evidence includes:

- `Unable to change power state from D3cold to D0, device inaccessible`;
- AMD-Vi `IOTLB_INV_TIMEOUT` for `0000:27:00.0`;
- xe VF GuC reset failures with `-EPROTO`;
- `Hardware reports unknown graphics version 0.00`;
- runtime-PM usage underflow on `0000:47:00.0`.

The repository's previous recovery notes classify this state as requiring a
full host reboot when xpu-smi/FLR/bus reset cannot restore device access. Do
not repeat the ASPM mutation on this kernel/driver stack.

## Next optimization after recovery

The strongest remaining collective candidate is not another transport or MHC
epilogue. During graph recording, oneCCL submits a separate 16-thread
sequence/update kernel before every BF16 `[4096]` LL256 ring kernel. Fusing
that sequence update into the ring workgroup could remove 87 serialized graph
commands per token without changing transport, arithmetic, or collective
count.

Before editing oneCCL, run a zero-code four-rank upper-bound screen of 87
chained exact-shape reductions with `CCL_SYCL_FORCE_RECORDING_PATH=0` versus
`1`. Reject the lane unless the forced recording path costs at least
`0.50 ms` per 87 calls. If it passes, require the fused candidate to save at
least `0.50 ms` per 87-call graph with exact changed-input results for at least
512 replays.
