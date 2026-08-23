# Ornith 1.5 35B-A3B: shared-expert scalar-gate fusions

Date: 2026-08-23 EDT

Status: **closed; aggressive form fails exactness, conservative form regresses serving**

Ornith's Qwen-derived shared-expert branch ends with a 2048-element FP32
activation projected through a one-row FP32 gate, followed by sigmoid and a
broadcast multiply over the 2048-element shared-expert output. This exact
boundary appears in all 40 MoE layers. The serialized current-stack profile
ranked the scalar projections at 238.753 us in aggregate, but those serialized
values were used only to select the boundary and were not extrapolated to
throughput.

## Aggressive three-node form: correctness negative

The first candidate replaced the stock FP32 scalar projection, sigmoid, and
broadcast multiply with one 256-work-item kernel. Its strict matcher fired all
5,080 expected times over forced 128-token generation. The custom parallel dot
reduction did not preserve the stock oneMKL reduction, however: canonical
output changed from
`d25039a7a21fccc7eaf5f9414803f80c1e3b58cc900ad8034448df8edb57e38c`
to `7f1a99473ffc6cfce7e313051a36fa8575dc2cad82140fcf4c1db7b5cfeb9181`.
It was rejected without timing.

## Conservative broadcast form: serving performance negative

The second candidate retained the stock scalar projection exactly and fused
only scalar sigmoid plus broadcast multiply. It removed 40 launches/token and
produced byte-identical forced output at all 5,080 expected sites.

| Protocol | Controls | Candidates | Mean delta |
| --- | --- | --- | ---: |
| `llama-bench p0/n128/d0/r7`, mirrored | `121.979737`, `121.507184` | `122.802105`, `122.571852` | **+0.78%** |
| fresh 12-prompt server suite | `118.812977`, `118.788521` | `117.513504`, `117.857575` | **-0.94%** |

The engine screen looked positive and both candidates beat both controls, but
the decisive fresh-server screen reversed it. All four server runs used unique
prompts once, reported `cached_tokens=0` for every row, and passed the final
measurement gate. Both serving candidates lost to both controls. Do not ship
this fusion.

The accepted eight-feature stack and its 118.048489 tok/s package headline are
unchanged. Structured results and raw rows are under
`../data/2026-08-23-ornith35b-shared-gate-broadcast-*`; both full candidate
patches are retained under `../patches/`.
