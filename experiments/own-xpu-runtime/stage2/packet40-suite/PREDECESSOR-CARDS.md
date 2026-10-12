# Packet38 coordinator evidence received during packet40 preparation

The coordinator's [cards0+1 chain](../packet38-integrated/receipts-cards01-20261012-chain/README.md)
ran on 2026-10-12, 16:04–16:41 UTC. These are packet38 device measurements,
not packet40 results. Packet40 has run no device window.

The [native MTP suite summary](../packet38-integrated/receipts-cards01-20261012-chain/WS/summary.json)
contains twelve prompts and two repeats, with a distinct excluded warm-up and
complete state reset before every request. All 24 requests passed: 1,536 tokens
and 9,216 retained layer fixtures matched their arithmetic-v2 oracle exactly.
The first-repeat median was **38.27 tok/s**, the second **38.25 tok/s**, and
the pooled 24-row median **38.25 tok/s**. The
[sequential suite](../packet38-integrated/receipts-cards01-20261012-chain/WSs/summary.json)
also passed all 24 requests, 1,536 tokens and 9,216 fixtures; its pooled median
was **25.36 tok/s**. These counts were checked against the per-request receipts.

Each request produced 64 tokens, so its rate is `63 / (t64 - t1)`. Both suites
include the cost of copying 48 layer fixtures for each of the first eight
generated steps. They are retained-instrumentation predecessor measurements.
The repeat medians remain separate evidence; the pooled median must not be
presented as a single cold first-response suite attempt. Packet40 prepares
retention-disabled speed windows with same-boot exactness companions.

The historical **28.49 tok/s** comparison belongs to a different runtime:
llama.cpp SYCL, two cards, with 22 observed non-immediate-EOS rows across the
reference attempts. The prompt set is shared, but runtime identity and observed
row population differ from packet38's 24 complete 64-token rows. The historical
reference excludes terminal EOS and uses `(N - 1) / (tN - t1)` with at most 64
non-EOS events. Preserve that convention separately from packet40's fixed
64-event metric; this note does not turn the comparison into a matched runtime
experiment or a publication claim. None of these 64-token runs supplies the
100-event metric or the repository's 512-cap final publication gate.

The chain also provides two operational lessons:

- [K2 grid/watchdog stop](../packet38-integrated/evidence/20261012-k2-grid-exceeds-watchdog/README.md):
  the 66-length QSA grid at 200 repetitions needed more than the 10,800-second
  window. The coordinator stopped it cooperatively; no kernel fault or boot
  latch occurred. The amended packet38 K2 uses six lengths, 88, 104, 120, 136,
  152 and 256. At review time packet40 still retained the original 66-length
  grid. Packet40 now retains that full grid with a six-hour planning allowance
  and an 86,468-second watchdog, rather than borrowing the sampled-grid result.
- [K2 compression/storage refusal](../packet38-integrated/evidence/20261012-k2-retention-storage-cap/README.md):
  valid device work produced about 979 MB of fixture bytes, then compression
  admission failed because raw and compressed copies coexisted under a 3 GB
  build cap. Packet38's later 6 GB workaround does not apply to packet40's
  binding 3 GB limit. Packet40 now places durable coordinator receipts inside
  its packet directory and uses destination-aware storage admission. Large
  fixture output retains authenticated hashes and its restoration recipe, then
  is deleted without a duplicate gzip. The 66-length raw-byte estimate is
  `979339200 + 60 * 1600 * 12292 = 2159371200`, with a 2.5 GB total write
  reservation for logs and metadata. An ordinary storage failure still must
  not latch the boot; CPU rehearsal cannot establish actual device duration.

These two gaps were reported before changes. Current wrapper source and its
CPU storage regressions cover the revised admission and retention behavior;
full wrapper rerehearsal and coordinator timing remain separate gates. This
predecessor note is not a passing packet40 gate.
