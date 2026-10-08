# Flash-Next FP8 Screen 1b — CPU port, execution refused

Screen 1b ports the lab's memory-lifetime safeguards onto the official vLLM
0.30.0 XPU image and the pinned Lumnus Python base. **It is not yet an admitted
GPU configuration.** The fit gate refuses unknown bounds as well as excessive
predictions. No server was started to develop or test this packet; the LTX
server and port 8188 were not contacted.

The direct-allocation PLE path removes the pageable-to-pinned duplicate of the
native checkpoint table. It preserves its dtype and values, checks complete
local shard coverage, filters non-owned PLE shards before materialization,
and uses the actual XPU device for UVA. Checkpoint copies are bounded and
serialized across ranks; cancellation drains outstanding copies. Python
shutdown changes remove automatic worker hard-kill escalation. These are
storage and lifetime changes, not an exact-GDN port or sampler change.

Whole-file Python replacements are sealed in [overlay-manifest.json](overlay-manifest.json).
[container-entrypoint.sh](container-entrypoint.sh) applies them after checking
both input and output hashes. The native wheel and unchanged Python files stay
in the official image, pinned by its `e4446310…` digest in
[image-plan.json](image-plan.json). The source checkout is left unchanged.
Attribution: the existing Lumnus/wu1ff deltas are pinned at
`9d79d28d7e32f33bdbd115c85d116583ce679cb6`; the new PLE/loading/shutdown port
adapts this lab's certified patch series. No community speed boost is claimed.

The requested MTP1 configuration keeps maximum length 4,352, TP4+EP, native FP8
model/table bytes, BF16 activations and full 16-bit KV. It uses selective UVA
for PLE and whole expert tensors, at 16.25 GiB per rank with whole-parameter
overshoot. Its predicted final pins are **70.494044 GB**. With the fit note's
20 GiB overhead assumptions and one 256 MiB live staging buffer, the planning
peak is **92.237316 GB**, above the **90 GB** ceiling. This is an assumption-based
prediction, not measured host RAM. Complete V30 runtime/retention and VRAM
bounds remain unqualified; the authoritative qualified peak is therefore
unknown and execution refuses independently of that numeric failure.

Final v5 expert-row placement is **not added**. Under those same allowances,
even ideal placement cannot meet both the host ceiling and four GiB spare per
card: an optimistic static calculation already needs 28.560915 GiB per card
before several runtime costs. v5 changes which rows live on host, not this
total-memory obstruction. Smaller *evidenced* overhead bounds or another
lossless memory reduction are needed before choosing an admitted placement.
See [runtime notes](runtime-notes.md) for the component table and limitations.

From this directory, preview the prediction and exact command without any GPU
or Docker operation:

```sh
python3 screen.py run --mode mtp1 --dry-run
```

The exact future execution command is:

```sh
python3 screen.py run --mode mtp1 --execute
```

**That command currently refuses the memory gate.** It is supplied for review,
not as a claim of permission or readiness to displace LTX. A later admitted
execution requires idle cards, complete passive process/journal access, a
fresh result directory (default `runs/screen1b-mtp1`), the existing pinned image,
and the lane's five-minute shutdown gap. No password/sudo fallback exists.
Nothing retries, restarts, changes host settings, or installs into a venv.

On an admitted run, the controller rechecks the source/model/launch prediction
before and after full model hashing. The independent watchdog polls every
250 ms from startup through drainage. At accounted host pressure ≥80 GB or
MemAvailable ≤32 GiB it writes a cancellation latch and sends **one SIGINT**;
normal cleanup shares the same latch. Loader admission also checks the next
allocation against those thresholds. Signal failure or a drain timeout leaves
evidence for review; it never escalates to a hard kill. These guards cannot
guarantee safety under unbounded unrelated host pressure.

The protocol remains sixteen requests: exact-2K twice, exact-4K twice, then all
twelve cold realistic prompts once, with zero cached tokens and a 512-token
response cap. Fused GDN remains in place. A pin miss establishes a mismatch on
that fixture, but cannot attribute it solely to GDN; model lineage, compiler,
MoE and placement also differ from certification. A match establishes only
those checked token streams. Neither establishes broad exactness, full quality,
MTP3 correctness, or fresh-server determinism. Any speed remains diagnostic;
46.854250 tok/s is a historical reference, not a matched A/B.

CPU validation commands and results are in [VALIDATION.md](VALIDATION.md).
