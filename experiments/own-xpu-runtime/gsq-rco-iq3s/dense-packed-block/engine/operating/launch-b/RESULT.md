# Dense packed block full-engine result

Independent closed readback passes all26 requests, all24 measured arms and all54
state bundles. Every measured token and full target state matches the original
SC117 baseline. Both target GPU contacts were observed; both owners exited and
drained safely, with unchanged fault baseline and protected vision owner.

| Mode | Output tokens | Decode intervals | Decode wall time | Interval-weighted tokens/s |
|---|---:|---:|---:|---:|
| Target-only |1536|1524|77,711.287841 ms|19.611051|
| Target-verified MTP |1536|1524|54,161.207790 ms|28.138220|

All twelve original short prompts use128-output caps and full RESET. Two disjoint
eight-token warmups are excluded. MTP retains1160 accepted and364 rejected
proposals out of1524, exactly as before. The two order groups measure28.072354
and28.204396 MTP tokens/s. Prompt processing totals21,359.404236 ms target-only
and22,812.067354 ms MTP, separately from decode; these short mixed-length prompts
do not provide a512-token prefill benchmark.

This is an internal resident screen. Separate-run comparison with the earlier
16.17/23.44 result is descriptive, not a controlled cross-binary speed claim.
All original samples remain. The older binary's long-input coverage does not
qualify this binary, and no broad-quality or public record is promoted here.
Next is the [expanded task readback](../../../../quality-expanded/PLAN.md).

The116-site Q4_K/Q5_K/IQ4_XS block decoder changes no weights, floating-point
accumulation order, BF16 output/KV, target verifier, full draft vocabulary or
resident allocation. Actual logical device bytes remain30,994,676,618 and
29,966,053,268. Native binary5aef74d5… is retained for subsequent checks.

## Accounting correction

The original unexecuted launch-A plan and sources remain in lineage. Prelaunch
review caught an inherited guard counting already-written target captures twice.
Launch-B credits only successful RESET/DUMP/FINISH acknowledgements, with all
reserves unchanged. The independently checked52-event sequence ends at zero
remaining payload after safe closure. Extra verified duplicate-file recovery
provided margin for cumulative metadata. No failed model run was retried.

## Evidence

- [Actual review](evidence/device-b/review.json):
  `ccd77d4456f5c66eb0a64d7456a3abb8a23528ab390924c703b471deece6aced`.
- [Artifact index](evidence/device-b/artifact-index.jsonl.gz):
  `56855d71b336d9658fc8fbfd1a200ec0cc14b38e71100b02565b81b674970bbe`.
- Actual plan: `7fbfc6631213c1577deb2fddf5428bcaf4b4175e3455e9440605894e45682ca9`.
- Full result: `4f4ac05e1ce87a3083439bb83f2376d3cdab59fa12876903988e0cb3dfa50970`.
- Native build: `3fe225c3c7076fbf680b3d7e0d1a051e533a34b5ed059da0048b8743323aed95`.
- Native binary: `5aef74d5f803b33758711db352ee5e1a393a364e6c33aa9f8a4cdb4478f5fe6a`.

The946 indexed artifacts total6,343,981,224 bytes. Raw evidence root is
`/mnt/usb-models/own-xpu-runtime-results/gsq-dense-packed-block-engine-b`;
control root is `/home/steve/own-xpu-runtime-results/gsq-dense-packed-block-engine-b.control`.
