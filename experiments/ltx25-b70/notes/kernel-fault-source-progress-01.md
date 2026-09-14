# Progress while native GPU work is fault-blocked

September14: the previous goal turn made concrete progress: it completed the
25-request exact encoder screen, prepared the native compiler gate, and captured
the subsequent kernel incident. This turn revalidated the same boot and the
still-present kernel-stuck client96119. Its SIGINT remains pending; server95931
remains present. New watchdog reports persist. No GPU requests were submitted.
This is not a completed compiler experiment or a recovered host.

One bounded diagnostic attempted to obtain CPU backtraces using SysRq `l`.
The [kernel documentation](https://docs.kernel.org/admin-guide/sysrq.html)
defines this as the CPU stack-dump operation; no SysRq configuration change was
needed or made. The command timed out after25 seconds with exit124. Its owned
sudo/timeout processes subsequently disappeared, and no SysRq/NMI-backtrace
marker appeared in the captured journal. No stack capture is claimed and no
retry occurred. [Diagnostic receipt](../data/kernel-cpu-stacks-01/summary.json)
and [original evidence](../data/kernel-cpu-stacks-01/evidence.json.gz) preserve
the negative result and a read-only interrupt-counter snapshot. The underlying
cross-CPU wait remains unexplained; these observations do not identify a kernel
patch, power-setting change, or driver reset as a remedy.

The future compiler package now incorporates the tested explicit host-kernel
fault signatures. The [new offline builder](../scripts/prepare-compiler-runtime-v2.py)
verifies model/source provenance while copying files even when the current host
is faulted. Runtime admission remains unchanged and continues to refuse the
fault latch. No running/frozen source was edited.

Prepared package: `prepared-encoder-compiler-03`, manifest SHA256
`9ecd5f9863289e00a934c1f4f400582092f37d0ee92035512fc095773ad02980`.
All1,229 inventory files were checked. The copied launcher's actual read-only
check rejected `FAULT.json` and created no server run. Three offline admission
tests and eight detector tests passed. This tests the boundary between building
source and admitting GPU work; it does not fix the kernel or qualify compilation.

Evidence: [preparation](../data/compiler-packet-03-preparation.json),
[verification including expected rejection](../data/compiler-packet-03-verification.json),
[manifest](../data/compiler-runtime-prepared-03-manifest.json),
[builder delta](../patches/prepare-compiler-runtime-offline-host-fault-v2.patch).
The original builder and prior packages remain preserved. Native testing still
needs recovered host health, a new campaign identity and the original strict
four-output oracle. The under-one-second, continuous24fps goal is unchanged.
