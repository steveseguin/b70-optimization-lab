# Float continuation input implemented; runtime qualification pending

The next-clip graph now has a concrete provider for the predecessor's final
float32 frame. This advances the continuous-generation stage of [the plan](../PLAN.md)
without changing the independent-clip speed or quality baseline. The host fault
remains active: PID96119 and the tiny CPU-test PID102144 were still present with
SIGINT pending at this turn's bounded status check. PID95931 remains present.
No Torch imports, GPU requests, server actions, reboot, device reset or host
setting changes were performed in this work.

## Implementation and cost

[continuation_anchor_io.py](../scripts/continuation_anchor_io.py) reads the
safetensors header and exactly786432 bytes for frame24 of the original
`images` F32 `[25,256,256,3]` capture. It validates tensor ranges and finite
IEEE754 sample bits without converting samples. The [I/O note](continuation-anchor-io-cpu.md)
details its bounds and failure handling.

[continuation_anchor_node.py](../scripts/continuation_anchor_node.py) supplies
`LTXLoadFloatContinuationAnchor(predecessor_run, expected_sha256) -> IMAGE`.
The expected digest is checked against the actual captured bytes on each
request. A changing-cache hook prevents a cached IMAGE from hiding a missing or
changed capture. Its successful runtime path explicitly uses float32
`frombuffer`, reshape and clone into independent CPU storage; it contains no
media decoder, clamp or precision conversion. That Torch path has **not run**.
The fault check precedes any tensor-runtime import or input read.

The node accepts simple lowercase capture names under the output validation
directory. Existing symlink paths are rejected, but this is not a concurrent
filesystem replacement lock. The future stream controller must own the
predecessor's immutable lifetime. A filename/hash alone does not establish
the previous chunk's model/runtime identity or prompt/seed schedule.

Extraction checks every sample once. The provider compares the resulting
digest without repeating the same Python finite-value scan. Error strings are
constructed only for invalid samples. These remove unnecessary work from this
new input path; no latency or full-clip speed improvement has been measured.
No full clip is loaded to construct the anchor, and no new media is saved.

[bind-continuation-anchor.py](../scripts/bind-continuation-anchor.py) pins the
previous graph constructor, adds this one provider node, and validates the now
closed graph. Both existing native image-conditioning nodes use its output.
Sampler schedules, seed application, resolutions, precision and audio paths
are unchanged from the [continuation graph constructor](continuation-graph-constructor-cpu.md).
The wrapper also restricts new run names to the existing capture node's
lowercase rule; the older generic constructor allowed uppercase names.

The output remains an inactive envelope, with deployment, native tensor
qualification, predecessor lineage, delivery slicing, replay, seams and audio
alignment explicitly pending. `provider_implemented=true` means code exists,
not that it is installed or qualified. A [concrete module](../data/continuation-anchor-reference-module-01.json)
uses the preserved boat frame hash, predecessor `baseline-01`, seed43 and output
`continuation-reference-boat-01` for future review. No graph was submitted.

## Evidence

- [13 I/O tests](../data/continuation-anchor-io-cpu-01.json) cover malformed
  captures, exact float bit patterns, nonfinite samples, file ranges, bounded
  reads and nonregular input rejection.
- [12 integration checks](../data/continuation-anchor-node-cpu-02.json) cover
  exact synthetic predecessor bytes, corruption, paths, the fault gate before
  Torch import, node schema, unchanged graph except for the provider, and
  accurate pending qualification fields. The successful Torch tensor path is
  deliberately not executed. [Log](../data/continuation-anchor-node-cpu-02.log).
- [Three protected reference captures](../data/continuation-reference-anchors-01.json)
  passed actual byte validation. The verifier streamed all images in64KiB
  reads and matched their original tracked hashes, independently retained the
  final frame, and matched both the extraction helper and provider's byte-read
  path against it. This used existing boat, marble and bird captures only.
  It saved compact receipts, no payloads or clips. It did not run the tensor
  path or establish any generated continuation result.

The initial integration test also passed before removing the duplicate scan.
Its [receipt](../data/continuation-anchor-node-cpu-01.json) and
[log](../data/continuation-anchor-node-cpu-01.log) remain preserved.
[Initial source archive](../data/continuation-anchor-node-source-01.json.gz)
contains the exact helper, provider, binder and test bytes named by that
receipt; the unchanged base constructor remains pinned separately. Final
receipts bind the current source. No failed numerical run is recast as passing.

Useful repeat commands on a healthy host, with new receipt paths:

```bash
python3 experiments/ltx25-b70/scripts/test-continuation-anchor-node.py \
  --receipt /tmp/continuation-anchor-node-check.json
python3 experiments/ltx25-b70/scripts/verify-continuation-reference-anchors.py \
  --receipt /tmp/continuation-reference-anchor-check.json
```

## Next requirements

Implement bounded delivery state and single-request scheduling: bind each
completed predecessor, exclude frame0 after the first chunk, prevent duplicate
delivery and unbounded queues, and preserve failed state without automatic
retry. State must retain only the required anchor and bounded review/playback
buffers; this read-only provider does not implement retention or deletion.

After host recovery, qualify the native tensor path, prepare and attest a
separate runtime, then establish a short continuation chain with exact replay
and visual seam review. VAE conditioning can change the decoded boundary
pixels; lossless anchor transport does not guarantee exact boundary pixels or
long-term scene coherence. Audio timing remains unresolved. The greater-than24
new frames/second target, original quality gates and endurance requirements
remain unchanged and unachieved.
