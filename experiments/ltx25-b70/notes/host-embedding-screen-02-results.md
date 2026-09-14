# Packet12: safe encoder construction refusal

Screen02 is terminal and incomplete: five control clips passed all four original
raw bytewise comparisons. Request6 stopped before constructing the host-table
encoder. No optimized or restored-control clip completed; no speed promotion.

The four warm control previews range6.272–6.351s (median6.297120s).
The first loaded clip took55.947s including cold initialization. Each uses
25frames256×256 at24fps, original BF168+3 steps and all four raw output oracles.
This remains far from the subsecond25-frame north star; these timings are
control evidence, not an optimization win.

The source-budgeted cold admission passed. During control→host replacement:

- after-release: 46.580 GiB available; 8.000 GiB required; passed=True.
- before-construction: 46.580 GiB available; 56.890 GiB required; passed=False.
- before-restore: 45.848 GiB available; 31.960 GiB required; passed=True.

All four old CLIP/group/patcher/model weakrefs were dead and the old patcher
was absent from the native registry. Seven nonencoder owners remained retained.
This establishes actual release at this transition, but does not prove the CPU
or driver allocators returned all freed storage to the operating system.
The replacement constructor never ran. The factory recorded a sticky failure,
and the client exited1 with no further requests. The memory guard was not lowered.

Postflight found an empty queue, only server PID11888 on all render devices,
same user-reboot boot5414a640, no root FAULT latch and no new kernel entries.
The application remains running for inspection (exec40923); the client exec12642
is terminal. No application retry/reload, computer restart, driver reset or
power/swap/cache setting change was performed after the refusal.

Next: preserve complete failed evidence, account for observed storage, and
design encoder ownership reuse that avoids rereading/reconstructing52.495GB
of encoder state. Keep the restore budget, native accounting and exact output
gates. Sampler same-device output partition has a separate source route audit;
it cannot be injected into the frozen running application.

Postflight: `../data/host-embedding-screen-02-postflight.json`.
Raw terminal root: `/mnt/fast-ai/bench-results/ltx25-baseline-20260913/host-embedding-screen-02`.
Runtime receipt root: `encoder-server-host-embedding-12` alongside it.
