# Load-crash forensics + load probes, 2026-09-21 00:16-00:25 EDT (boot f64b14c5)

## The second GP fault is the same crash, not a new one

00:16:15, warm-00 of the packet-89 campaign: `traps: python[7290] general
protection fault ip:184cfbb ... in python3.12` — the **identical instruction
pointer** to the 17:26 crash on the previous boot. Disassembly: the faulting
instruction is `mov eax, [r13]` at `PyBytes_FromObject+0xba`, dereferencing
an item pointer taken from a Python object array. A general-protection fault
there means a non-canonical pointer in the heap. Both crashes sit at the same
extremely hot dereference site: heap corruption during the 26 GB encoder load,
with the crash landing wherever the busiest object walk is. Same-IP is what
any heap corruption looks like; it does not convict the binary (the on-disk
binary loads the same code fine on many runs, and page-cache corruption
cannot survive the reboot that separated the two crashes). The corruptor is
unknown: bad RAM (userspace memtest passed; kernel/DMA pages untested),
a driver-side DMA write astray, or a C-extension bug in the load path.

## Load probes: single-prompt loads survive

A launch→one-prompt→stop probe loop (single prompt = the failure mode here
has always been process death, never a host wedge) went **2/2 clean with no
rest** before the campaign's 60 s idle rest. Both GP-fault crashes happened
*with* the rest. Two samples each way — suggestive, not proven — that an
idle dwell between server construction and the first heavy load is part of
the trigger, consistent with the freeze pattern (all five freezes hit at
load *transitions*, never during steady work).

## Probe teardown faulted the GPU: this boot is burned

Killing probe 2's server (00:24:38) produced `xe ... Fault response:
Unsuccessful -ENOENT` plus two engine resets (ccs + bcs) on card 0000:27:00.0.
The sealed launcher's fault gate now refuses launches for the rest of this
boot — correctly. Teardown of a server with in-flight graph work is not
safe; the probe script's bare `kill` has been replaced with a graceful stop.
**No further GPU launches until a reboot.** This is the third fault class
this week that maps to "GPU server lifecycle under this driver stack is
fragile": launches, stops, and load transitions each carry wedge/corruption
risk.

## Standing recommendations (user-held, unchanged)

memtest86+ at console; BIOS Power Supply Idle Control = Typical Current
Idle; kernel cmdline `drm_kms_helper.fbdev_emulation=0` so pstore records
the next panic; PSU 12 V rail math. New addition: when rebooting anyway,
note that graceful stops (the campaign's supervised stop path) have not
faulted; bare kills have.
