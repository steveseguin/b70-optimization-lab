# Memory block 57 is online on boot 2cba7160 (2026-10-18 03:00 UTC)

- Packet 58h's passive inspection, then the coordinator's own check, found:
  - memory blocks **53–56 offline**, **57 online** (2 GiB blocks; the faulty physical range is `0x1a80000000–0x1cffffffff` = blocks 53–57);
  - `b70-offline-bad-memory.service` enabled and active.
- **Cause:** the service runs `for n in 54 56 53 55 57; do echo offline > …/memory$n/state 2>/dev/null || true; done`. Errors are ignored, so block 57's failure at boot (Oct 16 09:28 local) went unnoticed. Block 57 has been in service for this whole boot, including every record run since. All record and screen runs passed their exactness gates (12/12 or 13/13 against the packet 49 oracle).
- **Coordinator action:** one bounded re-application of the existing fence at 02:59 UTC (`echo offline > /sys/devices/system/memory/memory57/state` via sudo, per the owner's standing instruction to re-apply the memory fence). The kernel refused with an I/O error because of an **unmovable page** (page-cache page, zone Normal); it logged a page dump.
  - Block 57 remains online. No retry, no other memory-setting change, no stress test, no reboot.
  - The GPU fault count is unchanged at 2; the dump lines match no fault pattern.
- **Next:** at the next boot, check that all five blocks go offline. The service hides failures, so check the block states, not just the unit status. Changing the service itself is a memory-setting change for the owner to decide, and is not done here.
