# Packet105 — exact target head row split

## Scope and admission

CPU only, 3.5-hour box. Copied packet97 sources after the 97e fix; no old packet,
screen, live queue or orchestration edits. GNU and Intel builds serialize through
packet94’s compiler lock, nice 19, CPUs 8–15/24–31, 8 GiB address-space limit,
stdin closed. Build cap 300 MB. Records remain on lane A.

Initial `git pull --rebase` refused active unstaged orchestration files. Fetch
confirmed HEAD and origin/main identical; no stash or active-file mutation.
DO-NOT-REPEAT checks cover 79/87/88/93: do not move the draft trunk, invent
rollback overlap, or treat lane-B head results as lane-A confirmation.

## Implementation and gates

In progress. Target range: rank1 [0,202240), rank0 [202240,248320).
Expanded suffix weights require 155750400 bytes plus private scratch and logits.
The transfer request carries only the verified target final.mix (5120 bytes),
with position/sequence ownership; the return is 16 bytes. Tie rule is the lowest
global index after unchanged BF16 rounding. Any nonfinite logit prevents output.
The frozen parent orchestration outputs will not enter dependency seals.
