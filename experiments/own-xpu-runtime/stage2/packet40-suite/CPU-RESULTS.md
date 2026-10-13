# Packet40 sealed CPU qualification

This supersedes the copied packet38 summary. No device ran and no packet40
speed is claimed. The current-source [build receipt](build-receipt.json) is
sealed with 104 gate receipts and 53 artifact hashes. The
[final audit](seal40-audit.json) passes all 91 inherited obligations. Copied
parent receipts and pre-rebuild attempts remain historical inputs, not
authorization for the current binaries.

Current completed coverage, verified against the strict rollback builds:

- [Strict terminal rollback](terminal-eos-all-state-gates.json): 472 checks,
  comprising 408 miniature and 64 sampled real-model checks; 460 positive
  physical-state comparisons and 12 corruption controls. Both controllers and
  both retention selectors are covered, with 480 owner archives. The mini model
  visits every actual launch boundary and the completed-half case. The real
  model samples boundaries at positions 7 and 8 using its full-weight launch
  plan on the original seven-token prompt prefix. This is diagnostic state
  evidence, not full-prompt oracle or speed evidence.
- Refreshed mini runtime gates: [GNU 130 cases](mini-gnu-host.json),
  [Intel 7 cases](mini-icpx-host.json), and [ASAN 7 cases](mini-asan.json).
- [Actual native/Python controller comparison](native-mini-cpu.json): 1,109
  miniature paired cases, including 1,093 ternary guess patterns through length
  six and twelve randomized 64-token cases. Its inherited terminal comparison
  has a narrower scope; the separate strict proof above establishes complete
  physical-state equality for the declared terminal cases.
- Standalone controller checks: 1,123 cases each for normal, ASAN and TSan,
  plus five mailbox cases for each build. These exercise the standalone
  controller binaries; they are separate from the runtime mini gate counts.

- Refreshed nonterminal cancellation: 101 miniature gates per controller,
  including every actual launch boundary and retention independence; five
  real-model gates comprise four seeded cuts out of 909 launches plus one
  retention comparison on the original 87-token prompt. The separate
  [inventory audit](cancellation-inventory-gates.json) rechecks all 204 forced-cut
  cases; it is an audit of those cases, not 204 additional executions. Only
  logical-event telemetry is excluded, with original hashes/counters retained.
- [Long retention independence](retention-caps-gates.json): eight comparisons
  across twelve requests, both controllers and 64/128-token caps, comparing
  tokens and complete target-state inventories for disabled, early and
  early/tail retention.
- [Draft publication/failure](draft-async-gates-gnu.json): 28 cases across both
  controllers and retention modes. Native publication is asynchronous; Python
  remains the synchronous reference. Target tokens and full target state agree.
- Real-model Python-controller qualification: GNU and Intel each pass all five
  modes (none, ngram, forced hit, forced miss, MTP), with eight exact tokens and
  384 layer fixtures per mode: 40 tokens and 1,920 fixtures per compiler. The
  [GNU](real-campaign-gnu-host.json) and [Intel](real-campaign-icpx-host.json)
  aggregate receipts bind their five current narrow execution ledgers; earlier
  failed outer campaign bookkeeping remains preserved.
- The refreshed cheap campaign records 23 passing receipts. Within that set,
  [prepared structural review](review-prepared-gates.json) passes 29 source
  checks and rejects 43 negative mutations. The separate
  [rollback audit tests](rollback-audit-unit-tests.json) pass eight cases.
  Structural checks supplement execution; they are not model runs.
- Independent [cancellation/retention](review-cancellation-retention-p40.json)
  and [suite-prefix admission](review-suite-prefix40.json) reviews are signed.
  The prefix exporter has 27 synthetic checks and compiler preflight has ten;
  shortened diagnostics cannot replace the inherited full64 suite gate.

- [Inherited real CPU suite](suite-real-cpu.json): all three requests pass at
  64 outputs each, totaling 192 exact tokens and 1,152 layer fixtures. The
  Intel host backend uses native MTP with a fresh state reset per request.
  `incident-retrospective`, `code-review` and `customer-email` constitute a
  partial 3/12 prompt set; `requested_max_new=64`, `oracle_token_cap=64`,
  `prefix_only=false` and `full_oracle_generation=true` distinguish full
  responses from complete suite coverage. Scratch was archived and removed.
- Selected-dispatch GNU captures match fresh Intel host references for four
  prompts at 64 positions each, including full-vocabulary logits, cache and
  control bytes. [Pipeline draft agreement](pipeline-draft-agreement.json)
  also passes for both compilers: each has 93 draft rows, eight scored rows,
  identical proposals and byte-equal final cache/control files. This is draft
  arithmetic/identity evidence, not a target suite throughput sample.

- [Native real-controller comparison](real-controller-gates.json): all five
  modes (none, ngram, forced hit, forced miss, MTP) pass against their matching
  GNU Python-controller references. Each mode has eight exact tokens and 384
  fixtures, totaling 40 tokens and 1,920 fixtures. The comparison includes both
  ranks' full final-state bytes and all allocation/host inventory fields;
  only `logical_event` scheduling telemetry is excluded, with original counters
  and raw inventory hashes retained. These paired comparisons reuse the Python
  reference evidence described above; their counts are not independent target
  oracle coverage to add to it.

- [128-token tail-fixture gate](suite128-tail-cpu-gates.json):
  `incident-retrospective` passes all 128 tokens and 768 fixtures at steps
  1–8 and 97–104 on the real Intel host backend with native MTP. The owner
  scratch was archived and removed. This is partial 1/12 CPU correctness
  evidence, not a complete suite or a speed/publication result; the final
  realistic-suite gate remains false.
- [Input integrity](resume-input-integrity.json) reauthenticates 3,718 hashes,
  covering the target input bundle, official draft contract and shard/tensor
  bytes, and imported target streams. No accelerator is opened.
- All [12 standalone Python producers](python-standalone-gates.json) pass.
  These are producer counts, not twelve model executions; they launch no
  native ranks.

Final qualification also passes:

- [Python discovery](python-regression-gates.json): 211 tests, no failures,
  errors or skips.
- [Every-window rehearsal](full-wrapper-gates.json): 22 complete success/failure
  pairs through the host backend, including summaries; no device timing is
  qualified. [Admission checks](window-seal-admission-gates.json) pass 31 gates
  without launching a device.
- [Build identity](build-identity40.json): all 53 artifacts are unchanged after
  current mirror regeneration and four dependency builds; a second pass is
  a no-op for all four builds.
- [Scratch cleanup](scratch-cleanup.json) and
  [final cleanup](final-scratch-cleanup.json) pass, preserving all 53 sealed
  artifacts and leaving no packet binary owners.

The strict terminal proof resolves the earlier abandoned-byte limitation for
its exhaustive miniature and sampled real coverage, without an owner exception
or model-state canonicalization. Oracle, wrapper, capture, build and admission
obligations have their own current, sealed receipts.

The 27 metric unit tests and other pure/kernel checks have their own receipts;
consult the final execution audit for current source and binary bindings. These
are separate gate counts, not one combined benchmark sample size. CPU
preparation is sealed. Device validation, actual queue overlap and latency,
same-boot exactness/speed companions and complete twelve-prompt performance
remain unmeasured. The 128-token screening cap does not satisfy the 512-token
response-cap publication gate.
