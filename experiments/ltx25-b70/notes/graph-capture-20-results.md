# Packet20: shared per-device buffers; sampler 1.86x, clip 6.34 -> 4.70 s

September15, 2026, on the fresh boot `831530c8` after the host freeze. Packet20
(`prepared-encoder-graph-capture-20`, manifest
`5cfda07e35a4af655274c317726e9e12a874bc5b96969188ab94a581ffee2127`), server
`encoder-server-graph-capture-20b`, PID3926. Ten clips, schedule original x2,
graph x5, restored, original x2. **All ten matched their original references
bytewise on all four raw outputs.**

## Result

| Measure | Control (n=3) | Graph replay (n=4) | Effect |
| --- | ---: | ---: | ---: |
| Sampler 344+368 | 3.584 s mean | **1.931 s** median | **1.86x, −1.653 s** |
| Preview ready | 6.338 s mean | **4.696 s** median | **1.35x, −1.642 s** |
| Text encode 364 | 1.741 s | 1.748 s | unchanged |
| Video decode 374 | 0.613 s | 0.611 s | unchanged |

Control sampler values 3.511 / 3.611 / 3.631 s bracket the graph arm on both
sides. Against packet19's 2.001 s graph median this is **70 ms better**, a 3.5%
improvement on the sampler, with the rest of the 1.86x inherited from packet19.

## What changed, and whether it did what it was designed to do

Packet19 gave every block its own static buffers, so each of the 48 blocks
copied all 18 of its argument tensors on every step, even though 16 of the 18
are the *same objects* for every block within one forward. Packet20 keeps one
shared buffer set per device, computes the argument signature once per forward
instead of once per block, and runs the full registration and residency
validation once per forward instead of once per block call.

The receipt confirms the mechanism directly:

| | Packet19 | Packet20 |
| --- | ---: | ---: |
| Static buffer copies per block replay | 18 | **0.733** |
| Copies across the arm | ~47,520 | **1,935** |

A **24.6x reduction in copies**, for 70 ms. That ratio is the useful part of the
result: it confirms the earlier profile, which put the adapter's entire remaining
Python at about 12% of sampler wall time, so removing most of one of its parts
could never have been worth much. The sampler is GPU-bound now.

Because the blocks update their activations in place, the shared buffers also
remove every copy *between* consecutive blocks on a device: block i's captured
graph writes the buffer that block i+1's captured graph reads. Capture asserts
this in-place property per graph and refuses if a block ever stops honouring it.

96 graphs (48 blocks x 2 stage shapes), 2 signatures per block, 2,640 replays,
20.62 GiB on XPU0 and 19.47 GiB on XPU1 against ~20 GiB of resident weights.

## Standing position

| | Original | Now | Effect |
| --- | ---: | ---: | ---: |
| Warm clip preview | 6.338 s | **4.696 s** | −1.642 s |
| Sampler | 3.584 s | **1.931 s** | 1.86x |
| Text encode | 1.741 s | 1.741 s | untouched |
| Video decode | 0.613 s | 0.611 s | untouched |

For 1.042 s of video at 256x256, 25 frames, 24 fps, native BF16, 8+3 steps,
bytewise identical to the original references throughout.

## Interruption

The first attempt at this arm ran on the previous boot and produced one matching
graph clip (1.924 s sampler) before an `xe` GuC hard lockup latched the fault and
then froze the host. See [the incident](xe-lockup-incident-01.md). The arm above
is a complete re-run on a clean boot and does not reuse any of it.

Evidence: [`data/graph-capture-20-result.json`](../data/graph-capture-20-result.json)
and the per-clip summaries under [`data/graph-capture-20/`](../data/graph-capture-20/).
