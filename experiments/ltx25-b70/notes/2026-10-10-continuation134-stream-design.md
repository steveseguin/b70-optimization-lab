# Packet 134: the admissible 169-frame split36 arm

Parent is sealed 133b, manifest
`ed908a9031a937801d17264edacfe0807bea543badc412a32eb6118daa214fd3`.
This packet prepares **169 frames, split36, cone graph off, eager display and
audio on xpu:3**, with legacy auxiliary placement. No model or server was
started. Native qualification and memory remain pending.

The [measured 145 budget and corrected 169 census](2026-10-10-continuation133b-results-145.md)
explain why the graph arms are refused. The graph/display3 arm lacks 1.843 GiB
on card 3 after charging both full reserves; the replica2 arm lacks 5.122 GiB
on card 2. The selected arm clears every floor plus 0.75 GiB screening. Its
card 3 margin is 4.861 GiB at the measured dg0 predecode boundary, and still
0.905 GiB when the entire display allowance is charged against the lowest
dg0 qualification phase without credit for retained display storage.

## Scope and gates

`LTX_CHUNK_ARM=split36-169` is explicit and default-off. It admits only the
169/frame/dg0/cone/bo1/pa1/two-way20-28 path, split36 text, legacy auxiliaries
and audio, serial eager-display on xpu:3, full fingerprint snapshots and zero
anchor read-ahead. It rejects the graph, replica, audio relocation, allocator
release and pool-cap combinations. `LTX_CHUNK_ARM=off` retains 133b's accepted
scopes, including its 145 split36/cone-graph option. The option is bound into
server identity, receipts, qualification, client expectations and run naming.

Every full 169 native display decode checks physical free memory against
**6.5 GiB transient + 9 GiB floor + 0.75 GiB screening = 16.25 GiB before**,
and **9.75 GiB after**. The reserve is an estimate, never described as a
measured peak. Both readings and their complete arithmetic are recorded in
the decode record. Server qualification and the client validate the evidence;
missing, forged, mistyped or below-floor records refuse. No cache release,
host setting, lower precision or alternate fallback is used.

Text moves once, before graph capture, retaining 36 layers on card 2 and 12 on
card 3. The parent's pinned 12-prompt conditioning oracle and 40 window-probe
rows remain unchanged. Unknown prompts refuse. Tensor arithmetic, weights,
full precision caches, sampling settings, qualification ids and all 220
numerical contracts remain unchanged. Existing 49/97/145 output tables are
preserved byte-for-byte as JSON values.

The new 169 table pins the three eager outputs from the successful 123b 169-frame
qualification, with 21 hashes reconstructed from six verdict-bound receipt
and decode snapshots. Its auxiliary placement was xpu:2, whereas134 uses
legacy placement; provenance records this difference. It is a strict
cross-placement byte oracle, not a matched performance comparison. Any
native difference refuses 134; no different outputs are accepted quietly.
The full nine-output, cone/full-image, conditioning, repeated-chain,
capture-freeze and per-chunk checks remain required.

## Packet closure and import coverage

The exclusive destination is
`/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-continuation-stream-134`.
Every changed parent file has its exact predecessor under
`provenance/packet133b/`; the parent manifest is a recursive dependency.
The new 169 reference table and its provenance are bundled and hash-bound.
The client pins the inner `plan_sha256`, never the JSON-envelope file hash.

The sealed-import test starts a fresh `bin/python -B` child, reproduces the
launch-only import path, then tests the runtime import path. It imports every
declared helper from `source/scripts/` and every component copy from
`resolution/components/`, verifies each origin, and injects a missing-file
failure for every helper copy. It also covers the launcher-local text helper
and oracle and reproduces the original 133 packaging failure. It blocks
device/server imports, sockets, subprocess creation, locks, writes and
startup calls inside each probe. It neither calls a launcher nor invokes
check-only. Both off 145 and selected 169 modes must pass before sealing.

