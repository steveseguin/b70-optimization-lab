# Packet163 — widen both IQ3 records to prompt reading and complete answers

Prepared two private measurement packets under
[packet163-full-gate](../experiments/own-xpu-runtime/stage2/packet163-full-gate/README.md).
No GPU work, model payload reads, services, queue changes, sudo or settings
changes occurred. Existing packet trees and shared operations code were left
untouched. Compilation used the shared compiler turn and waited through the
protected timing window. CPU work used the assigned cores and nice19; observed
compiler/probe memory remained below4GB.

The two-card packet uses packet136 bundle8, 58.798109 tok/s. Packet155 bundle9
stopped at W0p with `shared extent`, before timing, and is parked in its own
[work note](2026-10-19-own-runtime-packet155.md). It did not replace the record.
The one-card packet uses packet58aj, 31.966820 tok/s. Both numbers remain the
existing128-token records. New512-token prefill and complete-answer speeds are
still unmeasured.

Each proposed row loads once, runs one512-input-token prefill request, then the
full twelve-prompt realistic suite with a512-token response cap and natural EOS.
Every request starts with reset request state and zero cached tokens. Each
proposal has a second fresh load that compares every output token. Two-card A
and B are alternative proposals; one-card uses A with the whole host reserved.
Nothing was queued.

The prefill input follows the existing tokenizer-and-truncate method in
`experiments/qwen38-27b-b70/scripts/bench-prefill-followup.py`, using an unrepeated
real prose excerpt from its frozen corpus. The official tokenizer reproduced
all twelve registered suite token sequences before constructing the new input.
Prefill reports512 input tokens divided by the native prompt-loop time through
the first generated token. TTFT remains separate. The primary decode rate uses
99 intervals between events1 and100, summarized by prompt-class medians. Reports
also retain mean, p10, all-prompt median, wall rate, complete natural generation,
cap-limited generation, token timestamps and hashes.

The packet49 oracle covers128 tokens. Those tokens must match exactly. Output
beyond128 is labeled determinism-checked only after matching fresh loads; it is
never called oracle-exact. Extending the oracle was not feasible within this
preparation window: the original128-token CPU run took over six hours. The
independent full-output quality and publication gates remain unfinished.

The native parser originally rejected caps above128. The one-card native suite
also rejected more than12 requests. Private entry builds widen only these
admission bounds (512 tokens;13 one-card requests), relocate constant paths, and
add pre-device `--help`. Source reversal checks prove that all other source
bytes match the parents; all linked kernel objects retain their original hashes.
Selection, dispatch, target arithmetic and BF16 KV are unchanged. Every native
flag was checked against the built executable's help.

Both CPU preparation probes passed under the actual loader environment and a
Landlock policy denying model files and GPU devices. They use CPU transport and
synthetic/opaque weights, so they make no GPU arithmetic or speed claim. The
one-card probe includes resident lookup preparation and first-decode sites. The
two-card probe covers both ranks at positions0,1,511,512. The largest measured
probe RSS was about1.11GB. Device-path imports passed for one-card A and two-card
A/B. The analyzer reproduces both real parent rates; synthetic512 report tests
also pass, including malformed-stream, cache, oracle and repeat refusal cases.

The review caught two further preparation mistakes and they were corrected:
two-card rank timing streams are checked after RESET closes their buffers, and
heavy trace analysis is deferred until devices have drained. The native wait is
explicitly600 seconds; the two-card controller wait is1200 seconds. No stream
proof is tied to a wall-clock deadline. Stop handling remains graceful and never
automatically retries a failed stage.

All six rows pass `lanequeue plan`; all three proposal files pass
`ops/rehearse_entry.py --report`. Shared report fixtures are64/128-token synthetic
inputs and remain strict512=false; separate local tests cover the512 report.
The shared preparation subcheck retains a warning because its frozen schema
cannot admit the one-card argv or private4MB rotary file. The separate sandboxed
preparation probes supply that evidence. No warning was hidden or converted into
a device-quality pass.

Device free-space floor is25GB; CPU stop is27GB. Per-load reservations are
1,222,788,768 bytes for two cards and57,141,252 bytes for one card. These are twice
an explicitly scaled512 write estimate from measured parent files, including
raw state or driver-cache costs. They are not measured512 write totals. Every
fresh load checks disk space again.

The two private4MiB rotary tables are deliberately retained in Git because each
engine resolves its own source-relative constant path. Their restoration hashes
and source paths are recorded. Build binaries, objects, compiler caches and probe
scratch stay out of Git; exact build commands and a hash-checking local restore
script are retained. This is a local preparation packet, not a public recipe.

Final READY markers are written after all CPU checks and seals. Actual512 runs,
long-output oracle extension and any quality decision remain future work.

## Packet165c — one-card idle I/O launch repair

The one-card native command now runs under `/usr/bin/ionice -c3`, matching
packet58aj. The old packet163 attempt refused before reading model bytes or
starting compute; its evidence is preserved. Binary, model, arithmetic,
full-precision KV, requests, waits and budgets are unchanged.

Both proposals have fresh `p165c` names and `device-p165c-*` output paths, with
the second load referencing its new first load. All four real entry/worker
sequences pass the intercepted exec gate: the real ionice child reports Linux
I/O class3, every native flag is accepted by built help, imports use the closed
launch environment, all request streams and oracle prefixes pass, and the
analyzer reproduces real parent device evidence. The CPU native fixture passes
56 resets and224 sensor checks across the four registered sequences. Only that
CPU test fixture was compiled; production binaries were unchanged.

Temporary lanequeue plans and shared report rehearsals pass. The first plan's
stale READY proposal-pin refusal is retained; pending markers deny launch until
final checks complete. Existing shared preparation-adapter warnings remain
visible. Final READY files are written last with `ready_for_device=true`.
No GPU, model read, service, sudo, host setting or live queue changed. Work used
nice19, cores8–15/24–31, Python `-B`, stdin `/dev/null`, under4GB memory and a
26MB CPU fixture build. The unrelated dirty workspace was preserved.

[Repair, checks and retained prior identities](../experiments/own-xpu-runtime/stage2/packet165c-ionice/README.md).
