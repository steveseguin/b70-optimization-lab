# Qwen3.8 Flash-Next TP4 MTP0 PIECEWISE graph attempt 1 result

Date: 2026-08-28

## Result

Attempt 1 is a bounded Grade-D negative: the exact TP4/EP4/MTP0 PIECEWISE arm
exhausted global host memory and the existing 8-GiB swap during post-load graph
compilation. The API never became healthy, the client was never invoked, and
there were zero model requests, quality responses, replay responses, or speed
rows. This result says nothing about graph output parity or graph throughput.

The frozen identity remained model revision `bcd9f01d`, vLLM `1372c62d`, XPU
kernels `ad25aa9f`, staged runtime `2f829747`, TP4/EP4, MTP0, PIECEWISE with
capture size `[1]`, max length 4,352, MBT 64, one sequence, the exact
201,326,592-byte BLHNC cache, prefix cache off, and the eager-a4 selective UVA
PLE/input-embedding placement. The four-rank preflight passed. All 131 shards
loaded from local NVMe in 73.48 seconds; ranks reported 31.27 GiB model memory
and 81.881498-82.152417 seconds model-load time. Rank 0 then entered compilation
and logged caching compile range `(1, 64)`.

## Host-memory timeline

- `10:21:35`: the first global OOM invocation began. The kernel reported only
  252 kB free from 8,388,604 kB total swap.
- `10:21:39`: the first OOM selection killed `wireplumber`.
- `10:23:22`: a later selection killed `pipewire-pulse`.
- `10:23:25`: global OOM killed PID 1852126, worker TP3. vLLM immediately
  reported `VllmWorker-3` dead and started executor shutdown.
- `10:28:30`: during the prolonged failed-engine teardown, another global OOM
  killed PID 1852043, worker TP2; only 196 kB swap remained free.
- `10:28:55`: bounded descendant cleanup and postflight evidence capture had
  completed.

This is direct evidence of host-memory exhaustion in the exact arm. It does not
by itself prove a leak, prove that swap is sufficient, or attribute every byte
to compilation. The journal also records host-service disruption; this cannot
be described as a clean-host run.

## Cleanup and evidence

The supervisor closed with rc `130`; journal read rc was `0`. Port 19674, the
owned server/workers, compile scratch, and RPC scratch were absent afterward.
All four expected B70s were discoverable at 42.875-42.883 MiB. The run journal
has no B70-addressed reset/fault/timeout/fatal event, while retaining all global
OOM records. The zero-byte `health.json` is durable proof that health did not
complete, not a successful receipt.

Raw roots:

- run:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt1`
- supervisor:
  `/mnt/usb-models/bench-results/qwen38-flash-next-fp8-b70/qwen38-flash-next-fp8-tp4-ep4-piecewise-mtp0-4352-r1-attempt1-supervisor`

The tracked 41-entry primary-evidence manifest is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt1-primary-evidence.sha256`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt1-primary-evidence.sha256),
SHA-256
`ffc849c14bd36a66f638953f6d668d55fc61599674d85caec676c0671b964231`.
All entries verify against the two raw roots. The structured closeout is
[`20260828-tp4-mtp0-current-piecewise-graph-attempt1-result.json`](../data/20260828-tp4-mtp0-current-piecewise-graph-attempt1-result.json).

## Protected results

Nothing is replaced or lowered. Current eager-a4 short rates remain
`5.315577824 / 5.223788770 / 5.219404722 tok/s` (median
`5.223788770`). Its exact-4K rates remain `4.720311370 / 4.795324835`
(median `4.757818102`). Every faster MTP and legacy result stays under its own
identity. Attempt 1 has no graph speed, no matrix/site credit, and no
LocalMaxxing authority.

The next bounded treatment is a temporary explicit 64-GiB root-ext4 swapfile,
with the complete serving identity unchanged and fail-closed root, swap,
memory, journal, lifecycle, graph-mode, and quality gates. It requires a new
attempt, port, paths, scripts, hashes, and independent audit before launch.
