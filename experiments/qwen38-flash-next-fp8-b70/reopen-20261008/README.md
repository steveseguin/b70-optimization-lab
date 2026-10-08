# Flash-Next FP8 Screen 1 — prepared, not run

**Free at least 89 GiB on the Docker/output filesystem before pulling anything.**
The October 8 metadata read found 53.68 GiB free: approximately **35.32 GiB more
is needed**. No cleanup is authorized or automated. The amd64 image has
4,311,802,107 compressed layer bytes (4.016 GiB). Admission budgets 24 GiB unpacked
(estimate), 5 GiB downloaded content, 10 GiB scratch and the untouched 50 GiB
reserve. A present image still requires 60 GiB free. See [image plan](image-plan.json)
and [raw metadata](evidence/official-v0300-manifest.json).

Choose **official v0.30.0 + pinned Lumnus Python file mounts**, no native build.
This is a partial community stack: official 0.1.14.1 kernels, fused GDN, Triton
FP8 MoE, full decode graphs, TP4+EP, unchanged 131-shard FP8 checkpoint, BF16
activations/16-bit KV, and generic 16.25 GiB/rank UVA weight offload. No external
PLE table or config replacement. Missing b70.3 fixes and the source/build choices
are detailed in [runtime notes](runtime-notes.md). Fit and startup remain untested.
The R276-era local images occupy roughly 23.3–23.9 GB each in `docker images`;
metadata does not confirm R304, vLLM ≥0.30 or kernels ≥0.1.14 in any of them.

Preview everything from this directory; these commands perform no GPU work:

```sh
python3 screen.py preflight --dry-run
python3 screen.py run --mode mtp1 --run-dir "$PWD/runs/screen1-mtp1" --dry-run
python3 screen.py run --mode mtp0 --run-dir "$PWD/runs/optional-mtp0" --dry-run
python3 screen.py run --mode mtp3 --run-dir "$PWD/runs/optional-mtp3" --dry-run
python3 protocol.py --mode mtp1 --dry-run
```

In a **later GPU execution task**, with storage and lane ownership admitted,
`python3 screen.py prepare --execute` checks admission and pulls the pinned
amd64 digest. Then the chosen `screen.py run ... --execute` command creates a
single systemd user unit, hashes the full model tree, rechecks admission, starts
one container, waits for `/health` and `/v1/models`, runs the client, and sends
one SIGINT on completion/failure. It never retries or escalates to a hard kill.
Use the printed unit command to follow/stop it. Retain the stopped container and
all receipts; do not rerun an existing result directory. Allow the lane's five-minute
gap after any earlier server shutdown. No GPU health probe is run by this packet.

Admission checks idle render nodes, a free port (19988; never LTX's 8188), clean
current-boot kernel log, 100 GiB available RAM, disk, pinned overlay files and
`scripts/verify-qwen38-flash-next-fp8-tree.py`. **Complete passive process/journal
read access is required.** Ordinary `steve` cannot inspect root-owned `/proc/*/fd`;
the controller fails closed on that visibility gap. No sudo/password fallback or
permission changes are supplied. This and disk are pre-execution blockers, not
reasons to weaken admission. Runtime polling stops new work on a fault, low RAM,
or reserve breach; a shutdown exceeding 300 seconds is retained for owner review.

**Request contract:** one static MTP1 launch sends 16 generation requests:
exact-2K twice (`afffd211…`), exact-4K twice (`1d833e5f…`), then all twelve fixed
realistic prompts once. [protocol.py](protocol.py) pins the lab depth/realistic
clients, fixture and full hashes; it compares all 128 diagnostic output tokens.
The suite uses zero cached tokens, a 512-token cap, and the class-balanced median
of `99 / (timestamp100 − timestamp1)`, with TTFT, mean, p10, wall/full-completion
rates, token IDs and hashes retained. Repeated diagnostic timing is separate.
**The morning 32-request plan means K1+K3 (16+16)**. Stock V30 has no reviewed
per-request depth switch: these need separate launches, and the runner never
chains them. MTP0 would add 16 more. No invented warmups fill the difference.

Budget roughly **one hour including pull**, conditional on network, model hashing,
loading and compilation; generic offload can make it longer. Bounds are 30 minutes
to readiness and 90 minutes total server time, followed by graceful teardown.
Pin misses still allow diagnostic-only suite speed, as requested. A fused-GDN
miss is expected and records the speed/exactness tradeoff; it does not isolate
GDN's cost because the model implementation, compiler and placement also changed.
Even matching pins cannot establish general MTP3 exactness or replace the full
quality battery and fresh-server repeats. A historical comparison to **46.854250
tok/s** is not an A/B, a record, or a validated community boost.

Next: if startup/fit fails, preserve that single failure and repair the stated
cause before another screen. If pins miss, port the lab's exact serial GDN and
remaining authority arithmetic to this base → **Screen 2**, with matched fused
and exact runs. If pins pass, retain the result and run full quality/determinism
qualification before matched speed work. MTP3 needs its own pins, acceptance and
rollback evidence. The [offline community queue](runtime-notes.md#community-queue-beyond-lumnus-offline-evidence-only)
includes nacolias SYCL and upstream GDN/MoE leads, with shallow-history limits.
