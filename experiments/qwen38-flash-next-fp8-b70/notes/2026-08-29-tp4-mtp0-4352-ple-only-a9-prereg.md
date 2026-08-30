# Flash-Next TP4 MTP0 4K PLE-only A9 preregistration

## Objective

Test one deployment-shaped placement candidate for the active
`Qwen/Qwen3.8-Flash-Next-FP8` lane: maximize reliable, lossless MTP0 decode at
the user's roughly 4K ceiling before adding MTP, longer context, or prefill
work. This arm is additive. It cannot lower, replace, or relabel any captured
speed.

## Frozen change

Relative to the passing current-runtime configured-4,352 anchor, change only
the following material memory selectors:

- keep `ple_embedding.ngram_embedding.weight` in host RAM through selective
  UVA: 12,800,061,440 bytes per rank, or 51,200,245,760 bytes across TP4;
- move `embed_tokens.weight` back to device memory: 317,849,600 bytes per
  rank;
- reduce fixed KV memory from 201,326,592 to 134,217,728 bytes per rank;
- use `cpu_offload_gb=12.0` with only the exact PLE selector.

The candidate retains the local NVMe checkpoint, TP4/EP4, MTP0, eager
graph-off execution, BF16 activations, FP8 model artifact, automatic KV dtype,
one sequence, 64 scheduled tokens, disabled prefix caching, disabled async
scheduling, and configured maximum length 4,352. There is no diagnostic patch
or sampler change.

The net device increase is 250,740,736 bytes (239.125 MiB) per rank. Scaling
the passing anchor's 7,121-token/201,326,592-byte cache gives about 4,747
tokens at 134,217,728 bytes, above both the 4,224 tokens required by the exact
4K gate and the 4,352 configured ceiling. This is static evidence only; live
admission and fit remain required. The structured arithmetic is in
`data/20260829-tp4-mtp0-4352-ple-only-static-budget.json`.

## Frozen identity and launch packet

- model revision: `bcd9f01ddc9cff2316eb84281bebcd5b058bddce`;
- vLLM: `e5137bfd8ca2ca718c4fd93d86d54bb843e2999b`;
- XPU kernels: `ad25aa9f69a2171612b9c6b83dfa82c69559f9e4`;
- staged runtime build: `2f829747503c77d4814834dffd0840fb1dd9f75a`;
- campaign: `qwen38-flash-next-fp8-tp4-ep4-eager-mtp0-4352-ple-only-r1`,
  attempt 9, port 19681;
- launcher: `tools/launch-tp4-mtp0-4352-ple-only-a9.sh`;
- client: `tools/run-tp4-mtp0-4352-ple-only-a9-client.sh`;
- supervisor: `tools/supervise-tp4-mtp0-4352-ple-only-a9.sh`.

Each wrapper binds the checksum of its frozen source and the checksum of the
derived executable. The supervisor additionally binds the exact launcher and
client wrapper hashes. No GPU launch is authorized until these files, this
note, and the static budget are committed on `main`.

## Required gates

The launch must pass exact source, runtime, model, four-card discovery,
per-card idle-memory, and four-rank collective gates. It must then report four
exact 11.92-GiB PLE-only offload receipts, become healthy, expose at least
4,224 cache tokens, and retain the frozen served identity.

The client must pass the recovery canary, the established seven-case semantic
battery (allowing only the already known `code_execution=30` model boundary),
16/16 one-hash repeats, the exact cache-zero 4K needle, three p146/o256 rows,
and two exact p4096/o128 rows. All three short rows must match
`5f40744644b98ddd58a0c202fe855af324c0b1c33e1a6275afd74c12488f89f0`.
Both exact-4K rows must match
`1d833e5f463366223a669aa15495840d1337b173e675a9ea04f00a5ae339d5cc`.
The supervisor must own shutdown and pass the residue, four-card idle, and
B70-addressed journal gates.

Protected comparison points are 5.223788770075911 tok/s for the short median
and 4.7578181021380175 tok/s for the exact-4K median. A candidate is a speed
win only after every correctness, repeatability, identity, and lifecycle gate
passes. The old rows remain authoritative unless and until a separately
reviewed promotion changes presentation.

## Frozen interpretations

- Failure before health or cache admission: bounded fit/startup negative; no
  unchanged retry.
- Any unexpected output, semantic boundary, cache reuse, or repeat mismatch:
  reject as non-lossless.
- Any lifecycle or B70 postflight failure: quarantine; no deployment or speed
  credit.
- Full pass at equal or lower speed: valid placement evidence, but retain the
  previous decode recipe as preferred.
- Full pass above a protected median: additive promotion candidate. Preserve
  all earlier results and record the exact deltas.

If fit fails, restore the already proven PLE-plus-input-embedding placement.
That fallback costs only about 1.271 GB more host RAM across four ranks and is
not a regression or a reason to alter prior results. No MTP, graph, 8K+,
prefill, website, or LocalMaxxing action is part of this arm.
