# Packet 55: one-card feasibility measurements

CPU preparation for the owner's one-card and two-card IQ3 engine project.
This packet prepares three measurements; **no GPU or throughput window was
run by the preparer**. Packet49c's record and packet49d's separate work remain
unchanged. This is the Unsloth UD-IQ3_XXS quantized compressed version, with
the packet49 `iq3-p49-split32-v1` arithmetic and full BF16 KV.

Preparation passed: two fresh 54,001-check CPU expert runs; native/host route
builds; controller token/state/reset checks; four route, three H2D and nine
offline-analysis tests. [Final source/binary checks](preparation-check.json),
[independent review](REVIEW-INDEPENDENT.md), [preparation closeout](CPU-PREPARATION-CLOSEOUT.md).

| Component | What it establishes | Coordinator work |
| --- | --- | --- |
| [Route diagnostic](route/) | Separate packet49c overlay; target and draft IDs/weights; independent 24-prompt calibration set | Cards 2+3, one sanity check against packet49 oracle, then 256-token-cap calibration |
| [CPU experts](cpu/README.md) | Eight output rows per AVX2 vector, exact production order; CPU fixture equality | Quiet 1/4/8/12/16-thread throughput and measured 4/6/10-miss batches |
| [Expert streaming](h2d/README.md) | Dedicated copy-engine probe with verified payload and concurrent compute | Card 2 or 3, two fresh windows, both expert sizes, 4–10 slabs |
| [Offline cache analysis](analysis/) | LRU, LFU and static cache policy trained on half the independent prompts | Replay held-out traces without a GPU |

The [decision equations](../../ONE-CARD-FEASIBILITY.md) explain how these
inputs constrain CPU misses, streamed misses and a hybrid, with MTP sharing
the same card. Missing values remain missing. Twenty-four GB is a cache
sensitivity point, not an admitted one-card allocation.

All local commands use `nice -n 19 taskset -c 4-15,20-31`, with `python3 -B`
for Python. One compiler runs at a time. No power, page-cache, swap, services,
memory fence or driver state is changed. The coordinator starts long GPU
windows in its own systemd user unit and chooses actual device ownership.
Physical card 2 is `0000:43:00.0`; card 3 is `0000:47:00.0`. Other-card work
does not establish enough host-memory headroom for two additional model owners.

Every packet55 measurement window holds the same exclusive `window.lock`.
This only coordinates packet55. The quiet CPU benchmark requires **all** GPU
windows, including packet49d, to remain stopped throughout. Route and H2D
windows require their selected cards to be free, and coordinator scheduling
still governs foreign jobs. No automatic retries or device resets occur.

The target model path is the owner's admitted IQ3 directory. Packet49c's
existing MTP weights are at a different official-model path; route execution
requires the owner's narrow exception for those existing hash-bound weights.
Preparation does not read that draft source. A command-line acknowledgment
records a decision already made; it is not permission by itself.

Build trees are ignored and reproducible from scripts/receipts. The entire
packet55 retained build must stay below 1 GB. Keep raw route records in binary
and derived logs compressed. Do not commit large generated binaries or model
payloads. The CPU benchmark pins no memory; the streaming probe pins at most
23,300,096 bytes. Retain failed attempts and interrupted-window evidence.

Credit Niko1221 / Strata for the GPU hot-expert cache and CPU-miss idea already
documented in [ONE-CARD-DESIGN](../../ONE-CARD-DESIGN.md). Implementations are
independent lab code, using only the lab's existing arithmetic and fixtures
and Intel platform dependencies. [Task record](../../../../notes/2026-10-17-own-runtime-packet55.md).
