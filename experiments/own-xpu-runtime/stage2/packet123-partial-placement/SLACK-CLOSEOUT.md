# Packet123 slack investigation — closeout

<!-- campaign-closeout -->

## Question and identity

October18, CPU-only: can bundle7 move layer24's mixer or FFN from rank1 to
rank0 with at least0.3 ms spare hit-path time? Existing lane-B composite
`p118-89f2d60778eb2d6e`, Unsloth quantized compressed Flash-Next,
`iq3-p49-split32-v1`, two B70s, fixed80,128 draft prefix, split target head.
Exact identities and original inputs are pinned in [slack.json](slack.json).

## Outcome

Blocked at slack admission, not a measured placement loss. Across932 hits,
the apparent rank0 tail is0.482640 ms, but untraced head service consumes an
unknown part. Measured copies alone consume at least0.043010 ms, leaving a
loose mean upper bound of0.439630 ms. Actual slack is unknown; neither
≥0.3 ms admission nor <0.3 ms closure is established. No implementation,
compile, memory census, byte gate, smoke, seal or queue proposal followed.

## What worked

The unchanged packet108 command-union and packet85 interval join reproduce
all2,376 intervals from the candidate and prior control. Inspecting the
current controller and head path prevented treating mandatory head work as
idle time. An independent read-only review reached the same conclusion.

## What failed or remains uncertain

The old dependency accounting predates the head split. Rank0's suffix
service is outside command tracing; rank1's command includes its merge wait.
Empty event files and duration-only transfer rows cannot recover service
begin/end or available slack. The first raw extraction's apparent admission
was withdrawn before any runtime change. No partial-layer benefit or loss
has been measured, and no new output-quality result is claimed.

## Evidence and patches

[Definitions, numbers, source reasoning and replay](README.md),
[summary and hashes](slack.json), [every interval](intervals.json.gz),
[original-byte input snapshot](inputs.tar.gz),
[CPU extractor](extract.py), [snapshot writer](capture_inputs.py),
[unchanged packet108 method](method/p108_extract.py),
[unchanged packet85 join](method/p85_model.py).
There is no runtime patch. Snapshot members are byte-verified; original
untracked logs and every frozen tree remain intact. See README retention.

## When to revisit

Obtain common-clock rank0 head-service and rank1 head-readiness timings with
request/position/sequence identities in a separately authorized device run.
Recompute the gate on that exact bundle before preparing partial placement.
The current CPU-only task does not authorize that run. No owner question or
GPU launch is pending from this packet; the coordinator has the prerequisite.
