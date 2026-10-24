# Exact kernel result; physical observation incomplete

**The operating qualification remains failed/incomplete.** Independent audit confirms
all84 native control/candidate comparisons match all6,400 BF16 outputs and ten status
values against the saved original baseline. The native owner completed safely with
zero live allocations/in-flight work and no signals. The post-run target descriptors
were empty; the fault baseline and protected vision process were unchanged.

The1.366second run ended before the passive monitor observed a native target GPU
file descriptor. The intended BDF was0000:23:00.0, but this run does not independently
attest that physical assignment. Neither the terminal nor this result is upgraded
to a fully qualified device result. The independent review deliberately separates
`audit_passed=true` from `passed=false` and `qualification_complete=false`.

The retained event-time observations below are from that incomplete qualification.
They cover72 measured pairs after12 excluded warmup pairs, both AB/BA orders,
three fixed real routed cases and168 kernel submissions. These are repeated isolated
kernel events with fixed routes/consumed slices, not full-model expert traffic,
model throughput, cold-cache timing or a public record.

| Fixed case | Measured pairs | Candidate/control summed event time | AB | BA |
| --- | ---: | ---: | ---: | ---: |
| Layer 0 | 24 | 0.422922 | 0.429558 | 0.416494 |
| Layer 22 | 24 | 0.424351 | 0.433586 | 0.415519 |
| Layer 46 | 24 | 0.415145 | 0.433110 | 0.398313 |

Across all72 measured pairs the ratio is0.420782. All pairs and bothorders are retained; no tolerance or outlier removal was used.

This supports preparing the34-site full-engine candidate for a **new** qualification.
That run must use complete model banks, changing routes, all original prompts and
exact target-state checks, with positive physical ownership observations for both
ranks. It can establish its own qualification; it cannot retroactively pass this
micro or establish the physical BDF of these event timings. No micro replay is queued.

[Independent audit](evidence/device-a/review.json) SHA256:
`70b9710a4dce8048cbaf3caf53f887beefbdae56930aad39dabc38490c346ba5`.
Native binary SHA256:
`fb6b43d571240313f30ab1aa1f75aff92cfc895481d6ddd80d8e328a6dad4e27`.
Native build receipt SHA256:
`50a6fe7ab35a9688ad291c78679e54991dca8c946f9388a2d420a2e1bd4ed39a`.
[Operational plan](evidence/operating-plan.json) SHA256:
`38c8cc86c52f220fce53cb7267b4c1053c93722efe1f48337bbbc74a8e7e24eb`.
Raw receipts/results stay at
`/home/steve/own-xpu-runtime-results/gsq-iq3xxs-block-micro-a`.

The initial native compile failed for two missing backend includes before any GPU
execution. The include-only fix and failed attempt are preserved. The real fixture
extraction used the originald403 reader successfully; the later failure-flag fix
is preserved separately as unexecutedv2. All15 fixture files and the generated
header were independently verified. Neither issue changed kernel arithmetic or
required repeating the successful CPU proof or extraction.
