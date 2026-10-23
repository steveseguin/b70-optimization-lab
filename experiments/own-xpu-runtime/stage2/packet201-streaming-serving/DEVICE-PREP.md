# Packet201 exact mixed streaming: device preparation

## Question and identity

Can the tested one-card native runtime send text incrementally while preserving
every output and state disposition from the sixteen-turn ordinary serving pilot?
The unchanged p198 ELF uses full BF16 state, context4096 and a21,552,729,600-byte
expert cache. The additive Python streaming components and borrowed-owner session
are already covered by CPU fixtures and a separate tiny synthetic native proof.
This packet will qualify actual model streaming, not a speed record.

## Outcome

Preparation has110 CPU checks:31 worker,25 client and54 controller/execution/
restoration checks, each independently reviewed. Root repeated the25 client
checks and verified the combined source maps. Native, service, queue and device
operations are intercepted; a temporary HTTP/1.0 loopback fixture exercises real
socket framing. No model/device execution follows from these test receipts.

## What worked

The sixteen prior prompts, output caps, token IDs and session relationships are
preserved. Seven requests use streamed replies and nine use ordinary JSON. All
sixteen outputs, consumed prompts, text, finish reasons and usage must match the
recorded p200 run, totaling1484 output tokens under the1728-token cap. Five older
full-length token oracles and the resumed/fresh pair remain independent checks.
Natural stops and Unicode are included. Baseline identity is not a new semantic
quality oracle for the eight short practical prompts.

The client validates bounded UTF-8 event frames, stable response identity,
role/content/terminal usage ordering, one final marker and EOF. Partial failures
retain bounded raw bytes and halt further requests. It explicitly closes a
partially consumed response and enforces the remaining receive deadline on each
bounded socket read. Recorded frame times describe client observation only.

The worker preserves the pilot's ownership, diagnostic drain and two-phase
completion ordering. Its49-file streaming closure supplements the unchanged
canonical profile. The controller requires successful worker and client exit,
matching manifest/vector/listener identities,16 native requests and dispositions,
all exact output/SSE checks, and independent physical drain before one guarded
restore30. Direct restore invocation requires the same proof. No retry, group
kill, automatic restart chain or settings change is introduced.

## What failed or remains uncertain

Client review fixed detached HTTP/1.0 socket deadline handling, explicit response
closure and a trickled-line timeout gap. The earlier22-check candidate remains
under lineage/client-before-response-close-and-chunk-deadline. Preparation
estimates roughly295KB baseline and373KB cap-replay client evidence; these are
not universal bounds. The writer retains its hard1MiB/40file limit and refuses
overflow. Frame timings are not native generation latency or a speed claim.

The native/driver forecast remains768MiB, plus1MiB client evidence, above the
27GB root floor. This is monitored headroom, not a quota over every external
writer. Closed compiler caches are being separately archived and verified to
recover margin. The conservative launch-time idle origin remains: model loading
consumes the initial240-second allowance, and the fixed client starts promptly
at the fresh listener. No retry is authorized if that allowance expires.

## Evidence and patches

- [Combined CPU gate](evidence/device-cpu-gates.json).
- [Worker review](evidence/independent-worker-review.json),
  [client review](evidence/independent-client-review.json), and
  [adapter review](evidence/independent-adapter-review.json).
- [Worker preparation](README.md), [client scope](CLIENT.md),
  [fixed vectors](client-vectors.json), [execution entry](run.py), and
  [controller/restoration contract](../../ops/packet201-window/DRIVER.md).
- [Privileged cache retention preparation](../../integration/CLOSED-RESTORE-CACHES-PRIVILEGED.md).

The original engine, canonical profile, p197–p200 packets and already reviewed
streaming components remain unchanged. Packet201 uses additive files and retains
exact parent diffs and intermediate candidates.

## When to revisit

Finish storage recovery, derive a fresh CPU plan in a private staging directory,
and independently audit the full source/external closure. Root then writes the
separate admission manifest and completes fresh live checks before one window.
Only successful joined qualification and physical drain permit restore30. Audit
both actual native/SSE results and restoration; preserve any failure and halt
new requests without retry.
