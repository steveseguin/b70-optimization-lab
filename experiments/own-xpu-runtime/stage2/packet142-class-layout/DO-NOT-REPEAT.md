# Packet142 boundaries

- Packet104/104b gate/up tile16 lost. Do not rerun that arm. `expert-gate-up-order600`
  retains exact E1 halfcache rows and only changes the allocation/order of copies.
- Packet136 bundle8 is frozen. This is its copy; existing packet trees and screen
  wrappers remain untouched. Historical instructions are in `lineage-inputs`.
- The initial 512 MiB budget could not hold one whole expert gate/up tuple
  (550,502,400 bytes). It failed CPU admission and was replaced by 600 MiB.
- CopyEngine has a 128 MiB transfer limit. Whole expert matrices exceed it;
  load-time copies use bounded 32 MiB chunks with waits and event retirement.
- Never accept a class switch outside the bank loaded at startup. Validate before
  mutating bank roles or captures. No allocation or weight write at view boundaries.
- Preserve all six rollback bank captures; recapturing only the active pair is unsafe.
- Allocation order does not imply physical adjacency. These are class-prefix
  experiments. A null result cannot close whole-class layout work.
- No rerun of other classes just because one packet141 class is positive.
- No launch through legacy root helpers. Only the locally sealed v5 entry is current.
- CPU fixture captures and GNU/Intel synthetic bytes do not establish device quality.
  Keep 12 x 64 smoke, five exact 12-prompt views, drift gates and later full promotion.
- No prompt/KV/response reuse, compressed KV, target changes or unchecked speculation.
- No queue edits or GPU/service launches during preparation. Coordinator selects
  candidates after packet141's receipt. Native exec retains unlimited address space.
- Keep the 25 GB root-free floor and 300 MB build cap. Copied objects exceeded
  the cap once; hash-bound links to allowed frozen parent objects fix the duplication.
