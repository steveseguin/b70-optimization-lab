# CPU results

No device ran; no speed is claimed.

| Prompt | Device-arithmetic draft acceptance | Packet31 FP8 acceptance | Agreement with FP8 | Agreement with int8 |
| --- | ---: | ---: | ---: | ---: |
| incident-retrospective | 84.3750% (54/64) | 84.3750% | 98.4375% | 100.0000% |
| code-review | 67.1875% (43/64) | 67.1875% | 98.4375% | 100.0000% |
| customer-email | 81.2500% (52/64) | 81.2500% | 100.0000% | 100.0000% |
| benchmark-analysis | 78.1250% (50/64) | 76.5625% | 98.4375% | 98.4375% |

Authentication rejection/teardown controls: 4; resident binding cases: 15.

Real oracle gates: five modes under each of GNU and Intel host builds; each 8/8 target tokens and 384/384 layer fixtures. No target tolerance.

Mini-model cases: gnu-host=130, icpx-host=7, asan=7.
Provider fault/state/cache cases: gnu-host=7, icpx-host=7, asan=7.

Compiled kernel captures: 351; maximum 744 bytes; 1025-byte negative control rejected.

Full per-position logit distances and sample/output hashes: agreement-*.json. Exact source/binary/official-tensor hashes and all gates: build-receipt.json.

| Prompt | Reference | Mean position RMS logit distance | Largest absolute logit distance |
| --- | --- | ---: | ---: |
| incident-retrospective | mtp_fp8_iq3 | 0.050105746 | 2.125000000 |
| incident-retrospective | mtp_int8_iq3 | 0.028970124 | 2.250000000 |
| code-review | mtp_fp8_iq3 | 0.050646897 | 1.621093750 |
| code-review | mtp_int8_iq3 | 0.030484749 | 1.601562500 |
| customer-email | mtp_fp8_iq3 | 0.048969609 | 3.062500000 |
| customer-email | mtp_int8_iq3 | 0.024394412 | 3.125000000 |
| benchmark-analysis | mtp_fp8_iq3 | 0.048444629 | 1.417968750 |
| benchmark-analysis | mtp_int8_iq3 | 0.028472148 | 1.441406250 |

Distances use the complete vocabulary at every scored position; they describe draft arithmetic only.
