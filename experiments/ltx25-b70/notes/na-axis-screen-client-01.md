# Decoder-axis native screen prepared

2026-09-14. New client and stdlib validator are ready for root review against
sealed packet09. This preparation made no endpoint request, native decode,
GPU initialization, profiler attachment, service action, or installed-source
change. Existing packet08 and its artifacts remain untouched.

The schedule is11 sequential clips: two bare original boat controls (first
initialization, second warm), followed by scoped original/cache/original triples
for boat42, marble17 and bird123. Numbered names follow `campaign-rNN-...`,
which the existing retention ownership guard accepts. No compiler gate or
node422 is present. Both guider model inputs still reference resident420
directly. Relative to the original encoder-control graph, only node374 changes
to `LTXNAAxisDecode` for scoped rows; samples/VAE connections stay identical.

[`run-na-axis-screen.py`](../scripts/run-na-axis-screen.py) reuses hash-pinned
encoder helpers and the packet08 client identity binding. It pins packet09
manifest `a53e06ae5bd1be8931eff11d4e9112b850912147b37fcabf1bda064b12f419ed`
and verifies its packet08 parent. Offline checks verify the complete packet,
runtime fingerprints, candidate/router/source hashes, exact graph changes and
decoder configuration. They do not contact the endpoint or import Torch.

Runtime admission additionally fetches `/object_info/LTXNAAxisDecode` before
any request and each subsequent preflight. Exact required inputs, output,
module, category and list/output-node flags must match. Comfy can swallow a
custom-node import error, so file identity alone is insufficient. Legacy
`object_info` does not expose `FUNCTION`; the pinned node source fixes
`FUNCTION="decode"`, while the endpoint check establishes registration.

[`ltx_na_axis_receipts.py`](../scripts/ltx_na_axis_receipts.py) validates both
exclusive `started.json` and `result.json` from each
`server_run/na-axis-RUN/` directory. The result must bind source/server/model
identity, four unchanged VAE owners, actual checkpoint config, scope reset,
monotonic timestamps, input/output metadata, and every ordered native NA call.
Each call checks all three input shapes/dtypes/devices, kernel, causal flags,
scale, output metadata, completion and index. The expected heads, stage lengths,
kernels and spatial/temporal growth come from the pinned decoder config and
audited untiled forward/upscale rules. They yield24 calls for this configuration,
rather than accepting any24-call sequence or trusting the first observation.

The caller supplies `is_causal=None`, but public Kitchen normalizes it to
`[False, False, False]` before dispatch reaches the router. Root review caught
the initial incorrect receipt expectation; the final test directly checks this
against preserved actual CPU router evidence. Boolean values cannot impersonate
integer dimensions or scalar scale values in the receipt validator.

Checkpoint metadata also contains decoder annotation keys absent from source
defaults. A naive whole-default-dictionary comparison would reject valid native
receipts. The client reads only the81,544-byte safetensors header plus8-byte
prefix, binds their SHA256, verifies every numerical decoder setting consumed
by the constructor matches the reviewed defaults, and compares actual model
config exactly to the header config. See
[`na-axis-checkpoint-config-01.json`](../data/na-axis-checkpoint-config-01.json).
This does not reverify the entire weight payload; the original model-verification
receipt remains the full-weight identity evidence.

The first scoped original receipt must match that source-derived untiled
sequence and pass the original four-output oracle before it becomes the
campaign discovery record. A different count/shape/tiled path stops the campaign
before the cache request; evidence is preserved for review without automatic
scope widening or retry. Every later scoped receipt must match the complete
discovered sequence, owners, input/output metadata and thread. First latent
device metadata is admitted only for CPU or the four indexed XPUs, then frozen;
old captures move tensors to CPU and cannot establish their earlier device.
All NA calls themselves require BF16 on XPU3.

Every clip must match original images, video latent, audio latent and waveform
bytes with strict determinism and finite, expected-size CPU captures. Only then
can owned raw archives be deleted. Latest three passing review previews remain.
Pair reports include both preview and decoder node event intervals. These
include diagnostic overhead and are screening measurements, not kernel timing
or a promoted speed claim. Timeouts/failures stop submissions and preserve the
server/job; they never retry, restart, restore a process, or bypass a fault.

Validation:

- [`test-na-axis-screen-stdlib.py`](../scripts/test-na-axis-screen-stdlib.py):
  14 tests passed, covering the real pinned source/header config, actual CPU
  causal normalization evidence, valid original/cache/original metadata,
  adversarial sequence/source/owner/context/type changes, started/result binding,
  exact graph scope, schedule, object-info admission, timing direction, and actual
  temporary-file retention ownership/deletion guards. No Torch import occurred.
- Final test receipt/log:
  [`na-axis-screen-stdlib-03.json`](../data/na-axis-screen-stdlib-03.json),
  [`na-axis-screen-stdlib-03.log`](../data/na-axis-screen-stdlib-03.log).
  Earlier01/02 receipts remain as version-specific development evidence;01
  predates the corrected public causal normalization and is superseded by03.
- Final offline sealed-packet check:
  [`na-axis-screen-check-only-02.json`](../data/na-axis-screen-check-only-02.json).
  The planned requests are printed; executed native requests remain zero.

Final client SHA256:
`c8a053d7ed0d6bc17585f0aab09cefb1f034151342fed96f542a04cd8adf1153`.
Validator SHA256:
`ac11e8fc95275660d76336cafd892a6ec67e0c4f68b0208f5752a328b254274c`.
CPU tests qualify the validator, not native decoder geometry, video parity,
continuation, or speed. Root owns deployment and any subsequent execution.
