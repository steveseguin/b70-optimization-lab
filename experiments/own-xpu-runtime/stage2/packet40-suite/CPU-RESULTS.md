# Packet40 CPU qualification in progress

This supersedes the copied packet38 summary. No device ran and no packet40
speed is claimed. The build receipt remains incomplete until all current-source
qualification is sealed. Copied parent receipts and pre-rebuild attempts are
historical inputs, not authorization for the current binaries.

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

Remaining qualification is explicit: the separate one-prompt 128-token gate
must check all 128 tokens and 768 early/tail fixtures. The native real-controller
campaign has passed its first four modes; MTP remains active. Every-window
wrapper/admission refresh, complete build/evidence validation and the final seal
remain pending. Earlier wrapper receipts are historical until their current
source/binary bindings and required fresh execution are established.

The strict terminal proof resolves the earlier abandoned-byte limitation for
its exhaustive miniature and sampled real coverage, without an owner exception
or model-state canonicalization. It does not replace the remaining oracle,
wrapper, capture, build or admission obligations.

The 27 metric unit tests and other pure/kernel checks have their own receipts;
consult the final execution audit for current source and binary bindings. These
are separate gate counts, not one combined benchmark sample size. Overall CPU
qualification and sealing remain in progress.
