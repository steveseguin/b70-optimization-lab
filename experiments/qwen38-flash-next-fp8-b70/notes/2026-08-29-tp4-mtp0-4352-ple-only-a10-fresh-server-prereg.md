# Flash-Next TP4 MTP0 PLE-only A10 fresh-server preregistration

## Objective

Run one fresh server with the exact passing A9 model, source, staged runtime,
placement, cache, and request battery. This is the required fresh-server
determinism gate for the PLE-only optimization. It is not a new selector or an
unchanged retry of a failure.

## Frozen identity

A10 retains:

- `Qwen/Qwen3.8-Flash-Next-FP8` revision
  `bcd9f01ddc9cff2316eb84281bebcd5b058bddce` from local NVMe;
- vLLM `e5137bfd8ca2ca718c4fd93d86d54bb843e2999b`, kernel source
  `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`, and staged build
  `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- TP4/EP4, eager graph-off, MTP0, 4,352 maximum tokens, one sequence, 64
  scheduled tokens, automatic KV dtype, disabled prefix caching, and disabled
  async scheduling;
- only `ple_embedding.ngram_embedding.weight` in selective UVA host placement,
  12.0-GiB/rank budget, input embedding on device, and exactly 134,217,728
  cache bytes per rank.

Only lifecycle identity changes: attempt 10, port 19682, A10 state/RPC paths,
and distinct raw-evidence roots. The campaign remains
`qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1` because serving
identity is unchanged.

Frozen tools:

- `tools/launch-tp4-mtp0-4352-ple-only-a10.sh`;
- `tools/run-tp4-mtp0-4352-ple-only-a10-client.sh`;
- `tools/supervise-tp4-mtp0-4352-ple-only-a10.sh`.

The A10 wrappers checksum-bind their A9 source, their derived executables, and
the exact launcher/client wrappers. No GPU launch is authorized until this
packet is committed on `main`.

## Required gates and interpretation

Repeat the complete A9 sequence: exact source/model/runtime checks, four-card
idle discovery, four-rank collective, four exact 11.92-GiB receipts, 4,747-or-
greater cache admission, health, recovery canary, the seven-case semantic
battery, 16/16 fixed repeats, exact cache-zero 4K needle, three short timing
rows, two exact-4K timing rows, and owned clean B70 teardown.

Every short row must return
`5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`.
Every exact-4K row must return
`1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc`.
The direct battery may retain only the inherited `code_execution=30` miss.

- Any fit, output, repeat, semantic, lifecycle, or B70 postflight failure
  rejects fresh-server qualification and leaves A9 Grade C.
- A full pass establishes the placement as a reliable/lossless MTP0 base under
  the two-server bounded contract. Report A9 and A10 separately plus the
  central estimate; never overwrite either run.
- A speed regression does not lower A9 or any older result. It is stability
  evidence and must be interpreted before further optimization.
- Corrected events limited to local NVMe remain a disclosed clean-host caveat;
  any B70-addressed event fails postflight.

No MTP, graph, alternate cache, source patch, website change, or LocalMaxxing
action is authorized in A10.