The full recovery and client suites, all-pins test, mocked preflight, matched
CPU runtime pairs and recursive verification are recorded in the
[build receipt](../data/resume-20261008/continuation134-build.json). These CPU
fixtures test control flow and byte preservation, not native device exactness,
peak memory or speed. All test children inherit device, live-port and signal
guards. Tests use owned scratch, which is removed after verification.

## Forecast and coordinator handoff

Expected period is **6.5–6.95 seconds per 7 seconds of new video**,
**0.929–0.993 s/s**, central 6.65/0.950. Expected display completion is about
4.70 seconds after anchor readiness, within the period. The serial audio and
record tail remains in the forecast. This does not predict a gain over
133b at 145's 0.869 s/s; it is the sole conservatively admissible 169 arm requested
for qualification. No 169 performance point is promoted.

The exact text-only command and matching client are in
[LAUNCH.md](../recovery/20261010-continuation134-stream/LAUNCH.md), with
[CONTRACT.md](../recovery/20261010-continuation134-stream/CONTRACT.md).
`start-client-134.sh` defaults to
`LTX_STREAM_WORKDIR=/home/steve/ltx-stream/s134-live01`.
Both shell wrappers use the pinned virtualenv's `bin/python -B`.
The coordinator retains control of live work. The separate 133b storage-guard
incident and packet 135 repair remain outside 134's scope.

## Sealed identity and development corrections

Manifest SHA256:
`a46fb116f2ce97948c694db870db5a939096814986222fcd0b732e8c025a653c`.
Inner plan SHA256:
`bc03692eb82ae24f67e9c06e11f60b1e1412ee7c02af21bdf93658f37175a46c`.

The sealed builder retains an old descriptive module header and a STATUS
sentence about the 133 packaging repair. Those descriptions are stale;
the manifest, plan basis, source closure and launch pin identify parent 133b
and the new 134 arm. The sealed bytes are preserved. This erratum changes
neither the seal nor the launch contract.

Development runs found three inherited test expectations that still named the
old parent, counted three reference shapes, or assumed two decoder call sites.
The fixtures now check parent 133b, four reference shapes, and the additional
guarded native decode path. The synthetic runtime fixture also supplies the
new arm's required free-memory reading. No native measurement is inferred
from that fixture. The initial client run collided with another packet's CPU
fake servers; its evidence is retained, and the complete client suite is
rerun with an isolated loopback port range. Port 8188 remains blocked before
any test address translation.

## Final CPU validation

- Recovery: **1,178/1,178**, including **76 sealed-import tests**. The latter
  cover all 31 runtime helpers, all 36 component copies and the launcher copy.
  Both sealed import modes also passed before sealing.
- Client: **6,761/6,761 across 45 suites**. This is the parent's 6,351,
  plus 158 new 134 checks, 208 integration checks, and 44 extra assertions
  from historical suites checking the new 134 and concurrent 135 pins.
- All-pins audit: **36/36 assertions across 18 packets**, checking inner
  plan hashes separately from envelope file hashes.
- CPU runtime: **four cases**, each with nine qualification and two stream
  chunks; **22 matched output comparisons** passed. All **10 mocked
  preflight checks** passed. Runtime and client source stayed unchanged
  throughout their final runs.
- Recursive verification: **2,336 bound files**, 2,338 physical files;
  author components match the seal. **Zero Python caches**. Owned recovery
  and client scratch is removed; historical scratch is untouched.

The shared client preserves the concurrent packet 135 registrations; this
packet does not include its storage repair. Repository document links,
manifest paths and shell syntax pass. The separate global literal-pin check
still reports 231 pre-existing Flash-Next drifts (87 matching, no missing
targets); those are outside this packet. The build receipt binds the final
results and the retained development evidence. No launcher, check-only,
model request, device open, live port, unit operation or process signal was
used. Native qualification, actual 169 memory and cadence remain pending.
