# Qwen3.8 Flash-Next FP8 dense-screen host freeze and A48 recovery

Date: 2026-09-01
Status: operational interruption; no A48 model result

The host became unresponsive after the real-weight dense component screen and
was restarted by the user. Attempt-48 state, run, compile, RPC, and supervisor
paths were all absent after boot, proving that A48 had not launched and no full
checkpoint load or endpoint request occurred.

The previous boot's kernel journal provides a concrete correlate: the local
Samsung NVMe endpoint `0000:01:00.0` emitted repeated hardware-corrected PCIe
receiver events from 09:47 through 09:50 while the component work read real
checkpoint weights. This repeats the A45/A46 link symptom. There was no A48
server or evidence path to attribute the event to `twoshots` or model
inference.

After restart, the host had 129,039,856 KiB available and unused swap, all four
B70s enumerated, and no model process. The Corsair NTFS evidence drive had not
auto-mounted; it was restored explicitly at `/mnt/usb-models`. ASPM already
reported `performance`, but GPU0/1 endpoint runtime power had reverted to
`auto`, so the tracked performance-policy helper was reapplied and all four
endpoints now report `on`.

The current boot accumulated 13 corrected NVMe events before the policy was
reapplied, then remained stable in the immediate post-policy check. A48 was
therefore amended without changing inference behavior: its privileged wrapper
captures post-policy NVMe/root-port AER counters, passes them as numeric
baselines, and both launcher and supervisor abort on the first increment. The
existing live kernel-journal guard remains. This is stronger than demanding a
literal zero before launch, which would require another reboot while failing
to distinguish old boot-time events from new benchmark-time events.

Protected eager and graph measurements remain unchanged.
