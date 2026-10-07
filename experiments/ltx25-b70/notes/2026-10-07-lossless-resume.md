# LTX lossless optimization resumed, October 7

The owner requested continuous improvements in speed, frame throughput and
reliability with no quality degradation. This explicitly resumes the lane after
consolidation. Main owns four-card host actions; the two-card host is separate.

## Fixed target and first control

Preserve the accepted native distilled BF16 checkpoint revision
`5e6e71018ee1756ed329b697a7b4aedc934dfce9`, 256×256, 25 frames at 24 fps,
original two-stage sampling and accepted short-window w93c references. Check all
four output tensors, prompt/seed identity, finite values, deterministic mode and
independent recomputation. The prior completed 1.308 s/clip is about 19.1 generated
frames/s, distinct from playback rate. No lower precision, fewer steps, altered
resolution, cached prompt results, interpolated frames or changed batch outputs
count as an improvement of this target.

Packet 98's two-way W2/B1 shared-pool/decode-card-2 control is the first baseline
candidate. It is historical reproduction, not a claim to current upstream.
Preserve its sealed manifest
`918b47a5530b4dc97fe8fc8f4ec77fd64521ec6846217c54f5fba589e0e8377f`.
The progress-display fix must be separately hash-bound, CPU-tested, and isolated
from sealed packets and the installed virtualenv. Its original exception must
still propagate. No application has been launched at this preparation checkpoint.
Complete a reviewed worst-case output/cache budget before choosing the run size.
Larger-size speed-only and changed-output batch arms are not queued.

## Successive levers

Start with the disk-full reliability failure and accepted-reference control.
Then prioritize sampler/card-0 work: packet 97 measured about 2.53 s per sampler
job with two jobs in flight. Audit within-clip invariant context transfers and
host synchronization before changing arithmetic or reopening closed encoder
experiments. Existing lean connector reuse and accepted text-window changes
are already in the baseline.

Resolve newest upstream and inventory accepted overlays before new runtime
development. Initial remote discovery reports ComfyUI HEAD
`b00c6e95279053474955540ba4f551646722b9aa`, versus the frozen source
`19e1058f4c445ef74047e77a23f9ca7684c1e4b6`. The reference packet stays an immutable
reproduction anchor; a refreshed implementation requires explicit overlay
disposition and unchanged quality gates before promotion.

## Host and evidence boundaries

Read-only preparation finds the four-card host, no listener on 8188, about
53 GiB root free and 111 GiB available host RAM. Memory blocks 53–57 remain
offline. These are point-in-time observations, not GPU health qualification.
Root reserve is 50 GiB; admission must include temporary outputs and compiler
caches. Do not fill the disk again or delete research to fit an unbudgeted run.

Each bounded device run requires exclusive ownership, fresh health admission,
fault monitoring, immutable inputs, unused result paths, verified graceful
shutdown and postflight. No power/memory/swap settings, reboot, driver reset or
automatic restart/retry chain. Keep exact failures and negative results. A
completed experiment advances to the next justified lever; the project remains
active rather than being declared finished at a local plateau.
