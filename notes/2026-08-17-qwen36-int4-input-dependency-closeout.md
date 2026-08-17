# 2026-08-17 Qwen3.6 27B INT4 input-dependency closeout

## Decision

Stop experimenting. Preserve the dependency work as a **failed normal-gate
candidate**, not a production patch. The current runtime is intentionally left
unchanged pending operator discussion; no restore and no additional diagnostic
was performed beyond the agreed matched gate and one bounded correction.

The final warmed four-prompt run is genuinely strong bounded evidence: all four
complete token arrays match both sealed target controls and the preferred
99-interval median is **`110.675 tok/s`**. It is not the normal promotion gate.
The suite is diagnostic-only and the objective quality gate was skipped.
The matched final-source 25-prompt candidate was only **15/25 exact** and
measured **`96.386 tok/s`** strict. The one permitted correction broadened the
dependency to all INT4 calls; it worsened parity to **12/25 exact** and measured
**`96.578 tok/s`**. Both are below `100 tok/s` and the historical `99.798 tok/s`
central screen. This approach therefore fails the agreed normal gate.

## Concise control table

Rates marked diagnostic are cold, traced, raw, or deliberately zero-accept and
must not be compared with warmed throughput.

| Control | Correctness | Execution | Warmed | Throughput |
| --- | --- | --- | --- | ---: |
| Current target 25 | reference | compiled PIECEWISE, M1 | yes | `50.067` strict |
| Current safe candidate 25 | 17/25 exact | compiled PIECEWISE, MTP3, exact GDN eager break | yes | `96.519` strict |
| Fixed-M4 target | 128/128 exact | target M1 with W4A16 padded to M4 | no | `11.675` strict, diagnostic |
| Synthetic zero acceptance | 128/128 exact | compiled MTP3, packed M4, accepts zero drafts | no | `7.044` strict, diagnostic |
| Normal incident trace | wrong at output 77 (`506`/`279`) | compiled MTP3 with trace | no | `8.104` strict, diagnostic |
| Python layer-0 event | 82/82 exact | raw/eager verifier | no | `5.459` legacy, diagnostic |
| Broad pre-schema INT4 dependency | 82/82 exact | raw/eager, all W4A16 | no | `5.457` legacy, diagnostic |
| Rebuilt raw scopes: layer0, all GDN-in, target, INC, all INT4 | all wrong at output 77 | raw/eager verifier | no | `5.492`–`5.536` legacy, diagnostic |
| Compiled all-INT4 dependency | 82/82 exact | compiled PIECEWISE MTP3 | no | `6.722` legacy, diagnostic |
| Compiled layer-0 dependency | 82/82 exact | compiled PIECEWISE MTP3 | no | `6.695` legacy, diagnostic |
| Compiled Python model event | wrong at output 77 | compiled PIECEWISE MTP3 | no | `6.708` legacy, diagnostic |
| Warmed layer-0 focused canary | 128/128 exact | compiled PIECEWISE MTP3 | yes | `108.966` strict |
| Final warmed four-prompt candidate | **4/4 exact** | compiled PIECEWISE MTP3 | yes | **`110.675` strict** |
| Final-source target 25 | reference; quality/cache pass | compiled PIECEWISE target-only | yes | `50.101` strict |
| Final-source layer0 candidate 25 | **15/25 exact**; quality/cache pass | compiled PIECEWISE MTP3 | yes | `96.386` strict |
| One correction: all-INT4 candidate 25 | **12/25 exact**; quality/cache pass | compiled PIECEWISE MTP3 | yes | `96.578` strict |

The final root is
`/mnt/usb-models/bench-results/qwen36-27b-autoround-int4-b70/int4-input-dependency-layer0-four-spec-a-20260817T014146Z`.
Its verified final manifest SHA256 is
`988ff654c1a3d0ddf7efd4a6331cfe955ceafdd914d82c90314896b8e2cd36a4`.

## What the focused trace established

The incident mismatch was an accepted verifier row, not a sampler leak. At
output index 77 the packed verifier preferred token `506` over target token
`279` by only `0.015625`. A device-only boundary after layer-0 normalization
and a broad pre-oneDNN dependency both changed the focused result to `279`.
The narrowed compiled oneDNN dependency then retained the focused correction
and warmed performance.

That is evidence of an ordering/code-generation-sensitive boundary at the
layer-0 GDN input projection. It is not a complete causal proof, because an
apparently equivalent rebuilt raw all-INT4 scope did not reproduce the broad
raw repair.

## Contradictions and confounders

- Broad pre-schema raw dependency: exact. Rebuilt raw scopes through all INT4:
  still wrong. The rebuild/schema/code-generation change is a live confounder.
- Compiled C++ dependency: exact on the focused prompt. Compiled Python event:
  still wrong. These are not interchangeable graph dependencies.
- The four-prompt output is also identical to the earlier safe-default
  four-prompt candidate; the matched normal gate proved that it did not
  generalize to the complete suite.
- Cold 5–12 tok/s rows include first-request compilation, trace overhead, or
  forced rejection. They say nothing about steady-state performance.
- The matched target itself differs from the older target on 10/25 prompts;
  only the final-source target is a valid comparator for these two candidates.
- The sole correction, all-INT4 dependency publication, worsened parity and
  did not clear the speed bar. No further correction is authorized.

## Preserved state

- [Structured control summary](../data/qwen36-27b-autoround-int4-input-dependency-controls-20260817.json)
- [Source/config packet](../patches/qwen36-27b-autoround-int4-b70/int4-input-dependency-20260817/README.md)
- Patch-packet manifest SHA256:
  `339d46f140c0c284d839c76b86d162373e0282a06deb1113771409240fe8081e`.
- All relevant raw roots now have post-teardown `SHA256SUMS` files that verify.
- [Sealed-root manifest index](../data/qwen36-27b-autoround-int4-input-dependency-sealed-roots-20260817.sha256)
  covers 22 roots and has SHA256
  `571d78b1624d091f8336f06ad9aaee2fd20c977923edc7f60c20ac56becd7d42`.
- Tested candidate `_xpu_C`: `ccbeecb4e49eb3419f5a8734c82e2b004bfdd9dffea5f0a9bbe2e8884041ef38`.
- Retained pre-dependency `_xpu_C`:
  `f494925774cf50cd2038684cb64325fcd491c51f2eab94454878c5e804dbaa61`.

No LocalMaxxing submission is warranted. No runtime was restored.
