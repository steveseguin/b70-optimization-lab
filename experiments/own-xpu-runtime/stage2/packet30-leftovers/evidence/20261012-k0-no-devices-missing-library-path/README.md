# Retired K0 admission failure, 2026-10-12

Coordinator decision:

> retired by the coordinator on 2026-10-12: preflight-class failure, zero devices enumerated, no device contact, kernel log empty; not a GPU fault

The coordinator launched K0 on card 2 at 2026-10-12 01:32:52 UTC. It exited
in about 5.3 seconds with `K0 card range`: the closed native environment omitted
`LD_LIBRARY_PATH`, so the runtime adapter was unavailable and enumeration was
empty. The native binary's ordinary `ldd` check had passed through its run path.
The kernel log contains only journalctl `-- No entries --` markers, no entries.
The old wrapper nevertheless wrote a device fault latch.

The latch and the entire failed `build/k0-card2` directory were moved here
without changing their bytes. [Archive manifest](archive-manifest.json) verifies
each file. `build/g3-card2` did not exist when archived: the coordinator reports
that queued G3 refused with `K0 not passed` before creating its output directory.
No G3 evidence was deleted or reconstructed. The original build identity is
retained in the K0 window receipt and repository history.

This retirement is the coordinator's explicit decision, not an automatic GPU
recovery. No device binary, discovery call, reset or health probe ran during
this CPU-only repair. K0/G3 remain pending with new output names in
[WINDOW.md](../../WINDOW.md).
