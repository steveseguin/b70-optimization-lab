# Qwen3.8 Q8 c2 quality isolation and dual-process result

Date: 2026-08-16  
Disposition: closed; neither route is promoted

## Single-process fusion isolation

The accepted `--parallel 2` server is exact for fixed prompt pair 0/1 but
schedule-dependent for pair 2/3. Three same-binary ablations tested whether a
lab fusion family was the source. Every request was cache-cold.

| Disjoint pair 2/3 arm | Aggregate conventional | Sequential hashes retained | Concurrent exact |
| --- | ---: | ---: | ---: |
| recurrent/GDN fusion family off | `57.005784 tok/s` | 2/2 | 0/2 |
| attention/QK fusion family off | `57.103579 tok/s` | 2/2 | 0/2 |
| all custom fusion off + Q8 two-row split to 1+1 | `54.402614 tok/s` | 1/2 | 0/2 |

Neither targeted family repairs the quality boundary. Broad fusion removal is
not a valid fallback: it still diverges under concurrency and changes one
single-request output from the accepted oracle. Combined with the separate
Q8-MMVQ row-split result, the c2 schedule sensitivity is not attributable to
one transferable lab fusion.

## Two independent TP2 processes

Two accepted `--parallel 1` servers were then loaded on the same two cards.
This preserves independent sequential arithmetic and avoids cross-request
batching. It fit safely:

- combined GPU allocation: `27390.46 MiB` and `27245.00 MiB`;
- process RSS: `684728 KiB` and `708728 KiB`;
- about 4.6–4.8 GiB of VRAM remained per card.

The dedicated
[`capture-target-only-dual-process.py`](../scripts/capture-target-only-dual-process.py)
harness recorded a cache-cold sequential oracle on each process, then released
the two 256-token streams through one barrier.

| Metric | Process 0 | Process 1 |
| --- | ---: | ---: |
| Sequential decode | `35.930344 tok/s` | `35.900248 tok/s` |
| Concurrent decode | `7.470598 tok/s` | `7.450620 tok/s` |
| Exact to own sequential oracle | yes | yes |

Aggregate conventional throughput was only **`14.890992 tok/s`** and aggregate
wall throughput was `14.767426 tok/s`. The route is quality-exact and
memory-feasible, but simultaneous TP2 processes contend catastrophically on
the shared device/collective path. It is substantially worse than one process
and cannot serve as the quality-preserving 40 tok/s route.

Both processes shut down cleanly with `VERIFY_MISMATCH=0`. GPU memory returned
to `151/42 MiB`, both cards reported normal, and the current boot log had no new
Xe fault, reset, hang, device-lost, or CAT error.

Structured evidence and raw hashes are in
[`2026-08-16-q8-c2-quality-isolation-and-dual-process.json`](../data/2026-08-16-q8-c2-quality-isolation-and-dual-process.json).

## Decision

Do not retry simple fusion-family ablations or two independent TP2 server
copies. The useful target-only work returns to one active stream and the
fused MMVQ/collective critical path. The existing narrow `57.398122 tok/s` c2
capture remains labeled prompt-specific and must not be promoted as a general
quality result.
