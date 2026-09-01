# B70 idle D3cold wake failure during Flash-Next component work

Date: 2026-09-01
Status: host reliability mitigation installed; GPU measurement pending reboot

After the A46 host interruption, a normal reboot initialized all four B70s
successfully. Before component work began, all four endpoints and several
Intel PCIe switch paths entered D3cold. The next Level Zero discovery could
not wake them: all endpoints reported an unknown header/link state, and the
kernel recorded corrected PCIe link timeouts. A bounded xe reload and changing
only endpoint `power/control` after the failure did not recover the paths.

The repository already contained
`scripts/tune-b70-runtime-performance-policy.sh`, which disables PCIe ASPM and
sets both every B70 endpoint and every upstream bridge path to
`power/control=on`. Applying it after the paths were inaccessible was too late,
but its complete-path coverage identifies why the earlier endpoint-only change
was insufficient.

`systemd/b70-runtime-performance-policy.service` now applies that existing,
reversible runtime policy during boot, before `multi-user.target`, so the
switch paths cannot enter D3cold before the optimization session begins. This
does not change model arithmetic, runtime source, benchmark selectors, or any
protected result. It increases idle platform power while enabled. Disable and
remove the unit after the kernel/firmware PCIe wake issue is corrected.

This is not a per-experiment reboot policy. One reboot is required to recover
the already-inaccessible links and validate the early policy; subsequent
component screens and full-model finalists may share the same healthy boot.
