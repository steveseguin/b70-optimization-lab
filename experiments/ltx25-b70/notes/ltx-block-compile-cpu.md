# Native LTXAV block CPU compiler gate

This unit experiment follows the [stock compiler audit](compile-source-audit.md).
It tests the actual frozen `BasicAVTransformerBlock` implementation on CPU,
using synthetic BF16 weights and deliberately small channel dimensions to
bound compiler memory. It is not a checkpoint quality or speed benchmark and
does not change generation resolution, frame count, precision or sampling.
No XPU tensors, server modification or core source edits are involved.

## Scope and configuration

[The helper](../scripts/test-ltx-block-compile-cpu.py) directly instantiates the
native block class with 32 video/audio channels, one 32-wide head and eight context
tokens. Both gated attention and cross-attention ADaLN are enabled. It executes
video/audio self-attention, text cross-attention, both directions of cross-modal
attention, feedforwards, RMS normalization, native RoPE and compressed timestep
expansion. The native inference path remains selected. No numerical operation
inside the block is substituted.

Video sequences contain 64 and 256 tokens, with four temporal positions, while the
audio sequence has 26 tokens. Seeds 17 and 123 supply independent nonzero inputs at
each size. These sequence lengths exercise the existing baseline's two stage
token counts; reduced hidden dimensions are solely a CPU unit fixture. The
random synthetic weights are not extracted from the checkpoint. Attention
masks are absent in this fixture, and this does not qualify masked variants.

Input construction, `CompressedTimestep` construction, input cloning and device
routing stay outside compilation. The existing block receives real compressed
timestep objects; its native timestep arithmetic is traced. Input cloning is
required because the original block updates the video/audio streams in place.

The configuration uses `fullgraph=True`, `dynamic=False`, intact guards,
one compiler worker, one CPU compute thread, eager BF16 rounding emulation,
eager division rounding, and disabled CUDA graphs and autotuning. Compiler
cache files live in a temporary directory removed after execution. Two calls
with fresh input clones establish repeatability for each case; comparisons
require both output streams to match the native eager block byte for byte.

## Results

[Receipt01](../data/ltx-block-compile-cpu-01.json) completed all four cases:
both output streams were finite, bitwise equal to eager, and exactly repeated.
The main process reported peak RSS 1,079,504 KiB (approximately 1.03 GiB); this is
not a summed peak for compiler subprocesses. The helper was then tightened to
record Dynamo counters and require at least two compiled graphs, preventing an
accidentally disabled compiler from qualifying through output parity alone.
The [exact helper delta](../patches/ltx-block-compile-cpu-01-to-02.patch) preserves
receipt01's original helper; reversing the patch reconstructs the SHA256 pinned
in that receipt.

[Receipt02](../data/ltx-block-compile-cpu-02.json) passed the strengthened gate:
two compiled graphs covered both sequence shapes and all four cases again
matched eager and repeated exactly. Dynamo recorded 986 captured calls and no
graph breaks, with two successful AOT/Inductor compilations. The block contains
43,654 parameters (87,308 BF16 bytes). Peak main-process RSS was 1,078,384 KiB.
Receipt02 supersedes receipt01 as compilation-coverage evidence; receipt01
remains an intact earlier output-parity observation.

This gate can establish CPU capture feasibility and eager equivalence for this
fixture. It cannot establish XPU lowering, native large matrix behavior,
checkpoint-weight parity, full-clip parity, throughput or the safety of
whole-model tracing through shard routing. Those remain separate gates.

Run from the repository root with a new result path:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python \
  experiments/ltx25-b70/scripts/test-ltx-block-compile-cpu.py \
  --output /tmp/ltx-block-compile-cpu-new.json
```

The helper retains capture failures, full exception traces, current phase and
case, source hashes, compiler options and memory observation. It does not retry
or fall back to a different graph mode after failure.
