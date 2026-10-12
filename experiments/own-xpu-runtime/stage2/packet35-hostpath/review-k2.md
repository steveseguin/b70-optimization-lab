# Independent K2 admission review

CPU-only review of `k2_summary.py`, the class registry, and the window gates.
No device binary was executed. The full window test suite passed77 tests after
this review, including13 additional admission regressions.

The registry lists every GEMV alternative and all required format/shape
workloads. Each comparison has a measured incumbent in the same run. The
incumbent's actual implementation must equal `baseline_implementation` where
set, otherwise the registered packet26 incumbent. Small tuple controls are
explicitly `r5.sum.members`; their dispatch fallback is the unfused control.
Diagnostic combine-norm and route-gather rows correctly name specialised as
their baseline even though their dispatch_section is null.

Every required repetition and workload is checked. Each workload separately
must have exact output and a median below0.9 times its own incumbent median.
A fast Q6 workload cannot hide a Q8 regression. Candidate availability and
implementation constancy are checked. The same-kernel predicate is evaluated
separately for every workload and honors an explicit same_kernel flag. An
alias in one workload prevents that candidate from being admitted, even if
another workload uses a distinct kernel and the aggregate timing looks good.

Each arm sums all its device events per repetition. Invalid timestamps exclude
the complete repetition. Missing repetitions, inconsistent stage counts,
duplicate recorded event IDs within a sequence, and nonexact outputs fail
admission. Where stage_count is recorded, every row in a workload/arm/repetition
must carry the same positive integer and the observed event count must match
it. This also detects a stage omitted consistently in every repetition.
Stage_count denotes the total arm count, including every incumbent sibling
submission for a fused comparison; it is not one individual submission's count.
The parser retains compatibility with historical rows containing no count.

A candidate failure excludes that candidate while preserving a complete table
and allowing other candidates/classes to run and qualify. Its measured
incumbent still must be complete and exact. Incumbent failure, missing
candidate coverage, execution-budget violation, or an incomplete workload
cannot be waived by recording a candidate failure. Candidate failures are
reported before safe teardown by the native fixture driver.

K1a/K1b require different owner PIDs, identical candidate-dispatch hashes,
matching output hashes against the host fixture result, and four safe owner
teardowns. K2 must link those two fixture receipts and the candidate identity.
W2m/W2c require the admitted K2 receipt, unchanged measured dispatch, events,
and summary hashes, plus the same K1 linkage. W2 forbids a custom dispatch and
uses the recorded packet26 default selection. No K2 result is presented as a
model decode speed.

Fixes from this review:

- Reject a baseline kernel that differs from the registered incumbent.
- Reject same-kernel candidates per workload, including explicit alias flags.
- Report bytes_equal only when both arms are exact.
- Reject duplicate stage event records.
- Validate declared complete stage counts, including uniform truncation and
  malformed/missing per-row metadata.

Regression tests cover complete multi-candidate selection, missing alternatives,
wrong incumbents, one-workload aliases, declared aliases, partial workload
coverage, failure isolation, incumbent byte failure, duplicate events, complete
stage counts, uniform missing stages, malformed counts, and partial metadata.

This review establishes parser/admission behavior only. Device exactness,
profiling timestamps and performance still require coordinator windows.

Final review also checked the native priority receipt. The wrapper records its
requested native nice level and compare_run requires both native_nice and
observed_nice to equal it. Priority metadata does not affect arithmetic or K2
kernel selection. The latest77-test window suite passed after this addition.

## Packet25 half-table coverage amendment

The final registry now requires `p25.half_table` for both expsgate.iq2 and
expsgate.iq3, matching the bridge alternatives list and the device-entry
validation gate's expected candidate set. K1 and K2 both enumerate that list;
K1 therefore compares it with the real R5 control and the unchanged CPU oracle
in every finite-input mode. K2 records the scale-preparation event and the
following GEMV event as one two-stage candidate sequence, so preparation cost
cannot disappear from the comparison. Missing half-table coverage fails the
registered candidate/workload gates. Missing, undersized and aliased scale
workspace mutations are also exercised before submission.

Dense packet25 alternatives remain rows4, scale8 and wide8. Routed IQ4 keeps
rows4, wg32, private_decode and wide8. Routed gate/up keeps rows4, wg32,
private_decode, paired_input and half_table. The unchanged real R5 kernel is
the control. The explicitly forbidden staged full-weight decode candidate
remains excluded. The77-test window suite passed again after the registry
amendment; no native binary or device entry was launched for this review.
