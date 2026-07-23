# Laguna shared-down counter analysis repair authorization

Date registered: 2026-07-23 America/Toronto

Status at registration: the first and only authorized counter capture completed
all 16 arms and sealed its campaign closure at
`shared-down-m8-counters-20260723T173812Z`. The original analyzer then failed
closed before writing an analysis because its device-timing parser assumed a
single row. No counter rerun, endpoint service, model generation, payload, or
submission occurred.

Read-only inspection proved that `--include-kernels gemm_kernel` filtered the
13-row metric-query table but not unitrace's device-timing summary. Every
sealed arm has the same exact six-row timing identity/call multiset: the
selected verbose SIMD16 GEMM plus five fixture memory-copy aggregates. Row
order varies because unitrace sorts by measured time. All timing totals,
integer averages/ranges, percentages, one-row GEMM properties, 96 raw evidence
file hashes, 16 arm manifests, four card manifests, 208 raw call-output hashes,
the campaign-open link, protocol digest, and authorization digest close
exactly.

Rerunning after observing the parser failure would create an avoidable second
sample. This authorization therefore permits one offline parser-only analysis
of the first sealed capture and explicitly forbids counter reexecution.

## Immutable inputs

- original execution authorization SHA-256:
  `3b8aa2cf10f27e50ccae778071b8d0b96480dd7c03a852b7199cb0de40928b1a`;
- campaign-open SHA-256:
  `c2ae3b524d010e118df0be0fed17e5c81718dc5376f38db8ca3d3c9ac3ccbb46`;
- campaign-complete SHA-256:
  `164d124d7d88b9ec4dd3a7f1280feb7ec274538fb9ccc842f62671e951562c12`;
- original runner SHA-256:
  `2c551194c55886138dab88854782ce9d008532fe358f8cf4bb1f1d502de3f0ab`;
- original analyzer SHA-256:
  `d3b8472556b558d92a2e73617ed7d968e03920126af71cba67719dae8f73fa24`.

## Repair boundary

The repair source commit is
`59952ea3f932d2c31b3c9f143b2295ce9b8d51f0`. The repair analyzer SHA-256 is
`14b18b3ba785e3ef2be44b009531aa8b249a07e1d341fa894dbd2f7a06c2a195`;
its 11-test CPU tamper suite SHA-256 is
`e70d481bc143be11921a2b0716c6d3bae4ee7a49b2ff0c7796c4ac262fe673fd`.
Ruff, formatting, whitespace, source-byte loading, and all 11 tests pass.
Independent source, authorization-design, and evidence audits report PASS.

The repair executes the exact hashed original runner/analyzer source bytes,
replaces only `parse_timing_properties`, and reuses the original metric parser,
campaign validator, exactness checks, comparisons, and thresholds unchanged.
It requires exact timing/property CSV headers and every physical record, the
unordered six-name/call set with no extras, exact L0 total linkage, bounded
display-percentage rounding, and the frozen AOT GEMM properties.

The original campaign root remains immutable. Any result is created
exclusively under the new local-NVMe sibling:

```text
/mnt/fast-ai/llm-optimization-artifacts/laguna-s-2.1/runs/shared-down-m8-counters-20260723T173812Z-analysis-repair-20260723T175756Z
```

The tracked structured authorization is
[`data/laguna-s-2.1-shared-down-m8-counter-analysis-repair-authorization-20260723.json`](../../../data/laguna-s-2.1-shared-down-m8-counter-analysis-repair-authorization-20260723.json).
It authorizes only sealed-capture reuse and offline analysis. Counter
reexecution, endpoint preregistration construction/execution, model generation,
payload creation, and LocalMaxxing submission remain false even if analysis
passes. A passing result requires a separate independent audit before any
endpoint preregistration is constructed.
