# Packet73 offline decision

The starting engine is packet70: wide64 experts, packet60 target HC,
packet59 draft HC, batch rollback, 24/24 target placement, full BF16 KV,
and `iq3-p49-split32-v1`. Packet72's measured in-engine bandwidth table
places HC and the two expert kernels well below the dense projections.
Those measurements motivate this packet; none is a packet73 speed result.

## Accepted for an in-engine screen

| View / changed kernel | Configured GRFs | Static instructions | Static load instructions | Spill metadata / spill-fill messages |
| --- | ---: | ---: | ---: | --- |
| production HC gate+mix | 128 | 2,166 | 24 | none |
| hc-wide gate+mix | 128 | 2,369 | 28 | none |
| production wide64 IQ2 | 128 | 1,993 | 51 | none |
| experts2-a IQ2 | 128 | 2,072 | 54 | none |
| production wide64 IQ4 | 128 | 2,981 | 79 | none |
| experts2-b IQ4 | 128 | 1,692 | 43 | none |

[Exact reports](register-report.json) retain assembly hashes and compiler
commands through the two translation-unit reports. Counts include control
flow and epilogues; they are static, not executed counts or memory traffic.
Configured GRFs are not measured resident occupancy. Linked library settings
slightly change the IQ4 baseline instruction count relative to packet65's
older unlinked report; both sides here use the same compiler path.

**HC:** each subgroup computes two adjacent output rows of one stream.
Both rows retain all original 32 logical lanes, their `k,j` sequence and their
original adjacent reduction tree. Their input BF16 vector is loaded once;
each row's two code words use a single packed vector read, and both rows'
raw operands are read before arithmetic. The dot body needs five raw load
instructions for two rows, versus eight for two independent production rows.
The complete kernel above has 28 static loads versus 24, but produces four
mixed output positions per workgroup versus two. Do not compare those totals
as if each kernel did the same amount of work. There are 640 WG256 groups,
versus production's 1,280. Streams remain in different subgroups, with the
original shared-memory gate/mix boundary. No decoded weight buffer is added.
The row pitch is 380 bytes, including the retained original half metadata.

**Expert A:** two IQ2 raw block spans are fetched before either block is
consumed. Each span already shares codes, high bits, scales and a half across
eight adjacent logical chains. It retains the original step/chain/j sums and
WG64 mapping. The three extra static loads and modest code growth are accepted
for one orthogonal screen of deeper load issue. They do not establish overlap,
more outstanding requests, better occupancy or a speed improvement. Down stays
wide64.

**Expert B:** two adjacent IQ4 blocks share one 32-byte code read and one
four-byte half-scale read, covering eight logical chains. The sixteen-chain
physical lane consumes two such spans. K640's last 128 elements stay bounded.
Gate/up stays wide64. This cuts static down loads 79 to 43, with no spill.
A four-block/64-byte version spilled and is rejected.

`combined` is HC plus expert B, selected before device results because B has
the clear load-count reduction. It does not silently include expert A.
All five views share one binary and fixed arithmetic, weights, draft and placement.

## Offline method correction

A raw TU translated straight to SPIR-V leaves `fmaf` unresolved. That produced
indirect calls and false stack-pressure evidence in HC's deterministic sigmoid.
The final report follows the compiler's device-library link step, then
`sycl-post-link`, SPIR-V translation and CPU-only `ocloc` for BMG-G31, with
correctly rounded divide/sqrt. Libraries and their hashes are retained.
SPV_KHR_fma is disabled in translation because this ocloc does not accept that
new extension; the supported standard instruction translation remains.
No platform device is opened by this workflow.

The virtual-four-chain HC arm still spilled flags after proper linking and
was rejected. Its four streams were separate subgroups, but the simpler
accepted two-output approach avoids virtualization entirely. A first two-row
implementation had a wrong 360-byte stride; the GNU fixture caught it on
finite inputs. Correcting it to the unchanged 380-byte layout and sharing
reduction predicates removed that mismatch and all remaining flag spills.
[Negative index](DO-NOT-REPEAT.md) and retained sources preserve these attempts.

GNU and Intel each pass 44 operator cases twice, 118,784 raw FP32 chain checks
and 3,456 raw FP32 tree checks per run. Fixtures include production shapes,
row tails, invalid routes, disabled/error states, invalid position, NaN
payloads, infinities, signed zeros and subnormals. These are small operator
fixtures, not CPU model runs. Device full-model identity remains pending.
