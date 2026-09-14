# Reuse decoder axis visibility within each attention call

2026-09-14. Prepared an inactive patch against the installed, original Comfy
Kitchen eager `na.py`. Nothing was installed, loaded into the active server,
sent to an endpoint, or tested on a GPU. The candidate passed23 CPU check groups;
native decoder/full-clip parity and speed remain unqualified.

The packet08 saved profile has25 prompt-worker samples inside `_group_mask`:
21 at line74 (`torch.tensor(starts)`), one at75 (`torch.tensor(ends)`), and three
at76 (`int(en.max())` within `arange`). Their0.25s total sample weight describes
Python stack occupancy, including possible waits for earlier GPU work. It is
not mask kernel time or recoverable latency. The initial subagent message
misidentified line74 as the scalar readback; direct numbered source inspection
corrected this before implementation. See
[`2026-09-14-packet08-native-dispatch-audit.md`](2026-09-14-packet08-native-dispatch-audit.md).

The native decoder caller is `NeighborhoodAttention3D.forward` in pinned
`comfy/ldm/lightricks/vae/na_diffusion_decoder.py:161`: it supplies kernel metadata,
`is_causal=None`, and scale1.0. No runtime tensor-shape trace is present in the
saved stack profile. Extracting the unchanged integer geometry code and applying
the previously documented default untiled decoder shapes gives:

| Dimensions | Blocks | Geometry groups/call | Original axis builds/call | Cached builds/call | Cached bool bytes/call |
| --- | ---: | ---: | ---: | ---: | ---: |
| 6×8×8 | 4 | 1 | 3 | 2 | 100 |
| 6×16×16 | 6 | 1 | 3 | 2 | 292 |
| 11×16×16 | 4 | 1 | 3 | 2 | 377 |
| 21×32×32 | 2 | 8 | 24 | 4 | 818 |
| 25×64×64 | 8 | 18 | 54 | 8 | 1,878 |

These are conditional source counts, not observed native call counts. Under
that geometry,522 axis builds become100; each cache hit skips the two integer
tensor constructions, extent reduction/readback, arange, and axis comparisons.
The original operations remain byte-for-byte on misses. This patch is separate
from the existing extent-only patch and deliberately retains its scalar
readback on misses, keeping this experiment attributable to axis reuse.

A fresh dictionary belongs to each `na3d` invocation. Keys contain the immutable
start/end tuples and the input's concrete device. Values are boolean axis
visibility tensors, independent of additive-mask dtype. Only `_group_mask`
receives the dictionary, and its downstream operations read these tensors.
It still constructs a fresh full additive mask for every group; changing that
returned mask cannot alter a cached axis. Public `na3d` inputs and outputs,
tile budgets/grouping, q/k/v operations, SDPA arguments and call order remain
unchanged. No prompt, latent, generated output, full attention mask or model
parameter is retained between calls.

The admission cap is64 entries, each no larger than4,096 boolean elements:
at most262,144 bytes of retained tensor payload per invocation. Oversized or
late entries execute the original uncached operations. Python key/dictionary
and tensor/allocator overhead is additional; this is not a total peak-memory
bound. The largest predicted stage needs just1,878 payload bytes. Retaining all
full BF16 masks at that stage would instead require335,486,976 payload bytes,
which is why this candidate caches only the separable axes.

The cache has no model, offload, global-device, or cross-request lifecycle.
Ordinary return releases its axes, verified by weak references in the CPU tests.
All internal work uses the invocation's normal stream context. A private cache
dictionary must not be exported or reused across calls/streams by future
integration; no such reuse is implemented or qualified here. Tensor immutability
is an ownership discipline, not a claim that PyTorch tensors cannot be mutated.

Artifacts:

- [`prepare-na-axis-cache.py`](../scripts/prepare-na-axis-cache.py) verifies the
  complete original source SHA and creates isolated original/candidate copies,
  a patch, and source-derived geometry/memory receipts without importing Torch.
- [`na-axis-visibility-call-cache-01.patch`](../patches/na-axis-visibility-call-cache-01.patch)
  is the reusable delta; the same bytes are in
  [`data/na-axis-cache-01/delta.patch`](../data/na-axis-cache-01/delta.patch).
- [`test-na-axis-cache-cpu.py`](../scripts/test-na-axis-cache-cpu.py) extracts the
  four functions from the saved sources, avoiding installed-module edits and
  custom-op registration. It uses actual CPU Torch with strict determinism.
- [`cpu-receipt.json`](../data/na-axis-cache-01/cpu-receipt.json) and
  [`cpu-test.log`](../data/na-axis-cache-01/cpu-test.log) record23 passing check
  groups. BF16/F32 masks and NA outputs are byte-exact against the original and
  candidate repeat. Tests check finite outputs, unchanged q/k/v, every SDPA
  input/argument/order, clipped/boundary/oversized/causal windows, identical-axis
  reuse, dtype independence, mutation isolation, capacity and release. A separate
  fixture-only64-element budget exercises multiple/partial tiles on tiny CPU
  tensors; native production constants remain unchanged. CPU aliases test
  device-key separation, not XPU placement or cross-stream correctness.

Reproduction of the completed CPU work:

```text
python -B -S experiments/ltx25-b70/scripts/prepare-na-axis-cache.py --output NEW_SOURCE_DIRECTORY
/home/steve/.venvs/ltx25-baseline/bin/python -B experiments/ltx25-b70/scripts/test-na-axis-cache-cpu.py --output NEW_RECEIPT.json
```

The CPU driver checks the fault latch before importing Torch and between cases.
It never enumerates or initializes GPUs. Its final check confirmed
`xpu_initialized=false` and that installed source was unchanged.

Original SHA256:
`4f1d82fe02af995d395969667f6cfd8d10635c3144eec8ca78fe37c103803995`.
Candidate SHA256:
`40e360bc1f791f0373997f907ca67e804087541498c86ffa5731c8a9eae40cc2`.
Patch SHA256:
`4a9eaece77d8572994142da0057ce21afa6baa954c978d2cf0e7dc3e8fb8880c`.

Feasibility: source reuse and CPU exactness justify preparing an isolated
runtime integration for native qualification. They do not establish a speed
win, full-clip losslessness, or production eligibility. No candidate was
promoted and no GPU work occurred during this preparation.
