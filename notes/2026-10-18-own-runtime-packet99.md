# Packet99: exact IQ2 grid lookup

CPU-only preparation from packet97. The initial `git pull --rebase` was refused
because coordinator-owned tracked files are dirty. `git fetch origin main`
confirmed HEAD already matched origin/main; those files were left untouched.

The source inspection found one dependent IQ2 grid lookup per eight weights,
not a second sign-table lookup. Signs are eight inline bits in the weight code.
Down is IQ4_NL and already uses register constants for its sixteen levels.

[Preregistered candidates and gates](../experiments/own-xpu-runtime/stage2/packet99-iq2-grid/PREREGISTRATION.md):
full and compact SLM grids, compact constant grid, and an IQ4 byte-pair SLM
table. Build and CPU qualification are in progress. No device, service, live
queue, memory-block fence or host setting has been touched.
