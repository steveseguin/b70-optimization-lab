# Packet58ab: one-card target HC fusion

Port packet60's exact norm, low/activation plus inject, and gate/mix stages to
packet58z's one-card source closure. This is CPU preparation, not a speed claim.
The target, oracle, tile16, all 48 layers, 21,552,729,600-byte cache, overlap,
BF16 KV and context 4096 remain unchanged. Final HC and draft are excluded.

`hc=production|p60fusion` is a runtime dimension at a quiescent boundary.
The smoke is twelve 64-token requests. The five-view comparison uses one load
and twelve 128-token requests per view: production/fusion/production/fusion/
production. A0 must be exact and is reported, but excluded from drift and gain.
The two warm controls must stay within 3%; both fusion views must beat both
controls by at least 2% for this port's speed gate. Fresh-start and final
promotion gates remain separate.

Nothing is queued. READY-FOR-DEVICE.json is valid only when written last,
with current commit, proposal hashes and all CPU/entry/planning checks.

[Work note](../../../../notes/2026-10-18-own-runtime-packet58ab.md).

## CPU evidence and remaining gate

GNU and Intel each match the production HC bodies byte for byte at the real
4×2560 / 320 shapes, in two fresh runs. Their complete transcripts also match
one another, including the nonfinite cases. The actual Engine capture test
checks BF16-writer invalidation, six BF16 intermediates, scratch, error, and
request reset. Full-size sparse mocks switch both ways at context 32 and 4096,
check 96 sides / 288 HC commands, empty absorbed slots and 48 layer hooks,
and reject switches during a position or with a sticky failure. There is no
new device cache or weight allocation.

The plan itself is regenerated only at the drained boundary: the production
path keeps its combine/norm absorption, and fusion restores the ordinary norm
sites before capturing its three stages. All plan-pointer indexes are rebuilt.
The unchanged production miniature matches the frozen record binary's tokens
and every retained state file.

**Required shared report check is blocked.** Both proposals are run through
`ops/rehearse_entry.py --report`. Their native loader and parser checks pass,
but that frozen tool only recognizes the two-card `screen.main` report path.
It refuses this one-card queue/window/suite runner before routing the report.
The actual one-card summary is independently exercised for smoke and all five
views, including refusal of corruption in the last token. Those passes do
not turn the shared-tool refusal into a pass. The last READY file therefore
records `ready_for_device=false`; do not enqueue these proposals until that
required gate is resolved in a separately authorized change.

## Reproduction and retention

All CPU commands use `nice -n 19 taskset -c 8-15,24-31 python3 -B`, stdin
`/dev/null`, and at most 4 GiB. Build: `build_engine.py`; proofs: `hc_gate.py`,
`protocol_gate.py`, `k1_gate.py`, `cpu_gates.py fullshape`, `cpu_gates.py reset`,
`control_gate.py`, `startup_gate.py`, `argument_gate.py`, `report_gate.py`,
`entry_gate.py`, and `run_cpu_gates.py`. Full-shape/K1 checks require the shared
compiler observer to report no active whole-host timing window first. All
compilation takes `ops/compile_turn.py`; imported modules never install caps.
The full-size mock reserves sparse virtual addresses and checks RSS below the
same 4 GiB limit. The finite-address-space refusal remains in real entries.

`lineage/58z-source.tar.gz` and `lineage/58xb-source-snapshot.tar.gz` are
intentionally retained source restoration artifacts (about 12 and 10 MB).
`lineage/owned-inputs` preserves the original small helper and admission
provenance. They exceed the 1 MiB hygiene threshold because the private source
closure must be reconstructible without mutable sibling sources. Do not
remove them without verifying a replacement and its consumers. Ignored
`frozen-inputs` is restored from these archives; immutable parent ELF/object
symlinks are preserved and hash-checked. Model payloads are never copied.
`retention.py` preserves extracted historical manifests under lineage so their
old pins do not masquerade as live dependencies. The original archives stay.

`seal.py` verifies CPU proof identities. `plan_queue.py` plans temporary copies
with the real pin guard; it never edits live queues. `ready_document.py
--write-last` follows the final implementation commit. No device equality,
physical-fit result, measured gain or new record is claimed here.
