# Packet98c CPU preparation closeout

Question: can packet97's kernel-only selections share one loaded model lifetime
without changing per-view arithmetic or preserving request-derived state?

Identity: packet97 checked bundle source copy, unchanged linked arithmetic
objects, new native command 13 switch/reset and a copy of packet98's v5 wrapper.
Target/draft weights, BF16 KV, 4K context, rank1 draft and 24/24 split remain fixed.
The proposed composite projection fixes experts at wide64.

Preparation is in progress; final CPU results will be recorded here. Device
13/13 exactness, acceptance equality, fresh device repeats and speed remain
pending. No device, service, live queue or parent packet is changed.

Useful mechanisms: strict pre-mutation choice validation; both target banks
recaptured; draft prepared specs and captured attention rebuilt; complete
request-state clearing, pinned-buffer clearing and immutable-weight lock.

The stronger capture test exposed two inherited audit omissions: HC capacity
and small-GEMV shapes. The local CPU serializer now includes them. This affects
test evidence only; linked production arithmetic remains unchanged. Original
failed preparation logs remain under evidence/. Unsupported layout changes
remain refused rather than approximated.

Evidence and reproduction: [README](README.md), [source audit](LAYOUT-AUDIT.md),
`evidence/`, `native/`, the copied sources and their provenance manifest.
Revisit after the small lane-B smoke, then complete independently qualified
brackets. No CPU receipt authorizes a GPU launch or promotes a result.
