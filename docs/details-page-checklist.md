# Details page checklist

Every model page on neural.download — all cataloged family pages (`models/<family>.html`,
from `tools/build-family-pages.py`) and the 13 package pages
(`models/<package-id>.html`, from `tools/build-model-pages.py`) — must carry the
same skeleton. A section with no data is shown as a labeled gap, never dropped,
so a visitor can tell "not measured" from "measured and boring". Nothing on the
page is hand-edited; fix the generator or the manifest and regenerate.

## The skeleton (in order)

| # | Section | Family page | Package page | Empty state |
| --- | --- | --- | --- | --- |
| 1 | **Hero**: breadcrumb · h1 (display name) · plain summary · **the measured headline number** (big), unit, ≈ words/second, one-line identity (cards · quant · runtime · single user · declared gate) | `featured_results` hero binding, else the promoted packet metric, else the best lab-measured decode run — never a sweep point, never a demoted run | `library.featured_metric` | A family with no measured decode run shows no number and says so |
| 2 | **Other measured results strip**: best result per other configuration + best combined multi-user rate, each with a visible gate word (✓ Full quality gate / ◇ Speed check only), never repeating the hero | curated `featured_results` support entries | — (single result) | omitted when there is nothing else |
| 3 | **Primary action**: "Open reproduction guide" / "Open deployment packet" only when a `repro/` guide or `packages/` manifest exists; otherwise "Read the lab report" plus "No step-by-step install guide is published for this model yet." | `packet_manifest_target` | "Open the full guide" + Copy Markdown | report tier is visible, never dressed as a guide |
| 4 | **Signals / facts**: one-line meta strip (B70 fit, quality evidence, measured results) with plain-words values | meta strip | facts grid incl. Good-for chips | pending/zero signals are dropped, not shown as 0 |
| 5 | **Packets and recipes**: one card per deployment variant, "Reproduce X tok/s on N× B70", status in words, evidence grade spelled out, lab-report cards marked as reports | packet cards | — | — |
| 6 | **What has been tried**: plain-words line per tested combination ("4 cards, no speculative decoding"), codes as tags, ⚠ failed runs with the number in muted prose, untested cells collapsed to one sentence | combos list | — | "No classified combinations in this slice yet." |
| 7 | **Measured results**: a chart only for ≥3 distinct x positions on a continuous axis; otherwise stat rows (current first, superseded muted); every point links to proof | views | measured performance profiles | grey "Not measured" placeholder |
| 8 | **Many people at once**: measured aggregate sweep when one exists, else a placeholder pointing at `learn/multi-user.html` | aggregate series | placeholder | placeholder |
| 9 | **How much faster could this get?** (labeled *Projected — not measured*): the ML Bottleneck card — measured here · tuned-run target · physical ceiling, grade = measured / target — plus projected input-length and users curves; built from the hero run's own quant/runtime/cards/workload | `FAMILY_ML_MODEL` map + hero measurement | `PACKAGE_ML` map | "No projection: this model is not in the ML Bottleneck catalog yet" / "no curated headline yet" / "workload shape not comparable" |
| 10 | **Fine print**: transfer boundary behind a toggle | ✓ | — | — |
| 11 | **Keep going** | ✓ | ✓ | — |

## Honesty rules that apply to every section

- Measured and projected numbers never share a table or a bar chart without a
  visible label; projections live only in section 9 and the plan links.
- The stock-software projection is not shown on model pages (it is the least
  trustworthy number for tuned Intel stacks); the card shows measured vs
  tuned-run target vs physical ceiling.
- Superseded, quarantined, and research numbers are visually subordinate to the
  promoted result and say why in words.
- Every visible number links to its evidence; the hero links to its record.
- Meaning required for honest reading is visible text; tooltips only add depth.
- No machine-local paths, run hashes in prose, or lab-internal run names as
  headings.

## Checking a page

`tools/test_build_family_pages.py` and `tools/test_measured_opt_contract.py`
pin the answer-first order, the hero binding rules, and the projection-workload
contract; run both after any generator or manifest change, then regenerate.
Visually: hero number is the largest element; nothing clips at 390 px; the
projection block renders a card with three bars when a mapping exists.

## Current gaps (2026-08-25)

- Families with no ML Bottleneck preset (no projection block yet):
  deepseek-coder-v2, nemotron-cascade-2, qwen-14b.
- Families with no measured multi-user sweep: all but qwen-35b.
- Families with no install guide (report tier): see each page's action button.
