# Bounded decoder axis-cache confirmation preparation — 2026-09-14

Prepared `scripts/run-na-axis-confirm.py` for 18 requests on the existing
packet10 process, PID84255. This preparation performed no endpoint requests,
Torch imports, native execution, process changes, or runtime edits.

The completed screen01 justified confirmation: its three cache clips preserved
all four original raw outputs, with paired decoder differences of approximately
−83, −77, and −98 ms. Three triplets do not establish a repeatable speed win.
The early bare warmup is not the steady-state comparison denominator.

The confirmation uses six triplets in order: boat OCO, marble COC, bird OCO,
bird COC, marble OCO, boat COC, where O is scoped original decoding and C is
axis caching. Each fixture therefore has three original and three cache clips.
For OCO, the effect is middle C minus mean endpoint O; for COC, it is mean
endpoint C minus middle O. Both signs mean cache minus original, and balanced
orders reduce sensitivity to linear timing drift. No extra warmup is scheduled.

Admission requires the exact completed screen01 progress hash
`a0da72e9a1a85086b41bb02c66e9eda63401a649b5795e0a63e46deceb244568`,
the same PID/start identity, source packet, components, owners, and discovered
full 24-call decoder sequence. The helper independently validates the existing
graphs, histories, strict finite capture metadata, all-four-output raw comparison
receipts, placement receipts, and scoped decoder receipts. It binds 161 evidence
files and rechecks those hashes before each new request. Previously pruned raw
archives are not reread; their durable comparison receipts are revalidated.
Every new clip runs the unchanged raw comparison against the original oracle.

The original transformer dispatch and numerical graph remain unchanged. Each
new clip has a unique numbered name, inherits the existing parity-gated media
retention, and must match the original sequence and owner identities. There are
no retries, restarts, fault bypasses, or automatic promotion. An admission or
request failure halts the campaign and preserves evidence.

Final source hashes:

- Client: `265c0925b9bf04bc53a7653b7bbcdde991b0a32fe2c887c1dfd6a9e48f5df22b`
- Admission helper: `2ee3f7d064454137a4192370cbf4e86247cbc5dd9f79c8c3de59cb9380210e0a`
- Test driver: `907eb2d21e8f3dd21fbc13bbff69efd8abc1e04603c8981d1ce9cb917956a2d3`
- Packet10 manifest: `d6ec6c63869d30dbe009708095f53811372e228becf16b7475ad30d11213fe6a`

Eight stdlib tests passed. They exercise actual saved evidence admission,
adversarial provenance/quality/owner/fault changes, schedule balance, both signed
pair formulas under synthetic drift, unchanged graph/gate functions, and
parity-gated deletion of temporary files. The offline client source/prior-evidence
check also passed. Final receipts are `data/na-axis-confirm-stdlib-02.json`, its
matching `.log`, and `data/na-axis-confirm-source-check-01.json`; the earlier
unsealed-client test log is retained separately as `-01.log`.

The old screen clients and shared validator are unchanged. Root owns review,
execution on the existing process, terminal export, and interpretation.
