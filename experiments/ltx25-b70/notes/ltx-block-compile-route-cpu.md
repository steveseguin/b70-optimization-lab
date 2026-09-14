# One native block compiler through unchanged shard routing

Status: **CPU unit/capture gate passed; inactive, no XPU or checkpoint result.**
The [additive ownership follow-up](ltx-block-compile-ownership-guard.md) preserves
this original gate and adds 51 checks, including the compiler callback itself
in the options registry. Its remaining lifecycle limitations are explicit.

The [new helper](../scripts/test-ltx-block-compile-route.py) tests the
[inactive adapter](../scripts/ltx_block_compile.py) against the frozen LTXAV
implementation without changing the original compiler tests, shard helper,
running server or pending encoder runtime packet.

The [receipt](../data/ltx-block-compile-route-cpu-01.json) and
[log](../data/ltx-block-compile-route-cpu-01.log) retain the complete result.
All source hashes recorded before import were checked against the files after
completion and still matched. This includes the adapter's strict deterministic
mode guard. No failed run or geometry sweep preceded this receipt.

## Boundary being tested

`CompiledBlockRoute` wraps one original `_BlockRoute`. It supplies an adapter
as `extra['original_block']`; the original route performs transfers and enters
the device context before calling the compiled block, then handles any final
return transfer. The compiled callable remains outside the registered model
tree. Neither the module's `forward` nor its registered weights are replaced.

The native closure is extracted directly from the pinned `av_model.py` AST
for an independent argument-mapping comparison. A recorder checks each supplied
argument by identity, including absent and present optional self-attention mask
and prompt timesteps. The test therefore does not merely compare two manually
copied argument lists.

The earlier native CPU fixture generator is extracted from its recorded helper
AST without executing that helper's main function. Its synthetic BF16 block
has 32-wide video/audio channels and one head, with all native self-attention,
text attention, cross-modal attention, gated attention, ADaLN, RoPE and
feedforward arithmetic intact. This remains a small unit fixture, not a model
generation at reduced resolution or a claim about the production matrix sizes.

## Result

All **29 checks passed**, including:

- Exact native closure argument mapping and required compiler settings.
- Ownership across a synthetic 48-block LTXAV shell partitioned by the original
  shard installer; only one callback changes on the clone. Parent and sibling
  callbacks, registered tensor identities, shapes, dtypes and byte totals remain
  unchanged when restoring the original route.
- Rejection of an additional compiled block, invalid index, restoration without
  a compiler, foreign block/route types and extra module hooks.
- Per-forward cache cleanup on success and exception, with distinct caches
  between calls.
- Actual compiled route execution at 64 and 256 video tokens, 26 audio tokens,
  and independent seeds 17 and 123. Both output streams matched the eager route
  byte for byte and repeated exactly.

The compiled calls received nonempty `transformer_options`: the block callback
registry, diffusion wrapper registry, callback registry, conditioning marker,
sigma tensors, original shape and native branch flags. Each per-forward transfer
cache also contained a retained source/destination pair. No options were removed
and no guard filter was installed. Construction and routing stayed outside
compilation; native `CompressedTimestep` arithmetic stayed inside the block.

Dynamo recorded **two compiled graphs, 986 captured calls and zero graph
breaks**, with two successful AOT/Inductor compilations. The screen requires
those coverage counters, so silent eager execution cannot qualify through
output equality alone. Main-process peak RSS was **1,155,792 KiB**, approximately
1.10 GiB; this is not summed compiler-process peak memory.

The test used one compiler worker, one CPU compute thread, full-graph static
compilation, eager BF16 rounding emulation and eager division rounding. CUDA
graphs and autotuning were disabled. Temporary compiler caches were removed.

## Limits and next gate

Both route devices are CPU in this test. It verifies callback composition and
ownership, but cannot prove cross-XPU transfer semantics, native large-matrix
lowering, actual checkpoint parity, device memory behavior or performance.
The rich callback registry uses ordinary route objects; production compilation
also needs qualification when that registry contains the compiler callback
itself. Masked attention and altered numerical branch flags remain unqualified.

The next compiler gate is an explicitly bounded native-weight one-block XPU
experiment with the same full options, followed by original four-output
full-clip comparison. This CPU pass does not authorize silently adding the
compiler to the separately prepared encoder experiment or replacing its server.

Run from the repository root with a new evidence path:

```bash
/home/steve/.venvs/ltx25-baseline/bin/python \
  experiments/ltx25-b70/scripts/test-ltx-block-compile-route.py \
  --output /tmp/ltx-block-route-cpu-new.json
```

The helper records exceptions and current phase/case in an exclusive receipt
and stops without changing compiler options or retrying the workload.
